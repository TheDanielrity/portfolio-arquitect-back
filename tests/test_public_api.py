from httpx import ASGITransport, AsyncClient

from app.core.config import Settings


async def test_public_read_contracts_validation_and_no_write_operations() -> None:
    from app.main import create_app

    application = create_app(Settings())
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
            paths = {
                path: operations
                for path, operations in schema["paths"].items()
                if path.startswith("/api/v1/public/") and not path.endswith("/contact")
            }
            assert len(paths) == 10
            for path, operations in paths.items():
                assert set(operations) == {"get"}
                assert not operations["get"].get("security")
                media_type = (
                    "application/octet-stream" if path.endswith("/content") else "application/json"
                )
                assert operations["get"]["responses"]["200"]["content"][media_type]["schema"]
                for method in ("POST", "PATCH", "DELETE"):
                    assert (
                        await client.request(method, path.replace("{slug}", "house"), json={})
                    ).status_code == 405
            for path in (
                "projects",
                "featured-projects",
                "categories",
                "tags",
                "services",
                "social-links",
            ):
                for query in (
                    "limit=0",
                    "limit=101",
                    "offset=-1",
                    "visibility=PRIVATE",
                    "status=DRAFT",
                ):
                    assert (await client.get(f"/api/v1/public/{path}?{query}")).status_code == 422
            assert (
                await client.get("/api/v1/public/projects?category=bad%20slug")
            ).status_code == 422
            assert (await client.get("/api/v1/public/projects/BAD_SLUG")).status_code == 422
