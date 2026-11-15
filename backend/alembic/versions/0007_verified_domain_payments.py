"""Verified mailbox sessions and one-time domain report purchases."""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "website_verifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("website_url", sa.String(2048), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column("discovered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("otp_digest", sa.String(64)),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("session_digest", sa.String(64), unique=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    for field in ("domain", "identity_hash"):
        op.create_index(f"ix_website_verifications_{field}", "website_verifications", [field])
    op.create_table(
        "domain_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "verification_id", sa.Uuid(), sa.ForeignKey("website_verifications.id"), nullable=False
        ),
        sa.Column("share_id", sa.Uuid(), sa.ForeignKey("report_shares.id"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("checkout_session_id", sa.String(255), unique=True),
        sa.Column("payment_intent_id", sa.String(255), unique=True),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="1900"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("rescan_until", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    for field in ("verification_id", "share_id", "domain"):
        op.create_index(f"ix_domain_orders_{field}", "domain_orders", [field])
    op.create_table(
        "payment_events",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("payment_intent_id", sa.String(255)),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_payment_events_payment_intent_id", "payment_events", ["payment_intent_id"])
    for field, target, name in (
        ("verification_id", "website_verifications.id", "fk_report_share_verification"),
        ("domain_order_id", "domain_orders.id", "fk_report_share_order"),
    ):
        op.add_column("report_shares", sa.Column(field, sa.Uuid(), nullable=True))
        table, column = target.split(".")
        op.create_foreign_key(name, "report_shares", table, [field], [column])
        op.create_index(f"ix_report_shares_{field}", "report_shares", [field])


def downgrade():
    for field, name in (
        ("domain_order_id", "fk_report_share_order"),
        ("verification_id", "fk_report_share_verification"),
    ):
        op.drop_index(f"ix_report_shares_{field}", table_name="report_shares")
        op.drop_constraint(name, "report_shares", type_="foreignkey")
        op.drop_column("report_shares", field)
    op.drop_table("payment_events")
    op.drop_table("domain_orders")
    op.drop_table("website_verifications")
