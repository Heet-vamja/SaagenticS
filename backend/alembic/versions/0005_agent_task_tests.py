"""Persist agent task aggregates, run metadata, usage, and admission buckets."""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

FAILURE_CATEGORIES = (
    "'element_not_found','blocked_by_captcha_or_bot_protection','content_requires_js',"
    "'ambiguous_navigation','step_limit','loop','malformed_output','infra_error','other'"
)


def upgrade():
    op.create_table(
        "agent_task_tests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "scan_id", sa.Uuid(), sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("requested_runs", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(9), nullable=False, server_default="PENDING"),
        sa.Column("outcome", sa.String(20)),
        sa.Column("consistency", sa.Boolean()),
        sa.Column("eligible_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("runs_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("failure_reason", sa.Text()),
        sa.CheckConstraint("length(task_type) <= 40", name="agent_task_type_length"),
        sa.CheckConstraint(
            "requested_runs BETWEEN 1 AND 3", name="agent_task_requested_runs_bounds"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETED','FAILED')", name="agent_task_status"
        ),
        sa.CheckConstraint(
            "eligible_runs >= 0 AND runs_completed >= 0", name="agent_task_run_counts_nonnegative"
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('SUCCEEDED','FAILED','INCONCLUSIVE','UNAVAILABLE')",
            name="agent_task_outcome_valid",
        ),
        sa.CheckConstraint(
            "eligible_runs <= runs_completed", name="agent_task_eligible_runs_lte_completed"
        ),
        sa.CheckConstraint(
            "runs_completed <= requested_runs", name="agent_task_completed_runs_lte_requested"
        ),
        sa.UniqueConstraint("id", "scan_id", name="uq_agent_task_test_id_scan"),
    )
    op.create_index("ix_agent_task_tests_scan_id", "agent_task_tests", ["scan_id"])
    op.create_index("ix_agent_task_tests_scan_status", "agent_task_tests", ["scan_id", "status"])
    op.create_index(
        "ix_agent_task_tests_scan_created_at", "agent_task_tests", ["scan_id", "created_at"]
    )

    op.add_column("workflow_tests", sa.Column("task_test_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_workflow_task_scan",
        "workflow_tests",
        "agent_task_tests",
        ["task_test_id", "scan_id"],
        ["id", "scan_id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "workflow_tests", sa.Column("run_number", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("workflow_tests", sa.Column("outcome", sa.String(20)))
    op.add_column(
        "workflow_tests",
        sa.Column(
            "verification_method", sa.String(12), nullable=False, server_default="unverified"
        ),
    )
    op.add_column(
        "workflow_tests",
        sa.Column("verification_evidence", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("workflow_tests", sa.Column("failure_category", sa.String(50)))
    op.add_column(
        "workflow_tests",
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "workflow_tests",
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("workflow_tests", sa.Column("estimated_cost_usd", sa.Float()))
    op.create_check_constraint("workflow_run_number_positive", "workflow_tests", "run_number >= 1")
    op.create_check_constraint(
        "workflow_tokens_nonnegative",
        "workflow_tests",
        "prompt_tokens >= 0 AND completion_tokens >= 0",
    )
    op.create_check_constraint(
        "workflow_cost_nonnegative",
        "workflow_tests",
        "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
    )
    op.create_check_constraint(
        "workflow_outcome_valid",
        "workflow_tests",
        "outcome IS NULL OR outcome IN ('SUCCEEDED','FAILED','INCONCLUSIVE','UNAVAILABLE')",
    )
    op.create_check_constraint(
        "workflow_verification_method_valid",
        "workflow_tests",
        "verification_method IN ('rules','judged','unverified')",
    )
    op.create_check_constraint(
        "workflow_failure_category_valid",
        "workflow_tests",
        f"failure_category IS NULL OR failure_category IN ({FAILURE_CATEGORIES})",
    )
    op.create_unique_constraint(
        "uq_workflow_task_run_number", "workflow_tests", ["task_test_id", "run_number"]
    )
    op.create_index("ix_workflow_tests_task_test_id", "workflow_tests", ["task_test_id"])

    op.add_column(
        "agent_steps", sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "agent_steps",
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_steps", sa.Column("llm_latency_ms", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("agent_steps", sa.Column("error_category", sa.String(50)))
    op.create_check_constraint(
        "agent_step_usage_nonnegative",
        "agent_steps",
        "prompt_tokens >= 0 AND completion_tokens >= 0 AND llm_latency_ms >= 0",
    )
    op.create_check_constraint(
        "agent_step_error_category_valid",
        "agent_steps",
        f"error_category IS NULL OR error_category IN ({FAILURE_CATEGORIES})",
    )

    op.create_table(
        "admission_buckets",
        sa.Column("bucket_key", sa.String(128), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("count >= 0", name="admission_bucket_count_nonnegative"),
    )
    op.create_index("ix_admission_buckets_expires_at", "admission_buckets", ["expires_at"])


def downgrade():
    op.drop_index("ix_admission_buckets_expires_at", "admission_buckets")
    op.drop_table("admission_buckets")
    op.drop_constraint("agent_step_error_category_valid", "agent_steps", type_="check")
    op.drop_constraint("agent_step_usage_nonnegative", "agent_steps", type_="check")
    for column in ("error_category", "llm_latency_ms", "completion_tokens", "prompt_tokens"):
        op.drop_column("agent_steps", column)
    op.drop_index("ix_workflow_tests_task_test_id", "workflow_tests")
    op.drop_constraint("uq_workflow_task_run_number", "workflow_tests", type_="unique")
    for name in (
        "workflow_failure_category_valid",
        "workflow_verification_method_valid",
        "workflow_outcome_valid",
        "workflow_cost_nonnegative",
        "workflow_tokens_nonnegative",
        "workflow_run_number_positive",
    ):
        op.drop_constraint(name, "workflow_tests", type_="check")
    op.drop_constraint("fk_workflow_task_scan", "workflow_tests", type_="foreignkey")
    for column in (
        "estimated_cost_usd",
        "completion_tokens",
        "prompt_tokens",
        "failure_category",
        "verification_evidence",
        "verification_method",
        "outcome",
        "run_number",
        "task_test_id",
    ):
        op.drop_column("workflow_tests", column)
    for name in (
        "ix_agent_task_tests_scan_created_at",
        "ix_agent_task_tests_scan_status",
        "ix_agent_task_tests_scan_id",
    ):
        op.drop_index(name, "agent_task_tests")
    op.drop_constraint("uq_agent_task_test_id_scan", "agent_task_tests", type_="unique")
    op.drop_table("agent_task_tests")
