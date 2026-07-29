from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import ProcessingState


class ContextStatistics:

    def __init__(self):
        self._contexts: list[Any] = []

    def add(self, ctx: Any) -> None:
        self._contexts.append(ctx)

    def add_batch(self, contexts: list[Any]) -> None:
        self._contexts.extend(contexts)

    def clear(self) -> None:
        self._contexts.clear()

    @property
    def count(self) -> int:
        return len(self._contexts)

    _MISSING = object()

    def _extract(self, ctx: Any, field_path: str, default: Any = 0.0) -> Any:
        parts = field_path.split(".")
        obj = ctx
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict):
                obj = obj.get(part, self._MISSING)
            else:
                return default
            if obj is self._MISSING:
                return default
            if obj is None:
                return default
        return obj

    def _has_field(self, ctx: Any, field_path: str) -> bool:
        parts = field_path.split(".")
        obj = ctx
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict):
                obj = obj.get(part, self._MISSING)
            else:
                return False
            if obj is self._MISSING:
                return False
            if obj is None:
                return False
        return True

    # ─── Aggregations ───────────────────────────────────────────────────

    def avg_confidence_expected(self) -> float:
        values = [
            self._extract(ctx, "prediction.confidence_expected", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "prediction") is not None
        ]
        return _avg(values)

    def avg_confidence_real(self) -> float:
        values = [
            self._extract(ctx, "execution.confidence_real", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "execution") is not None
        ]
        return _avg(values)

    def avg_coverage_expected(self) -> float:
        values = [
            self._extract(ctx, "prediction.coverage_expected", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "prediction") is not None
        ]
        return _avg(values)

    def avg_coverage_real(self) -> float:
        values = [
            self._extract(ctx, "execution.coverage_real", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "execution") is not None
        ]
        return _avg(values)

    def avg_estimated_time(self) -> float:
        values = [
            self._extract(ctx, "prediction.estimated_time", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "prediction") is not None
        ]
        return _avg(values)

    def avg_processing_time(self) -> float:
        values = [
            self._extract(ctx, "execution.processing_time", 0.0)
            for ctx in self._contexts
            if self._extract(ctx, "execution") is not None
        ]
        return _avg(values)

    def avg_accounts_per_document(self) -> float:
        values = [
            self._extract(ctx, "parser.total_accounts", 0)
            for ctx in self._contexts
            if self._extract(ctx, "parser") is not None
        ]
        return _avg(values)

    # ─── Counts ─────────────────────────────────────────────────────────

    def by_state(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for ctx in self._contexts:
            state = self._extract(ctx, "state", ProcessingState.NEW)
            state_str = state.value if isinstance(state, ProcessingState) else str(state)
            counts[state_str] = counts.get(state_str, 0) + 1
        return dict(sorted(counts.items()))

    def count_with_metadata(self) -> int:
        return sum(1 for ctx in self._contexts if self._has_field(ctx, "metadata"))

    def count_with_structure(self) -> int:
        return sum(1 for ctx in self._contexts if self._has_field(ctx, "structure"))

    def count_with_parser(self) -> int:
        return sum(1 for ctx in self._contexts if self._has_field(ctx, "parser"))

    def count_with_knowledge(self) -> int:
        return sum(1 for ctx in self._contexts if self._has_field(ctx, "knowledge"))

    def count_with_validation(self) -> int:
        return sum(1 for ctx in self._contexts if self._has_field(ctx, "validation"))

    def count_completed(self) -> int:
        return sum(
            1 for ctx in self._contexts
            if self._extract(ctx, "state", None) == ProcessingState.COMPLETED
        )

    def count_failed(self) -> int:
        return sum(
            1 for ctx in self._contexts
            if self._extract(ctx, "state", None) == ProcessingState.FAILED
        )

    # ─── Snapshots ──────────────────────────────────────────────────────

    def total_snapshots(self) -> int:
        return sum(
            len(getattr(ctx, "snapshots", []))
            for ctx in self._contexts
        )

    def avg_snapshots_per_document(self) -> float:
        if not self._contexts:
            return 0.0
        return self.total_snapshots() / len(self._contexts)

    def total_events(self) -> int:
        return sum(
            len(getattr(ctx, "events", []))
            for ctx in self._contexts
        )

    def avg_events_per_document(self) -> float:
        if not self._contexts:
            return 0.0
        return self.total_events() / len(self._contexts)

    # ─── Report ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.count,
            "by_state": self.by_state(),
            "count_with_metadata": self.count_with_metadata(),
            "count_with_structure": self.count_with_structure(),
            "count_with_parser": self.count_with_parser(),
            "count_with_knowledge": self.count_with_knowledge(),
            "count_with_validation": self.count_with_validation(),
            "count_completed": self.count_completed(),
            "count_failed": self.count_failed(),
            "avg_confidence_expected": round(self.avg_confidence_expected(), 4),
            "avg_confidence_real": round(self.avg_confidence_real(), 4),
            "avg_coverage_expected": round(self.avg_coverage_expected(), 4),
            "avg_coverage_real": round(self.avg_coverage_real(), 4),
            "avg_estimated_time": round(self.avg_estimated_time(), 2),
            "avg_processing_time": round(self.avg_processing_time(), 2),
            "avg_accounts_per_document": round(self.avg_accounts_per_document(), 1),
            "total_snapshots": self.total_snapshots(),
            "avg_snapshots_per_document": round(self.avg_snapshots_per_document(), 2),
            "total_events": self.total_events(),
            "avg_events_per_document": round(self.avg_events_per_document(), 2),
        }

    def generate_markdown(self) -> str:
        d = self.to_dict()
        lines = [
            "# Document Context — Estadísticas",
            "",
            "---",
            "",
            "## Resumen Global",
            "",
            "| Métrica | Valor |",
            "|---------|-------|",
        ]
        for key, value in d.items():
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.2f} |")
            else:
                lines.append(f"| {key} | {value} |")

        lines += [
            "",
            "## Distribución por Estado",
            "",
            "| Estado | Cantidad |",
            "|--------|----------|",
        ]
        for state_name, cnt in d.get("by_state", {}).items():
            lines.append(f"| {state_name} | {cnt} |")

        lines += [
            "",
            "---",
            f"*Generado: {datetime.now(timezone.utc).isoformat()}*",
        ]
        return "\n".join(lines)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
