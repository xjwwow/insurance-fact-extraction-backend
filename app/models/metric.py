from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.reference_data import (
    METRIC_LIFECYCLE_ACTIVE,
    build_document_label,
    get_report_type_label,
)
from app.db.base import Base
from app.models.mixins import TimestampMixin


class MetricDefinition(TimestampMixin, Base):
    __tablename__ = "metric_definitions"

    canonical_metric_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    metric_name: Mapped[str] = mapped_column(String(256), nullable=False)
    metric_name_en: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(128))
    subcategory: Mapped[str | None] = mapped_column(String(128))
    definition: Mapped[str | None] = mapped_column(Text)
    formula_expression: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str | None] = mapped_column(String(32))
    default_unit: Mapped[str | None] = mapped_column(String(64))
    parent_canonical_metric_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="SET NULL"),
        index=True,
    )
    hierarchy_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applicable_scope: Mapped[dict | None] = mapped_column(JSONB)
    applicable_statement_types: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default=METRIC_LIFECYCLE_ACTIVE, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    parent = relationship("MetricDefinition", remote_side=[canonical_metric_id], back_populates="children")
    children = relationship("MetricDefinition", back_populates="parent")
    aliases = relationship("MetricAlias", back_populates="metric", cascade="all, delete-orphan")
    evidences = relationship("MetricEvidence", back_populates="metric", cascade="all, delete-orphan")
    dependencies = relationship(
        "MetricDependency",
        back_populates="metric",
        cascade="all, delete-orphan",
        foreign_keys="MetricDependency.canonical_metric_id",
    )
    dependents = relationship(
        "MetricDependency",
        back_populates="depends_on_metric",
        cascade="all, delete-orphan",
        foreign_keys="MetricDependency.depends_on_metric_id",
    )
    facts = relationship("Fact", back_populates="metric")


class MetricAlias(Base):
    __tablename__ = "metric_aliases"

    alias_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_metric_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    alias_lang: Mapped[str | None] = mapped_column(String(16))
    company_id: Mapped[str | None] = mapped_column(String(64), index=True)
    report_type: Mapped[str | None] = mapped_column(String(32))
    valid_from_year: Mapped[int | None] = mapped_column(Integer)
    valid_to_year: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(8, 4))
    source: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    metric = relationship("MetricDefinition", back_populates="aliases")
    evidences = relationship("MetricEvidence", back_populates="alias")


class MetricEvidence(Base):
    __tablename__ = "metric_evidences"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_metric_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("metric_aliases.alias_id", ondelete="SET NULL"),
        index=True,
    )
    fact_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("facts.fact_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_id: Mapped[str | None] = mapped_column(String(64), index=True)
    document_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        index=True,
    )
    source_table_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("canonical_tables.table_id", ondelete="SET NULL"),
        index=True,
    )
    source_page_no: Mapped[int | None] = mapped_column(index=True)
    raw_metric_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_metric_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    statement_scope: Mapped[str | None] = mapped_column(String(64))
    period_type: Mapped[str | None] = mapped_column(String(16))
    unit_std: Mapped[str | None] = mapped_column(String(64))
    evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    metric = relationship("MetricDefinition", back_populates="evidences")
    alias = relationship("MetricAlias", back_populates="evidences")
    fact = relationship("Fact", back_populates="metric_evidence")
    document = relationship("Document")
    table = relationship("CanonicalTable")

    @property
    def document_label(self) -> str:
        if self.document is not None:
            return build_document_label(self.document.company_id, self.document.report_year, self.document.report_type)
        return build_document_label(self.company_id, None, None)

    @property
    def report_type_label(self) -> str | None:
        if self.document is not None:
            return get_report_type_label(self.document.report_type)
        return None

    @property
    def table_title(self) -> str:
        if self.table is None:
            return "未命名表格"
        return self.table.table_title_raw or self.table.table_title_norm or "未命名表格"

    @property
    def table_label(self) -> str:
        page_no = self.source_page_no or (self.table.page_start if self.table is not None else None)
        if page_no is None:
            return self.table_title
        return f"P.{page_no} / {self.table_title}"

    @property
    def viewer_params(self) -> dict:
        return {
            "document_id": self.document_id,
            "page": self.source_page_no,
            "table_id": self.source_table_id,
            "fact_id": self.fact_id,
        }

    @property
    def viewer_url(self) -> str | None:
        if not self.document_id:
            return None
        params = []
        if self.source_page_no is not None:
            params.append(f"page={self.source_page_no}")
        if self.source_table_id:
            params.append(f"table_id={self.source_table_id}")
        if self.fact_id:
            params.append(f"fact_id={self.fact_id}")
        query = "&".join(params)
        return f"/documents/{self.document_id}/viewer{f'?{query}' if query else ''}"


class MetricDependency(Base):
    __tablename__ = "metric_dependencies"

    dependency_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_metric_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    depends_on_metric_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("metric_definitions.canonical_metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="formula_input")
    expression_hint: Mapped[str | None] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    metric = relationship("MetricDefinition", foreign_keys=[canonical_metric_id], back_populates="dependencies")
    depends_on_metric = relationship("MetricDefinition", foreign_keys=[depends_on_metric_id], back_populates="dependents")

    @property
    def depends_on_metric_code(self) -> str | None:
        return self.depends_on_metric.metric_code if self.depends_on_metric is not None else None

    @property
    def depends_on_metric_name(self) -> str | None:
        return self.depends_on_metric.metric_name if self.depends_on_metric is not None else None
