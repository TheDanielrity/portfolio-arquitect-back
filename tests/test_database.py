import asyncio
from typing import Annotated

import pytest
from fastapi import Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn import Config

from app.core.config import Settings
from app.core.database import Database, SessionDependency, get_session


async def test_engine_and_metadata() -> None:
    database = Database(Settings())
    try:
        assert database.engine.dialect.name == "postgresql"
        assert database.engine.dialect.driver == "psycopg"
        assert database.engine.dialect.is_async
        assert database.engine.sync_engine.hide_parameters
    finally:
        await database.dispose()


@pytest.mark.parametrize("outcome", ["success", "error", "cancelled", "committed"])
async def test_session_transactions_and_close(outcome: str) -> None:
    database = Database(Settings())
    sessions: list[AsyncSession] = []

    async def use_session() -> None:
        async with database.session() as session:
            sessions.append(session)
            await session.begin()
            assert session.in_transaction()
            if outcome == "error":
                raise ValueError("Operation failed")
            if outcome == "cancelled":
                raise asyncio.CancelledError
            if outcome == "committed":
                await session.commit()

    try:
        if outcome == "error":
            with pytest.raises(ValueError, match="Operation failed"):
                await use_session()
        elif outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await use_session()
        else:
            await use_session()
        session = sessions[0]
        assert not session.in_transaction()
        with pytest.raises(InvalidRequestError, match="permanently closed"):
            await session.begin()
        async with database.session() as another:
            assert another is not session
    finally:
        await database.dispose()


async def test_dependency_is_request_scoped_and_disposed() -> None:
    from app.main import create_app

    application = create_app(Settings())
    sessions: list[AsyncSession] = []
    disposed: list[bool] = []

    @application.get("/test-session")
    async def session_route(
        session: SessionDependency,
        same_session: Annotated[AsyncSession, Depends(get_session)],
    ) -> dict[str, bool]:
        assert session is same_session
        sessions.append(session)
        await session.begin()
        return {"ok": True}

    async with application.router.lifespan_context(application):
        database: Database = application.state.database
        event.listen(
            database.engine.sync_engine, "engine_disposed", lambda engine: disposed.append(True)
        )
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for _ in range(2):
                assert (await client.get("/test-session")).status_code == 200
    assert sessions[0] is not sessions[1]
    assert all(not session.in_transaction() for session in sessions)
    assert disposed == [True]
    assert not hasattr(application.state, "database")


async def test_lifespan_disposes_engine_on_error() -> None:
    from app.main import create_app

    application = create_app(Settings())
    disposed: list[bool] = []
    with pytest.raises(ValueError, match="Lifespan failure"):
        async with application.router.lifespan_context(application):
            database: Database = application.state.database
            event.listen(
                database.engine.sync_engine, "engine_disposed", lambda engine: disposed.append(True)
            )
            raise ValueError("Lifespan failure")
    assert disposed == [True]
    assert not hasattr(application.state, "database")


def test_windows_compatible_loop() -> None:
    config = Config("app.main:app", loop="app.core.event_loop:selector_loop_factory")
    factory = config.get_loop_factory()
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
