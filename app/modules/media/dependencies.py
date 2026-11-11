from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.database import SessionDependency
from app.modules.media.service import MediaService
from app.modules.media.storage_adapters import LocalStorageAdapter, R2StorageAdapter
from app.modules.media.storage_port import StoragePort
from app.modules.media.upload_service import UploadService


def build_storage(settings: Settings) -> StoragePort:
    if settings.storage_provider == "r2":
        return R2StorageAdapter(settings)
    return LocalStorageAdapter(settings)


def get_upload_service(request: Request, session: SessionDependency) -> UploadService:
    return UploadService(
        session,
        cast(StoragePort, request.app.state.storage),
        cast(Settings, request.app.state.settings),
    )


UploadServiceDependency = Annotated[UploadService, Depends(get_upload_service)]


def get_media_service(session: SessionDependency) -> MediaService:
    return MediaService(session)


MediaServiceDependency = Annotated[MediaService, Depends(get_media_service)]
