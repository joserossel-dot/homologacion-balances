from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from .enums import DecisionCode


@dataclass
class DecisionTrace:
    document_id: str
    company: str
    layout: str
    layout_confidence: float
    ocr_confidence: float
    parser_confidence: float
    column_mapping_confidence: float
    candidate_accept_rate: float
    candidate_status: str
    candidate_reasons: list[str]
    normalized_name: str
    original_name: str
    cmcc_match: bool
    cmcc_match_type: str
    cmcc_variant: str
    cmcc_score: float
    dictionary_match: bool
    dictionary_source: str
    official_classification: str
    official_confidence: float
    shadow_classification: str
    shadow_confidence: float
    decision_code: str
    decision_description: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def explanation(self) -> str:
        lines = [self.original_name]
        lines.append(f"├─ Normalized: {self.normalized_name}")
        lines.append(f"├─ Parser: {'ACCEPT' if self.parser_confidence > 0 else 'REJECT'} "
                      f"(confidence={self.parser_confidence})")
        lines.append(f"├─ Layout: {self.layout}")
        if self.cmcc_match:
            lines.append(f"├─ CMCC: {self.cmcc_match_type} → {self.official_classification}")
        elif self.dictionary_match:
            lines.append(f"├─ Dictionary: {self.dictionary_source}")
        elif self.shadow_classification and self.shadow_confidence > 0:
            lines.append(f"├─ Shadow CMCC: {self.shadow_classification}")
        else:
            lines.append(f"├─ No Match: {self.decision_description}")
        lines.append(f"└─ Decision: [{self.decision_code}] {self.decision_description}")
        return "\n".join(lines)

    def summary_line(self) -> str:
        if self.official_classification and self.official_classification != "UNKNOWN":
            return f"[{self.decision_code}] {self.original_name[:60]} → {self.official_classification} ({self.official_confidence})"
        return f"[{self.decision_code}] {self.original_name[:60]} → UNKNOWN"
