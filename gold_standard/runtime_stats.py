"""gold_standard/runtime_stats.py — RuntimeStatistics (P5.5 Runtime Observability).

Fuente ÚNICA de información para la sección "📊 Runtime Analytics" del
Knowledge Manager. La UI no ejecuta SQL ni abre SQLite: todo se obtiene
desde este objeto, que a su vez delega en:

  - LearningEngine.get_metrics() / get_runtime_hits_by_code()  (uso en vivo)
  - RuntimeManager.get_runtime_statistics() / get_runtime_coverage() / load_history()

Restricciones P5.5:
  - Solo observabilidad: no promueve, no revierte, no puebla el runtime.
  - No modifica gold_standard.db ni el benchmark.
  - RuntimeManager no se modifica: se reutilizan sus getters existentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Nombres canónicos de las métricas de uso expuestas por LearningEngine
_HIT_METRICS: tuple[str, ...] = (
    "runtime_exact_hits",
    "runtime_fuzzy_hits",
    "gold_exact_hits",
    "gold_fuzzy_hits",
    "runtime_miss",
    "fallback_to_gold",
    "total_requests",
)

# Acciones de promotion_history (RuntimeManager)
_EVENT_PROMOTE = "PROMOTE"
_EVENT_ROLLBACK = "ROLLBACK"
_EVENT_REJECT = "REJECT"


@dataclass
class RuntimeStatistics:
    """Snapshot agregado de la observabilidad del runtime.

    Combina métricas de uso del LearningEngine (en memoria) con eventos y
    cobertura del RuntimeManager (gold_standard_runtime.db).
    """

    # Uso (LearningEngine)
    runtime_exact_hits: int = 0
    runtime_fuzzy_hits: int = 0
    gold_exact_hits: int = 0
    gold_fuzzy_hits: int = 0
    runtime_miss: int = 0
    fallback_to_gold: int = 0
    total_requests: int = 0

    # Eventos (RuntimeManager)
    promotion_count: int = 0
    rollback_count: int = 0
    reject_count: int = 0
    history_events: int = 0

    # Tamaños / cobertura
    runtime_size: int = 0
    runtime_distinct: int = 0
    gold_size: int = 0
    runtime_catalog_coverage: float = 0.0

    # Impacto por promoción (códigos estándar realmente usados)
    runtime_hit_codes: dict[str, int] = field(default_factory=dict)
    promotion_impact: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------

    @classmethod
    def capture(
        cls,
        *,
        engine: Any | None = None,
        metrics: dict[str, Any] | None = None,
        runtime: Any | None = None,
        gold_db: str = "gold_standard.db",
    ) -> "RuntimeStatistics":
        """Captura un snapshot desde un engine (o métricas) y un RuntimeManager.

        ``engine`` o ``metrics``: al menos uno. Si ambos, ``metrics`` tiene
        prioridad (por ejemplo un snapshot persistido en session_state).
        ``runtime`` es opcional: si se omite, solo se reporta el uso.
        """
        stats = cls()
        source = metrics if metrics is not None else (
            engine.get_metrics() if engine is not None else None
        )
        if source is not None:
            stats.load_metrics(source)
        if engine is not None:
            stats.runtime_hit_codes = engine.get_runtime_hits_by_code()
        elif metrics is not None:
            stats.runtime_hit_codes = dict(metrics.get("runtime_hits_by_code", {}))
        if runtime is not None:
            stats.load_runtime(runtime, gold_db)
        return stats

    def load_metrics(self, m: dict[str, Any]) -> None:
        for key in _HIT_METRICS:
            setattr(self, key, int(m.get(key, 0) or 0))

    def load_runtime(self, runtime: Any, gold_db: str) -> None:
        """Lee eventos y cobertura desde RuntimeManager (sin SQL directo)."""
        s = runtime.get_runtime_statistics(gold_db)
        self.promotion_count = int(s.get("promotions", 0))
        self.rollback_count = int(s.get("rollbacks", 0))
        self.reject_count = int(s.get("rejects", 0))
        self.history_events = int(s.get("history_events", 0))
        self.runtime_size = int(s.get("runtime_size", 0))
        self.gold_size = int(s.get("gold_size", 0))
        self.runtime_catalog_coverage = float(s.get("coverage", 0.0))

        cov = runtime.get_runtime_coverage(gold_db)
        self.runtime_distinct = int(cov.get("runtime_distinct", 0))

        # Impacto: promociones cuyo código realmente fue usado por el engine.
        self.promotion_impact = []
        if self.runtime_hit_codes:
            for h in runtime.load_history():
                if h.get("accion", "").upper() != _EVENT_PROMOTE:
                    continue
                code = h.get("codigo_nuevo") or ""
                hits = int(self.runtime_hit_codes.get(code, 0))
                self.promotion_impact.append({
                    "account_name": h.get("account_name", ""),
                    "code": code,
                    "promotion_id": h.get("promotion_id", ""),
                    "hits": hits,
                    "impactful": hits > 0,
                })

    # ------------------------------------------------------------------
    # Derivados
    # ------------------------------------------------------------------

    @property
    def runtime_resolved(self) -> int:
        return self.runtime_exact_hits + self.runtime_fuzzy_hits

    @property
    def gold_resolved(self) -> int:
        return self.gold_exact_hits + self.gold_fuzzy_hits

    @property
    def learning_used_pct(self) -> float:
        """Porcentaje de resoluciones que usaron el conocimiento runtime."""
        return self._pct(self.runtime_resolved)

    @property
    def runtime_usage_pct(self) -> float:
        """Cobertura de uso del runtime (resuelto por runtime / requests)."""
        return self._pct(self.runtime_resolved)

    @property
    def gold_usage_pct(self) -> float:
        """Cobertura de uso del gold (resuelto por gold / requests)."""
        return self._pct(self.gold_resolved)

    @property
    def fallback_pct(self) -> float:
        return self._pct(self.fallback_to_gold)

    @property
    def runtime_catalog_coverage_pct(self) -> float:
        return round(self.runtime_catalog_coverage, 2)

    @property
    def impactful_promotions(self) -> int:
        return sum(1 for p in self.promotion_impact if p["impactful"])

    def _pct(self, n: int) -> float:
        return round(n * 100.0 / self.total_requests, 2) if self.total_requests else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_exact_hits": self.runtime_exact_hits,
            "runtime_fuzzy_hits": self.runtime_fuzzy_hits,
            "gold_exact_hits": self.gold_exact_hits,
            "gold_fuzzy_hits": self.gold_fuzzy_hits,
            "runtime_miss": self.runtime_miss,
            "fallback_to_gold": self.fallback_to_gold,
            "total_requests": self.total_requests,
            "promotion_count": self.promotion_count,
            "rollback_count": self.rollback_count,
            "reject_count": self.reject_count,
            "history_events": self.history_events,
            "runtime_size": self.runtime_size,
            "runtime_distinct": self.runtime_distinct,
            "gold_size": self.gold_size,
            "runtime_catalog_coverage": self.runtime_catalog_coverage_pct,
            "runtime_usage_pct": self.runtime_usage_pct,
            "gold_usage_pct": self.gold_usage_pct,
            "learning_used_pct": self.learning_used_pct,
            "fallback_pct": self.fallback_pct,
            "impactful_promotions": self.impactful_promotions,
            "promotion_impact": self.promotion_impact,
        }
