from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReviewQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fact_id: str
    company_id: str
    document_id: str
    report_year: int
    canonical_metric_id: str | None
    metric_name_std: str | None
    value_raw: str | None
    value_numeric: Decimal | None
    validation_status: str
    review_status: str
    availability_status: str
    availability_label: str
    validation_score: Decimal | None
    source_page_no: int | None
    source_text_snippet: str | None


class FactActionResponse(BaseModel):
    fact_id: str
    review_status: str


class ApproveFactRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)
    comment: str | None = None


class CorrectFactRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)
    new_value: str
    comment: str | None = None


class RemapMetricRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)
    canonical_metric_id: str = Field(min_length=1, max_length=64)
    metric_name_std: str | None = None
    comment: str | None = None


class ReviewLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_log_id: str
    fact_id: str
    action: str
    old_value_json: dict | None
    new_value_json: dict | None
    reviewer: str
    comment: str | None
    created_at: datetime
