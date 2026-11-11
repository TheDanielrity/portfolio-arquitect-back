from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Category,
    Project,
    ProjectCategory,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
    ProjectTag,
    Tag,
)
from app.modules.portfolio.public_schemas import PublicProjectQuery
from app.modules.portfolio.schemas import PageQuery


def published_project(*, direct: bool = False) -> list[ColumnElement[bool]]:
    """Discovery never includes unlisted projects; direct access still requires publication."""
    return [
        Project.status == "PUBLISHED",
        Project.deleted_at.is_(None),
        Project.visibility.in_(["PUBLIC", "UNLISTED"] if direct else ["PUBLIC"]),
    ]


class PublicPortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _page[T](self, statement: Select[T], query: PageQuery) -> tuple[list[T], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = await self.session.scalars(statement.limit(query.limit).offset(query.offset))
        return list(rows), int(total or 0)

    async def projects(
        self, query: PublicProjectQuery, *, featured: bool = False
    ) -> tuple[list[Project], int]:
        criteria = published_project()
        if featured:
            criteria.append(Project.is_featured.is_(True))
        if query.category is not None:
            criteria.append(
                exists().where(
                    ProjectCategory.project_id == Project.id,
                    ProjectCategory.category_id == Category.id,
                    Category.slug == query.category,
                    Category.is_active.is_(True),
                )
            )
        if query.tag is not None:
            criteria.append(
                exists().where(
                    ProjectTag.project_id == Project.id,
                    ProjectTag.tag_id == Tag.id,
                    Tag.slug == query.tag,
                )
            )
        statement = (
            select(Project)
            .where(*criteria)
            .order_by(Project.sort_order, Project.published_at.desc().nullslast(), Project.slug)
            .options(
                selectinload(Project.media_links.and_(ProjectMedia.role == "COVER")).joinedload(
                    ProjectMedia.media_asset
                ),
                selectinload(Project.category_links).joinedload(ProjectCategory.category),
            )
        )
        return await self._page(statement, query)

    async def detail(self, slug: str) -> Project | None:
        return await self.session.scalar(
            select(Project)
            .where(*published_project(direct=True), Project.slug == slug)
            .options(
                selectinload(Project.category_links).joinedload(ProjectCategory.category),
                selectinload(Project.tag_links).joinedload(ProjectTag.tag),
                selectinload(Project.attributes),
                selectinload(Project.media_links).joinedload(ProjectMedia.media_asset),
                selectinload(Project.sections.and_(ProjectSection.is_visible.is_(True)))
                .selectinload(ProjectSection.media_links)
                .joinedload(ProjectSectionMedia.media_asset),
            )
        )

    async def categories(self, query: PageQuery) -> tuple[list[Category], int]:
        return await self._page(
            select(Category)
            .where(
                Category.is_active.is_(True),
                exists().where(
                    ProjectCategory.category_id == Category.id,
                    ProjectCategory.project_id == Project.id,
                    *published_project(),
                ),
            )
            .order_by(Category.sort_order, Category.slug),
            query,
        )

    async def tags(self, query: PageQuery) -> tuple[list[Tag], int]:
        return await self._page(
            select(Tag)
            .where(
                exists().where(
                    ProjectTag.tag_id == Tag.id,
                    ProjectTag.project_id == Project.id,
                    *published_project(),
                )
            )
            .order_by(func.lower(Tag.name), Tag.slug),
            query,
        )
