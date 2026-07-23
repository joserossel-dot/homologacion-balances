from __future__ import annotations

from typing import Any


class RegressionDetector:
    def __init__(self, before: dict, after: dict, drift: dict):
        self.before = before
        self.after = after
        self.drift = drift

    def regressions(self) -> list[dict]:
        findings: list[dict] = []

        ud = self.drift.get("unknown_drift", 0)
        if ud > 0:
            findings.append({
                "type": "MORE_UNKNOWN",
                "metric": "unknown",
                "before": self.before.get("unknown", 0),
                "after": self.after.get("unknown", 0),
                "delta": ud,
                "severity": "HIGH" if ud > 500 else "MEDIUM" if ud > 100 else "LOW",
                "description": f"UNKNOWN increased by {ud}",
            })
        elif ud < 0:
            findings.append({
                "type": "LESS_UNKNOWN",
                "metric": "unknown",
                "before": self.before.get("unknown", 0),
                "after": self.after.get("unknown", 0),
                "delta": abs(ud),
                "severity": "INFO",
                "description": f"UNKNOWN decreased by {abs(ud)} (improvement)",
            })

        cd = self.drift.get("coverage_drift", 0)
        if cd < 0:
            findings.append({
                "type": "COVERAGE_DROP",
                "metric": "coverage",
                "before": self.before.get("coverage", 0),
                "after": self.after.get("coverage", 0),
                "delta": abs(cd),
                "severity": "HIGH" if abs(cd) > 2 else "MEDIUM",
                "description": f"Coverage dropped by {abs(cd)} pp",
            })
        elif cd > 0:
            findings.append({
                "type": "COVERAGE_GAIN",
                "metric": "coverage",
                "before": self.before.get("coverage", 0),
                "after": self.after.get("coverage", 0),
                "delta": cd,
                "severity": "INFO",
                "description": f"Coverage improved by {cd} pp (improvement)",
            })

        ad = self.drift.get("accuracy_drift", 0)
        if ad < -1:
            findings.append({
                "type": "ACCURACY_DROP",
                "metric": "accuracy",
                "before": self.before.get("accuracy", 0),
                "after": self.after.get("accuracy", 0),
                "delta": abs(ad),
                "severity": "CRITICAL" if abs(ad) > 3 else "HIGH",
                "description": f"Accuracy dropped by {abs(ad)} pp",
            })

        pcd = self.drift.get("parser_confidence_drift", 0)
        if pcd < -0.05:
            findings.append({
                "type": "PARSER_CONFIDENCE_DROP",
                "metric": "average_parser_confidence",
                "before": self.before.get("average_parser_confidence", 0),
                "after": self.after.get("average_parser_confidence", 0),
                "delta": round(abs(pcd), 4),
                "severity": "HIGH" if abs(pcd) > 0.1 else "MEDIUM",
                "description": f"Parser confidence dropped by {round(abs(pcd), 4)}",
            })

        layout_drift = self.drift.get("layout_drift", {})
        for layout, delta in layout_drift.items():
            if abs(delta) > 100:
                findings.append({
                    "type": "LAYOUT_SHIFT",
                    "metric": f"layout:{layout}",
                    "before": self.before.get("layout_distribution", {}).get(layout, 0),
                    "after": self.after.get("layout_distribution", {}).get(layout, 0),
                    "delta": delta,
                    "severity": "MEDIUM",
                    "description": f"Layout '{layout}' shifted by {delta} accounts",
                })

        return findings

    def improvements(self) -> list[dict]:
        return [f for f in self.regressions() if "improvement" in f.get("description", "").lower()]

    def degradations(self) -> list[dict]:
        return [f for f in self.regressions() if "improvement" not in f.get("description", "").lower()]

    def summary(self) -> dict:
        regs = self.regressions()
        return {
            "total_regressions": len(regs),
            "improvements": len(self.improvements()),
            "degradations": len(self.degradations()),
            "critical_count": sum(1 for r in regs if r["severity"] == "CRITICAL"),
            "high_count": sum(1 for r in regs if r["severity"] == "HIGH"),
            "medium_count": sum(1 for r in regs if r["severity"] == "MEDIUM"),
            "low_count": sum(1 for r in regs if r["severity"] == "LOW"),
            "findings": regs,
        }
