from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    """Shared declarative metadata; import app.models to register domain tables."""


class Database:
    """Own one application's engine and factory, never a shared session."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, close_resets_only=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Services commit explicitly; unfinished transactions always roll back."""
        async with self.session_factory() as session:
            try:
                yield session
            finally:
                if session.in_transaction():
                    await session.rollback()

    async def verify_connection(self) -> None:
        """Perform a read-only connectivity check without touching domain schemas."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = cast(Database, request.app.state.database)
    async with database.session() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
