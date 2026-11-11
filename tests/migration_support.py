"""Create only disposable databases owned by the current test invocation."""

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import Connection, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ("auth", "portfolio", "media", "content", "contact")
REVISION = "0003_single_featured"


def engine_for(url: str | URL) -> AsyncEngine:
    return create_async_engine(
        url, poolclass=NullPool, hide_parameters=True, connect_args={"connect_timeout": 5}
    )


@asynccontextmanager
async def temporary_databases(admin_url: str) -> AsyncIterator[tuple[URL, URL]]:
    """Never reuse or delete a database that existed before this invocation."""
    url = make_url(admin_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Migration tests require postgresql+psycopg")
    admin = engine_for(url)
    created: list[str] = []
    names = tuple(f"portfolio_migration_{uuid4().hex}" for _ in range(2))
    try:
        async with admin.connect() as connection:
            connection = await connection.execution_options(isolation_level="AUTOCOMMIT")
            try:
                for name in names:
                    assert name != url.database
                    assert re.fullmatch(r"portfolio_migration_[0-9a-f]{32}", name)
                    identifier = connection.dialect.identifier_preparer.quote_identifier(name)
                    # Identifier is generated locally, never taken from input or database rows.
                    await connection.exec_driver_sql(
                        f"CREATE DATABASE {identifier} TEMPLATE template0"
                    )
                    created.append(name)
                yield url.set(database=names[0]), url.set(database=names[1])
            finally:
                for name in reversed(created):
                    assert name in names and name != url.database
                    identifier = connection.dialect.identifier_preparer.quote_identifier(name)
                    await connection.exec_driver_sql(f"DROP DATABASE {identifier}")
    finally:
        await admin.dispose()


def run_alembic(connection: Connection, action: str, target: str = "head") -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["connection"] = connection
    if action == "upgrade":
        command.upgrade(config, target)
    elif action == "downgrade":
        command.downgrade(config, target)
    elif action == "check":
        command.check(config)
    else:
        raise ValueError("Unsupported migration action")


async def migrate(url: URL, action: str, target: str = "head") -> None:
    engine = engine_for(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(run_alembic, action, target)
    finally:
        await engine.dispose()


def in_transaction(url: URL, operation: Callable[[AsyncConnection], Awaitable[None]]) -> None:
    """Each test gets a new engine and a transaction rolled back on every exit."""

    async def exercise() -> None:
        engine = engine_for(url)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    await operation(connection)
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())


async def catalog_snapshot(url: URL) -> dict[str, list[tuple[object, ...]]]:
    """Compare PostgreSQL's canonical definitions, not rendered DDL formatting."""
    queries = {
        "schemas": """
            SELECT nspname, obj_description(oid, 'pg_namespace')
            FROM pg_namespace WHERE nspname = ANY(:schemas) ORDER BY 1
        """,
        "tables": """
            SELECT n.nspname, c.relname, c.relkind, obj_description(c.oid, 'pg_class')
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = ANY(:schemas) AND c.relkind IN ('r','p') ORDER BY 1,2
        """,
        "columns": """
            SELECT n.nspname, c.relname, a.attname, a.attnum,
                   format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   pg_get_expr(d.adbin, d.adrelid)
            FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
            WHERE n.nspname = ANY(:schemas) AND c.relkind = 'r'
              AND a.attnum > 0 AND NOT a.attisdropped ORDER BY 1,2,4
        """,
        "constraints": """
            SELECT n.nspname, c.relname, k.conname, k.contype, pg_get_constraintdef(k.oid)
            FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = ANY(:schemas) ORDER BY 1,2,3
        """,
        "indexes": """
            SELECT schemaname, tablename, indexname, indexdef FROM pg_indexes
            WHERE schemaname = ANY(:schemas) ORDER BY 1,2,3
        """,
        "triggers": """
            SELECT n.nspname, c.relname, t.tgname, pg_get_triggerdef(t.oid)
            FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = ANY(:schemas) AND NOT t.tgisinternal ORDER BY 1,2,3
        """,
        "function": """
            SELECT p.proname, l.lanname, p.prosrc, p.provolatile, p.prosecdef,
                   pg_get_function_result(p.oid)
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_language l ON l.oid = p.prolang
            WHERE n.nspname = 'public' AND p.proname = 'set_updated_at'
        """,
        "extension": "SELECT extname FROM pg_extension WHERE extname = 'pgcrypto'",
    }
    engine = engine_for(url)
    try:
        async with engine.connect() as connection:
            result = {}
            for key, query in queries.items():
                rows = await connection.execute(text(query), {"schemas": list(SCHEMAS)})
                result[key] = [tuple(row) for row in rows]
            return result
    finally:
        await engine.dispose()
