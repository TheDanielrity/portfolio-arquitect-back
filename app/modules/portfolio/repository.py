from typing import Literal, cast
from uuid import UUID

from sqlalchemy import ColumnElement, delete, exists, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Base,
    Category,
    MediaAsset,
    Project,
    ProjectAttribute,
    ProjectCategory,
    ProjectMedia,
    ProjectTag,
    Tag,
)
from app.modules.portfolio.schemas import CategoryQuery, PageQuery, ProjectQuery, TagQuery

TaxonomyKind = Literal["categories", "tags"]
ChildKind = Literal["attributes", "media"]


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_featured_selection(self) -> None:
        """Serialize project writes before any row locks, including empty selections."""
        await self.session.execute(text("SELECT pg_advisory_xact_lock(192847, 1)"))

    async def clear_featured(self, except_id: UUID | None = None) -> None:
        statement = update(Project).where(Project.is_featured.is_(True))
        if except_id is not None:
            statement = statement.where(Project.id != except_id)
        await self.session.execute(statement.values(is_featured=False))

    async def save(self, row: Base) -> None:
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)

    async def remove(self, row: Base) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def project(self, project_id: UUID, *, lock: bool = False) -> Project | None:
        query = select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def projects(self, options: ProjectQuery) -> tuple[list[Project], int]:
        criteria: list[ColumnElement[bool]] = [Project.deleted_at.is_(None)]
        if options.q is not None:
            criteria.append(
                or_(
                    Project.title.icontains(options.q, autoescape=True),
                    Project.slug.icontains(options.q, autoescape=True),
                    Project.client_name.icontains(options.q, autoescape=True),
                    Project.location.icontains(options.q, autoescape=True),
                )
            )
        if options.status is not None:
            criteria.append(Project.status == options.status.value)
        if options.visibility is not None:
            criteria.append(Project.visibility == options.visibility.value)
        if options.is_featured is not None:
            criteria.append(Project.is_featured == options.is_featured)
        if options.category_id is not None:
            criteria.append(
                exists().where(
                    ProjectCategory.project_id == Project.id,
                    ProjectCategory.category_id == options.category_id,
                )
            )
        if options.tag_id is not None:
            criteria.append(
                exists().where(
                    ProjectTag.project_id == Project.id, ProjectTag.tag_id == options.tag_id
                )
            )
        total = await self.session.scalar(
            select(func.count()).select_from(Project).where(*criteria)
        )
        column = {
            "sort_order": Project.sort_order,
            "title": func.lower(Project.title),
            "created_at": Project.created_at,
            "updated_at": Project.updated_at,
        }[options.sort]
        order = column.asc() if options.direction == "asc" else column.desc()
        rows = await self.session.scalars(
            select(Project)
            .where(*criteria)
            .order_by(order, Project.created_at.desc(), Project.id)
            .limit(options.limit)
            .offset(options.offset)
        )
        return list(rows), int(total or 0)

    async def taxon(
        self, kind: TaxonomyKind, item_id: UUID, *, lock: bool = False
    ) -> Category | Tag | None:
        model = Category if kind == "categories" else Tag
        query = select(model).where(model.id == item_id)
        if lock:
            query = query.with_for_update()
        return cast(Category | Tag | None, await self.session.scalar(query))

    async def taxons(
        self, kind: TaxonomyKind, options: CategoryQuery | TagQuery, project_id: UUID | None = None
    ) -> tuple[list[Category | Tag], int]:
        model = Category if kind == "categories" else Tag
        rows = select(model)
        if options.q is not None:
            rows = rows.where(
                or_(
                    model.name.icontains(options.q, autoescape=True),
                    model.slug.icontains(options.q, autoescape=True),
                )
            )
        if isinstance(options, CategoryQuery) and options.is_active is not None:
            rows = rows.where(Category.is_active == options.is_active)
        if project_id is not None:
            if kind == "categories":
                rows = rows.where(
                    exists().where(
                        ProjectCategory.category_id == model.id,
                        ProjectCategory.project_id == project_id,
                    )
                )
            else:
                rows = rows.where(
                    exists().where(
                        ProjectTag.tag_id == model.id, ProjectTag.project_id == project_id
                    )
                )
        total = await self.session.scalar(select(func.count()).select_from(rows.subquery()))
        column = {
            "sort_order": Category.sort_order,
            "name": func.lower(model.name),
            "created_at": model.created_at,
        }[options.sort]
        order = column.asc() if options.direction == "asc" else column.desc()
        rows = rows.order_by(order, model.id)
        return list(
            await self.session.scalars(rows.limit(options.limit).offset(options.offset))
        ), int(total or 0)

    async def taxon_is_used(self, kind: TaxonomyKind, item_id: UUID) -> bool:
        condition = (
            ProjectCategory.category_id == item_id
            if kind == "categories"
            else ProjectTag.tag_id == item_id
        )
        return bool(await self.session.scalar(select(exists().where(condition))))

    async def replace_assignment(
        self, kind: TaxonomyKind, project_id: UUID, ids: list[UUID]
    ) -> bool:
        model = Category if kind == "categories" else Tag
        # Lock targets in a fixed order so deletion cannot race assignment.
        found = list(
            await self.session.scalars(
                select(model.id)
                .where(model.id.in_(ids))
                .order_by(model.id)
                .with_for_update(read=True, key_share=True)
            )
        )
        if set(found) != set(ids):
            return False
        if kind == "categories":
            await self.session.execute(
                delete(ProjectCategory).where(ProjectCategory.project_id == project_id)
            )
            self.session.add_all(
                [ProjectCategory(project_id=project_id, category_id=item) for item in ids]
            )
        else:
            await self.session.execute(
                delete(ProjectTag).where(ProjectTag.project_id == project_id)
            )
            self.session.add_all([ProjectTag(project_id=project_id, tag_id=item) for item in ids])
        await self.session.flush()
        return True

    async def child(
        self, kind: ChildKind, project_id: UUID, item_id: UUID
    ) -> ProjectAttribute | ProjectMedia | None:
        model = ProjectAttribute if kind == "attributes" else ProjectMedia
        return cast(
            ProjectAttribute | ProjectMedia | None,
            await self.session.scalar(
                select(model).where(model.id == item_id, model.project_id == project_id)
            ),
        )

    async def children(
        self, kind: ChildKind, project_id: UUID, options: PageQuery
    ) -> tuple[list[ProjectAttribute | ProjectMedia], int]:
        model = ProjectAttribute if kind == "attributes" else ProjectMedia
        total = await self.session.scalar(
            select(func.count()).select_from(model).where(model.project_id == project_id)
        )
        rows = await self.session.scalars(
            select(model)
            .where(model.project_id == project_id)
            .order_by(model.sort_order, model.id)
            .limit(options.limit)
            .offset(options.offset)
        )
        return cast(list[ProjectAttribute | ProjectMedia], list(rows)), int(total or 0)

    async def asset(self, asset_id: UUID) -> MediaAsset | None:
        return await self.session.scalar(
            select(MediaAsset)
            .where(MediaAsset.id == asset_id)
            .with_for_update(read=True, key_share=True)
        )

    async def cover(self, project_id: UUID) -> ProjectMedia | None:
        return await self.session.scalar(
            select(ProjectMedia).where(
                ProjectMedia.project_id == project_id, ProjectMedia.role == "COVER"
            )
        )

    async def has_image_cover(self, project_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(
                        ProjectMedia.project_id == project_id,
                        ProjectMedia.role == "COVER",
                        ProjectMedia.media_id == MediaAsset.id,
                        MediaAsset.type == "IMAGE",
                    )
                )
            )
        )
