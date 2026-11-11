import asyncio
import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import Database
from app.core.security import Security
from app.models import ContactMessage
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize

PUBLIC = "/api/v1/public/contact"
ADMIN = "/api/v1/admin/contact-messages"
BODY = {"name": "Ada", "email": "ada@example.org", "message": "Please discuss my project."}
pytestmark = pytest.mark.integration


@pytest.fixture
def contact_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL contact tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


def test_public_submission_validation_and_private_metadata(contact_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        response = await client.post(
            PUBLIC,
            json=BODY | {"phone": "+51 999 123 456", "subject": "Design"},
            headers={"User-Agent": "contact-test", "X-Forwarded-For": "203.0.113.77"},
        )
        assert response.status_code == 201, response.text
        assert response.json() == {"detail": "Message received"}
        assert response.headers["Cache-Control"] == "no-store"
        for changes in ({"email": "bad-email"}, {"message": " "}, {"status": "REPLIED"}):
            rejected = await client.post(PUBLIC, json=BODY | changes)
            assert rejected.status_code == 422
            assert BODY["message"] not in rejected.text
        async with database.session() as session:
            row = (await session.scalars(select(ContactMessage))).one()
            assert row.status == "NEW" and row.read_at is None and row.replied_at is None
            assert str(row.ip_address) == "127.0.0.1" and row.user_agent == "contact-test"
            assert row.phone == "+51 999 123 456" and row.subject == "Design"
            item_id = str(row.id)
        assert (await client.get(f"{ADMIN}/{item_id}")).status_code == 401
        await authorize(client, database, security)
        response = await client.get(f"{ADMIN}/{item_id}")
        assert response.status_code == 200 and response.json()["status"] == "NEW"
        assert "ip_address" not in response.json() and "user_agent" not in response.json()
        assert response.headers["Cache-Control"] == "no-store"
        assert (await client.get(f"{ADMIN}/{uuid4()}")).status_code == 404
        assert (
            await client.patch(f"{ADMIN}/{uuid4()}/status", json={"status": "READ"})
        ).status_code == 404

    exercise(contact_database, check)


def test_rate_limited_submissions_do_not_persist(contact_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        for _ in range(10):
            assert (await client.post(PUBLIC, json=BODY)).status_code == 201
        response = await client.post(PUBLIC, json=BODY)
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) >= 1
        async with database.session() as session:
            assert await session.scalar(select(func.count()).select_from(ContactMessage)) == 10

    exercise(contact_database, check)


def test_status_transitions_timestamps_and_concurrency(contact_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await client.post(PUBLIC, json=BODY)
        await authorize(client, database, security)
        row = (await client.get(ADMIN)).json()["items"][0]
        path = f"{ADMIN}/{row['id']}/status"
        read = await client.patch(path, json={"status": "READ"})
        assert read.status_code == 200
        first_read = read.json()["read_at"]
        assert first_read >= row["created_at"] and read.json()["replied_at"] is None
        reply = await client.patch(path, json={"status": "REPLIED"})
        first_reply = reply.json()["replied_at"]
        assert first_reply >= first_read
        for status in ("REPLIED", "ARCHIVED", "SPAM", "READ", "REPLIED"):
            changed = await client.patch(path, json={"status": status})
            assert changed.status_code == 200 and changed.json()["status"] == status
            assert changed.json()["read_at"] == first_read
            assert changed.json()["replied_at"] == first_reply
        for invalid_status in ("NEW", "INVALID", None):
            assert (await client.patch(path, json={"status": invalid_status})).status_code == 422
        assert (await client.get(f"{ADMIN}/{row['id']}")).json()["status"] == "REPLIED"
        await client.post(PUBLIC, json=BODY | {"name": "Second"})
        second = (await client.get(ADMIN)).json()["items"][0]
        second_path = f"{ADMIN}/{second['id']}/status"
        results = await asyncio.gather(
            *[client.patch(second_path, json={"status": "REPLIED"}) for _ in range(2)]
        )
        assert all(result.status_code == 200 for result in results)
        assert results[0].json() == results[1].json()
        assert results[0].json()["read_at"] == results[0].json()["replied_at"]
        async with database.session() as session:
            stored = await session.get(ContactMessage, UUID(second["id"]))
            assert stored is not None and stored.replied_at is not None
            assert stored.read_at == stored.replied_at >= stored.created_at

    exercise(contact_database, check)


def test_listing_filters_pagination_and_archive_without_reading(contact_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        assert (await client.get(ADMIN)).json() == {
            "items": [],
            "total": 0,
            "limit": 20,
            "offset": 0,
        }
        for name in ("First", "Second", "Third"):
            assert (await client.post(PUBLIC, json=BODY | {"name": name})).status_code == 201
        rows = (await client.get(ADMIN)).json()["items"]
        assert [row["name"] for row in rows] == ["Third", "Second", "First"]
        for row, status in zip(rows, ("ARCHIVED", "SPAM", "READ"), strict=True):
            result = await client.patch(f"{ADMIN}/{row['id']}/status", json={"status": status})
            assert result.status_code == 200
            if status != "READ":
                assert result.json()["read_at"] is None and result.json()["replied_at"] is None
            filtered = (await client.get(ADMIN, params={"status": status})).json()
            assert filtered["total"] == 1 and filtered["items"][0]["id"] == row["id"]
        page = (await client.get(ADMIN, params={"limit": 1, "offset": 1})).json()
        assert page["total"] == 3 and page["items"][0]["id"] == rows[1]["id"]
        assert (await client.get(ADMIN, params={"offset": 10})).json()["items"] == []
        for query in ({"status": "INVALID"}, {"limit": 101}, {"offset": -1}):
            assert (await client.get(ADMIN, params=query)).status_code == 422

    exercise(contact_database, check)


def test_contact_enabled_setting_controls_persistence(contact_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        setting = "/api/v1/admin/site-settings/contact_enabled"
        assert (await client.put(setting, json={"value": False})).status_code == 200
        assert (await client.post(PUBLIC, json=BODY)).status_code == 400
        async with database.session() as session:
            assert await session.scalar(select(func.count()).select_from(ContactMessage)) == 0
        assert (await client.put(setting, json={"value": True})).status_code == 200
        assert (await client.post(PUBLIC, json=BODY)).status_code == 201

    exercise(contact_database, check)
