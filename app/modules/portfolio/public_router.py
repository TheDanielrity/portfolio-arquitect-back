from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.core.api_docs import error_responses
from app.core.database import SessionDependency
from app.modules.portfolio.public_repository import PublicPortfolioRepository
from app.modules.portfolio.public_schemas import (
    PublicCategory,
    PublicProjectCard,
    PublicProjectDetail,
    PublicProjectQuery,
    PublicTag,
)
from app.modules.portfolio.public_service import PublicPortfolioService
from app.modules.portfolio.schemas import Page, PageQuery


def get_public_portfolio(session: SessionDependency) -> PublicPortfolioService:
    return PublicPortfolioService(PublicPortfolioRepository(session))


def prevent_caching(response: Response) -> None:
    # Visibility changes must not leave previously public content in shared API caches.
    response.headers["Cache-Control"] = "no-store"


Service = Annotated[PublicPortfolioService, Depends(get_public_portfolio)]
Pagination = Annotated[PageQuery, Query()]
ProjectsQuery = Annotated[PublicProjectQuery, Query()]
router = APIRouter(
    prefix="/public", tags=["public portfolio"], dependencies=[Depends(prevent_caching)]
)


@router.get("/projects", response_model=Page[PublicProjectCard], responses=error_responses(422))
async def list_projects(query: ProjectsQuery, service: Service) -> Page[PublicProjectCard]:
    return await service.projects(query)


@router.get(
    "/featured-projects", response_model=Page[PublicProjectCard], responses=error_responses(422)
)
async def featured_projects(query: ProjectsQuery, service: Service) -> Page[PublicProjectCard]:
    return await service.projects(query, featured=True)


@router.get(
    "/projects/{slug}", response_model=PublicProjectDetail, responses=error_responses(404, 422)
)
async def project_detail(
    slug: Annotated[str, Path(max_length=220, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")],
    service: Service,
) -> PublicProjectDetail:
    return await service.detail(slug)


@router.get("/categories", response_model=Page[PublicCategory], responses=error_responses(422))
async def categories(query: Pagination, service: Service) -> Page[PublicCategory]:
    return await service.categories(query)


@router.get("/tags", response_model=Page[PublicTag], responses=error_responses(422))
async def tags(query: Pagination, service: Service) -> Page[PublicTag]:
    return await service.tags(query)
