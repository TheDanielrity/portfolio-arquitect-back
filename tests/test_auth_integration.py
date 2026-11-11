import asyncio
import os
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete, func, select, update

from app.core.config import Settings
from app.core.database import Database
from app.core.security import Security, hash_refresh_token, new_refresh_token
from app.models import AppUser, RefreshToken
from app.modules.auth.create_admin import provision
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AdministratorCreate
from tests.migration_support import migrate, temporary_databases

pytestmark = pytest.mark.integration
PASSWORD = "Correct horse battery staple!"


@pytest.fixture(scope="module")
def auth_database() -> Iterator[str]:
    url = os.environ.get("MIGRATION_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Set MIGRATION_TEST_ADMIN_URL for isolated PostgreSQL authentication tests")
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        databases = temporary_databases(url)
        migrated, _ = runner.run(databases.__aenter__())
        try:
            runner.run(migrate(migrated, "upgrade"))
            yield migrated.render_as_string(hide_password=False)
        finally:
            runner.run(databases.__aexit__(None, None, None))


def exercise(
    url: str, operation: Callable[[AsyncClient, Database, Security], Awaitable[None]]
) -> None:
    from app.main import create_app

    async def run() -> None:
        application = create_app(Settings(database_url=SecretStr(url)))
        async with application.router.lifespan_context(application):
            async with AsyncClient(
                transport=ASGITransport(app=application, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                await operation(
                    client,
                    cast(Database, application.state.database),
                    cast(Security, application.state.security),
                )

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(run())


async def create_user(database: Database, security: Security, active: bool = True) -> AppUser:
    user = AppUser(
        email=f"architect-{uuid4().hex}@example.org",
        password_hash=security.hash_password(PASSWORD),
        first_name="Ada",
        last_name="Lovelace",
        is_active=active,
    )
    async with database.session() as session, session.begin():
        session.add(user)
    return user


async def login(client: AsyncClient, user: AppUser) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.status_code
    return cast(dict[str, str], response.json())


def authorization(pair: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_login_me_hash_storage_and_safe_responses(
    auth_database: str, caplog: pytest.LogCaptureFixture
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        response = await client.post(
            "/api/v1/auth/login", json={"email": f" {user.email.upper()} ", "password": PASSWORD}
        )
        assert response.status_code == 200
        pair = response.json()
        assert pair["token_type"] == "bearer" and 0 < pair["expires_in"] <= 900
        assert response.headers["Cache-Control"] == "no-store"
        me = await client.get("/api/v1/auth/me", headers=authorization(pair))
        assert me.status_code == 200
        assert me.json() == {
            "id": str(user.id),
            "email": user.email,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "is_active": True,
        }
        async with database.session() as session:
            token = (
                await session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id))
            ).one()
            stored_user = await session.get(AppUser, user.id)
            assert stored_user is not None and stored_user.last_login_at is not None
            assert token.token_hash == hash_refresh_token(pair["refresh_token"])
            assert token.token_hash != pair["refresh_token"]
            stored_token_hash = token.token_hash
        for secret in (
            PASSWORD,
            user.password_hash,
            pair["refresh_token"],
            pair["access_token"],
            stored_token_hash,
        ):
            assert secret not in me.text
            assert secret not in caplog.text

    exercise(auth_database, check)


@pytest.mark.parametrize("failure", ["wrong_password", "unknown", "inactive"])
def test_login_failures_are_uniform(auth_database: str, failure: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security, active=failure != "inactive")
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"missing-{user.email}" if failure == "unknown" else user.email,
                "password": "incorrect" if failure == "wrong_password" else PASSWORD,
            },
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required or invalid credentials"}
        assert response.headers["WWW-Authenticate"] == "Bearer"
        async with database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RefreshToken)
                    .where(RefreshToken.user_id == user.id)
                )
                == 0
            )

    exercise(auth_database, check)


def test_rotation_revokes_old_tokens_and_logout_revokes_new_session(auth_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        first = await login(client, user)
        rotated = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
        )
        assert rotated.status_code == 200
        second = rotated.json()
        assert second["refresh_token"] != first["refresh_token"]
        assert (
            await client.get("/api/v1/auth/me", headers=authorization(first))
        ).status_code == 401
        assert (
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
            )
        ).status_code == 401
        assert (
            await client.get("/api/v1/auth/me", headers=authorization(second))
        ).status_code == 200
        async with database.session() as session:
            rows = (
                await session.scalars(
                    select(RefreshToken)
                    .where(RefreshToken.user_id == user.id)
                    .order_by(RefreshToken.created_at)
                )
            ).all()
            assert len(rows) == 2 and rows[0].revoked_at is not None
            assert rows[0].expires_at == rows[1].expires_at
        for _ in range(2):
            response = await client.post(
                "/api/v1/auth/logout", json={"refresh_token": second["refresh_token"]}
            )
            assert response.status_code == 204 and response.content == b""
        assert (
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
            )
        ).status_code == 401
        assert (
            await client.get("/api/v1/auth/me", headers=authorization(second))
        ).status_code == 401

    exercise(auth_database, check)


@pytest.mark.parametrize("failure", ["expired", "revoked", "inactive", "deleted", "unknown"])
def test_invalid_backing_sessions_cannot_refresh_or_authenticate(
    auth_database: str, failure: str
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        pair = await login(client, user)
        async with database.session() as session, session.begin():
            if failure == "expired":
                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.user_id == user.id)
                    .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                )
            elif failure == "revoked":
                await session.execute(
                    update(RefreshToken)
                    .where(RefreshToken.user_id == user.id)
                    .values(revoked_at=datetime.now(UTC))
                )
            elif failure == "inactive":
                await session.execute(
                    update(AppUser).where(AppUser.id == user.id).values(is_active=False)
                )
            elif failure == "deleted":
                await session.execute(delete(AppUser).where(AppUser.id == user.id))
        refresh = new_refresh_token() if failure == "unknown" else pair["refresh_token"]
        assert (
            await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        ).status_code == 401
        if failure != "unknown":
            assert (
                await client.get("/api/v1/auth/me", headers=authorization(pair))
            ).status_code == 401

    exercise(auth_database, check)


def test_concurrent_refresh_has_one_winner(auth_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        pair = await login(client, user)
        responses = await asyncio.gather(
            *[
                client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
                for _ in range(2)
            ]
        )
        assert sorted(response.status_code for response in responses) == [200, 401]
        winner = next(response.json() for response in responses if response.status_code == 200)
        assert (
            await client.get("/api/v1/auth/me", headers=authorization(winner))
        ).status_code == 200
        async with database.session() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RefreshToken)
                    .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                )
                == 1
            )

    exercise(auth_database, check)


def test_refresh_failure_rolls_back_revocation_and_insert(
    auth_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        pair = await login(client, user)
        original = AuthRepository.add_session

        async def fail(
            repository: AuthRepository, user_id: UUID, token_hash: str, expires_at: datetime
        ) -> RefreshToken:
            await original(repository, user_id, token_hash, expires_at)
            raise RuntimeError("Simulated persistence failure")

        with monkeypatch.context() as patch:
            patch.setattr(AuthRepository, "add_session", fail)
            response = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}
            )
            assert response.status_code == 500
            assert response.json() == {"detail": "Internal server error"}
            assert response.headers["Cache-Control"] == "no-store"
            assert len(response.headers["X-Error-ID"]) == 32
            assert "Simulated persistence failure" not in response.text
        assert (await client.get("/api/v1/auth/me", headers=authorization(pair))).status_code == 200
        async with database.session() as session:
            rows = (
                await session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id))
            ).all()
            assert len(rows) == 1 and rows[0].revoked_at is None
        assert (
            await client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        ).status_code == 200

    exercise(auth_database, check)


def test_logout_is_session_scoped_and_unknown_token_is_idempotent(auth_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        first, second = await login(client, user), await login(client, user)
        assert (
            await client.post("/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]})
        ).status_code == 204
        assert (
            await client.get("/api/v1/auth/me", headers=authorization(second))
        ).status_code == 200
        assert (
            await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh_token()})
        ).status_code == 204

    exercise(auth_database, check)


def test_access_claims_must_match_user_and_session(auth_database: str) -> None:
    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        user = await create_user(database, security)
        pair = await login(client, user)
        identity = security.decode_access_token(pair["access_token"])
        now = datetime.now(UTC)
        for uid, sid, issued, expires in [
            (uuid4(), identity.session_id, now, now + timedelta(minutes=1)),
            (user.id, uuid4(), now, now + timedelta(minutes=1)),
            (user.id, identity.session_id, now - timedelta(minutes=2), now - timedelta(minutes=1)),
        ]:
            token = security.create_access_token(uid, sid, issued, expires)
            assert (
                await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            ).status_code == 401

    exercise(auth_database, check)


def test_local_provisioning_creates_hashed_account_and_rejects_duplicate(
    auth_database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", auth_database)

    async def check(client: AsyncClient, database: Database, security: Security) -> None:
        email = f"new-{uuid4().hex}@example.org"
        body = AdministratorCreate(
            email=email, first_name="Ada", last_name="Lovelace", password=SecretStr(PASSWORD)
        )
        assert await provision(body) == 0
        async with database.session() as session:
            user = (await session.scalars(select(AppUser).where(AppUser.email == email))).one()
            original_hash = user.password_hash
            assert original_hash.startswith("$argon2id$")
            assert security.verify_password(PASSWORD, original_hash) == (True, None)
        duplicate = body.model_copy(
            update={"email": email.upper(), "password": SecretStr("different-valid-password")}
        )
        assert await provision(duplicate) == 1
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert response.status_code == 200
        output = capsys.readouterr()
        assert "Administrator created" in output.out
        assert "already exists" in output.err
        assert PASSWORD not in output.out + output.err
        assert original_hash not in output.out + output.err

    exercise(auth_database, check)
