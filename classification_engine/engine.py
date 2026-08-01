"""classification_engine/engine.py — Orquestador del motor.

`DecisionEngine` compone el pipeline completo de clasificación por cuenta:

    generate (CandidateGenerator) → score (Scorer) → explain (Explainer)

Produce un `TopNResult` con ranking completo, score, confianza, fuente de
decisión y explicación trazable. Nunca devuelve un ranking vacío: si no hay
candidatos, devuelve un candidato UNKNOWN (code=None) para que el resultado
sea auditable.

La integración al pipeline de clasificación se hará en Sprint 39; este motor
es 100% independiente y testeable sin PDFs.
"""

from __future__ import annotations

from typing import Any, Optional

from classification_engine.candidate import CandidateGenerator, KnowledgeLoader
from classification_engine.decision import (
    Candidate,
    RankedCandidate,
    TopNResult,
)
from classification_engine.explainer import Explainer
from classification_engine.score import Scorer, WeightConfig

# Capas que cuentan como "decisión" (proponen código). Las capas de refuerzo
# no deciden por sí solas.
_DECISION_LAYERS = (
    "code", "catalog_exact", "synonyms_exact",
    "synonyms_fuzzy", "special_rules",
)


class DecisionEngine:
    """Orquesta clasificación por cuenta con ranking, score y explicación."""

    def __init__(
        self,
        loader: KnowledgeLoader | None = None,
        config: WeightConfig | None = None,
        generator: CandidateGenerator | None = None,
        scorer: Scorer | None = None,
        explainer: Explainer | None = None,
    ) -> None:
        self._loader = loader or KnowledgeLoader()
        self._config = config or WeightConfig()
        self._generator = generator or CandidateGenerator(
            loader=self._loader, config=self._config
        )
        self._scorer = scorer or Scorer(self._config)
        self._explainer = explainer or Explainer(self._config)

    @property
    def config(self) -> WeightConfig:
        return self._config

    @property
    def loader(self) -> KnowledgeLoader:
        return self._loader

    def classify(
        self,
        account_name: str,
        account_code: Optional[str] = None,
        context: Any = None,
    ) -> TopNResult:
        """Clasifica una cuenta y devuelve el ranking Top N.

        Args:
            account_name: nombre de la cuenta.
            account_code: código original (opcional).
            context: contexto del documento (read-only) o None.

        Returns:
            TopNResult siempre con ranking no vacío (posible UNKNOWN).
        """
        candidates = self._generator.generate(
            account_name=account_name,
            account_code=account_code,
            context=context,
        )
        ranked = self._scorer.score(candidates)
        ranked = self._ensure_non_empty(ranked)
        ranked = ranked[: self._config.top_n]

        explanation = self._explainer.explain(
            ranked, source_candidates=candidates, account_name=account_name
        )

        top = ranked[0]
        decision_source = self._decision_source(top)

        return TopNResult(
            account_code=account_code or "",
            account_name=account_name,
            account_tipo=top.tipo_estado,
            top_n=ranked,
            confidence=top.confidence,
            decision_source=decision_source,
            explanation=explanation,
            extra={
                "candidates_before_top_n": len(candidates),
                "loader_warnings": list(self._loader.warnings),
            },
        )

    @staticmethod
    def _ensure_non_empty(ranked: list[RankedCandidate]) -> list[RankedCandidate]:
        if ranked:
            return ranked
        return [
            RankedCandidate(
                code=None,
                name="",
                category="",
                score=0.0,
                confidence="UNKNOWN",
                rank=1,
                evidence=[],
            )
        ]

    @staticmethod
    def _decision_source(top: RankedCandidate) -> str:
        """Fuente de decisión del top 1: la capa con mayor contribución."""
        best_layer = "NONE"
        best_contrib = -1.0
        for ev in top.evidence:
            contrib = ev.weight * ev.score
            if contrib > best_contrib:
                best_contrib = contrib
                best_layer = ev.layer
        if top.code is None:
            return "UNKNOWN"
        return best_layer
