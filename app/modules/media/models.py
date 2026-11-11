from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    FetchedValue,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.content.models import Profile
    from app.modules.portfolio.models import ProjectMedia, ProjectSectionMedia


class MediaAsset(Base):
    __tablename__ = "media_asset"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_metadata: Mapped[dict[str, JsonValue] | None] = mapped_column(
        "metadata", JSONB(none_as_null=True), nullable=True
    )
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
        UniqueConstraint("storage_provider", "storage_key", name="uq_media_asset_storage"),
        CheckConstraint(
            " type IN ( 'IMAGE', 'VIDEO', 'PDF', 'MODEL_3D', 'DOCUMENT' ) ",
            name="ck_media_asset_type",
        ),
        CheckConstraint("BTRIM(original_filename) <> ''", name="ck_media_asset_original_filename"),
        CheckConstraint("BTRIM(storage_provider) <> ''", name="ck_media_asset_storage_provider"),
        CheckConstraint("BTRIM(storage_key) <> ''", name="ck_media_asset_storage_key"),
        CheckConstraint("BTRIM(url) <> ''", name="ck_media_asset_url"),
        CheckConstraint("BTRIM(mime_type) <> ''", name="ck_media_asset_mime_type"),
        CheckConstraint("file_size >= 0", name="ck_media_asset_file_size"),
        CheckConstraint(" width IS NULL OR width > 0 ", name="ck_media_asset_width"),
        CheckConstraint(" height IS NULL OR height > 0 ", name="ck_media_asset_height"),
        CheckConstraint(
            " metadata IS NULL OR jsonb_typeof(metadata) = 'object' ",
            name="ck_media_asset_metadata_object",
        ),
        Index("idx_media_asset_type", "type"),
        Index("idx_media_asset_created_at", created_at.desc()),
        {
            "schema": "media",
            "comment": "Metadata de archivos almacenados en servicios externos como S3, "
            "R2 o Cloudinary.",
        },
    )

    project_links: Mapped[list[ProjectMedia]] = relationship(
        back_populates="media_asset",
        foreign_keys="ProjectMedia.media_id",
        passive_deletes="all",
        lazy="raise",
    )

    section_links: Mapped[list[ProjectSectionMedia]] = relationship(
        back_populates="media_asset",
        foreign_keys="ProjectSectionMedia.media_id",
        passive_deletes="all",
        lazy="raise",
    )

    photo_profiles: Mapped[list[Profile]] = relationship(
        back_populates="profile_media",
        foreign_keys="Profile.profile_media_id",
        passive_deletes="all",
        lazy="raise",
    )

    cv_profiles: Mapped[list[Profile]] = relationship(
        back_populates="cv_media",
        foreign_keys="Profile.cv_media_id",
        passive_deletes="all",
        lazy="raise",
    )
