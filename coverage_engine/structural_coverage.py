from __future__ import annotations

from typing import Any

from .models import (
    StructuralCoverage, CoverageIssue, CoverageSeverity,
    FAMILY_ORDER,
)


class StructuralCoverageCalculator:
    """Calcula cobertura estructural del documento.

    Mide:
    - Subtotales detectados vs esperados
    - Subtotales validados (suma de hijos coincide)
    - Subtotales consistentes (validados + sin conflictos)
    - Jerarquía reconstruida (% nodos en árbol)
    - Template cubierto (% coincidencia con template)
    """

    def compute(
        self,
        structure_data: Any = None,
        validation_data: Any = None,
    ) -> tuple[StructuralCoverage, list[CoverageIssue]]:
        issues: list[CoverageIssue] = []

        subtotals_expected = len(FAMILY_ORDER)
        subtotals_detected = self._count_subtotals(structure_data, validation_data)
        subtotals_validated = self._count_validated_subtotals(validation_data)
        subtotals_consistent = self._count_consistent_subtotals(validation_data)
        hierarchy_reconstructed = self._compute_hierarchy_score(structure_data)
        template_coverage = self._compute_template_coverage(structure_data)

        if subtotals_detected < subtotals_expected:
            missing = subtotals_expected - subtotals_detected
            issues.append(CoverageIssue(
                issue_type="partial_template",
                severity=CoverageSeverity.HIGH if missing > 2 else CoverageSeverity.MEDIUM,
                monetary_impact=0.0,
                document_impact=round(missing / subtotals_expected, 4),
                detail=f"Subtotales detectados: {subtotals_detected}/{subtotals_expected}",
                family="",
            ))

        if subtotals_validated < subtotals_detected:
            diff = subtotals_detected - subtotals_validated
            issues.append(CoverageIssue(
                issue_type="inconsistent_subtotal",
                severity=CoverageSeverity.CRITICAL if diff > 0 else CoverageSeverity.INFO,
                monetary_impact=0.0,
                document_impact=round(diff / max(subtotals_detected, 1), 4),
                detail=f"Subtotales no válidos: {subtotals_detected - subtotals_validated}",
                family="",
            ))

        if hierarchy_reconstructed < 0.9:
            issues.append(CoverageIssue(
                issue_type="hierarchy_incomplete",
                severity=CoverageSeverity.MEDIUM,
                monetary_impact=0.0,
                document_impact=round(1.0 - hierarchy_reconstructed, 4),
                detail=f"Jerarquía reconstruida: {round(hierarchy_reconstructed * 100, 1)}%",
                family="",
            ))

        components = [
            (subtotals_detected / max(subtotals_expected, 1), 0.20),
            (subtotals_validated / max(subtotals_detected, 1), 0.25),
            (subtotals_consistent / max(subtotals_validated, 1), 0.20),
            (hierarchy_reconstructed, 0.20),
            (template_coverage, 0.15),
        ]
        overall = sum(score * weight for score, weight in components)

        structural = StructuralCoverage(
            subtotals_detected=subtotals_detected,
            subtotals_expected=subtotals_expected,
            subtotals_validated=subtotals_validated,
            subtotals_consistent=subtotals_consistent,
            hierarchy_reconstructed=hierarchy_reconstructed,
            template_coverage=template_coverage,
            overall=overall,
        )

        return structural, issues

    def _count_subtotals(self, structure_data: Any, validation_data: Any) -> int:
        count = 0
        if validation_data is not None:
            subtotal_validation = getattr(validation_data, "subtotal_validation", None)
            if subtotal_validation is not None:
                try:
                    count = len(subtotal_validation)
                except (TypeError, ValueError):
                    pass
        if count == 0 and structure_data is not None:
            tree = getattr(structure_data, "tree", None)
            if tree is not None:
                try:
                    count = getattr(tree, "subtotal_count", 0)
                except Exception:
                    pass
        return count

    def _count_validated_subtotals(self, validation_data: Any) -> int:
        if validation_data is None:
            return 0
        subtotal_validation = getattr(validation_data, "subtotal_validation", None)
        if subtotal_validation is None:
            return 0
        try:
            validated = sum(
                1 for sv in subtotal_validation
                if getattr(sv, "passed", False)
            )
            return validated
        except (TypeError, ValueError):
            return 0

    def _count_consistent_subtotals(self, validation_data: Any) -> int:
        if validation_data is None:
            return 0
        subtotal_validation = getattr(validation_data, "subtotal_validation", None)
        if subtotal_validation is None:
            return 0
        try:
            consistent = 0
            for sv in subtotal_validation:
                passed = getattr(sv, "passed", False)
                pct_diff = abs(float(getattr(sv, "pct_diff", 0) or 0))
                if passed and pct_diff < 0.01:
                    consistent += 1
            return consistent
        except (TypeError, ValueError):
            return 0

    def _compute_hierarchy_score(self, structure_data: Any) -> float:
        if structure_data is None:
            return 0.0
        tree = getattr(structure_data, "tree", None)
        if tree is None:
            return 0.0
        try:
            total_nodes = getattr(tree, "total_nodes", 0) or 0
            nodes = getattr(tree, "nodes", []) or []
            if total_nodes == 0:
                return 0.0
            node_count = len(nodes)
            return min(node_count / total_nodes, 1.0) if total_nodes > 0 else 0.0
        except Exception:
            return 0.0

    def _compute_template_coverage(self, structure_data: Any) -> float:
        if structure_data is None:
            return 0.0
        template = getattr(structure_data, "template", "") or ""
        if not template:
            return 0.0
        family = getattr(structure_data, "family", "") or ""
        if not family:
            return 0.5
        return 0.8
