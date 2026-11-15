"""Tag local development sessions so disabling the shortcut invalidates them."""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "website_verifications",
        sa.Column("verification_method", sa.String(20), nullable=False, server_default="EMAIL_OTP"),
    )


def downgrade():
    # Never turn a development session into an ordinary verified session by
    # losing its method tag during a rollback/reapply.
    op.execute(
        "UPDATE website_verifications SET session_digest = NULL, session_expires_at = NULL, verified_at = NULL WHERE verification_method IN ('DEV_SHORTCUT', 'DEV_EMAIL_OTP')"
    )
    op.drop_column("website_verifications", "verification_method")
