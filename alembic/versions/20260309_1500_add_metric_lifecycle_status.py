"""add metric lifecycle status

Revision ID: 20260309_1500
Revises: 20260308_1300_add_metric_evidences
Create Date: 2026-03-09 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260309_1500"
down_revision: str | None = "20260308_1300"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "metric_definitions",
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.create_index(
        "ix_metric_definitions_lifecycle_status",
        "metric_definitions",
        ["lifecycle_status"],
        unique=False,
    )

    op.execute(
        """
        UPDATE metric_definitions
        SET lifecycle_status = 'candidate'
        WHERE metric_code LIKE 'LEARNED_%'
        """
    )
    op.execute(
        """
        UPDATE metric_aliases
        SET source = 'candidate_observed'
        WHERE source = 'document_learned'
        """
    )
    op.execute(
        """
        UPDATE metric_definitions
        SET lifecycle_status = 'dismissed', is_active = FALSE
        WHERE lower(metric_name) ~ '^(metric|value|row|col)_[0-9]+$'
        """
    )

    op.alter_column("metric_definitions", "lifecycle_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_metric_definitions_lifecycle_status", table_name="metric_definitions")
    op.drop_column("metric_definitions", "lifecycle_status")
