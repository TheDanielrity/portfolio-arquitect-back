import asyncio
import logging
from collections.abc import AsyncIterator

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.error_boundary import ErrorBoundaryMiddleware
from app.core.request_limits import RequestLimitsMiddleware


async def test_body_limit_checks_streamed_bytes_before_route_execution() -> None:
    from app.main import create_app

    application = create_app(Settings(max_request_body_bytes=1024))
    calls = 0

    @application.post("/probe")
    async def probe(request: Request) -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"size": len(await request.body())}

    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 600
        yield b"x" * 425

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        exact = await client.post("/probe", content=b"x" * 1024)
        assert exact.json() == {"size": 1024}
        for headers in ({}, {"Content-Length": "1"}):
            response = await client.post("/probe", content=chunks(), headers=headers)
            assert response.status_code == 413
            assert response.headers["Cache-Control"] == "no-store"
        declared = await client.post("/probe", content=b"x", headers={"Content-Length": "1025"})
        assert declared.status_code == 413
        invalid = await client.post("/probe", content=b"x", headers={"Content-Length": "-1"})
        assert invalid.status_code == 400
    assert calls == 1


@pytest.mark.parametrize("debug", [False, True])
async def test_unexpected_error_has_safe_logs_json_and_cors(
    debug: bool,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import create_app

    application = create_app(Settings(debug=debug, cors_origins=["https://front.example"]))
    monkeypatch.setattr(logging.getLogger("app"), "propagate", True)

    @application.get("/failure")
    async def failure() -> None:
        try:
            raise ValueError("private-password-and-database-parameters")
        except ValueError as exc:
            raise RuntimeError("private-token") from exc

    with caplog.at_level(logging.ERROR, logger="app.core.error_boundary"):
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.get("/failure", headers={"Origin": "https://front.example"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Access-Control-Allow-Origin"] == "https://front.example"
    assert len(response.headers["X-Error-ID"]) == 32
    assert response.headers["X-Error-ID"] in caplog.text
    assert "RuntimeError" in caplog.text and ":failure" in caplog.text
    assert "private-" not in caplog.text + response.text


async def test_rate_limits_precede_validation_and_ignore_forwarded_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.main import create_app

    clock = [100.0]
    monkeypatch.setattr("app.core.request_limits.monotonic", lambda: clock[0])
    application = create_app(Settings(auth_requests_per_minute=2, contact_requests_per_minute=1))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        for path in ("login", "refresh"):
            response = await client.post(f"/api/v1/auth/{path}", json={})
            assert response.status_code == 422
        limited = await client.post(
            "/api/v1/auth/logout/",
            json={},
            headers={"X-Forwarded-For": "192.0.2.1", "Forwarded": "for=192.0.2.2"},
        )
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert limited.headers["Cache-Control"] == "no-store"
        assert (await client.post("/api/v1/public/contact", json={})).status_code == 422
        assert (await client.post("/api/v1/public/contact", json={})).status_code == 429
        assert (await client.get("/api/v1/health")).status_code == 200
        clock[0] += 60
        assert (await client.post("/api/v1/auth/login", json={})).status_code == 422
    # A second application does not share attempt state.
    other = create_app(Settings(auth_requests_per_minute=1))
    async with (
        other.router.lifespan_context(other),
        AsyncClient(transport=ASGITransport(app=other), base_url="http://test") as client,
    ):
        assert (await client.post("/api/v1/auth/login", json={})).status_code == 422


async def test_rate_limit_is_atomic_bounded_and_isolated_by_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [0.0]
    monkeypatch.setattr("app.core.request_limits.monotonic", lambda: clock[0])

    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    app = RequestLimitsMiddleware(
        endpoint,
        max_body_bytes=1024,
        auth_per_minute=2,
        contact_per_minute=1,
        max_clients=2,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("192.0.2.1", 1)), base_url="http://test"
    ) as client:
        responses = await asyncio.gather(
            *[client.post("/api/v1/auth/login", json={}) for _ in range(5)]
        )
        assert sorted(response.status_code for response in responses) == [200, 200, 429, 429, 429]
    for peer, expected in (("192.0.2.2", 200), ("192.0.2.3", 429)):
        async with AsyncClient(
            transport=ASGITransport(app=app, client=(peer, 1)), base_url="http://test"
        ) as client:
            assert (await client.post("/api/v1/auth/login")).status_code == expected
    clock[0] = 60
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("192.0.2.3", 1)), base_url="http://test"
    ) as client:
        assert (await client.post("/api/v1/auth/login")).status_code == 200


async def test_disconnect_does_not_execute_route() -> None:
    calls = 0

    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal calls
        calls += 1

    async def disconnected() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        pytest.fail("No response should be sent after a disconnected upload")

    app = RequestLimitsMiddleware(
        endpoint,
        max_body_bytes=1024,
        auth_per_minute=1,
        contact_per_minute=1,
    )
    await app(
        {"type": "http", "method": "POST", "path": "/probe", "headers": []},
        disconnected,
        send,
    )
    assert calls == 0


async def test_partial_response_failure_aborts_with_sanitized_exception() -> None:
    sent: list[Message] = []

    async def partial(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise ValueError("private-database-detail")

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        sent.append(message)

    with pytest.raises(RuntimeError, match="Response aborted") as error:
        await ErrorBoundaryMiddleware(partial)({"type": "http"}, receive, send)
    assert "private" not in str(error.value)
    assert error.value.__suppress_context__
    assert len(sent) == 1


async def test_request_cancellation_is_not_converted_to_server_error() -> None:
    async def cancelled(scope: Scope, receive: Receive, send: Send) -> None:
        raise asyncio.CancelledError

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        pytest.fail("Cancellation must not send an HTTP response")

    with pytest.raises(asyncio.CancelledError):
        await ErrorBoundaryMiddleware(cancelled)({"type": "http"}, receive, send)


async def test_deployment_root_path_cannot_bypass_rate_limit() -> None:
    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    app = RequestLimitsMiddleware(
        endpoint,
        max_body_bytes=1024,
        auth_per_minute=1,
        contact_per_minute=1,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app, root_path="/backend"), base_url="http://test"
    ) as client:
        assert (await client.post("/backend/api/v1/auth/login")).status_code == 200
        assert (await client.post("/backend/api/v1/auth/login")).status_code == 429
