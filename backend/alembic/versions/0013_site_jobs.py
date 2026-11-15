"""Dashboard-started site jobs: variant builds, session labeling and agent QA."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("edge_sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("detail", sa.String(300), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('build_variant','label_sessions','run_qa')", name="site_job_kind_valid"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')", name="site_job_status_valid"
        ),
    )
    op.create_index("ix_site_jobs_site_created", "site_jobs", ["site_id", "created_at"])
    op.create_index("ix_site_jobs_status_created", "site_jobs", ["status", "created_at"])
    op.create_index(
        "uq_site_jobs_active",
        "site_jobs",
        ["site_id", "kind"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING','RUNNING')"),
    )


def downgrade():
    op.drop_index("uq_site_jobs_active", table_name="site_jobs")
    op.drop_index("ix_site_jobs_status_created", table_name="site_jobs")
    op.drop_index("ix_site_jobs_site_created", table_name="site_jobs")
    op.drop_table("site_jobs")
