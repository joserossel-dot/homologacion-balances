"""classification_engine/score.py — Configuración de pesos y scoring.

WeightConfig
    Objeto único de configuración de pesos del motor. Nada se hardcodea en
    el cuerpo del motor: cada capa de evidencia tiene un peso configurable
    y el scoring usa estos pesos. Permite calibración post-hoc sin tocar
    código.

Scorer
    Agrega las evidencias de cada candidato en un score total ponderado por
    capa (0-1) y deriva la etiqueta de confianza desde umbrales
    configurables.

Algoritmo de scoring (documentado en detalle):

    1. Para un candidato C, se agrupan sus evidencias por capa.
    2. Score de capa s_l(C) = max(score) de las evidencias de esa capa.
    3. Score total = Σ(w_l · s_l) / Σ(w_l)  sobre las capas que aportan
       evidencia (si ninguna aporta → 0.0).
    4. Bonus de consenso: si el candidato es apoyado por >= 2 capas, se
       aplica un factor multiplicativo configurable (consensus_bonus).
    5. Se deriva la confianza desde confidence_thresholds (pares
       (min_score, label) evaluados en orden descendente).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from classification_engine.decision import Candidate, RankedCandidate


# ---------------------------------------------------------------------------
# Peso de capas por defecto (calibrables vía WeightConfig, no hardcodeadas
# en el motor)
# ---------------------------------------------------------------------------

DEFAULT_LAYER_WEIGHTS: dict[str, float] = {
    "code": 0.90,
    "catalog_exact": 1.00,
    "synonyms_exact": 0.95,
    "synonyms_fuzzy": 0.70,
    "special_rules": 0.90,
    "context": 0.55,
    "extractor": 0.40,
    "profile": 0.40,
}

# Capas que SÍ proponen un código (candidatos). Las capas de contexto/extractor/
# profile no generan candidatos nuevos: solo refuerzan candidatos existentes.
CANDIDATE_LAYERS: frozenset[str] = frozenset({
    "code", "catalog_exact", "synonyms_exact",
    "synonyms_fuzzy", "special_rules",
})

# Capas de refuerzo contextual (no generan candidatos).
BOOST_LAYERS: frozenset[str] = frozenset({
    "context", "extractor", "profile",
})

# Umbrales de confianza por defecto: pares (min_score, label) en orden
# descendente.
DEFAULT_CONFIDENCE_THRESHOLDS: list[tuple[float, str]] = [
    (0.95, "EXACT"),
    (0.85, "VERY_HIGH"),
    (0.70, "HIGH"),
    (0.50, "MEDIUM"),
    (0.30, "LOW"),
    (0.00, "UNKNOWN"),
]


@dataclass
class WeightConfig:
    """Configuración completa de pesos y umbrales del motor.

    Attributes:
        weights: dict capa -> peso (0-1). Solo capas presentes en
            DEFAULT_LAYER_WEIGHTS o nuevas capas registradas.
        fuzzy_threshold: umbral mínimo de similitud para aceptar un match
            fuzzy de sinónimos (0-1).
        consensus_bonus: factor multiplicativo aplicado al score cuando un
            candidato es apoyado por >= min_consensus_layers capas.
        min_consensus_layers: número mínimo de capas para aplicar el bonus.
        confidence_thresholds: pares (min_score, label) en orden descendente.
        top_n: tamaño del ranking por defecto que devuelve el motor.
    """

    weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_LAYER_WEIGHTS)
    )
    fuzzy_threshold: float = 0.88
    consensus_bonus: float = 1.10
    min_consensus_layers: int = 2
    confidence_thresholds: list[tuple[float, str]] = field(
        default_factory=lambda: list(DEFAULT_CONFIDENCE_THRESHOLDS)
    )
    top_n: int = 5

    # ------------------------------------------------------------------
    # Construcción / validación
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.weights, dict) or not self.weights:
            raise ValueError("WeightConfig.weights debe ser un dict no vacío")
        for layer, w in self.weights.items():
            if not isinstance(w, (int, float)) or w < 0:
                raise ValueError(f"Peso inválido para capa '{layer}': {w!r}")
        if not (0.0 <= self.fuzzy_threshold <= 1.0):
            raise ValueError("fuzzy_threshold debe estar en [0,1]")
        if self.consensus_bonus < 1.0:
            raise ValueError("consensus_bonus debe ser >= 1.0")
        if self.min_consensus_layers < 2:
            raise ValueError("min_consensus_layers debe ser >= 2")
        if not self.confidence_thresholds:
            raise ValueError("confidence_thresholds no puede estar vacío")
        sorted_thresholds = sorted(
            self.confidence_thresholds, key=lambda t: -t[0]
        )
        if sorted_thresholds != list(self.confidence_thresholds):
            raise ValueError("confidence_thresholds debe estar en orden descendente")

    def weight(self, layer: str) -> float:
        """Peso de una capa (default 0.0 si no configurada)."""
        return float(self.weights.get(layer, 0.0))

    def set_weight(self, layer: str, value: float) -> None:
        if value < 0:
            raise ValueError(f"Peso no puede ser negativo: {value!r}")
        self.weights[layer] = float(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": dict(self.weights),
            "fuzzy_threshold": self.fuzzy_threshold,
            "consensus_bonus": self.consensus_bonus,
            "min_consensus_layers": self.min_consensus_layers,
            "confidence_thresholds": [
                {"min_score": t[0], "label": t[1]}
                for t in self.confidence_thresholds
            ],
            "top_n": self.top_n,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeightConfig":
        weights = dict(DEFAULT_LAYER_WEIGHTS)
        if isinstance(data.get("weights"), dict):
            weights.update(data["weights"])
        raw_thresholds = data.get(
            "confidence_thresholds", DEFAULT_CONFIDENCE_THRESHOLDS
        )
        thresholds: list[tuple[float, str]] = []
        for t in raw_thresholds:
            if isinstance(t, dict):
                thresholds.append((float(t["min_score"]), str(t["label"])))
            else:
                thresholds.append((float(t[0]), str(t[1])))
        return cls(
            weights=weights,
            fuzzy_threshold=float(data.get("fuzzy_threshold", 0.88)),
            consensus_bonus=float(data.get("consensus_bonus", 1.10)),
            min_consensus_layers=int(data.get("min_consensus_layers", 2)),
            confidence_thresholds=thresholds,
            top_n=int(data.get("top_n", 5)),
        )

    @classmethod
    def from_json(cls, path: str) -> "WeightConfig":
        import json
        from pathlib import Path

        with open(Path(path), "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class Scorer:
    """Puntúa candidatos según sus evidencias y WeightConfig."""

    def __init__(self, config: WeightConfig | None = None) -> None:
        self._config = config or WeightConfig()

    @property
    def config(self) -> WeightConfig:
        return self._config

    def score_candidate(self, candidate: Candidate) -> RankedCandidate:
        """Computa el score de un candidato (sin asignar rank)."""
        layer_scores = candidate.layer_scores()

        # Capas que aportan evidencia con peso > 0
        used_layers = [
            l for l, s in layer_scores.items()
            if s > 0 and self._config.weight(l) > 0
        ]

        if not used_layers:
            total = 0.0
        else:
            num = sum(self._config.weight(l) * layer_scores[l] for l in used_layers)
            den = sum(self._config.weight(l) for l in used_layers)
            total = num / den if den > 0 else 0.0

        # Bonus de consenso (>= min_consensus_layers capas apoyan al candidato)
        if len(used_layers) >= self._config.min_consensus_layers:
            total = min(total * self._config.consensus_bonus, 1.0)

        total = round(total, 4)
        label = self.confidence_label(total)

        return RankedCandidate(
            code=candidate.code,
            name=candidate.name,
            category=candidate.category,
            tipo_estado=candidate.tipo_estado,
            score=total,
            confidence=label,
            rank=0,
            evidence=list(candidate.evidence),
        )

    def score(self, candidates: list[Candidate]) -> list[RankedCandidate]:
        """Puntúa todos los candidatos y devuelve el ranking ordenado
        (empates resueltos por código para determinismo)."""
        ranked = [self.score_candidate(c) for c in candidates]
        ranked.sort(key=lambda r: (-r.score, r.code or "", r.name))
        for i, r in enumerate(ranked, start=1):
            r.rank = i
        return ranked

    def confidence_label(self, score: float) -> str:
        """Deriva la etiqueta de confianza desde los umbrales configurados."""
        for min_score, label in self._config.confidence_thresholds:
            if score >= min_score:
                return label
        return "UNKNOWN"
