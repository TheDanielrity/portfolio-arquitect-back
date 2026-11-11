import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.database import Database
from app.core.security import Security
from app.models import (
    MediaAsset,
    Profile,
    Project,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
)
from app.modules.media.operation_models import StorageOperation
from app.modules.media.repository import MediaRepository
from app.modules.media.storage_adapters import LocalStorageAdapter
from app.modules.media.storage_port import ObjectMissing, StorageError
from app.modules.media.upload_service import UploadService
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_media_integration import media_database as media_database

pytestmark = pytest.mark.integration
DATA = b"\xff\xd8\xfftest-content"


async def upload(
    client: AsyncClient, *, access: str = "private", put: bool = True
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/media/uploads/presign",
        json={
            "original_filename": "building.jpg",
            "mime_type": "image/jpeg",
            "file_size": len(DATA),
            "access": access,
        },
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    if put:
        response = await client.put(result["upload_url"], content=DATA, headers=result["headers"])
        assert response.status_code == 204, response.text
    return result


async def confirm(client: AsyncClient, identifier: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/media/uploads/confirm", json={"upload_id": identifier}
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_upload_roundtrip_concurrent_confirmation_and_replay(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        authorization = await upload(client)
        other = await upload(client, put=False)
        assert other["upload_id"] != authorization["upload_id"]
        first, second = await asyncio.gather(
            confirm(client, authorization["upload_id"]), confirm(client, authorization["upload_id"])
        )
        assert first["id"] == second["id"]
        assert first["storage_key"].startswith("objects/")
        assert first["file_size"] == len(DATA) and first["width"] is None
        assert "X-Amz" not in first["url"]
        async with database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(MediaAsset)
                    .where(MediaAsset.storage_key == first["storage_key"])
                )
                == 1
            )
        # PUT cannot replace a confirmed local upload; R2 PUT can only change staging.
        assert (
            await client.put(
                authorization["upload_url"], content=DATA, headers=authorization["headers"]
            )
        ).status_code == 409
        path = f"/api/v1/admin/media/{first['id']}"
        assert (await client.get(path)).status_code == 200
        assert (await client.get(f"{path}/content")).content == DATA
        assert (await client.get(first["url"])).status_code == 404
        assert (
            await client.patch(path, json={"metadata": {"_storage": {"access": "public"}}})
        ).status_code == 400
        assert (await client.patch(path, json={"metadata": None})).json()["metadata"]["_storage"][
            "access"
        ] == "private"
        deleted = await asyncio.gather(client.delete(path), client.delete(path))
        assert [response.status_code for response in deleted] == [204, 204]
        assert (await client.delete(path)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (
            await client.post(
                "/api/v1/admin/media/uploads/confirm",
                json={"upload_id": authorization["upload_id"]},
            )
        ).status_code == 409
        adapter = LocalStorageAdapter(Settings())
        with pytest.raises(ObjectMissing):
            await adapter.head(first["storage_key"])
        async with database.session() as session:
            operations = list(
                await session.scalars(
                    select(StorageOperation).where(
                        StorageOperation.storage_key == first["storage_key"]
                    )
                )
            )
            assert {op.kind for op in operations} == {"UPLOAD", "DELETE"}
            assert all(op.status == "COMPLETED" for op in operations)

    exercise(media_database, check)


def test_missing_expired_cross_admin_and_cancelled_authorizations(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        owner = await authorize(client, database, security)
        authorization = await upload(client, put=False)
        target = "/api/v1/admin/media/uploads/confirm"
        assert (await client.post(target, json={"upload_id": str(uuid4())})).status_code == 404
        assert (
            await client.post(target, json={"upload_id": authorization["upload_id"]})
        ).status_code == 400
        await authorize(client, database, security)
        assert (
            await client.post(target, json={"upload_id": authorization["upload_id"]})
        ).status_code == 404
        # Restore operation ownership to current administrator for expiry/cancellation checks.
        current = (await client.get("/api/v1/auth/me")).json()["id"]
        async with database.session() as session, session.begin():
            await session.execute(
                update(StorageOperation)
                .where(StorageOperation.id == UUID(authorization["upload_id"]))
                .values(
                    created_by=UUID(current), expires_at=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
        assert owner != UUID(current)
        assert (
            await client.post(target, json={"upload_id": authorization["upload_id"]})
        ).status_code == 400
        pending = await upload(client)
        path = f"/api/v1/admin/media/uploads/{pending['upload_id']}"
        assert (await client.delete(path)).status_code == 204
        assert (await client.delete(path)).status_code == 204
        assert (
            await client.post(target, json={"upload_id": pending["upload_id"]})
        ).status_code == 409

    exercise(media_database, check)


@pytest.mark.parametrize("invalid", ["size", "mime", "header"])
def test_remote_object_mismatch_and_grace_cleanup(media_database: str, invalid: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        owner = await authorize(client, database, security)
        authorization = await upload(client)
        identifier = UUID(authorization["upload_id"])
        adapter = LocalStorageAdapter(Settings())
        async with database.session() as session:
            operation = await session.get(StorageOperation, identifier)
            assert operation is not None and operation.temporary_key is not None
            key = operation.temporary_key
        await adapter.put(
            key,
            DATA + b"x"
            if invalid == "size"
            else (b"x" * len(DATA) if invalid == "header" else DATA),
            "image/png" if invalid == "mime" else "image/jpeg",
        )
        response = await client.post(
            "/api/v1/admin/media/uploads/confirm", json={"upload_id": str(identifier)}
        )
        assert response.status_code == 400
        async with database.session() as session:
            service = UploadService(session, adapter, Settings())
            assert await service.reconcile(identifier) is False  # URL + grace still active.
        assert (await adapter.head(key)).size > 0
        async with database.session() as session, session.begin():
            await session.execute(
                update(StorageOperation)
                .where(StorageOperation.id == identifier)
                .values(expires_at=datetime.now(UTC) - timedelta(hours=2))
            )
        async with database.session() as session:
            assert await UploadService(session, adapter, Settings()).cleanup() >= 1
        with pytest.raises(ObjectMissing):
            await adapter.head(key)
        async with database.session() as session:
            operation = await session.get(StorageOperation, identifier)
            assert operation is not None and operation.status == "CLEANED"
            assert operation.created_by == owner and operation.media_id is None

    exercise(media_database, check)


@pytest.mark.parametrize("reference", ["project", "section", "photo", "cv"])
def test_managed_delete_checks_all_references(media_database: str, reference: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        asset = await confirm(client, (await upload(client))["upload_id"])
        identifier = UUID(asset["id"])
        async with database.session() as session, session.begin():
            if reference in {"photo", "cv"}:
                session.add(
                    Profile(
                        first_name="Test",
                        last_name="References",
                        is_active=False,
                        **{
                            (
                                "profile_media_id" if reference == "photo" else "cv_media_id"
                            ): identifier
                        },
                    )
                )
            else:
                project = Project(title="Test", slug=uuid4().hex)
                session.add(project)
                await session.flush()
                project.deleted_at = datetime.now(UTC)
                if reference == "project":
                    session.add(
                        ProjectMedia(project_id=project.id, media_id=identifier, role="GALLERY")
                    )
                else:
                    section = ProjectSection(project_id=project.id, section_type="IMAGE")
                    session.add(section)
                    await session.flush()
                    session.add(ProjectSectionMedia(section_id=section.id, media_id=identifier))
        assert (await client.delete(f"/api/v1/admin/media/{identifier}")).status_code == 409
        assert (await LocalStorageAdapter(Settings()).head(asset["storage_key"])).size == len(DATA)

    exercise(media_database, check)


def test_partial_confirmation_failure_recovers_immutable_destination(
    media_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        authorization = await upload(client)

        async def fail_create(repository: MediaRepository, values: dict[str, object]) -> MediaAsset:
            raise RuntimeError("Simulated database failure after copy")

        with monkeypatch.context() as patch:
            patch.setattr(MediaRepository, "create", fail_create)
            response = await client.post(
                "/api/v1/admin/media/uploads/confirm",
                json={"upload_id": authorization["upload_id"]},
            )
            assert response.status_code == 500
        async with database.session() as session:
            operation = await session.get(StorageOperation, UUID(authorization["upload_id"]))
            assert operation is not None and operation.status == "PROCESSING"
            assert operation.temporary_key is not None
            key = operation.temporary_key
        # Simulate a still-valid R2 PUT changing staging after the destination was copied.
        await LocalStorageAdapter(Settings()).put(key, b"bad", "image/png")
        asset = await confirm(client, authorization["upload_id"])
        assert asset["file_size"] == len(DATA)
        assert (await client.get(f"/api/v1/admin/media/{asset['id']}/content")).content == DATA

    exercise(media_database, check)


def test_delete_failure_keeps_retryable_intent(
    media_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        asset = await confirm(client, (await upload(client))["upload_id"])

        async def fail_delete(adapter: LocalStorageAdapter, key: str) -> None:
            raise StorageError("Simulated provider outage")

        path = f"/api/v1/admin/media/{asset['id']}"
        with monkeypatch.context() as patch:
            patch.setattr(LocalStorageAdapter, "delete", fail_delete)
            assert (await client.delete(path)).status_code == 204
        assert (await client.get(path)).status_code == 404
        adapter = LocalStorageAdapter(Settings())
        await adapter.head(asset["storage_key"])
        async with database.session() as session:
            operation = await session.scalar(
                select(StorageOperation).where(
                    StorageOperation.media_id == UUID(asset["id"]),
                    StorageOperation.kind == "DELETE",
                )
            )
            assert operation is not None and operation.status == "CLEANUP_PENDING"
        assert (await client.delete(path)).status_code == 204
        with pytest.raises(ObjectMissing):
            await adapter.head(asset["storage_key"])

    exercise(media_database, check)


def test_public_delivery_requires_policy_and_live_reference(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        asset = await confirm(client, (await upload(client, access="public"))["upload_id"])
        assert (await client.get(asset["url"])).status_code == 404
        async with database.session() as session, session.begin():
            project = Project(
                title="Public", slug=uuid4().hex, status="PUBLISHED", visibility="PUBLIC"
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMedia(project_id=project.id, media_id=UUID(asset["id"]), role="COVER")
            )
            project_id = project.id
        assert (await client.get(asset["url"])).content == DATA
        async with database.session() as session, session.begin():
            await session.execute(
                update(Project).where(Project.id == project_id).values(visibility="PRIVATE")
            )
        assert (await client.get(asset["url"])).status_code == 404

    exercise(media_database, check)


def test_partial_unique_index_allows_history_and_rejects_active_conflicts(
    media_database: str,
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        owner = await authorize(client, database, security)
        values = dict(
            created_by=owner,
            storage_provider="local",
            storage_key=f"objects/{uuid4().hex}.jpg",
            expires_at=datetime.now(UTC),
            expected_metadata={},
        )
        async with database.session() as session, session.begin():
            session.add(StorageOperation(kind="UPLOAD", status="COMPLETED", **values))
            session.add(StorageOperation(kind="DELETE", status="CLEANUP_PENDING", **values))
        with pytest.raises(IntegrityError):
            async with database.session() as session, session.begin():
                session.add(StorageOperation(kind="UPLOAD", status="PENDING", **values))

    exercise(media_database, check)


@pytest.mark.parametrize("after_remote", [False, True])
def test_delete_database_failure_recovery(
    media_database: str, monkeypatch: pytest.MonkeyPatch, after_remote: bool
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        asset = await confirm(client, (await upload(client))["upload_id"])
        path = f"/api/v1/admin/media/{asset['id']}"
        original = UploadService._commit
        calls = 0

        async def fail_commit(service: UploadService) -> None:
            nonlocal calls
            calls += 1
            if calls == (2 if after_remote else 1):
                await service.session.rollback()
                raise RuntimeError("Simulated database commit failure")
            await original(service)

        with monkeypatch.context() as patch:
            patch.setattr(UploadService, "_commit", fail_commit)
            assert (await client.delete(path)).status_code == 500
        adapter = LocalStorageAdapter(Settings())
        if after_remote:
            with pytest.raises(ObjectMissing):
                await adapter.head(asset["storage_key"])
            assert (await client.get(path)).status_code == 404
        else:
            assert (await adapter.head(asset["storage_key"])).size == len(DATA)
            assert (await client.get(path)).status_code == 200
        assert (await client.delete(path)).status_code == 204
        assert (await client.delete(path)).status_code == 204

    exercise(media_database, check)


def test_provider_failure_after_authorization_intent(
    media_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        owner = await authorize(client, database, security)
        from app.modules.media.storage_port import UploadTarget

        async def fail_sign(
            adapter: LocalStorageAdapter, key: str, mime: str, expires: int
        ) -> UploadTarget:
            raise StorageError("Provider unavailable")

        with monkeypatch.context() as patch:
            patch.setattr(LocalStorageAdapter, "presign", fail_sign)
            result = await client.post(
                "/api/v1/admin/media/uploads/presign",
                json={
                    "original_filename": "x.jpg",
                    "mime_type": "image/jpeg",
                    "file_size": len(DATA),
                },
            )
            assert result.status_code == 503
        async with database.session() as session:
            operation = await session.scalar(
                select(StorageOperation).where(StorageOperation.created_by == owner)
            )
            assert operation is not None and operation.status == "PENDING"

    exercise(media_database, check)


def test_cleanup_serializes_with_confirmation(
    media_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        authorization = await upload(client)
        entered, release = asyncio.Event(), asyncio.Event()
        original = LocalStorageAdapter.promote

        async def pause(
            adapter: LocalStorageAdapter, source: str, destination: str, etag: str
        ) -> None:
            entered.set()
            await release.wait()
            await original(adapter, source, destination, etag)

        async def cleanup() -> bool:
            async with database.session() as session:
                return await UploadService(
                    session, LocalStorageAdapter(Settings()), Settings()
                ).reconcile(UUID(authorization["upload_id"]))

        with monkeypatch.context() as patch:
            patch.setattr(LocalStorageAdapter, "promote", pause)
            confirming = asyncio.create_task(confirm(client, authorization["upload_id"]))
            await asyncio.wait_for(entered.wait(), 5)
            cleaning = asyncio.create_task(cleanup())
            try:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(cleaning), 0.2)
            finally:
                release.set()
            asset = await asyncio.wait_for(confirming, 5)
            assert await asyncio.wait_for(cleaning, 5) is False
        assert (await LocalStorageAdapter(Settings()).head(asset["storage_key"])).size == len(DATA)

    exercise(media_database, check)


def test_unconfirmed_copy_cleanup_preserves_confirmed_destination(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        authorization = await upload(client)
        asset = await confirm(client, authorization["upload_id"])
        async with database.session() as session, session.begin():
            operation = await session.get(StorageOperation, UUID(authorization["upload_id"]))
            assert operation is not None and operation.temporary_key is not None
            staging = operation.temporary_key
            operation.expires_at = datetime.now(UTC) - timedelta(hours=2)
            operation.updated_at = datetime.now(UTC) - timedelta(days=2)
            # Older intents of another provider must not starve the configured batch.
            session.add(
                StorageOperation(
                    kind="UPLOAD",
                    status="PENDING",
                    created_by=operation.created_by,
                    storage_provider="r2",
                    storage_key=f"objects/{uuid4().hex}.jpg",
                    expected_metadata={},
                    expires_at=datetime.now(UTC) - timedelta(days=1),
                    updated_at=datetime.now(UTC) - timedelta(days=3),
                )
            )
        adapter = LocalStorageAdapter(Settings())
        async with database.session() as session:
            assert await UploadService(session, adapter, Settings()).cleanup(limit=1) == 1
        with pytest.raises(ObjectMissing):
            await adapter.head(staging)
        assert (await adapter.head(asset["storage_key"])).size == len(DATA)
        assert (await confirm(client, authorization["upload_id"]))["id"] == asset["id"]

    exercise(media_database, check)
