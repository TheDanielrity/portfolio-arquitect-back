"""Exercise administrative listing conventions against migrated PostgreSQL."""

import asyncio
import os
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import Database
from app.core.security import Security
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_media_schemas import payload

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin"


@pytest.fixture
def admin_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated administrative API tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


@pytest.mark.parametrize(
    ("collection", "field", "filter_name", "filter_value"),
    [
        ("projects", "title", "status", "DRAFT"),
        ("categories", "name", "is_active", "false"),
        ("tags", "name", None, None),
        ("media", "original_filename", "type", "IMAGE"),
        ("services", "name", "is_visible", "false"),
        ("profile/social-links", "platform", "is_visible", "false"),
        ("contact-messages", "name", "status", "NEW"),
    ],
)
def test_search_sort_filters_and_pagination(
    admin_database: str,
    collection: str,
    field: str,
    filter_name: str | None,
    filter_value: str | None,
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        if collection == "profile/social-links":
            assert (
                await client.post(
                    f"{BASE}/profile",
                    json={
                        "first_name": "Ada",
                        "last_name": "Lima",
                    },
                )
            ).status_code == 201
        for index, name in enumerate(("Beta%_", "alpha%_", "Other")):
            body: dict[str, Any] = {field: name}
            if collection in ("projects", "categories", "tags", "services"):
                body["slug"] = uuid4().hex
            if collection in ("services", "profile/social-links"):
                body["is_visible"] = index == 2
            if collection == "categories":
                body["is_active"] = index == 2
            if collection == "profile/social-links":
                body["url"] = "https://example.org/profile"
            if collection == "media":
                body = payload(storage_key=uuid4().hex, original_filename=name)
            path = f"{BASE}/{collection}"
            if collection == "contact-messages":
                body.update(email="ada@example.org", message="Please contact me")
                path = "/api/v1/public/contact"
            response = await client.post(path, json=body)
            assert response.status_code == 201, response.text

        path = f"{BASE}/{collection}"
        query = {"q": " %_ ", "sort": field, "direction": "asc", "limit": "1"}
        if filter_name is not None and filter_value is not None:
            query[filter_name] = filter_value
        first = await client.get(path, params=query)
        assert first.status_code == 200, first.text
        page = first.json()
        assert set(page) == {"items", "total", "limit", "offset"}
        assert (page["total"], page["limit"], page["offset"]) == (2, 1, 0)
        assert page["items"][0][field] == "alpha%_"
        assert first.headers["Cache-Control"] == "no-store"
        second = (await client.get(path, params=query | {"offset": "1"})).json()
        assert second["items"][0][field] == "Beta%_"
        assert second["total"] == 2 and second["offset"] == 1
        descending = (await client.get(path, params=query | {"direction": "desc"})).json()
        assert descending["items"][0]["id"] == second["items"][0]["id"]
        empty = (await client.get(path, params=query | {"offset": "2"})).json()
        assert empty["items"] == [] and empty["total"] == 2
        assert (await client.get(path, params={"q": "ALPHA"})).json()["total"] == 1
        assert (await client.get(path, params={"q": "' OR 1=1 --"})).json()["total"] == 0
        schema = (await client.get("/openapi.json")).json()
        parameters = schema["paths"][path]["get"]["parameters"]
        sorts = next(item["schema"]["enum"] for item in parameters if item["name"] == "sort")
        for sort in sorts:
            for direction in ("asc", "desc"):
                response = await client.get(path, params={"sort": sort, "direction": direction})
                assert response.status_code == 200, response.text
                assert response.json()["total"] == 3
        first_default = (await client.get(path, params={"limit": 1})).json()
        second_default = (await client.get(path, params={"limit": 1, "offset": 1})).json()
        assert first_default["items"][0]["id"] != second_default["items"][0]["id"]
        assert (await client.get(path, params={"limit": 1})).json() == first_default
        if filter_name is not None:
            filter_only = (await client.get(path, params={filter_name: str(filter_value)})).json()
            assert filter_only["total"] == (2 if filter_value == "false" else 3)

        if collection == "projects":
            item_id = page["items"][0]["id"]
            assert (await client.delete(f"{path}/{item_id}")).status_code == 204
            assert (await client.get(path, params={"q": "ALPHA"})).json()["total"] == 0

    exercise(admin_database, check)
