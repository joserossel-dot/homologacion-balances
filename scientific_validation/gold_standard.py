from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ErrorCategory(str, Enum):
    PARSER = "PARSER"
    OCR = "OCR"
    LAYOUT = "LAYOUT"
    COLUMN_MAPPING = "COLUMN_MAPPING"
    NORMALIZATION = "NORMALIZATION"
    DICTIONARY = "DICTIONARY"
    RULE = "RULE"
    FUZZY = "FUZZY"
    CMCC = "CMCC"
    SHADOW = "SHADOW"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    HUMAN = "HUMAN"
    OTHER = "OTHER"

    def describe(self) -> str:
        return self.value


@dataclass
class GoldStandardCase:
    case_id: str
    company: str
    document: str
    layout: str
    ocr_used: bool
    account_name: str
    original_amount: float
    expected_code: str
    expected_concept: str
    review_status: str  # pending / reviewed / disputed
    reviewer: str
    review_date: str
    confidence_human: float
    comments: str
    source_document: str
    page: int
    line: int
    decision_trace_reference: str
    parser_confidence: float
    layout_confidence: float
    column_mapping_confidence: float
    candidate_accept_rate: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def fields() -> list[str]:
        return [
            "case_id", "company", "document", "layout", "ocr_used",
            "account_name", "original_amount", "expected_code",
            "expected_concept", "review_status", "reviewer", "review_date",
            "confidence_human", "comments", "source_document", "page", "line",
            "decision_trace_reference", "parser_confidence",
            "layout_confidence", "column_mapping_confidence",
            "candidate_accept_rate",
        ]


@dataclass
class ValidationResult:
    expected: str
    predicted: str
    correct: bool
    decision_type: str
    decision_code: str
    confidence_system: float
    confidence_human: float
    difference_reason: str
    error_category: str
    review_time_seconds: float

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def fields() -> list[str]:
        return [
            "expected", "predicted", "correct", "decision_type",
            "decision_code", "confidence_system", "confidence_human",
            "difference_reason", "error_category", "review_time_seconds",
        ]
