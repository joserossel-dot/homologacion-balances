"""Cobertura esperada del dataset (Sprint 33).

Responde preguntas como:
  "Si desarrollo extractor para las 5 familias principales,
   ¿qué porcentaje del dataset cubriré?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .family_detector import DocumentFamily

DEFAULT_TOP_NS = (5, 10, 20, 30)


@dataclass
class CoverageResult:
    """Cobertura acumulada para Top 5/10/20/30 familias."""

    total_documents: int
    tiers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "tiers": list(self.tiers),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoverageResult":
        return cls(
            total_documents=data.get("total_documents", 0),
            tiers=list(data.get("tiers", [])),
        )


def coverage_by_top_families(
    families: list[DocumentFamily],
    top_ns: tuple[int, ...] = DEFAULT_TOP_NS,
) -> CoverageResult:
    """Cobertura acumulada (documentos y %) de las Top-N familias."""
    total = sum(f.count for f in families)
    orden = sorted(families, key=lambda f: (-f.count, f.id))

    tiers: list[dict[str, Any]] = []
    acumulado = 0
    for top_n in top_ns:
        slice_fam = orden[:top_n]
        acumulado = sum(f.count for f in slice_fam)
        pct = round(acumulado / max(total, 1) * 100.0, 2)
        tiers.append({
            "top_n": top_n,
            "families": len(slice_fam),
            "documents": acumulado,
            "cumulative_pct": pct,
            "remaining_documents": total - acumulado,
            "remaining_pct": round(100.0 - pct, 2),
            "top_families": [
                {"id": f.id, "count": f.count, "top_company": f.top_company,
                 "layout": f.dominant_layout, "code": f.dominant_code_pattern}
                for f in slice_fam
            ],
        })

    return CoverageResult(total_documents=total, tiers=tiers)
