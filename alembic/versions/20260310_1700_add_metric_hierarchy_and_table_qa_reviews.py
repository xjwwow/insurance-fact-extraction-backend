"""add metric hierarchy and table qa reviews

Revision ID: 20260310_1700
Revises: 20260309_1500
Create Date: 2026-03-10 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260310_1700"
down_revision: str | None = "20260309_1500"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("metric_definitions", sa.Column("parent_canonical_metric_id", sa.String(length=64), nullable=True))
    op.add_column("metric_definitions", sa.Column("hierarchy_depth", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("metric_definitions", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_metric_definitions_parent_canonical_metric_id", "metric_definitions", ["parent_canonical_metric_id"], unique=False)
    op.create_foreign_key(
        "fk_metric_definitions_parent_canonical_metric_id",
        "metric_definitions",
        "metric_definitions",
        ["parent_canonical_metric_id"],
        ["canonical_metric_id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "metric_dependencies",
        sa.Column("dependency_id", sa.String(length=64), nullable=False),
        sa.Column("canonical_metric_id", sa.String(length=64), nullable=False),
        sa.Column("depends_on_metric_id", sa.String(length=64), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("expression_hint", sa.String(length=128), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_metric_id"], ["metric_definitions.canonical_metric_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_metric_id"], ["metric_definitions.canonical_metric_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dependency_id"),
    )
    op.create_index(op.f("ix_metric_dependencies_canonical_metric_id"), "metric_dependencies", ["canonical_metric_id"], unique=False)
    op.create_index(op.f("ix_metric_dependencies_depends_on_metric_id"), "metric_dependencies", ["depends_on_metric_id"], unique=False)

    op.create_table(
        "table_qa_reviews",
        sa.Column("qa_review_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("table_id", sa.String(length=64), nullable=False),
        sa.Column("manual_status", sa.String(length=32), nullable=True),
        sa.Column("manual_note", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["canonical_tables.table_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("qa_review_id"),
        sa.UniqueConstraint("table_id", name="uq_table_qa_reviews_table_id"),
    )
    op.create_index(op.f("ix_table_qa_reviews_document_id"), "table_qa_reviews", ["document_id"], unique=False)
    op.create_index(op.f("ix_table_qa_reviews_manual_status"), "table_qa_reviews", ["manual_status"], unique=False)
    op.create_index(op.f("ix_table_qa_reviews_table_id"), "table_qa_reviews", ["table_id"], unique=False)

    op.alter_column("metric_definitions", "hierarchy_depth", server_default=None)
    op.alter_column("metric_definitions", "sort_order", server_default=None)
    op.alter_column("metric_dependencies", "sort_order", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_table_qa_reviews_table_id"), table_name="table_qa_reviews")
    op.drop_index(op.f("ix_table_qa_reviews_manual_status"), table_name="table_qa_reviews")
    op.drop_index(op.f("ix_table_qa_reviews_document_id"), table_name="table_qa_reviews")
    op.drop_table("table_qa_reviews")

    op.drop_index(op.f("ix_metric_dependencies_depends_on_metric_id"), table_name="metric_dependencies")
    op.drop_index(op.f("ix_metric_dependencies_canonical_metric_id"), table_name="metric_dependencies")
    op.drop_table("metric_dependencies")

    op.drop_constraint("fk_metric_definitions_parent_canonical_metric_id", "metric_definitions", type_="foreignkey")
    op.drop_index("ix_metric_definitions_parent_canonical_metric_id", table_name="metric_definitions")
    op.drop_column("metric_definitions", "sort_order")
    op.drop_column("metric_definitions", "hierarchy_depth")
    op.drop_column("metric_definitions", "parent_canonical_metric_id")
