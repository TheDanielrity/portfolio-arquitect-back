"""Bounded, per-application request protection before parsing or database access."""

import math
from collections import OrderedDict
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestLimitsMiddleware:
    """Limit actual body bytes and fixed-window attempts by ASGI peer, per worker.

    Counters are updated without awaiting, so tasks on the application's event loop
    cannot race. An exhausted client table fails closed until a window expires.
    Distributed limits and trusted proxy configuration belong at the deployment edge.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        auth_per_minute: int,
        contact_per_minute: int,
        max_clients: int = 10000,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.auth_per_minute = auth_per_minute
        self.contact_per_minute = contact_per_minute
        self.max_clients = max_clients
        self._windows: OrderedDict[tuple[str, str], tuple[float, int]] = OrderedDict()

    def _retry_after(self, scope: Scope) -> int | None:
        path = scope["path"]
        root_path = scope.get("root_path", "")
        if root_path and path.startswith(root_path + "/"):
            path = path[len(root_path) :]
        path = path.rstrip("/")
        if scope["method"] != "POST":
            return None
        if path in {"/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/logout"}:
            group, limit = "auth", self.auth_per_minute
        elif path == "/api/v1/public/contact":
            group, limit = "contact", self.contact_per_minute
        else:
            return None
        now = monotonic()
        while self._windows and next(iter(self._windows.values()))[0] <= now:
            self._windows.popitem(last=False)
        peer = scope.get("client")
        key = (group, peer[0] if peer else "unknown")
        window = self._windows.get(key)
        if window is None:
            if len(self._windows) >= self.max_clients:
                return max(1, math.ceil(next(iter(self._windows.values()))[0] - now))
            self._windows[key] = (now + 60, 1)
        else:
            deadline, attempts = window
            if attempts >= limit:
                return max(1, math.ceil(deadline - now))
            self._windows[key] = (deadline, attempts + 1)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        retry_after = self._retry_after(scope)
        if retry_after is not None:
            await JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Cache-Control": "no-store", "Retry-After": str(retry_after)},
            )(scope, receive, send)
            return
        for name, value in scope["headers"]:
            if name.lower() == b"content-length":
                if not value.isdigit() or len(value) > 20:
                    await self._reject(scope, receive, send, 400, "Invalid content length")
                    return
                if int(value) > self.max_body_bytes:
                    await self._reject(scope, receive, send, 413, "Request body too large")
                    return
        # Buffer at most the configured body size before invoking any application code.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_body_bytes:
                await self._reject(scope, receive, send, 413, "Request body too large")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
        await JSONResponse(
            {"detail": detail}, status_code=status, headers={"Cache-Control": "no-store"}
        )(scope, receive, send)
