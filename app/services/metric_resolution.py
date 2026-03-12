from __future__ import annotations

import re

from app.core.reference_data import clean_metric_text
from app.repositories.metrics import MetricRepository


class MetricResolutionService:
    _space_pattern = re.compile(r"\s+")

    def __init__(self, metric_repository: MetricRepository | None = None) -> None:
        self.metric_repository = metric_repository

    def resolve_metric(self, candidate_fact: dict) -> dict:
        normalized_metric_text = self.normalize_metric_text(candidate_fact.get("raw_metric_text", ""))
        alias_matches = self.search_alias_candidates(
            raw_metric_text=candidate_fact.get("raw_metric_text", ""),
            company_id=candidate_fact.get("company_id"),
            report_type=candidate_fact.get("report_type"),
            report_year=candidate_fact.get("report_year"),
            statement_scope=candidate_fact.get("statement_scope"),
        )
        historical_matches = self.search_historical_templates(
            table_fingerprint=candidate_fact.get("template_fingerprint", ""),
            company_id=candidate_fact.get("company_id", ""),
            normalized_metric_text=normalized_metric_text,
        )

        scored: dict[str, dict] = {}
        for match in alias_matches:
            scored[match["canonical_metric_id"]] = {
                **match,
                "score": match["score"],
                "sources": ["alias"],
            }

        for match in historical_matches:
            current = scored.get(match["canonical_metric_id"])
            if current is None:
                scored[match["canonical_metric_id"]] = {
                    "canonical_metric_id": match["canonical_metric_id"],
                    "metric_name": match["metric_name"],
                    "metric_code": match["metric_code"],
                    "alias_text": match["raw_metric_text"],
                    "alias_source": "historical_template",
                    "score": match["score"],
                    "sources": ["historical_template"],
                }
                continue

            current["score"] = round(min(current["score"] + match["score"], 1.0), 4)
            current["sources"] = sorted(set(current["sources"] + ["historical_template"]))

        results = sorted(scored.values(), key=lambda item: item["score"], reverse=True)
        if results:
            best = results[0]
            return {
                "canonical_metric_id": best["canonical_metric_id"],
                "metric_name_std": best["metric_name"],
                "metric_lifecycle_status": best.get("lifecycle_status"),
                "resolution_confidence": best["score"],
                "resolution_trace": {
                    "normalized_metric_text": normalized_metric_text,
                    "alias_matches": alias_matches,
                    "historical_matches": historical_matches,
                    "scored_candidates": results,
                },
            }

        return {
            "canonical_metric_id": None,
            "metric_name_std": None,
            "metric_lifecycle_status": None,
            "resolution_confidence": 0.0,
            "resolution_trace": {
                "normalized_metric_text": normalized_metric_text,
                "alias_matches": [],
                "historical_matches": [],
                "scored_candidates": [],
            },
        }

    def search_alias_candidates(
        self,
        raw_metric_text: str,
        company_id: str | None = None,
        report_type: str | None = None,
        report_year: int | None = None,
        statement_scope: str | None = None,
        include_learned: bool = True,
    ) -> list[dict]:
        if self.metric_repository is None:
            return []

        normalized = self.normalize_metric_text(raw_metric_text)
        if not normalized:
            return []

        rows = self.metric_repository.search_aliases(
            raw_metric_text=normalized,
            company_id=company_id,
            report_type=report_type,
            report_year=report_year,
            limit=12,
        )

        results: list[dict] = []
        for alias, metric in rows:
            if not include_learned and metric.lifecycle_status != "active":
                continue

            alias_norm = self.normalize_metric_text(alias.alias_text or "")
            metric_norm = self.normalize_metric_text(metric.metric_name or "")
            score = 0.0

            if alias_norm == normalized:
                score += 0.65
            elif normalized.startswith(alias_norm) or alias_norm.startswith(normalized):
                score += 0.45
            elif normalized and (normalized in alias_norm or alias_norm in normalized):
                score += 0.3

            if metric_norm == normalized:
                score += 0.25

            score += min(float(alias.confidence or 0.0), 0.2)

            if alias.company_id == company_id:
                score += 0.08
            elif alias.company_id is None:
                score += 0.03

            if report_type and alias.report_type == report_type:
                score += 0.04
            elif alias.report_type is None:
                score += 0.01

            if report_year is not None:
                if alias.valid_from_year is None and alias.valid_to_year is None:
                    score += 0.01
                elif (alias.valid_from_year is None or alias.valid_from_year <= report_year) and (
                    alias.valid_to_year is None or alias.valid_to_year >= report_year
                ):
                    score += 0.04

            applicable_scope = (metric.applicable_scope or {}).get("values", [])
            if statement_scope and applicable_scope:
                if statement_scope in applicable_scope:
                    score += 0.04
                else:
                    score -= 0.08

            applicable_statement_types = (metric.applicable_statement_types or {}).get("values", [])
            if report_type and applicable_statement_types:
                if report_type in applicable_statement_types:
                    score += 0.03
                else:
                    score -= 0.05

            results.append(
                {
                    "canonical_metric_id": metric.canonical_metric_id,
                    "metric_name": metric.metric_name,
                    "metric_code": metric.metric_code,
                    "lifecycle_status": metric.lifecycle_status,
                    "alias_text": alias.alias_text,
                    "alias_source": alias.source,
                    "score": round(max(min(score, 1.0), 0.0), 4),
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results

    def search_historical_templates(
        self,
        table_fingerprint: str,
        company_id: str,
        normalized_metric_text: str,
    ) -> list[dict]:
        if self.metric_repository is None or not table_fingerprint or not company_id:
            return []

        rows = self.metric_repository.search_historical_template_candidates(
            company_id=company_id,
            template_fingerprint=table_fingerprint,
            normalized_metric_text=normalized_metric_text,
            limit=50,
        )

        aggregated: dict[str, dict] = {}
        for evidence, metric, table in rows:
            entry = aggregated.setdefault(
                metric.canonical_metric_id,
                {
                    "canonical_metric_id": metric.canonical_metric_id,
                    "metric_name": metric.metric_name,
                    "metric_code": metric.metric_code,
                    "raw_metric_text": evidence.raw_metric_text,
                    "score": 0.0,
                    "evidence_count": 0,
                    "pages": set(),
                    "table_ids": set(),
                },
            )
            entry["evidence_count"] += 1
            entry["pages"].add(evidence.source_page_no)
            entry["table_ids"].add(table.table_id)

            if evidence.normalized_metric_text == normalized_metric_text:
                entry["score"] += 0.34
            elif normalized_metric_text and (
                evidence.normalized_metric_text.startswith(normalized_metric_text)
                or normalized_metric_text.startswith(evidence.normalized_metric_text)
            ):
                entry["score"] += 0.22
            else:
                entry["score"] += 0.1

        results: list[dict] = []
        for value in aggregated.values():
            evidence_bonus = min(value["evidence_count"] * 0.08, 0.28)
            score = round(min(value["score"] + evidence_bonus, 0.92), 4)
            results.append(
                {
                    "canonical_metric_id": value["canonical_metric_id"],
                    "metric_name": value["metric_name"],
                    "metric_code": value["metric_code"],
                    "lifecycle_status": "active",
                    "raw_metric_text": value["raw_metric_text"],
                    "score": score,
                    "evidence_count": value["evidence_count"],
                    "pages": sorted(page for page in value["pages"] if page is not None),
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return results

    @classmethod
    def normalize_metric_text(cls, text: str) -> str:
        normalized = clean_metric_text(text)
        normalized = normalized.replace("－", "-").replace("—", "-").replace("–", "-")
        normalized = normalized.replace("％", "%")
        normalized = normalized.replace("*", "")
        normalized = cls._space_pattern.sub("", normalized)
        normalized = normalized.strip(" :：-_")
        return normalized.lower()
