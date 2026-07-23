from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    source: str
    detail: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "detail": self.detail, "confidence": self.confidence}


@dataclass
class ConfidenceResult:
    standard_code: str | None = None
    confidence: float = 0.0
    review_required: bool = True
    method: str = ""
    evidence: list[EvidenceItem] = field(default_factory=list)
    learning_hits: int = 0
    conflicts: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard_code": self.standard_code,
            "confidence": round(self.confidence, 4),
            "review_required": self.review_required,
            "method": self.method,
            "evidence": [e.to_dict() for e in self.evidence],
            "learning_hits": self.learning_hits,
            "conflicts": self.conflicts,
        }
