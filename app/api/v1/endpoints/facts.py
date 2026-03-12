from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.facts import FactRepository
from app.schemas.facts import FactRead
from app.services.reporting import ReportingService


router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("", response_model=list[FactRead])
def query_facts(
    company_id: str | None = Query(default=None),
    report_year: int | None = Query(default=None),
    metric_code: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    source_table_id: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[FactRead]:
    service = ReportingService(FactRepository(db))
    facts = service.query_facts(
        company_id=company_id,
        report_year=report_year,
        metric_code=metric_code,
        document_id=document_id,
        source_table_id=source_table_id,
        review_status=review_status,
        limit=limit,
    )
    return [FactRead.model_validate(fact) for fact in facts]
