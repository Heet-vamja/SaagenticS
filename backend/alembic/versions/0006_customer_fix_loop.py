"""Capability-scoped fix interactions and explicit rescan baseline."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("report_shares", sa.Column("baseline_scan_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_report_share_baseline",
        "report_shares",
        "scans",
        ["baseline_scan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "report_fix_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "share_id",
            sa.Uuid(),
            sa.ForeignKey("report_shares.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fix_key", sa.String(64), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("share_id", "fix_key", "event_type", name="uq_report_fix_event"),
        sa.CheckConstraint(
            "event_type IN ('PROMPT_COPIED','ASSET_DOWNLOADED','FIX_APPLIED',"
            "'USEFUL','NOT_USEFUL','PRICE_INTERESTED','PRICE_NOT_INTERESTED','PACK_DOWNLOADED')",
            name="report_fix_event_type",
        ),
    )
    op.create_index("ix_report_fix_events_share_id", "report_fix_events", ["share_id"])


def downgrade():
    op.drop_index("ix_report_fix_events_share_id", table_name="report_fix_events")
    op.drop_table("report_fix_events")
    op.drop_constraint("fk_report_share_baseline", "report_shares", type_="foreignkey")
    op.drop_column("report_shares", "baseline_scan_id")
