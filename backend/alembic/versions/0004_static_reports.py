"""Deterministic audit summaries, queue timestamps and revocable report shares."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "scans",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.execute("UPDATE scans SET created_at = started_at WHERE started_at IS NOT NULL")
    op.add_column(
        "scans", sa.Column("audit_summary", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_index("ix_scans_status_created_at", "scans", ["status", "created_at"])
    op.create_table(
        "report_shares",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "scan_id", sa.Uuid(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_report_shares_scan_id", "report_shares", ["scan_id"])


def downgrade():
    op.drop_table("report_shares")
    op.drop_index("ix_scans_status_created_at", "scans")
    op.drop_column("scans", "audit_summary")
    op.drop_column("scans", "created_at")
