"""initial domain schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="project_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                name="scan_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "completed_at IS NULL OR (started_at IS NOT NULL AND completed_at >= started_at)",
            name="scan_time_order",
        ),
        sa.CheckConstraint("overall_score BETWEEN 0 AND 100", name="scan_score_range"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_project_status", "scans", ["project_id", "status"], unique=False)
    op.create_table(
        "pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.CheckConstraint("status_code BETWEEN 100 AND 599", name="page_http_status"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "scan_id", name="uq_page_id_scan"),
        sa.UniqueConstraint("scan_id", "url", name="uq_page_scan_url"),
    )
    op.create_index(op.f("ix_pages_scan_id"), "pages", ["scan_id"], unique=False)
    op.create_table(
        "workflow_tests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=300), nullable=False),
        sa.Column("starting_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "PASSED",
                "FAILED",
                name="workflow_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("evidence_location", sa.Text(), nullable=True),
        sa.Column("execution_duration", sa.Float(), nullable=True),
        sa.CheckConstraint("execution_duration >= 0", name="workflow_duration_nonnegative"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_tests_scan_id"), "workflow_tests", ["scan_id"], unique=False)
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("page_id", sa.Uuid(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "DISCOVERABILITY",
                "UNDERSTANDABILITY",
                "NAVIGABILITY",
                "INTERACTABILITY",
                "RELIABILITY",
                name="finding_category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "INFO",
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="finding_severity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="finding_confidence_range"),
        sa.ForeignKeyConstraint(
            ["page_id", "scan_id"],
            ["pages.id", "pages.scan_id"],
            name="fk_finding_page_scan",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_findings_page_id"), "findings", ["page_id"], unique=False)
    op.create_index("ix_findings_scan_category", "findings", ["scan_id", "category"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_findings_scan_category", table_name="findings")
    op.drop_index(op.f("ix_findings_page_id"), table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_workflow_tests_scan_id"), table_name="workflow_tests")
    op.drop_table("workflow_tests")
    op.drop_index(op.f("ix_pages_scan_id"), table_name="pages")
    op.drop_table("pages")
    op.drop_index("ix_scans_project_status", table_name="scans")
    op.drop_table("scans")
    op.drop_table("projects")
