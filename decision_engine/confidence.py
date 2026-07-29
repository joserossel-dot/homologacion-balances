from __future__ import annotations

from typing import Any

from document_context import DocumentContext

from .models import DecisionEvidence


DEFAULT_WEIGHTS: dict[str, float] = {
    "parser": 0.30,
    "knowledge": 0.30,
    "validation": 0.20,
    "structure": 0.10,
    "die": 0.10,
}


class ConfidenceCalculator:
    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = {**DEFAULT_WEIGHTS}
        if weights:
            self._weights.update(weights)
        self._validate_weights()

    def _validate_weights(self) -> None:
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.001:
            import logging
            logging.warning(
                "Confidence weights sum to %.4f (expected 1.0). Normalizing.",
                total,
            )

    def compute(self, evidence: list[DecisionEvidence], ctx: DocumentContext | None = None) -> float:
        module_scores = self._group_by_module(evidence)
        weighted_sum = 0.0
        total_weight = 0.0
        for module, score in module_scores.items():
            w = self._weights.get(module, 0.05)
            weighted_sum += w * score
            total_weight += w
        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 4)

    def compute_per_module(self, evidence: list[DecisionEvidence]) -> dict[str, float]:
        return self._group_by_module(evidence)

    def _group_by_module(self, evidence: list[DecisionEvidence]) -> dict[str, float]:
        module_scores: dict[str, list[float]] = {}
        for e in evidence:
            if e.source not in module_scores:
                module_scores[e.source] = []
            module_scores[e.source].append(e.confidence)
        result: dict[str, float] = {}
        for module, scores in module_scores.items():
            result[module] = round(sum(scores) / len(scores), 4) if scores else 0.0
        return result

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)
