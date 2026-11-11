import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.api_docs import API_DESCRIPTION, error_responses
from app.core.config import Settings
from app.core.database import Database
from app.core.error_boundary import ErrorBoundaryMiddleware
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_limits import RequestLimitsMiddleware
from app.core.security import Security
from app.modules.auth.router import router as auth_router
from app.modules.contact.router import admin_router as contact_admin_router
from app.modules.contact.router import public_router as contact_public_router
from app.modules.content.public_router import router as public_content_router
from app.modules.content.router import router as content_router
from app.modules.media.dependencies import build_storage
from app.modules.media.router import router as media_router
from app.modules.media.upload_router import delivery_router
from app.modules.media.upload_router import router as upload_router
from app.modules.portfolio.public_router import router as public_portfolio_router
from app.modules.portfolio.router import router as portfolio_router

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an independent application, optionally with explicit settings for tests."""
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(debug=settings.debug)
        application.state.security = await run_in_threadpool(Security, settings)
        database = Database(settings)
        application.state.database = database
        application.state.storage = await run_in_threadpool(build_storage, settings)
        logger.info("Application started")
        try:
            yield
        finally:
            await database.dispose()
            del application.state.database
            del application.state.security
            del application.state.storage
            logger.info("Application stopped")

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=API_DESCRIPTION,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = settings
    register_exception_handlers(application)
    application.add_middleware(
        RequestLimitsMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
        auth_per_minute=settings.auth_requests_per_minute,
        contact_per_minute=settings.contact_requests_per_minute,
    )
    application.add_middleware(ErrorBoundaryMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After", "X-Error-ID"],
    )
    router = APIRouter(prefix="/api/v1", responses=error_responses(400, 413, 500))

    @router.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse()

    router.include_router(auth_router)
    router.include_router(media_router)
    router.include_router(upload_router)
    router.include_router(delivery_router)
    router.include_router(portfolio_router)
    router.include_router(content_router)
    router.include_router(contact_public_router)
    router.include_router(contact_admin_router)
    router.include_router(public_portfolio_router)
    router.include_router(public_content_router)
    application.include_router(router)
    return application


app = create_app()
