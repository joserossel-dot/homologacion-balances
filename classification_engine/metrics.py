"""classification_engine/metrics.py — Métricas de evaluación.

Métricas deterministas sobre resultados del motor:

  - Top-1 / Top-N accuracy (exact match contra código esperado).
  - MRR (Mean Reciprocal Rank) para el código esperado.
  - Coverage: % de cuentas con al menos un candidato.
  - Distribución de etiquetas de confianza.

Pensadas para calibración post-hoc (Sprint 39+), no para la ruta de
clasificación en sí.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from classification_engine.decision import TopNResult


@dataclass
class MetricsResult:
    """Resultado agregado de métricas sobre un batch de resultados."""

    total: int = 0
    top1_hits: int = 0
    top1_accuracy: float = 0.0
    top5_hits: int = 0
    top5_accuracy: float = 0.0
    mrr: float = 0.0
    coverage: float = 0.0
    confidence_distribution: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "top1_hits": self.top1_hits,
            "top1_accuracy": round(self.top1_accuracy, 4),
            "top5_hits": self.top5_hits,
            "top5_accuracy": round(self.top5_accuracy, 4),
            "mrr": round(self.mrr, 4),
            "coverage": round(self.coverage, 4),
            "confidence_distribution": dict(self.confidence_distribution),
        }


def compute_metrics(
    results: list[TopNResult],
    expected_by_account: dict[str, Optional[str]],
    top_n: int = 5,
) -> MetricsResult:
    """Computa métricas dado el código esperado por cuenta.

    Args:
        results: resultados del motor (uno por cuenta).
        expected_by_account: mapa account_name -> código esperado.
        top_n: tamaño del ranking para Top-N.
    """
    m = MetricsResult(total=len(results))

    reciprocal_sum = 0.0
    covered = 0

    for res in results:
        expected = expected_by_account.get(res.account_name)
        has_real_candidate = bool(res.top_n and res.top_n[0].code)
        if has_real_candidate:
            covered += 1
            codes = [c.code for c in res.top_n[:top_n]]

            if expected and codes and codes[0] == expected:
                m.top1_hits += 1
            if expected and expected in codes:
                m.top5_hits += 1
                reciprocal_sum += 1.0 / (codes.index(expected) + 1)

        # Distribución de confianza
        label = res.confidence or "UNKNOWN"
        m.confidence_distribution[label] = m.confidence_distribution.get(label, 0) + 1

    if m.total > 0:
        m.top1_accuracy = m.top1_hits / m.total
        m.top5_accuracy = m.top5_hits / m.total
        m.coverage = covered / m.total
        if m.total > 0:
            m.mrr = reciprocal_sum / m.total

    return m
