from __future__ import annotations

from app.repositories.documents import DocumentRepository
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.services.metric_resolution import MetricResolutionService


class MetricMaintenanceService:
    def __init__(
        self,
        metric_repository: MetricRepository,
        fact_repository: FactRepository,
        document_repository: DocumentRepository,
    ) -> None:
        self.metric_repository = metric_repository
        self.fact_repository = fact_repository
        self.document_repository = document_repository
        self.metric_resolution_service = MetricResolutionService(metric_repository)

    def backfill_fact_metric_links(self, document_id: str | None = None) -> dict:
        facts = self.fact_repository.list_by_document(document_id) if document_id else self.fact_repository.list(limit=5000)
        updated = 0
        cleared = 0

        for fact in facts:
            if not fact.metric_alias_raw:
                continue
            needs_backfill = (
                str(fact.canonical_metric_id or "").startswith("metric_learned_")
                or str(fact.canonical_metric_id or "").startswith("metric_candidate_")
                or fact.metric_lifecycle_status in {"candidate", "merged", "dismissed"}
            )
            if not needs_backfill:
                continue

            document = self.document_repository.get(fact.document_id)
            if document is None:
                continue

            resolved = self.metric_resolution_service.resolve_metric(
                {
                    "raw_metric_text": fact.metric_alias_raw,
                    "company_id": fact.company_id,
                    "report_year": fact.report_year,
                    "report_type": document.report_type,
                    "statement_scope": fact.statement_scope,
                    "template_fingerprint": None,
                }
            )
            canonical_metric_id = resolved.get("canonical_metric_id")
            if canonical_metric_id:
                fact.canonical_metric_id = canonical_metric_id
                fact.metric_name_std = resolved.get("metric_name_std")
                fact.dimensions_json = {**(fact.dimensions_json or {}), "metric_lifecycle_status": resolved.get("metric_lifecycle_status")}
                updated += 1
            else:
                fact.canonical_metric_id = None
                fact.metric_name_std = None
                fact.dimensions_json = {**(fact.dimensions_json or {}), "metric_lifecycle_status": None}
                fact.review_status = "PENDING"
                cleared += 1
            self.fact_repository.db.add(fact)

        self.fact_repository.commit()
        return {
            "document_id": document_id,
            "facts_scanned": len(facts),
            "facts_updated": updated,
            "facts_cleared": cleared,
        }
