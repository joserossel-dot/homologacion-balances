from __future__ import annotations

from typing import Any

from document_context import DocumentContext

from .models import DecisionEvidence, DecisionConflict, DecisionScore
from .evidence import EvidenceCollector
from .conflict_resolver import ConflictResolver
from .confidence import ConfidenceCalculator
from .scorer import Scorer


class EvidenceAggregator:
    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = weights or {}
        self._conflict_resolver = ConflictResolver()
        self._confidence = ConfidenceCalculator(weights=self._weights if self._weights else None)
        self._scorer = Scorer()

    def aggregate(self, ctx: DocumentContext) -> dict[str, Any]:
        evidence = EvidenceCollector.collect_all(ctx)
        conflicts = self._conflict_resolver.resolve(evidence)
        score = self._scorer.compute(evidence, ctx)
        confidence = self._confidence.compute(evidence, ctx)
        return {
            "evidence": evidence,
            "conflicts": conflicts,
            "score": score,
            "confidence": confidence,
        }
