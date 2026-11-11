"""Storage workflow with durable intents and PostgreSQL serialization."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import InvalidOperation, ResourceConflict, ResourceNotFound
from app.modules.media.operation_models import StorageOperation
from app.modules.media.operation_repository import OperationRepository
from app.modules.media.repository import MediaRepository
from app.modules.media.schemas import MediaResponse
from app.modules.media.storage_adapters import LocalStorageAdapter
from app.modules.media.storage_port import ObjectInfo, ObjectMissing, StorageError, StoragePort
from app.modules.media.upload_policy import validate_object, validate_request
from app.modules.media.upload_schemas import UploadRequest, UploadResponse


class UploadService:
    def __init__(self, session: AsyncSession, storage: StoragePort, settings: Settings) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.operations = OperationRepository(session)
        self.media = MediaRepository(session)

    async def _verify(self, key: str, body: UploadRequest) -> ObjectInfo:
        info = await self.storage.head(key)
        _, _, limit = validate_request(body, self.settings)
        if info.size != body.file_size or info.size > limit or info.mime_type != body.mime_type:
            raise InvalidOperation("Stored object size or MIME type does not match authorization")
        validate_object(info, await self.storage.prefix(key, info.etag), body, self.settings)
        return info

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise

    async def _operation(self, identifier: UUID, user: UUID) -> StorageOperation:
        operation = await self.operations.get(identifier)
        if operation is None or operation.kind != "UPLOAD" or operation.created_by != user:
            raise ResourceNotFound("Upload authorization not found")
        if operation.storage_provider != self.settings.storage_provider:
            raise ResourceConflict("Operation belongs to another storage provider")
        return operation

    async def presign(self, body: UploadRequest, user: UUID) -> UploadResponse:
        extension, _, maximum = validate_request(body, self.settings)
        if self.settings.storage_provider == "local":
            maximum = min(maximum, self.settings.max_request_body_bytes)
            if body.file_size > maximum:
                raise InvalidOperation("Local uploads exceed the backend request limit")
        identifier = uuid4()
        expiry = datetime.now(UTC) + timedelta(
            seconds=self.settings.r2_presigned_url_expire_seconds
        )
        operation = StorageOperation(
            id=identifier,
            kind="UPLOAD",
            status="PENDING",
            created_by=user,
            storage_provider=self.settings.storage_provider,
            storage_key=f"objects/{uuid4().hex}{extension}",
            temporary_key=f"staging/{identifier.hex}{extension}",
            expected_metadata=body.model_dump(mode="json"),
            expires_at=expiry,
        )
        self.session.add(operation)
        await self._commit()  # Authorization intent exists before signing or any remote I/O.
        remaining = int((expiry - datetime.now(UTC)).total_seconds())
        if remaining < 1:
            raise InvalidOperation("Upload authorization expired")
        assert operation.temporary_key is not None
        target = await self.storage.presign(operation.temporary_key, body.mime_type, expiry)
        return UploadResponse(
            upload_id=identifier,
            upload_url=target.url,
            headers=target.headers,
            expires_at=expiry,
            max_file_size=maximum,
            provider=self.settings.storage_provider,
        )

    async def confirm(self, identifier: UUID, user: UUID) -> MediaResponse:
        operation = await self._operation(identifier, user)
        if operation.status == "COMPLETED":
            asset = await self.media.get(operation.media_id) if operation.media_id else None
            if asset is None:
                raise ResourceConflict("Confirmed asset has been deleted")
            return MediaResponse.model_validate(asset)
        if operation.status not in {"PENDING", "PROCESSING"}:
            raise ResourceConflict("Upload authorization is no longer usable")
        if operation.expires_at <= datetime.now(UTC):
            raise InvalidOperation("Upload authorization expired")
        operation.status = "PROCESSING"
        operation.updated_at = datetime.now(UTC)
        await self._commit()  # Durable promotion intent before executing the copy.
        operation = await self._operation(identifier, user)
        # Another request may have completed while the intent transaction committed.
        if operation.status == "COMPLETED":
            return await self.confirm(identifier, user)
        if operation.status != "PROCESSING" or operation.expires_at <= datetime.now(UTC):
            raise ResourceConflict("Upload authorization is no longer usable")
        body = UploadRequest.model_validate(operation.expected_metadata)
        assert operation.temporary_key is not None
        try:
            try:
                info = await self._verify(operation.storage_key, body)
            except ObjectMissing:
                info = await self._verify(operation.temporary_key, body)
                await self.storage.promote(
                    operation.temporary_key, operation.storage_key, info.etag
                )
                info = await self._verify(operation.storage_key, body)
        except ObjectMissing:
            raise InvalidOperation("Uploaded object does not exist") from None
        except InvalidOperation:
            operation.status = "CLEANUP_PENDING"
            operation.updated_at = datetime.now(UTC)
            await self._commit()  # Invalid objects are cleaned only after URL expiry + grace.
            raise
        _, media_type, _ = validate_request(body, self.settings)
        asset_id = uuid4()
        try:
            asset = await self.media.create(
                {
                    "id": asset_id,
                    "type": media_type,
                    "original_filename": body.original_filename,
                    "storage_provider": operation.storage_provider,
                    "storage_key": operation.storage_key,
                    "url": (
                        f"{self.settings.media_base_url.rstrip('/')}"
                        f"/api/v1/public/media/{asset_id}/content"
                    ),
                    "mime_type": info.mime_type,
                    "file_size": info.size,
                    "alt_text": body.alt_text,
                    "title": body.title,
                    "description": body.description,
                    "asset_metadata": {
                        "_storage": {
                            "access": body.access,
                            "upload_id": str(identifier),
                            "inspection": "header-only",
                        }
                    },
                }
            )
            operation.media_id = asset.id
            operation.status = "COMPLETED"
            operation.updated_at = datetime.now(UTC)
            response = MediaResponse.model_validate(asset)
            await self._commit()
            return response
        except BaseException:
            await self.session.rollback()
            # PROCESSING remains durable; retry verifies the existing immutable destination.
            raise

    async def local_put(self, identifier: UUID, user: UUID, content: bytes, mime: str) -> None:
        operation = await self._operation(identifier, user)
        if not isinstance(self.storage, LocalStorageAdapter):
            raise InvalidOperation("R2 uploads must go directly to object storage")
        if operation.status != "PENDING" or operation.expires_at <= datetime.now(UTC):
            raise ResourceConflict("Upload authorization is no longer usable")
        body = UploadRequest.model_validate(operation.expected_metadata)
        if len(content) != body.file_size or mime != body.mime_type:
            raise InvalidOperation("Local upload does not match authorization")
        assert operation.temporary_key is not None
        await self.storage.put(operation.temporary_key, content, mime)
        await self._commit()

    async def cancel(self, identifier: UUID, user: UUID) -> None:
        operation = await self._operation(identifier, user)
        if operation.status in {"CANCELLED", "CLEANED"}:
            return
        if operation.status == "COMPLETED":
            raise ResourceConflict("Delete the confirmed asset instead")
        operation.status = "CANCELLED"
        operation.updated_at = datetime.now(UTC)
        await self._commit()

    async def delete(self, asset_id: UUID, user: UUID) -> None:
        asset = await self.media.get(asset_id, lock=True)
        if asset is None:
            operation = await self.operations.deletion(asset_id)
            if operation is None:
                raise ResourceNotFound("Media asset not found")
            # Existing durable tombstone makes repeated deletion idempotent.
            if operation.storage_provider != self.settings.storage_provider:
                raise ResourceConflict("Operation belongs to another storage provider")
            await self._commit()
            await self.reconcile(operation.id)
            return
        if await self.media.is_referenced(asset_id):
            raise ResourceConflict("Media asset is still referenced")
        if asset.storage_provider not in {"r2", "local"}:
            await self.media.delete(asset)
            await self._commit()
            return
        if asset.storage_provider != self.settings.storage_provider:
            raise ResourceConflict("Asset belongs to another storage provider")
        operation = StorageOperation(
            id=uuid4(),
            kind="DELETE",
            status="CLEANUP_PENDING",
            created_by=user,
            storage_provider=asset.storage_provider,
            storage_key=asset.storage_key,
            media_id=asset.id,
            expected_metadata={},
            expires_at=datetime.now(UTC),
        )
        self.session.add(operation)
        await self.media.delete(asset)
        # Delete intent and metadata removal are atomic, before remote deletion.
        await self._commit()
        await self.reconcile(operation.id)

    async def reconcile(self, identifier: UUID) -> bool:
        operation = await self.operations.get(identifier)
        if operation is None or operation.storage_provider != self.settings.storage_provider:
            return False
        if operation.kind == "DELETE" and operation.status != "CLEANUP_PENDING":
            return True
        if operation.kind == "UPLOAD":
            deadline = operation.expires_at + timedelta(
                seconds=self.settings.media_cleanup_grace_seconds
            )
            if datetime.now(UTC) <= deadline:
                return False
        try:
            if operation.kind == "DELETE":
                if await self.operations.registered(
                    operation.storage_provider, operation.storage_key
                ):
                    raise ResourceConflict("Cleanup object is registered")
                await self.storage.delete(operation.storage_key)
                operation.status = "COMPLETED"
            else:
                if operation.temporary_key:
                    await self.storage.delete(operation.temporary_key)
                    operation.temporary_key = None
                if operation.status != "COMPLETED":
                    if not await self.operations.registered(
                        operation.storage_provider, operation.storage_key
                    ):
                        await self.storage.delete(operation.storage_key)
                    operation.status = "CLEANED"
            operation.updated_at = datetime.now(UTC)
            await self._commit()
            return True
        except StorageError:
            # The durable intent survives failures and process crashes; retry is safe.
            operation.updated_at = datetime.now(UTC)
            await self._commit()
            return False

    async def cleanup(self, limit: int = 100) -> int:
        deadline = datetime.now(UTC) - timedelta(seconds=self.settings.media_cleanup_grace_seconds)
        candidates = await self.operations.cleanup_candidates(
            deadline, limit, self.settings.storage_provider
        )
        await self._commit()
        count = 0
        for identifier in candidates:
            count += await self.reconcile(identifier)
            await self._commit()
        return count

    async def delivery(self, asset_id: UUID, *, public: bool) -> tuple[str, str]:
        asset = await self.media.get(asset_id)
        if asset is None:
            raise ResourceNotFound("Media asset not found")
        if asset.storage_provider not in {"r2", "local"}:
            raise ResourceNotFound("Managed asset not found")
        if asset.storage_provider != self.settings.storage_provider:
            raise ResourceNotFound("Storage provider not available")
        policy = (asset.asset_metadata or {}).get("_storage")
        if public and (
            not isinstance(policy, dict)
            or policy.get("access") != "public"
            or not await self.operations.publicly_referenced(asset_id)
        ):
            raise ResourceNotFound("Media asset not found")
        return asset.storage_key, asset.mime_type
