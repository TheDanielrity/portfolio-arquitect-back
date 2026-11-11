import asyncio
import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.database import Database
from app.core.security import Security
from app.models import Profile, SiteSetting, SocialLink
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_portfolio_integration import BASE, asset

pytestmark = pytest.mark.integration


@pytest.fixture
def content_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL content tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


def test_profile_bootstrap_concurrency_update_and_media_validation(content_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        path = f"{BASE}/profile"
        assert (await client.get(path)).status_code == 404
        assert (await client.patch(path, json={"first_name": "Ada"})).status_code == 404
        body = {"first_name": "Ada", "last_name": "Lima"}
        results = await asyncio.gather(client.post(path, json=body), client.post(path, json=body))
        assert sorted(response.status_code for response in results) == [201, 409]
        row = (await client.get(path)).json()
        assert row["is_active"] is True
        assert (await client.get(path)).headers["Cache-Control"] == "no-store"
        photo, cv, video = (
            await asset(client),
            await asset(client, "PDF"),
            await asset(client, "VIDEO"),
        )
        changed = await client.patch(
            path,
            json={
                "profile_media_id": photo,
                "cv_media_id": cv,
                "email": "ada@example.org",
                "biography": "Architect",
                "first_name": " Ada Maria ",
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["first_name"] == "Ada Maria"
        assert changed.json()["id"] == row["id"]
        for changes, status in (
            ({"profile_media_id": cv}, 400),
            ({"cv_media_id": video}, 400),
            ({"cv_media_id": str(uuid4())}, 404),
        ):
            assert (
                await client.patch(path, json=changes | {"biography": "Rollback"})
            ).status_code == status
            assert (await client.get(path)).json()["biography"] == "Architect"
        for media_id in (photo, cv):
            assert (await client.delete(f"{BASE}/media/{media_id}")).status_code == 409
        document = await asset(client, "DOCUMENT")
        assert (await client.patch(path, json={"cv_media_id": document})).status_code == 200
        assert (
            await client.patch(
                path, json={"profile_media_id": None, "cv_media_id": None, "email": None}
            )
        ).status_code == 200
        assert (await client.delete(f"{BASE}/media/{photo}")).status_code == 204
        # PostgreSQL independently enforces the one-active-profile rule.
        async with database.session() as session:
            session.add(Profile(first_name="Other", last_name="Architect", is_active=True))
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            count = await session.scalar(
                select(func.count()).select_from(Profile).where(Profile.is_active.is_(True))
            )
            assert count == 1

    exercise(content_database, check)


def test_social_crud_ordering_visibility_and_active_profile_scope(content_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        path = f"{BASE}/profile/social-links"
        assert (await client.get(path)).status_code == 404
        await client.post(f"{BASE}/profile", json={"first_name": "Ada", "last_name": "Lima"})
        row = (
            await client.post(
                path, json={"platform": "Instagram", "url": "https://example.org/ada"}
            )
        ).json()
        detail = path + f"/{row['id']}"
        assert (await client.get(detail)).json() == row
        assert (
            await client.post(path, json={"platform": " instagram ", "url": "https://example.org"})
        ).status_code == 409
        second = (
            await client.post(
                path, json={"platform": "LinkedIn", "url": "https://example.org/linkedin"}
            )
        ).json()
        assert (
            await client.patch(detail, json={"platform": "linkedin", "username": "Rollback"})
        ).status_code == 409
        changed = await client.patch(
            detail, json={"url": "https://example.org/new", "username": "ada", "is_visible": False}
        )
        assert changed.status_code == 200 and changed.json()["is_visible"] is False
        assert (await client.patch(detail, json={"username": None})).json()["username"] is None
        async with database.session() as session:
            async with session.begin():
                inactive = Profile(first_name="Other", last_name="Architect", is_active=False)
                session.add(inactive)
                await session.flush()
                foreign = SocialLink(
                    profile_id=inactive.id, platform="Web", url="https://example.org"
                )
                session.add(foreign)
                await session.flush()
                foreign_id = str(foreign.id)
        assert (await client.get(path + f"/{foreign_id}")).status_code == 404
        assert (await client.delete(path + f"/{foreign_id}")).status_code == 404
        order = {"items": [{"id": row["id"], "sort_order": 9}, {"id": foreign_id, "sort_order": 0}]}
        assert (await client.put(path + "/order", json=order)).status_code == 404
        assert (await client.get(detail)).json()["sort_order"] == 0
        order["items"] = [{"id": row["id"], "sort_order": 9}, {"id": second["id"], "sort_order": 1}]
        assert (await client.put(path + "/order", json=order)).status_code == 204
        page = (await client.get(path, params={"limit": 1, "offset": 1})).json()
        assert page["total"] == 2 and page["items"][0]["id"] == row["id"]
        assert (await client.delete(detail)).status_code == 204
        assert (await client.get(detail)).status_code == 404

    exercise(content_database, check)


def test_services_crud_conflicts_atomic_order_and_visibility(content_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        path = f"{BASE}/services"
        body = {"name": "Design", "slug": " DESIGN ", "icon": "blueprint"}
        created = await client.post(path, json=body)
        assert created.status_code == 201, created.text
        row = created.json()
        detail = path + f"/{row['id']}"
        assert row["slug"] == "design" and (await client.get(detail)).json() == row
        assert (await client.post(path, json=body)).status_code == 409
        second = (await client.post(path, json={"name": "Planning", "slug": "planning"})).json()
        assert (
            await client.patch(detail, json={"slug": "PLANNING", "name": "Rollback"})
        ).status_code == 409
        assert (await client.get(detail)).json()["name"] == "Design"
        changed = await client.patch(
            detail, json={"is_visible": False, "description": "New", "icon": None}
        )
        assert changed.status_code == 200 and changed.json()["is_visible"] is False
        assert (await client.patch(detail, json={"description": None})).json()[
            "description"
        ] is None
        bad = {
            "items": [
                {"id": row["id"], "sort_order": 9},
                {"id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "sort_order": 9},
            ]
        }
        assert (await client.put(path + "/order", json=bad)).status_code == 404
        assert (await client.get(detail)).json()["sort_order"] == 0
        assert (
            await client.put(
                path + "/order",
                json={"items": [{"id": item["id"], "sort_order": 4} for item in (row, second)]},
            )
        ).status_code == 204
        first_page = (await client.get(path, params={"limit": 1})).json()
        second_page = (await client.get(path, params={"limit": 1, "offset": 1})).json()
        assert (
            first_page["total"] == 2
            and first_page["items"][0]["id"] != second_page["items"][0]["id"]
        )
        assert (await client.delete(detail)).status_code == 204
        assert (await client.get(detail)).status_code == 404
        assert (await client.post(path, json=body)).status_code == 201

    exercise(content_database, check)


def test_settings_allowlist_validation_and_concurrent_upsert(content_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        path = f"{BASE}/site-settings"
        assert (await client.get(path)).json() == []
        assert (await client.get(path + "/site_title")).status_code == 404
        values = {
            "site_title": "Architecture",
            "site_description": "Selected works",
            "contact_enabled": True,
        }
        for key, value in values.items():
            updated = await client.put(path + f"/{key}", json={"value": value})
            assert updated.status_code == 200, updated.text
            assert (await client.get(path + f"/{key}")).json()["value"] == value
        for key in ("jwt_secret_key", "database_url", "custom_script"):
            assert (
                await client.put(path + f"/{key}", json={"value": "not-allowed"})
            ).status_code == 422
        for key, value in (
            ("site_title", True),
            ("contact_enabled", "false"),
            ("site_description", "<script>bad</script>"),
        ):
            assert (await client.put(path + f"/{key}", json={"value": value})).status_code == 400
            assert (await client.get(path + f"/{key}")).json()["value"] == values[key]
        assert (
            await client.put(path + "/site_title", json={"value": {"nested": "bad"}})
        ).status_code == 422
        results = await asyncio.gather(
            *[
                client.put(path + "/site_title", json={"value": value})
                for value in ("First", "Second")
            ]
        )
        assert all(response.status_code == 200 for response in results)
        async with database.session() as session:
            async with session.begin():
                session.add(SiteSetting(key="legacy_private_key", value="must-not-be-returned"))
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(SiteSetting)
                    .where(SiteSetting.key == "site_title")
                )
                == 1
            )
        response = await client.get(path)
        assert len(response.json()) == 3 and "must-not-be-returned" not in response.text
        assert response.headers["Cache-Control"] == "no-store"

    exercise(content_database, check)
