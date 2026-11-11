from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.models import AppUser
from app.modules.auth.dependencies import get_current_user


async def test_upload_routes_require_authentication() -> None:
    from app.main import create_app

    app = create_app(Settings())
    identifier = uuid4()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        for method, path, body in [
            ("POST", "/api/v1/admin/media/uploads/presign", {}),
            ("POST", "/api/v1/admin/media/uploads/confirm", {"upload_id": str(identifier)}),
            ("DELETE", f"/api/v1/admin/media/uploads/{identifier}", None),
            ("PUT", f"/api/v1/admin/media/uploads/{identifier}/content", None),
            ("GET", f"/api/v1/admin/media/{identifier}/content", None),
        ]:
            response = await client.request(method, path, json=body)
            assert response.status_code == 401
            assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "overrides",
    [
        {"original_filename": "x.exe"},
        {"mime_type": "image/png"},
        {"file_size": 20971521},
        {"original_filename": "../house.jpg"},
        {"original_filename": "house.gltf", "mime_type": "model/gltf+json"},
    ],
)
async def test_invalid_upload_policy_fails_before_persistence(overrides: dict[str, object]) -> None:
    from app.main import create_app

    app = create_app(Settings())
    app.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/v1/admin/media/uploads/presign",
            json={
                "original_filename": "house.jpg",
                "mime_type": "image/jpeg",
                "file_size": 10,
            }
            | overrides,
        )
        assert response.status_code == 400


async def test_invalid_database_text_is_request_validation_error() -> None:
    from app.main import create_app

    app = create_app(Settings())
    app.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        response = await client.post(
            "/api/v1/admin/media/uploads/presign",
            json={
                "original_filename": "invalid\x00.jpg",
                "mime_type": "image/jpeg",
                "file_size": 10,
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "original_filename"]
