import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import Database
from app.core.security import Security
from app.models import (
    MediaAsset,
    Profile,
    Project,
    ProjectMedia,
    ProjectSection,
    ProjectSectionMedia,
    RefreshToken,
)
from app.modules.media.repository import MediaRepository
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import authorization, create_user, exercise, login
from tests.test_media_schemas import payload

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def media_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL media tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


async def authorize(client: AsyncClient, database: Database, security: Security) -> UUID:
    user = await create_user(database, security)
    client.headers.update(authorization(await login(client, user)))
    return user.id


def test_media_crud_roundtrip_and_null_patch(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        body = payload(
            storage_key=uuid4().hex,
            width=1920,
            height=1080,
            title="Original",
            metadata={"nested": {"credit": "Ada"}},
        )
        created = await client.post("/api/v1/admin/media", json=body)
        assert created.status_code == 201, created.text
        asset = created.json()
        path = f"/api/v1/admin/media/{asset['id']}"
        assert asset["metadata"] == body["metadata"]
        assert "asset_metadata" not in asset
        assert asset["width"] == 1920 and asset["height"] == 1080
        assert asset["storage_key"] == body["storage_key"]
        assert created.headers["Cache-Control"] == "no-store"
        assert (await client.get(path)).json() == asset
        updated = await client.patch(
            path, json={"alt_text": "Courtyard", "metadata": {"replacement": True}}
        )
        assert updated.status_code == 200
        assert updated.json()["metadata"] == {"replacement": True}
        assert updated.json()["title"] == "Original"
        assert updated.json()["updated_at"] >= asset["updated_at"]
        cleared = await client.patch(path, json={"title": None, "metadata": None})
        assert cleared.json()["title"] is None and cleared.json()["metadata"] is None
        assert cleared.json()["alt_text"] == "Courtyard"
        unchanged = await client.patch(path, json={})
        assert unchanged.json() == cleared.json()
        deleted = await client.delete(path)
        assert deleted.status_code == 204 and deleted.content == b""
        for method in ("GET", "DELETE", "PATCH"):
            response = await client.request(method, path, json={} if method == "PATCH" else None)
            assert response.status_code == 404
            assert response.json() == {"detail": "Media asset not found"}

    exercise(media_database, check)


def test_unique_storage_conflict_and_provider_independence(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        body = payload(storage_key=uuid4().hex, storage_provider="provider-one")
        assert (await client.post("/api/v1/admin/media", json=body)).status_code == 201
        duplicate = await client.post("/api/v1/admin/media", json=body)
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "This storage object is already registered"}
        assert "uq_media_asset_storage" not in duplicate.text
        assert (
            await client.post(
                "/api/v1/admin/media", json=body | {"storage_provider": "provider-two"}
            )
        ).status_code == 201

    exercise(media_database, check)


def test_pagination_type_filter_and_nullable_dimensions(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        initial = (await client.get("/api/v1/admin/media?type=PDF")).json()["total"]
        ids = []
        for index in range(3):
            response = await client.post(
                "/api/v1/admin/media",
                json=payload(
                    type="PDF",
                    mime_type="application/pdf",
                    storage_key=uuid4().hex,
                    title=str(index),
                ),
            )
            assert response.status_code == 201
            assert response.json()["width"] is None and response.json()["height"] is None
            ids.append(response.json()["id"])
        page = (await client.get("/api/v1/admin/media?type=PDF&limit=2&offset=0")).json()
        assert page["total"] == initial + 3 and page["limit"] == 2 and page["offset"] == 0
        assert [item["id"] for item in page["items"]] == list(reversed(ids))[0:2]
        next_page = (await client.get("/api/v1/admin/media?type=PDF&limit=1&offset=2")).json()
        assert next_page["items"][0]["id"] == ids[0]
        empty = (await client.get(f"/api/v1/admin/media?type=PDF&offset={initial + 3}")).json()
        assert empty["items"] == [] and empty["total"] == initial + 3

    exercise(media_database, check)


@pytest.mark.parametrize("reference", ["project", "deleted_project", "section", "profile", "cv"])
def test_referenced_assets_cannot_be_removed(media_database: str, reference: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        response = await client.post("/api/v1/admin/media", json=payload(storage_key=uuid4().hex))
        assert response.status_code == 201
        asset_id = UUID(response.json()["id"])
        async with database.session() as session, session.begin():
            if reference in ("profile", "cv"):
                profile = Profile(first_name="Ada", last_name="Lovelace", is_active=False)
                if reference == "profile":
                    profile.profile_media_id = asset_id
                else:
                    profile.cv_media_id = asset_id
                session.add(profile)
            else:
                project = Project(title="House", slug=f"house-{uuid4().hex}")
                session.add(project)
                await session.flush()
                if reference == "deleted_project":
                    project.deleted_at = datetime.now(UTC)
                if reference == "section":
                    section = ProjectSection(project_id=project.id, section_type="IMAGE")
                    session.add(section)
                    await session.flush()
                    session.add(ProjectSectionMedia(section_id=section.id, media_id=asset_id))
                else:
                    session.add(
                        ProjectMedia(project_id=project.id, media_id=asset_id, role="COVER")
                    )
        path = f"/api/v1/admin/media/{asset_id}"
        rejected = await client.delete(path)
        assert rejected.status_code == 409
        assert rejected.json() == {"detail": "Media asset is still referenced"}
        assert (await client.get(path)).status_code == 200
        async with database.session() as session:
            assert await session.get(MediaAsset, asset_id) is not None
            if reference in ("profile", "cv"):
                field = Profile.profile_media_id if reference == "profile" else Profile.cv_media_id
                assert await session.scalar(select(field).where(field == asset_id)) == asset_id

    exercise(media_database, check)


def test_revoked_admin_session_cannot_manage_media(media_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user_id = await authorize(client, database, security)
        response = await client.post("/api/v1/admin/media", json=payload(storage_key=uuid4().hex))
        assert response.status_code == 201
        path = f"/api/v1/admin/media/{response.json()['id']}"
        async with database.session() as session, session.begin():
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id)
                .values(revoked_at=datetime.now(UTC))
            )
        for method in ("GET", "PATCH", "DELETE"):
            response = await client.request(method, path, json={} if method == "PATCH" else None)
            assert response.status_code == 401
        assert (
            await client.post("/api/v1/admin/media", json=payload(storage_key=uuid4().hex))
        ).status_code == 401

    exercise(media_database, check)


def test_delete_serializes_against_new_profile_reference(
    media_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        response = await client.post("/api/v1/admin/media", json=payload(storage_key=uuid4().hex))
        assert response.status_code == 201
        asset_id = UUID(response.json()["id"])
        checked, release, inserting = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original = MediaRepository.is_referenced

        async def pause_after_check(repository: MediaRepository, target: UUID) -> bool:
            referenced = await original(repository, target)
            checked.set()
            await release.wait()
            return referenced

        async def attach_profile() -> bool:
            try:
                async with database.session() as session, session.begin():
                    session.add(
                        Profile(
                            first_name="Concurrent",
                            last_name="Profile",
                            is_active=False,
                            profile_media_id=asset_id,
                        )
                    )
                    inserting.set()
                    await session.flush()
                return True
            except IntegrityError:
                return False

        with monkeypatch.context() as patch:
            patch.setattr(MediaRepository, "is_referenced", pause_after_check)
            deletion = asyncio.create_task(client.delete(f"/api/v1/admin/media/{asset_id}"))
            try:
                await asyncio.wait_for(checked.wait(), timeout=5)
                attachment = asyncio.create_task(attach_profile())
                await asyncio.wait_for(inserting.wait(), timeout=5)
                try:
                    with pytest.raises(TimeoutError):
                        await asyncio.wait_for(asyncio.shield(attachment), timeout=0.2)
                finally:
                    release.set()
                assert (await asyncio.wait_for(deletion, timeout=5)).status_code == 204
                assert await asyncio.wait_for(attachment, timeout=5) is False
            finally:
                release.set()
                if not deletion.done():
                    await asyncio.wait_for(deletion, timeout=5)

    exercise(media_database, check)
