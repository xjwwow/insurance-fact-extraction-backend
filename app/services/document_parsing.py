from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pdfplumber

from app.core.config import settings
from app.models.document import Document


class DocumentParsingService:
    _numeric_pattern = re.compile(r"(?<![A-Za-z0-9_])-?\d[\d,]*(?:\.\d+)?")
    _numeric_token_pattern = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?%?$")
    _year_token_pattern = re.compile(r"^(19|20)\d{2}年?$")
    _year_header_pattern = re.compile(r"^(?P<year>(19|20)\d{2})年?(?:(?P<month>\d{1,2})月(?P<day>\d{1,2})日)?$")
    _year_range_header_pattern = re.compile(r"^(19|20)\d{2}年?[－—\-至](19|20)\d{2}年?$")
    _month_day_header_pattern = re.compile(r"^\d{1,2}月\d{1,2}日$")

    def __init__(self) -> None:
        self.table_settings: dict[str, Any] = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "intersection_tolerance": 5,
        }

    def parse_document(self, document: Document) -> list[dict]:
        file_path = Path(document.file_path)
        if not file_path.exists():
            return []

        try:
            with pdfplumber.open(file_path) as pdf:
                page_layouts: list[dict] = []
                for index, page in enumerate(pdf.pages, start=1):
                    page_layouts.append(self._parse_pdf_page_with_retry(document, file_path, page, index))
                return page_layouts
        except Exception as exc:
            return [self._build_non_pdf_page(document, file_path, error=str(exc))]

    def parse_page(self, document: Document, page_no: int) -> dict:
        file_path = Path(document.file_path)
        try:
            with pdfplumber.open(file_path) as pdf:
                if page_no < 1 or page_no > len(pdf.pages):
                    return self._empty_page(document.document_id, page_no)
                page = pdf.pages[page_no - 1]
                return self._parse_pdf_page_with_retry(document, file_path, page, page_no)
        except Exception as exc:
            if page_no == 1:
                return self._build_non_pdf_page(document, file_path, error=str(exc))
            return self._empty_page(document.document_id, page_no, error=str(exc))

    def detect_tables(self, page_layout: dict) -> list[dict]:
        return list(page_layout.get("tables", []))

    def _parse_pdf_page_with_retry(
        self,
        document: Document,
        file_path: Path,
        page: pdfplumber.page.Page,
        page_no: int,
    ) -> dict:
        attempts = max(1, int(settings.parse_page_retries) + 1)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                layout = self._parse_pdf_page_core(document, file_path, page, page_no)
                layout.setdefault("parse_trace", {})["attempts"] = attempt
                return layout
            except Exception as exc:
                last_error = exc

        return self._empty_page(document.document_id, page_no, error=str(last_error) if last_error else "unknown")

    def _parse_pdf_page_core(
        self,
        document: Document,
        file_path: Path,
        page: pdfplumber.page.Page,
        page_no: int,
    ) -> dict:
        text = (page.extract_text() or "").strip()
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []

        blocks: list[dict] = []
        if text:
            blocks.append(
                {
                    "block_type": "text",
                    "engine": "pdfplumber",
                    "text": text,
                    "word_count": len(words),
                }
            )

        raw_tables = self._extract_pdfplumber_tables(page_no, page)

        used_ocr = False
        if (not text or len(text) < settings.ocr_min_text_len) and settings.ocr_enabled:
            ocr_text, ocr_words = self._extract_ocr_payload(file_path, page_no)
            if ocr_text:
                blocks.append(
                    {
                        "block_type": "text",
                        "engine": "pytesseract",
                        "text": ocr_text,
                        "word_count": len(ocr_text.split()),
                    }
                )
                used_ocr = True

                if not raw_tables:
                    raw_tables = self._build_table_from_ocr_words(ocr_words, page_no)
                    if not raw_tables:
                        raw_tables = self._build_numeric_table_from_text(ocr_text, page_no, engine="ocr_text_fallback")

        if not raw_tables and text and not self._is_toc_like_page(text):
            raw_tables = self._build_table_from_words(words, page_no, text, engine="word_layout_fallback")
            if not raw_tables and self._should_use_numeric_text_fallback(text):
                raw_tables = self._build_numeric_table_from_text(text, page_no, engine="text_fallback")

        for table in raw_tables:
            trace = table.setdefault("parse_trace", {})
            trace["page_width"] = float(page.width)
            trace["page_height"] = float(page.height)
            if "bbox" not in trace or not trace.get("bbox"):
                bbox = self._compute_table_bbox(table.get("cells", []))
                if bbox:
                    trace["bbox"] = bbox

        return {
            "document_id": document.document_id,
            "page_no": page_no,
            "width": float(page.width),
            "height": float(page.height),
            "blocks": blocks,
            "tables": raw_tables,
            "parse_trace": {
                "text_len": len(text),
                "word_count": len(words),
                "table_count": len(raw_tables),
                "ocr_used": used_ocr,
            },
        }

    def _extract_pdfplumber_tables(self, page_no: int, page: pdfplumber.page.Page) -> list[dict]:
        raw_tables: list[dict] = []
        page_words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
        tables = page.find_tables(self.table_settings) or []

        for idx, table_obj in enumerate(tables, start=1):
            matrix = table_obj.extract()
            normalized_rows = self._normalize_table_rows(matrix)
            if len(normalized_rows) < 2:
                continue

            header_rows, body = self._split_header_rows(normalized_rows)
            header_paths = self._build_header_paths(header_rows)
            if not body:
                continue

            cells: list[dict] = []
            for row_idx, row in enumerate(body, start=1):
                row_header = self._merge_row_label(row) or f"row_{row_idx}"
                numeric_positions = [pos for pos, value in enumerate(row) if value and self._looks_numeric(value)]
                for pos in numeric_positions:
                    value = row[pos]
                    if not value:
                        continue
                    col_path = header_paths[pos] if pos < len(header_paths) and header_paths[pos] else [f"col_{pos + 1}"]
                    cells.append(
                        {
                            "row_path": [row_header],
                            "col_path": col_path,
                            "value_raw": value,
                            "bbox": [0.0, 0.0, 0.0, 0.0],
                            "confidence": 0.85,
                        }
                    )

            if not cells:
                continue

            table_title = self._extract_table_title_from_page_words(page_words, table_obj.bbox, idx)
            col_headers = list(dict.fromkeys(self._merge_header_path(cell.get("col_path", []), index) for index, cell in enumerate(cells, start=1) if cell.get("col_path")))

            raw_tables.append(
                {
                    "page_no": page_no,
                    "table_title_raw": table_title,
                    "table_title_norm": self._normalize_title(table_title),
                    "unit_raw": None,
                    "currency_raw": None,
                    "row_headers": [self._merge_row_label(row) for row in body if row],
                    "col_headers": col_headers or [item for item in header if item],
                    "cells": cells,
                    "footnotes": [],
                    "parse_engine": "pdfplumber",
                    "parse_confidence": 0.85,
                    "parse_trace": {
                        "rows": len(normalized_rows),
                        "cells": len(cells),
                        "bbox": list(table_obj.bbox),
                        "header_levels": max((len(path) for path in header_paths), default=1),
                    },
                }
            )

        return raw_tables

    def _extract_ocr_payload(self, file_path: Path, page_no: int) -> tuple[str, list[dict]]:
        try:
            import pypdfium2 as pdfium
            import pytesseract
            from pytesseract import Output
        except Exception:
            return "", []

        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        if settings.tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = settings.tessdata_prefix

        try:
            pdf = pdfium.PdfDocument(str(file_path))
            page = pdf[page_no - 1]
            bitmap = page.render(scale=float(settings.pdf_render_scale))
            image = bitmap.to_pil()

            raw = pytesseract.image_to_data(image, lang=settings.ocr_language, output_type=Output.DICT)
            words: list[dict] = []
            count = len(raw.get("text", []))
            for i in range(count):
                text = (raw["text"][i] or "").strip()
                if not text:
                    continue
                conf = self._safe_float(raw.get("conf", ["0"])[i])
                if conf < 0:
                    continue
                words.append(
                    {
                        "text": text,
                        "left": int(raw.get("left", [0])[i]),
                        "top": int(raw.get("top", [0])[i]),
                        "width": int(raw.get("width", [0])[i]),
                        "height": int(raw.get("height", [0])[i]),
                        "conf": conf,
                        "block_num": int(raw.get("block_num", [0])[i]),
                        "par_num": int(raw.get("par_num", [0])[i]),
                        "line_num": int(raw.get("line_num", [0])[i]),
                    }
                )

            words.sort(key=lambda item: (item["top"], item["left"]))
            text = self._ocr_words_to_text(words)
            return text, words
        except Exception:
            return "", []

    def _build_table_from_ocr_words(self, words: list[dict], page_no: int) -> list[dict]:
        if not words:
            return []

        grouped: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
        for word in words:
            key = (word.get("block_num", 0), word.get("par_num", 0), word.get("line_num", 0))
            grouped[key].append(word)

        cells: list[dict] = []
        metric_idx = 0
        for _, line_words in sorted(grouped.items(), key=lambda item: (min(w["top"] for w in item[1]), min(w["left"] for w in item[1]))):
            line_words.sort(key=lambda item: item["left"])
            for idx, token in enumerate(line_words):
                token_text = token["text"]
                if not self._looks_numeric(token_text):
                    continue

                metric_idx += 1
                left_context = [w["text"] for w in line_words[:idx] if not self._looks_numeric(w["text"])][-3:]
                row_name = " ".join(left_context).strip() or f"metric_{metric_idx}"
                bbox = [
                    float(token["left"]),
                    float(token["top"]),
                    float(token["left"] + token["width"]),
                    float(token["top"] + token["height"]),
                ]
                cells.append(
                    {
                        "row_path": [row_name],
                        "col_path": ["current_period"],
                        "value_raw": token_text,
                        "bbox": bbox,
                        "confidence": round(max(min(token["conf"] / 100.0, 1.0), 0.0), 4),
                    }
                )

        if not cells:
            return []

        return [
            {
                "page_no": page_no,
                "table_title_raw": "OCR-detected numeric table",
                "table_title_norm": "ocr_detected_numeric_table",
                "unit_raw": None,
                "currency_raw": None,
                "row_headers": [cell["row_path"][0] for cell in cells],
                "col_headers": ["current_period"],
                "cells": cells,
                "footnotes": [],
                "parse_engine": "ocr_layout",
                "parse_confidence": round(sum(cell["confidence"] for cell in cells) / len(cells), 4),
                "parse_trace": {
                    "detected_numeric_cells": len(cells),
                    "source": "pytesseract.image_to_data",
                },
            }
        ]

    def _build_numeric_table_from_text(self, text: str, page_no: int, engine: str) -> list[dict]:
        numbers = self._numeric_pattern.findall(text)
        if not numbers:
            return []

        unit_raw, currency_raw = self._infer_unit_currency_from_text(text)

        cells: list[dict] = []
        for idx, value in enumerate(numbers[:100], start=1):
            cells.append(
                {
                    "row_path": [f"metric_{idx}"],
                    "col_path": ["current_period"],
                    "value_raw": value,
                    "bbox": [0.0, 0.0, 0.0, 0.0],
                    "confidence": 0.6,
                }
            )

        return [
            {
                "page_no": page_no,
                "table_title_raw": "Auto-detected numeric table",
                "table_title_norm": "auto_detected_numeric_table",
                "unit_raw": unit_raw,
                "currency_raw": currency_raw,
                "row_headers": [],
                "col_headers": ["current_period"],
                "cells": cells,
                "footnotes": [],
                "parse_engine": engine,
                "parse_confidence": 0.6,
                "parse_trace": {"detected_numeric_cells": len(cells)},
            }
        ]

    def _build_table_from_words(self, words: list[dict], page_no: int, text: str, engine: str) -> list[dict]:
        if not words:
            return []

        line_groups = self._group_words_into_lines(words)
        if not line_groups:
            return []

        unit_raw, currency_raw = self._infer_unit_currency_from_text(text)
        tables: list[dict] = []
        current_table: dict | None = None
        current_col_header_paths: list[list[str]] = []
        recent_context: list[str] = []
        pending_title: str | None = None
        previous_bottom: float | None = None

        for line_words in line_groups:
            tokens = [str(word.get("text", "")).strip() for word in line_words if str(word.get("text", "")).strip()]
            if not tokens:
                continue

            line_top = min(float(word.get("top", 0.0)) for word in line_words)
            line_bottom = max(float(word.get("bottom", 0.0)) for word in line_words)
            vertical_gap = 0.0 if previous_bottom is None else max(0.0, line_top - previous_bottom)
            previous_bottom = line_bottom

            numeric_positions = [idx for idx, token in enumerate(tokens) if self._looks_numeric(token)]
            header_positions = [idx for idx, token in enumerate(tokens) if self._is_header_value_token(token)]

            if not numeric_positions:
                if len(header_positions) >= 2 and self._is_header_line(tokens, header_positions):
                    if header_positions and header_positions[0] == 0 and tokens[0] in {"(%)", "%"} and len(header_positions) >= 3:
                        header_positions = header_positions[1:]
                    if current_table and current_table["cells"] and vertical_gap >= 8:
                        tables.append(current_table)
                        current_table = None
                    next_headers = [self._normalize_header_value_token(tokens[idx], position) for position, idx in enumerate(header_positions, start=1)]
                    if current_col_header_paths and vertical_gap <= 10:
                        current_col_header_paths = self._merge_header_bands(current_col_header_paths, next_headers)
                    else:
                        current_col_header_paths = [[header] if header else [] for header in next_headers]
                    continue

                label = self._clean_row_label(" ".join(tokens))
                if self._looks_like_table_title(label, tokens):
                    if current_table and current_table["cells"] and vertical_gap >= 8:
                        tables.append(current_table)
                        current_table = None
                    pending_title = label
                if label and not self._is_noise_label(label):
                    recent_context.append(label)
                    recent_context = recent_context[-3:]
                if current_table and current_table["cells"] and vertical_gap >= 28:
                    tables.append(current_table)
                    current_table = None
                continue

            label = self._label_from_line(tokens, numeric_positions)
            if not label and recent_context:
                label = recent_context[-1]

            if not label or self._should_skip_line(label, tokens, numeric_positions):
                continue

            if current_table is None or (current_table["cells"] and vertical_gap >= 24):
                if current_table and current_table["cells"]:
                    tables.append(current_table)
                title = pending_title or f"第 {page_no} 页表格 {len(tables) + 1}"
                current_table = {
                    "page_no": page_no,
                    "table_title_raw": title,
                    "table_title_norm": self._normalize_title(title),
                    "unit_raw": unit_raw,
                    "currency_raw": currency_raw,
                    "row_headers": [],
                    "col_headers": [],
                    "cells": [],
                    "footnotes": [],
                    "parse_engine": engine,
                    "parse_confidence": 0.72,
                    "parse_trace": {
                        "source": "pdfplumber.extract_words",
                    },
                }
                pending_title = None

            current_table["row_headers"].append(label)
            value_index = 0
            for pos in numeric_positions:
                token = tokens[pos]
                word = line_words[pos]
                col_path = self._resolve_col_path(current_col_header_paths, value_index, len(numeric_positions))
                value_index += 1
                current_table["cells"].append(
                    {
                        "row_path": [label],
                        "col_path": col_path,
                        "value_raw": token,
                        "bbox": [
                            float(word.get("x0", 0.0)),
                            float(word.get("top", 0.0)),
                            float(word.get("x1", 0.0)),
                            float(word.get("bottom", 0.0)),
                        ],
                        "confidence": 0.72,
                    }
                )
            current_table["col_headers"] = list(
                dict.fromkeys(
                    [*current_table["col_headers"], *(self._merge_header_path(cell.get("col_path", []), index) for index, cell in enumerate(current_table["cells"], start=1))]
                )
            )

        if current_table and current_table["cells"]:
            tables.append(current_table)

        for index, table in enumerate(tables, start=1):
            if not table["cells"]:
                continue
            table["row_headers"] = list(dict.fromkeys(table["row_headers"]))
            table["col_headers"] = list(dict.fromkeys(self._merge_header_path(cell.get("col_path", []), index) for index, cell in enumerate(table["cells"], start=1)))
            bbox = self._compute_table_bbox(table["cells"])
            if bbox:
                table["parse_trace"]["bbox"] = bbox
            table["parse_trace"]["detected_numeric_cells"] = len(table["cells"])
            table["parse_trace"]["header_levels"] = max((len(cell.get("col_path", [])) for cell in table["cells"]), default=1)
            if not table["table_title_raw"]:
                fallback_title = f"第 {page_no} 页表格 {index}"
                table["table_title_raw"] = fallback_title
                table["table_title_norm"] = self._normalize_title(fallback_title)

        return [table for table in tables if table["cells"] and self._should_keep_word_layout_table(table)]

    def _split_header_rows(self, rows: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
        header_rows: list[list[str]] = []
        body_rows = rows
        for idx, row in enumerate(rows[:3]):
            numeric_count = sum(1 for value in row if value and self._looks_numeric(value))
            if numeric_count == 0:
                header_rows.append(row)
                body_rows = rows[idx + 1 :]
                continue
            break
        if not header_rows and rows:
            header_rows = [rows[0]]
            body_rows = rows[1:]
        return header_rows, body_rows

    def _merge_header_rows(self, header_rows: list[list[str]]) -> list[str]:
        width = max((len(row) for row in header_rows), default=0)
        merged: list[str] = []
        for col_idx in range(width):
            tokens = []
            for row in header_rows:
                value = row[col_idx] if col_idx < len(row) else ""
                if value:
                    tokens.append(value)
            merged.append(self._clean_row_label(" ".join(tokens)))
        return merged

    def _build_header_paths(self, header_rows: list[list[str]]) -> list[list[str]]:
        width = max((len(row) for row in header_rows), default=0)
        paths: list[list[str]] = []
        for col_idx in range(width):
            tokens = []
            for row in header_rows:
                value = row[col_idx] if col_idx < len(row) else ""
                cleaned = self._clean_row_label(value)
                if cleaned:
                    tokens.append(cleaned)
            paths.append(tokens or [f"col_{col_idx + 1}"])
        return paths

    def _merge_row_label(self, row: list[str]) -> str:
        if not row:
            return ""
        numeric_positions = [idx for idx, value in enumerate(row) if value and self._looks_numeric(value)]
        if not numeric_positions:
            return self._clean_row_label(" ".join(item for item in row if item))
        first_numeric = numeric_positions[0]
        label_tokens = [value for value in row[:first_numeric] if value and not self._looks_numeric(value)]
        return self._clean_row_label(" ".join(label_tokens))

    def _extract_table_title_from_page_words(self, words: list[dict], bbox: tuple[float, float, float, float], index: int) -> str:
        top = float(bbox[1])
        x0 = float(bbox[0])
        x1 = float(bbox[2])
        candidates = [
            word for word in words
            if float(word.get("bottom", 0.0)) <= top
            and float(word.get("bottom", 0.0)) >= top - 80
            and float(word.get("x0", 0.0)) <= x1
            and float(word.get("x1", 0.0)) >= x0 - 20
        ]
        if not candidates:
            return f"第 {index} 表"
        grouped = self._group_words_into_lines(candidates, tolerance=2.5)
        if not grouped:
            return f"第 {index} 表"
        line_candidates = [self._clean_row_label(" ".join(word["text"] for word in line)) for line in grouped]
        filtered = [
            line for line in line_candidates
            if line
            and len(line) <= 24
            and not line.endswith(("。", "；", "："))
            and not any(char.isdigit() for char in line[-4:])
        ]
        if filtered:
            return filtered[-1]
        title = self._clean_row_label(" ".join(word["text"] for word in grouped[-1]))
        return title or f"第 {index} 表"

    def _normalize_title(self, title: str) -> str:
        value = re.sub(r"\s+", "_", title.strip().lower())
        value = re.sub(r"[^\w\u4e00-\u9fff]+", "_", value)
        return value.strip("_") or "table"

    def _looks_like_table_title(self, label: str, tokens: list[str]) -> bool:
        compact = label.replace(" ", "")
        if not compact or self._is_noise_label(label):
            return False
        if compact.endswith(("。", "；", "：", "影响")):
            return False
        if len(tokens) == 1 and len(compact) <= 18 and not any(char.isdigit() for char in compact):
            return True
        if len(compact) <= 22 and any(key in compact for key in ("表", "收益", "收入", "负债", "资产", "利润", "现金流", "投资", "分析", "情况")):
            return True
        return False

    def _infer_unit_currency_from_text(self, text: str) -> tuple[str | None, str | None]:
        known_units = ["亿元", "百万元", "万元", "千元", "元", "万股", "股", "%", "％"]

        unit_raw = None
        declaration = re.search(r"单位[:：]\s*([^\n\r]{1,24})", text)
        if declaration:
            segment = declaration.group(1)
            for unit in known_units:
                if unit in segment:
                    unit_raw = unit
                    break

        if unit_raw is None:
            compact = text.replace(" ", "")
            for unit in known_units:
                if f"单位:{unit}" in compact or f"单位：{unit}" in compact:
                    unit_raw = unit
                    break

        compact = text.replace(" ", "")
        currency_raw = None
        if any(x in compact for x in ("人民币", "RMB", "CNY", "¥")):
            currency_raw = "CNY"
        elif any(x in compact for x in ("美元", "USD", "$")):
            currency_raw = "USD"
        elif any(x in compact for x in ("港元", "HKD")):
            currency_raw = "HKD"

        return unit_raw, currency_raw

    def _normalize_table_rows(self, matrix: list[list[str | None]]) -> list[list[str]]:
        rows: list[list[str]] = []
        for raw_row in matrix:
            row = [((cell or "").strip()) for cell in raw_row]
            if not any(row):
                continue
            rows.append(row)
        return rows

    def _build_non_pdf_page(self, document: Document, file_path: Path, error: str | None = None) -> dict:
        data = file_path.read_bytes() if file_path.exists() else b""
        text = self._decode_bytes(data)
        tables = self._build_numeric_table_from_text(text, page_no=1, engine="binary_fallback")
        return {
            "document_id": document.document_id,
            "page_no": 1,
            "width": 0.0,
            "height": 0.0,
            "blocks": [
                {
                    "block_type": "text",
                    "engine": "binary_fallback",
                    "text": text,
                    "word_count": len(text.split()),
                }
            ],
            "tables": tables,
            "parse_trace": {
                "text_len": len(text),
                "word_count": len(text.split()),
                "table_count": len(tables),
                "ocr_used": False,
                "error": error,
            },
        }

    def _empty_page(self, document_id: str, page_no: int, error: str | None = None) -> dict:
        return {
            "document_id": document_id,
            "page_no": page_no,
            "width": 0.0,
            "height": 0.0,
            "blocks": [],
            "tables": [],
            "parse_trace": {
                "text_len": 0,
                "word_count": 0,
                "table_count": 0,
                "ocr_used": False,
                "error": error,
            },
        }

    def _looks_numeric(self, value: str) -> bool:
        token = value.replace(" ", "").replace("\u00a0", "")
        return self._numeric_token_pattern.fullmatch(token) is not None

    def _is_header_value_token(self, value: str) -> bool:
        token = self._normalize_header_candidate(value)
        if (
            self._year_header_pattern.fullmatch(token)
            or self._year_range_header_pattern.fullmatch(token)
            or self._month_day_header_pattern.fullmatch(token)
        ):
            return True
        return token in {
            "变动",
            "变动(%)",
            "同比",
            "同比(%)",
            "同比增长率",
            "同比变化",
            "同比变化(%)",
            "增长率",
            "增长率(%)",
            "本期",
            "上期",
            "当前期",
            "本年",
            "上年",
            "本报告期",
            "上年同期",
            "较年初变动",
            "(%)",
            "调整前",
            "调整后(1)",
            "第一季度",
            "第二季度",
            "第三季度",
            "第四季度",
            "current_period",
        }

    def _normalize_header_value_token(self, value: str, position: int) -> str:
        token = self._normalize_header_candidate(value)
        year_match = self._year_header_pattern.fullmatch(token)
        if year_match:
            year = year_match.group("year")
            month = year_match.group("month")
            day = year_match.group("day")
            if month and day:
                return f"{year}年{month}月{day}日"
            return f"{year}年"
        if self._year_range_header_pattern.fullmatch(token):
            return token.replace("－", "-").replace("—", "-")
        if self._month_day_header_pattern.fullmatch(token):
            return token
        token = token.replace("％", "%")
        if token in {"同比变化", "增长率"}:
            return f"{token}(%)"
        if token:
            return token
        return f"value_{position}"

    def _group_words_into_lines(self, words: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
        sorted_words = sorted(words, key=lambda item: (float(item.get("top", 0.0)), float(item.get("x0", 0.0))))
        lines: list[list[dict]] = []

        for word in sorted_words:
            top = float(word.get("top", 0.0))
            if not lines:
                lines.append([word])
                continue

            last_line = lines[-1]
            last_top = sum(float(item.get("top", 0.0)) for item in last_line) / len(last_line)
            if abs(top - last_top) <= tolerance:
                last_line.append(word)
            else:
                lines.append([word])

        for line in lines:
            line.sort(key=lambda item: float(item.get("x0", 0.0)))
        return lines

    def _label_from_line(self, tokens: list[str], numeric_positions: list[int]) -> str:
        first_numeric = numeric_positions[0]
        leading_tokens = [token for token in tokens[:first_numeric] if not self._looks_numeric(token)]
        if leading_tokens:
            return self._clean_row_label(" ".join(leading_tokens))

        non_numeric_tokens = [token for idx, token in enumerate(tokens) if idx not in numeric_positions and not self._looks_numeric(token)]
        return self._clean_row_label(" ".join(non_numeric_tokens))

    def _clean_row_label(self, text: str) -> str:
        cleaned = text.replace("\u3000", " ").replace("·", " ").replace("•", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.strip(" -:：|")
        pairs = {"(": ")", "（": "）", "[": "]", "【": "】"}
        if cleaned and cleaned[0] in pairs and cleaned.endswith(pairs[cleaned[0]]):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    def _should_skip_line(self, label: str, tokens: list[str], numeric_positions: list[int]) -> bool:
        compact = label.replace(" ", "")
        if self._is_noise_label(label):
            return True
        if len(numeric_positions) == 1 and len(tokens) <= 2:
            return True
        if len(compact) > 40 and len(numeric_positions) <= 1:
            return True
        if len(tokens) > 14 and len(numeric_positions) <= 1:
            return True
        return False

    def _is_noise_label(self, label: str) -> bool:
        compact = label.replace(" ", "")
        if not compact:
            return True
        if compact in {"目录", "释义", "注", "注释"}:
            return True
        if compact.startswith(("注：", "注:", "二零二四年年报", "中国平安保险（集团）股份有限公司")):
            return True
        if compact.endswith("年报"):
            return True
        return False

    def _is_header_line(self, tokens: list[str], header_positions: list[int]) -> bool:
        if len(header_positions) < 2:
            return False
        non_header_positions = [idx for idx in range(len(tokens)) if idx not in header_positions]
        if not non_header_positions:
            return True
        if len(non_header_positions) == 1 and non_header_positions[0] < header_positions[0]:
            prefix = self._clean_row_label(tokens[non_header_positions[0]])
            return any(key in prefix for key in ("单位", "人民币", "百万元", "万元", "%", "元"))
        return False

    def _resolve_col_label(self, headers: list[str], position: int, value_count: int) -> str:
        if position < len(headers):
            return headers[position]
        if value_count == 1:
            return "current_period"
        return f"value_{position + 1}"

    def _resolve_col_path(self, paths: list[list[str]], position: int, value_count: int) -> list[str]:
        if position < len(paths) and paths[position]:
            return paths[position]
        if value_count == 1:
            return ["current_period"]
        return [f"value_{position + 1}"]

    def _merge_header_bands(self, current_headers: list[list[str]], next_headers: list[str]) -> list[list[str]]:
        width = max(len(current_headers), len(next_headers))
        merged: list[list[str]] = []
        trailing_context = current_headers[-1][-1] if current_headers and current_headers[-1] else ""
        for index in range(width):
            left = current_headers[index] if index < len(current_headers) else []
            right = next_headers[index] if index < len(next_headers) else ""
            if left and right:
                if right == left[-1]:
                    merged.append(left)
                else:
                    merged.append([*left, right])
            else:
                if left:
                    merged.append(left)
                else:
                    candidate = right
                    if right in {"调整前", "调整后(1)"} and trailing_context:
                        candidate = f"{trailing_context}{right}"
                    merged.append([candidate] if candidate else [])
        return merged

    def _merge_header_tokens(self, left: str, right: str) -> str:
        if self._year_header_pattern.fullmatch(left) and self._month_day_header_pattern.fullmatch(right):
            return f"{left}{right}"
        if self._year_header_pattern.fullmatch(left) and right in {"第一季度", "第二季度", "第三季度", "第四季度"}:
            return f"{left}{right}"
        if left == "较年初变动" and right == "(%)":
            return "较年初变动(%)"
        return f"{left}{right}"

    def _merge_header_path(self, path: list[str], position: int) -> str:
        if not path:
            return f"value_{position}"
        compact = []
        for token in path:
            if token not in compact:
                compact.append(token)
        if len(compact) == 1:
            return compact[0]
        return " / ".join(compact)

    def _normalize_header_candidate(self, value: str) -> str:
        token = value.strip().replace(" ", "")
        token = token.replace("╱", "").replace("/", "").replace("／", "")
        token = token.replace("（", "(").replace("）", ")")
        token = token.replace("％", "%").replace("﹪", "%")
        token = token.strip("[]【】:：;；,.。")
        return token

    def _should_use_numeric_text_fallback(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 4:
            return False
        if self._is_toc_like_page(text):
            return False
        structured_lines = 0
        for line in lines[:80]:
            tokens = [token for token in re.split(r"\s+", line) if token]
            numeric_count = sum(1 for token in tokens if self._looks_numeric(token))
            if numeric_count >= 2:
                structured_lines += 1
        has_unit_declaration = "单位" in text or "人民币" in text
        has_year_header = len(re.findall(r"(19|20)\d{2}年", text)) >= 2
        return structured_lines >= 3 and (has_unit_declaration or has_year_header)

    def _is_toc_like_page(self, text: str) -> bool:
        compact = text.replace(" ", "")
        markers = ("目录", "目目录录", "目次")
        has_marker = any(marker in compact for marker in markers)
        if not has_marker:
            return False
        toc_entries = len(re.findall(r"(19|20)?\d{1,3}\s*$", text, flags=re.MULTILINE))
        return toc_entries >= 4 or compact.count("报告") >= 2

    def _should_keep_word_layout_table(self, table: dict) -> bool:
        col_headers = table.get("col_headers", [])
        title = str(table.get("table_title_raw") or "")
        generic_headers = all(
            header == "current_period" or header.startswith("value_")
            for header in col_headers
        )
        if generic_headers:
            bad_titles = {
                "经营亮点",
                "我们是谁",
                "公司使命",
                "时代机遇",
                "公司战略",
                "科技赋能",
                "医疗养老",
                "综合金融",
            }
            if title in bad_titles:
                return False

        if generic_headers and len(table.get("cells", [])) < 8:
            return False

        row_headers = table.get("row_headers", [])
        long_row_count = sum(1 for header in row_headers if len(header.replace(" ", "")) >= 22)
        if row_headers and long_row_count / max(len(row_headers), 1) > 0.45:
            return False
        return True

    def _compute_table_bbox(self, cells: list[dict]) -> list[float] | None:
        boxes = [cell.get("bbox", []) for cell in cells if len(cell.get("bbox", [])) == 4]
        boxes = [box for box in boxes if any(float(value) != 0.0 for value in box)]
        if not boxes:
            return None
        return [
            min(float(box[0]) for box in boxes),
            min(float(box[1]) for box in boxes),
            max(float(box[2]) for box in boxes),
            max(float(box[3]) for box in boxes),
        ]

    @staticmethod
    def _decode_bytes(data: bytes) -> str:
        if not data:
            return ""
        for encoding in ("utf-8", "latin-1"):
            try:
                text = data.decode(encoding)
                if text:
                    return text[:30000]
            except UnicodeDecodeError:
                continue
        return ""

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _ocr_words_to_text(words: list[dict]) -> str:
        if not words:
            return ""

        grouped: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
        for word in words:
            key = (word.get("block_num", 0), word.get("par_num", 0), word.get("line_num", 0))
            grouped[key].append(word)

        lines: list[str] = []
        for _, line_words in sorted(grouped.items(), key=lambda item: (min(w["top"] for w in item[1]), min(w["left"] for w in item[1]))):
            line_words.sort(key=lambda item: item["left"])
            lines.append(" ".join(word["text"] for word in line_words))

        return "\n".join(lines).strip()

