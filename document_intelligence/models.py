from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentType(str, Enum):
    BALANCE_TRIBUTARIO = "BALANCE_TRIBUTARIO"
    BALANCE_GENERAL = "BALANCE_GENERAL"
    ESTADO_RESULTADOS = "ESTADO_RESULTADOS"
    ESTADO_PATRIMONIO = "ESTADO_PATRIMONIO"
    ESTADO_FLUJO = "ESTADO_FLUJO"
    NOTAS = "NOTAS"
    OTRO = "OTRO"


class Family(str, Enum):
    BALANCE_ESTANDAR = "BALANCE_ESTANDAR"
    EEFF_AUDITADOS = "EEFF_AUDITADOS"
    TRIBUTARIO = "TRIBUTARIO"
    BALANCE_SIMPLE = "BALANCE_SIMPLE"
    CLASIFICADO = "CLASIFICADO"
    CPT_TASACION = "CPT_TASACION"
    DESCONOCIDO = "DESCONOCIDO"


class Complexity(str, Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class Recommendation(str, Enum):
    CONTINUE = "CONTINUE"
    REVIEW = "REVIEW"
    STRESS = "STRESS"
    REJECT = "REJECT"


class ParserName(str, Enum):
    UNIVERSAL = "Universal"
    CORE2 = "Core2"
    EXCEL = "Excel"
    OCR = "OCR"
    DESCONOCIDO = "Desconocido"


@dataclass
class DocumentProfile:
    document_type: DocumentType | None = None
    family: Family | None = None
    template: str | None = None
    template_id: str = ""
    pages: int = 0
    orientation: str = ""
    layout: str = ""
    table_count: int = 0
    column_count: int = 0
    header_style: str = ""
    footer_style: str = ""
    ocr_probability: float = 0.0
    estimated_accounts: int = 0
    estimated_sections: int = 0
    estimated_subtotals: int = 0
    estimated_complexity: Complexity = Complexity.MEDIA

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type.value if self.document_type else None,
            "family": self.family.value if self.family else None,
            "template": self.template,
            "template_id": self.template_id,
            "pages": self.pages,
            "orientation": self.orientation,
            "layout": self.layout,
            "table_count": self.table_count,
            "column_count": self.column_count,
            "header_style": self.header_style,
            "footer_style": self.footer_style,
            "ocr_probability": round(self.ocr_probability, 4),
            "estimated_accounts": self.estimated_accounts,
            "estimated_sections": self.estimated_sections,
            "estimated_subtotals": self.estimated_subtotals,
            "estimated_complexity": self.estimated_complexity.value,
        }


@dataclass
class DocumentClassification:
    document_type: DocumentType
    confidence: float
    signals: list[str] = field(default_factory=list)
    raw_detected_headers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_type": self.document_type.value,
            "confidence": round(self.confidence, 4),
            "signals": self.signals,
            "raw_detected_headers": self.raw_detected_headers[:10],
        }


@dataclass
class FamilyClassification:
    family: Family
    confidence: float
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family.value,
            "confidence": round(self.confidence, 4),
            "signals": self.signals,
        }


@dataclass
class TemplatePrediction:
    template_id: str
    template_name: str
    family: str
    similarity: float
    confidence: float
    matched_sections: int = 0
    total_sections: int = 0
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "family": self.family,
            "similarity": round(self.similarity, 4),
            "confidence": round(self.confidence, 4),
            "matched_sections": self.matched_sections,
            "total_sections": self.total_sections,
        }


@dataclass
class ParserRecommendation:
    parser_name: ParserName
    confidence: float
    reason: str
    fallback_parser: ParserName | None = None
    needs_ocr: bool = False
    estimated_time_ms: int = 0
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser_name": self.parser_name.value,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "fallback_parser": self.fallback_parser.value if self.fallback_parser else None,
            "needs_ocr": self.needs_ocr,
            "estimated_time_ms": self.estimated_time_ms,
        }


@dataclass
class ValidationRecommendation:
    ejecutar_biv: bool = True
    ejecutar_equation: bool = True
    ejecutar_subtotales: bool = True
    ejecutar_missing_accounts: bool = True
    ejecutar_integrity: bool = True
    confidence: float = 1.0
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ejecutar_biv": self.ejecutar_biv,
            "ejecutar_equation": self.ejecutar_equation,
            "ejecutar_subtotales": self.ejecutar_subtotales,
            "ejecutar_missing_accounts": self.ejecutar_missing_accounts,
            "ejecutar_integrity": self.ejecutar_integrity,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class ConfidencePrediction:
    global_score: float
    per_account_signals: int = 0
    known_template_boost: float = 0.0
    known_family_boost: float = 0.0
    ocr_penalty: float = 0.0
    unknown_accounts_penalty: float = 0.0
    validation_boost: float = 0.0
    signals: list[str] = field(default_factory=list)

    @property
    def confidence_pct(self) -> float:
        return round(self.global_score * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_score": round(self.global_score, 4),
            "confidence_pct": self.confidence_pct,
            "known_template_boost": round(self.known_template_boost, 4),
            "known_family_boost": round(self.known_family_boost, 4),
            "ocr_penalty": round(self.ocr_penalty, 4),
            "unknown_accounts_penalty": round(self.unknown_accounts_penalty, 4),
            "validation_boost": round(self.validation_boost, 4),
        }


@dataclass
class CoveragePrediction:
    global_pct: float
    estimated_covered: int = 0
    estimated_total: int = 0
    kb_size: int = 0
    signals: list[str] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        return round(self.global_pct * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_pct": round(self.global_pct, 4),
            "coverage_pct": self.coverage_pct,
            "estimated_covered": self.estimated_covered,
            "estimated_total": self.estimated_total,
            "kb_size": self.kb_size,
        }


@dataclass
class ProcessingRecommendation:
    recommendation: Recommendation
    explanation: str
    complexity: Complexity
    estimated_time_seconds: float
    needs_ocr: bool
    needs_human_review: bool
    severity: str = "info"
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.recommendation.value,
            "explanation": self.explanation,
            "complexity": self.complexity.value,
            "estimated_time_seconds": round(self.estimated_time_seconds, 1),
            "needs_ocr": self.needs_ocr,
            "needs_human_review": self.needs_human_review,
            "severity": self.severity,
        }


@dataclass
class IntelligenceReport:
    profile: DocumentProfile
    classification: DocumentClassification
    family: FamilyClassification
    template: TemplatePrediction | None = None
    parser: ParserRecommendation | None = None
    validation: ValidationRecommendation | None = None
    confidence: ConfidencePrediction | None = None
    coverage: CoveragePrediction | None = None
    recommendation: ProcessingRecommendation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "classification": self.classification.to_dict(),
            "family": self.family.to_dict(),
            "template": self.template.to_dict() if self.template else None,
            "parser": self.parser.to_dict() if self.parser else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
        }

    def summary(self) -> str:
        lines = [
            "═══ Document Intelligence Report ═══",
            f"Documento:        {self.profile.document_type.value if self.profile.document_type else 'N/A'}",
            f"Familia:          {self.profile.family.value if self.profile.family else 'N/A'}",
            f"Template:         {self.profile.template or 'N/A'}",
            f"Parser:           {self.parser.parser_name.value if self.parser else 'N/A'}",
            f"Validaciones:     {'BIV' if self.validation and self.validation.ejecutar_biv else 'N/A'}",
            f"Confianza:        {self.confidence.confidence_pct if self.confidence else 'N/A'}%",
            f"Cobertura:        {self.coverage.coverage_pct if self.coverage else 'N/A'}%",
            f"Complejidad:      {self.recommendation.complexity.value if self.recommendation else 'N/A'}",
            f"Tiempo estimado:  {self.recommendation.estimated_time_seconds if self.recommendation else 0:.1f}s",
            f"Necesita OCR:     {'Sí' if self.recommendation and self.recommendation.needs_ocr else 'No'}",
            f"Revisión humana:  {'Sí' if self.recommendation and self.recommendation.needs_human_review else 'No'}",
            f"Recomendación:    {self.recommendation.recommendation.value if self.recommendation else 'N/A'}",
        ]
        return "\n".join(lines)
