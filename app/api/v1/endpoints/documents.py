from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.reference_data import (
    is_supported_business_line,
    is_supported_company,
    is_supported_report_type,
    normalize_company_id,
    normalize_report_type,
)
from app.db.session import get_db
from app.models.enums import ParseStatus
from app.repositories.documents import DocumentRepository
from app.repositories.table_qa import TableQARepository
from app.schemas.documents import (
    CanonicalTableDetailRead,
    CanonicalTableRead,
    DocumentListItem,
    DocumentRead,
    DocumentUploadResponse,
    OutlineNodeRead,
    ParseTaskStatusResponse,
    ParseTaskSubmitResponse,
)
from app.schemas.table_qa import TableQARecordRead, TableQAReviewResponse, TableQAReviewUpsertRequest
from app.services.document_ingestion import DocumentIngestionService
from app.services.document_outline import DocumentOutlineService
from app.services.document_preview import DocumentPreviewService
from app.services.table_qa import TableQAService
from app.tasks.parse_tasks import parse_document_task


router = APIRouter(prefix="/documents", tags=["documents"])


def _table_sort_key(table) -> tuple[int, float, str]:
    trace = getattr(table, "parse_trace_json", {}) or {}
    bbox = trace.get("bbox") if isinstance(trace, dict) else None
    top = float(bbox[1]) if isinstance(bbox, list) and len(bbox) == 4 else 999999.0
    title = getattr(table, "table_title_raw", None) or getattr(table, "table_title_norm", None) or ""
    return (getattr(table, "page_start", 0), top, title)


def _build_table_qa_service(db: Session) -> TableQAService:
    return TableQAService(
        document_repository=DocumentRepository(db),
        table_qa_repository=TableQARepository(db),
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    company_id: str = Form(...),
    business_line: str = Form(...),
    report_year: int = Form(...),
    report_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    normalized_company_id = normalize_company_id(company_id)
    normalized_report_type = normalize_report_type(report_type)
    if not is_supported_company(normalized_company_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported company_id")
    if not is_supported_report_type(normalized_report_type):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported report_type")
    if not is_supported_business_line(business_line):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported business_line")

    repository = DocumentRepository(db)
    service = DocumentIngestionService(repository)
    document = service.ingest(
        file_name=file.filename or "document.pdf",
        file_bytes=content,
        company_id=normalized_company_id,
        business_line=business_line,
        report_year=report_year,
        report_type=normalized_report_type,
    )
    return DocumentUploadResponse(document_id=document.document_id, status=document.parse_status)


@router.post("/{document_id}/parse", response_model=ParseTaskSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_parse(document_id: str, db: Session = Depends(get_db)) -> ParseTaskSubmitResponse:
    repository = DocumentRepository(db)
    ingestion_service = DocumentIngestionService(repository)
    document = ingestion_service.queue_parse(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        task_result = parse_document_task.delay(document_id)
    except Exception as exc:
        repository.update_parse_status(document, ParseStatus.FAILED.value)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Queue unavailable: {exc}") from exc

    return ParseTaskSubmitResponse(
        document_id=document.document_id,
        parse_status=document.parse_status,
        task_id=task_result.id,
        task_state=task_result.state,
    )


@router.get("/parse-tasks/{task_id}", response_model=ParseTaskStatusResponse)
def get_parse_task_status(task_id: str) -> ParseTaskStatusResponse:
    result = AsyncResult(task_id, app=celery_app)

    payload = ParseTaskStatusResponse(
        task_id=task_id,
        task_state=result.state,
        ready=result.ready(),
        successful=result.successful(),
        failed=result.failed(),
    )

    if result.ready():
        if result.successful():
            value = result.result
            if isinstance(value, dict):
                payload.parse_result = value
            else:
                payload.parse_result = {"result": str(value)}
        else:
            payload.error = str(result.result)

    return payload


@router.get("", response_model=list[DocumentListItem])
def list_documents(
    company_id: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DocumentListItem]:
    repository = DocumentRepository(db)
    company_filter = normalize_company_id(company_id) if company_id else None
    documents = repository.list(company_id=company_filter, limit=limit)
    return [DocumentListItem.model_validate(document) for document in documents]


@router.get("/{document_id}/file")
def get_document_file(document_id: str, db: Session = Depends(get_db)) -> FileResponse:
    repository = DocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )


@router.get("/{document_id}/pages/{page_no}/preview")
def get_document_page_preview(document_id: str, page_no: int, db: Session = Depends(get_db)) -> FileResponse:
    repository = DocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    service = DocumentPreviewService()
    try:
        preview_path = service.render_page_preview(document, page_no)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FileResponse(path=preview_path, media_type="image/png")


@router.get("/{document_id}/tables", response_model=list[CanonicalTableRead])
def list_document_tables(document_id: str, db: Session = Depends(get_db)) -> list[CanonicalTableRead]:
    repository = DocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    tables = sorted(repository.list_tables(document_id), key=_table_sort_key)
    return [CanonicalTableRead.model_validate(table) for table in tables]


@router.get("/{document_id}/outline", response_model=list[OutlineNodeRead])
def get_document_outline(document_id: str, db: Session = Depends(get_db)) -> list[OutlineNodeRead]:
    repository = DocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    tables = sorted(repository.list_tables(document_id), key=_table_sort_key)
    outline = DocumentOutlineService().build_outline(
        document=document,
        tables=[
            {
                "table_id": table.table_id,
                "table_title_raw": table.table_title_raw,
                "table_title_norm": table.table_title_norm,
                "page_start": table.page_start,
                "page_end": table.page_end,
            }
            for table in tables
        ],
    )
    return [OutlineNodeRead(**item) for item in outline]


@router.get("/{document_id}/tables/{table_id}", response_model=CanonicalTableDetailRead)
def get_document_table(document_id: str, table_id: str, db: Session = Depends(get_db)) -> CanonicalTableDetailRead:
    repository = DocumentRepository(db)
    table = repository.get_table(document_id=document_id, table_id=table_id)
    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return CanonicalTableDetailRead.model_validate(table)


@router.get("/{document_id}/qa", response_model=list[TableQARecordRead])
def get_document_table_qa(document_id: str, db: Session = Depends(get_db)) -> list[TableQARecordRead]:
    service = _build_table_qa_service(db)
    try:
        rows = service.list_document_qa(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [TableQARecordRead(**row) for row in rows]


@router.post("/{document_id}/qa/reviews/{table_id}", response_model=TableQAReviewResponse)
def upsert_document_table_qa_review(
    document_id: str,
    table_id: str,
    payload: TableQAReviewUpsertRequest,
    db: Session = Depends(get_db),
) -> TableQAReviewResponse:
    service = _build_table_qa_service(db)
    try:
        review = service.save_review(
            document_id=document_id,
            table_id=table_id,
            manual_status=payload.manual_status,
            manual_note=payload.manual_note,
            reviewer=payload.reviewer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return TableQAReviewResponse(**review)


@router.get("/{document_id}/qa/export")
def export_document_table_qa(document_id: str, db: Session = Depends(get_db)) -> FileResponse:
    service = _build_table_qa_service(db)
    try:
        export_path = service.export_document_qa(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        path=export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=export_path.name,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentRead:
    repository = DocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentRead.model_validate(document)
