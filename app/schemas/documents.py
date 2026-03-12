from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    company_id: str
    company_label: str
    business_line: str | None
    business_line_label: str
    report_year: int
    report_type: str
    report_type_label: str
    document_label: str
    file_path: str
    file_hash: str
    document_type: str
    parse_status: str
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    company_id: str
    company_label: str
    business_line: str | None
    business_line_label: str
    report_year: int
    report_type: str
    report_type_label: str
    document_label: str
    parse_status: str
    created_at: datetime


class ParseResultResponse(BaseModel):
    document_id: str
    status: str
    pages_parsed: int
    failed_pages: int
    tables_detected: int
    facts_extracted: int


class ParseTaskSubmitResponse(BaseModel):
    document_id: str
    parse_status: str
    task_id: str
    task_state: str


class ParseTaskStatusResponse(BaseModel):
    task_id: str
    task_state: str
    ready: bool
    successful: bool
    failed: bool
    parse_result: dict[str, Any] | None = None
    error: str | None = None


class CanonicalTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    table_id: str
    document_id: str
    page_start: int
    page_end: int
    table_title_raw: str | None
    table_title_norm: str | None
    unit_raw: str | None
    currency_raw: str | None
    template_fingerprint: str | None
    parse_engine: str | None
    parse_confidence: float | None
    created_at: datetime


class CanonicalTableDetailRead(CanonicalTableRead):
    table_json: dict[str, Any]
    parse_trace_json: dict[str, Any] | None = None


class TableNavItem(BaseModel):
    table_id: str
    title: str
    page_start: int
    page_end: int


class OutlineNodeRead(BaseModel):
    node_id: str
    kind: str
    title: str
    page_start: int | None = None
    page_end: int | None = None
    level: int = 1
    children: list["OutlineNodeRead"] = []
    tables: list[TableNavItem] = []


OutlineNodeRead.model_rebuild()
