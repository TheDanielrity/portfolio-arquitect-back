from httpx import ASGITransport, AsyncClient

from app.core.config import Settings


async def test_application_starts() -> None:
    from app.main import create_app

    application = create_app(Settings(_env_file=None, app_env="test"))
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            schema = await client.get("/openapi.json")
            assert "/api/v1/health" in schema.json()["paths"]


async def test_health_response() -> None:
    from app.main import create_app

    application = create_app(Settings(_env_file=None))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_cors_allows_only_configured_origin() -> None:
    from app.main import create_app

    application = create_app(Settings(_env_file=None, cors_origins=["http://localhost:4200"]))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        allowed = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:4200",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = await client.options(
            "/api/v1/health",
            headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
        )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
