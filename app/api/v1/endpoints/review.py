from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.repositories.review import ReviewLogRepository
from app.schemas.review import (
    ApproveFactRequest,
    CorrectFactRequest,
    FactActionResponse,
    RemapMetricRequest,
    ReviewQueueItem,
)
from app.services.review_workbench import ReviewWorkbenchService


router = APIRouter(prefix="/review", tags=["review"])


def _build_service(db: Session) -> ReviewWorkbenchService:
    return ReviewWorkbenchService(
        fact_repository=FactRepository(db),
        review_log_repository=ReviewLogRepository(db),
        metric_repository=MetricRepository(db),
    )


@router.get("/queue", response_model=list[ReviewQueueItem])
def list_review_queue(
    company_id: str | None = Query(default=None),
    report_year: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ReviewQueueItem]:
    service = _build_service(db)
    facts = service.list_review_queue(company_id=company_id, report_year=report_year, limit=limit)
    return [ReviewQueueItem.model_validate(fact) for fact in facts]


@router.post("/facts/{fact_id}/approve", response_model=FactActionResponse)
def approve_fact(fact_id: str, payload: ApproveFactRequest, db: Session = Depends(get_db)) -> FactActionResponse:
    service = _build_service(db)
    try:
        fact = service.approve_fact(fact_id=fact_id, reviewer=payload.reviewer, comment=payload.comment)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FactActionResponse(fact_id=fact.fact_id, review_status=fact.review_status)


@router.post("/facts/{fact_id}/correct", response_model=FactActionResponse)
def correct_fact(fact_id: str, payload: CorrectFactRequest, db: Session = Depends(get_db)) -> FactActionResponse:
    service = _build_service(db)
    try:
        fact = service.correct_fact(
            fact_id=fact_id,
            new_value=payload.new_value,
            reviewer=payload.reviewer,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FactActionResponse(fact_id=fact.fact_id, review_status=fact.review_status)


@router.post("/facts/{fact_id}/remap-metric", response_model=FactActionResponse)
def remap_metric(fact_id: str, payload: RemapMetricRequest, db: Session = Depends(get_db)) -> FactActionResponse:
    service = _build_service(db)
    try:
        fact = service.remap_metric(
            fact_id=fact_id,
            canonical_metric_id=payload.canonical_metric_id,
            reviewer=payload.reviewer,
            metric_name_std=payload.metric_name_std,
            comment=payload.comment,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return FactActionResponse(fact_id=fact.fact_id, review_status=fact.review_status)
