import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.migration_support import engine_for, migrate, temporary_databases


@pytest.mark.integration
def test_featured_migration_retains_hero_and_enforces_uniqueness() -> None:
    admin = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not admin:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL tests")

    async def check() -> None:
        async with temporary_databases(admin) as (url, _):
            await migrate(url, "upgrade", "0002_storage_operations")
            engine = engine_for(url)
            try:
                async with engine.begin() as connection:
                    # Migration preserves the public hero over a draft with a lower order.
                    await connection.execute(
                        text("""
                        INSERT INTO portfolio.project
                            (title, slug, status, visibility, is_featured, sort_order)
                        VALUES ('Draft', 'draft', 'DRAFT', 'PUBLIC', TRUE, 0),
                               ('Hero', 'hero', 'PUBLISHED', 'PUBLIC', TRUE, 2),
                               ('Other', 'other', 'PUBLISHED', 'PUBLIC', TRUE, 3)
                    """)
                    )
                await migrate(url, "upgrade")
                async with engine.connect() as connection:
                    assert (
                        await connection.execute(
                            text("SELECT slug FROM portfolio.project WHERE is_featured")
                        )
                    ).scalars().all() == ["hero"]
                with pytest.raises(IntegrityError):
                    async with engine.begin() as connection:
                        await connection.execute(
                            text(
                                "INSERT INTO portfolio.project (title, slug, is_featured) "
                                "VALUES ('Duplicate', :slug, TRUE)"
                            ),
                            {"slug": uuid4().hex},
                        )
                await migrate(url, "downgrade", "0002_storage_operations")
                await migrate(url, "upgrade")
            finally:
                await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(check())
