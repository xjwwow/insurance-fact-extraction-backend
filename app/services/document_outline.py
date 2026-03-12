from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pdfplumber

from app.models.document import Document


class DocumentOutlineService:
    _roman_pattern = re.compile(r"^[ivxlcdmIVXLCDM]{1,8}$")
    _section_titles = {"关于我们", "公司管治", "经营情况讨论及分析", "财务报表", "其他信息"}

    def build_outline(self, document: Document, tables: list[dict]) -> list[dict]:
        file_path = Path(document.file_path)
        if not file_path.exists():
            return self._build_fallback_outline(tables)

        try:
            sections = self._extract_toc_sections(file_path)
        except Exception:
            return self._build_fallback_outline(tables)
        if not sections:
            return self._build_fallback_outline(tables)
        return self._assign_tables_to_outline(sections, tables)

    def _extract_toc_sections(self, file_path: Path, max_pages: int = 16) -> list[dict]:
        with pdfplumber.open(file_path) as pdf:
            start_index = self._find_toc_start_page(pdf.pages[:max_pages])
            if start_index is None:
                return []

            sections: list[dict] = []
            current_by_column: dict[int, dict | None] = {0: None, 1: None}
            default_section: dict | None = None

            for page in pdf.pages[start_index:max_pages]:
                entries_on_page = 0
                lines = self._group_words_into_lines(page.extract_words(use_text_flow=False, keep_blank_chars=False) or [])
                split_x = float(page.width) * 0.5

                for line_words in lines:
                    column_zones = self._split_line_into_columns(line_words, split_x)
                    for column_index, zone in column_zones.items():
                        if not zone:
                            continue
                        text = self._clean_text(" ".join(word["text"] for word in zone))
                        if not text:
                            continue
                        compact = text.replace(" ", "")
                        if compact in {"目录", "目次", "目目录录", "目录CONTENTS", "CONTENTS"}:
                            continue

                        entry = self._parse_zone_entry(zone)
                        if entry is not None:
                            entries_on_page += 1
                            target_section = current_by_column.get(column_index)
                            if target_section is None:
                                if default_section is None:
                                    default_section = self._build_section("目录", entry["page_start"])
                                    sections.append(default_section)
                                target_section = default_section
                            target_section["children"].append(self._build_item(entry["title"], entry["page_start"]))
                            continue

                        if self._looks_like_section_title(text):
                            section = self._build_section(text, None)
                            sections.append(section)
                            current_by_column[column_index] = section

                if entries_on_page == 0 and sections:
                    break

        self._fill_ranges(sections)
        return [section for section in sections if section["children"] or section["tables"]]

    def _assign_tables_to_outline(self, sections: list[dict], tables: list[dict]) -> list[dict]:
        items: list[dict] = []
        for section in sections:
            items.extend(section.get("children", []))

        items = sorted((item for item in items if item.get("page_start") is not None), key=lambda item: item["page_start"])
        for index, item in enumerate(items):
            next_start = items[index + 1]["page_start"] if index + 1 < len(items) else 100000
            item["page_end"] = next_start - 1

        fallback_section = next((section for section in sections if section["title"] == "未归类"), None)
        if fallback_section is None:
            fallback_section = self._build_section("未归类", None)
            sections.append(fallback_section)

        for table in tables:
            nav = {
                "table_id": table["table_id"],
                "title": table.get("table_title_raw") or table.get("table_title_norm") or f"第 {table.get('page_start')} 页表格",
                "page_start": table["page_start"],
                "page_end": table["page_end"],
            }
            target = None
            for item in items:
                page_end = item.get("page_end") or item["page_start"]
                if item["page_start"] <= table["page_start"] <= page_end:
                    target = item
                    break
            if target is None:
                fallback_section["tables"].append(nav)
            else:
                target["tables"].append(nav)

        for section in sections:
            section["children"] = sorted(section.get("children", []), key=lambda item: (item.get("page_start") or 999999, item.get("title") or ""))
            section["tables"] = sorted(section.get("tables", []), key=lambda item: (item.get("page_start") or 999999, item.get("title") or ""))

        ordered_sections = [section for section in sections if section["children"] or section["tables"]]
        ordered_sections.sort(key=lambda section: (section.get("page_start") or 999999, section.get("title") or ""))
        return ordered_sections

    def _find_toc_start_page(self, pages: list[pdfplumber.page.Page]) -> int | None:
        for index, page in enumerate(pages):
            text = (page.extract_text() or "").replace(" ", "")
            if any(marker in text for marker in ("目录", "目目录录", "目次", "CONTENTS")):
                return index
        return None

    def _split_line_into_columns(self, line_words: list[dict], split_x: float) -> dict[int, list[dict]]:
        left = [word for word in line_words if float(word.get("x0", 0.0)) < split_x]
        right = [word for word in line_words if float(word.get("x0", 0.0)) >= split_x]
        return {0: left, 1: right}

    def _parse_zone_entry(self, zone_words: list[dict]) -> dict | None:
        tokens = [self._clean_text(str(word.get("text", ""))) for word in zone_words]
        tokens = [token for token in tokens if token]
        if len(tokens) < 2:
            return None

        page_token = tokens[-1]
        page_value = self._parse_page_token(page_token)
        if page_value is None:
            return None

        title_tokens = tokens[:-1]
        if title_tokens and self._is_prefix_page_token(title_tokens[0]):
            title_tokens = title_tokens[1:]
        title = self._clean_text(" ".join(title_tokens))
        if not title or len(title) > 42:
            return None
        if title in self._section_titles:
            return None
        return {"title": title, "page_start": page_value}

    def _parse_page_token(self, token: str) -> int | None:
        if token.isdigit():
            return int(token)
        if self._roman_pattern.fullmatch(token):
            return self._roman_to_int(token)
        return None

    def _is_prefix_page_token(self, token: str) -> bool:
        return token.isdigit() or self._roman_pattern.fullmatch(token) is not None

    def _looks_like_section_title(self, text: str) -> bool:
        compact = text.replace(" ", "")
        return compact in self._section_titles

    def _fill_ranges(self, sections: list[dict]) -> None:
        ordered_sections = [section for section in sections if section.get("children")]
        for index, section in enumerate(ordered_sections):
            child_pages = [child["page_start"] for child in section["children"] if child.get("page_start") is not None]
            section["page_start"] = min(child_pages) if child_pages else section.get("page_start")
            next_start = None
            for later in ordered_sections[index + 1:]:
                later_pages = [child["page_start"] for child in later["children"] if child.get("page_start") is not None]
                if later_pages:
                    next_start = min(later_pages)
                    break
            if section["page_start"] is not None and next_start is not None:
                section["page_end"] = next_start - 1

    def _build_section(self, title: str, page_start: int | None) -> dict:
        return {
            "node_id": self._make_node_id("section", title, page_start),
            "kind": "section",
            "title": title,
            "page_start": page_start,
            "page_end": None,
            "level": 1,
            "children": [],
            "tables": [],
        }

    def _build_item(self, title: str, page_start: int) -> dict:
        return {
            "node_id": self._make_node_id("item", title, page_start),
            "kind": "item",
            "title": title,
            "page_start": page_start,
            "page_end": None,
            "level": 2,
            "children": [],
            "tables": [],
        }

    def _build_fallback_outline(self, tables: list[dict]) -> list[dict]:
        return [
            {
                "node_id": self._make_node_id("section", "全部表格", 1),
                "kind": "section",
                "title": "全部表格",
                "page_start": 1,
                "page_end": None,
                "level": 1,
                "children": [],
                "tables": [
                    {
                        "table_id": table["table_id"],
                        "title": table.get("table_title_raw") or table.get("table_title_norm") or f"第 {table.get('page_start')} 页表格",
                        "page_start": table["page_start"],
                        "page_end": table["page_end"],
                    }
                    for table in tables
                ],
            }
        ]

    def _group_words_into_lines(self, words: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
        sorted_words = sorted(words, key=lambda item: (float(item.get("top", 0.0)), float(item.get("x0", 0.0))))
        lines: list[list[dict]] = []
        for word in sorted_words:
            top = float(word.get("top", 0.0))
            if not lines:
                lines.append([word])
                continue
            last_line = lines[-1]
            avg_top = sum(float(item.get("top", 0.0)) for item in last_line) / len(last_line)
            if abs(avg_top - top) <= tolerance:
                last_line.append(word)
            else:
                lines.append([word])
        for line in lines:
            line.sort(key=lambda item: float(item.get("x0", 0.0)))
        return lines

    @staticmethod
    def _clean_text(text: str) -> str:
        value = re.sub(r"\s+", " ", text).strip()
        value = value.strip(" .·•:：-_/")
        value = value.replace("目目录录", "目录")
        return value

    @staticmethod
    def _roman_to_int(token: str) -> int:
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        result = 0
        prev = 0
        for char in token.upper()[::-1]:
            value = values.get(char, 0)
            if value < prev:
                result -= value
            else:
                result += value
                prev = value
        return result

    @staticmethod
    def _make_node_id(prefix: str, title: str, page_start: int | None) -> str:
        raw = f"{prefix}|{title}|{page_start or 0}"
        return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"
