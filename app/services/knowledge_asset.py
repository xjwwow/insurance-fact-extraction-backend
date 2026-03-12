from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.core.reference_data import (
    METRIC_LIFECYCLE_ACTIVE,
    METRIC_LIFECYCLE_CANDIDATE,
    clean_metric_text,
    is_placeholder_metric_name,
)
from app.models.fact import Fact
from app.repositories.documents import DocumentRepository
from app.repositories.facts import FactRepository
from app.repositories.metrics import MetricRepository
from app.services.metric_resolution import MetricResolutionService


class KnowledgeAssetService:
    _date_like_pattern = re.compile(r"^(19|20)\d{2}(年)?([:/.-]\d{1,2}([:/.-]\d{1,2})?)?$")
    _keyword_pattern = re.compile(r"(资产|负债|收入|利润|费用|保费|投资|价值|权益|偿付|成本|现金|股本|分红|赔付|税金|收益|规模|客户|合同|内含)")
    _bad_phrase_pattern = re.compile(r"(以下简称|本公司|本集团|年报|附注|个人代理|银行保险|公司直销|产品|注册用户|覆盖全国|拓客|服务能力)")
    _sentence_punctuation_pattern = re.compile(r"[。；;！？!?]")
    _corp_suffix_pattern = re.compile(r"(inc\.?|limited|ltd\.?|corp\.?|holdings?|s\.?a\.?)", re.IGNORECASE)

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
        self.seed_file_path = Path(__file__).resolve().parents[2] / "data" / "metric_library" / "insurance_metrics.json"

    def bootstrap_metric_library(self) -> dict:
        entries = self._load_seed_entries()
        metrics_created = 0
        aliases_created = 0

        for entry in entries:
            payload = {
                "canonical_metric_id": entry["canonical_metric_id"],
                "metric_code": entry["metric_code"],
                "metric_name": entry["metric_name"],
                "metric_name_en": entry.get("metric_name_en"),
                "category": entry.get("category"),
                "subcategory": entry.get("subcategory"),
                "definition": entry.get("definition"),
                "formula_expression": entry.get("formula_expression"),
                "value_type": entry.get("value_type"),
                "default_unit": entry.get("default_unit"),
                "applicable_scope": entry.get("applicable_scope"),
                "applicable_statement_types": entry.get("applicable_statement_types"),
                "is_active": True,
                "lifecycle_status": METRIC_LIFECYCLE_ACTIVE,
                "version": 1,
            }
            _, created = self.metric_repository.upsert_metric_definition(payload)
            if created:
                metrics_created += 1

            for alias_text in entry.get("aliases", []):
                alias_payload = {
                    "alias_id": self._stable_alias_id(entry["canonical_metric_id"], alias_text, None, None),
                    "canonical_metric_id": entry["canonical_metric_id"],
                    "alias_text": alias_text,
                    "alias_lang": "zh-CN",
                    "company_id": None,
                    "report_type": None,
                    "valid_from_year": None,
                    "valid_to_year": None,
                    "confidence": 0.98,
                    "source": "seed",
                }
                _, alias_created = self.metric_repository.upsert_alias(alias_payload)
                if alias_created:
                    aliases_created += 1

        self.metric_repository.commit()
        return {
            "metrics_created": metrics_created,
            "aliases_created": aliases_created,
            "seed_entries": len(entries),
        }

    def build_metric_library_for_document(self, document_id: str) -> dict:
        document = self.document_repository.get(document_id)
        if document is None:
            raise ValueError(f"document not found: {document_id}")

        self.bootstrap_metric_library()
        self.metric_repository.prune_company_candidate_aliases(document.company_id)
        self.metric_repository.prune_orphaned_candidate_metrics()
        facts = self.fact_repository.list_by_document(document_id)
        raw_metric_stats = self._collect_metric_text_stats(facts)

        metrics_created = 0
        aliases_created = 0
        evidences_created = 0
        facts_linked = 0

        for fact in facts:
            raw_metric_text = self._clean_metric_text(fact.metric_alias_raw or "")
            if not raw_metric_text:
                continue

            candidate = {
                "raw_metric_text": raw_metric_text,
                "company_id": fact.company_id,
                "report_year": fact.report_year,
                "report_type": document.report_type,
                "statement_scope": fact.statement_scope,
            }
            resolved = self.metric_resolution_service.resolve_metric(candidate)
            canonical_metric_id = resolved.get("canonical_metric_id")
            metric_name_std = resolved.get("metric_name_std")
            resolution_confidence = float(resolved.get("resolution_confidence", 0.0))
            metric_lifecycle_status = resolved.get("metric_lifecycle_status")
            alias_source = "document_observed"

            if not canonical_metric_id:
                if not self._should_learn_metric(raw_metric_text, raw_metric_stats.get(raw_metric_text, {})):
                    continue
                candidate_metric, metric_created = self._get_or_create_candidate_metric(raw_metric_text, fact, document.report_type)
                canonical_metric_id = candidate_metric.canonical_metric_id
                metric_name_std = candidate_metric.metric_name
                metric_lifecycle_status = candidate_metric.lifecycle_status
                resolution_confidence = max(resolution_confidence, 0.58)
                alias_source = "candidate_observed"
                if metric_created:
                    metrics_created += 1

            alias_payload = {
                "alias_id": self._stable_alias_id(canonical_metric_id, raw_metric_text, fact.company_id, document.report_type),
                "canonical_metric_id": canonical_metric_id,
                "alias_text": raw_metric_text,
                "alias_lang": "zh-CN",
                "company_id": fact.company_id,
                "report_type": document.report_type,
                "valid_from_year": fact.report_year,
                "valid_to_year": fact.report_year,
                "confidence": round(max(resolution_confidence, 0.6), 4),
                "source": alias_source,
            }
            alias, alias_created = self.metric_repository.upsert_alias(alias_payload)
            if alias_created:
                aliases_created += 1

            evidence_payload = {
                "evidence_id": self._stable_evidence_id(fact.fact_id),
                "canonical_metric_id": canonical_metric_id,
                "alias_id": alias.alias_id,
                "fact_id": fact.fact_id,
                "company_id": fact.company_id,
                "document_id": fact.document_id,
                "source_table_id": fact.source_table_id,
                "source_page_no": fact.source_page_no,
                "raw_metric_text": raw_metric_text,
                "normalized_metric_text": self.metric_resolution_service.normalize_metric_text(raw_metric_text),
                "statement_scope": fact.statement_scope,
                "period_type": fact.period_type,
                "unit_std": fact.unit_std,
                "evidence_json": {
                    "source_row_path": fact.source_row_path,
                    "source_col_path": fact.source_col_path,
                    "source_cell_bbox": fact.source_cell_bbox,
                    "source_text_snippet": fact.source_text_snippet,
                    "dimensions": fact.dimensions_json,
                },
            }
            _, evidence_created = self.metric_repository.upsert_evidence(evidence_payload)
            if evidence_created:
                evidences_created += 1

            if (
                fact.canonical_metric_id != canonical_metric_id
                or fact.metric_name_std != metric_name_std
                or (fact.dimensions_json or {}).get("metric_lifecycle_status") != metric_lifecycle_status
            ):
                fact.canonical_metric_id = canonical_metric_id
                fact.metric_name_std = metric_name_std
                fact.dimensions_json = {**(fact.dimensions_json or {}), "metric_lifecycle_status": metric_lifecycle_status}
                facts_linked += 1

        self.fact_repository.commit()
        return {
            "document_id": document_id,
            "facts_scanned": len(facts),
            "facts_linked": facts_linked,
            "metrics_created": metrics_created,
            "aliases_created": aliases_created,
            "evidences_created": evidences_created,
        }

    def _get_or_create_candidate_metric(self, raw_metric_text: str, fact: Fact, report_type: str) -> tuple[object, bool]:
        normalized = self.metric_resolution_service.normalize_metric_text(raw_metric_text)
        digest = hashlib.sha1(f"{fact.company_id}:{normalized}".encode("utf-8")).hexdigest()
        canonical_metric_id = f"metric_candidate_{digest[:16]}"
        metric_code = f"CANDIDATE_{digest[:12].upper()}"

        payload = {
            "canonical_metric_id": canonical_metric_id,
            "metric_code": metric_code,
            "metric_name": raw_metric_text,
            "metric_name_en": None,
            "category": "文档学习",
            "subcategory": fact.company_id,
            "definition": f"从 {fact.company_id} {fact.report_year} 年报自动学习到的指标别名。",
            "formula_expression": None,
            "value_type": "RATIO" if fact.unit_std == "PERCENT" else "AMOUNT",
            "default_unit": fact.unit_std or fact.unit_raw,
            "applicable_scope": {"values": [fact.statement_scope] if fact.statement_scope else []},
            "applicable_statement_types": {"values": [report_type]},
            "is_active": True,
            "lifecycle_status": METRIC_LIFECYCLE_CANDIDATE,
            "version": 1,
        }
        return self.metric_repository.upsert_metric_definition(payload)

    def _load_seed_entries(self) -> list[dict]:
        return json.loads(self.seed_file_path.read_text(encoding="utf-8"))

    def _collect_metric_text_stats(self, facts: list[Fact]) -> dict[str, dict]:
        counts: dict[str, dict] = {}
        for fact in facts:
            text = self._clean_metric_text(fact.metric_alias_raw or "")
            if not text:
                continue
            stats = counts.setdefault(text, {"count": 0, "pages": set(), "periods": set(), "units": set()})
            stats["count"] += 1
            if fact.source_page_no is not None:
                stats["pages"].add(fact.source_page_no)
            if fact.period_type:
                stats["periods"].add(fact.period_type)
            if fact.unit_std or fact.unit_raw:
                stats["units"].add(fact.unit_std or fact.unit_raw)
        return counts

    @staticmethod
    def _clean_metric_text(text: str) -> str:
        return clean_metric_text(text)

    def _should_learn_metric(self, text: str, stats: dict) -> bool:
        compact = text.replace(" ", "")
        if len(compact) < 2 or len(compact) > 36:
            return False
        if is_placeholder_metric_name(compact):
            return False
        if "cid:" in compact.lower():
            return False
        if self._bad_phrase_pattern.search(compact):
            return False
        if self._date_like_pattern.fullmatch(compact):
            return False
        if compact.startswith("(") and compact.endswith(")"):
            return False
        if self._sentence_punctuation_pattern.search(compact):
            return False
        if compact.count("。") >= 2:
            return False
        if self._corp_suffix_pattern.search(compact):
            return False
        if not re.search(r"[\u4e00-\u9fffA-Za-z%]", compact):
            return False
        return self._score_learn_metric_candidate(compact, stats) >= 0.8

    def _score_learn_metric_candidate(self, compact: str, stats: dict) -> float:
        count = int(stats.get("count", 0))
        page_count = len(stats.get("pages", set()))
        unit_count = len(stats.get("units", set()))

        score = 0.0
        score += min(count * 0.12, 0.36)
        score += min(page_count * 0.04, 0.08)

        if 3 <= len(compact) <= 18:
            score += 0.12
        elif len(compact) <= 24:
            score += 0.06

        if self._keyword_pattern.search(compact):
            score += 0.22
        if unit_count > 0:
            score += 0.05

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", compact))
        ascii_chars = len(re.findall(r"[A-Za-z]", compact))
        if chinese_chars >= 4:
            score += 0.08
        if ascii_chars >= 4:
            score -= 0.12

        if re.search(r"[A-Za-z]{3,}", compact):
            score -= 0.06
        if re.search(r"\d{4,}", compact):
            score -= 0.08
        if compact.startswith("其中"):
            score -= 0.08
        if compact.endswith("分析") or compact.endswith("情况"):
            score -= 0.08
        if "-" in compact:
            score -= 0.08
        if "以下简称" in compact:
            score -= 0.25
        if not self._keyword_pattern.search(compact) and count < 3:
            score -= 0.2

        return score

    @staticmethod
    def _stable_alias_id(canonical_metric_id: str, alias_text: str, company_id: str | None, report_type: str | None) -> str:
        raw = f"{canonical_metric_id}|{company_id or '*'}|{report_type or '*'}|{alias_text.strip().lower()}"
        return f"alias_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"

    @staticmethod
    def _stable_evidence_id(fact_id: str) -> str:
        return f"mev_{hashlib.sha1(fact_id.encode('utf-8')).hexdigest()[:20]}"
