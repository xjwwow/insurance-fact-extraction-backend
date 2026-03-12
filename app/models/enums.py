from enum import StrEnum


class ParseStatus(StrEnum):
    INGESTED = "INGESTED"
    PARSE_QUEUED = "PARSE_QUEUED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    FAILED = "FAILED"


class ValidationStatus(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CORRECTED = "CORRECTED"
    REMAPPED = "REMAPPED"
    REJECTED = "REJECTED"
