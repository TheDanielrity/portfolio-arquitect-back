"""Create the approved architecture portfolio schema.

Revision ID: 0001_initial_schema
Revises: None

Downgrade permanently deletes all domain tables and their data. It preserves
pgcrypto, which can be shared with other applications. No DROP uses CASCADE.
This revision is self-contained: it never imports current application models
or reads mutable design documents.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute("CREATE SCHEMA IF NOT EXISTS portfolio")
    op.execute("CREATE SCHEMA IF NOT EXISTS media")
    op.execute("CREATE SCHEMA IF NOT EXISTS content")
    op.execute("CREATE SCHEMA IF NOT EXISTS contact")
    op.execute(
        """CREATE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;"""
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(email) <> ''", name="ck_app_user_email_not_empty"),
        sa.CheckConstraint("BTRIM(first_name) <> ''", name="ck_app_user_first_name_not_empty"),
        sa.CheckConstraint("BTRIM(last_name) <> ''", name="ck_app_user_last_name_not_empty"),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index(
        "uq_app_user_email_lower",
        "app_user",
        [sa.literal_column("lower(email)")],
        unique=True,
        schema="auth",
    )
    op.create_table(
        "contact_message",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default=sa.text("'NEW'"), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            " status IN ( 'NEW', 'READ', 'REPLIED', 'ARCHIVED', 'SPAM' ) ",
            name="ck_contact_message_status",
        ),
        sa.CheckConstraint("BTRIM(email) <> ''", name="ck_contact_message_email"),
        sa.CheckConstraint("BTRIM(message) <> ''", name="ck_contact_message_content"),
        sa.CheckConstraint("BTRIM(name) <> ''", name="ck_contact_message_name"),
        sa.CheckConstraint(
            " read_at IS NULL OR read_at >= created_at ", name="ck_contact_message_read_date"
        ),
        sa.CheckConstraint(
            " replied_at IS NULL OR replied_at >= created_at ", name="ck_contact_message_reply_date"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="contact",
    )
    op.create_index(
        "idx_contact_message_created",
        "contact_message",
        [sa.literal_column("created_at DESC")],
        unique=False,
        schema="contact",
    )
    op.create_index(
        "idx_contact_message_inbox",
        "contact_message",
        ["status", sa.literal_column("created_at DESC")],
        unique=False,
        schema="contact",
    )
    op.create_index(
        "idx_contact_message_new",
        "contact_message",
        [sa.literal_column("created_at DESC")],
        unique=False,
        schema="contact",
        postgresql_where=sa.text("status = 'NEW'"),
    )
    op.create_index(
        "idx_contact_message_status", "contact_message", ["status"], unique=False, schema="contact"
    )
    op.create_table(
        "service",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=170), nullable=False),
        sa.Column("short_description", sa.String(length=300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_service_slug_format"),
        sa.CheckConstraint("BTRIM(name) <> ''", name="ck_service_name"),
        sa.CheckConstraint("BTRIM(slug) <> ''", name="ck_service_slug"),
        sa.CheckConstraint("sort_order >= 0", name="ck_service_sort"),
        sa.PrimaryKeyConstraint("id"),
        schema="content",
    )
    op.create_index(
        "idx_service_visible_order",
        "service",
        ["is_visible", "sort_order"],
        unique=False,
        schema="content",
    )
    op.create_index(
        "uq_service_slug_lower",
        "service",
        [sa.literal_column("lower(slug)")],
        unique=True,
        schema="content",
    )
    op.create_table(
        "site_setting",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(key) <> ''", name="ck_site_setting_key"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_site_setting_key"),
        schema="content",
        comment="Configuraciones dinámicas globales del sitio almacenadas como JSONB.",
    )
    op.create_table(
        "media_asset",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            " metadata IS NULL OR jsonb_typeof(metadata) = 'object' ",
            name="ck_media_asset_metadata_object",
        ),
        sa.CheckConstraint(
            " type IN ( 'IMAGE', 'VIDEO', 'PDF', 'MODEL_3D', 'DOCUMENT' ) ",
            name="ck_media_asset_type",
        ),
        sa.CheckConstraint("BTRIM(mime_type) <> ''", name="ck_media_asset_mime_type"),
        sa.CheckConstraint(
            "BTRIM(original_filename) <> ''", name="ck_media_asset_original_filename"
        ),
        sa.CheckConstraint("BTRIM(storage_key) <> ''", name="ck_media_asset_storage_key"),
        sa.CheckConstraint("BTRIM(storage_provider) <> ''", name="ck_media_asset_storage_provider"),
        sa.CheckConstraint("BTRIM(url) <> ''", name="ck_media_asset_url"),
        sa.CheckConstraint(" height IS NULL OR height > 0 ", name="ck_media_asset_height"),
        sa.CheckConstraint(" width IS NULL OR width > 0 ", name="ck_media_asset_width"),
        sa.CheckConstraint("file_size >= 0", name="ck_media_asset_file_size"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_provider", "storage_key", name="uq_media_asset_storage"),
        schema="media",
        comment="Metadata de archivos almacenados en servicios externos como S3, R2 o Cloudinary.",
    )
    op.create_index(
        "idx_media_asset_created_at",
        "media_asset",
        [sa.literal_column("created_at DESC")],
        unique=False,
        schema="media",
    )
    op.create_index("idx_media_asset_type", "media_asset", ["type"], unique=False, schema="media")
    op.create_table(
        "category",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_category_slug_format"),
        sa.CheckConstraint("BTRIM(name) <> ''", name="ck_category_name_not_empty"),
        sa.CheckConstraint("BTRIM(slug) <> ''", name="ck_category_slug_not_empty"),
        sa.CheckConstraint("sort_order >= 0", name="ck_category_sort_order"),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
    )
    op.create_index(
        "idx_category_active_order",
        "category",
        ["is_active", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "uq_category_slug_lower",
        "category",
        [sa.literal_column("lower(slug)")],
        unique=True,
        schema="portfolio",
    )
    op.create_table(
        "project",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("area_m2", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column(
            "visibility", sa.String(length=20), server_default=sa.text("'PUBLIC'"), nullable=False
        ),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("seo_title", sa.String(length=200), nullable=True),
        sa.Column("seo_description", sa.String(length=320), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_project_slug_format"),
        sa.CheckConstraint(
            " status IN ( 'DRAFT', 'PUBLISHED', 'ARCHIVED' ) ", name="ck_project_status"
        ),
        sa.CheckConstraint(
            " visibility IN ( 'PUBLIC', 'PRIVATE', 'UNLISTED' ) ", name="ck_project_visibility"
        ),
        sa.CheckConstraint("BTRIM(slug) <> ''", name="ck_project_slug_not_empty"),
        sa.CheckConstraint("BTRIM(title) <> ''", name="ck_project_title_not_empty"),
        sa.CheckConstraint(" area_m2 IS NULL OR area_m2 > 0 ", name="ck_project_area"),
        sa.CheckConstraint(
            " deleted_at IS NULL OR deleted_at >= created_at ", name="ck_project_deleted_at"
        ),
        sa.CheckConstraint(" year IS NULL OR year BETWEEN 1800 AND 2200 ", name="ck_project_year"),
        sa.CheckConstraint("sort_order >= 0", name="ck_project_sort_order"),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
        comment="Proyectos publicados o administrados dentro del portafolio.",
    )
    op.create_index(
        "idx_project_active",
        "project",
        [sa.literal_column("created_at DESC")],
        unique=False,
        schema="portfolio",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_project_featured",
        "project",
        ["is_featured", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "idx_project_public_listing",
        "project",
        ["status", "visibility", "sort_order"],
        unique=False,
        schema="portfolio",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_project_published_at",
        "project",
        [sa.literal_column("published_at DESC")],
        unique=False,
        schema="portfolio",
    )
    op.create_index("idx_project_status", "project", ["status"], unique=False, schema="portfolio")
    op.create_index(
        "idx_project_visibility", "project", ["visibility"], unique=False, schema="portfolio"
    )
    op.create_index(
        "uq_project_slug_active",
        "project",
        [sa.literal_column("lower(slug)")],
        unique=True,
        schema="portfolio",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "tag",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(" slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' ", name="ck_tag_slug_format"),
        sa.CheckConstraint("BTRIM(name) <> ''", name="ck_tag_name_not_empty"),
        sa.CheckConstraint("BTRIM(slug) <> ''", name="ck_tag_slug_not_empty"),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
    )
    op.create_index(
        "uq_tag_name_lower",
        "tag",
        [sa.literal_column("lower(name)")],
        unique=True,
        schema="portfolio",
    )
    op.create_index(
        "uq_tag_slug_lower",
        "tag",
        [sa.literal_column("lower(slug)")],
        unique=True,
        schema="portfolio",
    )
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(token_hash) <> ''", name="ck_refresh_token_hash_not_empty"),
        sa.CheckConstraint(
            " revoked_at IS NULL OR revoked_at >= created_at ", name="ck_refresh_token_dates"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["auth.app_user.id"], name="fk_refresh_token_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
        schema="auth",
    )
    op.create_index(
        "idx_refresh_token_active_user",
        "refresh_token",
        ["user_id", "expires_at"],
        unique=False,
        schema="auth",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_refresh_token_expires_at", "refresh_token", ["expires_at"], unique=False, schema="auth"
    )
    op.create_index(
        "idx_refresh_token_user_id", "refresh_token", ["user_id"], unique=False, schema="auth"
    )
    op.create_table(
        "profile",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("professional_title", sa.String(length=150), nullable=True),
        sa.Column("short_bio", sa.Text(), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("profile_media_id", sa.UUID(), nullable=True),
        sa.Column("cv_media_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(first_name) <> ''", name="ck_profile_first_name"),
        sa.CheckConstraint("BTRIM(last_name) <> ''", name="ck_profile_last_name"),
        sa.ForeignKeyConstraint(
            ["cv_media_id"],
            ["media.media_asset.id"],
            name="fk_profile_cv_media",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["profile_media_id"],
            ["media.media_asset.id"],
            name="fk_profile_profile_media",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="content",
    )
    op.create_index(
        "idx_profile_cv_media", "profile", ["cv_media_id"], unique=False, schema="content"
    )
    op.create_index(
        "idx_profile_profile_media", "profile", ["profile_media_id"], unique=False, schema="content"
    )
    op.create_index(
        "uq_profile_single_active",
        "profile",
        [sa.literal_column("(1)")],
        unique=True,
        schema="content",
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_table(
        "project_attribute",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(label) <> ''", name="ck_project_attribute_label"),
        sa.CheckConstraint("BTRIM(value) <> ''", name="ck_project_attribute_value"),
        sa.CheckConstraint("sort_order >= 0", name="ck_project_attribute_sort"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_attribute_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
        comment="Atributos variables descriptivos de un proyecto, como arquitecto, "
        "fotógrafo o constructora.",
    )
    op.create_index(
        "idx_project_attribute_project_order",
        "project_attribute",
        ["project_id", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.create_table(
        "project_category",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["portfolio.category.id"],
            name="fk_project_category_category",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_category_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "category_id", name="pk_project_category"),
        schema="portfolio",
    )
    op.create_index(
        "idx_project_category_category",
        "project_category",
        ["category_id"],
        unique=False,
        schema="portfolio",
    )
    op.create_table(
        "project_media",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("media_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            " role IN ( 'COVER', 'GALLERY', 'PLAN', 'RENDER', 'DOCUMENT', 'MODEL' ) ",
            name="ck_project_media_role",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_project_media_sort"),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.media_asset.id"],
            name="fk_project_media_media",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_media_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "media_id", "role", name="uq_project_media_role"),
        schema="portfolio",
    )
    op.create_index(
        "idx_project_media_media", "project_media", ["media_id"], unique=False, schema="portfolio"
    )
    op.create_index(
        "idx_project_media_order",
        "project_media",
        ["project_id", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "idx_project_media_project",
        "project_media",
        ["project_id"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "uq_project_single_cover",
        "project_media",
        ["project_id"],
        unique=True,
        schema="portfolio",
        postgresql_where=sa.text("role = 'COVER'"),
    )
    op.create_table(
        "project_section",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("section_type", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "section_type IN ('TEXT', 'IMAGE', 'GALLERY', 'VIDEO', 'MODEL_3D', 'QUOTE', 'SPLIT')",
            name="ck_project_section_type",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_project_section_sort"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_section_project",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
        comment="Bloques dinámicos utilizados para construir la presentación narrativa de "
        "cada proyecto.",
    )
    op.create_index(
        "idx_project_section_project",
        "project_section",
        ["project_id"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "idx_project_section_project_order",
        "project_section",
        ["project_id", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.create_table(
        "project_tag",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["portfolio.project.id"],
            name="fk_project_tag_project",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["portfolio.tag.id"], name="fk_project_tag_tag", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("project_id", "tag_id", name="pk_project_tag"),
        schema="portfolio",
    )
    op.create_index(
        "idx_project_tag_tag", "project_tag", ["tag_id"], unique=False, schema="portfolio"
    )
    op.create_table(
        "social_link",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("BTRIM(platform) <> ''", name="ck_social_link_platform"),
        sa.CheckConstraint("BTRIM(url) <> ''", name="ck_social_link_url"),
        sa.CheckConstraint("sort_order >= 0", name="ck_social_link_sort"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["content.profile.id"],
            name="fk_social_link_profile",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="content",
    )
    op.create_index(
        "idx_social_link_profile", "social_link", ["profile_id"], unique=False, schema="content"
    )
    op.create_index(
        "idx_social_link_profile_order",
        "social_link",
        ["profile_id", "sort_order"],
        unique=False,
        schema="content",
    )
    op.create_index(
        "uq_social_link_profile_platform",
        "social_link",
        ["profile_id", sa.literal_column("lower(platform)")],
        unique=True,
        schema="content",
    )
    op.create_table(
        "project_section_media",
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("media_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("caption", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_project_section_media_sort"),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.media_asset.id"],
            name="fk_project_section_media_media",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["portfolio.project_section.id"],
            name="fk_project_section_media_section",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("section_id", "media_id", name="pk_project_section_media"),
        schema="portfolio",
    )
    op.create_index(
        "idx_project_section_media_media",
        "project_section_media",
        ["media_id"],
        unique=False,
        schema="portfolio",
    )
    op.create_index(
        "idx_project_section_media_order",
        "project_section_media",
        ["section_id", "sort_order"],
        unique=False,
        schema="portfolio",
    )
    op.execute(
        """CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON auth.app_user
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_media_asset_updated_at
BEFORE UPDATE ON media.media_asset
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_project_updated_at
BEFORE UPDATE ON portfolio.project
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_category_updated_at
BEFORE UPDATE ON portfolio.category
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_project_attribute_updated_at
BEFORE UPDATE ON portfolio.project_attribute
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_project_section_updated_at
BEFORE UPDATE ON portfolio.project_section
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_profile_updated_at
BEFORE UPDATE ON content.profile
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_social_link_updated_at
BEFORE UPDATE ON content.social_link
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_service_updated_at
BEFORE UPDATE ON content.service
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute(
        """CREATE TRIGGER trg_site_setting_updated_at
BEFORE UPDATE ON content.site_setting
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();"""
    )
    op.execute("COMMENT ON SCHEMA auth IS 'Autenticación y sesiones administrativas.'")
    op.execute(
        "COMMENT ON SCHEMA portfolio IS 'Proyectos, categorías, etiquetas y estructura "
        "del portafolio.'"
    )
    op.execute(
        "COMMENT ON SCHEMA media IS 'Gestión centralizada de archivos y recursos multimedia.'"
    )
    op.execute("COMMENT ON SCHEMA content IS 'Contenido general configurable del sitio web.'")
    op.execute("COMMENT ON SCHEMA contact IS 'Mensajes recibidos desde formularios públicos.'")


def downgrade() -> None:
    op.drop_table("project_section_media", schema="portfolio")
    op.drop_table("social_link", schema="content")
    op.drop_table("project_tag", schema="portfolio")
    op.drop_table("project_section", schema="portfolio")
    op.drop_table("project_media", schema="portfolio")
    op.drop_table("project_category", schema="portfolio")
    op.drop_table("project_attribute", schema="portfolio")
    op.drop_table("profile", schema="content")
    op.drop_table("refresh_token", schema="auth")
    op.drop_table("tag", schema="portfolio")
    op.drop_table("project", schema="portfolio")
    op.drop_table("category", schema="portfolio")
    op.drop_table("media_asset", schema="media")
    op.drop_table("site_setting", schema="content")
    op.drop_table("service", schema="content")
    op.drop_table("contact_message", schema="contact")
    op.drop_table("app_user", schema="auth")
    op.execute("DROP FUNCTION public.set_updated_at()")
    op.execute("DROP SCHEMA contact")
    op.execute("DROP SCHEMA content")
    op.execute("DROP SCHEMA media")
    op.execute("DROP SCHEMA portfolio")
    op.execute("DROP SCHEMA auth")
