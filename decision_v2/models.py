from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    source: str
    proposed_code: str | None
    score: float = 0.0
    weight: float = 0.0
    tier: int = 0
    method: str = ""
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "proposed_code": self.proposed_code,
            "score": self.score,
            "weight": self.weight,
            "tier": self.tier,
            "method": self.method,
            "explanation": self.explanation,
        }


@dataclass
class DecisionResultV2:
    final_code: str | None
    final_score: float = 0.0
    confidence_label: str = "UNKNOWN"
    review_required: bool = True
    decision_source: str = "NONE"
    evidence: list[Evidence] = field(default_factory=list)
    consensus_count: int = 0
    conflict_count: int = 0
    explanation: str = "Sin evidencia"

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_code": self.final_code,
            "final_score": round(self.final_score, 4),
            "confidence_label": self.confidence_label,
            "review_required": self.review_required,
            "decision_source": self.decision_source,
            "evidence": [e.to_dict() for e in self.evidence],
            "consensus_count": self.consensus_count,
            "conflict_count": self.conflict_count,
            "explanation": self.explanation,
        }
