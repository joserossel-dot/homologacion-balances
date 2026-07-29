from __future__ import annotations

from typing import Any

from .models import QARisk, RiskLevel, DEFAULT_RISK_WEIGHTS
from .models import risk_level_from_score, risk_score_from_coverage


class RiskCalculator:
    """Calcula el riesgo del documento en 5 dimensiones.

    Cada riesgo se expresa en escala 0-100:
    - document_risk: secciones faltantes o incorrectas
    - structural_risk: problemas de jerarquía/subtotales
    - monetary_risk: montos no explicados
    - semantic_risk: cuentas no clasificadas
    - operational_risk: errores de parser/validación
    - total_risk: combinación ponderada
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = {**DEFAULT_RISK_WEIGHTS}
        if weights:
            self._weights.update(weights)

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def compute(
        self,
        coverage_data: dict[str, Any] | None = None,
        validation_data: Any = None,
        parser_data: Any = None,
        structure_data: Any = None,
        decision_stats: dict[str, Any] | None = None,
    ) -> QARisk:
        doc_risk = self._document_risk(coverage_data)
        struct_risk = self._structural_risk(coverage_data, structure_data)
        mon_risk = self._monetary_risk(coverage_data)
        sem_risk = self._semantic_risk(coverage_data)
        op_risk = self._operational_risk(
            validation_data, parser_data, decision_stats,
        )

        total = (
            self._weights.get("document", 0.15) * doc_risk
            + self._weights.get("structural", 0.20) * struct_risk
            + self._weights.get("monetary", 0.25) * mon_risk
            + self._weights.get("semantic", 0.20) * sem_risk
            + self._weights.get("operational", 0.20) * op_risk
        )

        level = risk_level_from_score(total)

        return QARisk(
            document_risk=round(doc_risk, 2),
            structural_risk=round(struct_risk, 2),
            monetary_risk=round(mon_risk, 2),
            semantic_risk=round(sem_risk, 2),
            operational_risk=round(op_risk, 2),
            total_risk=round(total, 2),
            level=level,
        )

    def _document_risk(
        self, coverage_data: dict[str, Any] | None,
    ) -> float:
        if not coverage_data:
            return 50.0
        document = coverage_data.get("document", {}) or {}
        cov = float(document.get("coverage_pct", 0.0))
        return risk_score_from_coverage(cov)

    def _structural_risk(
        self,
        coverage_data: dict[str, Any] | None,
        structure_data: Any = None,
    ) -> float:
        if coverage_data:
            structural = coverage_data.get("structural", {}) or {}
            cov = float(structural.get("overall", 0.0))
            return risk_score_from_coverage(cov)
        if structure_data is not None:
            family = getattr(structure_data, "family", "") or ""
            template = getattr(structure_data, "template", "") or ""
            if not family and not template:
                return 70.0
            if not family or not template:
                return 40.0
            return 10.0
        return 50.0

    def _monetary_risk(
        self, coverage_data: dict[str, Any] | None,
    ) -> float:
        if not coverage_data:
            return 50.0
        monetary = coverage_data.get("monetary", {}) or {}
        cov = float(monetary.get("coverage_pct", 0.0))
        total = float(monetary.get("total_amount", 0.0))
        explained = float(monetary.get("explained_amount", 0.0))
        base_risk = risk_score_from_coverage(cov)
        if total > 0 and (total - explained) > total * 0.1:
            base_risk = min(base_risk + 15, 100)
        return base_risk

    def _semantic_risk(
        self, coverage_data: dict[str, Any] | None,
    ) -> float:
        if not coverage_data:
            return 50.0
        semantic = coverage_data.get("semantic", {}) or {}
        cov = float(semantic.get("overall", 0.0))
        unknown = semantic.get("unknown_count", 0) or 0
        total = semantic.get("total_accounts", 0) or 0
        base_risk = risk_score_from_coverage(cov)
        if total > 0 and unknown > 0:
            unknown_ratio = unknown / total
            if unknown_ratio > 0.2:
                base_risk = min(base_risk + 20, 100)
        return base_risk

    def _operational_risk(
        self,
        validation_data: Any = None,
        parser_data: Any = None,
        decision_stats: dict[str, Any] | None = None,
    ) -> float:
        risk = 0.0
        signals = 0

        if validation_data is not None:
            errors = len(getattr(validation_data, "errors", []) or [])
            warnings = len(getattr(validation_data, "warnings", []) or [])
            if errors > 0:
                risk += min(errors * 15, 60)
                signals += 1
            if warnings > 5:
                risk += min(warnings * 2, 20)
                signals += 1
            has_errors = getattr(validation_data, "has_errors", False)
            if has_errors:
                risk += 10
                signals += 1

        if parser_data is not None:
            selected = getattr(parser_data, "selected_parser", "") or ""
            if not selected:
                risk += 30
                signals += 1

        if decision_stats is not None:
            conflicts = decision_stats.get("conflicts_detected", 0) or 0
            if conflicts > 0:
                risk += min(conflicts * 5, 25)
                signals += 1

        if signals == 0:
            return 10.0

        return min(risk / signals * 1.5, 100.0)
