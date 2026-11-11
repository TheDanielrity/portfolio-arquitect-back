from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class StorageError(Exception):
    """Provider unavailable; technical details must not reach clients or logs."""


class ObjectMissing(StorageError):
    """Object does not exist."""


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    mime_type: str
    etag: str


@dataclass(frozen=True)
class UploadTarget:
    url: str
    headers: dict[str, str]


class StoragePort(Protocol):
    async def presign(self, key: str, mime: str, expires_at: datetime) -> UploadTarget: ...
    async def head(self, key: str) -> ObjectInfo: ...
    async def prefix(self, key: str, etag: str) -> bytes: ...
    async def promote(self, source: str, destination: str, etag: str) -> None: ...
    async def access(self, key: str, expires: int) -> str: ...
    async def delete(self, key: str) -> None: ...
