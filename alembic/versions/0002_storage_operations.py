"""Add durable storage intents without changing the original domain tables."""

from alembic import op

revision = "0002_storage_operations"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

SQL = """
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
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED',
                         'CLEANUP_PENDING', 'CLEANED')),
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
"""


def upgrade() -> None:
    op.execute(SQL)


def downgrade() -> None:
    # Refuse to lose unresolved remote intents; reconcile before downgrading.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM media.storage_operation
                   WHERE status IN ('PENDING', 'PROCESSING', 'CLEANUP_PENDING')
                      OR temporary_key IS NOT NULL) THEN
            RAISE EXCEPTION 'Reconcile storage operations before downgrade';
        END IF;
    END $$""")
    op.drop_table("storage_operation", schema="media")
