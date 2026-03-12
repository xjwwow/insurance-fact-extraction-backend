from app.repositories.facts import FactRepository


class ReportingService:
    def __init__(self, fact_repository: FactRepository) -> None:
        self.fact_repository = fact_repository

    def query_facts(
        self,
        company_id: str | None = None,
        report_year: int | None = None,
        metric_code: str | None = None,
        document_id: str | None = None,
        source_table_id: str | None = None,
        review_status: str | None = None,
        limit: int = 200,
    ):
        return self.fact_repository.list(
            company_id=company_id,
            report_year=report_year,
            metric_code=metric_code,
            document_id=document_id,
            source_table_id=source_table_id,
            review_status=review_status,
            limit=limit,
        )
