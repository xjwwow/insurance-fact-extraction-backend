import hashlib
import json

from app.core.ids import generate_id


class CanonicalizationService:
    def build_canonical_table(self, raw_table: dict, page_context: dict) -> dict:
        table = {
            "table_id": generate_id("tbl"),
            "document_id": page_context["document_id"],
            "page_start": int(raw_table.get("page_no", 1)),
            "page_end": int(raw_table.get("page_no", 1)),
            "table_title_raw": raw_table.get("table_title_raw"),
            "table_title_norm": raw_table.get("table_title_norm"),
            "unit_raw": raw_table.get("unit_raw"),
            "currency_raw": raw_table.get("currency_raw"),
            "table_json": {
                "row_headers": raw_table.get("row_headers", []),
                "col_headers": raw_table.get("col_headers", []),
                "cells": raw_table.get("cells", []),
                "footnotes": raw_table.get("footnotes", []),
            },
            "parse_engine": raw_table.get("parse_engine", "unknown"),
            "parse_confidence": raw_table.get("parse_confidence", 0.0),
            "parse_trace_json": raw_table.get("parse_trace", {}),
        }
        table["template_fingerprint"] = self.compute_fingerprint(table)
        return self.normalize_headers(table)

    def normalize_headers(self, table: dict) -> dict:
        title = table.get("table_title_norm") or table.get("table_title_raw") or ""
        table["table_title_norm"] = title.strip().lower().replace(" ", "_")
        return table

    def compute_fingerprint(self, table: dict) -> str:
        payload = {
            "title": table.get("table_title_norm") or table.get("table_title_raw"),
            "row_headers": table.get("table_json", {}).get("row_headers", []),
            "col_headers": table.get("table_json", {}).get("col_headers", []),
        }
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()
