from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.core.config import Settings


async def test_all_content_routes_are_authenticated_and_documented() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
            count = 0
            for path, operations in schema["paths"].items():
                if not path.startswith(
                    (
                        "/api/v1/admin/profile",
                        "/api/v1/admin/services",
                        "/api/v1/admin/site-settings",
                    )
                ):
                    continue
                target = path.replace("{item_id}", str(uuid4())).replace("{key}", "site_title")
                for method, operation in operations.items():
                    assert operation["security"] == [{"HTTPBearer": []}]
                    response = await client.request(method, target, json={})
                    assert response.status_code == 401, (method, path, response.text)
                    count += 1
            assert count == 18
