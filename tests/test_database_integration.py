import asyncio
import os

import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import Settings
from app.core.database import Database

pytestmark = pytest.mark.integration


def test_postgresql_connection_and_transaction_recovery() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")

    async def exercise_database() -> None:
        database = Database(Settings(database_url=SecretStr(url)))
        try:
            await database.verify_connection()
            with pytest.raises(DBAPIError):
                async with database.session() as session:
                    await session.execute(text("SELECT 1 / 0"))
            async with database.session() as session:
                assert await session.scalar(text("SELECT 1")) == 1
                await session.commit()
            assert isinstance(database.engine.pool, AsyncAdaptedQueuePool)
            assert database.engine.pool.checkedout() == 0
        finally:
            await database.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise_database())
