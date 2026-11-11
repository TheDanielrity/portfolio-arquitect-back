from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.core.api_docs import ErrorResponse, ValidationErrorResponse
from app.core.config import Settings


def test_documented_operations_and_security() -> None:
    from app.main import create_app

    schema = create_app(Settings(_env_file=None)).openapi()
    inventory = (Path(__file__).resolve().parents[1] / "docs/api/endpoints.md").read_text(
        encoding="utf-8"
    )
    operation_ids: list[str] = []
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            assert f"| {method.upper()} | {path} |" in inventory
            protected = path.startswith("/api/v1/admin/") or path == "/api/v1/auth/me"
            assert bool(operation.get("security")) == protected
            operation_ids.append(operation["operationId"])
            for status, response in operation["responses"].items():
                if status == "204":
                    assert "content" not in response
                elif status == "307":
                    assert "content" not in response
                elif status == "200" and path.endswith("/content"):
                    assert (
                        response["content"]["application/octet-stream"]["schema"]["format"]
                        == "binary"
                    )
                else:
                    assert "schema" in response["content"]["application/json"]
    assert len(operation_ids) == len(set(operation_ids))
    assert len(operation_ids) == 89
    plan = (Path(__file__).resolve().parents[1] / "PLANS.md").read_text(encoding="utf-8")
    assert f"the {len(operation_ids)}-operation inventory" in plan
    assert len(operation_ids) == sum(line.startswith("| ") for line in inventory.splitlines()) - 2
    bearer = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert bearer["scheme"] == "bearer"
    assert bearer["bearerFormat"] == "JWT"
    validation = schema["components"]["schemas"]["ValidationIssue"]
    assert set(validation["properties"]) == {"loc", "msg", "type"}


async def test_documented_errors_match_http_contract() -> None:
    from app.main import create_app

    application = create_app(Settings(_env_file=None, max_request_body_bytes=1024))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        invalid = await client.get("/api/v1/public/projects?limit=0")
        oversized = await client.post("/api/v1/auth/login", content=b"x" * 1025)
    assert invalid.status_code == 422
    assert ValidationErrorResponse.model_validate(invalid.json()).detail[0].loc == [
        "query",
        "limit",
    ]
    assert oversized.status_code == 413
    assert ErrorResponse.model_validate(oversized.json()).detail
    responses = application.openapi()["paths"]["/api/v1/public/projects"]["get"]["responses"]
    assert responses["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ValidationErrorResponse"
    }
