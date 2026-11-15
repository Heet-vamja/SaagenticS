"""Agent sessions (labels), request-to-session links and agent QA runs."""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("edge_sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("client_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("variant_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task", sa.String(160), nullable=True),
        sa.Column("outcome", sa.String(10), nullable=False, server_default="UNKNOWN"),
        sa.Column("failed_step", sa.String(300), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("label_source", sa.String(10), nullable=False, server_default="none"),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('SUCCEEDED','FAILED','UNKNOWN')", name="agent_session_outcome_valid"
        ),
    )
    op.create_index("ix_agent_sessions_site_started", "agent_sessions", ["site_id", "started_at"])
    op.add_column(
        "agent_requests",
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("agent_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_agent_requests_session_id", "agent_requests", ["session_id"])
    op.create_table(
        "qa_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("edge_sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("task_key", sa.String(60), nullable=False),
        sa.Column("task_prompt", sa.Text(), nullable=False),
        sa.Column("target", sa.String(10), nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("verification", sa.String(10), nullable=False, server_default="rules"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("detail", sa.String(300), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("target IN ('original','variant')", name="qa_run_target_valid"),
        sa.CheckConstraint("outcome IN ('PASSED','FAILED','ERROR')", name="qa_run_outcome_valid"),
    )
    op.create_index("ix_qa_runs_site_batch", "qa_runs", ["site_id", "batch_id"])


def downgrade():
    op.drop_index("ix_qa_runs_site_batch", table_name="qa_runs")
    op.drop_table("qa_runs")
    op.drop_index("ix_agent_requests_session_id", table_name="agent_requests")
    op.drop_column("agent_requests", "session_id")
    op.drop_index("ix_agent_sessions_site_started", table_name="agent_sessions")
    op.drop_table("agent_sessions")
