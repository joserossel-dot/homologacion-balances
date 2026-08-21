from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    CONTINUE = "CONTINUE"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECT = "REJECT"
    STRESS = "STRESS"
    LEARNING = "LEARNING"


class ConflictSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


@dataclass
class DecisionEvidence:
    source: str
    field: str
    value: Any = None
    confidence: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "field": self.field,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "detail": self.detail,
        }


@dataclass
class DecisionConflict:
    evidence_a: DecisionEvidence
    evidence_b: DecisionEvidence
    severity: ConflictSeverity
    reason: str
    resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_a": self.evidence_a.to_dict(),
            "evidence_b": self.evidence_b.to_dict(),
            "severity": self.severity.value,
            "reason": self.reason,
            "resolution": self.resolution,
        }


@dataclass
class DecisionScore:
    confidence: float = 0.0
    coverage: float = 0.0
    evidence_quality: float = 0.0
    consistency: float = 0.0
    learning_weight: float = 0.0

    @property
    def weighted_total(self) -> float:
        return round(
            0.40 * self.confidence
            + 0.25 * self.coverage
            + 0.15 * self.evidence_quality
            + 0.10 * self.consistency
            + 0.10 * self.learning_weight,
            4,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": round(self.confidence, 4),
            "coverage": round(self.coverage, 4),
            "evidence_quality": round(self.evidence_quality, 4),
            "consistency": round(self.consistency, 4),
            "learning_weight": round(self.learning_weight, 4),
            "weighted_total": self.weighted_total,
        }


@dataclass
class DecisionExplanation:
    account_code: str = ""
    account_name: str = ""
    classified_code: str = ""
    reasons: list[str] = field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = field(default_factory=list)
    confidence_breakdown: dict[str, float] = field(default_factory=dict)
    final_confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "classified_code": self.classified_code,
            "reasons": self.reasons,
            "evidence_summary": self.evidence_summary,
            "confidence_breakdown": self.confidence_breakdown,
            "final_confidence": round(self.final_confidence, 4),
        }


@dataclass
class DecisionStatistics:
    total_decisions: int = 0
    decisions_by_type: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    confidence_by_module: dict[str, float] = field(default_factory=dict)
    conflicts_detected: int = 0
    conflicts_by_severity: dict[str, int] = field(default_factory=dict)
    explanations_generated: int = 0
    total_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "decisions_by_type": self.decisions_by_type,
            "avg_confidence": round(self.avg_confidence, 4),
            "confidence_by_module": self.confidence_by_module,
            "conflicts_detected": self.conflicts_detected,
            "conflicts_by_severity": self.conflicts_by_severity,
            "explanations_generated": self.explanations_generated,
            "total_time_seconds": round(self.total_time_seconds, 3),
        }


@dataclass
class Decision:
    account_code: str = ""
    account_name: str = ""
    decision_type: DecisionType = DecisionType.CONTINUE
    final_code: str = ""
    confidence: float = 0.0
    evidence: list[DecisionEvidence] = field(default_factory=list)
    conflicts: list[DecisionConflict] = field(default_factory=list)
    score: DecisionScore | None = None
    explanation: DecisionExplanation | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "decision_type": self.decision_type.value,
            "final_code": self.final_code,
            "confidence": round(self.confidence, 4),
            "evidence_count": len(self.evidence),
            "conflicts_count": len(self.conflicts),
            "score": self.score.to_dict() if self.score else None,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "timestamp": self.timestamp.isoformat(),
        }
