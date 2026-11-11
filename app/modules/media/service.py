from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceConflict, ResourceNotFound
from app.models import MediaAsset
from app.modules.media.repository import MediaRepository
from app.modules.media.schemas import (
    MediaCreate,
    MediaListQuery,
    MediaPage,
    MediaResponse,
    MediaUpdate,
)


class MediaService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = MediaRepository(session)

    @asynccontextmanager
    async def _write(self) -> AsyncIterator[None]:
        """Commit the request transaction, including the authentication read."""
        try:
            yield
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_media_asset_storage":
                raise ResourceConflict("This storage object is already registered") from exc
            if constraint in ("fk_project_media_media", "fk_project_section_media_media"):
                raise ResourceConflict("Media asset is still referenced") from exc
            raise
        except BaseException:
            await self.session.rollback()
            raise

    async def _get(self, asset_id: UUID, *, lock: bool = False) -> MediaAsset:
        asset = await self.repository.get(asset_id, lock=lock)
        if asset is None:
            raise ResourceNotFound("Media asset not found")
        return asset

    async def list(self, query: MediaListQuery) -> MediaPage:
        assets, total = await self.repository.list(query)
        return MediaPage(
            items=[MediaResponse.model_validate(asset) for asset in assets],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get(self, asset_id: UUID) -> MediaResponse:
        return MediaResponse.model_validate(await self._get(asset_id))

    async def create(self, body: MediaCreate) -> MediaResponse:
        if body.storage_provider in {"local", "r2"}:
            raise InvalidOperation("Managed storage assets require upload confirmation")
        values = body.model_dump(mode="json")
        values["asset_metadata"] = values.pop("metadata")
        async with self._write():
            asset = await self.repository.create(values)
            response = MediaResponse.model_validate(asset)
        return response

    async def update(self, asset_id: UUID, body: MediaUpdate) -> MediaResponse:
        values = body.model_dump(mode="json", exclude_unset=True)
        if "metadata" in values:
            values["asset_metadata"] = values.pop("metadata")
        async with self._write():
            asset = await self._get(asset_id, lock=True)
            if asset.storage_provider in {"local", "r2"} and "asset_metadata" in values:
                supplied = values["asset_metadata"]
                if isinstance(supplied, dict) and "_storage" in supplied:
                    raise InvalidOperation("Storage policy cannot be edited through metadata")
                preserved = (asset.asset_metadata or {}).get("_storage")
                values["asset_metadata"] = dict(supplied or {}) | {"_storage": preserved}
            await self.repository.update(asset, values)
            response = MediaResponse.model_validate(asset)
        return response

    async def delete(self, asset_id: UUID) -> None:
        async with self._write():
            # FOR UPDATE also serializes against new references taking a FK key-share lock.
            asset = await self._get(asset_id, lock=True)
            if await self.repository.is_referenced(asset_id):
                raise ResourceConflict("Media asset is still referenced")
            await self.repository.delete(asset)
