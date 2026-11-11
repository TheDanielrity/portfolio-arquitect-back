import asyncio
import logging

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.database import Database
from app.core.logging import configure_logging

logger = logging.getLogger("app.core.check_database")


async def check_database() -> int:
    """Return a process status without printing connection credentials or driver errors."""
    configure_logging(debug=False)
    try:
        database = Database(Settings())
    except (ValidationError, SQLAlchemyError):
        logger.error("Invalid database configuration; check DATABASE_URL")
        return 1
    try:
        await database.verify_connection()
    except (SQLAlchemyError, OSError):
        logger.error("Database connection failed; check server availability and credentials")
        return 1
    finally:
        await database.dispose()
    logger.info("Database connection verified")
    return 0


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        raise SystemExit(runner.run(check_database()))
