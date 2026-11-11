-- ============================================================
-- ARCHITECTURE PORTFOLIO
-- PostgreSQL
-- ============================================================

BEGIN;

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- SCHEMAS
-- ============================================================

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS portfolio;
CREATE SCHEMA IF NOT EXISTS media;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS contact;


-- ============================================================
-- FUNCTION: AUTO UPDATE updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


-- ============================================================
-- AUTH
-- ============================================================

CREATE TABLE auth.app_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email VARCHAR(320) NOT NULL,
    password_hash TEXT NOT NULL,

    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    last_login_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_app_user_email_not_empty
        CHECK (BTRIM(email) <> ''),

    CONSTRAINT ck_app_user_first_name_not_empty
        CHECK (BTRIM(first_name) <> ''),

    CONSTRAINT ck_app_user_last_name_not_empty
        CHECK (BTRIM(last_name) <> '')
);


-- Email case-insensitive único.
CREATE UNIQUE INDEX uq_app_user_email_lower
    ON auth.app_user (LOWER(email));


CREATE TABLE auth.refresh_token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL,

    token_hash VARCHAR(128) NOT NULL,

    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_refresh_token_user
        FOREIGN KEY (user_id)
        REFERENCES auth.app_user(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_refresh_token_hash
        UNIQUE (token_hash),

    CONSTRAINT ck_refresh_token_hash_not_empty
        CHECK (BTRIM(token_hash) <> ''),

    CONSTRAINT ck_refresh_token_dates
        CHECK (
            revoked_at IS NULL
            OR revoked_at >= created_at
        )
);


CREATE INDEX idx_refresh_token_user_id
    ON auth.refresh_token(user_id);

CREATE INDEX idx_refresh_token_expires_at
    ON auth.refresh_token(expires_at);

CREATE INDEX idx_refresh_token_active_user
    ON auth.refresh_token(user_id, expires_at)
    WHERE revoked_at IS NULL;


-- ============================================================
-- MEDIA
-- ============================================================

CREATE TABLE media.media_asset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    type VARCHAR(30) NOT NULL,

    original_filename VARCHAR(255) NOT NULL,

    storage_provider VARCHAR(50) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,

    url TEXT NOT NULL,
    thumbnail_url TEXT,

    mime_type VARCHAR(150) NOT NULL,

    file_size BIGINT NOT NULL,

    width INTEGER,
    height INTEGER,

    alt_text VARCHAR(255),
    title VARCHAR(255),
    description TEXT,

    metadata JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_media_asset_storage
        UNIQUE (storage_provider, storage_key),

    CONSTRAINT ck_media_asset_type
        CHECK (
            type IN (
                'IMAGE',
                'VIDEO',
                'PDF',
                'MODEL_3D',
                'DOCUMENT'
            )
        ),

    CONSTRAINT ck_media_asset_original_filename
        CHECK (BTRIM(original_filename) <> ''),

    CONSTRAINT ck_media_asset_storage_provider
        CHECK (BTRIM(storage_provider) <> ''),

    CONSTRAINT ck_media_asset_storage_key
        CHECK (BTRIM(storage_key) <> ''),

    CONSTRAINT ck_media_asset_url
        CHECK (BTRIM(url) <> ''),

    CONSTRAINT ck_media_asset_mime_type
        CHECK (BTRIM(mime_type) <> ''),

    CONSTRAINT ck_media_asset_file_size
        CHECK (file_size >= 0),

    CONSTRAINT ck_media_asset_width
        CHECK (
            width IS NULL
            OR width > 0
        ),

    CONSTRAINT ck_media_asset_height
        CHECK (
            height IS NULL
            OR height > 0
        ),

    CONSTRAINT ck_media_asset_metadata_object
        CHECK (
            metadata IS NULL
            OR jsonb_typeof(metadata) = 'object'
        )
);


CREATE INDEX idx_media_asset_type
    ON media.media_asset(type);

CREATE INDEX idx_media_asset_created_at
    ON media.media_asset(created_at DESC);


-- ============================================================
-- PORTFOLIO
-- ============================================================

CREATE TABLE portfolio.project (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    title VARCHAR(200) NOT NULL,
    slug VARCHAR(220) NOT NULL,

    short_description VARCHAR(500),
    description TEXT,

    location VARCHAR(255),

    year SMALLINT,
    area_m2 NUMERIC(12,2),

    client_name VARCHAR(200),

    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',

    visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',

    is_featured BOOLEAN NOT NULL DEFAULT FALSE,

    sort_order INTEGER NOT NULL DEFAULT 0,

    seo_title VARCHAR(200),
    seo_description VARCHAR(320),

    published_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    deleted_at TIMESTAMPTZ,

    CONSTRAINT ck_project_title_not_empty
        CHECK (BTRIM(title) <> ''),

    CONSTRAINT ck_project_slug_not_empty
        CHECK (BTRIM(slug) <> ''),

    CONSTRAINT ck_project_slug_format
        CHECK (
            slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        ),

    CONSTRAINT ck_project_year
        CHECK (
            year IS NULL
            OR year BETWEEN 1800 AND 2200
        ),

    CONSTRAINT ck_project_area
        CHECK (
            area_m2 IS NULL
            OR area_m2 > 0
        ),

    CONSTRAINT ck_project_status
        CHECK (
            status IN (
                'DRAFT',
                'PUBLISHED',
                'ARCHIVED'
            )
        ),

    CONSTRAINT ck_project_visibility
        CHECK (
            visibility IN (
                'PUBLIC',
                'PRIVATE',
                'UNLISTED'
            )
        ),

    CONSTRAINT ck_project_sort_order
        CHECK (sort_order >= 0),

    CONSTRAINT ck_project_deleted_at
        CHECK (
            deleted_at IS NULL
            OR deleted_at >= created_at
        )
);


-- Slug único únicamente entre proyectos no eliminados.
CREATE UNIQUE INDEX uq_project_slug_active
    ON portfolio.project(LOWER(slug))
    WHERE deleted_at IS NULL;


CREATE INDEX idx_project_status
    ON portfolio.project(status);

CREATE INDEX idx_project_visibility
    ON portfolio.project(visibility);

CREATE INDEX idx_project_published_at
    ON portfolio.project(published_at DESC);

CREATE UNIQUE INDEX uq_project_single_featured
    ON portfolio.project(is_featured)
    WHERE is_featured AND deleted_at IS NULL;

CREATE INDEX idx_project_featured
    ON portfolio.project(is_featured, sort_order);

CREATE INDEX idx_project_public_listing
    ON portfolio.project(status, visibility, sort_order)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_project_active
    ON portfolio.project(created_at DESC)
    WHERE deleted_at IS NULL;


-- ============================================================
-- CATEGORY
-- ============================================================

CREATE TABLE portfolio.category (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(100) NOT NULL,
    slug VARCHAR(120) NOT NULL,

    description TEXT,

    sort_order INTEGER NOT NULL DEFAULT 0,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_category_name_not_empty
        CHECK (BTRIM(name) <> ''),

    CONSTRAINT ck_category_slug_not_empty
        CHECK (BTRIM(slug) <> ''),

    CONSTRAINT ck_category_slug_format
        CHECK (
            slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        ),

    CONSTRAINT ck_category_sort_order
        CHECK (sort_order >= 0)
);


CREATE UNIQUE INDEX uq_category_slug_lower
    ON portfolio.category(LOWER(slug));

CREATE INDEX idx_category_active_order
    ON portfolio.category(is_active, sort_order);


-- ============================================================
-- PROJECT CATEGORY
-- ============================================================

CREATE TABLE portfolio.project_category (
    project_id UUID NOT NULL,
    category_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_project_category
        PRIMARY KEY (project_id, category_id),

    CONSTRAINT fk_project_category_project
        FOREIGN KEY (project_id)
        REFERENCES portfolio.project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_project_category_category
        FOREIGN KEY (category_id)
        REFERENCES portfolio.category(id)
        ON DELETE CASCADE
);


CREATE INDEX idx_project_category_category
    ON portfolio.project_category(category_id);


-- ============================================================
-- TAG
-- ============================================================

CREATE TABLE portfolio.tag (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(80) NOT NULL,
    slug VARCHAR(100) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_tag_name_not_empty
        CHECK (BTRIM(name) <> ''),

    CONSTRAINT ck_tag_slug_not_empty
        CHECK (BTRIM(slug) <> ''),

    CONSTRAINT ck_tag_slug_format
        CHECK (
            slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        )
);


CREATE UNIQUE INDEX uq_tag_name_lower
    ON portfolio.tag(LOWER(name));

CREATE UNIQUE INDEX uq_tag_slug_lower
    ON portfolio.tag(LOWER(slug));


-- ============================================================
-- PROJECT TAG
-- ============================================================

CREATE TABLE portfolio.project_tag (
    project_id UUID NOT NULL,
    tag_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_project_tag
        PRIMARY KEY (project_id, tag_id),

    CONSTRAINT fk_project_tag_project
        FOREIGN KEY (project_id)
        REFERENCES portfolio.project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_project_tag_tag
        FOREIGN KEY (tag_id)
        REFERENCES portfolio.tag(id)
        ON DELETE CASCADE
);


CREATE INDEX idx_project_tag_tag
    ON portfolio.project_tag(tag_id);


-- ============================================================
-- PROJECT ATTRIBUTE
-- ============================================================

CREATE TABLE portfolio.project_attribute (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL,

    label VARCHAR(100) NOT NULL,
    value VARCHAR(500) NOT NULL,

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_project_attribute_project
        FOREIGN KEY (project_id)
        REFERENCES portfolio.project(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_project_attribute_label
        CHECK (BTRIM(label) <> ''),

    CONSTRAINT ck_project_attribute_value
        CHECK (BTRIM(value) <> ''),

    CONSTRAINT ck_project_attribute_sort
        CHECK (sort_order >= 0)
);


CREATE INDEX idx_project_attribute_project_order
    ON portfolio.project_attribute(project_id, sort_order);


-- ============================================================
-- PROJECT MEDIA
-- ============================================================

CREATE TABLE portfolio.project_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL,
    media_id UUID NOT NULL,

    role VARCHAR(30) NOT NULL,

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_project_media_project
        FOREIGN KEY (project_id)
        REFERENCES portfolio.project(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_project_media_media
        FOREIGN KEY (media_id)
        REFERENCES media.media_asset(id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_project_media_role
        UNIQUE (project_id, media_id, role),

    CONSTRAINT ck_project_media_role
        CHECK (
            role IN (
                'COVER',
                'GALLERY',
                'PLAN',
                'RENDER',
                'DOCUMENT',
                'MODEL'
            )
        ),

    CONSTRAINT ck_project_media_sort
        CHECK (sort_order >= 0)
);


CREATE INDEX idx_project_media_project
    ON portfolio.project_media(project_id);

CREATE INDEX idx_project_media_media
    ON portfolio.project_media(media_id);

CREATE INDEX idx_project_media_order
    ON portfolio.project_media(project_id, sort_order);


-- Un proyecto solo puede tener una portada.
CREATE UNIQUE INDEX uq_project_single_cover
    ON portfolio.project_media(project_id)
    WHERE role = 'COVER';


-- ============================================================
-- PROJECT SECTION
-- ============================================================

CREATE TABLE portfolio.project_section (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL,

    title VARCHAR(200),

    content TEXT,

    section_type VARCHAR(30) NOT NULL,

    sort_order INTEGER NOT NULL DEFAULT 0,

    is_visible BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_project_section_project
        FOREIGN KEY (project_id)
        REFERENCES portfolio.project(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_project_section_type
        CHECK (
            section_type IN (
                'TEXT',
                'IMAGE',
                'GALLERY',
                'VIDEO',
                'MODEL_3D',
                'QUOTE',
                'SPLIT'
            )
        ),

    CONSTRAINT ck_project_section_sort
        CHECK (sort_order >= 0)
);


CREATE INDEX idx_project_section_project
    ON portfolio.project_section(project_id);

CREATE INDEX idx_project_section_project_order
    ON portfolio.project_section(project_id, sort_order);


-- ============================================================
-- PROJECT SECTION MEDIA
-- ============================================================

CREATE TABLE portfolio.project_section_media (
    section_id UUID NOT NULL,
    media_id UUID NOT NULL,

    sort_order INTEGER NOT NULL DEFAULT 0,

    caption VARCHAR(255),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_project_section_media
        PRIMARY KEY (section_id, media_id),

    CONSTRAINT fk_project_section_media_section
        FOREIGN KEY (section_id)
        REFERENCES portfolio.project_section(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_project_section_media_media
        FOREIGN KEY (media_id)
        REFERENCES media.media_asset(id)
        ON DELETE RESTRICT,

    CONSTRAINT ck_project_section_media_sort
        CHECK (sort_order >= 0)
);


CREATE INDEX idx_project_section_media_media
    ON portfolio.project_section_media(media_id);

CREATE INDEX idx_project_section_media_order
    ON portfolio.project_section_media(section_id, sort_order);


-- ============================================================
-- CONTENT
-- ============================================================

CREATE TABLE content.profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    professional_title VARCHAR(150),

    short_bio TEXT,
    biography TEXT,

    email VARCHAR(320),
    phone VARCHAR(50),

    location VARCHAR(200),

    profile_media_id UUID,
    cv_media_id UUID,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_profile_profile_media
        FOREIGN KEY (profile_media_id)
        REFERENCES media.media_asset(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_profile_cv_media
        FOREIGN KEY (cv_media_id)
        REFERENCES media.media_asset(id)
        ON DELETE SET NULL,

    CONSTRAINT ck_profile_first_name
        CHECK (BTRIM(first_name) <> ''),

    CONSTRAINT ck_profile_last_name
        CHECK (BTRIM(last_name) <> '')
);


CREATE INDEX idx_profile_profile_media
    ON content.profile(profile_media_id);

CREATE INDEX idx_profile_cv_media
    ON content.profile(cv_media_id);


-- Solo puede existir un perfil activo.
CREATE UNIQUE INDEX uq_profile_single_active
    ON content.profile ((1))
    WHERE is_active = TRUE;


-- ============================================================
-- SOCIAL LINK
-- ============================================================

CREATE TABLE content.social_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    profile_id UUID NOT NULL,

    platform VARCHAR(50) NOT NULL,

    url TEXT NOT NULL,

    username VARCHAR(100),

    sort_order INTEGER NOT NULL DEFAULT 0,

    is_visible BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_social_link_profile
        FOREIGN KEY (profile_id)
        REFERENCES content.profile(id)
        ON DELETE CASCADE,

    CONSTRAINT ck_social_link_platform
        CHECK (BTRIM(platform) <> ''),

    CONSTRAINT ck_social_link_url
        CHECK (BTRIM(url) <> ''),

    CONSTRAINT ck_social_link_sort
        CHECK (sort_order >= 0)
);


CREATE INDEX idx_social_link_profile
    ON content.social_link(profile_id);

CREATE INDEX idx_social_link_profile_order
    ON content.social_link(profile_id, sort_order);


-- Evita duplicar la misma plataforma en el mismo perfil.
CREATE UNIQUE INDEX uq_social_link_profile_platform
    ON content.social_link(profile_id, LOWER(platform));


-- ============================================================
-- SERVICE
-- ============================================================

CREATE TABLE content.service (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(150) NOT NULL,

    slug VARCHAR(170) NOT NULL,

    short_description VARCHAR(300),

    description TEXT,

    icon VARCHAR(100),

    sort_order INTEGER NOT NULL DEFAULT 0,

    is_visible BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_service_name
        CHECK (BTRIM(name) <> ''),

    CONSTRAINT ck_service_slug
        CHECK (BTRIM(slug) <> ''),

    CONSTRAINT ck_service_slug_format
        CHECK (
            slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        ),

    CONSTRAINT ck_service_sort
        CHECK (sort_order >= 0)
);


CREATE UNIQUE INDEX uq_service_slug_lower
    ON content.service(LOWER(slug));

CREATE INDEX idx_service_visible_order
    ON content.service(is_visible, sort_order);


-- ============================================================
-- SITE SETTING
-- ============================================================

CREATE TABLE content.site_setting (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    key VARCHAR(100) NOT NULL,

    value JSONB NOT NULL,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_site_setting_key
        UNIQUE (key),

    CONSTRAINT ck_site_setting_key
        CHECK (BTRIM(key) <> '')
);


-- ============================================================
-- CONTACT
-- ============================================================

CREATE TABLE contact.contact_message (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(150) NOT NULL,

    email VARCHAR(320) NOT NULL,

    phone VARCHAR(50),

    subject VARCHAR(200),

    message TEXT NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'NEW',

    ip_address INET,

    user_agent TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    read_at TIMESTAMPTZ,

    replied_at TIMESTAMPTZ,

    CONSTRAINT ck_contact_message_name
        CHECK (BTRIM(name) <> ''),

    CONSTRAINT ck_contact_message_email
        CHECK (BTRIM(email) <> ''),

    CONSTRAINT ck_contact_message_content
        CHECK (BTRIM(message) <> ''),

    CONSTRAINT ck_contact_message_status
        CHECK (
            status IN (
                'NEW',
                'READ',
                'REPLIED',
                'ARCHIVED',
                'SPAM'
            )
        ),

    CONSTRAINT ck_contact_message_read_date
        CHECK (
            read_at IS NULL
            OR read_at >= created_at
        ),

    CONSTRAINT ck_contact_message_reply_date
        CHECK (
            replied_at IS NULL
            OR replied_at >= created_at
        )
);


CREATE INDEX idx_contact_message_status
    ON contact.contact_message(status);

CREATE INDEX idx_contact_message_created
    ON contact.contact_message(created_at DESC);

CREATE INDEX idx_contact_message_inbox
    ON contact.contact_message(status, created_at DESC);


-- Optimiza específicamente mensajes pendientes.
CREATE INDEX idx_contact_message_new
    ON contact.contact_message(created_at DESC)
    WHERE status = 'NEW';


-- ============================================================
-- updated_at TRIGGERS
-- ============================================================

CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON auth.app_user
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_media_asset_updated_at
BEFORE UPDATE ON media.media_asset
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_project_updated_at
BEFORE UPDATE ON portfolio.project
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_category_updated_at
BEFORE UPDATE ON portfolio.category
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_project_attribute_updated_at
BEFORE UPDATE ON portfolio.project_attribute
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_project_section_updated_at
BEFORE UPDATE ON portfolio.project_section
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_profile_updated_at
BEFORE UPDATE ON content.profile
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_social_link_updated_at
BEFORE UPDATE ON content.social_link
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_service_updated_at
BEFORE UPDATE ON content.service
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


CREATE TRIGGER trg_site_setting_updated_at
BEFORE UPDATE ON content.site_setting
FOR EACH ROW
EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- COMMENTS
-- ============================================================

COMMENT ON SCHEMA auth IS
'Autenticación y sesiones administrativas.';

COMMENT ON SCHEMA portfolio IS
'Proyectos, categorías, etiquetas y estructura del portafolio.';

COMMENT ON SCHEMA media IS
'Gestión centralizada de archivos y recursos multimedia.';

COMMENT ON SCHEMA content IS
'Contenido general configurable del sitio web.';

COMMENT ON SCHEMA contact IS
'Mensajes recibidos desde formularios públicos.';


COMMENT ON TABLE portfolio.project IS
'Proyectos publicados o administrados dentro del portafolio.';

COMMENT ON TABLE media.media_asset IS
'Metadata de archivos almacenados en servicios externos como S3, R2 o Cloudinary.';

COMMENT ON TABLE portfolio.project_section IS
'Bloques dinámicos utilizados para construir la presentación narrativa de cada proyecto.';

COMMENT ON TABLE portfolio.project_attribute IS
'Atributos variables descriptivos de un proyecto, como arquitecto, fotógrafo o constructora.';

COMMENT ON TABLE content.site_setting IS
'Configuraciones dinámicas globales del sitio almacenadas como JSONB.';



CREATE TABLE media.storage_operation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_by UUID NOT NULL,
    storage_provider VARCHAR(50) NOT NULL,
    storage_key VARCHAR(500) NOT NULL,
    temporary_key VARCHAR(500),
    expected_metadata JSONB NOT NULL,
    media_id UUID,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_storage_operation_kind
        CHECK (kind IN ('UPLOAD', 'DELETE')),
    CONSTRAINT ck_storage_operation_status
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'CLEANUP_PENDING', 'CLEANED')),
    CONSTRAINT ck_storage_operation_identity
        CHECK (BTRIM(storage_provider) <> '' AND BTRIM(storage_key) <> ''),
    CONSTRAINT ck_storage_operation_metadata
        CHECK (jsonb_typeof(expected_metadata) = 'object')
);
CREATE UNIQUE INDEX uq_storage_operation_active
    ON media.storage_operation(storage_provider, storage_key)
    WHERE status IN ('PENDING', 'PROCESSING', 'CLEANUP_PENDING');
CREATE INDEX idx_storage_operation_cleanup
    ON media.storage_operation(status, expires_at);
CREATE INDEX idx_storage_operation_media
    ON media.storage_operation(media_id, kind);

COMMIT;