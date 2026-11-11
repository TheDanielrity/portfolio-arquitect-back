from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaAsset, ProjectSection, ProjectSectionMedia
from app.modules.portfolio.schemas import PageQuery
from app.modules.portfolio.section_schemas import SectionMediaInput


class SectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, project_id: UUID, section_id: UUID) -> ProjectSection | None:
        return await self.session.scalar(
            select(ProjectSection).where(
                ProjectSection.project_id == project_id,
                ProjectSection.id == section_id,
            )
        )

    async def sections(
        self, project_id: UUID, query: PageQuery
    ) -> tuple[list[ProjectSection], int]:
        condition = ProjectSection.project_id == project_id
        total = await self.session.scalar(
            select(func.count()).select_from(ProjectSection).where(condition)
        )
        rows = await self.session.scalars(
            select(ProjectSection)
            .where(condition)
            .order_by(ProjectSection.sort_order, ProjectSection.id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(rows), int(total or 0)

    async def media(
        self, section_id: UUID, query: PageQuery
    ) -> tuple[list[ProjectSectionMedia], int]:
        condition = ProjectSectionMedia.section_id == section_id
        total = await self.session.scalar(
            select(func.count()).select_from(ProjectSectionMedia).where(condition)
        )
        rows = await self.session.scalars(
            select(ProjectSectionMedia)
            .where(condition)
            .order_by(ProjectSectionMedia.sort_order, ProjectSectionMedia.media_id)
            .limit(query.limit)
            .offset(query.offset)
        )
        return list(rows), int(total or 0)

    async def link(self, section_id: UUID, media_id: UUID) -> ProjectSectionMedia | None:
        return await self.session.get(ProjectSectionMedia, (section_id, media_id))

    async def media_types(self, section_id: UUID) -> dict[str, int]:
        rows = await self.session.execute(
            select(MediaAsset.type, func.count())
            .join(ProjectSectionMedia, ProjectSectionMedia.media_id == MediaAsset.id)
            .where(ProjectSectionMedia.section_id == section_id)
            .group_by(MediaAsset.type)
        )
        return {kind: count for kind, count in rows}

    async def replace_media(self, section_id: UUID, items: list[SectionMediaInput]) -> None:
        await self.session.execute(
            delete(ProjectSectionMedia).where(ProjectSectionMedia.section_id == section_id)
        )
        self.session.add_all(
            [ProjectSectionMedia(section_id=section_id, **item.model_dump()) for item in items]
        )
        await self.session.flush()
