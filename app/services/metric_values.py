from __future__ import annotations

from sqlalchemy import Select, asc, or_, select
from sqlalchemy.orm import Session

from app.core.reference_data import get_business_line_label, get_company_label, get_report_type_label
from app.models.canonical import CanonicalTable
from app.models.document import Document
from app.models.fact import Fact
from app.models.metric import MetricDefinition


class MetricValueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def query_values(
        self,
        canonical_metric_id: str | None = None,
        company_id: str | None = None,
        report_type: str | None = None,
        report_year: int | None = None,
        business_line: str | None = None,
        period_type: str | None = None,
        availability_status: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        stmt: Select = (
            select(Fact, Document, MetricDefinition, CanonicalTable)
            .join(Document, Fact.document_id == Document.document_id)
            .outerjoin(MetricDefinition, Fact.canonical_metric_id == MetricDefinition.canonical_metric_id)
            .outerjoin(CanonicalTable, Fact.source_table_id == CanonicalTable.table_id)
        )

        if canonical_metric_id:
            stmt = stmt.where(Fact.canonical_metric_id == canonical_metric_id)
        if company_id:
            stmt = stmt.where(Fact.company_id == company_id)
        if report_type:
            stmt = stmt.where(Document.report_type == report_type)
        if report_year is not None:
            stmt = stmt.where(Fact.report_year == report_year)
        if business_line:
            stmt = stmt.where(Document.business_line == business_line)
        if period_type:
            stmt = stmt.where(Fact.period_type == period_type)

        stmt = stmt.order_by(
            asc(Document.company_id),
            asc(Fact.report_year),
            asc(Fact.source_page_no),
            asc(Fact.fact_id),
        ).limit(limit)

        rows = []
        for fact, document, metric, table in self.db.execute(stmt).all():
            availability = fact.availability_status
            if availability_status and availability != availability_status:
                continue
            rows.append(
                {
                    "fact_id": fact.fact_id,
                    "canonical_metric_id": fact.canonical_metric_id,
                    "metric_code": metric.metric_code if metric is not None else None,
                    "metric_name": metric.metric_name if metric is not None else fact.metric_name_std,
                    "company_id": fact.company_id,
                    "company_label": get_company_label(fact.company_id),
                    "report_year": fact.report_year,
                    "report_type": document.report_type,
                    "report_type_label": get_report_type_label(document.report_type),
                    "business_line": document.business_line,
                    "business_line_label": get_business_line_label(document.business_line),
                    "period_type": fact.period_type,
                    "period_label": fact.period_label,
                    "value_raw": fact.value_raw,
                    "value_numeric": fact.value_numeric,
                    "unit_raw": fact.unit_raw,
                    "unit_std": fact.unit_std,
                    "validation_status": fact.validation_status,
                    "review_status": fact.review_status,
                    "availability_status": availability,
                    "availability_label": fact.availability_label,
                    "document_id": fact.document_id,
                    "document_label": document.document_label,
                    "source_page_no": fact.source_page_no,
                    "source_table_id": fact.source_table_id,
                    "table_title": (
                        table.table_title_raw or table.table_title_norm if table is not None else "未命名表格"
                    ),
                    "viewer_url": fact.viewer_url,
                }
            )
        return rows
