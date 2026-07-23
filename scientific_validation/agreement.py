from __future__ import annotations

import math
from collections import Counter
from typing import Any


class Agreement:
    def __init__(self, ratings_a: list[str], ratings_b: list[str], labels: list[str] | None = None):
        self.a = ratings_a
        self.b = ratings_b
        self.n = len(ratings_a)
        self.labels = labels or sorted(set(ratings_a + ratings_b))

    def observed_agreement(self) -> float:
        if self.n == 0:
            return 0.0
        agree = sum(1 for x, y in zip(self.a, self.b) if x == y)
        return round(agree / self.n, 4)

    def disagreement_list(self) -> list[dict]:
        return [
            {"index": i, "rater_a": x, "rater_b": y}
            for i, (x, y) in enumerate(zip(self.a, self.b))
            if x != y
        ]

    def cohen_kappa(self) -> float:
        if self.n == 0:
            return 0.0
        po = self.observed_agreement()
        marg_a = Counter(self.a)
        marg_b = Counter(self.b)
        pe = 0.0
        for label in self.labels:
            pa = marg_a.get(label, 0) / self.n
            pb = marg_b.get(label, 0) / self.n
            pe += pa * pb
        if pe >= 1.0:
            return 0.0
        kappa = (po - pe) / (1.0 - pe) if (1.0 - pe) != 0 else 0.0
        return round(max(-1.0, min(1.0, kappa)), 4)

    @staticmethod
    def interpret_kappa(kappa: float) -> str:
        if kappa >= 0.81:
            return "Almost perfect"
        elif kappa >= 0.61:
            return "Substantial"
        elif kappa >= 0.41:
            return "Moderate"
        elif kappa >= 0.21:
            return "Fair"
        elif kappa >= 0.0:
            return "Slight"
        else:
            return "Poor"

    def summary(self) -> dict:
        return {
            "n": self.n,
            "observed_agreement": self.observed_agreement(),
            "observed_agreement_pct": round(self.observed_agreement() * 100, 1),
            "cohen_kappa": self.cohen_kappa(),
            "kappa_interpretation": self.interpret_kappa(self.cohen_kappa()),
            "disagreements": len(self.disagreement_list()),
        }
