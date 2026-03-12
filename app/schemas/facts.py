from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fact_id: str
    company_id: str
    document_id: str
    report_year: int
    period_type: str
    statement_scope: str | None
    canonical_metric_id: str | None
    metric_name_std: str | None
    metric_alias_raw: str | None
    value_raw: str | None
    value_numeric: Decimal | None
    unit_raw: str | None
    unit_std: str | None
    currency: str | None
    dimensions_json: dict | None
    source_page_no: int | None
    source_table_id: str | None
    source_row_path: dict | None
    source_col_path: dict | None
    source_cell_bbox: dict | None
    source_text_snippet: str | None
    extraction_method: str | None
    extraction_confidence: Decimal | None
    validation_score: Decimal | None
    validation_status: str
    review_status: str
    metric_lifecycle_status: str | None
    period_label: str | None
    availability_status: str
    availability_label: str
    viewer_url: str
    reviewer_comment: str | None
    created_at: datetime
    updated_at: datetime
