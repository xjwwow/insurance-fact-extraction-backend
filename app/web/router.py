from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(include_in_schema=False)

STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"


@router.get("/")
def upload_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@router.get("/documents/{document_id}/viewer")
def viewer_page(document_id: str) -> FileResponse:
    _ = document_id
    return FileResponse(STATIC_ROOT / "viewer.html")


@router.get("/documents/{document_id}/qa")
def document_qa_page(document_id: str) -> FileResponse:
    _ = document_id
    return FileResponse(STATIC_ROOT / "document-qa.html")


@router.get("/metrics/review")
def metric_review_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "metrics-review.html")


@router.get("/metrics/library")
def metric_library_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "metrics-library.html")


@router.get("/metrics/values")
def metric_values_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "metrics-values.html")


@router.get("/qa/workbench")
def qa_workbench_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "qa-workbench.html")
