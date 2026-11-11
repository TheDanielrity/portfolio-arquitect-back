from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.exceptions import AdministratorAlreadyExists, AuthenticationError
from app.core.security import Security, hash_refresh_token, new_refresh_token
from app.models import AppUser
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import AdministratorCreate, TokenResponse, UserResponse


class AuthService:
    def __init__(self, session: AsyncSession, security: Security, settings: Settings) -> None:
        self.session = session
        self.repository = AuthRepository(session)
        self.security = security
        self.settings = settings

    async def _issue_tokens(self, user: AppUser, expires_at: datetime) -> TokenResponse:
        now = datetime.now(UTC)
        access_expires = min(
            now + timedelta(minutes=self.settings.access_token_expire_minutes), expires_at
        )
        if int(access_expires.timestamp()) <= int(now.timestamp()):
            raise AuthenticationError
        raw_token = new_refresh_token()
        token = await self.repository.add_session(
            user.id, hash_refresh_token(raw_token), expires_at
        )
        return TokenResponse(
            access_token=self.security.create_access_token(user.id, token.id, now, access_expires),
            refresh_token=raw_token,
            expires_in=int(access_expires.timestamp()) - int(now.timestamp()),
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        async with self.session.begin():
            user = await self.repository.user_by_email(email.strip())
            valid, updated_hash = await run_in_threadpool(
                self.security.verify_password, password, user.password_hash if user else None
            )
            if not valid or user is None or not user.is_active:
                raise AuthenticationError
            if updated_hash is not None:
                user.password_hash = updated_hash
            user.last_login_at = datetime.now(UTC)
            return await self._issue_tokens(
                user, datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days)
            )

    async def refresh(self, raw_token: str) -> TokenResponse:
        async with self.session.begin():
            token = await self.repository.lock_refresh_token(hash_refresh_token(raw_token))
            now = datetime.now(UTC)
            if token is None or token.revoked_at is not None or token.expires_at <= now:
                raise AuthenticationError
            user = await self.repository.lock_user(token.user_id)
            if user is None or not user.is_active:
                raise AuthenticationError
            token.revoked_at = now
            # Keep the original session deadline; rotation does not extend it indefinitely.
            return await self._issue_tokens(user, token.expires_at)

    async def logout(self, raw_token: str) -> None:
        """Idempotently revoke only the session identified by this refresh secret."""
        async with self.session.begin():
            token = await self.repository.lock_refresh_token(hash_refresh_token(raw_token))
            if token is not None and token.revoked_at is None:
                token.revoked_at = datetime.now(UTC)

    async def authenticate(self, access_token: str) -> AppUser:
        identity = self.security.decode_access_token(access_token)
        user = await self.repository.authenticated_user(identity.user_id, identity.session_id)
        if user is None:
            raise AuthenticationError
        return user

    async def create_administrator(self, body: AdministratorCreate) -> UserResponse:
        """Provision an administrator locally without replacing an existing account."""
        password_hash = await run_in_threadpool(
            self.security.hash_password, body.password.get_secret_value()
        )
        try:
            async with self.session.begin():
                user = await self.repository.add_user(
                    body.email, body.first_name, body.last_name, password_hash
                )
                return UserResponse.model_validate(user)
        except IntegrityError as exc:
            if (
                getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "uq_app_user_email_lower"
            ):
                raise AdministratorAlreadyExists from exc
            raise
