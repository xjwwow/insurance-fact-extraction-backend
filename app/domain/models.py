from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    document_id: str
    company_id: str
    report_year: int
    report_type: str
    file_path: str
    file_hash: str
    document_type: str


@dataclass
class PageLayout:
    document_id: str
    page_no: int
    width: float
    height: float
    blocks: list[dict[str, Any]]
    tables: list[dict[str, Any]]


@dataclass
class TableCell:
    row_path: list[str]
    col_path: list[str]
    value_raw: str
    bbox: tuple[float, float, float, float]
    confidence: float


@dataclass
class CanonicalTableDomain:
    table_id: str
    document_id: str
    page_start: int
    page_end: int
    table_title_raw: str
    table_title_norm: str
    unit_raw: str | None
    currency_raw: str | None
    row_headers: list[Any]
    col_headers: list[Any]
    cells: list[TableCell]
    footnotes: list[str]
    template_fingerprint: str
    parse_confidence: float


@dataclass
class CandidateFact:
    company_id: str
    document_id: str
    report_year: int
    period_type: str
    statement_scope: str
    raw_metric_text: str
    value_raw: str
    value_numeric: float | None
    unit_raw: str | None
    currency: str | None
    dimensions: dict[str, Any]
    source_page_no: int
    source_table_id: str
    source_row_path: list[str]
    source_col_path: list[str]
    source_cell_bbox: tuple[float, float, float, float]
    source_text_snippet: str
    extraction_confidence: float


@dataclass
class ResolvedFact:
    fact_id: str
    canonical_metric_id: str
    metric_name_std: str
    candidate_fact: CandidateFact
    resolution_confidence: float
    resolution_trace: dict[str, Any] = field(default_factory=dict)
