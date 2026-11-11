"""Enforce a single active featured project."""

from alembic import op

revision = "0003_single_featured"
down_revision = "0002_storage_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Retain the current public hero where possible, with deterministic tie breaks.
    op.execute("LOCK TABLE portfolio.project IN SHARE ROW EXCLUSIVE MODE")
    op.execute("""
        WITH ranked AS (
            SELECT id, row_number() OVER (
                ORDER BY (status = 'PUBLISHED' AND visibility = 'PUBLIC') DESC,
                         sort_order, published_at DESC NULLS LAST, slug, id
            ) AS position
            FROM portfolio.project WHERE is_featured AND deleted_at IS NULL
        )
        UPDATE portfolio.project SET is_featured = FALSE
        WHERE id IN (SELECT id FROM ranked WHERE position > 1)
           OR (is_featured AND deleted_at IS NOT NULL)
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_project_single_featured
        ON portfolio.project(is_featured)
        WHERE is_featured AND deleted_at IS NULL
    """)


def downgrade() -> None:
    # Previous multiple selections cannot be reconstructed.
    op.drop_index("uq_project_single_featured", table_name="project", schema="portfolio")
