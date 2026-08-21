from __future__ import annotations

from typing import Any

from .models import (
    ApprovalState, QAResult, QARisk, QAConfidence, QualityGate,
    QAIssue, QARecommendation,
)


class ApprovalEngine:
    """Motor de aprobación basado en reglas configurables.

    Evalúa toda la evidencia disponible y determina el estado de aprobación:
    APPROVED, APPROVED_WITH_WARNINGS, MANUAL_REVIEW, LEARNING, STRESS, REJECTED, FAILED.

    Reglas (configurables por pesos/thresholds):

    1. APPROVED:
       - Coverage monetario >= 95%
       - Coverage estructural >= 85%
       - Coverage semántico >= 80%
       - Sin issues CRITICAL
       - Confianza >= 0.70

    2. APPROVED_WITH_WARNINGS:
       - Coverage monetario >= 85%
       - Coverage estructural >= 70%
       - Sin issues CRITICAL
       - Confianza >= 0.50

    3. REJECTED:
       - Documento no es balance (structure invalid)
       - Coverage monetario < 30%
       - Issues CRITICAL de parser/validación

    4. LEARNING:
       - Template nuevo/desconocido
       - Parser correcto
       - Coverage alto (monetario >= 80%)

    5. STRESS:
       - Formato extremadamente raro
       - Coverage muy bajo pero documento parece válido

    6. FAILED:
       - Errores de procesamiento graves
       - Sin parser
       - Sin datos

    Por defecto: MANUAL_REVIEW
    """

    def __init__(
        self,
        thresholds: dict[str, float] | None = None,
    ):
        self._thresholds = {
            "approve_monetary": 0.95,
            "approve_structural": 0.85,
            "approve_semantic": 0.80,
            "approve_document": 0.90,
            "approve_confidence": 0.70,
            "warn_monetary": 0.85,
            "warn_structural": 0.70,
            "warn_confidence": 0.50,
            "reject_monetary": 0.30,
            "learning_monetary": 0.80,
            "stress_monetary": 0.40,
            "stress_structural": 0.30,
            "max_issues_approve": 0,
            "max_warnings_approve": 5,
        }
        if thresholds:
            self._thresholds.update(thresholds)

    def decide(
        self,
        coverage_data: dict[str, Any] | None = None,
        gates: list[QualityGate] | None = None,
        issues: list[QAIssue] | None = None,
        risk: QARisk | None = None,
        confidence: QAConfidence | None = None,
        structure_data: Any = None,
        parser_data: Any = None,
        validation_data: Any = None,
    ) -> tuple[ApprovalState, str]:
        gates = gates or []
        issues = issues or []

        monetary_cov = self._get_coverage_value(coverage_data, "monetary")
        structural_cov = self._get_coverage_value(coverage_data, "structural")
        semantic_cov = self._get_coverage_value(coverage_data, "semantic")
        document_cov = self._get_coverage_value(coverage_data, "document")
        conf_score = confidence.overall if confidence else 0.0
        risk_score = risk.total_risk if risk else 0.0

        t = self._thresholds

        critical_issues = [i for i in issues if i.severity == "CRITICAL"]
        high_issues = [i for i in issues if i.severity == "HIGH"]
        has_validation_errors = self._has_validation_errors(validation_data)

        if self._should_fail(
            parser_data, coverage_data, validation_data,
        ):
            return ApprovalState.FAILED, (
                "Documento falló: sin parser, sin datos de coverage, "
                "o errores de procesamiento graves"
            )

        if self._should_reject(
            structure_data, monetary_cov, critical_issues,
            has_validation_errors, gates,
        ):
            reasons = []
            if not self._is_balance(structure_data):
                reasons.append("no corresponde a un balance")
            if monetary_cov < t["reject_monetary"]:
                reasons.append(f"coverage monetario {monetary_cov:.1%}")
            if critical_issues:
                reasons.append(f"{len(critical_issues)} issue(s) crítico(s)")
            return ApprovalState.REJECTED, (
                "Documento rechazado: " + ", ".join(reasons)
            )

        if self._should_stress(
            structure_data, monetary_cov, structural_cov,
            gates, risk_score,
        ):
            return ApprovalState.STRESS, (
                "Documento en STRESS: formato extremadamente raro "
                f"(monetario={monetary_cov:.1%}, estructural={structural_cov:.1%})"
            )

        if self._should_learn(
            structure_data, monetary_cov, parser_data,
            gates, confidence,
        ):
            return ApprovalState.LEARNING, (
                "Documento enviado a aprendizaje: template nuevo "
                f"con parser correcto (coverage={monetary_cov:.1%})"
            )

        if self._should_approve(
            monetary_cov, structural_cov, semantic_cov, document_cov,
            conf_score, critical_issues, gates,
        ):
            return ApprovalState.APPROVED, (
                "Documento aprobado para exportación automática: "
                f"monetario={monetary_cov:.1%}, estructural={structural_cov:.1%}, "
                f"semántico={semantic_cov:.1%}, confianza={conf_score:.1%}"
            )

        if self._should_approve_warnings(
            monetary_cov, structural_cov, conf_score, critical_issues,
            high_issues, gates,
        ):
            warnings_detail = ""
            if high_issues:
                warnings_detail = f" ({len(high_issues)} advertencia(s))"
            return ApprovalState.APPROVED_WITH_WARNINGS, (
                "Documento aprobado con advertencias" + warnings_detail + ": "
                f"monetario={monetary_cov:.1%}, estructural={structural_cov:.1%}"
            )

        review_reasons = []
        if monetary_cov < t["approve_monetary"]:
            review_reasons.append(f"coverage monetario bajo ({monetary_cov:.1%})")
        if structural_cov < t["approve_structural"]:
            review_reasons.append(f"coverage estructural bajo ({structural_cov:.1%})")
        if semantic_cov < t["approve_semantic"]:
            review_reasons.append(f"coverage semántico bajo ({semantic_cov:.1%})")
        if critical_issues:
            review_reasons.append(f"{len(critical_issues)} issue(s) crítico(s)")
        if conf_score < t["approve_confidence"]:
            review_reasons.append(f"confianza baja ({conf_score:.1%})")

        return ApprovalState.MANUAL_REVIEW, (
            "Documento requiere revisión manual: "
            + ", ".join(review_reasons)
        )

    def _get_coverage_value(
        self, coverage_data: dict[str, Any] | None, key: str,
    ) -> float:
        if not coverage_data:
            return 0.0
        section = coverage_data.get(key, {}) or {}
        if key == "monetary":
            return float(section.get("coverage_pct", 0.0))
        if key == "structural":
            return float(section.get("overall", 0.0))
        if key == "semantic":
            return float(section.get("overall", 0.0))
        if key == "document":
            return float(section.get("coverage_pct", 0.0))
        return 0.0

    def _is_balance(self, structure_data: Any = None) -> bool:
        if structure_data is None:
            return True
        family = getattr(structure_data, "family", "") or ""
        doc_type = getattr(structure_data, "document_type", "") or ""
        if not family and not doc_type:
            return True
        family_lower = family.lower()
        type_lower = doc_type.lower()
        balance_keywords = [
            "balance", "tributario", "eeff", "activo", "pasivo",
            "patrimonio", "resultado",
        ]
        return any(kw in family_lower or kw in type_lower for kw in balance_keywords)

    def _has_validation_errors(self, validation_data: Any = None) -> bool:
        if validation_data is None:
            return False
        return bool(getattr(validation_data, "has_errors", False))

    def _should_fail(
        self,
        parser_data: Any = None,
        coverage_data: dict[str, Any] | None = None,
        validation_data: Any = None,
    ) -> bool:
        if parser_data is not None:
            selected = getattr(parser_data, "selected_parser", "") or ""
            if not selected:
                return True
        if coverage_data is None:
            return True
        if validation_data is not None:
            errors = getattr(validation_data, "errors", []) or []
            if len(errors) > 10:
                return True
        return False

    def _should_reject(
        self,
        structure_data: Any = None,
        monetary_cov: float = 0.0,
        critical_issues: list[QAIssue] | None = None,
        has_validation_errors: bool = False,
        gates: list[QualityGate] | None = None,
    ) -> bool:
        if critical_issues is None:
            critical_issues = []
        if not self._is_balance(structure_data):
            return True
        if monetary_cov < self._thresholds["reject_monetary"]:
            return True
        parser_fail = False
        for g in (gates or []):
            if g.name == "parser_success" and not g.passed:
                parser_fail = True
        if parser_fail and has_validation_errors:
            return True
        return False

    def _should_stress(
        self,
        structure_data: Any = None,
        monetary_cov: float = 0.0,
        structural_cov: float = 0.0,
        gates: list[QualityGate] | None = None,
        risk_score: float = 0.0,
    ) -> bool:
        t = self._thresholds
        if monetary_cov < t["stress_monetary"] and structural_cov < t["stress_structural"]:
            return True
        if risk_score >= 80:
            return True
        return False

    def _should_learn(
        self,
        structure_data: Any = None,
        monetary_cov: float = 0.0,
        parser_data: Any = None,
        gates: list[QualityGate] | None = None,
        confidence: QAConfidence | None = None,
    ) -> bool:
        t = self._thresholds
        if monetary_cov < t["learning_monetary"]:
            return False
        if structure_data is None:
            return False
        template = getattr(structure_data, "template", "") or ""
        family = getattr(structure_data, "family", "") or ""
        if template or family:
            return False
        if parser_data is not None:
            selected = getattr(parser_data, "selected_parser", "") or ""
            if not selected:
                return False
        return bool(parser_data is not None) and bool(monetary_cov >= t["learning_monetary"])

    def _should_approve(
        self,
        monetary_cov: float = 0.0,
        structural_cov: float = 0.0,
        semantic_cov: float = 0.0,
        document_cov: float = 0.0,
        confidence: float = 0.0,
        critical_issues: list[QAIssue] | None = None,
        gates: list[QualityGate] | None = None,
    ) -> bool:
        t = self._thresholds
        if critical_issues is None:
            critical_issues = []
        if len(critical_issues) > t["max_issues_approve"]:
            return False
        if monetary_cov < t["approve_monetary"]:
            return False
        if structural_cov < t["approve_structural"]:
            return False
        if semantic_cov < t["approve_semantic"]:
            return False
        if document_cov < t["approve_document"]:
            return False
        if confidence < t["approve_confidence"]:
            return False
        return True

    def _should_approve_warnings(
        self,
        monetary_cov: float = 0.0,
        structural_cov: float = 0.0,
        confidence: float = 0.0,
        critical_issues: list[QAIssue] | None = None,
        high_issues: list[QAIssue] | None = None,
        gates: list[QualityGate] | None = None,
    ) -> bool:
        t = self._thresholds
        if critical_issues is None:
            critical_issues = []
        if high_issues is None:
            high_issues = []
        if len(critical_issues) > 0:
            return False
        if monetary_cov < t["warn_monetary"]:
            return False
        if structural_cov < t["warn_structural"]:
            return False
        if confidence < t["warn_confidence"]:
            return False
        return True
