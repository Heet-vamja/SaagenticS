"""Agent lane early-access requests from the landing page."""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "early_access_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("website_url", sa.String(2048), nullable=False),
        sa.Column("identity_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("email", "domain", name="uq_early_access_email_domain"),
    )
    op.create_index("ix_early_access_requests_domain", "early_access_requests", ["domain"])


def downgrade():
    op.drop_index("ix_early_access_requests_domain", table_name="early_access_requests")
    op.drop_table("early_access_requests")
