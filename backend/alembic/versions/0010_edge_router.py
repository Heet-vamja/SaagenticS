"""Edge router sites and agent request log."""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "edge_sites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("origin_url", sa.String(2048), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("routing_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("host", name="edge_sites_host_key"),
    )
    op.create_table(
        "agent_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "site_id",
            sa.Uuid(),
            sa.ForeignKey("edge_sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("agent_kind", sa.String(10), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(2048), nullable=False),
        sa.Column("action", sa.String(80), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("served_by", sa.String(10), nullable=False),
        sa.Column("response_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_hash", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(300), nullable=False),
        sa.CheckConstraint("agent_kind IN ('agent','crawler')", name="agent_request_kind_valid"),
        sa.CheckConstraint(
            "served_by IN ('origin','variant','router')", name="agent_request_served_valid"
        ),
    )
    op.create_index("ix_agent_requests_site_received", "agent_requests", ["site_id", "received_at"])
    op.create_index("ix_agent_requests_site_agent", "agent_requests", ["site_id", "agent"])


def downgrade():
    op.drop_index("ix_agent_requests_site_agent", table_name="agent_requests")
    op.drop_index("ix_agent_requests_site_received", table_name="agent_requests")
    op.drop_table("agent_requests")
    op.drop_table("edge_sites")
