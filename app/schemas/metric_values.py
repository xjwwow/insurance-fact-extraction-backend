from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MetricValueRead(BaseModel):
    fact_id: str
    canonical_metric_id: str | None
    metric_code: str | None
    metric_name: str | None
    company_id: str
    company_label: str
    report_year: int
    report_type: str
    report_type_label: str
    business_line: str | None
    business_line_label: str
    period_type: str
    period_label: str | None
    value_raw: str | None
    value_numeric: Decimal | None
    unit_raw: str | None
    unit_std: str | None
    validation_status: str
    review_status: str
    availability_status: str
    availability_label: str
    document_id: str
    document_label: str
    source_page_no: int | None
    source_table_id: str | None
    table_title: str
    viewer_url: str


class MetricTreeNodeRead(BaseModel):
    key: str
    title: str
    count: int
    children: list["MetricTreeNodeRead"] = []


MetricTreeNodeRead.model_rebuild()
