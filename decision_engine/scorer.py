from __future__ import annotations

from typing import Any

from document_context import DocumentContext

from .models import DecisionEvidence, DecisionScore


class Scorer:
    def compute(
        self,
        evidence: list[DecisionEvidence],
        ctx: DocumentContext | None = None,
    ) -> DecisionScore:
        confidence = self._confidence_score(evidence)
        coverage = self._coverage_score(evidence, ctx)
        quality = self._evidence_quality(evidence)
        consistency = self._consistency_score(evidence)
        learning = self._learning_weight(ctx)
        return DecisionScore(
            confidence=confidence,
            coverage=coverage,
            evidence_quality=quality,
            consistency=consistency,
            learning_weight=learning,
        )

    def _confidence_score(self, evidence: list[DecisionEvidence]) -> float:
        if not evidence:
            return 0.0
        scores = [e.confidence for e in evidence if e.confidence > 0]
        return round(sum(scores) / len(scores), 4) if scores else 0.0

    def _coverage_score(self, evidence: list[DecisionEvidence], ctx: DocumentContext | None) -> float:
        if ctx is None:
            return 0.0
        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        total = len(classified) + len(ignored)
        if total == 0:
            return 0.0
        classified_count = len(classified)
        return round(classified_count / total, 4)

    def _evidence_quality(self, evidence: list[DecisionEvidence]) -> float:
        if not evidence:
            return 0.0
        high = sum(1 for e in evidence if e.confidence >= 0.8)
        medium = sum(1 for e in evidence if 0.4 <= e.confidence < 0.8)
        total = len(evidence)
        return round((high * 1.0 + medium * 0.5) / total, 4) if total else 0.0

    def _consistency_score(self, evidence: list[DecisionEvidence]) -> float:
        if len(evidence) < 2:
            return 1.0
        scores = [e.confidence for e in evidence]
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        consistency = 1.0 - min(std_dev, 1.0)
        return round(consistency, 4)

    def _learning_weight(self, ctx: DocumentContext | None) -> float:
        if ctx is None:
            return 0.0
        knowledge = ctx.knowledge
        if knowledge is None:
            return 0.0
        learning_count = len(knowledge.learning_hits)
        dict_count = len(knowledge.dictionary_matches)
        total = learning_count + dict_count
        if total == 0:
            return 0.0
        return round(min(total / 20.0, 1.0), 4)
