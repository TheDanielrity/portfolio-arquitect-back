from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.media.models import MediaAsset


class Profile(Base):
    __tablename__ = "profile"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    professional_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    short_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_media_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    cv_media_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
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
        ForeignKeyConstraint(
            ["profile_media_id"],
            ["media.media_asset.id"],
            name="fk_profile_profile_media",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["cv_media_id"],
            ["media.media_asset.id"],
            name="fk_profile_cv_media",
            ondelete="SET NULL",
        ),
        CheckConstraint("BTRIM(first_name) <> ''", name="ck_profile_first_name"),
        CheckConstraint("BTRIM(last_name) <> ''", name="ck_profile_last_name"),
        Index("idx_profile_profile_media", "profile_media_id"),
        Index("idx_profile_cv_media", "cv_media_id"),
        Index(
            "uq_profile_single_active",
            text("(1)"),
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
        {"schema": "content"},
    )

    profile_media: Mapped[MediaAsset | None] = relationship(
        back_populates="photo_profiles", foreign_keys=[profile_media_id], lazy="raise"
    )

    cv_media: Mapped[MediaAsset | None] = relationship(
        back_populates="cv_profiles", foreign_keys=[cv_media_id], lazy="raise"
    )

    social_links: Mapped[list[SocialLink]] = relationship(
        back_populates="profile",
        foreign_keys="SocialLink.profile_id",
        passive_deletes="all",
        lazy="raise",
    )


class SocialLink(Base):
    __tablename__ = "social_link"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
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
        ForeignKeyConstraint(
            ["profile_id"],
            ["content.profile.id"],
            name="fk_social_link_profile",
            ondelete="CASCADE",
        ),
        CheckConstraint("BTRIM(platform) <> ''", name="ck_social_link_platform"),
        CheckConstraint("BTRIM(url) <> ''", name="ck_social_link_url"),
        CheckConstraint("sort_order >= 0", name="ck_social_link_sort"),
        Index("idx_social_link_profile", "profile_id"),
        Index("idx_social_link_profile_order", "profile_id", "sort_order"),
        Index(
            "uq_social_link_profile_platform",
            "profile_id",
            func.lower(platform),
            unique=True,
        ),
        {"schema": "content"},
    )

    profile: Mapped[Profile] = relationship(
        back_populates="social_links", foreign_keys=[profile_id], lazy="raise"
    )


class Service(Base):
    __tablename__ = "service"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(170), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
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
        CheckConstraint("BTRIM(name) <> ''", name="ck_service_name"),
        CheckConstraint("BTRIM(slug) <> ''", name="ck_service_slug"),
        CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_service_slug_format"),
        CheckConstraint("sort_order >= 0", name="ck_service_sort"),
        Index("uq_service_slug_lower", func.lower(slug), unique=True),
        Index("idx_service_visible_order", "is_visible", "sort_order"),
        {"schema": "content"},
    )


class SiteSetting(Base):
    __tablename__ = "site_setting"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[JsonValue] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=FetchedValue(),
    )

    __table_args__ = (
        UniqueConstraint("key", name="uq_site_setting_key"),
        CheckConstraint("BTRIM(key) <> ''", name="ck_site_setting_key"),
        {
            "schema": "content",
            "comment": "Configuraciones dinámicas globales del sitio almacenadas como JSONB.",
        },
    )
