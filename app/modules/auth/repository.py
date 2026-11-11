from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, RefreshToken


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user_by_email(self, email: str) -> AppUser | None:
        return await self.session.scalar(
            select(AppUser).where(func.lower(AppUser.email) == func.lower(email)).with_for_update()
        )

    async def lock_user(self, user_id: UUID) -> AppUser | None:
        return await self.session.scalar(
            select(AppUser).where(AppUser.id == user_id).with_for_update()
        )

    async def lock_refresh_token(self, token_hash: str) -> RefreshToken | None:
        return await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )

    async def add_session(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(token)
        await self.session.flush()
        return token

    async def authenticated_user(self, user_id: UUID, session_id: UUID) -> AppUser | None:
        return await self.session.scalar(
            select(AppUser)
            .join(RefreshToken, RefreshToken.user_id == AppUser.id)
            .where(
                AppUser.id == user_id,
                AppUser.is_active.is_(True),
                RefreshToken.id == session_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.clock_timestamp(),
            )
        )

    async def add_user(
        self, email: str, first_name: str, last_name: str, password_hash: str
    ) -> AppUser:
        user = AppUser(
            email=email, first_name=first_name, last_name=last_name, password_hash=password_hash
        )
        self.session.add(user)
        await self.session.flush()
        return user
