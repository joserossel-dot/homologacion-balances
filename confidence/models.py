from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfidenceBreakdown:
    base_score: float = 0.0
    tier_penalty: int = 0
    source_bonus: int = 0
    type_bonus: int = 0
    dict_bonus: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_score": round(self.base_score, 4),
            "tier_penalty": self.tier_penalty,
            "source_bonus": self.source_bonus,
            "type_bonus": self.type_bonus,
            "dict_bonus": self.dict_bonus,
            "total": self.total,
        }


@dataclass
class ConfidenceResult:
    score: int
    label: str
    breakdown: ConfidenceBreakdown = field(default_factory=ConfidenceBreakdown)

    LABELS = {
        (81, 100): "VERY_HIGH",
        (61, 80): "HIGH",
        (41, 60): "MEDIUM",
        (21, 40): "LOW",
        (0, 20): "UNKNOWN",
    }

    @staticmethod
    def label_for(score: int) -> str:
        for (lo, hi), lbl in ConfidenceResult.LABELS.items():
            if lo <= score <= hi:
                return lbl
        return "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "breakdown": self.breakdown.to_dict(),
        }
