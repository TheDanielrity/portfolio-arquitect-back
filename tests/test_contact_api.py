from ipaddress import ip_address
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.core.config import Settings
from app.modules.contact.dependencies import get_submission_context


async def test_contact_authorization_contract_and_policy_boundary() -> None:
    from app.main import create_app

    application = create_app(Settings())

    async def deny_submission() -> None:
        raise HTTPException(
            status_code=429, detail="Too many requests", headers={"Retry-After": "60"}
        )

    application.dependency_overrides[get_submission_context] = deny_submission
    async with application.router.lifespan_context(application):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
            assert not schema["paths"]["/api/v1/public/contact"]["post"].get("security")
            count = 0
            for path, operations in schema["paths"].items():
                if not path.startswith("/api/v1/admin/contact-messages"):
                    continue
                for method, operation in operations.items():
                    assert operation["security"] == [{"HTTPBearer": []}]
                    response = await client.request(
                        method, path.replace("{item_id}", str(uuid4())), json={}
                    )
                    assert response.status_code == 401
                    count += 1
            assert count == 3
            response = await client.post(
                "/api/v1/public/contact",
                json={"name": "Ada", "email": "ada@example.org", "message": "Hello"},
            )
            assert response.status_code == 429 and response.headers["Retry-After"] == "60"
            assert (await client.get("/api/v1/public/contact")).status_code == 405
            assert (await client.get(f"/api/v1/public/contact/{uuid4()}")).status_code == 404


@pytest.mark.parametrize("peer", ["127.0.0.1", "2001:db8::1", "testclient"])
async def test_submission_metadata_uses_peer_not_forwarded_headers(peer: str) -> None:
    request = Request(
        {
            "type": "http",
            "client": (peer, 1234),
            "headers": [(b"x-forwarded-for", b"203.0.113.1"), (b"user-agent", b"a" * 2000)],
        }
    )
    context = await get_submission_context(request)
    assert context.ip_address == (None if peer == "testclient" else ip_address(peer))
    assert context.user_agent == "a" * 1024


async def test_missing_peer_and_invalid_metadata_are_safe() -> None:
    context = await get_submission_context(
        Request({"type": "http", "headers": [(b"user-agent", b"bad\x00agent")]})
    )
    assert context.ip_address is None and context.user_agent is None
