from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidOperation, ResourceNotFound
from app.models import Project
from app.modules.portfolio.repository import PortfolioRepository
from app.modules.portfolio.schemas import (
    Page,
    ProjectCreate,
    ProjectQuery,
    ProjectResponse,
    ProjectUpdate,
    Reorder,
)
from app.modules.portfolio.transactions import write_transaction


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PortfolioRepository(session)

    async def require_project(self, project_id: UUID, *, lock: bool = False) -> Project:
        project = await self.repository.project(project_id, lock=lock)
        if project is None:
            raise ResourceNotFound("Project not found")
        return project

    async def list(self, query: ProjectQuery) -> Page[ProjectResponse]:
        rows, total = await self.repository.projects(query)
        return Page(
            items=[ProjectResponse.model_validate(row) for row in rows],
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def get(self, project_id: UUID) -> ProjectResponse:
        return ProjectResponse.model_validate(await self.require_project(project_id))

    async def create(self, body: ProjectCreate) -> ProjectResponse:
        if body.status == "PUBLISHED":
            raise InvalidOperation("Attach an image cover before publishing a project")
        async with write_transaction(self.session):
            await self.repository.lock_featured_selection()
            project = Project(**body.model_dump())
            if project.is_featured:
                await self.repository.clear_featured()
            await self.repository.save(project)
            response = ProjectResponse.model_validate(project)
        return response

    async def update(self, project_id: UUID, body: ProjectUpdate) -> ProjectResponse:
        async with write_transaction(self.session):
            await self.repository.lock_featured_selection()
            project = await self.require_project(project_id, lock=True)
            if body.is_featured is True:
                await self.repository.clear_featured(project.id)
            for key, value in body.model_dump(exclude_unset=True).items():
                setattr(project, key, value)
            if project.status == "PUBLISHED":
                if not await self.repository.has_image_cover(project.id):
                    raise InvalidOperation("Published projects require an image cover")
                if project.published_at is None:
                    project.published_at = datetime.now(UTC)
            await self.repository.save(project)
            response = ProjectResponse.model_validate(project)
        return response

    async def delete(self, project_id: UUID) -> None:
        async with write_transaction(self.session):
            await self.repository.lock_featured_selection()
            project = await self.require_project(project_id, lock=True)
            project.is_featured = False
            project.deleted_at = datetime.now(UTC)
            await self.repository.save(project)

    async def reorder(self, body: Reorder) -> None:
        async with write_transaction(self.session):
            await self.repository.lock_featured_selection()
            for item in sorted(body.items, key=lambda entry: entry.id):
                project = await self.require_project(item.id, lock=True)
                project.sort_order = item.sort_order
                await self.repository.save(project)
