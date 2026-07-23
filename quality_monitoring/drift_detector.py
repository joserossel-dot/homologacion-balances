from __future__ import annotations

from typing import Any


class DriftDetector:
    def __init__(self, before: dict, after: dict):
        self.before = before
        self.after = after

    def _float_diff(self, key: str) -> float:
        return round(
            self.after.get(key, 0) - self.before.get(key, 0), 2
        )

    def _pct_diff(self, before_val: float, after_val: float) -> float:
        if before_val == 0:
            return 0.0
        return round((after_val - before_val) / before_val * 100, 1)

    def coverage_drift(self) -> float:
        return self._float_diff("coverage")

    def unknown_drift(self) -> int:
        return self.after.get("unknown", 0) - self.before.get("unknown", 0)

    def accuracy_drift(self) -> float:
        return self._float_diff("accuracy")

    def precision_drift(self) -> float:
        return self._float_diff("precision")

    def recall_drift(self) -> float:
        return self._float_diff("recall")

    def f1_drift(self) -> float:
        return self._float_diff("macro_f1")

    def parser_confidence_drift(self) -> float:
        return self._float_diff("average_parser_confidence")

    def _dict_diff(self, key: str) -> dict[str, float]:
        da = self.before.get(key, {})
        db = self.after.get(key, {})
        all_keys = set(da.keys()) | set(db.keys())
        result = {}
        for k in sorted(all_keys):
            va = da.get(k, 0)
            vb = db.get(k, 0)
            delta = vb - va
            if delta != 0:
                result[k] = delta
        return result

    def decision_distribution_drift(self) -> dict[str, float]:
        return self._dict_diff("decision_distribution")

    def layout_distribution_drift(self) -> dict[str, float]:
        return self._dict_diff("layout_distribution")

    def summary(self) -> dict:
        return {
            "coverage_drift": self.coverage_drift(),
            "unknown_drift": self.unknown_drift(),
            "accuracy_drift": self.accuracy_drift(),
            "precision_drift": self.precision_drift(),
            "recall_drift": self.recall_drift(),
            "f1_drift": self.f1_drift(),
            "parser_confidence_drift": self.parser_confidence_drift(),
            "decision_drift": self.decision_distribution_drift(),
            "layout_drift": self.layout_distribution_drift(),
            "before_snapshot": self.before.get("snapshot_id", "unknown"),
            "after_snapshot": self.after.get("snapshot_id", "unknown"),
        }
