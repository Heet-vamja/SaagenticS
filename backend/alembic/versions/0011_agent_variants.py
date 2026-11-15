"""Agent variants, variant pages and owner delivery rules."""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("edge_sites", sa.Column("delivery_rules", sa.JSON(), nullable=True))
    op.create_table(
        "site_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "site_id",
            sa.Uuid(),
            sa.ForeignKey("edge_sites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("catalog", sa.JSON(), nullable=False),
        sa.Column("parity", sa.JSON(), nullable=False),
        sa.Column("evidence_summary", sa.JSON(), nullable=False),
        sa.Column("llms_txt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("site_id", "version", name="uq_site_variant_version"),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','REJECTED','SUPERSEDED')",
            name="site_variant_status_valid",
        ),
    )
    op.create_index("ix_site_variants_site_status", "site_variants", ["site_id", "status"])
    op.create_table(
        "variant_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "variant_id",
            sa.Uuid(),
            sa.ForeignKey("site_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.UniqueConstraint("variant_id", "path", name="uq_variant_page_path"),
    )


def downgrade():
    op.drop_table("variant_pages")
    op.drop_index("ix_site_variants_site_status", table_name="site_variants")
    op.drop_table("site_variants")
    op.drop_column("edge_sites", "delivery_rules")
