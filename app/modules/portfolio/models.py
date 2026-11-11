from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.media.models import MediaAsset


class Project(Base):
    __tablename__ = "project"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'DRAFT'"))
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PUBLIC'")
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    seo_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(320), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        server_onupdate=FetchedValue(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("BTRIM(title) <> ''", name="ck_project_title_not_empty"),
        CheckConstraint("BTRIM(slug) <> ''", name="ck_project_slug_not_empty"),
        CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_project_slug_format"),
        CheckConstraint(" year IS NULL OR year BETWEEN 1800 AND 2200 ", name="ck_project_year"),
        CheckConstraint(" area_m2 IS NULL OR area_m2 > 0 ", name="ck_project_area"),
        CheckConstraint(
            " status IN ( 'DRAFT', 'PUBLISHED', 'ARCHIVED' ) ", name="ck_project_status"
        ),
        CheckConstraint(
            " visibility IN ( 'PUBLIC', 'PRIVATE', 'UNLISTED' ) ", name="ck_project_visibility"
        ),
        CheckConstraint("sort_order >= 0", name="ck_project_sort_order"),
        CheckConstraint(
            " deleted_at IS NULL OR deleted_at >= created_at ", name="ck_project_deleted_at"
        ),
        Index(
            "uq_project_slug_active",
            func.lower(slug),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_project_status", "status"),
        Index("idx_project_visibility", "visibility"),
        Index("idx_project_published_at", published_at.desc()),
        Index("idx_project_featured", "is_featured", "sort_order"),
        Index(
            "uq_project_single_featured",
            "is_featured",
            unique=True,
            postgresql_where=text("is_featured AND deleted_at IS NULL"),
        ),
        Index(
            "idx_project_public_listing",
            "status",
            "visibility",
            "sort_order",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_project_active",
            created_at.desc(),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {
            "schema": "portfolio",
            "comment": "Proyectos publicados o administrados dentro del portafolio.",
        },
    )

    category_links: Mapped[list[ProjectCategory]] = relationship(
        back_populates="project",
        foreign_keys="ProjectCategory.project_id",
        passive_deletes="all",
        lazy="raise",
    )

    tag_links: Mapped[list[ProjectTag]] = relationship(
        back_populates="project",
        foreign_keys="ProjectTag.project_id",
        passive_deletes="all",
        lazy="raise",
    )

    attributes: Mapped[list[ProjectAttribute]] = relationship(
        back_populates="project",
        foreign_keys="ProjectAttribute.project_id",
        passive_deletes="all",
        lazy="raise",
    )

    media_links: Mapped[list[ProjectMedia]] = relationship(
        back_populates="project",
        foreign_keys="ProjectMedia.project_id",
        passive_deletes="all",
        lazy="raise",
    )

    sections: Mapped[list[ProjectSection]] = relationship(
        back_populates="project",
        foreign_keys="ProjectSection.project_id",
        passive_deletes="all",
        lazy="raise",
    )


class Category(Base):
    __tablename__ = "category"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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
        CheckConstraint("BTRIM(name) <> ''", name="ck_category_name_not_empty"),
        CheckConstraint("BTRIM(slug) <> ''", name="ck_category_slug_not_empty"),
        CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_category_slug_format"),
        CheckConstraint("sort_order >= 0", name="ck_category_sort_order"),
        Index("uq_category_slug_lower", func.lower(slug), unique=True),
        Index("idx_category_active_order", "is_active", "sort_order"),
        {"schema": "portfolio"},
    )

    project_links: Mapped[list[ProjectCategory]] = relationship(
        back_populates="category",
        foreign_keys="ProjectCategory.category_id",
        passive_deletes="all",
        lazy="raise",
    )


class ProjectCategory(Base):
    __tablename__ = "project_category"
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    category_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        PrimaryKeyConstraint("project_id", "category_id", name="pk_project_category"),
        ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_category_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["category_id"],
            ["portfolio.category.id"],
            name="fk_project_category_category",
            ondelete="CASCADE",
        ),
        Index("idx_project_category_category", "category_id"),
        {"schema": "portfolio"},
    )

    project: Mapped[Project] = relationship(
        back_populates="category_links", foreign_keys=[project_id], lazy="raise"
    )

    category: Mapped[Category] = relationship(
        back_populates="project_links", foreign_keys=[category_id], lazy="raise"
    )


class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint("BTRIM(name) <> ''", name="ck_tag_name_not_empty"),
        CheckConstraint("BTRIM(slug) <> ''", name="ck_tag_slug_not_empty"),
        CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_tag_slug_format"),
        Index("uq_tag_name_lower", func.lower(name), unique=True),
        Index("uq_tag_slug_lower", func.lower(slug), unique=True),
        {"schema": "portfolio"},
    )

    project_links: Mapped[list[ProjectTag]] = relationship(
        back_populates="tag", foreign_keys="ProjectTag.tag_id", passive_deletes="all", lazy="raise"
    )


class ProjectTag(Base):
    __tablename__ = "project_tag"
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tag_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        PrimaryKeyConstraint("project_id", "tag_id", name="pk_project_tag"),
        ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_tag_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tag_id"], ["portfolio.tag.id"], name="fk_project_tag_tag", ondelete="CASCADE"
        ),
        Index("idx_project_tag_tag", "tag_id"),
        {"schema": "portfolio"},
    )

    project: Mapped[Project] = relationship(
        back_populates="tag_links", foreign_keys=[project_id], lazy="raise"
    )

    tag: Mapped[Tag] = relationship(
        back_populates="project_links", foreign_keys=[tag_id], lazy="raise"
    )


class ProjectAttribute(Base):
    __tablename__ = "project_attribute"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
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
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_attribute_project",
            ondelete="CASCADE",
        ),
        CheckConstraint("BTRIM(label) <> ''", name="ck_project_attribute_label"),
        CheckConstraint("BTRIM(value) <> ''", name="ck_project_attribute_value"),
        CheckConstraint("sort_order >= 0", name="ck_project_attribute_sort"),
        Index("idx_project_attribute_project_order", "project_id", "sort_order"),
        {
            "schema": "portfolio",
            "comment": "Atributos variables descriptivos de un proyecto, como arquitecto, "
            "fotógrafo o constructora.",
        },
    )

    project: Mapped[Project] = relationship(
        back_populates="attributes", foreign_keys=[project_id], lazy="raise"
    )


class ProjectMedia(Base):
    __tablename__ = "project_media"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    media_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_media_project",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["media_id"],
            ["media.media_asset.id"],
            name="fk_project_media_media",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("project_id", "media_id", "role", name="uq_project_media_role"),
        CheckConstraint(
            " role IN ( 'COVER', 'GALLERY', 'PLAN', 'RENDER', 'DOCUMENT', 'MODEL' ) ",
            name="ck_project_media_role",
        ),
        CheckConstraint("sort_order >= 0", name="ck_project_media_sort"),
        Index("idx_project_media_project", "project_id"),
        Index("idx_project_media_media", "media_id"),
        Index("idx_project_media_order", "project_id", "sort_order"),
        Index(
            "uq_project_single_cover",
            "project_id",
            unique=True,
            postgresql_where=text("role = 'COVER'"),
        ),
        {"schema": "portfolio"},
    )

    project: Mapped[Project] = relationship(
        back_populates="media_links", foreign_keys=[project_id], lazy="raise"
    )

    media_asset: Mapped[MediaAsset] = relationship(
        back_populates="project_links", foreign_keys=[media_id], lazy="raise"
    )


class ProjectSection(Base):
    __tablename__ = "project_section"
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
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
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_section_project",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "section_type IN ('TEXT', 'IMAGE', 'GALLERY', 'VIDEO', 'MODEL_3D', 'QUOTE', 'SPLIT')",
            name="ck_project_section_type",
        ),
        CheckConstraint("sort_order >= 0", name="ck_project_section_sort"),
        Index("idx_project_section_project", "project_id"),
        Index("idx_project_section_project_order", "project_id", "sort_order"),
        {
            "schema": "portfolio",
            "comment": "Bloques dinámicos utilizados para construir la presentación "
            "narrativa de cada proyecto.",
        },
    )

    project: Mapped[Project] = relationship(
        back_populates="sections", foreign_keys=[project_id], lazy="raise"
    )

    media_links: Mapped[list[ProjectSectionMedia]] = relationship(
        back_populates="section",
        foreign_keys="ProjectSectionMedia.section_id",
        passive_deletes="all",
        lazy="raise",
    )


class ProjectSectionMedia(Base):
    __tablename__ = "project_section_media"
    section_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    media_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        PrimaryKeyConstraint("section_id", "media_id", name="pk_project_section_media"),
        ForeignKeyConstraint(
            ["section_id"],
            ["portfolio.project_section.id"],
            name="fk_project_section_media_section",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["media_id"],
            ["media.media_asset.id"],
            name="fk_project_section_media_media",
            ondelete="RESTRICT",
        ),
        CheckConstraint("sort_order >= 0", name="ck_project_section_media_sort"),
        Index("idx_project_section_media_media", "media_id"),
        Index("idx_project_section_media_order", "section_id", "sort_order"),
        {"schema": "portfolio"},
    )

    section: Mapped[ProjectSection] = relationship(
        back_populates="media_links", foreign_keys=[section_id], lazy="raise"
    )

    media_asset: Mapped[MediaAsset] = relationship(
        back_populates="section_links", foreign_keys=[media_id], lazy="raise"
    )
