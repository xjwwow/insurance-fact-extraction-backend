from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.documents import DocumentRepository
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.services.document_processing import DocumentProcessingService


@celery_app.task(name="document.parse", bind=True)
def parse_document_task(self, document_id: str) -> dict:
    _ = self
    with SessionLocal() as db:
        processor = DocumentProcessingService(
            document_repository=DocumentRepository(db),
            fact_repository=FactRepository(db),
            metric_repository=MetricRepository(db),
        )
        return processor.process_document(document_id)
