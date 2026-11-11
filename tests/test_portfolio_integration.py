import asyncio
import os
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import Database
from app.core.security import Security
from app.models import Project
from tests.migration_support import migrate, temporary_databases
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_media_schemas import payload

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin"


@pytest.fixture(scope="module")
def portfolio_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL portfolio tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


async def project(client: AsyncClient, **changes: object) -> dict[str, Any]:
    response = await client.post(
        f"{BASE}/projects",
        json={
            "title": "Courtyard",
            "slug": uuid4().hex,
        }
        | changes,
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def asset(client: AsyncClient, media_type: str = "IMAGE") -> str:
    response = await client.post(
        f"{BASE}/media",
        json=payload(
            storage_key=uuid4().hex,
            type=media_type,
        ),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_project_crud_conflicts_soft_delete_and_slug_reuse(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        row = await project(client, area_m2="123.45", description="Original")
        path = f"{BASE}/projects/{row['id']}"
        assert row["area_m2"] == "123.45"
        response = await client.get(path)
        assert response.json() == row and response.headers["Cache-Control"] == "no-store"
        assert (
            await client.post(
                f"{BASE}/projects",
                json={
                    "title": "Conflict",
                    "slug": row["slug"].upper(),
                },
            )
        ).status_code == 409
        second = await project(client)
        assert (
            await client.patch(path, json={"slug": second["slug"], "title": "Rollback"})
        ).status_code == 409
        assert (await client.get(path)).json()["title"] == row["title"]
        changed = await client.patch(
            path,
            json={
                "description": None,
                "is_featured": True,
                "visibility": "PRIVATE",
                "status": "ARCHIVED",
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["description"] is None and changed.json()["is_featured"] is True
        assert (await client.delete(path)).status_code == 204
        for method in ("GET", "PATCH", "DELETE"):
            assert (
                await client.request(method, path, json={} if method == "PATCH" else None)
            ).status_code == 404
        async with database.session() as session:
            stored = await session.scalar(select(Project).where(Project.id == UUID(row["id"])))
            assert stored is not None and stored.deleted_at is not None
        replacement = await project(client, slug=row["slug"])
        assert replacement["id"] != row["id"]
        listed = (await client.get(f"{BASE}/projects", params={"limit": 100})).json()
        assert row["id"] not in {item["id"] for item in listed["items"]}

    exercise(portfolio_database, check)


def test_publication_and_cover_replacement_rules(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        assert (
            await client.post(
                f"{BASE}/projects",
                json={
                    "title": "Invalid",
                    "slug": uuid4().hex,
                    "status": "PUBLISHED",
                },
            )
        ).status_code == 400
        row = await project(client)
        path = f"{BASE}/projects/{row['id']}"
        assert (
            await client.patch(path, json={"status": "PUBLISHED", "title": "Rollback"})
        ).status_code == 400
        assert (await client.get(path)).json()["title"] == row["title"]
        pdf = await asset(client, "PDF")
        assert (await client.put(path + "/cover", json={"media_id": pdf})).status_code == 400
        assert (
            await client.put(path + "/cover", json={"media_id": str(uuid4())})
        ).status_code == 404
        first, second = await asset(client), await asset(client)
        selected = await client.put(path + "/cover", json={"media_id": first})
        assert selected.status_code == 200, selected.text
        cover_id = selected.json()["id"]
        assert (await client.put(path + "/cover", json={"media_id": first})).json()[
            "id"
        ] == cover_id
        published = await client.patch(path, json={"status": "PUBLISHED"})
        assert published.status_code == 200, published.text
        timestamp = published.json()["published_at"]
        assert timestamp is not None
        for visibility in ("PUBLIC", "PRIVATE", "UNLISTED"):
            changed = await client.patch(path, json={"visibility": visibility})
            assert changed.status_code == 200 and changed.json()["visibility"] == visibility
            assert changed.json()["published_at"] == timestamp
        assert (await client.delete(path + f"/media/{cover_id}")).status_code == 409
        assert (
            await client.patch(path + f"/media/{cover_id}", json={"role": "GALLERY"})
        ).status_code == 409
        assert (
            await client.post(path + "/media", json={"media_id": second, "role": "COVER"})
        ).status_code == 409
        replaced = await client.put(path + "/cover", json={"media_id": second})
        assert replaced.status_code == 200
        links = (await client.get(path + "/media")).json()["items"]
        assert len(links) == 1 and links[0]["media_id"] == second
        assert (await client.get(f"{BASE}/media/{first}")).status_code == 200
        assert (await client.delete(f"{BASE}/media/{second}")).status_code == 409
        assert (await client.patch(path, json={"status": "DRAFT"})).status_code == 200
        assert (await client.delete(path + f"/media/{replaced.json()['id']}")).status_code == 204
        assert (await client.patch(path, json={"status": "PUBLISHED"})).status_code == 400

    exercise(portfolio_database, check)


@pytest.mark.parametrize("kind", ["categories", "tags"])
def test_taxonomy_crud_assignment_atomicity_and_safe_delete(
    portfolio_database: str, kind: str
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        body = {"name": uuid4().hex, "slug": uuid4().hex}
        created = await client.post(f"{BASE}/{kind}", json=body)
        assert created.status_code == 201, created.text
        item = created.json()
        path = f"{BASE}/{kind}/{item['id']}"
        assert (await client.get(path)).json() == item
        assert (
            await client.post(f"{BASE}/{kind}", json=body | {"slug": body["slug"].upper()})
        ).status_code == 409
        if kind == "tags":
            assert (
                await client.post(
                    f"{BASE}/{kind}",
                    json=body | {"name": body["name"].upper(), "slug": uuid4().hex},
                )
            ).status_code == 409
        else:
            assert (await client.patch(path, json={"is_active": False})).json()[
                "is_active"
            ] is False
        changed = await client.patch(path, json={"name": uuid4().hex})
        assert changed.status_code == 200 and changed.json()["name"] != body["name"]
        row = await project(client)
        assignments = f"{BASE}/projects/{row['id']}/{kind}"
        assert (await client.put(assignments, json={"ids": [item["id"]]})).status_code == 204
        assert (await client.delete(path)).status_code == 409
        assert (await client.put(assignments, json={"ids": [str(uuid4())]})).status_code == 404
        assigned = (await client.get(assignments, params={"limit": 1})).json()
        assert assigned["total"] == 1 and assigned["items"][0]["id"] == item["id"]
        filter_key = "category_id" if kind == "categories" else "tag_id"
        filtered = (await client.get(f"{BASE}/projects", params={filter_key: item["id"]})).json()
        assert filtered["total"] == 1 and filtered["items"][0]["id"] == row["id"]
        assert (await client.put(assignments, json={"ids": []})).status_code == 204
        assert (await client.delete(path)).status_code == 204
        assert (await client.get(path)).status_code == 404
        assert (await client.get(f"{BASE}/{kind}", params={"limit": 1})).status_code == 200

    exercise(portfolio_database, check)


def test_attributes_scoping_reordering_and_transaction_rollback(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        first, second = await project(client), await project(client)
        path = f"{BASE}/projects/{first['id']}/attributes"
        created = await client.post(path, json={"label": "Structure", "value": "Concrete"})
        assert created.status_code == 201, created.text
        item = created.json()
        assert (await client.patch(path + f"/{item['id']}", json={"value": "Timber"})).json()[
            "value"
        ] == "Timber"
        foreign = f"{BASE}/projects/{second['id']}/attributes/{item['id']}"
        assert (await client.patch(foreign, json={"value": "Bad"})).status_code == 404
        assert (await client.delete(foreign)).status_code == 404
        order = {
            "items": [{"id": item["id"], "sort_order": 9}, {"id": str(uuid4()), "sort_order": 0}]
        }
        assert (await client.put(path + "/order", json=order)).status_code == 404
        assert (await client.get(path)).json()["items"][0]["sort_order"] == 0
        order["items"].pop()
        assert (await client.put(path + "/order", json=order)).status_code == 204
        assert (await client.get(path)).json()["items"][0]["sort_order"] == 9
        assert (await client.delete(path + f"/{item['id']}")).status_code == 204
        assert (await client.get(path)).json()["total"] == 0

    exercise(portfolio_database, check)


def test_media_roles_reorder_duplicates_and_parent_scoping(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        first, second = await project(client), await project(client)
        path = f"{BASE}/projects/{first['id']}/media"
        media_id = await asset(client)
        body = {"media_id": media_id, "role": "GALLERY"}
        created = await client.post(path, json=body)
        assert created.status_code == 201, created.text
        item = created.json()
        assert (await client.post(path, json=body)).status_code == 409
        assert (await client.post(path, json=body | {"role": "PLAN"})).status_code == 201
        assert (
            await client.patch(path + f"/{item['id']}", json={"role": "PLAN"})
        ).status_code == 409
        assert (
            await client.patch(path + f"/{item['id']}", json={"role": "RENDER"})
        ).status_code == 200
        assert (
            await client.put(path + "/order", json={"items": [{"id": item["id"], "sort_order": 7}]})
        ).status_code == 204
        page = (await client.get(path, params={"limit": 1, "offset": 1})).json()
        assert page["total"] == 2 and page["items"][0]["sort_order"] == 7
        foreign = f"{BASE}/projects/{second['id']}/media/{item['id']}"
        assert (await client.delete(foreign)).status_code == 404
        assert (await client.delete(path + f"/{item['id']}")).status_code == 204
        assert (await client.get(f"{BASE}/media/{media_id}")).status_code == 200

    exercise(portfolio_database, check)


def test_project_filters_pagination_and_atomic_order(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        rows = [
            await project(client, status="ARCHIVED", visibility="UNLISTED", is_featured=True)
            for _ in range(2)
        ]
        featured = (await client.get(f"{BASE}/projects", params={"is_featured": True})).json()
        assert featured["total"] == 1 and featured["items"][0]["id"] == rows[-1]["id"]
        items = [{"id": row["id"], "sort_order": 3} for row in rows]
        assert (
            await client.put(f"{BASE}/projects/order", json={"items": items})
        ).status_code == 204
        # The maximum UUID sorts last, so one write occurs before the failure.
        invalid = [
            {"id": rows[0]["id"], "sort_order": 8},
            {"id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "sort_order": 8},
        ]
        assert (
            await client.put(f"{BASE}/projects/order", json={"items": invalid})
        ).status_code == 404
        assert (await client.get(f"{BASE}/projects/{rows[0]['id']}")).json()["sort_order"] == 3
        params: dict[str, str | int] = {
            "status": "ARCHIVED",
            "visibility": "UNLISTED",
            "limit": 1,
        }
        page = (await client.get(f"{BASE}/projects", params=params)).json()
        next_page = (await client.get(f"{BASE}/projects", params=params | {"offset": 1})).json()
        assert page["total"] == 2 and next_page["total"] == 2
        assert {page["items"][0]["id"], next_page["items"][0]["id"]} == {row["id"] for row in rows}
        assert (await client.delete(f"{BASE}/projects/{rows[0]['id']}")).status_code == 204
        assert (await client.get(f"{BASE}/projects/{rows[0]['id']}/media")).status_code == 404
        assert (await client.get(f"{BASE}/projects", params=params)).json()["total"] == 1

    exercise(portfolio_database, check)


def test_single_featured_replacement_rollback_and_concurrency(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        first = await project(client, is_featured=True)
        second = await project(client, is_featured=True)
        first_path = f"{BASE}/projects/{first['id']}"
        second_path = f"{BASE}/projects/{second['id']}"
        assert (await client.get(first_path)).json()["is_featured"] is False
        assert (await client.get(second_path)).json()["is_featured"] is True

        # Clearing the old selection must roll back with a failed write.
        failed = await client.patch(first_path, json={"is_featured": True, "slug": second["slug"]})
        assert failed.status_code == 409, failed.text
        assert (await client.get(second_path)).json()["is_featured"] is True
        failed = await client.patch(first_path, json={"is_featured": True, "status": "PUBLISHED"})
        assert failed.status_code == 400, failed.text
        assert (await client.get(second_path)).json()["is_featured"] is True

        # Both requests succeed; the serialized last writer owns the selection.
        responses = await asyncio.gather(
            client.patch(first_path, json={"is_featured": True}),
            client.patch(second_path, json={"is_featured": True}),
        )
        assert [r.status_code for r in responses] == [200, 200]
        selected = (await client.get(f"{BASE}/projects", params={"is_featured": True})).json()[
            "items"
        ]
        assert len(selected) == 1
        selected_path = f"{BASE}/projects/{selected[0]['id']}"
        assert (await client.delete(selected_path)).status_code == 204
        assert (await client.get(f"{BASE}/projects", params={"is_featured": True})).json()[
            "total"
        ] == 0

    exercise(portfolio_database, check)


def test_featured_public_hero_changes_without_reordering(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        first = await project(client, sort_order=0)
        second = await project(client, sort_order=999)
        for row in (first, second):
            path = f"{BASE}/projects/{row['id']}"
            cover = await asset(client)
            assert (await client.put(path + "/cover", json={"media_id": cover})).status_code == 200
            response = await client.patch(
                path, json={"status": "PUBLISHED", "visibility": "PUBLIC", "is_featured": True}
            )
            assert response.status_code == 200, response.text
            featured = (await client.get("/api/v1/public/featured-projects")).json()
            assert featured["total"] == 1
            assert featured["items"][0]["slug"] == row["slug"]
        assert (await client.get(f"{BASE}/projects/{first['id']}")).json()["sort_order"] == 0
        assert (await client.get(f"{BASE}/projects/{second['id']}")).json()["sort_order"] == 999

    exercise(portfolio_database, check)
