"""Real browser agent executions and bounded step traces.
Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("workflow_status", "workflow_tests", type_="check")
    op.alter_column("workflow_tests", "status", existing_type=sa.String(7), type_=sa.String(9))
    op.create_check_constraint(
        "workflow_status",
        "workflow_tests",
        "status IN ('PENDING','RUNNING','PASSED','FAILED','COMPLETED')",
    )
    for name, length in (("task_type", 40), ("model_identifier", 200), ("final_url", 2048)):
        op.add_column("workflow_tests", sa.Column(name, sa.String(length), nullable=True))
    for name in ("task_description", "agent_declared_outcome"):
        op.add_column("workflow_tests", sa.Column(name, sa.Text(), nullable=True))
    for name in ("started_at", "completed_at", "execution_deadline"):
        op.add_column("workflow_tests", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "workflow_tests",
        sa.Column("allowed_domains", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "workflow_tests",
        sa.Column("steps_completed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "workflow_tests", sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workflow_test_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_tests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("page_url", sa.String(2048), nullable=False),
        sa.Column("observation_summary", sa.JSON(), nullable=False),
        sa.Column("action_type", sa.String(40), nullable=False),
        sa.Column("action_arguments", sa.JSON(), nullable=False),
        sa.Column("reasoning_summary", sa.String(300), nullable=False),
        sa.Column("action_result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workflow_test_id", "step_number", name="uq_agent_step_number"),
        sa.CheckConstraint("step_number >= 1 AND duration_ms >= 0", name="agent_step_bounds"),
    )
    op.create_index("ix_agent_steps_workflow_test_id", "agent_steps", ["workflow_test_id"])


def downgrade():
    op.drop_table("agent_steps")
    for name in (
        "task_type",
        "model_identifier",
        "final_url",
        "task_description",
        "agent_declared_outcome",
        "started_at",
        "completed_at",
        "execution_deadline",
        "allowed_domains",
        "steps_completed",
        "metrics",
    ):
        op.drop_column("workflow_tests", name)
    op.execute("UPDATE workflow_tests SET status = 'FAILED' WHERE status = 'COMPLETED'")
    op.drop_constraint("workflow_status", "workflow_tests", type_="check")
    op.alter_column("workflow_tests", "status", existing_type=sa.String(9), type_=sa.String(7))
    op.create_check_constraint(
        "workflow_status", "workflow_tests", "status IN ('PENDING','RUNNING','PASSED','FAILED')"
    )
