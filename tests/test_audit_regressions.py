import re
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings
from app.models import AppUser
from app.modules.auth.dependencies import get_current_user
from app.modules.content.schemas import ProfileUpdate, ServiceUpdate, SocialUpdate
from app.modules.media.schemas import MediaListQuery, MediaUpdate
from app.modules.portfolio.schemas import (
    AttributeUpdate,
    CategoryUpdate,
    MediaLinkUpdate,
    PageQuery,
    Patch,
    ProjectUpdate,
    TagUpdate,
)
from app.modules.portfolio.section_schemas import SectionMediaUpdate, SectionUpdate

PATCH_MODELS = (
    ProjectUpdate,
    CategoryUpdate,
    TagUpdate,
    AttributeUpdate,
    MediaLinkUpdate,
    ProfileUpdate,
    SocialUpdate,
    ServiceUpdate,
    SectionUpdate,
    SectionMediaUpdate,
)


def allows_null(schema: dict[str, Any]) -> bool:
    return schema.get("type") == "null" or any(
        allows_null(option) for option in schema.get("anyOf", [])
    )


@pytest.mark.parametrize("model", PATCH_MODELS)
def test_patch_openapi_matches_null_and_omission_contract(model: type[Patch]) -> None:
    from app.main import create_app

    schemas = create_app(Settings()).openapi()["components"]["schemas"]
    schema = schemas[model.__name__]
    assert not schema.get("required")
    assert model.model_validate({}).model_dump(exclude_unset=True) == {}
    for name, field in schema["properties"].items():
        if name in model.non_nullable:
            assert not allows_null(field), name
            assert "default" not in field
            with pytest.raises(ValidationError):
                model.model_validate({name: None})
        else:
            assert allows_null(field), name
            assert model.model_validate({name: None}).model_dump(exclude_unset=True) == {name: None}


def test_media_patch_still_accepts_explicit_null() -> None:
    for name, field in MediaUpdate.model_json_schema()["properties"].items():
        assert allows_null(field)
        assert MediaUpdate.model_validate({name: None}).model_dump(exclude_unset=True) == {
            name: None
        }


@pytest.mark.parametrize("model", (PageQuery, MediaListQuery))
def test_offset_bigint_boundary(model: type[PageQuery] | type[MediaListQuery]) -> None:
    assert model(offset=2**63 - 1).offset == 2**63 - 1
    assert model(offset=0).offset == 0
    for value in (-1, 2**63, 10**100):
        with pytest.raises(ValidationError):
            model(offset=value)


async def test_every_paginated_endpoint_rejects_offset_overflow() -> None:
    from app.main import create_app

    application = create_app(Settings())
    application.dependency_overrides[get_current_user] = lambda: AppUser(id=uuid4())
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        checked = 0
        for path, methods in application.openapi()["paths"].items():
            operation = methods.get("get", {})
            offsets = [p for p in operation.get("parameters", []) if p["name"] == "offset"]
            if not offsets:
                continue
            assert offsets[0]["schema"]["maximum"] == 2**63 - 1
            concrete = re.sub(r"\{[^}]+\}", str(uuid4()), path)
            for offset in (2**63, 10**100):
                response = await client.get(concrete, params={"offset": str(offset)})
                assert response.status_code == 422, (path, response.text)
                assert response.json()["detail"][0]["loc"] == ["query", "offset"]
            checked += 1
        assert checked == 19


def test_openapi_errors_are_operation_specific() -> None:
    from app.main import create_app

    paths = create_app(Settings()).openapi()["paths"]
    limited = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/public/contact",
    }
    for path, methods in paths.items():
        for method, operation in methods.items():
            responses = operation["responses"]
            assert ("429" in responses) == (method == "post" and path in limited)
            authenticated = path.startswith("/api/v1/admin/") or path in {
                "/api/v1/auth/login",
                "/api/v1/auth/refresh",
                "/api/v1/auth/me",
            }
            assert ("401" in responses) == authenticated
            if method == "get":
                assert "409" not in responses
    assert set(paths["/api/v1/health"]["get"]["responses"]) == {"200", "400", "413", "500"}
    for path in ("/api/v1/public/projects", "/api/v1/admin/media"):
        assert "404" not in paths[path]["get"]["responses"]
    for path in ("/api/v1/public/projects/{slug}", "/api/v1/public/profile"):
        assert "404" in paths[path]["get"]["responses"]


async def test_global_middleware_errors_apply_even_to_health() -> None:
    from app.main import create_app

    application = create_app(Settings(max_request_body_bytes=1024))
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        invalid = await client.get("/api/v1/health", headers={"Content-Length": "invalid"})
        oversized = await client.request("GET", "/api/v1/health", content=b"x" * 1025)
    assert invalid.status_code == 400
    assert oversized.status_code == 413
