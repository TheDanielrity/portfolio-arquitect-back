"""Network and disk adapters. Blocking I/O always runs in a worker thread."""

import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.modules.media.storage_port import ObjectInfo, ObjectMissing, StorageError, UploadTarget


def check_key(key: str) -> None:
    if not re.fullmatch(r"(?:staging|objects)/[0-9a-f]{32}\.[a-z0-9]+", key):
        raise StorageError("Invalid managed storage key")


class R2StorageAdapter:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.r2_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 2},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    async def presign(self, key: str, mime: str, expires_at: datetime) -> UploadTarget:
        check_key(key)

        def sign() -> str:
            # Compute TTL after worker queue delays, using the persisted deadline.
            remaining = int((expires_at - datetime.now(UTC)).total_seconds())
            if remaining < 1:
                raise StorageError("Upload signing deadline elapsed")
            return self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": mime},
                ExpiresIn=remaining,
            )

        try:
            url = await run_in_threadpool(sign)
            return UploadTarget(url, {"Content-Type": mime})
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable") from None

    async def head(self, key: str) -> ObjectInfo:
        check_key(key)
        try:
            result = await run_in_threadpool(self.client.head_object, Bucket=self.bucket, Key=key)
            return ObjectInfo(
                result["ContentLength"], result.get("ContentType", ""), result["ETag"]
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectMissing("Object not found") from None
            raise StorageError("Storage unavailable") from None
        except BotoCoreError:
            raise StorageError("Storage unavailable") from None

    async def prefix(self, key: str, etag: str) -> bytes:
        check_key(key)

        def read() -> bytes:
            result = self.client.get_object(
                Bucket=self.bucket, Key=key, Range="bytes=0-63", IfMatch=etag
            )
            try:
                return result["Body"].read(64)
            finally:
                result["Body"].close()

        try:
            return await run_in_threadpool(read)
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable or object changed") from None

    async def promote(self, source: str, destination: str, etag: str) -> None:
        check_key(source)
        check_key(destination)
        try:
            await run_in_threadpool(
                self.client.copy_object,
                Bucket=self.bucket,
                Key=destination,
                CopySource={"Bucket": self.bucket, "Key": source},
                CopySourceIfMatch=etag,
                MetadataDirective="COPY",
            )
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable or object changed") from None

    async def access(self, key: str, expires: int) -> str:
        check_key(key)
        try:
            return await run_in_threadpool(
                self.client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable") from None

    async def delete(self, key: str) -> None:
        check_key(key)
        try:
            await run_in_threadpool(self.client.delete_object, Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            raise StorageError("Storage unavailable") from None


class LocalStorageAdapter:
    """Local PUT uses an authenticated operation route, never an invented signed URL."""

    def __init__(self, settings: Settings) -> None:
        self.root = settings.local_storage_path.resolve()
        self.base_url = settings.media_base_url.rstrip("/")

    def path(self, key: str) -> Path:
        check_key(key)
        path = self.root / key
        if not path.resolve().is_relative_to(self.root):
            raise StorageError("Invalid local path")
        return path

    async def presign(self, key: str, mime: str, expires_at: datetime) -> UploadTarget:
        check_key(key)
        operation = key.split("/")[1].split(".")[0]
        return UploadTarget(
            f"{self.base_url}/api/v1/admin/media/uploads/{operation}/content",
            {"Content-Type": mime},
        )

    async def put(self, key: str, content: bytes, mime: str) -> None:
        def write() -> None:
            path = self.path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{uuid4().hex}.writing")
            try:
                temporary.write_bytes(content)
                path.with_suffix(path.suffix + ".json").write_text(json.dumps({"mime": mime}))
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            await run_in_threadpool(write)
        except OSError:
            raise StorageError("Local storage unavailable") from None

    async def head(self, key: str) -> ObjectInfo:
        def inspect() -> ObjectInfo:
            path = self.path(key)
            # Bounded streaming hash, never load an entire file into memory.
            with path.open("rb") as stream:
                etag = hashlib.file_digest(stream, "sha256").hexdigest()
            mime = json.loads(path.with_suffix(path.suffix + ".json").read_text())["mime"]
            return ObjectInfo(path.stat().st_size, str(mime), etag)

        try:
            return await run_in_threadpool(inspect)
        except FileNotFoundError:
            raise ObjectMissing("Object not found") from None
        except (OSError, ValueError, KeyError):
            raise StorageError("Local storage unavailable") from None

    async def prefix(self, key: str, etag: str) -> bytes:
        if (await self.head(key)).etag != etag:
            raise StorageError("Object changed")

        def read() -> bytes:
            with self.path(key).open("rb") as stream:
                return stream.read(64)

        try:
            return await run_in_threadpool(read)
        except OSError:
            raise StorageError("Local storage unavailable") from None

    async def promote(self, source: str, destination: str, etag: str) -> None:
        if (await self.head(source)).etag != etag:
            raise StorageError("Object changed")

        def copy() -> None:
            origin, target = self.path(source), self.path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{uuid4().hex}.writing")
            try:
                shutil.copyfile(origin, temporary)
                shutil.copyfile(
                    origin.with_suffix(origin.suffix + ".json"),
                    target.with_suffix(target.suffix + ".json"),
                )
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)

        try:
            await run_in_threadpool(copy)
        except OSError:
            raise StorageError("Local storage unavailable") from None

    async def access(self, key: str, expires: int) -> str:
        raise StorageError("Local access uses authenticated or public-reference delivery")

    async def delete(self, key: str) -> None:
        def remove() -> None:
            path = self.path(key)
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".json").unlink(missing_ok=True)

        try:
            await run_in_threadpool(remove)
        except OSError:
            raise StorageError("Local storage unavailable") from None
