"""Separate explicit development report skips from real Stripe entitlements."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "report_shares",
        sa.Column("development_unlocked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "domain_orders", sa.Column("livemode", sa.Boolean(), nullable=False, server_default="false")
    )


def downgrade():
    op.drop_column("domain_orders", "livemode")
    op.drop_column("report_shares", "development_unlocked")
