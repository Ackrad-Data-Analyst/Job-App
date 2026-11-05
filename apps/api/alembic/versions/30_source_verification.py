"""Persist owner-requested official employer page checks."""

import sqlalchemy as sa
from alembic import op

revision = "30_source_verification"
down_revision = "20_private_postgres"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_verifications",
        sa.Column("catalog_key", sa.String(160), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("final_url", sa.String(2048), nullable=False),
        sa.Column("page_title", sa.String(300), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("feed_ids", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("catalog_key"),
    )
    for name, kind, default in [
        ("published_at", sa.String(160), ""),
        ("published_at_kind", sa.String(30), "unknown"),
        ("published_at_evidence", sa.Text(), ""),
        ("applicant_metric", sa.String(30), "unknown"),
        ("applicant_count_relation", sa.String(30), "exact"),
        ("applicant_count_evidence", sa.Text(), ""),
    ]:
        op.add_column("vacancies", sa.Column(name, kind, nullable=False, server_default=default))
    op.add_column("vacancies", sa.Column("applicant_count", sa.Integer(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE source_verifications ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON TABLE source_verifications FROM PUBLIC")
        roles = set(op.get_bind().exec_driver_sql("SELECT rolname FROM pg_roles").scalars())
        for role in ["anon", "authenticated"]:
            if role in roles:
                op.execute(f'REVOKE ALL ON TABLE source_verifications FROM "{role}"')


def downgrade():
    for name in [
        "published_at",
        "published_at_kind",
        "published_at_evidence",
        "applicant_count",
        "applicant_metric",
        "applicant_count_relation",
        "applicant_count_evidence",
    ]:
        op.drop_column("vacancies", name)
    op.drop_table("source_verifications")
