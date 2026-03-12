import hashlib
from pathlib import Path

from app.core.config import settings
from app.core.ids import generate_id
from app.models.document import Document
from app.models.enums import ParseStatus
from app.repositories.documents import DocumentRepository


class DocumentIngestionService:
    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    def ingest(
        self,
        file_name: str,
        file_bytes: bytes,
        company_id: str,
        business_line: str | None,
        report_year: int,
        report_type: str,
    ) -> Document:
        document_id = generate_id("doc")
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        document_type = self.detect_document_type(file_name, file_bytes)

        storage_root = Path(settings.storage_root)
        storage_root.mkdir(parents=True, exist_ok=True)
        target_name = f"{document_id}.pdf"
        target_path = storage_root / target_name
        target_path.write_bytes(file_bytes)

        record = Document(
            document_id=document_id,
            company_id=company_id,
            business_line=business_line,
            report_year=report_year,
            report_type=report_type,
            file_path=str(target_path),
            file_hash=file_hash,
            document_type=document_type,
            parse_status=ParseStatus.INGESTED.value,
        )
        return self.repository.create(record)

    def detect_document_type(self, file_name: str, file_bytes: bytes) -> str:
        _ = file_name
        _ = file_bytes
        return "pdf"

    def queue_parse(self, document_id: str) -> Document | None:
        document = self.repository.get(document_id)
        if not document:
            return None
        return self.repository.update_parse_status(document, ParseStatus.PARSE_QUEUED.value)
