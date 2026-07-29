from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


FAMILY_ORDER = [
    "Activo",
    "Pasivo",
    "Patrimonio",
    "Resultado",
    "Ingresos",
    "Costos",
    "Gastos",
]

FAMILY_PREFIX_MAP = {
    "AC": "Activo",
    "ANC": "Activo",
    "PC": "Pasivo",
    "PNC": "Pasivo",
    "PAT": "Patrimonio",
    "ER": "Resultado",
}

DEFAULT_COVERAGE_WEIGHTS: dict[str, float] = {
    "monetary": 0.40,
    "structural": 0.25,
    "semantic": 0.20,
    "document": 0.15,
}

EXPECTED_SECTIONS = [
    "Activo",
    "Pasivo",
    "Patrimonio",
    "Resultado",
]


class CoverageType(str, Enum):
    MONETARY = "monetary"
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    DOCUMENT = "document"
    OVERALL = "overall"


class CoverageSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


def family_from_code(code: str | None) -> str:
    if not code:
        return "Unknown"
    prefix = str(code).split(".")[0] if "." in str(code) else str(code)
    if prefix in FAMILY_PREFIX_MAP:
        return FAMILY_PREFIX_MAP[prefix]
    if prefix.startswith("1"):
        return "Activo"
    if prefix.startswith("2"):
        return "Pasivo"
    if prefix.startswith("3"):
        return "Patrimonio"
    if prefix.startswith("4"):
        return "Resultado"
    if prefix.startswith("5"):
        return "Costos"
    if prefix.startswith("6"):
        return "Gastos"
    return "Unknown"


@dataclass
class CoverageIssue:
    issue_type: str = ""
    severity: CoverageSeverity = CoverageSeverity.INFO
    monetary_impact: float = 0.0
    document_impact: float = 0.0
    detail: str = ""
    family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity.value,
            "monetary_impact": round(self.monetary_impact, 2),
            "document_impact": round(self.document_impact, 4),
            "detail": self.detail,
            "family": self.family,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageIssue:
        return cls(
            issue_type=data.get("issue_type", ""),
            severity=CoverageSeverity(data.get("severity", "INFO")),
            monetary_impact=float(data.get("monetary_impact", 0.0)),
            document_impact=float(data.get("document_impact", 0.0)),
            detail=data.get("detail", ""),
            family=data.get("family", ""),
        )


@dataclass
class MonetaryCoverage:
    total_amount: float = 0.0
    explained_amount: float = 0.0
    coverage_pct: float = 0.0
    by_family: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_amount": round(self.total_amount, 2),
            "explained_amount": round(self.explained_amount, 2),
            "coverage_pct": round(self.coverage_pct, 4),
            "by_family": self.by_family,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MonetaryCoverage:
        return cls(
            total_amount=float(data.get("total_amount", 0.0)),
            explained_amount=float(data.get("explained_amount", 0.0)),
            coverage_pct=float(data.get("coverage_pct", 0.0)),
            by_family=data.get("by_family", {}),
        )


@dataclass
class StructuralCoverage:
    subtotals_detected: int = 0
    subtotals_expected: int = 0
    subtotals_validated: int = 0
    subtotals_consistent: int = 0
    hierarchy_reconstructed: float = 0.0
    template_coverage: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "subtotals_detected": self.subtotals_detected,
            "subtotals_expected": self.subtotals_expected,
            "subtotals_validated": self.subtotals_validated,
            "subtotals_consistent": self.subtotals_consistent,
            "hierarchy_reconstructed": round(self.hierarchy_reconstructed, 4),
            "template_coverage": round(self.template_coverage, 4),
            "overall": round(self.overall, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuralCoverage:
        return cls(
            subtotals_detected=int(data.get("subtotals_detected", 0)),
            subtotals_expected=int(data.get("subtotals_expected", 0)),
            subtotals_validated=int(data.get("subtotals_validated", 0)),
            subtotals_consistent=int(data.get("subtotals_consistent", 0)),
            hierarchy_reconstructed=float(data.get("hierarchy_reconstructed", 0.0)),
            template_coverage=float(data.get("template_coverage", 0.0)),
            overall=float(data.get("overall", 0.0)),
        )


@dataclass
class SemanticCoverage:
    total_accounts: int = 0
    classified_count: int = 0
    known_count: int = 0
    learning_hits: int = 0
    kb_matches: int = 0
    review_workspace: int = 0
    unknown_count: int = 0
    by_family: dict[str, dict[str, float | int]] = field(default_factory=dict)
    overall: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_accounts": self.total_accounts,
            "classified_count": self.classified_count,
            "known_count": self.known_count,
            "learning_hits": self.learning_hits,
            "kb_matches": self.kb_matches,
            "review_workspace": self.review_workspace,
            "unknown_count": self.unknown_count,
            "by_family": self.by_family,
            "overall": round(self.overall, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SemanticCoverage:
        return cls(
            total_accounts=int(data.get("total_accounts", 0)),
            classified_count=int(data.get("classified_count", 0)),
            known_count=int(data.get("known_count", 0)),
            learning_hits=int(data.get("learning_hits", 0)),
            kb_matches=int(data.get("kb_matches", 0)),
            review_workspace=int(data.get("review_workspace", 0)),
            unknown_count=int(data.get("unknown_count", 0)),
            by_family=data.get("by_family", {}),
            overall=float(data.get("overall", 0.0)),
        )


@dataclass
class DocumentCoverage:
    expected_sections: list[str] = field(default_factory=list)
    present_sections: list[str] = field(default_factory=list)
    correct_sections: list[str] = field(default_factory=list)
    not_applicable_sections: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    section_details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_sections": self.expected_sections,
            "present_sections": self.present_sections,
            "correct_sections": self.correct_sections,
            "not_applicable_sections": self.not_applicable_sections,
            "coverage_pct": round(self.coverage_pct, 4),
            "section_details": self.section_details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentCoverage:
        return cls(
            expected_sections=data.get("expected_sections", []),
            present_sections=data.get("present_sections", []),
            correct_sections=data.get("correct_sections", []),
            not_applicable_sections=data.get("not_applicable_sections", []),
            coverage_pct=float(data.get("coverage_pct", 0.0)),
            section_details=data.get("section_details", {}),
        )


@dataclass
class CoverageResult:
    monetary: MonetaryCoverage = field(default_factory=MonetaryCoverage)
    structural: StructuralCoverage = field(default_factory=StructuralCoverage)
    semantic: SemanticCoverage = field(default_factory=SemanticCoverage)
    document: DocumentCoverage = field(default_factory=DocumentCoverage)
    overall: float = 0.0
    weights: dict[str, float] = field(default_factory=dict)
    issues: list[CoverageIssue] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "monetary": self.monetary.to_dict(),
            "structural": self.structural.to_dict(),
            "semantic": self.semantic.to_dict(),
            "document": self.document.to_dict(),
            "overall": round(self.overall, 4),
            "weights": dict(self.weights),
            "issues": [i.to_dict() for i in self.issues],
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageResult:
        return cls(
            monetary=MonetaryCoverage.from_dict(data.get("monetary", {})),
            structural=StructuralCoverage.from_dict(data.get("structural", {})),
            semantic=SemanticCoverage.from_dict(data.get("semantic", {})),
            document=DocumentCoverage.from_dict(data.get("document", {})),
            overall=float(data.get("overall", 0.0)),
            weights=data.get("weights", {}),
            issues=[CoverageIssue.from_dict(i) for i in data.get("issues", [])],
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class CoverageStatistics:
    total_documents: int = 0
    overall_avg: float = 0.0
    overall_median: float = 0.0
    overall_p25: float = 0.0
    overall_p75: float = 0.0
    monetary_avg: float = 0.0
    structural_avg: float = 0.0
    semantic_avg: float = 0.0
    document_avg: float = 0.0
    by_family: dict[str, dict[str, float]] = field(default_factory=dict)
    by_template: dict[str, dict[str, float]] = field(default_factory=dict)
    by_parser: dict[str, dict[str, float]] = field(default_factory=dict)
    by_company: dict[str, dict[str, float]] = field(default_factory=dict)
    by_year: dict[str, dict[str, float]] = field(default_factory=dict)
    distribution: dict[str, int] = field(default_factory=dict)
    all_scores: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "overall_avg": round(self.overall_avg, 4),
            "overall_median": round(self.overall_median, 4),
            "overall_p25": round(self.overall_p25, 4),
            "overall_p75": round(self.overall_p75, 4),
            "monetary_avg": round(self.monetary_avg, 4),
            "structural_avg": round(self.structural_avg, 4),
            "semantic_avg": round(self.semantic_avg, 4),
            "document_avg": round(self.document_avg, 4),
            "by_family": self.by_family,
            "by_template": self.by_template,
            "by_parser": self.by_parser,
            "by_company": self.by_company,
            "by_year": self.by_year,
            "distribution": self.distribution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageStatistics:
        return cls(
            total_documents=int(data.get("total_documents", 0)),
            overall_avg=float(data.get("overall_avg", 0.0)),
            overall_median=float(data.get("overall_median", 0.0)),
            overall_p25=float(data.get("overall_p25", 0.0)),
            overall_p75=float(data.get("overall_p75", 0.0)),
            monetary_avg=float(data.get("monetary_avg", 0.0)),
            structural_avg=float(data.get("structural_avg", 0.0)),
            semantic_avg=float(data.get("semantic_avg", 0.0)),
            document_avg=float(data.get("document_avg", 0.0)),
            by_family=data.get("by_family", {}),
            by_template=data.get("by_template", {}),
            by_parser=data.get("by_parser", {}),
            by_company=data.get("by_company", {}),
            by_year=data.get("by_year", {}),
            distribution=data.get("distribution", {}),
            all_scores=data.get("all_scores", []),
        )


@dataclass
class CoverageSummary:
    overall: float = 0.0
    monetary: float = 0.0
    structural: float = 0.0
    semantic: float = 0.0
    document: float = 0.0
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    top_documents: list[dict[str, Any]] = field(default_factory=list)
    worst_documents: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "monetary": round(self.monetary, 4),
            "structural": round(self.structural, 4),
            "semantic": round(self.semantic, 4),
            "document": round(self.document, 4),
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "high_issues": self.high_issues,
            "top_documents": self.top_documents,
            "worst_documents": self.worst_documents,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverageSummary:
        return cls(
            overall=float(data.get("overall", 0.0)),
            monetary=float(data.get("monetary", 0.0)),
            structural=float(data.get("structural", 0.0)),
            semantic=float(data.get("semantic", 0.0)),
            document=float(data.get("document", 0.0)),
            total_issues=int(data.get("total_issues", 0)),
            critical_issues=int(data.get("critical_issues", 0)),
            high_issues=int(data.get("high_issues", 0)),
            top_documents=data.get("top_documents", []),
            worst_documents=data.get("worst_documents", []),
        )
