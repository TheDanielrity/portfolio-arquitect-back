from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactMessage(Base):
    __tablename__ = "contact_message"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'NEW'"))
    ip_address: Mapped[IPv4Address | IPv6Address | IPv4Interface | IPv6Interface | None] = (
        mapped_column(INET, nullable=True)
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("BTRIM(name) <> ''", name="ck_contact_message_name"),
        CheckConstraint("BTRIM(email) <> ''", name="ck_contact_message_email"),
        CheckConstraint("BTRIM(message) <> ''", name="ck_contact_message_content"),
        CheckConstraint(
            " status IN ( 'NEW', 'READ', 'REPLIED', 'ARCHIVED', 'SPAM' ) ",
            name="ck_contact_message_status",
        ),
        CheckConstraint(
            " read_at IS NULL OR read_at >= created_at ", name="ck_contact_message_read_date"
        ),
        CheckConstraint(
            " replied_at IS NULL OR replied_at >= created_at ", name="ck_contact_message_reply_date"
        ),
        Index("idx_contact_message_status", "status"),
        Index("idx_contact_message_created", created_at.desc()),
        Index("idx_contact_message_inbox", "status", created_at.desc()),
        Index(
            "idx_contact_message_new",
            created_at.desc(),
            postgresql_where=text("status = 'NEW'"),
        ),
        {"schema": "contact"},
    )
