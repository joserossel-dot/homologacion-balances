from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd

from .gold_standard import ValidationResult


class Metrics:
    def __init__(self, results: list[ValidationResult]):
        self.results = results
        self.total = len(results)

    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        correct = sum(1 for r in self.results if r.correct)
        return round(correct / self.total, 4)

    def _binary_metrics(self, positive_label: str) -> dict:
        tp = sum(1 for r in self.results if r.correct and r.expected == positive_label)
        fp = sum(1 for r in self.results if not r.correct and r.predicted == positive_label)
        fn = sum(1 for r in self.results if not r.correct and r.expected == positive_label)
        tn = self.total - tp - fp - fn

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        return {
            "label": positive_label,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    def per_label_metrics(self) -> list[dict]:
        labels = sorted(set(r.expected for r in self.results) |
                        set(r.predicted for r in self.results if r.predicted != "UNKNOWN"))
        return [self._binary_metrics(label) for label in labels]

    def macro_f1(self) -> float:
        per_label = self.per_label_metrics()
        if not per_label:
            return 0.0
        f1s = [m["f1"] for m in per_label]
        return round(sum(f1s) / len(f1s), 4)

    def micro_f1(self) -> float:
        if self.total == 0:
            return 0.0
        tp = sum(1 for r in self.results if r.correct)
        fp = sum(1 for r in self.results if not r.correct)
        fn = fp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return round(f1, 4)

    def precision_by_type(self) -> list[dict]:
        groups: dict[str, list[bool]] = defaultdict(list)
        for r in self.results:
            groups[r.decision_type].append(r.correct)
        results = []
        for dtype, correct_list in sorted(groups.items()):
            p = sum(correct_list) / len(correct_list) if correct_list else 0.0
            results.append({
                "decision_type": dtype,
                "count": len(correct_list),
                "precision": round(p, 4),
            })
        return results

    def precision_by_decision_code(self) -> list[dict]:
        groups: dict[str, list[bool]] = defaultdict(list)
        for r in self.results:
            groups[r.decision_code].append(r.correct)
        results = []
        for code, correct_list in sorted(groups.items()):
            p = sum(correct_list) / len(correct_list) if correct_list else 0.0
            results.append({
                "decision_code": code,
                "count": len(correct_list),
                "precision": round(p, 4),
            })
        return results

    def precision_by_error_category(self) -> list[dict]:
        groups: dict[str, list[bool]] = defaultdict(list)
        for r in self.results:
            groups[r.error_category].append(r.correct)
        results = []
        for cat, correct_list in sorted(groups.items()):
            p = sum(correct_list) / len(correct_list) if correct_list else 0.0
            results.append({
                "category": cat,
                "count": len(correct_list),
                "precision": round(p, 4),
            })
        return results

    def confusion_matrix(self) -> pd.DataFrame:
        labels = sorted(set(
            r.expected for r in self.results
        ) | set(
            r.predicted for r in self.results if r.predicted != "UNKNOWN"
        ))
        matrix: dict[str, Counter] = {expected: Counter() for expected in labels}
        for r in self.results:
            exp = r.expected if r.expected in labels else "UNKNOWN"
            pred = r.predicted if r.predicted in labels else "UNKNOWN"
            if exp not in matrix:
                matrix[exp] = Counter()
            matrix[exp][pred] += 1
        rows = []
        for expected in labels:
            row: dict = {"expected": expected}
            for predicted in labels:
                row[predicted] = matrix.get(expected, Counter()).get(predicted, 0)
            rows.append(row)
        return pd.DataFrame(rows)

    def top_errors(self, n: int = 10) -> list[dict]:
        errors = [r for r in self.results if not r.correct]
        error_types: Counter = Counter()
        for e in errors:
            error_types[e.error_category] += 1
        return [
            {"category": cat, "count": cnt}
            for cat, cnt in error_types.most_common(n)
        ]

    def error_summary(self) -> dict:
        total_errors = sum(1 for r in self.results if not r.correct)
        if total_errors == 0:
            return {"total_errors": 0}
        error_by_cat: Counter = Counter()
        for r in self.results:
            if not r.correct:
                error_by_cat[r.error_category] += 1
        return {
            "total_errors": total_errors,
            "error_rate": round(total_errors / max(self.total, 1) * 100, 1),
            "by_category": dict(error_by_cat.most_common()),
        }

    def summary(self) -> dict:
        return {
            "total": self.total,
            "correct": sum(1 for r in self.results if r.correct),
            "incorrect": sum(1 for r in self.results if not r.correct),
            "accuracy": self.accuracy(),
            "accuracy_pct": round(self.accuracy() * 100, 1),
            "macro_f1": self.macro_f1(),
            "micro_f1": self.micro_f1(),
            "unknown_rate": round(
                sum(1 for r in self.results if r.predicted == "UNKNOWN") / max(self.total, 1) * 100, 1
            ),
            "per_type_precision": self.precision_by_type(),
            "per_decision_code": self.precision_by_decision_code(),
            "top_errors": self.top_errors(10),
        }
