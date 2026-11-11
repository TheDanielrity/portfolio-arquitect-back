import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import Database
from app.core.security import Security
from app.models import MediaAsset, ProjectSection, ProjectSectionMedia
from tests.test_auth_integration import exercise
from tests.test_media_integration import authorize
from tests.test_portfolio_integration import BASE, asset, project
from tests.test_portfolio_integration import portfolio_database as portfolio_database

pytestmark = pytest.mark.integration


def test_section_crud_visibility_scoping_and_soft_deleted_parent(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        parent, other = await project(client), await project(client)
        path = f"{BASE}/projects/{parent['id']}/sections"
        created = await client.post(
            path, json={"section_type": "TEXT", "content": "Narrative", "title": "Concept"}
        )
        assert created.status_code == 201, created.text
        row = created.json()
        detail = path + f"/{row['id']}"
        response = await client.get(detail)
        assert response.json() == row and response.headers["Cache-Control"] == "no-store"
        hidden = await client.patch(
            detail, json={"is_visible": False, "content": None, "title": None}
        )
        assert hidden.status_code == 200 and hidden.json()["content"] is None
        assert (await client.patch(detail, json={"is_visible": True})).status_code == 400
        assert (await client.get(detail)).json()["is_visible"] is False
        assert (
            await client.patch(
                detail, json={"content": "Quote", "section_type": "QUOTE", "is_visible": True}
            )
        ).status_code == 200
        foreign = f"{BASE}/projects/{other['id']}/sections/{row['id']}"
        for method, suffix, body in [
            ("GET", "", None),
            ("PATCH", "", {"title": "Bad"}),
            ("DELETE", "", None),
            ("GET", "/media", None),
        ]:
            assert (await client.request(method, foreign + suffix, json=body)).status_code == 404
        assert (await client.get(path)).json()["total"] == 1
        assert (await client.delete(f"{BASE}/projects/{parent['id']}")).status_code == 204
        for suffix in ("", f"/{row['id']}", f"/{row['id']}/media"):
            assert (await client.get(path + suffix)).status_code == 404
        assert (
            await client.post(path, json={"section_type": "TEXT", "content": "New"})
        ).status_code == 404
        async with database.session() as session:
            assert await session.get(ProjectSection, UUID(row["id"])) is not None

    exercise(portfolio_database, check)


def test_all_section_types_media_compatibility_and_visible_requirements(
    portfolio_database: str,
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        parent = await project(client)
        path = f"{BASE}/projects/{parent['id']}/sections"
        assets = {
            kind: await asset(client, kind)
            for kind in ("IMAGE", "VIDEO", "MODEL_3D", "PDF", "DOCUMENT")
        }
        expected = {
            "TEXT": None,
            "QUOTE": None,
            "IMAGE": "IMAGE",
            "GALLERY": "IMAGE",
            "VIDEO": "VIDEO",
            "MODEL_3D": "MODEL_3D",
            "SPLIT": "IMAGE",
        }
        for section_type, media_type in expected.items():
            body: dict[str, object] = {"section_type": section_type, "content": "Meaningful text"}
            valid_media = [] if media_type is None else [{"media_id": assets[media_type]}]
            valid = await client.post(path, json=body | {"media": valid_media})
            assert valid.status_code == 201, (section_type, valid.text)
            empty = await client.post(path, json={"section_type": section_type})
            assert empty.status_code == 400, section_type
            hidden = await client.post(
                path, json={"section_type": section_type, "is_visible": False}
            )
            assert hidden.status_code == 201
            for kind, media_id in assets.items():
                response = await client.post(path, json=body | {"media": [{"media_id": media_id}]})
                assert response.status_code == (201 if kind == media_type else 400), (
                    section_type,
                    kind,
                    response.text,
                )
            if section_type in ("TEXT", "QUOTE", "SPLIT"):
                assert (
                    await client.post(path, json=body | {"content": " \n ", "media": valid_media})
                ).status_code == 400
        # A media error rolls back section insertion as well.
        before = (await client.get(path)).json()["total"]
        assert (
            await client.post(
                path, json={"section_type": "IMAGE", "media": [{"media_id": str(uuid4())}]}
            )
        ).status_code == 404
        assert (await client.get(path)).json()["total"] == before

    exercise(portfolio_database, check)


def test_atomic_type_and_media_replacement_and_deletion_cascade(portfolio_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        parent = await project(client)
        path = f"{BASE}/projects/{parent['id']}/sections"
        image, video = await asset(client), await asset(client, "VIDEO")
        row = (
            await client.post(
                path,
                json={
                    "section_type": "IMAGE",
                    "media": [{"media_id": image, "caption": "Original"}],
                },
            )
        ).json()
        detail = path + f"/{row['id']}"
        assert (await client.patch(detail, json={"section_type": "VIDEO"})).status_code == 400
        assert (
            await client.patch(detail, json={"media": [{"media_id": video}]})
        ).status_code == 400
        assert (await client.patch(detail, json={"media": []})).status_code == 400
        assert (await client.get(detail)).json()["section_type"] == "IMAGE"
        assert (await client.get(detail + "/media")).json()["items"][0]["media_id"] == image
        changed = await client.patch(
            detail, json={"section_type": "VIDEO", "media": [{"media_id": video}]}
        )
        assert changed.status_code == 200, changed.text
        assert (await client.delete(f"{BASE}/media/{video}")).status_code == 409
        assert (await client.delete(detail)).status_code == 204
        assert (await client.get(detail)).status_code == 404
        async with database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ProjectSectionMedia)
                    .where(ProjectSectionMedia.section_id == UUID(row["id"]))
                )
                == 0
            )
            assert await session.get(MediaAsset, UUID(video)) is not None
        assert (await client.delete(f"{BASE}/media/{video}")).status_code == 204

    exercise(portfolio_database, check)


def test_section_media_crud_ordering_and_concurrent_last_asset_removal(
    portfolio_database: str,
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        parent = await project(client)
        path = f"{BASE}/projects/{parent['id']}/sections"
        row = (
            await client.post(path, json={"section_type": "GALLERY", "is_visible": False})
        ).json()
        detail = path + f"/{row['id']}"
        media_path = detail + "/media"
        first, second = await asset(client), await asset(client)
        for media_id in (first, second):
            attached = await client.post(
                media_path, json={"media_id": media_id, "caption": "Photo"}
            )
            assert attached.status_code == 201, attached.text
        assert (await client.post(media_path, json={"media_id": first})).status_code == 409
        assert (await client.patch(media_path + f"/{first}", json={"caption": None})).json()[
            "caption"
        ] is None
        assert (
            await client.put(
                media_path + "/order",
                json={
                    "items": [{"id": first, "sort_order": 7}, {"id": str(uuid4()), "sort_order": 0}]
                },
            )
        ).status_code == 404
        assert {item["sort_order"] for item in (await client.get(media_path)).json()["items"]} == {
            0
        }
        assert (
            await client.put(
                media_path + "/order", json={"items": [{"id": first, "sort_order": 7}]}
            )
        ).status_code == 204
        page = (await client.get(media_path, params={"limit": 1, "offset": 1})).json()
        assert page["total"] == 2 and page["items"][0]["media_id"] == first
        assert (await client.patch(detail, json={"is_visible": True})).status_code == 200
        results = await asyncio.gather(
            client.delete(media_path + f"/{first}"), client.delete(media_path + f"/{second}")
        )
        assert sorted(response.status_code for response in results) == [204, 400]
        assert (await client.get(media_path)).json()["total"] == 1
        assert (await client.patch(detail, json={"is_visible": False})).status_code == 200
        remaining = (await client.get(media_path)).json()["items"][0]["media_id"]
        assert (await client.delete(media_path + f"/{remaining}")).status_code == 204

    exercise(portfolio_database, check)


def test_section_order_batch_rollback_pagination_and_single_asset_limits(
    portfolio_database: str,
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        await authorize(client, database, security)
        parent, other = await project(client), await project(client)
        path = f"{BASE}/projects/{parent['id']}/sections"
        rows = [
            (await client.post(path, json={"section_type": "TEXT", "content": "Text"})).json()
            for _ in range(2)
        ]
        foreign = (
            await client.post(
                f"{BASE}/projects/{other['id']}/sections",
                json={"section_type": "TEXT", "content": "Foreign"},
            )
        ).json()
        assert (
            await client.put(
                path + "/order",
                json={
                    "items": [
                        {"id": rows[0]["id"], "sort_order": 9},
                        {"id": foreign["id"], "sort_order": 0},
                    ]
                },
            )
        ).status_code == 404
        assert (await client.get(path + f"/{rows[0]['id']}")).json()["sort_order"] == 0
        assert (
            await client.put(
                path + "/order",
                json={"items": [{"id": row["id"], "sort_order": 2} for row in rows]},
            )
        ).status_code == 204
        page = (await client.get(path, params={"limit": 1})).json()
        next_page = (await client.get(path, params={"limit": 1, "offset": 1})).json()
        assert page["total"] == 2 and page["items"][0]["id"] != next_page["items"][0]["id"]
        for kind, media_type in (
            ("IMAGE", "IMAGE"),
            ("VIDEO", "VIDEO"),
            ("MODEL_3D", "MODEL_3D"),
            ("SPLIT", "IMAGE"),
        ):
            first, second = await asset(client, media_type), await asset(client, media_type)
            row = (
                await client.post(
                    path,
                    json={"section_type": kind, "content": "Text", "media": [{"media_id": first}]},
                )
            ).json()
            media_path = path + f"/{row['id']}/media"
            assert (await client.post(media_path, json={"media_id": second})).status_code == 400
            assert (await client.get(media_path)).json()["total"] == 1

    exercise(portfolio_database, check)
