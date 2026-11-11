from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceNotFound
from app.models import ProjectSection, ProjectSectionMedia
from app.modules.portfolio.schemas import Page, PageQuery, Reorder
from app.modules.portfolio.section_repository import SectionRepository
from app.modules.portfolio.section_schemas import (
    SectionCreate,
    SectionMediaInput,
    SectionMediaResponse,
    SectionMediaUpdate,
    SectionResponse,
    SectionUpdate,
)
from app.modules.portfolio.service import ProjectService
from app.modules.portfolio.transactions import write_transaction


class SectionService:
    """Serialize section edits on the parent project, validating the complete resulting state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectService(session)
        self.persistence = self.projects.repository
        self.repository = SectionRepository(session)

    async def require(self, project_id: UUID, section_id: UUID) -> ProjectSection:
        section = await self.repository.get(project_id, section_id)
        if section is None:
            raise ResourceNotFound("Project section not found")
        return section

    async def _link(self, section_id: UUID, media_id: UUID) -> ProjectSectionMedia:
        row = await self.repository.link(section_id, media_id)
        if row is None:
            raise ResourceNotFound("Section media link not found")
        return row

    async def _assets(self, items: list[SectionMediaInput]) -> None:
        for item in sorted(items, key=lambda item: item.media_id):
            if await self.persistence.asset(item.media_id) is None:
                raise ResourceNotFound("Media asset not found")

    async def _validate(self, section: ProjectSection) -> None:
        types = await self.repository.media_types(section.id)
        count = sum(types.values())
        expected = {
            "IMAGE": "IMAGE",
            "GALLERY": "IMAGE",
            "SPLIT": "IMAGE",
            "VIDEO": "VIDEO",
            "MODEL_3D": "MODEL_3D",
        }.get(section.section_type)
        if count > 100:
            raise InvalidOperation("A section may contain at most 100 media assets")
        if types and (expected is None or set(types) != {expected}):
            raise InvalidOperation("Media types are incompatible with the section type")
        if section.section_type in {"IMAGE", "VIDEO", "MODEL_3D", "SPLIT"} and count > 1:
            raise InvalidOperation("This section type supports only one media asset")
        if section.is_visible:
            if (
                section.section_type in {"TEXT", "QUOTE", "SPLIT"}
                and not (section.content or "").strip()
            ):
                raise InvalidOperation("Visible text, quote and split sections require content")
            if expected is not None and count == 0:
                raise InvalidOperation("Visible media sections require a compatible asset")

    async def list(self, project_id: UUID, query: PageQuery) -> Page[SectionResponse]:
        await self.projects.require_project(project_id)
        rows, total = await self.repository.sections(project_id, query)
        return Page(
            items=[SectionResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get(self, project_id: UUID, section_id: UUID) -> SectionResponse:
        await self.projects.require_project(project_id)
        return SectionResponse.model_validate(await self.require(project_id, section_id))

    async def create(self, project_id: UUID, body: SectionCreate) -> SectionResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self._assets(body.media)
            row = ProjectSection(project_id=project_id, **body.model_dump(exclude={"media"}))
            await self.persistence.save(row)
            await self.repository.replace_media(row.id, body.media)
            await self._validate(row)
            response = SectionResponse.model_validate(row)
        return response

    async def update(
        self, project_id: UUID, section_id: UUID, body: SectionUpdate
    ) -> SectionResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            row = await self.require(project_id, section_id)
            if body.media is not None:
                await self._assets(body.media)
                await self.repository.replace_media(row.id, body.media)
            for key, value in body.model_dump(exclude_unset=True, exclude={"media"}).items():
                setattr(row, key, value)
            await self._validate(row)
            await self.persistence.save(row)
            response = SectionResponse.model_validate(row)
        return response

    async def delete(self, project_id: UUID, section_id: UUID) -> None:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self.persistence.remove(await self.require(project_id, section_id))

    async def list_media(
        self, project_id: UUID, section_id: UUID, query: PageQuery
    ) -> Page[SectionMediaResponse]:
        await self.projects.require_project(project_id)
        await self.require(project_id, section_id)
        rows, total = await self.repository.media(section_id, query)
        return Page(
            items=[SectionMediaResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def attach(
        self, project_id: UUID, section_id: UUID, body: SectionMediaInput
    ) -> SectionMediaResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            section = await self.require(project_id, section_id)
            await self._assets([body])
            row = ProjectSectionMedia(section_id=section_id, **body.model_dump())
            await self.persistence.save(row)
            await self._validate(section)
            response = SectionMediaResponse.model_validate(row)
        return response

    async def update_media(
        self, project_id: UUID, section_id: UUID, media_id: UUID, body: SectionMediaUpdate
    ) -> SectionMediaResponse:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            await self.require(project_id, section_id)
            row = await self._link(section_id, media_id)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.persistence.save(row)
            response = SectionMediaResponse.model_validate(row)
        return response

    async def detach(self, project_id: UUID, section_id: UUID, media_id: UUID) -> None:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            section = await self.require(project_id, section_id)
            await self.persistence.remove(await self._link(section_id, media_id))
            await self._validate(section)

    async def reorder(
        self, project_id: UUID, body: Reorder, section_id: UUID | None = None
    ) -> None:
        """For section media ordering, item.id identifies the asset's composite-key component."""
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            if section_id is not None:
                await self.require(project_id, section_id)
            for item in body.items:
                row = (
                    await self.require(project_id, item.id)
                    if section_id is None
                    else await self._link(section_id, item.id)
                )
                row.sort_order = item.sort_order
                await self.persistence.save(row)
