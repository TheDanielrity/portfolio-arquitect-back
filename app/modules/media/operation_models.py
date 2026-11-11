"""Durable storage intents; original domain tables remain unchanged."""

from datetime import datetime
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StorageOperation(Base):
    __tablename__ = "storage_operation"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Identity snapshot, intentionally no FK: history survives administrator removal.
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    temporary_key: Mapped[str | None] = mapped_column(String(500))
    expected_metadata: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, nullable=False)
    media_id: Mapped[UUID | None]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint("kind IN ('UPLOAD', 'DELETE')", name="ck_storage_operation_kind"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', "
            "'CLEANUP_PENDING', 'CLEANED')",
            name="ck_storage_operation_status",
        ),
        CheckConstraint(
            "BTRIM(storage_provider) <> '' AND BTRIM(storage_key) <> ''",
            name="ck_storage_operation_identity",
        ),
        CheckConstraint(
            "jsonb_typeof(expected_metadata) = 'object'", name="ck_storage_operation_metadata"
        ),
        Index(
            "uq_storage_operation_active",
            "storage_provider",
            "storage_key",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'PROCESSING', 'CLEANUP_PENDING')"),
        ),
        Index("idx_storage_operation_cleanup", "status", "expires_at"),
        Index("idx_storage_operation_media", "media_id", "kind"),
        {"schema": "media"},
    )
