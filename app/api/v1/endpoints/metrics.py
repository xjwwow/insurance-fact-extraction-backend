from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.documents import DocumentRepository
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.schemas.metric_values import MetricTreeNodeRead, MetricValueRead
from app.schemas.metrics import (
    MetricBootstrapResponse,
    MetricDefinitionDetailRead,
    MetricDefinitionRead,
    MetricDismissRequest,
    MetricImportPreviewResponse,
    MetricImportResponse,
    MetricLibraryBuildResponse,
    MetricMergeRequest,
    MetricReviewActionResponse,
    MetricReviewQueueItem,
)
from app.services.knowledge_asset import KnowledgeAssetService
from app.services.metric_library_import import MetricLibraryImportService
from app.services.metric_maintenance import MetricMaintenanceService
from app.services.metric_review import MetricReviewService
from app.services.metric_values import MetricValueService


router = APIRouter(prefix="/metrics", tags=["metrics"])


def _build_knowledge_service(db: Session) -> KnowledgeAssetService:
    return KnowledgeAssetService(
        metric_repository=MetricRepository(db),
        fact_repository=FactRepository(db),
        document_repository=DocumentRepository(db),
    )


def _build_review_service(db: Session) -> MetricReviewService:
    return MetricReviewService(
        metric_repository=MetricRepository(db),
        fact_repository=FactRepository(db),
    )


def _build_import_service(db: Session) -> MetricLibraryImportService:
    return MetricLibraryImportService(metric_repository=MetricRepository(db))


def _build_value_service(db: Session) -> MetricValueService:
    return MetricValueService(db)


def _build_maintenance_service(db: Session) -> MetricMaintenanceService:
    return MetricMaintenanceService(
        metric_repository=MetricRepository(db),
        fact_repository=FactRepository(db),
        document_repository=DocumentRepository(db),
    )


@router.get("", response_model=list[MetricDefinitionRead])
def list_metrics(
    company_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MetricDefinitionRead]:
    repository = MetricRepository(db)
    metrics = repository.list_metrics(company_id=company_id, limit=limit)
    return [MetricDefinitionRead.model_validate(metric) for metric in metrics]


@router.get("/tree", response_model=list[MetricTreeNodeRead])
def get_metric_tree(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MetricTreeNodeRead]:
    repository = MetricRepository(db)
    metrics = repository.list_metrics(company_id=company_id, limit=1000)
    grouped: dict[str, dict[str, int]] = {}
    for metric in metrics:
        category = metric.category or "未分类"
        subcategory = metric.subcategory or "未分组"
        grouped.setdefault(category, {})
        grouped[category][subcategory] = grouped[category].get(subcategory, 0) + 1

    nodes = []
    for category, subgroups in sorted(grouped.items()):
        children = [
            MetricTreeNodeRead(key=f"{category}:{subcategory}", title=subcategory, count=count, children=[])
            for subcategory, count in sorted(subgroups.items())
        ]
        nodes.append(
            MetricTreeNodeRead(
                key=category,
                title=category,
                count=sum(subgroups.values()),
                children=children,
            )
        )
    return nodes


@router.get("/values", response_model=list[MetricValueRead])
def list_metric_values(
    canonical_metric_id: str | None = Query(default=None),
    company_id: str | None = Query(default=None),
    report_type: str | None = Query(default=None),
    report_year: int | None = Query(default=None),
    business_line: str | None = Query(default=None),
    period_type: str | None = Query(default=None),
    availability_status: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[MetricValueRead]:
    service = _build_value_service(db)
    values = service.query_values(
        canonical_metric_id=canonical_metric_id,
        company_id=company_id,
        report_type=report_type,
        report_year=report_year,
        business_line=business_line,
        period_type=period_type,
        availability_status=availability_status,
        limit=limit,
    )
    return [MetricValueRead(**item) for item in values]


@router.post("/bootstrap", response_model=MetricBootstrapResponse)
def bootstrap_metric_library(db: Session = Depends(get_db)) -> MetricBootstrapResponse:
    service = _build_knowledge_service(db)
    result = service.bootstrap_metric_library()
    return MetricBootstrapResponse(**result)


@router.post("/import/preview", response_model=MetricImportPreviewResponse)
async def preview_metric_import(file: UploadFile = File(...), db: Session = Depends(get_db)) -> MetricImportPreviewResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    service = _build_import_service(db)
    try:
        result = service.preview(file.filename or "metrics.xlsx", content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MetricImportPreviewResponse(**result)


@router.post("/import", response_model=MetricImportResponse)
async def import_metric_library(file: UploadFile = File(...), db: Session = Depends(get_db)) -> MetricImportResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    service = _build_import_service(db)
    try:
        result = service.import_rows(file.filename or "metrics.xlsx", content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MetricImportResponse(**result)


@router.post("/build-library", response_model=MetricLibraryBuildResponse)
def build_metric_library(document_id: str = Query(...), db: Session = Depends(get_db)) -> MetricLibraryBuildResponse:
    service = _build_knowledge_service(db)
    try:
        result = service.build_metric_library_for_document(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MetricLibraryBuildResponse(**result)


@router.post("/maintenance/backfill-facts")
def backfill_metric_facts(
    document_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    service = _build_maintenance_service(db)
    return service.backfill_fact_metric_links(document_id=document_id)


@router.get("/review/queue", response_model=list[MetricReviewQueueItem])
def list_metric_review_queue(
    company_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MetricReviewQueueItem]:
    service = _build_review_service(db)
    return [MetricReviewQueueItem(**item) for item in service.list_review_queue(company_id=company_id, limit=limit)]


@router.post("/review/{source_canonical_metric_id}/merge", response_model=MetricReviewActionResponse)
def merge_metric_review(
    source_canonical_metric_id: str,
    payload: MetricMergeRequest,
    db: Session = Depends(get_db),
) -> MetricReviewActionResponse:
    service = _build_review_service(db)
    try:
        result = service.merge_metric(
            source_canonical_metric_id=source_canonical_metric_id,
            target_canonical_metric_id=payload.target_canonical_metric_id,
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return MetricReviewActionResponse(**result)


@router.post("/review/{source_canonical_metric_id}/dismiss", response_model=MetricReviewActionResponse)
def dismiss_metric_review(
    source_canonical_metric_id: str,
    payload: MetricDismissRequest,
    db: Session = Depends(get_db),
) -> MetricReviewActionResponse:
    service = _build_review_service(db)
    try:
        result = service.dismiss_metric(
            source_canonical_metric_id=source_canonical_metric_id,
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MetricReviewActionResponse(**result)


@router.get("/{canonical_metric_id}", response_model=MetricDefinitionDetailRead)
def get_metric(canonical_metric_id: str, db: Session = Depends(get_db)) -> MetricDefinitionDetailRead:
    repository = MetricRepository(db)
    metric = repository.get_with_related(canonical_metric_id)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return MetricDefinitionDetailRead.model_validate(metric)
