from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.api_docs import error_responses
from app.core.database import SessionDependency
from app.modules.auth.dependencies import get_current_user
from app.modules.content.repository import ContentRepository
from app.modules.content.schemas import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    ServiceCreate,
    ServiceQuery,
    ServiceResponse,
    ServiceUpdate,
    SettingKey,
    SettingResponse,
    SettingUpdate,
    SocialCreate,
    SocialQuery,
    SocialResponse,
    SocialUpdate,
)
from app.modules.content.service import ContentService
from app.modules.content.settings_service import SettingsService
from app.modules.portfolio.schemas import Page, Reorder


def get_content_service(session: SessionDependency) -> ContentService:
    return ContentService(session)


def get_settings_service(session: SessionDependency) -> SettingsService:
    return SettingsService(ContentRepository(session))


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


Content = Annotated[ContentService, Depends(get_content_service)]
Settings = Annotated[SettingsService, Depends(get_settings_service)]
router = APIRouter(
    prefix="/admin",
    tags=["administrative content"],
    dependencies=[Depends(get_current_user), Depends(prevent_caching)],
)


@router.get("/profile", response_model=ProfileResponse, responses=error_responses(401, 404))
async def get_profile(service: Content) -> ProfileResponse:
    return await service.get_profile()


@router.post(
    "/profile",
    response_model=ProfileResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def create_profile(body: ProfileCreate, service: Content) -> ProfileResponse:
    return await service.create_profile(body)


@router.patch(
    "/profile", response_model=ProfileResponse, responses=error_responses(401, 404, 409, 422)
)
async def update_profile(body: ProfileUpdate, service: Content) -> ProfileResponse:
    return await service.update_profile(body)


@router.get(
    "/profile/social-links",
    response_model=Page[SocialResponse],
    responses=error_responses(401, 404, 422),
)
async def list_socials(
    query: Annotated[SocialQuery, Query()], service: Content
) -> Page[SocialResponse]:
    return await service.list_socials(query)


@router.post(
    "/profile/social-links",
    response_model=SocialResponse,
    status_code=201,
    responses=error_responses(401, 404, 409, 422),
)
async def create_social(body: SocialCreate, service: Content) -> SocialResponse:
    return await service.create_social(body)


@router.put(
    "/profile/social-links/order", status_code=204, responses=error_responses(401, 404, 422)
)
async def order_socials(body: Reorder, service: Content) -> None:
    await service.reorder_socials(body)


@router.get(
    "/profile/social-links/{item_id}",
    response_model=SocialResponse,
    responses=error_responses(401, 404, 422),
)
async def get_social(item_id: UUID, service: Content) -> SocialResponse:
    return await service.get_social(item_id)


@router.patch(
    "/profile/social-links/{item_id}",
    response_model=SocialResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_social(item_id: UUID, body: SocialUpdate, service: Content) -> SocialResponse:
    return await service.update_social(item_id, body)


@router.delete(
    "/profile/social-links/{item_id}", status_code=204, responses=error_responses(401, 404, 422)
)
async def delete_social(item_id: UUID, service: Content) -> None:
    await service.delete_social(item_id)


@router.get("/services", response_model=Page[ServiceResponse], responses=error_responses(401, 422))
async def list_services(
    query: Annotated[ServiceQuery, Query()], service: Content
) -> Page[ServiceResponse]:
    return await service.list_services(query)


@router.post(
    "/services",
    response_model=ServiceResponse,
    status_code=201,
    responses=error_responses(401, 409, 422),
)
async def create_service(body: ServiceCreate, service: Content) -> ServiceResponse:
    return await service.create_service(body)


@router.put("/services/order", status_code=204, responses=error_responses(401, 404, 422))
async def order_services(body: Reorder, service: Content) -> None:
    await service.reorder_services(body)


@router.get(
    "/services/{item_id}", response_model=ServiceResponse, responses=error_responses(401, 404, 422)
)
async def get_service(item_id: UUID, service: Content) -> ServiceResponse:
    return await service.get_service(item_id)


@router.patch(
    "/services/{item_id}",
    response_model=ServiceResponse,
    responses=error_responses(401, 404, 409, 422),
)
async def update_service(item_id: UUID, body: ServiceUpdate, service: Content) -> ServiceResponse:
    return await service.update_service(item_id, body)


@router.delete("/services/{item_id}", status_code=204, responses=error_responses(401, 404, 422))
async def delete_service(item_id: UUID, service: Content) -> None:
    await service.delete_service(item_id)


@router.get("/site-settings", response_model=list[SettingResponse], responses=error_responses(401))
async def list_settings(service: Settings) -> list[SettingResponse]:
    return await service.list()


@router.get(
    "/site-settings/{key}", response_model=SettingResponse, responses=error_responses(401, 404, 422)
)
async def get_setting(key: SettingKey, service: Settings) -> SettingResponse:
    return await service.get(key)


@router.put(
    "/site-settings/{key}", response_model=SettingResponse, responses=error_responses(401, 422)
)
async def put_setting(key: SettingKey, body: SettingUpdate, service: Settings) -> SettingResponse:
    return await service.put(key, body)
