from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AlertSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class QualityAlert:
    alert_id: str
    timestamp: str
    severity: str
    category: str
    metric: str
    before_value: float
    after_value: float
    delta: float
    threshold: float
    description: str
    snapshot_before: str
    snapshot_after: str

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "category": self.category,
            "metric": self.metric,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "delta": self.delta,
            "threshold": self.threshold,
            "description": self.description,
            "snapshot_before": self.snapshot_before,
            "snapshot_after": self.snapshot_after,
        }


class AlertEngine:
    DEFAULTS: dict[str, float] = {
        "coverage_drop_pct": 2.0,
        "accuracy_drop_pct": 1.0,
        "unknown_increase_abs": 500,
        "unknown_increase_pct": 5.0,
        "parser_confidence_drop": 0.1,
        "precision_drop_pct": 1.0,
        "recall_drop_pct": 1.0,
        "f1_drop_pct": 0.02,
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self.thresholds = {**self.DEFAULTS, **(thresholds or {})}
        self.alerts: list[QualityAlert] = []

    def evaluate(self, drift: dict, before: dict, after: dict) -> list[QualityAlert]:
        self.alerts = []
        ts = datetime.now(timezone.utc).isoformat()

        # Coverage drift
        cd = drift.get("coverage_drift", 0)
        threshold_cov = self.thresholds["coverage_drop_pct"]
        if cd < 0 and abs(cd) >= threshold_cov:
            sev = AlertSeverity.CRITICAL if abs(cd) >= threshold_cov * 2 else AlertSeverity.HIGH
            self._add_alert(ts, sev, "coverage", "coverage",
                            before.get("coverage", 0), after.get("coverage", 0),
                            cd, threshold_cov, "Coverage dropped")

        # Accuracy drift
        ad = drift.get("accuracy_drift", 0)
        threshold_acc = self.thresholds["accuracy_drop_pct"]
        if ad < 0 and abs(ad) >= threshold_acc:
            sev = AlertSeverity.CRITICAL if abs(ad) >= threshold_acc * 2 else AlertSeverity.HIGH
            self._add_alert(ts, sev, "accuracy", "accuracy",
                            before.get("accuracy", 0), after.get("accuracy", 0),
                            ad, threshold_acc, "Accuracy dropped")

        # UNKNOWN increase
        ud = drift.get("unknown_drift", 0)
        unknown_pct = (ud / max(before.get("accounts", 1), 1)) * 100
        if ud > self.thresholds["unknown_increase_abs"] or unknown_pct >= self.thresholds["unknown_increase_pct"]:
            sev = AlertSeverity.CRITICAL if unknown_pct >= self.thresholds["unknown_increase_pct"] * 2 else AlertSeverity.HIGH
            self._add_alert(ts, sev, "unknown", "unknown",
                            before.get("unknown", 0), after.get("unknown", 0),
                            ud, self.thresholds["unknown_increase_pct"],
                            f"UNKNOWN increased by {ud} ({round(unknown_pct, 1)}%)")

        # Parser confidence drift
        pcd = drift.get("parser_confidence_drift", 0)
        threshold_pc = self.thresholds["parser_confidence_drop"]
        if pcd < 0 and abs(pcd) >= threshold_pc:
            sev = AlertSeverity.HIGH if abs(pcd) >= threshold_pc * 2 else AlertSeverity.MEDIUM
            self._add_alert(ts, sev, "parser", "average_parser_confidence",
                            before.get("average_parser_confidence", 0),
                            after.get("average_parser_confidence", 0),
                            pcd, threshold_pc, "Parser confidence dropped")

        return self.alerts

    def _add_alert(self, ts: str, severity: AlertSeverity, category: str, metric: str,
                   before: float, after: float, delta: float, threshold: float, desc: str):
        alert = QualityAlert(
            alert_id=f"ALERT-{category.upper()}-{ts[:16]}",
            timestamp=ts,
            severity=severity.value if isinstance(severity, AlertSeverity) else severity,
            category=category,
            metric=metric,
            before_value=before,
            after_value=after,
            delta=round(delta, 4),
            threshold=threshold,
            description=f"{desc}: {before} → {after} (delta={round(delta, 2)})",
            snapshot_before="",
            snapshot_after="",
        )
        self.alerts.append(alert)
