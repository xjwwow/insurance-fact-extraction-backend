from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class TableQAReview(TimestampMixin, Base):
    __tablename__ = "table_qa_reviews"
    __table_args__ = (UniqueConstraint("table_id", name="uq_table_qa_reviews_table_id"),)

    qa_review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("canonical_tables.table_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    manual_status: Mapped[str | None] = mapped_column(String(32), index=True)
    manual_note: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now())

    document = relationship("Document")
    table = relationship("CanonicalTable")
