from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.api_docs import error_responses
from app.core.database import SessionDependency
from app.modules.content.public_repository import PublicContentRepository
from app.modules.content.public_schemas import (
    PublicProfile,
    PublicService,
    PublicSetting,
    PublicSocialLink,
)
from app.modules.content.public_service import PublicContentService
from app.modules.portfolio.schemas import Page, PageQuery


def get_public_content(session: SessionDependency) -> PublicContentService:
    return PublicContentService(PublicContentRepository(session))


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


Content = Annotated[PublicContentService, Depends(get_public_content)]
Pagination = Annotated[PageQuery, Query()]
router = APIRouter(
    prefix="/public", tags=["public content"], dependencies=[Depends(prevent_caching)]
)


@router.get("/profile", response_model=PublicProfile, responses=error_responses(404))
async def profile(service: Content) -> PublicProfile:
    return await service.profile()


@router.get("/services", response_model=Page[PublicService], responses=error_responses(422))
async def services(query: Pagination, service: Content) -> Page[PublicService]:
    return await service.services(query)


@router.get("/social-links", response_model=Page[PublicSocialLink], responses=error_responses(422))
async def social_links(query: Pagination, service: Content) -> Page[PublicSocialLink]:
    return await service.social_links(query)


@router.get("/site-settings", response_model=list[PublicSetting])
async def settings(service: Content) -> list[PublicSetting]:
    return await service.settings()
