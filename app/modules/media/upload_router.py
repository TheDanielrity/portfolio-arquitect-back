from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.core.api_docs import error_responses
from app.modules.auth.dependencies import CurrentUser, get_current_user
from app.modules.media.dependencies import UploadServiceDependency
from app.modules.media.router import prevent_caching
from app.modules.media.schemas import MediaResponse
from app.modules.media.storage_adapters import LocalStorageAdapter
from app.modules.media.upload_schemas import ConfirmRequest, UploadRequest, UploadResponse

router = APIRouter(
    prefix="/admin/media/uploads",
    tags=["administrative media uploads"],
    dependencies=[Depends(get_current_user), Depends(prevent_caching)],
)


@router.post(
    "/presign", response_model=UploadResponse, responses=error_responses(401, 400, 422, 503)
)
async def presign(
    body: UploadRequest, user: CurrentUser, service: UploadServiceDependency
) -> UploadResponse:
    return await service.presign(body, user.id)


@router.post(
    "/confirm",
    response_model=MediaResponse,
    responses=error_responses(401, 400, 404, 409, 422, 503),
)
async def confirm(
    body: ConfirmRequest, user: CurrentUser, service: UploadServiceDependency
) -> MediaResponse:
    return await service.confirm(body.upload_id, user.id)


@router.put(
    "/{upload_id}/content",
    status_code=204,
    responses=error_responses(401, 400, 404, 409, 422, 503),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def local_put(
    upload_id: UUID, request: Request, user: CurrentUser, service: UploadServiceDependency
) -> None:
    await service.local_put(
        upload_id, user.id, await request.body(), request.headers.get("content-type", "")
    )


@router.delete("/{upload_id}", status_code=204, responses=error_responses(401, 404, 409, 422))
async def cancel(upload_id: UUID, user: CurrentUser, service: UploadServiceDependency) -> None:
    await service.cancel(upload_id, user.id)


delivery_router = APIRouter(tags=["media delivery"])
DELIVERY_RESPONSES = error_responses(404, 422, 503) | {
    200: {
        "description": "Local file bytes",
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    },
    307: {"description": "Temporary redirect to a signed private object URL"},
}


async def deliver(asset_id: UUID, service: UploadServiceDependency, *, public: bool) -> Response:
    key, mime = await service.delivery(asset_id, public=public)
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    if isinstance(service.storage, LocalStorageAdapter):
        await service.storage.head(key)
        return FileResponse(service.storage.path(key), media_type=mime, headers=headers)
    return RedirectResponse(await service.storage.access(key, 60), status_code=307, headers=headers)


@delivery_router.get(
    "/public/media/{asset_id}/content", response_class=Response, responses=DELIVERY_RESPONSES
)
async def public_content(asset_id: UUID, service: UploadServiceDependency) -> Response:
    return await deliver(asset_id, service, public=True)


@delivery_router.get(
    "/admin/media/{asset_id}/content",
    response_class=Response,
    dependencies=[Depends(get_current_user)],
    responses=DELIVERY_RESPONSES | error_responses(401),
)
async def admin_content(asset_id: UUID, service: UploadServiceDependency) -> Response:
    return await deliver(asset_id, service, public=False)
