from __future__ import annotations

from typing import Any

from .models import Decision, DecisionStatistics, DecisionConflict, ConflictSeverity


class DecisionStatisticsCollector:
    def __init__(self):
        self._decisions: list[Decision] = []

    def add(self, decision: Decision) -> None:
        self._decisions.append(decision)

    def add_many(self, decisions: list[Decision]) -> None:
        self._decisions.extend(decisions)

    @property
    def count(self) -> int:
        return len(self._decisions)

    @property
    def decisions(self) -> list[Decision]:
        return list(self._decisions)

    def compute(self) -> DecisionStatistics:
        if not self._decisions:
            return DecisionStatistics()

        stats = DecisionStatistics(total_decisions=len(self._decisions))

        by_type: dict[str, int] = {}
        total_conf = 0.0
        module_confs: dict[str, list[float]] = {}
        total_conflicts = 0
        conflict_severities: dict[str, int] = {}
        explanations = 0
        total_time = 0.0

        for d in self._decisions:
            dt = d.decision_type.value
            by_type[dt] = by_type.get(dt, 0) + 1
            total_conf += d.confidence

            for e in d.evidence:
                if e.source not in module_confs:
                    module_confs[e.source] = []
                module_confs[e.source].append(e.confidence)

            total_conflicts += len(d.conflicts)
            for c in d.conflicts:
                sv = c.severity.value
                conflict_severities[sv] = conflict_severities.get(sv, 0) + 1

            if d.explanation is not None:
                explanations += 1

            total_time += 0.001

        stats.decisions_by_type = by_type
        stats.avg_confidence = round(total_conf / len(self._decisions), 4) if self._decisions else 0.0
        stats.confidence_by_module = {
            m: round(sum(s) / len(s), 4) for m, s in module_confs.items()
        }
        stats.conflicts_detected = total_conflicts
        stats.conflicts_by_severity = conflict_severities
        stats.explanations_generated = explanations
        stats.total_time_seconds = round(total_time, 3)

        return stats
