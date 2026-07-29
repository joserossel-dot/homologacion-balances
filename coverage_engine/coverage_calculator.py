from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from document_context import DocumentContext

from .models import (
    CoverageResult, CoverageIssue, DEFAULT_COVERAGE_WEIGHTS,
)
from .monetary_coverage import MonetaryCoverageCalculator
from .structural_coverage import StructuralCoverageCalculator
from .semantic_coverage import SemanticCoverageCalculator
from .document_coverage import DocumentCoverageCalculator


class CoverageCalculator:
    """Calculadora de cobertura consolidada.

    Recibe un DocumentContext y produce un CoverageResult con:
    - Monetary Coverage
    - Structural Coverage
    - Semantic Coverage
    - Document Coverage
    - Coverage total (ponderado)

    Los pesos son configurables (no hardcodeados).
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = {**DEFAULT_COVERAGE_WEIGHTS}
        if weights:
            self._weights.update(weights)
        self._validate_weights()

        self._monetary = MonetaryCoverageCalculator()
        self._structural = StructuralCoverageCalculator()
        self._semantic = SemanticCoverageCalculator()
        self._document = DocumentCoverageCalculator()

    def _validate_weights(self) -> None:
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.001:
            import logging
            logging.warning(
                "Coverage weights sum to %.4f (expected 1.0). Using as-is.",
                total,
            )

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def compute(self, ctx: DocumentContext) -> CoverageResult:
        all_issues: list[CoverageIssue] = []

        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        decisions = ctx.get_custom("decisions", [])
        validation_data = ctx.validation
        structure_data = ctx.structure
        metadata = ctx.metadata
        knowledge_data = ctx.knowledge

        monetary, m_issues = self._monetary.compute_from_ctx(
            classified=classified,
            validation_data=validation_data,
            structure_data=structure_data,
        )
        all_issues.extend(m_issues)

        structural, s_issues = self._structural.compute(
            structure_data=structure_data,
            validation_data=validation_data,
        )
        all_issues.extend(s_issues)

        semantic, sem_issues = self._semantic.compute_from_ctx(
            classified=classified,
            decisions=decisions,
            knowledge_data=knowledge_data,
            ignored=ignored,
        )
        all_issues.extend(sem_issues)

        document, d_issues = self._document.compute(
            structure_data=structure_data,
            metadata=metadata,
        )
        all_issues.extend(d_issues)

        overall = (
            self._weights.get("monetary", 0.0) * monetary.coverage_pct
            + self._weights.get("structural", 0.0) * structural.overall
            + self._weights.get("semantic", 0.0) * semantic.overall
            + self._weights.get("document", 0.0) * document.coverage_pct
        )

        result = CoverageResult(
            monetary=monetary,
            structural=structural,
            semantic=semantic,
            document=document,
            overall=overall,
            weights=dict(self._weights),
            issues=all_issues,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return result

    def compute_from_data(
        self,
        classified: list[dict[str, Any]],
        ignored: list[dict[str, Any]] | None = None,
        decisions: list[dict[str, Any]] | None = None,
        validation_data: Any = None,
        structure_data: Any = None,
        metadata: Any = None,
        knowledge_data: Any = None,
    ) -> CoverageResult:
        all_issues: list[CoverageIssue] = []
        ignored = ignored or []

        monetary, m_issues = self._monetary.compute_from_ctx(
            classified=classified,
            validation_data=validation_data,
            structure_data=structure_data,
        )
        all_issues.extend(m_issues)

        structural, s_issues = self._structural.compute(
            structure_data=structure_data,
            validation_data=validation_data,
        )
        all_issues.extend(s_issues)

        semantic, sem_issues = self._semantic.compute_from_ctx(
            classified=classified,
            decisions=decisions,
            knowledge_data=knowledge_data,
            ignored=ignored,
        )
        all_issues.extend(sem_issues)

        document, d_issues = self._document.compute(
            structure_data=structure_data,
            metadata=metadata,
        )
        all_issues.extend(d_issues)

        overall = (
            self._weights.get("monetary", 0.0) * monetary.coverage_pct
            + self._weights.get("structural", 0.0) * structural.overall
            + self._weights.get("semantic", 0.0) * semantic.overall
            + self._weights.get("document", 0.0) * document.coverage_pct
        )

        result = CoverageResult(
            monetary=monetary,
            structural=structural,
            semantic=semantic,
            document=document,
            overall=overall,
            weights=dict(self._weights),
            issues=all_issues,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return result
