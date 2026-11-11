from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaAsset, Profile, ProjectMedia, ProjectSectionMedia
from app.modules.media.schemas import MediaListQuery


class MediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, asset_id: UUID, *, lock: bool = False) -> MediaAsset | None:
        query = select(MediaAsset).where(MediaAsset.id == asset_id)
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def list(self, query: MediaListQuery) -> tuple[list[MediaAsset], int]:
        rows = select(MediaAsset)
        if query.type is not None:
            rows = rows.where(MediaAsset.type == query.type.value)
        if query.q is not None:
            rows = rows.where(
                or_(
                    MediaAsset.original_filename.icontains(query.q, autoescape=True),
                    MediaAsset.title.icontains(query.q, autoescape=True),
                    MediaAsset.alt_text.icontains(query.q, autoescape=True),
                )
            )
        total = await self.session.scalar(select(func.count()).select_from(rows.subquery()))
        column = {
            "created_at": MediaAsset.created_at,
            "original_filename": func.lower(MediaAsset.original_filename),
            "file_size": MediaAsset.file_size,
        }[query.sort]
        order = column.asc() if query.direction == "asc" else column.desc()
        result = await self.session.scalars(
            rows.order_by(order, MediaAsset.id.desc()).limit(query.limit).offset(query.offset)
        )
        return list(result), int(total or 0)

    async def create(self, values: dict[str, object]) -> MediaAsset:
        asset = MediaAsset(**values)
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset)
        return asset

    async def update(self, asset: MediaAsset, values: dict[str, object]) -> None:
        for name, value in values.items():
            setattr(asset, name, value)
        await self.session.flush()
        await self.session.refresh(asset)

    async def is_referenced(self, asset_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    or_(
                        exists().where(ProjectMedia.media_id == asset_id),
                        exists().where(ProjectSectionMedia.media_id == asset_id),
                        exists().where(Profile.profile_media_id == asset_id),
                        exists().where(Profile.cv_media_id == asset_id),
                    )
                )
            )
        )

    async def delete(self, asset: MediaAsset) -> None:
        await self.session.delete(asset)
        await self.session.flush()
