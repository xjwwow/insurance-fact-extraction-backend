from app.core.reference_data import (
    METRIC_LIFECYCLE_DISMISSED,
    METRIC_LIFECYCLE_MERGED,
    clean_metric_text,
    is_placeholder_metric_name,
)
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.services.metric_resolution import MetricResolutionService


class MetricReviewService:
    def __init__(
        self,
        metric_repository: MetricRepository,
        fact_repository: FactRepository,
    ) -> None:
        self.metric_repository = metric_repository
        self.fact_repository = fact_repository
        self.metric_resolution_service = MetricResolutionService(metric_repository)

    def list_review_queue(self, company_id: str | None = None, limit: int = 100) -> list[dict]:
        metrics = self.metric_repository.list_candidate_metrics(company_id=company_id, limit=limit)
        queue: list[dict] = []

        for metric in metrics:
            if is_placeholder_metric_name(metric.metric_name):
                continue

            aliases = self.metric_repository.list_aliases(metric.canonical_metric_id)
            evidences = self.metric_repository.list_evidences(metric.canonical_metric_id, limit=200)
            facts = self.fact_repository.list_by_metric(metric.canonical_metric_id)

            company = company_id
            if company is None:
                company = next((alias.company_id for alias in aliases if alias.company_id), None)
            if company is None:
                company = next((evidence.company_id for evidence in evidences if evidence.company_id), None)

            suggested_targets = self.metric_resolution_service.search_alias_candidates(
                raw_metric_text=metric.metric_name,
                company_id=company,
                report_type="annual_report",
                include_learned=False,
            )[:5]

            unique_pages = sorted({evidence.source_page_no for evidence in evidences if evidence.source_page_no is not None})[:20]
            sample_aliases = sorted({alias.alias_text for alias in aliases if alias.alias_text})[:8]
            confidence_score = self._score_review_candidate(metric.metric_name, len(evidences), len(sample_aliases))
            if confidence_score < 0.62:
                continue

            queue.append(
                {
                    "canonical_metric_id": metric.canonical_metric_id,
                    "metric_code": metric.metric_code,
                    "metric_name": metric.metric_name,
                    "company_id": company,
                    "alias_count": len(aliases),
                    "evidence_count": len(evidences),
                    "fact_count": len(facts),
                    "document_count": len({evidence.document_id for evidence in evidences if evidence.document_id}),
                    "pages": unique_pages,
                    "sample_aliases": sample_aliases,
                    "confidence_score": confidence_score,
                    "suggested_targets": [
                        {
                            "canonical_metric_id": item["canonical_metric_id"],
                            "metric_code": item["metric_code"],
                            "metric_name": item["metric_name"],
                            "score": item["score"],
                        }
                        for item in suggested_targets
                    ],
                }
            )

        queue.sort(key=lambda item: (item["confidence_score"], item["evidence_count"]), reverse=True)
        return queue

    def merge_metric(
        self,
        source_canonical_metric_id: str,
        target_canonical_metric_id: str,
        reviewer: str,
        comment: str | None = None,
    ) -> dict:
        source = self.metric_repository.get_with_related(source_canonical_metric_id)
        target = self.metric_repository.get_with_related(target_canonical_metric_id)
        if source is None:
            raise ValueError(f"source metric not found: {source_canonical_metric_id}")
        if target is None:
            raise ValueError(f"target metric not found: {target_canonical_metric_id}")
        if source.canonical_metric_id == target.canonical_metric_id:
            raise ValueError("source and target metric must be different")

        facts = self.fact_repository.list_by_metric(source.canonical_metric_id)
        evidences = self.metric_repository.list_evidences(source.canonical_metric_id, limit=5000)
        aliases = self.metric_repository.list_aliases(source.canonical_metric_id)

        if source.metric_name:
            existing_root_alias = self.metric_repository.find_alias(
                canonical_metric_id=target.canonical_metric_id,
                alias_text=source.metric_name,
                company_id=None,
                report_type=None,
            )
            if existing_root_alias is None:
                self.metric_repository.upsert_alias(
                    {
                        "alias_id": f"alias_merge_{source.canonical_metric_id[-12:]}_{target.canonical_metric_id[-8:]}",
                        "canonical_metric_id": target.canonical_metric_id,
                        "alias_text": source.metric_name,
                        "alias_lang": "zh-CN",
                        "company_id": None,
                        "report_type": None,
                        "valid_from_year": None,
                        "valid_to_year": None,
                        "confidence": 0.9,
                        "source": "review_merged",
                    }
                )

        merged_alias_count = 0
        for alias in aliases:
            existing = self.metric_repository.find_alias(
                canonical_metric_id=target.canonical_metric_id,
                alias_text=alias.alias_text,
                company_id=alias.company_id,
                report_type=alias.report_type,
            )
            if existing is not None and existing.alias_id != alias.alias_id:
                self.metric_repository.reassign_evidence_alias(alias.alias_id, existing.alias_id)
                self.metric_repository.delete_alias(alias)
            else:
                alias.canonical_metric_id = target.canonical_metric_id
                alias.source = "review_merged"
                self.metric_repository.save_alias(alias)
            merged_alias_count += 1

        for evidence in evidences:
            evidence.canonical_metric_id = target.canonical_metric_id
            self.metric_repository.save_evidence(evidence)

        for fact in facts:
            fact.canonical_metric_id = target.canonical_metric_id
            fact.metric_name_std = target.metric_name
            self.fact_repository.db.add(fact)

        source.is_active = False
        source.lifecycle_status = METRIC_LIFECYCLE_MERGED
        note = f"[merged by {reviewer}] -> {target.canonical_metric_id}"
        if comment:
            note = f"{note} | {comment}"
        source.definition = "\n".join(part for part in [source.definition, note] if part)
        self.metric_repository.save_metric(source)
        self.fact_repository.commit()
        self.metric_repository.commit()

        return {
            "source_canonical_metric_id": source.canonical_metric_id,
            "target_canonical_metric_id": target.canonical_metric_id,
            "action": "merge",
            "affected_facts": len(facts),
            "affected_aliases": merged_alias_count,
            "affected_evidences": len(evidences),
        }

    def dismiss_metric(self, source_canonical_metric_id: str, reviewer: str, comment: str | None = None) -> dict:
        source = self.metric_repository.get_with_related(source_canonical_metric_id)
        if source is None:
            raise ValueError(f"metric not found: {source_canonical_metric_id}")

        evidences = self.metric_repository.list_evidences(source.canonical_metric_id, limit=5000)
        facts = self.fact_repository.list_by_metric(source.canonical_metric_id)
        for fact in facts:
            fact.canonical_metric_id = None
            fact.metric_name_std = None
            self.fact_repository.db.add(fact)

        source.is_active = False
        source.lifecycle_status = METRIC_LIFECYCLE_DISMISSED
        note = f"[dismissed by {reviewer}]"
        if comment:
            note = f"{note} | {comment}"
        source.definition = "\n".join(part for part in [source.definition, note] if part)
        self.metric_repository.save_metric(source)
        self.fact_repository.commit()
        self.metric_repository.commit()

        return {
            "source_canonical_metric_id": source.canonical_metric_id,
            "target_canonical_metric_id": None,
            "action": "dismiss",
            "affected_facts": len(facts),
            "affected_aliases": len(self.metric_repository.list_aliases(source.canonical_metric_id)),
            "affected_evidences": len(evidences),
        }

    @staticmethod
    def _score_review_candidate(metric_name: str, evidence_count: int, alias_count: int) -> float:
        score = 0.0
        score += min(evidence_count * 0.05, 0.45)
        score += min(alias_count * 0.07, 0.21)
        compact = clean_metric_text(metric_name).replace(" ", "")
        if 3 <= len(compact) <= 18:
            score += 0.16
        if any(token in compact for token in ("收入", "利润", "收益", "保费", "价值", "成本", "现金", "偿付", "资产", "负债")):
            score += 0.18
        if any(token in compact for token in ("以下简称", "产品", "注册用户", "渠道")):
            score -= 0.35
        return round(max(min(score, 1.0), 0.0), 4)
