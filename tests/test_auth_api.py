import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings


@pytest.mark.parametrize(
    "body",
    [
        {"email": "bad\x00@example.org", "password": "valid"},
        {"email": "bad\ud800@example.org", "password": "valid"},
        {"email": "ada@example.org", "password": "invalid\ud800"},
    ],
)
async def test_login_rejects_unencodable_input_before_database(body: dict[str, str]) -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                content=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
    assert response.status_code == 422
    assert "invalid" not in response.text


async def test_missing_and_malformed_authorization() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for header in (None, "Basic wrong", "Bearer malformed", "Bearer"):
                response = await client.get(
                    "/api/v1/auth/me", headers={"Authorization": header} if header else {}
                )
                assert response.status_code == 401
                assert response.headers["WWW-Authenticate"] == "Bearer"
                assert response.headers["Cache-Control"] == "no-store"


async def test_auth_validation_never_echoes_submitted_secrets() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for path, body, secret in [
                ("login", {"email": "x", "password": "secret-" * 200}, "secret-"),
                ("refresh", {"refresh_token": "private-refresh"}, "private-refresh"),
                ("logout", {"refresh_token": "private-refresh"}, "private-refresh"),
                (
                    "login",
                    {"email": "x", "password": "valid", "unexpected": "private-extra"},
                    "private-extra",
                ),
            ]:
                response = await client.post(f"/api/v1/auth/{path}", json=body)
                assert response.status_code == 422
                assert secret not in response.text
                assert all(
                    "input" not in error and "ctx" not in error
                    for error in response.json()["detail"]
                )


async def test_auth_openapi_and_cors_contract() -> None:
    from app.main import create_app

    application = create_app(Settings(cors_origins=["http://localhost:4200"]))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        schema = (await client.get("/openapi.json")).json()
        assert schema["paths"]["/api/v1/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
        assert set(schema["components"]["schemas"]["UserResponse"]["properties"]) == {
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
        }
        for origin, status in [("http://localhost:4200", 200), ("https://untrusted.example", 400)]:
            response = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            assert response.status_code == status
