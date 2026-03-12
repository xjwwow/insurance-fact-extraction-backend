from __future__ import annotations

import re
from decimal import Decimal

from app.core.parsers import parse_decimal
from app.core.reference_data import clean_metric_text, is_placeholder_metric_name


class FactExtractionService:
    _year_pattern = re.compile(r"(19|20)\d{2}")

    _invalid_tokens = {"", "-", "--", "—", "N/A", "n/a", "不适用", "无", "nan"}

    def extract_facts(self, table: dict, doc_meta: dict) -> list[dict]:
        facts: list[dict] = []
        cells = table.get("table_json", {}).get("cells", [])
        table_context = self._build_table_context(table)

        for cell in cells:
            fact = self.extract_cell_fact(table, cell, table_context)
            if fact is None:
                continue

            fact.update(
                {
                    "company_id": doc_meta["company_id"],
                    "document_id": doc_meta["document_id"],
                    "report_year": doc_meta["report_year"],
                    "report_type": doc_meta.get("report_type"),
                }
            )
            facts.append(fact)

        return facts

    def extract_cell_fact(self, table: dict, cell: dict, table_context: dict | None = None) -> dict | None:
        value_raw = str(cell.get("value_raw", "")).strip()
        if value_raw in self._invalid_tokens:
            return None

        row_path = [str(x).strip() for x in list(cell.get("row_path", [])) if str(x).strip()]
        col_path = [str(x).strip() for x in list(cell.get("col_path", [])) if str(x).strip()]

        row_sem = self._parse_row_semantics(row_path)
        col_sem = self._parse_col_semantics(col_path)

        unit_ctx = self._resolve_unit_context(
            table=table,
            row_path=row_path,
            col_path=col_path,
            table_context=table_context or self._build_table_context(table),
        )
        normalized = self.normalize_numeric_value(value_raw, unit_ctx)
        if not normalized["is_valid"]:
            return None

        metric_text = row_sem["metric_text"]
        statement_scope = row_sem["statement_scope"] or col_sem["statement_scope"] or unit_ctx.get("statement_scope") or "group"

        confidence = float(cell.get("confidence", 0.5))
        if metric_text != "unknown_metric" and not is_placeholder_metric_name(metric_text):
            confidence += 0.1
        if col_sem.get("year"):
            confidence += 0.05
        if unit_ctx.get("unit_std"):
            confidence += 0.05
        confidence = max(0.0, min(confidence, 1.0))

        period_type = col_sem.get("period_type") or "ANNUAL"
        period_label = col_sem.get("period_label") or "current_period"

        dimensions = {
            "period_label": period_label,
            "year": col_sem.get("year"),
            "row_path": row_path,
            "col_path": col_path,
            "unit_multiplier": str(unit_ctx.get("multiplier", Decimal("1"))),
            "parse_engine": table.get("parse_engine"),
        }

        return {
            "period_type": period_type,
            "statement_scope": statement_scope,
            "raw_metric_text": metric_text,
            "template_fingerprint": table.get("template_fingerprint"),
            "value_raw": value_raw,
            "value_numeric": normalized["value_numeric"],
            "unit_raw": unit_ctx.get("unit_raw"),
            "unit_std": unit_ctx.get("unit_std"),
            "currency": unit_ctx.get("currency") or table.get("currency_raw"),
            "dimensions": dimensions,
            "source_page_no": int(table.get("page_start", 1)),
            "source_table_id": table["table_id"],
            "source_row_path": row_path,
            "source_col_path": col_path,
            "source_cell_bbox": list(cell.get("bbox", [])),
            "source_text_snippet": f"{metric_text} | {period_label}",
            "extraction_method": "semantic_numeric_cell",
            "extraction_confidence": confidence,
        }

    def normalize_numeric_value(self, value_raw: str, unit_ctx: dict) -> dict:
        cleaned, negative, is_percent = self._clean_numeric_text(value_raw)
        if not cleaned:
            return {"is_valid": False, "value_numeric": None}

        value = parse_decimal(cleaned)
        if value is None:
            return {"is_valid": False, "value_numeric": None}

        if negative:
            value = -value

        multiplier: Decimal = unit_ctx.get("multiplier", Decimal("1"))
        unit_std = unit_ctx.get("unit_std")

        if is_percent and unit_std is None:
            unit_ctx["unit_std"] = "PERCENT"
            unit_std = "PERCENT"

        if unit_std != "PERCENT":
            value = value * multiplier

        return {
            "is_valid": True,
            "value_numeric": value,
        }

    def _parse_row_semantics(self, row_path: list[str]) -> dict:
        metric_text = "unknown_metric"
        statement_scope = None

        for token in row_path:
            candidate = self._clean_header_token(token)
            if not candidate:
                continue
            metric_text = candidate

        joined = " ".join(row_path)
        if any(key in joined for key in ("母公司", "本公司")):
            statement_scope = "company"
        elif any(key in joined for key in ("集团", "合并")):
            statement_scope = "group"

        return {
            "metric_text": metric_text,
            "statement_scope": statement_scope,
        }

    def _parse_col_semantics(self, col_path: list[str]) -> dict:
        joined = " ".join(col_path)
        lowered = joined.lower()

        period_type = "ANNUAL"
        if any(key in lowered for key in ("q1", "q2", "q3", "q4", "季度", "1-3月", "4-6月", "7-9月", "10-12月")):
            period_type = "QUARTER"
        elif any(key in lowered for key in ("半年度", "半年", "上半年", "下半年")):
            period_type = "HALF_YEAR"
        elif any(key in lowered for key in ("月", "month")):
            period_type = "MONTHLY"

        year_match = self._year_pattern.search(joined)
        year = int(year_match.group(0)) if year_match else None

        statement_scope = None
        if any(key in joined for key in ("母公司", "本公司")):
            statement_scope = "company"
        elif any(key in joined for key in ("集团", "合并")):
            statement_scope = "group"

        return {
            "period_type": period_type,
            "year": year,
            "period_label": joined or "current_period",
            "statement_scope": statement_scope,
        }

    def _resolve_unit_context(self, table: dict, row_path: list[str], col_path: list[str], table_context: dict) -> dict:
        unit_raw = table.get("unit_raw") or table_context.get("unit_raw")
        unit_std = table_context.get("unit_std")
        multiplier = table_context.get("multiplier", Decimal("1"))
        currency = table_context.get("currency")

        candidates = [unit_raw, table.get("table_title_raw"), table.get("table_title_norm")] + row_path + col_path
        for candidate in candidates:
            if not candidate:
                continue
            parsed = self._parse_unit_candidate(str(candidate))
            if parsed["unit_std"]:
                unit_std = parsed["unit_std"]
                multiplier = parsed["multiplier"]
            if parsed["currency"] and not currency:
                currency = parsed["currency"]

        return {
            "unit_raw": unit_raw,
            "unit_std": unit_std,
            "multiplier": multiplier,
            "currency": currency,
        }

    def _build_table_context(self, table: dict) -> dict:
        unit_raw = table.get("unit_raw")
        unit_std = None
        multiplier = Decimal("1")
        currency = None

        for candidate in (unit_raw, table.get("table_title_raw"), table.get("table_title_norm")):
            if not candidate:
                continue
            parsed = self._parse_unit_candidate(str(candidate))
            if parsed["unit_std"]:
                unit_std = parsed["unit_std"]
                multiplier = parsed["multiplier"]
            if parsed["currency"] and not currency:
                currency = parsed["currency"]

        return {
            "unit_raw": unit_raw,
            "unit_std": unit_std,
            "multiplier": multiplier,
            "currency": currency,
        }

    def _parse_unit_candidate(self, text: str) -> dict:
        normalized = text.replace(" ", "").replace("（", "(").replace("）", ")")

        currency = None
        if any(x in normalized for x in ("人民币", "RMB", "CNY", "¥")):
            currency = "CNY"
        elif any(x in normalized for x in ("美元", "USD", "$")):
            currency = "USD"
        elif any(x in normalized for x in ("港元", "HKD")):
            currency = "HKD"

        mappings: list[tuple[tuple[str, ...], str, Decimal]] = [
            (("亿元",), "CNY_YI", Decimal("100000000")),
            (("百万元",), "CNY_MILLION", Decimal("1000000")),
            (("万元",), "CNY_10K", Decimal("10000")),
            (("千元",), "CNY_1K", Decimal("1000")),
            (("元",), "CNY", Decimal("1")),
            (("万股",), "SHARES_10K", Decimal("10000")),
            (("股",), "SHARES", Decimal("1")),
            (("%", "％", "百分比", "增长率"), "PERCENT", Decimal("1")),
        ]

        for keys, unit_std, multiplier in mappings:
            if any(key in normalized for key in keys):
                return {
                    "unit_std": unit_std,
                    "multiplier": multiplier,
                    "currency": currency,
                }

        return {
            "unit_std": None,
            "multiplier": Decimal("1"),
            "currency": currency,
        }

    def _clean_header_token(self, text: str) -> str:
        cleaned = clean_metric_text(text)
        if is_placeholder_metric_name(cleaned):
            return ""
        return cleaned.strip(" :：*·")

    def _clean_numeric_text(self, value_raw: str) -> tuple[str, bool, bool]:
        text = value_raw.strip().replace("，", ",").replace("％", "%")
        text = text.replace("−", "-").replace("－", "-").replace("—", "-")
        text = text.replace(" ", "")

        if text in self._invalid_tokens:
            return "", False, False

        is_percent = text.endswith("%")
        if is_percent:
            text = text[:-1]

        negative = False
        if (text.startswith("(") and text.endswith(")")) or (text.startswith("（") and text.endswith("）")):
            negative = True
            text = text[1:-1]

        text = text.replace("（", "").replace("）", "")
        text = text.replace("*", "")

        if text.startswith("+"):
            text = text[1:]

        return text, negative, is_percent
