from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionEvidence:
    rule: str
    details: str
    score_sm: float | None = None
    tier_sm: int | None = None
    confidence_sm: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "details": self.details,
            "score_sm": self.score_sm,
            "tier_sm": self.tier_sm,
            "confidence_sm": self.confidence_sm,
        }


@dataclass
class DecisionResult:
    codigo_final: str | None
    decision_source: str
    confidence: str
    evidence: list[DecisionEvidence] = field(default_factory=list)
    review_required: bool = False
    reason: str = ""

    DECISION_SOURCES = {
        "SM_AND_REGEX_AGREE",
        "SM_HIGH_CONFIDENCE",
        "REGEX_EXACT",
        "SM_ONLY",
        "REGEX_ONLY",
        "CONFLICT_UNRESOLVED",
        "BOTH_UNKNOWN",
        "TYPE_FILTER_REJECTED",
    }

    CONFIDENCE_LEVELS = {"VERY_HIGH", "HIGH", "MEDIUM", "LOW", "UNKNOWN"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "codigo_final": self.codigo_final,
            "decision_source": self.decision_source,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "review_required": self.review_required,
            "reason": self.reason,
        }
