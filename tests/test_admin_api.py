"""Cross-module administrative contracts, without database access."""

import re
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.models import AppUser
from app.modules.auth.dependencies import get_current_user

COLLECTIONS = (
    "projects",
    "categories",
    "tags",
    "media",
    "services",
    "profile/social-links",
    "contact-messages",
)


async def test_every_admin_operation_requires_authentication() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        schema = (await client.get("/openapi.json")).json()
        checked = 0
        for path, operations in schema["paths"].items():
            if not path.startswith("/api/v1/admin/"):
                continue
            concrete = re.sub(r"\{[^}]+\}", str(uuid4()), path)
            for method, operation in operations.items():
                assert operation["security"]
                for headers in ({}, {"Authorization": "Bearer invalid"}):
                    response = await client.request(method, concrete, headers=headers, json={})
                    assert response.status_code == 401, (method, path, response.text)
                    assert response.headers["WWW-Authenticate"] == "Bearer"
                    assert response.headers["Cache-Control"] == "no-store"
                assert {"200", "201", "204", "307"} & operation["responses"].keys()
                checked += 1
        assert checked >= 60


@pytest.mark.parametrize("collection", COLLECTIONS)
async def test_admin_list_validation_is_consistent(collection: str) -> None:
    from app.main import create_app

    application = create_app(Settings())
    application.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        for query in (
            {"limit": "0"},
            {"limit": "101"},
            {"offset": "-1"},
            {"q": "   "},
            {"q": "x" * 201},
            {"q": "\x00"},
            {"sort": "password_hash"},
            {"direction": "sideways"},
            {"unknown": "value"},
        ):
            response = await client.get(f"/api/v1/admin/{collection}", params=query)
            assert response.status_code == 422, response.text
            assert response.headers["Cache-Control"] == "no-store"
            assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])


@pytest.mark.parametrize(
    "collection",
    ("categories", "tags", "attributes", "media", "sections", "sections/{section_id}/media"),
)
async def test_nested_admin_pagination_validation(collection: str) -> None:
    from app.main import create_app

    application = create_app(Settings())
    application.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    path = f"/api/v1/admin/projects/{uuid4()}/{collection}".replace("{section_id}", str(uuid4()))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        for query in ({"limit": "0"}, {"limit": "101"}, {"offset": "-1"}, {"unknown": "x"}):
            response = await client.get(path, params=query)
            assert response.status_code == 422, response.text
            assert response.headers["Cache-Control"] == "no-store"
            assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])
