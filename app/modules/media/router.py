from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.api_docs import error_responses
from app.modules.auth.dependencies import CurrentUser, get_current_user
from app.modules.media.dependencies import MediaServiceDependency, UploadServiceDependency
from app.modules.media.schemas import (
    MediaCreate,
    MediaListQuery,
    MediaPage,
    MediaResponse,
    MediaUpdate,
)


def prevent_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/admin/media",
    tags=["administrative media"],
    dependencies=[Depends(get_current_user), Depends(prevent_caching)],
)


@router.get("", response_model=MediaPage, responses=error_responses(401, 422))
async def list_media(
    query: Annotated[MediaListQuery, Query()], service: MediaServiceDependency
) -> MediaPage:
    return await service.list(query)


@router.get("/{asset_id}", response_model=MediaResponse, responses=error_responses(401, 404, 422))
async def get_media(asset_id: UUID, service: MediaServiceDependency) -> MediaResponse:
    return await service.get(asset_id)


@router.post(
    "",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 409, 422),
)
async def create_media(body: MediaCreate, service: MediaServiceDependency) -> MediaResponse:
    return await service.create(body)


@router.patch("/{asset_id}", response_model=MediaResponse, responses=error_responses(401, 404, 422))
async def update_media(
    asset_id: UUID, body: MediaUpdate, service: MediaServiceDependency
) -> MediaResponse:
    return await service.update(asset_id, body)


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404, 409, 422),
)
async def delete_media(asset_id: UUID, user: CurrentUser, service: UploadServiceDependency) -> None:
    await service.delete(asset_id, user.id)
