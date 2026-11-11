from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.models import AppUser
from app.modules.auth.dependencies import get_current_user
from tests.test_media_schemas import payload


async def test_all_media_operations_require_authentication() -> None:
    from app.main import create_app

    application = create_app(Settings())
    path = f"/api/v1/admin/media/{uuid4()}"
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for method, target, body in [
                ("GET", "/api/v1/admin/media", None),
                ("GET", path, None),
                ("POST", "/api/v1/admin/media", payload()),
                ("PATCH", path, {"title": "New"}),
                ("DELETE", path, None),
            ]:
                response = await client.request(method, target, json=body)
                assert response.status_code == 401
                assert response.headers["WWW-Authenticate"] == "Bearer"
            assert (await client.get("/api/v1/public/media")).status_code == 404


async def test_media_query_and_body_validation() -> None:
    from app.main import create_app

    application = create_app(Settings())
    application.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for query in ("limit=0", "limit=101", "offset=-1", "type=UNKNOWN", "unknown=1"):
                assert (await client.get(f"/api/v1/admin/media?{query}")).status_code == 422
            assert (await client.get("/api/v1/admin/media/not-a-uuid")).status_code == 422
            response = await client.post("/api/v1/admin/media", json=payload(width=0))
            assert response.status_code == 422
            response = await client.patch(
                f"/api/v1/admin/media/{uuid4()}", json={"storage_key": "cannot-change"}
            )
            assert response.status_code == 422


async def test_media_openapi_and_cors() -> None:
    from app.main import create_app

    application = create_app(Settings(cors_origins=["http://localhost:4200"]))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        schema = (await client.get("/openapi.json")).json()
        for path in ("/api/v1/admin/media", "/api/v1/admin/media/{asset_id}"):
            for operation in schema["paths"][path].values():
                assert operation["security"] == [{"HTTPBearer": []}]
        for method in ("PATCH", "DELETE"):
            response = await client.options(
                "/api/v1/admin/media",
                headers={
                    "Origin": "http://localhost:4200",
                    "Access-Control-Request-Method": method,
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            assert response.status_code == 200
