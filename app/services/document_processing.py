from app.core.ids import generate_id
from app.models.canonical import CanonicalTable, DocumentPage
from app.models.enums import ParseStatus, ReviewStatus
from app.models.fact import Fact
from app.repositories.documents import DocumentRepository
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.services.canonicalization import CanonicalizationService
from app.services.document_parsing import DocumentParsingService
from app.services.fact_extraction import FactExtractionService
from app.services.knowledge_asset import KnowledgeAssetService
from app.services.metric_resolution import MetricResolutionService
from app.services.validation_engine import ValidationEngine


class DocumentProcessingService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        fact_repository: FactRepository,
        metric_repository: MetricRepository,
    ) -> None:
        self.document_repository = document_repository
        self.fact_repository = fact_repository
        self.metric_repository = metric_repository

        self.document_parsing_service = DocumentParsingService()
        self.canonicalization_service = CanonicalizationService()
        self.fact_extraction_service = FactExtractionService()
        self.metric_resolution_service = MetricResolutionService(metric_repository=metric_repository)
        self.knowledge_asset_service = KnowledgeAssetService(
            metric_repository=metric_repository,
            fact_repository=fact_repository,
            document_repository=document_repository,
        )
        self.validation_engine = ValidationEngine()

    def process_document(self, document_id: str) -> dict:
        document = self.document_repository.get(document_id)
        if document is None:
            raise ValueError(f"document not found: {document_id}")

        try:
            self.document_repository.update_parse_status(document, ParseStatus.PARSING.value)
            self._clear_previous_outputs(document.document_id)
            self.knowledge_asset_service.bootstrap_metric_library()

            page_layouts = self.document_parsing_service.parse_document(document)
            if not page_layouts:
                raise RuntimeError("no pages parsed")

            failed_pages = sum(1 for page in page_layouts if page.get("parse_trace", {}).get("error"))
            self._persist_pages(document.document_id, page_layouts)

            raw_tables = []
            for page_layout in page_layouts:
                raw_tables.extend(self.document_parsing_service.detect_tables(page_layout))

            canonical_tables = self._persist_canonical_tables(document.document_id, raw_tables)

            doc_meta = {
                "company_id": document.company_id,
                "document_id": document.document_id,
                "report_year": document.report_year,
                "report_type": document.report_type,
            }
            candidate_facts: list[dict] = []
            for table in canonical_tables:
                candidate_facts.extend(self.fact_extraction_service.extract_facts(table, doc_meta))

            resolved_facts: list[dict] = []
            for candidate in candidate_facts:
                resolved_facts.append(
                    {
                        **candidate,
                        **self.metric_resolution_service.resolve_metric(candidate),
                    }
                )

            validations = self.validation_engine.validate_batch(resolved_facts)
            persisted_facts = self._persist_facts(document, resolved_facts, validations)
            metric_library_result = self.knowledge_asset_service.build_metric_library_for_document(document.document_id)

            if failed_pages >= len(page_layouts):
                final_status = ParseStatus.FAILED.value
            else:
                final_status = ParseStatus.PARSED.value
            self.document_repository.update_parse_status(document, final_status)

            return {
                "document_id": document.document_id,
                "status": final_status,
                "pages_parsed": len(page_layouts),
                "failed_pages": failed_pages,
                "tables_detected": len(canonical_tables),
                "facts_extracted": len(persisted_facts),
                "metrics_linked": metric_library_result["facts_linked"],
                "metrics_created": metric_library_result["metrics_created"],
                "aliases_created": metric_library_result["aliases_created"],
            }
        except Exception:
            self.document_repository.update_parse_status(document, ParseStatus.FAILED.value)
            raise

    def _clear_previous_outputs(self, document_id: str) -> None:
        self.fact_repository.clear_by_document(document_id)
        self.document_repository.clear_tables(document_id)
        self.document_repository.clear_pages(document_id)

    def _persist_pages(self, document_id: str, page_layouts: list[dict]) -> None:
        for page in page_layouts:
            model = DocumentPage(
                page_id=generate_id("page"),
                document_id=document_id,
                page_no=int(page.get("page_no", 1)),
                page_image_path=None,
                layout_json=page,
            )
            self.document_repository.create_page(model)

    def _persist_canonical_tables(self, document_id: str, raw_tables: list[dict]) -> list[dict]:
        tables: list[dict] = []
        for raw_table in raw_tables:
            canonical = self.canonicalization_service.build_canonical_table(
                raw_table=raw_table,
                page_context={"document_id": document_id},
            )
            model = CanonicalTable(
                table_id=canonical["table_id"],
                document_id=document_id,
                page_start=canonical["page_start"],
                page_end=canonical["page_end"],
                table_title_raw=canonical.get("table_title_raw"),
                table_title_norm=canonical.get("table_title_norm"),
                unit_raw=canonical.get("unit_raw"),
                currency_raw=canonical.get("currency_raw"),
                table_json=canonical.get("table_json", {}),
                template_fingerprint=canonical.get("template_fingerprint"),
                parse_engine=canonical.get("parse_engine"),
                parse_confidence=canonical.get("parse_confidence"),
                parse_trace_json=canonical.get("parse_trace_json"),
            )
            self.document_repository.create_table(model)
            tables.append(canonical)
        return tables

    def _persist_facts(self, document, resolved_facts: list[dict], validations: list[dict]) -> list[Fact]:
        facts: list[Fact] = []
        for resolved, validation in zip(resolved_facts, validations, strict=False):
            validation_status = validation["validation_status"]
            metric_lifecycle_status = resolved.get("metric_lifecycle_status")
            auto_approved = validation_status == "PASS" and metric_lifecycle_status == "active"
            review_status = ReviewStatus.APPROVED.value if auto_approved else ReviewStatus.PENDING.value
            dimensions = {**(resolved.get("dimensions") or {})}
            if metric_lifecycle_status:
                dimensions["metric_lifecycle_status"] = metric_lifecycle_status

            facts.append(
                Fact(
                    fact_id=generate_id("fact"),
                    company_id=document.company_id,
                    document_id=document.document_id,
                    report_year=document.report_year,
                    period_type=resolved.get("period_type", "ANNUAL"),
                    statement_scope=resolved.get("statement_scope"),
                    canonical_metric_id=resolved.get("canonical_metric_id"),
                    metric_name_std=resolved.get("metric_name_std"),
                    metric_alias_raw=resolved.get("raw_metric_text"),
                    value_raw=resolved.get("value_raw"),
                    value_numeric=resolved.get("value_numeric"),
                    unit_raw=resolved.get("unit_raw"),
                    unit_std=resolved.get("unit_std"),
                    currency=resolved.get("currency"),
                    dimensions_json=dimensions,
                    source_page_no=resolved.get("source_page_no"),
                    source_table_id=resolved.get("source_table_id"),
                    source_row_path={"path": resolved.get("source_row_path", [])},
                    source_col_path={"path": resolved.get("source_col_path", [])},
                    source_cell_bbox={"bbox": resolved.get("source_cell_bbox", [])},
                    source_text_snippet=resolved.get("source_text_snippet"),
                    extraction_method=resolved.get("extraction_method"),
                    extraction_confidence=resolved.get("extraction_confidence"),
                    validation_score=validation.get("validation_score"),
                    validation_status=validation_status,
                    review_status=review_status,
                    reviewer_comment=None,
                )
            )

        return self.fact_repository.create_many(facts)
