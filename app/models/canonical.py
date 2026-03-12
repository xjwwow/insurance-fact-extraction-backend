from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_no: Mapped[int] = mapped_column(nullable=False)
    page_image_path: Mapped[str | None] = mapped_column(Text)
    layout_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    document = relationship("Document", back_populates="pages")


class CanonicalTable(Base):
    __tablename__ = "canonical_tables"

    table_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_start: Mapped[int] = mapped_column(nullable=False)
    page_end: Mapped[int] = mapped_column(nullable=False)
    table_title_raw: Mapped[str | None] = mapped_column(Text)
    table_title_norm: Mapped[str | None] = mapped_column(Text)
    unit_raw: Mapped[str | None] = mapped_column(String(64))
    currency_raw: Mapped[str | None] = mapped_column(String(64))
    table_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    template_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    parse_engine: Mapped[str | None] = mapped_column(String(64))
    parse_confidence: Mapped[float | None] = mapped_column(Numeric(8, 4))
    parse_trace_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    document = relationship("Document", back_populates="tables")
    facts = relationship("Fact", back_populates="table")
