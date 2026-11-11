"""Run bounded reconciliation explicitly or from the OS task scheduler."""

import argparse
import asyncio

from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.database import Database
from app.modules.media.dependencies import build_storage
from app.modules.media.upload_service import UploadService


async def cleanup(limit: int) -> int:
    settings = Settings()
    database = Database(settings)
    try:
        storage = await run_in_threadpool(build_storage, settings)
        async with database.session() as session:
            return await UploadService(session, storage, settings).cleanup(limit)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile pending media storage operations")
    parser.add_argument("--limit", type=int, default=100)
    arguments = parser.parse_args()
    if not 1 <= arguments.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        print(f"Reconciled operations: {runner.run(cleanup(arguments.limit))}")


if __name__ == "__main__":
    main()
