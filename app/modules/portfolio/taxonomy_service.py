from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceConflict, ResourceNotFound
from app.models import Category, Tag
from app.modules.portfolio.repository import PortfolioRepository, TaxonomyKind
from app.modules.portfolio.schemas import (
    Assignment,
    CategoryCreate,
    CategoryQuery,
    CategoryResponse,
    CategoryUpdate,
    Page,
    TagCreate,
    TagQuery,
    TagResponse,
    TagUpdate,
)
from app.modules.portfolio.service import ProjectService
from app.modules.portfolio.transactions import write_transaction

TaxonResponse = CategoryResponse | TagResponse
TaxonPage = Page[CategoryResponse] | Page[TagResponse]


class TaxonomyService:
    """Categories and tags share assignment and safe-deletion rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PortfolioRepository(session)
        self.projects = ProjectService(session)

    async def _get(
        self, kind: TaxonomyKind, item_id: UUID, *, lock: bool = False
    ) -> Category | Tag:
        row = await self.repository.taxon(kind, item_id, lock=lock)
        if row is None:
            raise ResourceNotFound("Category or tag not found")
        return row

    def _response(self, row: Category | Tag) -> TaxonResponse:
        if isinstance(row, Category):
            return CategoryResponse.model_validate(row)
        return TagResponse.model_validate(row)

    async def list(
        self, kind: TaxonomyKind, query: CategoryQuery | TagQuery, project_id: UUID | None = None
    ) -> TaxonPage:
        if project_id is not None:
            await self.projects.require_project(project_id)
        rows, total = await self.repository.taxons(kind, query, project_id)
        if kind == "categories":
            return Page(
                items=[CategoryResponse.model_validate(row) for row in rows],
                total=total,
                limit=query.limit,
                offset=query.offset,
            )
        return Page(
            items=[TagResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get(self, kind: TaxonomyKind, item_id: UUID) -> TaxonResponse:
        return self._response(await self._get(kind, item_id))

    async def create(self, body: CategoryCreate | TagCreate) -> TaxonResponse:
        async with write_transaction(self.session):
            model = Category if isinstance(body, CategoryCreate) else Tag
            row = model(**body.model_dump())
            await self.repository.save(row)
            response = self._response(row)
        return response

    async def update(
        self, kind: TaxonomyKind, item_id: UUID, body: CategoryUpdate | TagUpdate
    ) -> TaxonResponse:
        async with write_transaction(self.session):
            row = await self._get(kind, item_id, lock=True)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            await self.repository.save(row)
            response = self._response(row)
        return response

    async def delete(self, kind: TaxonomyKind, item_id: UUID) -> None:
        async with write_transaction(self.session):
            row = await self._get(kind, item_id, lock=True)
            if await self.repository.taxon_is_used(kind, item_id):
                raise ResourceConflict("Category or tag is still assigned to a project")
            await self.repository.remove(row)

    async def assign(self, kind: TaxonomyKind, project_id: UUID, body: Assignment) -> None:
        async with write_transaction(self.session):
            await self.projects.require_project(project_id, lock=True)
            if not await self.repository.replace_assignment(kind, project_id, body.ids):
                raise ResourceNotFound("One or more categories or tags do not exist")
