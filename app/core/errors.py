from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AuthenticationError,
    InvalidOperation,
    ResourceConflict,
    ResourceNotFound,
)
from app.modules.media.storage_port import ObjectMissing, StorageError


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(StorageError)
    async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
        return JSONResponse(
            status_code=404 if isinstance(exc, ObjectMissing) else 503,
            content={
                "detail": "Object not found"
                if isinstance(exc, ObjectMissing)
                else "Storage temporarily unavailable"
            },
            headers={"Cache-Control": "no-store"},
        )

    @application.exception_handler(InvalidOperation)
    async def invalid_operation(request: Request, exc: InvalidOperation) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"detail": str(exc)}, headers={"Cache-Control": "no-store"}
        )

    @application.exception_handler(ResourceNotFound)
    async def resource_not_found(request: Request, exc: ResourceNotFound) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": str(exc)}, headers={"Cache-Control": "no-store"}
        )

    @application.exception_handler(ResourceConflict)
    async def resource_conflict(request: Request, exc: ResourceConflict) -> JSONResponse:
        return JSONResponse(
            status_code=409, content={"detail": str(exc)}, headers={"Cache-Control": "no-store"}
        )

    @application.exception_handler(AuthenticationError)
    async def authentication_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required or invalid credentials"},
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default error includes submitted input, which may contain credentials.
        errors = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"}
        )
