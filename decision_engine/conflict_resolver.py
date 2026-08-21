from __future__ import annotations

from typing import Any

from .models import DecisionEvidence, DecisionConflict, ConflictSeverity


class ConflictResolver:
    def resolve(self, evidence: list[DecisionEvidence]) -> list[DecisionConflict]:
        conflicts: list[DecisionConflict] = []
        grouped = self._group_by_field(evidence)
        field_conflicts = self._detect_field_conflicts(grouped)
        conflicts.extend(field_conflicts)
        return conflicts

    def _group_by_field(self, evidence: list[DecisionEvidence]) -> dict[str, list[DecisionEvidence]]:
        grouped: dict[str, list[DecisionEvidence]] = {}
        for e in evidence:
            key = e.field
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(e)
        return grouped

    def _detect_field_conflicts(self, grouped: dict[str, list[DecisionEvidence]]) -> list[DecisionConflict]:
        conflicts: list[DecisionConflict] = []
        for field, ev_list in grouped.items():
            if len(ev_list) < 2:
                continue
            for i in range(len(ev_list)):
                for j in range(i + 1, len(ev_list)):
                    a, b = ev_list[i], ev_list[j]
                    if a.value != b.value and a.source != b.source:
                        severity = self._determine_severity(a, b)
                        if severity != ConflictSeverity.NONE:
                            conflicts.append(DecisionConflict(
                                evidence_a=a,
                                evidence_b=b,
                                severity=severity,
                                reason=(
                                    f"Conflicto entre {a.source}.{a.field}={a.value} "
                                    f"y {b.source}.{b.field}={b.value}"
                                ),
                            ))
        return conflicts

    def _determine_severity(self, a: DecisionEvidence, b: DecisionEvidence) -> ConflictSeverity:
        both_high = a.confidence >= 0.8 and b.confidence >= 0.8
        if both_high and a.value is not None and b.value is not None and a.value != b.value:
            return ConflictSeverity.CRITICAL
        if a.confidence >= 0.6 and b.confidence >= 0.6 and a.value != b.value:
            return ConflictSeverity.HIGH
        if a.value != b.value:
            return ConflictSeverity.MEDIUM
        return ConflictSeverity.NONE
