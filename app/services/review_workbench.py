from app.core.ids import generate_id
from app.core.parsers import parse_decimal
from app.models.enums import ReviewStatus
from app.models.validation import ReviewLog
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.repositories.review import ReviewLogRepository


class ReviewWorkbenchService:
    def __init__(
        self,
        fact_repository: FactRepository,
        review_log_repository: ReviewLogRepository,
        metric_repository: MetricRepository,
    ) -> None:
        self.fact_repository = fact_repository
        self.review_log_repository = review_log_repository
        self.metric_repository = metric_repository

    def list_review_queue(
        self,
        company_id: str | None = None,
        report_year: int | None = None,
        limit: int = 100,
    ):
        return self.fact_repository.list(
            company_id=company_id,
            report_year=report_year,
            review_status=ReviewStatus.PENDING.value,
            limit=limit,
        )

    def approve_fact(self, fact_id: str, reviewer: str, comment: str | None = None):
        fact = self._get_fact_or_raise(fact_id)
        old_value = {"review_status": fact.review_status, "reviewer_comment": fact.reviewer_comment}
        fact.review_status = ReviewStatus.APPROVED.value
        fact.reviewer_comment = comment
        saved = self.fact_repository.save(fact)
        self._write_log(fact_id, "approve", old_value, {"review_status": saved.review_status}, reviewer, comment)
        return saved

    def correct_fact(self, fact_id: str, new_value: str, reviewer: str, comment: str | None = None):
        fact = self._get_fact_or_raise(fact_id)
        old_value = {"value_raw": fact.value_raw, "value_numeric": str(fact.value_numeric) if fact.value_numeric is not None else None}
        fact.value_raw = new_value
        parsed = parse_decimal(new_value)
        fact.value_numeric = parsed
        fact.review_status = ReviewStatus.CORRECTED.value
        fact.reviewer_comment = comment
        saved = self.fact_repository.save(fact)
        new_value_json = {"value_raw": saved.value_raw, "value_numeric": str(saved.value_numeric) if saved.value_numeric is not None else None}
        self._write_log(fact_id, "correct", old_value, new_value_json, reviewer, comment)
        return saved

    def remap_metric(
        self,
        fact_id: str,
        canonical_metric_id: str,
        reviewer: str,
        metric_name_std: str | None = None,
        comment: str | None = None,
    ):
        fact = self._get_fact_or_raise(fact_id)
        metric = self.metric_repository.get(canonical_metric_id)
        if metric is None:
            raise ValueError(f"metric not found: {canonical_metric_id}")

        old_value = {
            "canonical_metric_id": fact.canonical_metric_id,
            "metric_name_std": fact.metric_name_std,
        }
        fact.canonical_metric_id = canonical_metric_id
        fact.metric_name_std = metric_name_std or metric.metric_name
        fact.review_status = ReviewStatus.REMAPPED.value
        fact.reviewer_comment = comment
        saved = self.fact_repository.save(fact)
        self._write_log(
            fact_id,
            "remap_metric",
            old_value,
            {
                "canonical_metric_id": saved.canonical_metric_id,
                "metric_name_std": saved.metric_name_std,
            },
            reviewer,
            comment,
        )
        return saved

    def _get_fact_or_raise(self, fact_id: str):
        fact = self.fact_repository.get(fact_id)
        if fact is None:
            raise ValueError(f"fact not found: {fact_id}")
        return fact

    def _write_log(
        self,
        fact_id: str,
        action: str,
        old_value_json: dict | None,
        new_value_json: dict | None,
        reviewer: str,
        comment: str | None,
    ) -> ReviewLog:
        review_log = ReviewLog(
            review_log_id=generate_id("rvw"),
            fact_id=fact_id,
            action=action,
            old_value_json=old_value_json,
            new_value_json=new_value_json,
            reviewer=reviewer,
            comment=comment,
        )
        return self.review_log_repository.create(review_log)
