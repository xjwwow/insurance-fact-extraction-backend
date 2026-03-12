from sqlalchemy import Select, delete, select

from app.models.fact import Fact
from app.models.metric import MetricDefinition
from app.repositories.base import Repository


class FactRepository(Repository):
    def get(self, fact_id: str) -> Fact | None:
        return self.db.get(Fact, fact_id)

    def list(
        self,
        company_id: str | None = None,
        report_year: int | None = None,
        metric_code: str | None = None,
        document_id: str | None = None,
        source_table_id: str | None = None,
        review_status: str | None = None,
        limit: int = 200,
    ) -> list[Fact]:
        stmt: Select[tuple[Fact]] = select(Fact)

        if metric_code:
            stmt = stmt.join(
                MetricDefinition,
                Fact.canonical_metric_id == MetricDefinition.canonical_metric_id,
            ).where(MetricDefinition.metric_code == metric_code)

        if company_id:
            stmt = stmt.where(Fact.company_id == company_id)
        if report_year:
            stmt = stmt.where(Fact.report_year == report_year)
        if document_id:
            stmt = stmt.where(Fact.document_id == document_id)
        if source_table_id:
            stmt = stmt.where(Fact.source_table_id == source_table_id)
        if review_status:
            stmt = stmt.where(Fact.review_status == review_status)

        if document_id or source_table_id:
            stmt = stmt.order_by(Fact.source_page_no.asc().nullslast(), Fact.fact_id.asc())
        else:
            stmt = stmt.order_by(Fact.updated_at.desc())
        stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def list_by_document(self, document_id: str) -> list[Fact]:
        stmt = (
            select(Fact)
            .where(Fact.document_id == document_id)
            .order_by(Fact.source_page_no.asc().nullslast(), Fact.fact_id.asc())
        )
        return list(self.db.scalars(stmt))

    def list_by_metric(self, canonical_metric_id: str) -> list[Fact]:
        stmt = (
            select(Fact)
            .where(Fact.canonical_metric_id == canonical_metric_id)
            .order_by(Fact.updated_at.desc(), Fact.fact_id.asc())
        )
        return list(self.db.scalars(stmt))

    def save(self, fact: Fact) -> Fact:
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        return fact

    def create_many(self, facts: list[Fact]) -> list[Fact]:
        if not facts:
            return []
        self.db.add_all(facts)
        self.db.commit()
        for fact in facts:
            self.db.refresh(fact)
        return facts

    def clear_by_document(self, document_id: str) -> None:
        self.db.execute(delete(Fact).where(Fact.document_id == document_id))
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()
