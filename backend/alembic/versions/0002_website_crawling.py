"""Website crawler progress and page metadata.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "scans", sa.Column("execution_deadline", sa.DateTime(timezone=True), nullable=True)
    )
    for name in ("pages_discovered", "pages_crawled", "pages_failed"):
        op.add_column("scans", sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
    op.add_column("scans", sa.Column("error_summary", sa.Text(), nullable=True))
    op.add_column(
        "scans", sa.Column("crawl_metadata", sa.JSON(), nullable=False, server_default="{}")
    )
    for name in ("meta_description", "crawl_error"):
        op.add_column("pages", sa.Column(name, sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("canonical_url", sa.String(2048), nullable=True))
    op.add_column("pages", sa.Column("content_type", sa.String(255), nullable=True))
    op.add_column(
        "pages", sa.Column("crawl_depth", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade():
    op.drop_column("scans", "execution_deadline")
    for name in ("crawl_depth", "content_type", "canonical_url", "crawl_error", "meta_description"):
        op.drop_column("pages", name)
    for name in (
        "crawl_metadata",
        "error_summary",
        "pages_failed",
        "pages_crawled",
        "pages_discovered",
    ):
        op.drop_column("scans", name)
