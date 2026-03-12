from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ReviewStatus, ValidationStatus
from app.models.mixins import TimestampMixin


class Fact(TimestampMixin, Base):
    __tablename__ = "facts"

    fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_year: Mapped[int] = mapped_column(nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    statement_scope: Mapped[str | None] = mapped_column(String(64))
    canonical_metric_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="SET NULL"),
        index=True,
    )
    metric_name_std: Mapped[str | None] = mapped_column(String(256))
    metric_alias_raw: Mapped[str | None] = mapped_column(Text)
    value_raw: Mapped[str | None] = mapped_column(Text)
    value_numeric: Mapped[float | None] = mapped_column(Numeric(28, 8))
    unit_raw: Mapped[str | None] = mapped_column(String(64))
    unit_std: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(32))
    dimensions_json: Mapped[dict | None] = mapped_column(JSONB)
    source_page_no: Mapped[int | None] = mapped_column()
    source_table_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("canonical_tables.table_id", ondelete="SET NULL"),
    )
    source_row_path: Mapped[dict | None] = mapped_column(JSONB)
    source_col_path: Mapped[dict | None] = mapped_column(JSONB)
    source_cell_bbox: Mapped[dict | None] = mapped_column(JSONB)
    source_text_snippet: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(64))
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(8, 4))
    validation_score: Mapped[float | None] = mapped_column(Numeric(8, 4))
    validation_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ValidationStatus.REVIEW.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ReviewStatus.PENDING.value,
        index=True,
    )
    reviewer_comment: Mapped[str | None] = mapped_column(Text)

    document = relationship("Document", back_populates="facts")
    metric = relationship("MetricDefinition", back_populates="facts")
    table = relationship("CanonicalTable", back_populates="facts")
    metric_evidence = relationship("MetricEvidence", back_populates="fact", uselist=False, cascade="all, delete-orphan")
    review_logs = relationship("ReviewLog", back_populates="fact", cascade="all, delete-orphan")

    @property
    def metric_lifecycle_status(self) -> str | None:
        if isinstance(self.dimensions_json, dict):
            value = self.dimensions_json.get("metric_lifecycle_status")
            if isinstance(value, str):
                return value
        return None

    @property
    def period_label(self) -> str | None:
        if isinstance(self.dimensions_json, dict):
            label = self.dimensions_json.get("period_label")
            if isinstance(label, str) and label:
                return label
        if isinstance(self.source_col_path, dict):
            path = self.source_col_path.get("path", [])
            if isinstance(path, list) and path:
                return " / ".join(str(item) for item in path if item)
        return None

    @property
    def availability_status(self) -> str:
        if self.review_status == ReviewStatus.REJECTED.value:
            return "REJECTED"
        if self.review_status == ReviewStatus.CORRECTED.value:
            return "MANUAL_CONFIRMED"
        if self.review_status == ReviewStatus.REMAPPED.value:
            return "NEEDS_RECHECK"
        if (
            self.review_status == ReviewStatus.APPROVED.value
            and self.validation_status == ValidationStatus.PASS.value
            and bool(self.canonical_metric_id)
            and self.metric_lifecycle_status == "active"
        ):
            return "AUTO_READY"
        return "PENDING_REVIEW"

    @property
    def availability_label(self) -> str:
        labels = {
            "AUTO_READY": "自动可用",
            "PENDING_REVIEW": "待审核",
            "MANUAL_CONFIRMED": "人工确认可用",
            "NEEDS_RECHECK": "待复核",
            "REJECTED": "已驳回",
        }
        return labels.get(self.availability_status, self.availability_status)

    @property
    def viewer_url(self) -> str:
        params = [f"page={self.source_page_no or 1}"]
        if self.source_table_id:
            params.append(f"table_id={self.source_table_id}")
        params.append(f"fact_id={self.fact_id}")
        return f"/documents/{self.document_id}/viewer?{'&'.join(params)}"
