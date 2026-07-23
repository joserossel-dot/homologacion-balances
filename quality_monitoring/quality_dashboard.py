from __future__ import annotations

from typing import Any


class QualityDashboard:
    def __init__(self, snapshot: dict, drift: dict, regressions: dict, alerts: list[dict]):
        self.snapshot = snapshot
        self.drift = drift
        self.regressions = regressions
        self.alerts = alerts

    def to_dict(self) -> dict:
        return {
            "current_snapshot": {
                "id": self.snapshot.get("snapshot_id", ""),
                "timestamp": self.snapshot.get("timestamp", ""),
                "accounts": self.snapshot.get("accounts", 0),
                "coverage": self.snapshot.get("coverage", 0),
                "unknown_rate": self.snapshot.get("unknown_rate", 0),
                "accuracy": self.snapshot.get("accuracy", 0),
                "precision": self.snapshot.get("precision", 0),
                "recall": self.snapshot.get("recall", 0),
                "macro_f1": self.snapshot.get("macro_f1", 0),
                "micro_f1": self.snapshot.get("micro_f1", 0),
                "avg_parser_confidence": self.snapshot.get("average_parser_confidence", 0),
            },
            "drift": self.drift,
            "regressions": {
                "total": self.regressions.get("total_regressions", 0),
                "improvements": self.regressions.get("improvements", 0),
                "degradations": self.regressions.get("degradations", 0),
                "critical": self.regressions.get("critical_count", 0),
                "high": self.regressions.get("high_count", 0),
                "medium": self.regressions.get("medium_count", 0),
            },
            "alerts": self.alerts,
            "top_concepts": list(self.snapshot.get("decision_distribution", {}).keys())[:5],
            "top_layouts": list(self.snapshot.get("layout_distribution", {}).keys()),
        }

    def changed_metrics(self) -> list[dict]:
        metrics = []
        for key in ["coverage", "accuracy", "precision", "recall", "macro_f1"]:
            delta = self.drift.get(f"{key}_drift", 0)
            if delta != 0:
                metrics.append({
                    "metric": key,
                    "before": self.snapshot.get(key, 0),
                    "delta": delta,
                    "trend": "up" if delta > 0 else "down",
                })
        return metrics

    def top_regressions(self, n: int = 5) -> list[dict]:
        findings = self.regressions.get("findings", [])
        degs = [f for f in findings if "improvement" not in f.get("description", "").lower()]
        return sorted(degs, key=lambda x: -abs(x.get("delta", 0)))[:n]

    def top_improvements(self, n: int = 5) -> list[dict]:
        findings = self.regressions.get("findings", [])
        imps = [f for f in findings if "improvement" in f.get("description", "").lower()]
        return sorted(imps, key=lambda x: -abs(x.get("delta", 0)))[:n]
