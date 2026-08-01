"""classification_engine/explainer.py — Explicación reconstruible.

`Explainer` convierte el resultado del motor en una explicación completa:

  - `reasons`: lista legible de motivos por capa que sustentan el top 1.
  - `confidence_breakdown`: contribución ponderada de cada capa al score.
  - `candidate_explanations`: por cada candidato, capas y evidencias.

Todo lo que aparece aquí se deriva exclusivamente de la evidencia registrada
en los `RankedCandidate` (nada oculto, nada reconstruido por el lado).
"""

from __future__ import annotations

from typing import Any, Optional

from classification_engine.decision import (
    Candidate,
    ClassificationExplanation,
    RankedCandidate,
)
from classification_engine.score import WeightConfig


class Explainer:
    """Genera explicaciones legibles y reconstruibles de un ranking."""

    def __init__(self, config: WeightConfig | None = None) -> None:
        self._config = config or WeightConfig()

    def explain(
        self,
        candidates: list[RankedCandidate],
        source_candidates: Optional[list[Candidate]] = None,
        account_name: str = "",
    ) -> ClassificationExplanation:
        """Construye la explicación completa para un ranking ya puntuado.

        Args:
            candidates: ranking puntuado (resultado del Scorer).
            source_candidates: candidatos originales (opcional, para cruzar
                evidencias por capa antes de la agregación).
            account_name: nombre de la cuenta clasificada.
        """
        reasons: list[str] = []
        breakdown: dict[str, float] = {}
        candidate_explanations: list[dict[str, Any]] = []

        for i, cand in enumerate(candidates, start=1):
            layers: dict[str, Any] = {}
            for ev in cand.evidence:
                layer = ev.layer
                if layer not in layers:
                    layers[layer] = {
                        "score": ev.score,
                        "weight": ev.weight,
                        "sources": [],
                    }
                layers[layer]["sources"].append(
                    {
                        "source": ev.source,
                        "detail": ev.detail,
                        "matched_value": ev.matched_value,
                        "score": round(ev.score, 4),
                    }
                )

            candidate_explanations.append(
                {
                    "rank": i,
                    "code": cand.code,
                    "name": cand.name,
                    "score": round(cand.score, 4),
                    "confidence": cand.confidence,
                    "layers": layers,
                }
            )

            if i == 1:
                for layer, info in layers.items():
                    w = self._config.weight(layer)
                    contribution = w * info["score"]
                    breakdown[layer] = contribution
                    top_src = info["sources"][0]
                    reasons.append(
                        self._reason_text(
                            layer,
                            cand,
                            contribution,
                            top_src["detail"],
                            top_src["matched_value"],
                        )
                    )

        if not reasons:
            reasons.append(
                f"'{account_name or '(sin nombre)'}': no hay evidencia que "
                "sustente ningún candidato."
            )

        return ClassificationExplanation(
            reasons=reasons,
            confidence_breakdown=breakdown,
            candidate_explanations=candidate_explanations,
        )

    def _reason_text(
        self,
        layer: str,
        cand: RankedCandidate,
        contribution: float,
        detail: str,
        matched_value: str,
    ) -> str:
        base = (
            f"Top {cand.rank} {cand.code} ({cand.confidence}, score {cand.score:.3f}): "
            f"capa '{layer}' contribuye {contribution:.3f}"
        )
        if detail:
            base += f" — {detail}"
        if matched_value:
            base += f" [match: {matched_value}]"
        return base
