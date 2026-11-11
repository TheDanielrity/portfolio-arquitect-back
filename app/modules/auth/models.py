from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppUser(Base):
    __tablename__ = "app_user"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=FetchedValue(),
    )

    __table_args__ = (
        CheckConstraint("BTRIM(email) <> ''", name="ck_app_user_email_not_empty"),
        CheckConstraint("BTRIM(first_name) <> ''", name="ck_app_user_first_name_not_empty"),
        CheckConstraint("BTRIM(last_name) <> ''", name="ck_app_user_last_name_not_empty"),
        Index("uq_app_user_email_lower", func.lower(email), unique=True),
        {"schema": "auth"},
    )

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        foreign_keys="RefreshToken.user_id",
        passive_deletes="all",
        lazy="raise",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_token"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["auth.app_user.id"], name="fk_refresh_token_user", ondelete="CASCADE"
        ),
        UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
        CheckConstraint("BTRIM(token_hash) <> ''", name="ck_refresh_token_hash_not_empty"),
        CheckConstraint(
            " revoked_at IS NULL OR revoked_at >= created_at ", name="ck_refresh_token_dates"
        ),
        Index("idx_refresh_token_user_id", "user_id"),
        Index("idx_refresh_token_expires_at", "expires_at"),
        Index(
            "idx_refresh_token_active_user",
            "user_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        {"schema": "auth"},
    )

    user: Mapped[AppUser] = relationship(
        back_populates="refresh_tokens", foreign_keys=[user_id], lazy="raise"
    )
