from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.models import AppUser
from app.modules.auth.dependencies import get_current_user


async def test_every_portfolio_endpoint_requires_authentication() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
            operations = 0
            for path, methods in schema["paths"].items():
                if not path.startswith(
                    ("/api/v1/admin/projects", "/api/v1/admin/categories", "/api/v1/admin/tags")
                ):
                    continue
                target = (
                    path.replace("{project_id}", str(uuid4()))
                    .replace("{item_id}", str(uuid4()))
                    .replace("{section_id}", str(uuid4()))
                    .replace("{media_id}", str(uuid4()))
                )
                for method, operation in methods.items():
                    assert operation["security"] == [{"HTTPBearer": []}]
                    response = await client.request(method, target, json={})
                    assert response.status_code == 401, (method, path, response.text)
                    assert response.headers["WWW-Authenticate"] == "Bearer"
                    operations += 1
            assert operations == 42


async def test_portfolio_validation_and_put_cors() -> None:
    from app.main import create_app

    application = create_app(Settings(cors_origins=["http://localhost:4200"]))
    application.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for query in (
                "limit=0",
                "limit=101",
                "offset=-1",
                "status=UNKNOWN",
                "visibility=UNKNOWN",
                "unknown=1",
            ):
                assert (await client.get(f"/api/v1/admin/projects?{query}")).status_code == 422
            assert (
                await client.post("/api/v1/admin/projects", json={"title": " ", "slug": "house"})
            ).status_code == 422
            assert (
                await client.patch(f"/api/v1/admin/projects/{uuid4()}", json={"status": None})
            ).status_code == 422
            response = await client.options(
                "/api/v1/admin/projects/order",
                headers={
                    "Origin": "http://localhost:4200",
                    "Access-Control-Request-Method": "PUT",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            assert response.status_code == 200
