"""add_business_line_to_documents

Revision ID: 20260308_1100
Revises: 63851bd8742e
Create Date: 2026-03-08 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260308_1100"
down_revision: Union[str, None] = "63851bd8742e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("business_line", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_documents_business_line"), "documents", ["business_line"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_documents_business_line"), table_name="documents")
    op.drop_column("documents", "business_line")
