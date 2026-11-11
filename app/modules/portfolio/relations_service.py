from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceConflict, ResourceNotFound
from app.models import ProjectAttribute, ProjectMedia
from app.modules.portfolio.repository import ChildKind
from app.modules.portfolio.schemas import (
    AttributeCreate,
    AttributeResponse,
    AttributeUpdate,
    CoverSelection,
    MediaAttach,
    MediaLinkResponse,
    MediaLinkUpdate,
    Page,
    PageQuery,
    Reorder,
)
from app.modules.portfolio.service import ProjectService
from app.modules.portfolio.transactions import write_transaction


class ProjectRelationsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectService(session)
        self.repository = self.projects.repository

    async def _child(
        self, kind: ChildKind, project_id: UUID, item_id: UUID
    ) -> ProjectAttribute | ProjectMedia:
        row = await self.repository.child(kind, project_id, item_id)
        if row is None:
            raise ResourceNotFound("Project attribute or media link not found")
        return row

    async def _validate_asset(self, media_id: UUID, role: str) -> None:
        asset = await self.repository.asset(media_id)
        if asset is None:
            raise ResourceNotFound("Media asset not found")
        if role == "COVER" and asset.type != "IMAGE":
            raise InvalidOperation("Project covers must use an image asset")

    async def list_attributes(self, project_id: UUID, query: PageQuery) -> Page[AttributeResponse]:
        await self.projects.require_project(project_id)
        rows, total = await self.repository.children("attributes", project_id, query)
        return Page(
            items=[AttributeResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def add_attribute(self, project_id: UUID, body: AttributeCreate) -> AttributeResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            row = ProjectAttribute(project_id=project_id, **body.model_dump())
            await self.repository.save(row)
            response = AttributeResponse.model_validate(row)
        return response

    async def update_attribute(
        self, project_id: UUID, item_id: UUID, body: AttributeUpdate
    ) -> AttributeResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            row = await self._child("attributes", project_id, item_id)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = AttributeResponse.model_validate(row)
        return response

    async def delete_attribute(self, project_id: UUID, item_id: UUID) -> None:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self.repository.remove(await self._child("attributes", project_id, item_id))

    async def list_media(self, project_id: UUID, query: PageQuery) -> Page[MediaLinkResponse]:
        await self.projects.require_project(project_id)
        rows, total = await self.repository.children("media", project_id, query)
        return Page(
            items=[MediaLinkResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def attach(self, project_id: UUID, body: MediaAttach) -> MediaLinkResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self._validate_asset(body.media_id, body.role)
            row = ProjectMedia(project_id=project_id, **body.model_dump())
            await self.repository.save(row)
            response = MediaLinkResponse.model_validate(row)
        return response

    async def update_media(
        self, project_id: UUID, item_id: UUID, body: MediaLinkUpdate
    ) -> MediaLinkResponse:
        async with write_transaction(self.session):
            project = await self.projects.require_project(project_id, lock=True)
            row = await self._child("media", project_id, item_id)
            assert isinstance(row, ProjectMedia)
            if body.role is not None and body.role != row.role:
                if row.role == "COVER" and project.status == "PUBLISHED":
                    raise ResourceConflict("Replace the cover or unpublish the project first")
                await self._validate_asset(row.media_id, body.role)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = MediaLinkResponse.model_validate(row)
        return response

    async def detach(self, project_id: UUID, item_id: UUID) -> None:
        async with write_transaction(self.session):
            project = await self.projects.require_project(project_id, lock=True)
            row = await self._child("media", project_id, item_id)
            assert isinstance(row, ProjectMedia)
            if row.role == "COVER" and project.status == "PUBLISHED":
                raise ResourceConflict("Replace the cover or unpublish the project first")
            await self.repository.remove(row)

    async def select_cover(self, project_id: UUID, body: CoverSelection) -> MediaLinkResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self._validate_asset(body.media_id, "COVER")
            previous = await self.repository.cover(project_id)
            if previous is not None and previous.media_id == body.media_id:
                response = MediaLinkResponse.model_validate(previous)
            else:
                if previous is not None:
                    await self.repository.remove(previous)
                row = ProjectMedia(
                    project_id=project_id, media_id=body.media_id, role="COVER", sort_order=0
                )
                await self.repository.save(row)
                response = MediaLinkResponse.model_validate(row)
        return response

    async def reorder(self, kind: ChildKind, project_id: UUID, body: Reorder) -> None:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            for item in body.items:
                row = await self._child(kind, project_id, item.id)
                row.sort_order = item.sort_order
                await self.repository.save(row)
