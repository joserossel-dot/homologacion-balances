from __future__ import annotations

from document_context import DocumentContext

from .coverage_calculator import CoverageCalculator


class CoverageAdapter:
    """Adapter de Coverage Engine para Pipeline V2.

    Recibe un DocumentContext, ejecuta CoverageCalculator y
    almacena el CoverageResult en ctx.coverage (custom).
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self._calculator = CoverageCalculator(weights=weights)

    def run(self, ctx: DocumentContext) -> DocumentContext:
        result = self._calculator.compute(ctx)
        ctx.set_custom("coverage", result.to_dict())
        ctx.set_custom("coverage_overall", result.overall)
        ctx.set_custom(
            "coverage_monetary", result.monetary.coverage_pct,
        )
        ctx.set_custom(
            "coverage_structural", result.structural.overall,
        )
        ctx.set_custom(
            "coverage_semantic", result.semantic.overall,
        )
        ctx.set_custom(
            "coverage_document", result.document.coverage_pct,
        )
        ctx.set_custom("coverage_issues", [
            i.to_dict() for i in result.issues
        ])
        ctx.set_custom("coverage_weights", dict(result.weights))

        return ctx
