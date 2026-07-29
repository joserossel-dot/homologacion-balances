from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ApprovalState(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_WARNINGS = "APPROVED_WITH_WARNINGS"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    LEARNING = "LEARNING"
    STRESS = "STRESS"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


DEFAULT_GATE_THRESHOLDS: dict[str, float] = {
    "monetary_coverage": 0.95,
    "structural_coverage": 0.85,
    "semantic_coverage": 0.80,
    "document_coverage": 0.90,
    "decision_confidence": 0.70,
    "validation_integrity": 0.80,
    "parser_success": 0.50,
    "structure_valid": 0.50,
    "knowledge_presence": 0.30,
    "die_confidence": 0.50,
}

DEFAULT_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "coverage": 0.25,
    "decision": 0.20,
    "validation": 0.20,
    "parser": 0.10,
    "knowledge": 0.10,
    "structure": 0.10,
    "die": 0.05,
}

DEFAULT_RISK_WEIGHTS: dict[str, float] = {
    "document": 0.15,
    "structural": 0.20,
    "monetary": 0.25,
    "semantic": 0.20,
    "operational": 0.20,
}


@dataclass
class QualityGate:
    name: str = ""
    passed: bool = False
    score: float = 0.0
    weight: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "weight": round(self.weight, 4),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityGate:
        return cls(
            name=data.get("name", ""),
            passed=bool(data.get("passed", False)),
            score=float(data.get("score", 0.0)),
            weight=float(data.get("weight", 0.0)),
            detail=data.get("detail", ""),
        )


@dataclass
class QAIssue:
    source: str = ""
    issue_type: str = ""
    severity: str = "INFO"
    detail: str = ""
    impact: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "detail": self.detail,
            "impact": round(self.impact, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAIssue:
        return cls(
            source=data.get("source", ""),
            issue_type=data.get("issue_type", ""),
            severity=data.get("severity", "INFO"),
            detail=data.get("detail", ""),
            impact=float(data.get("impact", 0.0)),
        )


@dataclass
class QARisk:
    document_risk: float = 0.0
    structural_risk: float = 0.0
    monetary_risk: float = 0.0
    semantic_risk: float = 0.0
    operational_risk: float = 0.0
    total_risk: float = 0.0
    level: RiskLevel = RiskLevel.LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_risk": round(self.document_risk, 2),
            "structural_risk": round(self.structural_risk, 2),
            "monetary_risk": round(self.monetary_risk, 2),
            "semantic_risk": round(self.semantic_risk, 2),
            "operational_risk": round(self.operational_risk, 2),
            "total_risk": round(self.total_risk, 2),
            "level": self.level.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QARisk:
        return cls(
            document_risk=float(data.get("document_risk", 0.0)),
            structural_risk=float(data.get("structural_risk", 0.0)),
            monetary_risk=float(data.get("monetary_risk", 0.0)),
            semantic_risk=float(data.get("semantic_risk", 0.0)),
            operational_risk=float(data.get("operational_risk", 0.0)),
            total_risk=float(data.get("total_risk", 0.0)),
            level=RiskLevel(data.get("level", "LOW")),
        )


@dataclass
class QAConfidence:
    overall: float = 0.0
    coverage: float = 0.0
    decision: float = 0.0
    validation: float = 0.0
    parser: float = 0.0
    knowledge: float = 0.0
    structure: float = 0.0
    die: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "coverage": round(self.coverage, 4),
            "decision": round(self.decision, 4),
            "validation": round(self.validation, 4),
            "parser": round(self.parser, 4),
            "knowledge": round(self.knowledge, 4),
            "structure": round(self.structure, 4),
            "die": round(self.die, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAConfidence:
        return cls(
            overall=float(data.get("overall", 0.0)),
            coverage=float(data.get("coverage", 0.0)),
            decision=float(data.get("decision", 0.0)),
            validation=float(data.get("validation", 0.0)),
            parser=float(data.get("parser", 0.0)),
            knowledge=float(data.get("knowledge", 0.0)),
            structure=float(data.get("structure", 0.0)),
            die=float(data.get("die", 0.0)),
        )


@dataclass
class QARecommendation:
    message: str = ""
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "actions": list(self.actions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QARecommendation:
        return cls(
            message=data.get("message", ""),
            actions=data.get("actions", []),
        )


@dataclass
class QAResult:
    approval_state: ApprovalState = ApprovalState.MANUAL_REVIEW
    confidence: QAConfidence = field(default_factory=QAConfidence)
    risk: QARisk = field(default_factory=QARisk)
    gates: list[QualityGate] = field(default_factory=list)
    issues: list[QAIssue] = field(default_factory=list)
    recommendations: list[QARecommendation] = field(default_factory=list)
    decision_reason: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_state": self.approval_state.value,
            "confidence": self.confidence.to_dict(),
            "risk": self.risk.to_dict(),
            "gates": [g.to_dict() for g in self.gates],
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "decision_reason": self.decision_reason,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QAResult:
        return cls(
            approval_state=ApprovalState(data.get("approval_state", "MANUAL_REVIEW")),
            confidence=QAConfidence.from_dict(data.get("confidence", {})),
            risk=QARisk.from_dict(data.get("risk", {})),
            gates=[QualityGate.from_dict(g) for g in data.get("gates", [])],
            issues=[QAIssue.from_dict(i) for i in data.get("issues", [])],
            recommendations=[QARecommendation.from_dict(r) for r in data.get("recommendations", [])],
            decision_reason=data.get("decision_reason", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class QASummary:
    total_documents: int = 0
    approved: int = 0
    approved_with_warnings: int = 0
    manual_review: int = 0
    learning: int = 0
    stress: int = 0
    rejected: int = 0
    failed: int = 0
    avg_confidence: float = 0.0
    avg_risk: float = 0.0
    avg_risk_level: RiskLevel = RiskLevel.LOW
    by_template: dict[str, dict[str, float]] = field(default_factory=dict)
    by_parser: dict[str, dict[str, float]] = field(default_factory=dict)
    by_company: dict[str, dict[str, float]] = field(default_factory=dict)
    by_family: dict[str, dict[str, float]] = field(default_factory=dict)
    by_year: dict[str, dict[str, float]] = field(default_factory=dict)
    distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "approved": self.approved,
            "approved_with_warnings": self.approved_with_warnings,
            "manual_review": self.manual_review,
            "learning": self.learning,
            "stress": self.stress,
            "rejected": self.rejected,
            "failed": self.failed,
            "avg_confidence": round(self.avg_confidence, 4),
            "avg_risk": round(self.avg_risk, 2),
            "avg_risk_level": self.avg_risk_level.value,
            "by_template": self.by_template,
            "by_parser": self.by_parser,
            "by_company": self.by_company,
            "by_family": self.by_family,
            "by_year": self.by_year,
            "distribution": self.distribution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QASummary:
        return cls(
            total_documents=int(data.get("total_documents", 0)),
            approved=int(data.get("approved", 0)),
            approved_with_warnings=int(data.get("approved_with_warnings", 0)),
            manual_review=int(data.get("manual_review", 0)),
            learning=int(data.get("learning", 0)),
            stress=int(data.get("stress", 0)),
            rejected=int(data.get("rejected", 0)),
            failed=int(data.get("failed", 0)),
            avg_confidence=float(data.get("avg_confidence", 0.0)),
            avg_risk=float(data.get("avg_risk", 0.0)),
            avg_risk_level=RiskLevel(data.get("avg_risk_level", "LOW")),
            by_template=data.get("by_template", {}),
            by_parser=data.get("by_parser", {}),
            by_company=data.get("by_company", {}),
            by_family=data.get("by_family", {}),
            by_year=data.get("by_year", {}),
            distribution=data.get("distribution", {}),
        )


def risk_level_from_score(score: float) -> RiskLevel:
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def risk_score_from_coverage(coverage_pct: float) -> float:
    return round((1.0 - coverage_pct) * 100, 2)
