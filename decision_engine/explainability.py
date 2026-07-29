from __future__ import annotations

from typing import Any

from .models import DecisionEvidence, DecisionConflict, DecisionExplanation, DecisionScore
from .confidence import ConfidenceCalculator


class ExplanationGenerator:
    def __init__(self, confidence: ConfidenceCalculator | None = None):
        self._confidence = confidence or ConfidenceCalculator()

    def generate(
        self,
        account_code: str,
        account_name: str,
        classified_code: str,
        evidence: list[DecisionEvidence],
        conflicts: list[DecisionConflict],
        score: DecisionScore | None = None,
    ) -> DecisionExplanation:
        reasons: list[str] = []
        evidence_summary: list[dict[str, Any]] = []
        confidence_breakdown: dict[str, float] = {}

        for e in evidence:
            evidence_summary.append(e.to_dict())
            module = e.source
            if module not in confidence_breakdown:
                confidence_breakdown[module] = e.confidence
            else:
                confidence_breakdown[module] = max(confidence_breakdown[module], e.confidence)

        for e in evidence:
            if e.confidence >= 0.8:
                reasons.append(f"Alta confianza en {e.source}: {e.field}={e.value} ({e.confidence:.0%})")
            elif e.confidence >= 0.5:
                reasons.append(f"Confianza media en {e.source}: {e.field}={e.value} ({e.confidence:.0%})")

        for c in conflicts:
            reasons.append(
                f"Conflicto {c.severity.value}: {c.evidence_a.source}.{c.evidence_a.field} "
                f"vs {c.evidence_b.source}.{c.evidence_b.field} — {c.reason}"
            )

        final_conf = self._confidence.compute(evidence)
        if score is not None:
            final_conf = max(final_conf, score.weighted_total)

        return DecisionExplanation(
            account_code=account_code,
            account_name=account_name,
            classified_code=classified_code,
            reasons=reasons,
            evidence_summary=evidence_summary,
            confidence_breakdown=confidence_breakdown,
            final_confidence=round(final_conf, 4),
        )

    def generate_summary(self, explanations: list[DecisionExplanation]) -> str:
        if not explanations:
            return "No hay explicaciones disponibles."
        lines = ["═══ DECISION ENGINE — EXPLICACIONES ═══", ""]
        for exp in explanations:
            lines.append(f"Cuenta: {exp.account_code} — {exp.account_name}")
            lines.append(f"Clasificada: {exp.classified_code}")
            lines.append(f"Confianza final: {exp.final_confidence:.2%}")
            for r in exp.reasons:
                lines.append(f"  • {r}")
            lines.append("")
        return "\n".join(lines)
