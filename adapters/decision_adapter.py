from __future__ import annotations

from document_context import DocumentContext

from decision_engine import (
    Decision, DecisionType, DecisionScore,
    EvidenceCollector, ConflictResolver, ConfidenceCalculator,
    Scorer, ExplanationGenerator, DecisionStatisticsCollector,
)


class DecisionAdapter:
    def __init__(self, weights: dict[str, float] | None = None):
        self._conflict_resolver = ConflictResolver()
        self._confidence = ConfidenceCalculator(weights=weights)
        self._scorer = Scorer()
        self._explainer = ExplanationGenerator(confidence=self._confidence)
        self._stats = DecisionStatisticsCollector()

    def run(self, ctx: DocumentContext) -> DocumentContext:
        classified = ctx.get_custom("classified", [])
        all_evidence = EvidenceCollector.collect_all(ctx)
        decisions = []

        for acct in classified:
            d = self._decide_for_account(acct, ctx, all_evidence)
            decisions.append(d)
            self._stats.add(d)

        stats = self._stats.compute()
        ctx.set_custom("decisions", [d.to_dict() for d in decisions])
        ctx.set_custom("decision_stats", stats.to_dict())
        ctx.set_custom("decision_conflicts", stats.conflicts_detected)

        ctx.set_custom("decision_confidence_real", stats.avg_confidence)
        ctx.set_custom("decision_coverage_real", self._compute_coverage(ctx))

        return ctx

    def _decide_for_account(
        self,
        acct: dict,
        ctx: DocumentContext,
        all_evidence: list,
    ) -> Decision:
        account_code = acct.get("account_code", "")
        account_name = acct.get("account_name", "")
        final_code = acct.get("final_code") or acct.get("standard_code") or ""
        method = acct.get("method", "unknown")
        confidence = float(acct.get("confidence", 0.0))

        evidence = [
            e for e in all_evidence
            if e.source in ("parser", "knowledge", "structure", "validation", "die")
        ]

        conflicts = self._conflict_resolver.resolve(evidence)
        score = self._scorer.compute(evidence, ctx)
        explanation = self._explainer.generate(
            account_code=account_code,
            account_name=account_name,
            classified_code=final_code,
            evidence=evidence,
            conflicts=conflicts,
            score=score,
        )

        decision_type = self._determine_decision_type(
            method=method,
            confidence=confidence,
            score=score,
            conflicts=conflicts,
        )

        return Decision(
            account_code=account_code,
            account_name=account_name,
            decision_type=decision_type,
            final_code=final_code,
            confidence=round(confidence, 4),
            evidence=evidence,
            conflicts=conflicts,
            score=score,
            explanation=explanation,
        )

    def _determine_decision_type(
        self,
        method: str,
        confidence: float,
        score: DecisionScore,
        conflicts: list,
    ) -> DecisionType:
        if method == "ignored":
            return DecisionType.REJECT
        if method == "unclassified":
            return DecisionType.MANUAL_REVIEW
        if method.startswith("learning_"):
            return DecisionType.LEARNING
        if conflicts and any(c.severity.value == "CRITICAL" for c in conflicts):
            return DecisionType.MANUAL_REVIEW
        if confidence >= 0.7 and score.weighted_total >= 0.6:
            return DecisionType.CONTINUE
        if confidence >= 0.4:
            return DecisionType.STRESS
        return DecisionType.MANUAL_REVIEW

    def _compute_coverage(self, ctx: DocumentContext) -> float:
        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        total = len(classified) + len(ignored)
        if total == 0:
            return 0.0
        return round(len(classified) / total, 4)
