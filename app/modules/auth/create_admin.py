"""Interactive local provisioning; passwords never appear in command arguments."""

import asyncio
import getpass
import sys

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.database import Database
from app.core.exceptions import AdministratorAlreadyExists
from app.core.security import Security
from app.modules.auth.schemas import AdministratorCreate
from app.modules.auth.service import AuthService


async def provision(body: AdministratorCreate) -> int:
    database: Database | None = None
    try:
        settings = Settings()
        security = await run_in_threadpool(Security, settings)
        database = Database(settings)
        async with database.session() as session:
            await AuthService(session, security, settings).create_administrator(body)
        print("Administrator created.")
        return 0
    except AdministratorAlreadyExists:
        print("An administrator with that email already exists.", file=sys.stderr)
    except (ValidationError, SQLAlchemyError, OSError):
        print(
            "Provisioning failed; check configuration, database access and migrations.",
            file=sys.stderr,
        )
    finally:
        if database is not None:
            await database.dispose()
    return 1


def main() -> int:
    if not sys.stdin.isatty():
        print("Run this command in an interactive terminal.", file=sys.stderr)
        return 1
    try:
        email = input("Email: ")
        first_name = input("First name: ")
        last_name = input("Last name: ")
        password = getpass.getpass("Password (12–1024 characters): ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
        body = AdministratorCreate(
            email=email, first_name=first_name, last_name=last_name, password=SecretStr(password)
        )
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            return runner.run(provision(body))
    except ValidationError:
        print(
            "Invalid details: supply an email, names and a 12–1024 character password.",
            file=sys.stderr,
        )
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Provisioning cancelled.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
