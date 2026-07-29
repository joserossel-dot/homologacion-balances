from __future__ import annotations

from typing import Any

from .models import QualityGate, DEFAULT_GATE_THRESHOLDS


class QualityGateEvaluator:
    """Evalúa todos los Quality Gates del sistema.

    Cada gate representa un módulo/engine diferente:
    - Coverage Engine (monetary, structural, semantic, document)
    - Decision Engine
    - Validation Engine
    - Document Intelligence
    - Structure Engine
    - Knowledge Base
    - Parser

    Ningún gate tiene prioridad absoluta. Todos aportan evidencia.
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_GATE_THRESHOLDS}
        if thresholds:
            self._thresholds.update(thresholds)

    @property
    def thresholds(self) -> dict[str, float]:
        return dict(self._thresholds)

    def evaluate(
        self,
        coverage_data: dict[str, Any] | None = None,
        decision_stats: dict[str, Any] | None = None,
        validation_data: Any = None,
        structure_data: Any = None,
        parser_data: Any = None,
        knowledge_data: Any = None,
        predictions: Any = None,
    ) -> list[QualityGate]:
        gates: list[QualityGate] = []

        gates.append(self._eval_monetary_coverage(coverage_data))
        gates.append(self._eval_structural_coverage(coverage_data))
        gates.append(self._eval_semantic_coverage(coverage_data))
        gates.append(self._eval_document_coverage(coverage_data))
        gates.append(self._eval_decision_confidence(decision_stats))
        gates.append(self._eval_validation_integrity(validation_data))
        gates.append(self._eval_parser_success(parser_data))
        gates.append(self._eval_structure_valid(structure_data))
        gates.append(self._eval_knowledge_presence(knowledge_data))
        gates.append(self._eval_die_confidence(predictions))

        return gates

    def _eval_monetary_coverage(
        self, data: dict[str, Any] | None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de coverage"
        if data:
            monetary = data.get("monetary", {}) or {}
            score = float(monetary.get("coverage_pct", 0.0))
            total = float(monetary.get("total_amount", 0.0))
            explained = float(monetary.get("explained_amount", 0.0))
            detail = (
                f"Monetario: {score:.2%} "
                f"({explained:,.0f}/{total:,.0f})"
            )
        threshold = self._thresholds.get("monetary_coverage", 0.95)
        return QualityGate(
            name="monetary_coverage",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_structural_coverage(
        self, data: dict[str, Any] | None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de coverage"
        if data:
            structural = data.get("structural", {}) or {}
            score = float(structural.get("overall", 0.0))
            detected = structural.get("subtotals_detected", 0)
            expected = structural.get("subtotals_expected", 0)
            detail = (
                f"Estructural: {score:.2%} "
                f"({detected}/{expected} subtotales)"
            )
        threshold = self._thresholds.get("structural_coverage", 0.85)
        return QualityGate(
            name="structural_coverage",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_semantic_coverage(
        self, data: dict[str, Any] | None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de coverage"
        if data:
            semantic = data.get("semantic", {}) or {}
            score = float(semantic.get("overall", 0.0))
            classified = semantic.get("classified_count", 0)
            total = semantic.get("total_accounts", 0)
            detail = (
                f"Semántico: {score:.2%} "
                f"({classified}/{total} cuentas)"
            )
        threshold = self._thresholds.get("semantic_coverage", 0.80)
        return QualityGate(
            name="semantic_coverage",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_document_coverage(
        self, data: dict[str, Any] | None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de coverage"
        if data:
            document = data.get("document", {}) or {}
            score = float(document.get("coverage_pct", 0.0))
            ps = document.get("present_sections", [])
            present = len(ps) if isinstance(ps, (list, tuple)) else int(ps)
            es = document.get("expected_sections", [])
            expected = len(es) if isinstance(es, (list, tuple)) else int(es)
            detail = (
                f"Documental: {score:.2%} "
                f"({present}/{expected} secciones)"
            )
        threshold = self._thresholds.get("document_coverage", 0.90)
        return QualityGate(
            name="document_coverage",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_decision_confidence(
        self, stats: dict[str, Any] | None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de decisión"
        if stats:
            score = float(stats.get("avg_confidence", 0.0))
            total = stats.get("total_decisions", 0)
            detail = f"Decisión: {score:.2%} (promedio {total} decisiones)"
        threshold = self._thresholds.get("decision_confidence", 0.70)
        return QualityGate(
            name="decision_confidence",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_validation_integrity(
        self, validation_data: Any = None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de validación"
        if validation_data is not None:
            has_errors = getattr(validation_data, "has_errors", False)
            has_warnings = getattr(validation_data, "has_warnings", False)
            integrity = getattr(validation_data, "integrity", None)
            if integrity is not None:
                overall = getattr(integrity, "overall", 0) or 0
                score = float(overall)
            elif not has_errors:
                score = 1.0
            warnings_count = len(getattr(validation_data, "warnings", []) or [])
            errors_count = len(getattr(validation_data, "errors", []) or [])
            detail = (
                f"Validación: {score:.2%} "
                f"({errors_count} errores, {warnings_count} advertencias)"
            )
        threshold = self._thresholds.get("validation_integrity", 0.80)
        return QualityGate(
            name="validation_integrity",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_parser_success(
        self, parser_data: Any = None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de parser"
        if parser_data is not None:
            selected = getattr(parser_data, "selected_parser", "") or ""
            total = getattr(parser_data, "total_accounts", 0) or 0
            raw = getattr(parser_data, "total_raw", 0) or 0
            if selected:
                score = min(total / max(raw, 1), 1.0) if raw > 0 else 0.5
            detail = (
                f"Parser: {score:.2%} "
                f"(parser={selected}, cuentas={total})"
            )
        threshold = self._thresholds.get("parser_success", 0.50)
        return QualityGate(
            name="parser_success",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_structure_valid(
        self, structure_data: Any = None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de estructura"
        if structure_data is not None:
            family = getattr(structure_data, "family", "") or ""
            template = getattr(structure_data, "template", "") or ""
            doc_type = getattr(structure_data, "document_type", "") or ""
            has_family = bool(family)
            has_template = bool(template)
            has_type = bool(doc_type)
            signals = sum([has_family, has_template, has_type])
            score = signals / 3.0
            detail = (
                f"Estructura: {score:.2%} "
                f"(familia={family}, template={template})"
            )
        threshold = self._thresholds.get("structure_valid", 0.50)
        return QualityGate(
            name="structure_valid",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_knowledge_presence(
        self, knowledge_data: Any = None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de knowledge base"
        if knowledge_data is not None:
            cmcc = len(getattr(knowledge_data, "cmcc_matches", []) or [])
            learning = len(getattr(knowledge_data, "learning_hits", []) or [])
            dictionary = len(getattr(knowledge_data, "dictionary_matches", []) or [])
            total_found = cmcc + learning + dictionary
            score = min(total_found / 3.0, 1.0)
            detail = (
                f"KB: {score:.2%} "
                f"({total_found} matches)"
            )
        threshold = self._thresholds.get("knowledge_presence", 0.30)
        return QualityGate(
            name="knowledge_presence",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )

    def _eval_die_confidence(
        self, predictions: Any = None,
    ) -> QualityGate:
        score = 0.0
        detail = "Sin datos de DIE"
        if predictions is not None:
            confidence = getattr(predictions, "confidence_expected", 0.0) or 0.0
            coverage = getattr(predictions, "coverage_expected", 0.0) or 0.0
            score = float((confidence + coverage) / 2.0)
            detail = (
                f"DIE: {score:.2%} "
                f"(confianza={confidence:.2%}, coverage={coverage:.2%})"
            )
        threshold = self._thresholds.get("die_confidence", 0.50)
        return QualityGate(
            name="die_confidence",
            passed=score >= threshold,
            score=score,
            weight=threshold,
            detail=detail,
        )
