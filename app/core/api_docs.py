"""Shared OpenAPI contracts for the application's exception handlers and middleware."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    detail: list[ValidationIssue]


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {"model": ErrorResponse, "description": "Storage provider temporarily unavailable."},
    400: {
        "model": ErrorResponse,
        "description": "Invalid Content-Length header or operation violates a business rule.",
    },
    401: {
        "model": ErrorResponse,
        "description": "Protected operation or credentials require a valid active session.",
        "headers": {"WWW-Authenticate": {"schema": {"type": "string", "example": "Bearer"}}},
    },
    404: {"model": ErrorResponse, "description": "Resource missing or not publicly accessible."},
    409: {
        "model": ErrorResponse,
        "description": "Duplicate value, reference or conflicting state.",
    },
    413: {"model": ErrorResponse, "description": "Request body exceeds the configured byte limit."},
    422: {
        "model": ValidationErrorResponse,
        "description": "Invalid input; submitted values and validation context are omitted.",
    },
    429: {
        "model": ErrorResponse,
        "description": "Auth/contact POST quota exceeded; wait before retrying.",
        "headers": {
            "Retry-After": {"schema": {"type": "string"}, "description": "Seconds to wait"}
        },
    },
    500: {
        "model": ErrorResponse,
        "description": "Unexpected failure; detail is Internal server error.",
        "headers": {"X-Error-ID": {"schema": {"type": "string"}}},
    },
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Select only errors applicable to the operation or router."""
    return {code: ERROR_RESPONSES[code] for code in codes}


API_DESCRIPTION = """
Architecture portfolio API for the public website and private Angular administration.

All business endpoints use `/api/v1`. Public routes require no token. Administrative
routes and `/auth/me` require an active administrator's bearer access token.
Use JSON `/auth/login`, then paste only `access_token` into Swagger's Authorize dialog.
Refresh rotates **both** tokens and immediately invalidates the old access token;
serialize refresh requests. Logout accepts the latest refresh token in JSON.

Collections use `{items, total, limit, offset}` (limit 1–100, default 20;
offset 0–9223372036854775807).
Public settings are a bounded plain array and project detail includes complete nested
composition. Public discovery includes only PUBLISHED/PUBLIC/nondeleted projects;
direct slug detail also allows UNLISTED. Private/draft/deleted projects return 404.

Error responses are declared per operation. Global 400/413 responses come from
request-body middleware; 500 is the shared unexpected-error boundary.
204 responses have no body. PATCH omits unchanged fields; explicit null only clears
nullable fields. Runtime business validation can impose constraints beyond JSON Schema.
See `docs/api/frontend-handoff.md` and `docs/development.md` in the repository for
workflows, section rules, browser integration and local setup.
"""
