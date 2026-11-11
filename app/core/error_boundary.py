"""Keep unexpected exception payloads out of HTTP responses and server logs."""

import logging
from pathlib import Path
from traceback import walk_tb
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class ErrorBoundaryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track_response(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track_response)
        except Exception as exc:
            error_id = uuid4().hex
            # Do not format exception messages, chained exceptions, source lines or locals:
            # database diagnostics and validation exceptions can contain submitted secrets.
            frames = [
                f"{Path(frame.f_code.co_filename).name}:{line}:{frame.f_code.co_name}"
                for frame, line in walk_tb(exc.__traceback__)
            ]
            logger.error(
                "request_failed error_id=%s exception_type=%s frames=%s",
                error_id,
                type(exc).__name__,
                ";".join(frames),
            )
            if started:
                # A partial response cannot be replaced; let the server abort it without
                # propagating the original exception or its potentially sensitive chain.
                raise RuntimeError(f"Response aborted; error_id={error_id}") from None
            await JSONResponse(
                {"detail": "Internal server error"},
                status_code=500,
                headers={"Cache-Control": "no-store", "X-Error-ID": error_id},
            )(scope, receive, send)
