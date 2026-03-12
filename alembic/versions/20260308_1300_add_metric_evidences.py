"""add_metric_evidences

Revision ID: 20260308_1300
Revises: 20260308_1100
Create Date: 2026-03-08 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260308_1300"
down_revision: Union[str, None] = "20260308_1100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metric_evidences",
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("canonical_metric_id", sa.String(length=64), nullable=False),
        sa.Column("alias_id", sa.String(length=64), nullable=True),
        sa.Column("fact_id", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("document_id", sa.String(length=64), nullable=True),
        sa.Column("source_table_id", sa.String(length=64), nullable=True),
        sa.Column("source_page_no", sa.Integer(), nullable=True),
        sa.Column("raw_metric_text", sa.Text(), nullable=False),
        sa.Column("normalized_metric_text", sa.Text(), nullable=False),
        sa.Column("statement_scope", sa.String(length=64), nullable=True),
        sa.Column("period_type", sa.String(length=16), nullable=True),
        sa.Column("unit_std", sa.String(length=64), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["alias_id"], ["metric_aliases.alias_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["canonical_metric_id"], ["metric_definitions.canonical_metric_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fact_id"], ["facts.fact_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_table_id"], ["canonical_tables.table_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("fact_id"),
    )
    op.create_index(op.f("ix_metric_evidences_alias_id"), "metric_evidences", ["alias_id"], unique=False)
    op.create_index(op.f("ix_metric_evidences_canonical_metric_id"), "metric_evidences", ["canonical_metric_id"], unique=False)
    op.create_index(op.f("ix_metric_evidences_company_id"), "metric_evidences", ["company_id"], unique=False)
    op.create_index(op.f("ix_metric_evidences_document_id"), "metric_evidences", ["document_id"], unique=False)
    op.create_index(op.f("ix_metric_evidences_fact_id"), "metric_evidences", ["fact_id"], unique=False)
    op.create_index(op.f("ix_metric_evidences_normalized_metric_text"), "metric_evidences", ["normalized_metric_text"], unique=False)
    op.create_index(op.f("ix_metric_evidences_source_page_no"), "metric_evidences", ["source_page_no"], unique=False)
    op.create_index(op.f("ix_metric_evidences_source_table_id"), "metric_evidences", ["source_table_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_metric_evidences_source_table_id"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_source_page_no"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_normalized_metric_text"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_fact_id"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_document_id"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_company_id"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_canonical_metric_id"), table_name="metric_evidences")
    op.drop_index(op.f("ix_metric_evidences_alias_id"), table_name="metric_evidences")
    op.drop_table("metric_evidences")
