from __future__ import annotations

import re

COMPANY_OPTIONS: dict[str, str] = {
    "pingan": "平安",
    "china_life": "国寿",
    "picc": "人保",
    "cpic": "太保",
    "taiping": "太平",
    "nci": "新华",
    "taikang": "泰康",
}

COMPANY_ALIASES: dict[str, str] = {
    "china-life": "china_life",
    "chinallife": "china_life",
    "中国人寿": "china_life",
    "平安": "pingan",
    "中国平安": "pingan",
    "人保": "picc",
    "中国人保": "picc",
    "太保": "cpic",
    "中国太保": "cpic",
    "太平": "taiping",
    "新华": "nci",
    "新华保险": "nci",
    "泰康": "taikang",
}

REPORT_TYPE_OPTIONS: dict[str, str] = {
    "annual_report": "年报",
    "semiannual_report": "半年报",
    "quarterly_report": "季报",
    "monthly_report": "月报",
}

BUSINESS_LINE_OPTIONS: dict[str, str] = {
    "group": "集团",
    "life": "寿险",
    "pnc": "产险",
}

METRIC_LIFECYCLE_ACTIVE = "active"
METRIC_LIFECYCLE_CANDIDATE = "candidate"
METRIC_LIFECYCLE_MERGED = "merged"
METRIC_LIFECYCLE_DISMISSED = "dismissed"

_metric_note_suffix_pattern = re.compile(r"\s*[（(](?:注|附注)?\s*[0-9A-Za-z一二三四五六七八九十]+\s*[）)]\s*$")
_metric_prefix_index_pattern = re.compile(r"^[（(]?[一二三四五六七八九十百千0-9]+[)）.、\-\s]*")
_metric_placeholder_pattern = re.compile(r"^(?:metric|value|row|col|unknown)(?:[_-]?\d+)?$", re.IGNORECASE)
_metric_invalid_only_pattern = re.compile(r"^[\W_()（）0-9]+$")


def get_company_label(company_id: str | None) -> str:
    if not company_id:
        return "未配置公司"
    return COMPANY_OPTIONS.get(company_id, company_id)


def get_report_type_label(report_type: str | None) -> str:
    if not report_type:
        return "未知报告"
    return REPORT_TYPE_OPTIONS.get(report_type, report_type)


def get_business_line_label(business_line: str | None) -> str:
    if not business_line:
        return "未分类"
    return BUSINESS_LINE_OPTIONS.get(business_line, business_line)


def build_document_label(company_id: str | None, report_year: int | None, report_type: str | None) -> str:
    company_label = get_company_label(company_id)
    report_type_label = get_report_type_label(report_type)
    if report_year is None:
        return f"{company_label} {report_type_label}"
    return f"{company_label} {report_year} {report_type_label}"


def clean_metric_text(text: str | None) -> str:
    value = (text or "").strip()
    value = value.replace("\u3000", " ")
    value = value.replace("（", "(").replace("）", ")")
    value = _metric_prefix_index_pattern.sub("", value)
    previous = None
    while previous != value:
        previous = value
        value = _metric_note_suffix_pattern.sub("", value).strip()
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" :：-_*/")
    if value in {"注", "附注", "unknown_metric"}:
        return ""
    return value


def is_placeholder_metric_name(text: str | None) -> bool:
    value = clean_metric_text(text).strip().lower()
    if not value:
        return True
    if _metric_placeholder_pattern.fullmatch(value):
        return True
    if _metric_invalid_only_pattern.fullmatch(value):
        return True
    return False


def normalize_company_id(company_id: str | None) -> str:
    value = (company_id or "").strip()
    if not value:
        return ""
    value = value.replace(" ", "_").replace("-", "_").lower()
    if value in COMPANY_OPTIONS:
        return value
    return COMPANY_ALIASES.get(company_id or "", COMPANY_ALIASES.get(value, value))


def is_supported_company(company_id: str | None) -> bool:
    return normalize_company_id(company_id) in COMPANY_OPTIONS


def normalize_report_type(report_type: str | None) -> str:
    value = (report_type or "").strip()
    if not value:
        return ""
    reverse = {label: code for code, label in REPORT_TYPE_OPTIONS.items()}
    if value in REPORT_TYPE_OPTIONS:
        return value
    return reverse.get(value, value)


def is_supported_report_type(report_type: str | None) -> bool:
    return normalize_report_type(report_type) in REPORT_TYPE_OPTIONS


def is_supported_business_line(business_line: str | None) -> bool:
    return (business_line or "").strip() in BUSINESS_LINE_OPTIONS
