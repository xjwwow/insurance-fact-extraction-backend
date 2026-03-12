from app.core.reference_data import is_placeholder_metric_name


class ValidationEngine:
    def validate_fact(self, fact: dict) -> dict:
        failed_rules: list[str] = []
        warnings: list[str] = []

        has_numeric = fact.get("value_numeric") is not None
        has_evidence = bool(fact.get("source_page_no") and fact.get("source_table_id"))
        resolution_conf = float(fact.get("resolution_confidence", 0.0))
        has_core_metric = bool(fact.get("canonical_metric_id")) and fact.get("metric_lifecycle_status") == "active"
        structure_ok = not is_placeholder_metric_name(fact.get("raw_metric_text")) and bool(
            fact.get("source_row_path") or fact.get("source_col_path")
        )

        score_parts = [
            1.0 if has_numeric else 0.0,
            1.0 if has_evidence else 0.0,
            1.0 if has_core_metric else 0.0,
            1.0 if structure_ok else 0.0,
            resolution_conf,
        ]
        score = sum(score_parts) / len(score_parts)

        if not has_numeric:
            failed_rules.append("NUMERIC_FORMAT")
        if not has_evidence:
            failed_rules.append("EVIDENCE_PRESENT")
        if not has_core_metric:
            warnings.append("metric_not_in_core_library")
        if not structure_ok:
            warnings.append("structure_incomplete")
        if resolution_conf == 0.0:
            warnings.append("metric_not_resolved")

        if score >= 0.8 and not failed_rules and has_core_metric and structure_ok:
            status = "PASS"
        elif score >= 0.4:
            status = "REVIEW"
        else:
            status = "FAIL"

        return {
            "validation_score": round(score, 4),
            "validation_status": status,
            "failed_rules": failed_rules,
            "warnings": warnings,
            "evidence_chain": {
                "source_page_no": fact.get("source_page_no"),
                "source_table_id": fact.get("source_table_id"),
                "source_row_path": fact.get("source_row_path"),
                "source_col_path": fact.get("source_col_path"),
                "source_cell_bbox": fact.get("source_cell_bbox"),
            },
        }

    def validate_batch(self, facts: list[dict]) -> list[dict]:
        return [self.validate_fact(fact) for fact in facts]

    def score_fact(self, fact: dict, rule_results: list[dict]) -> float:
        _ = rule_results
        result = self.validate_fact(fact)
        return float(result["validation_score"])
