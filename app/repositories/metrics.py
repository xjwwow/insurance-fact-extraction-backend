from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.models.canonical import CanonicalTable
from app.models.metric import MetricAlias, MetricDefinition, MetricDependency, MetricEvidence
from app.repositories.base import Repository


class MetricRepository(Repository):
    def get(self, canonical_metric_id: str) -> MetricDefinition | None:
        return self.db.get(MetricDefinition, canonical_metric_id)

    def get_with_related(self, canonical_metric_id: str) -> MetricDefinition | None:
        stmt = (
            select(MetricDefinition)
            .options(
                selectinload(MetricDefinition.aliases),
                selectinload(MetricDefinition.evidences).selectinload(MetricEvidence.document),
                selectinload(MetricDefinition.evidences).selectinload(MetricEvidence.table),
                selectinload(MetricDefinition.dependencies).selectinload(MetricDependency.depends_on_metric),
            )
            .where(MetricDefinition.canonical_metric_id == canonical_metric_id)
        )
        return self.db.scalar(stmt)

    def get_by_code(self, metric_code: str) -> MetricDefinition | None:
        stmt = select(MetricDefinition).where(MetricDefinition.metric_code == metric_code)
        return self.db.scalar(stmt)

    def get_by_name(self, metric_name: str) -> MetricDefinition | None:
        stmt = select(MetricDefinition).where(func.lower(MetricDefinition.metric_name) == metric_name.strip().lower())
        return self.db.scalar(stmt)

    def list_metrics(self, company_id: str | None = None, limit: int = 100) -> list[MetricDefinition]:
        stmt = (
            select(MetricDefinition)
            .where(
                MetricDefinition.is_active.is_(True),
                MetricDefinition.lifecycle_status == "active",
            )
            .order_by(
                MetricDefinition.category.asc().nullslast(),
                MetricDefinition.subcategory.asc().nullslast(),
                MetricDefinition.sort_order.asc(),
                MetricDefinition.metric_name.asc(),
            )
            .limit(limit)
        )

        if company_id:
            stmt = stmt.where(
                or_(
                    MetricDefinition.canonical_metric_id.in_(
                        select(MetricAlias.canonical_metric_id).where(
                            or_(MetricAlias.company_id == company_id, MetricAlias.company_id.is_(None))
                        )
                    ),
                    MetricDefinition.canonical_metric_id.in_(
                        select(MetricEvidence.canonical_metric_id).where(MetricEvidence.company_id == company_id)
                    ),
                )
            )

        return list(self.db.scalars(stmt))

    def list_candidate_metrics(self, company_id: str | None = None, limit: int = 100) -> list[MetricDefinition]:
        stmt = (
            select(MetricDefinition)
            .where(
                MetricDefinition.is_active.is_(True),
                MetricDefinition.lifecycle_status == "candidate",
            )
            .order_by(MetricDefinition.updated_at.desc(), MetricDefinition.metric_name.asc())
            .limit(limit)
        )
        if company_id:
            stmt = stmt.where(
                MetricDefinition.canonical_metric_id.in_(
                    select(MetricAlias.canonical_metric_id).where(MetricAlias.company_id == company_id)
                )
            )
        return list(self.db.scalars(stmt))

    def search_aliases(
        self,
        raw_metric_text: str,
        company_id: str | None = None,
        report_type: str | None = None,
        report_year: int | None = None,
        limit: int = 10,
    ) -> list[tuple[MetricAlias, MetricDefinition]]:
        text = raw_metric_text.strip()
        if not text:
            return []

        lowered = text.lower()
        stmt = (
            select(MetricAlias, MetricDefinition)
            .join(
                MetricDefinition,
                MetricAlias.canonical_metric_id == MetricDefinition.canonical_metric_id,
            )
            .where(
                MetricDefinition.is_active.is_(True),
                MetricDefinition.lifecycle_status == "active",
            )
            .where(
                or_(
                    func.lower(MetricAlias.alias_text) == lowered,
                    func.lower(MetricAlias.alias_text).startswith(lowered),
                    func.lower(MetricAlias.alias_text).contains(lowered),
                    func.lower(MetricDefinition.metric_name) == lowered,
                )
            )
            .limit(limit)
        )

        if company_id:
            stmt = stmt.where(or_(MetricAlias.company_id == company_id, MetricAlias.company_id.is_(None)))
        if report_type:
            stmt = stmt.where(or_(MetricAlias.report_type == report_type, MetricAlias.report_type.is_(None)))
        if report_year is not None:
            stmt = stmt.where(
                or_(MetricAlias.valid_from_year.is_(None), MetricAlias.valid_from_year <= report_year)
            ).where(
                or_(MetricAlias.valid_to_year.is_(None), MetricAlias.valid_to_year >= report_year)
            )

        return list(self.db.execute(stmt).all())

    def list_aliases(self, canonical_metric_id: str) -> list[MetricAlias]:
        stmt = (
            select(MetricAlias)
            .where(MetricAlias.canonical_metric_id == canonical_metric_id)
            .order_by(MetricAlias.company_id.asc().nullsfirst(), MetricAlias.alias_text.asc())
        )
        return list(self.db.scalars(stmt))

    def list_evidences(self, canonical_metric_id: str, limit: int = 100) -> list[MetricEvidence]:
        stmt = (
            select(MetricEvidence)
            .where(MetricEvidence.canonical_metric_id == canonical_metric_id)
            .order_by(MetricEvidence.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def search_historical_template_candidates(
        self,
        company_id: str,
        template_fingerprint: str,
        normalized_metric_text: str,
        limit: int = 50,
    ) -> list[tuple[MetricEvidence, MetricDefinition, CanonicalTable]]:
        stmt = (
            select(MetricEvidence, MetricDefinition, CanonicalTable)
            .join(MetricDefinition, MetricEvidence.canonical_metric_id == MetricDefinition.canonical_metric_id)
            .join(CanonicalTable, MetricEvidence.source_table_id == CanonicalTable.table_id)
            .where(
                MetricEvidence.company_id == company_id,
                CanonicalTable.template_fingerprint == template_fingerprint,
                MetricDefinition.is_active.is_(True),
                MetricDefinition.lifecycle_status == "active",
            )
            .limit(limit)
        )
        if normalized_metric_text:
            stmt = stmt.where(
                or_(
                    MetricEvidence.normalized_metric_text == normalized_metric_text,
                    MetricEvidence.normalized_metric_text.startswith(normalized_metric_text),
                    MetricEvidence.normalized_metric_text.contains(normalized_metric_text),
                )
            )
        stmt = stmt.order_by(MetricEvidence.created_at.desc())
        return list(self.db.execute(stmt).all())

    def upsert_metric_definition(self, payload: dict) -> tuple[MetricDefinition, bool]:
        metric = self.get(payload["canonical_metric_id"])
        created = metric is None
        if metric is None:
            metric = MetricDefinition(**payload)
        else:
            for field, value in payload.items():
                if field == "canonical_metric_id":
                    continue
                setattr(metric, field, value)
        self.db.add(metric)
        self.db.flush()
        return metric, created

    def find_alias(
        self,
        canonical_metric_id: str,
        alias_text: str,
        company_id: str | None = None,
        report_type: str | None = None,
    ) -> MetricAlias | None:
        stmt = select(MetricAlias).where(
            MetricAlias.canonical_metric_id == canonical_metric_id,
            func.lower(MetricAlias.alias_text) == alias_text.strip().lower(),
        )
        if company_id is None:
            stmt = stmt.where(MetricAlias.company_id.is_(None))
        else:
            stmt = stmt.where(MetricAlias.company_id == company_id)
        if report_type is None:
            stmt = stmt.where(MetricAlias.report_type.is_(None))
        else:
            stmt = stmt.where(MetricAlias.report_type == report_type)
        return self.db.scalar(stmt)

    def upsert_alias(self, payload: dict) -> tuple[MetricAlias, bool]:
        alias = self.find_alias(
            canonical_metric_id=payload["canonical_metric_id"],
            alias_text=payload["alias_text"],
            company_id=payload.get("company_id"),
            report_type=payload.get("report_type"),
        )
        created = alias is None
        if alias is None:
            alias = MetricAlias(**payload)
        else:
            for field, value in payload.items():
                if field == "alias_id":
                    continue
                setattr(alias, field, value)
        self.db.add(alias)
        self.db.flush()
        return alias, created

    def get_evidence_by_fact(self, fact_id: str) -> MetricEvidence | None:
        stmt = select(MetricEvidence).where(MetricEvidence.fact_id == fact_id)
        return self.db.scalar(stmt)

    def upsert_evidence(self, payload: dict) -> tuple[MetricEvidence, bool]:
        evidence = self.get_evidence_by_fact(payload["fact_id"])
        created = evidence is None
        if evidence is None:
            evidence = MetricEvidence(**payload)
        else:
            for field, value in payload.items():
                if field == "evidence_id":
                    continue
                setattr(evidence, field, value)
        self.db.add(evidence)
        self.db.flush()
        return evidence, created

    def reassign_evidence_alias(self, old_alias_id: str, new_alias_id: str) -> None:
        self.db.execute(
            update(MetricEvidence)
            .where(MetricEvidence.alias_id == old_alias_id)
            .values(alias_id=new_alias_id)
        )
        self.db.flush()

    def delete_alias(self, alias: MetricAlias) -> None:
        self.db.delete(alias)
        self.db.flush()

    def save_metric(self, metric: MetricDefinition) -> MetricDefinition:
        self.db.add(metric)
        self.db.flush()
        return metric

    def save_alias(self, alias: MetricAlias) -> MetricAlias:
        self.db.add(alias)
        self.db.flush()
        return alias

    def save_evidence(self, evidence: MetricEvidence) -> MetricEvidence:
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def list_dependencies(self, canonical_metric_id: str) -> list[MetricDependency]:
        stmt = (
            select(MetricDependency)
            .where(MetricDependency.canonical_metric_id == canonical_metric_id)
            .order_by(MetricDependency.sort_order.asc(), MetricDependency.depends_on_metric_id.asc())
        )
        return list(self.db.scalars(stmt))

    def clear_dependencies(self, canonical_metric_id: str) -> None:
        self.db.execute(delete(MetricDependency).where(MetricDependency.canonical_metric_id == canonical_metric_id))
        self.db.flush()

    def add_dependency(self, payload: dict) -> MetricDependency:
        dependency = MetricDependency(**payload)
        self.db.add(dependency)
        self.db.flush()
        return dependency

    def commit(self) -> None:
        self.db.commit()

    def prune_company_candidate_aliases(self, company_id: str) -> None:
        evidence_alias_subquery = select(MetricEvidence.alias_id).where(MetricEvidence.alias_id.is_not(None))
        stmt = delete(MetricAlias).where(
            MetricAlias.company_id == company_id,
            MetricAlias.source == "candidate_observed",
            ~MetricAlias.alias_id.in_(evidence_alias_subquery),
        )
        self.db.execute(stmt)
        self.db.flush()

    def prune_orphaned_candidate_metrics(self) -> None:
        alias_metric_subquery = select(MetricAlias.canonical_metric_id)
        evidence_metric_subquery = select(MetricEvidence.canonical_metric_id)
        stmt = delete(MetricDefinition).where(
            MetricDefinition.lifecycle_status == "candidate",
            ~MetricDefinition.canonical_metric_id.in_(alias_metric_subquery),
            ~MetricDefinition.canonical_metric_id.in_(evidence_metric_subquery),
        )
        self.db.execute(stmt)
        self.db.flush()
