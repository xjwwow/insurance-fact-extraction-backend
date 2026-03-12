from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetricAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alias_id: str
    canonical_metric_id: str
    alias_text: str
    alias_lang: str | None
    company_id: str | None
    report_type: str | None
    valid_from_year: int | None
    valid_to_year: int | None
    confidence: float | None
    source: str | None
    created_at: datetime


class MetricEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evidence_id: str
    canonical_metric_id: str
    alias_id: str | None
    fact_id: str
    company_id: str | None
    document_id: str | None
    source_table_id: str | None
    source_page_no: int | None
    document_label: str
    report_type_label: str | None
    table_title: str
    table_label: str
    viewer_params: dict
    viewer_url: str | None
    raw_metric_text: str
    normalized_metric_text: str
    statement_scope: str | None
    period_type: str | None
    unit_std: str | None
    evidence_json: dict | None
    created_at: datetime


class MetricDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    canonical_metric_id: str
    metric_code: str | None
    metric_name: str
    metric_name_en: str | None
    category: str | None
    subcategory: str | None
    definition: str | None
    formula_expression: str | None
    value_type: str | None
    default_unit: str | None
    parent_canonical_metric_id: str | None
    hierarchy_depth: int
    sort_order: int
    applicable_scope: dict | None
    applicable_statement_types: dict | None
    is_active: bool
    lifecycle_status: str
    version: int
    created_at: datetime
    updated_at: datetime


class MetricDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dependency_id: str
    canonical_metric_id: str
    depends_on_metric_id: str
    depends_on_metric_code: str | None
    depends_on_metric_name: str | None
    relation_type: str
    expression_hint: str | None
    sort_order: int
    created_at: datetime


class MetricDefinitionDetailRead(MetricDefinitionRead):
    aliases: list[MetricAliasRead]
    evidences: list[MetricEvidenceRead]
    dependencies: list[MetricDependencyRead]


class MetricLibraryBuildResponse(BaseModel):
    document_id: str
    facts_scanned: int
    facts_linked: int
    metrics_created: int
    aliases_created: int
    evidences_created: int


class MetricBootstrapResponse(BaseModel):
    metrics_created: int
    aliases_created: int
    seed_entries: int


class MetricImportPreviewItem(BaseModel):
    row_number: int
    metric_code: str
    metric_name: str
    aliases: list[str]
    category: str | None
    default_unit: str | None
    report_types: list[str]
    business_lines: list[str]


class MetricImportPreviewResponse(BaseModel):
    total_rows: int
    valid_rows: int
    errors: list[str]
    preview_items: list[MetricImportPreviewItem]


class MetricImportResponse(BaseModel):
    total_rows: int
    metrics_created: int
    metrics_updated: int
    aliases_created: int
    aliases_updated: int
    errors: list[str]


class MetricSuggestion(BaseModel):
    canonical_metric_id: str
    metric_code: str | None
    metric_name: str
    score: float


class MetricReviewQueueItem(BaseModel):
    canonical_metric_id: str
    metric_code: str | None
    metric_name: str
    company_id: str | None
    alias_count: int
    evidence_count: int
    fact_count: int
    document_count: int
    pages: list[int]
    sample_aliases: list[str]
    confidence_score: float
    suggested_targets: list[MetricSuggestion]


class MetricMergeRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)
    target_canonical_metric_id: str = Field(min_length=1, max_length=64)
    comment: str | None = None


class MetricDismissRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=128)
    comment: str | None = None


class MetricReviewActionResponse(BaseModel):
    source_canonical_metric_id: str
    action: str
    affected_facts: int
    affected_aliases: int
    affected_evidences: int
    target_canonical_metric_id: str | None = None
