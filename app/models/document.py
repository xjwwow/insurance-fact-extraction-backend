from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.reference_data import build_document_label, get_business_line_label, get_company_label, get_report_type_label
from app.db.base import Base
from app.models.enums import ParseStatus
from app.models.mixins import TimestampMixin


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_line: Mapped[str | None] = mapped_column(String(32), index=True)
    report_year: Mapped[int] = mapped_column(nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ParseStatus.INGESTED.value,
    )

    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    tables = relationship("CanonicalTable", back_populates="document", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="document", cascade="all, delete-orphan")

    @property
    def company_label(self) -> str:
        return get_company_label(self.company_id)

    @property
    def report_type_label(self) -> str:
        return get_report_type_label(self.report_type)

    @property
    def business_line_label(self) -> str:
        return get_business_line_label(self.business_line)

    @property
    def document_label(self) -> str:
        return build_document_label(self.company_id, self.report_year, self.report_type)
