from __future__ import annotations

from typing import Any

from .models import QAConfidence, DEFAULT_CONFIDENCE_WEIGHTS


class ConfidenceEngine:
    """Calcula la confianza general del sistema.

    Combina evidencia de todos los motores:
    - Coverage Engine
    - Decision Engine
    - Validation Engine
    - Parser
    - Knowledge Base
    - Structure Engine
    - Document Intelligence

    Todo determinístico. Sin IA.
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self._weights = {**DEFAULT_CONFIDENCE_WEIGHTS}
        if weights:
            self._weights.update(weights)

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def compute(
        self,
        coverage_data: dict[str, Any] | None = None,
        decision_stats: dict[str, Any] | None = None,
        validation_data: Any = None,
        parser_data: Any = None,
        knowledge_data: Any = None,
        structure_data: Any = None,
        predictions: Any = None,
    ) -> QAConfidence:
        coverage_score = self._coverage_confidence(coverage_data)
        decision_score = self._decision_confidence(decision_stats)
        validation_score = self._validation_confidence(validation_data)
        parser_score = self._parser_confidence(parser_data)
        knowledge_score = self._knowledge_confidence(knowledge_data)
        structure_score = self._structure_confidence(structure_data)
        die_score = self._die_confidence(predictions)

        total_weight = 0.0
        weighted_sum = 0.0
        for score, key in [
            (coverage_score, "coverage"),
            (decision_score, "decision"),
            (validation_score, "validation"),
            (parser_score, "parser"),
            (knowledge_score, "knowledge"),
            (structure_score, "structure"),
            (die_score, "die"),
        ]:
            w = self._weights.get(key, 0.05)
            weighted_sum += w * score
            total_weight += w

        overall = (weighted_sum / total_weight) if total_weight > 0 else 0.0
        overall = round(max(0.0, min(1.0, overall)), 4)

        return QAConfidence(
            overall=overall,
            coverage=round(coverage_score, 4),
            decision=round(decision_score, 4),
            validation=round(validation_score, 4),
            parser=round(parser_score, 4),
            knowledge=round(knowledge_score, 4),
            structure=round(structure_score, 4),
            die=round(die_score, 4),
        )

    def _coverage_confidence(
        self, data: dict[str, Any] | None,
    ) -> float:
        if not data:
            return 0.0
        return float(data.get("overall", 0.0))

    def _decision_confidence(
        self, stats: dict[str, Any] | None,
    ) -> float:
        if not stats:
            return 0.0
        return float(stats.get("avg_confidence", 0.0))

    def _validation_confidence(
        self, validation_data: Any = None,
    ) -> float:
        if validation_data is None:
            return 0.0
        integrity = getattr(validation_data, "integrity", None)
        if integrity is not None:
            overall = getattr(integrity, "overall", 0) or 0
            return float(overall)
        has_errors = getattr(validation_data, "has_errors", False)
        if has_errors:
            return 0.3
        warnings = len(getattr(validation_data, "warnings", []) or [])
        if warnings > 5:
            return 0.5
        if warnings > 0:
            return 0.7
        return 0.9

    def _parser_confidence(
        self, parser_data: Any = None,
    ) -> float:
        if parser_data is None:
            return 0.0
        selected = getattr(parser_data, "selected_parser", "") or ""
        if not selected:
            return 0.0
        total = getattr(parser_data, "total_accounts", 0) or 0
        raw = getattr(parser_data, "total_raw", 0) or 0
        if raw == 0:
            return 0.5
        ratio = total / raw
        score = min(ratio, 1.0)
        score = score * 0.8 + 0.2
        return score

    def _knowledge_confidence(
        self, knowledge_data: Any = None,
    ) -> float:
        if knowledge_data is None:
            return 0.0
        total = getattr(knowledge_data, "total_matches", 0) or 0
        cmcc = len(getattr(knowledge_data, "cmcc_matches", []) or [])
        learning = len(getattr(knowledge_data, "learning_hits", []) or [])
        dictionary = len(getattr(knowledge_data, "dictionary_matches", []) or [])
        total_found = cmcc + learning + dictionary
        if total == 0 and total_found == 0:
            return 0.3
        if total == 0:
            return 0.5
        ratio = total_found / total
        score = min(ratio * 1.2, 1.0)
        return score

    def _structure_confidence(
        self, structure_data: Any = None,
    ) -> float:
        if structure_data is None:
            return 0.0
        family = getattr(structure_data, "family", "") or ""
        template = getattr(structure_data, "template", "") or ""
        sections = getattr(structure_data, "sections", []) or []
        score = 0.0
        if family:
            score += 0.35
        if template:
            score += 0.35
        if sections:
            score += 0.30
        return score

    def _die_confidence(
        self, predictions: Any = None,
    ) -> float:
        if predictions is None:
            return 0.0
        confidence = getattr(predictions, "confidence_expected", 0.0) or 0.0
        coverage = getattr(predictions, "coverage_expected", 0.0) or 0.0
        return float((confidence + coverage) / 2.0)
