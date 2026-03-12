from datetime import datetime

from pydantic import BaseModel, Field


class TableQARecordRead(BaseModel):
    document_id: str
    document_label: str
    table_id: str
    section_path: str
    page_start: int
    page_end: int
    table_title: str
    parse_engine: str
    header_levels: int
    col_header_count: int
    row_count: int
    cell_count: int
    generic_title: bool
    generic_headers: int
    merged_header_detected: bool
    suspected_wrap_issue: bool
    suspected_value_issue: bool
    bbox_quality: str
    overall_status: str
    auto_flags: list[str]
    viewer_url: str
    manual_status: str | None = None
    manual_note: str | None = None
    reviewer: str | None = None
    reviewed_at: datetime | None = None


class TableQAReviewUpsertRequest(BaseModel):
    manual_status: str | None = Field(default=None, max_length=32)
    manual_note: str | None = None
    reviewer: str | None = Field(default=None, max_length=128)


class TableQAReviewResponse(BaseModel):
    qa_review_id: str
    table_id: str
    manual_status: str | None
    manual_note: str | None
    reviewer: str | None
    reviewed_at: datetime | None
