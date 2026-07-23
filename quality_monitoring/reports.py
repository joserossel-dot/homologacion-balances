from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class QualityReports:
    def __init__(self, snapshot: dict, drift: dict, regressions: dict,
                 alerts: list[dict], dashboard: dict):
        self.snapshot = snapshot
        self.drift = drift
        self.regressions = regressions
        self.alerts = alerts
        self.dashboard = dashboard

    def generate_history(self, path: str | Path, previous_snapshots: list[dict] | None = None) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        snapshots = list(previous_snapshots or []) + [self.snapshot]
        rows = []
        for s in snapshots:
            rows.append({
                "snapshot_id": s.get("snapshot_id", ""),
                "timestamp": s.get("timestamp", ""),
                "accounts": s.get("accounts", 0),
                "classified": s.get("classified", 0),
                "unknown": s.get("unknown", 0),
                "coverage": s.get("coverage", 0),
                "accuracy": s.get("accuracy", 0),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
            "snapshot_id", "timestamp", "accounts", "classified", "unknown", "coverage", "accuracy",
        ])
        df.to_excel(out, index=False)
        return out

    def generate_snapshots(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "snapshot_id": self.snapshot.get("snapshot_id", ""),
            "timestamp": self.snapshot.get("timestamp", ""),
            "git_commit": self.snapshot.get("git_commit", ""),
            "documents": self.snapshot.get("documents", 0),
            "accounts": self.snapshot.get("accounts", 0),
            "classified": self.snapshot.get("classified", 0),
            "unknown": self.snapshot.get("unknown", 0),
            "coverage": self.snapshot.get("coverage", 0),
            "unknown_rate": self.snapshot.get("unknown_rate", 0),
            "variant_count": self.snapshot.get("variant_count", 0),
            "concept_count": self.snapshot.get("concept_count", 0),
        }
        pd.DataFrame([row]).to_excel(out, index=False)
        return out

    def generate_drift_analysis(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for key, val in self.drift.items():
            if key in ("before_snapshot", "after_snapshot"):
                continue
            if isinstance(val, dict):
                for k2, v2 in val.items():
                    rows.append({"metric": f"{key}:{k2}", "delta": v2})
            else:
                rows.append({"metric": key, "delta": val})
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["metric", "delta"])
        df.to_excel(out, index=False)
        return out

    def generate_regression_analysis(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        findings = self.regressions.get("findings", [])
        rows = []
        for f in findings:
            rows.append({
                "type": f.get("type", ""),
                "metric": f.get("metric", ""),
                "before": f.get("before", 0),
                "after": f.get("after", 0),
                "delta": f.get("delta", 0),
                "severity": f.get("severity", ""),
                "description": f.get("description", ""),
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
            "type", "metric", "before", "after", "delta", "severity", "description",
        ])
        df.to_excel(out, index=False)
        return out

    def generate_alert_history(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(self.alerts) if self.alerts else pd.DataFrame(columns=[
            "alert_id", "timestamp", "severity", "category", "metric",
            "before_value", "after_value", "delta", "threshold", "description",
        ])
        df.to_excel(out, index=False)
        return out

    def generate_dashboard(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"metric": "Coverage", "value": self.snapshot.get("coverage", 0)},
            {"metric": "Unknown Rate", "value": self.snapshot.get("unknown_rate", 0)},
            {"metric": "Accuracy", "value": self.snapshot.get("accuracy", 0)},
            {"metric": "Avg Parser Confidence", "value": self.snapshot.get("average_parser_confidence", 0)},
            {"metric": "Variants", "value": self.snapshot.get("variant_count", 0)},
        ]
        for f in self.regressions.get("findings", [])[:10]:
            rows.append({
                "metric": f"REG: {f.get('type', '')}",
                "value": f"{f.get('description', '')}",
            })
        df = pd.DataFrame(rows)
        df.to_excel(out, index=False)
        return out

    def generate_markdown(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Continuous Quality Monitoring Report", "",
                  f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", ""]

        lines.append("## Current Snapshot")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Snapshot | {self.snapshot.get('snapshot_id', '')} |")
        lines.append(f"| Git Commit | {self.snapshot.get('git_commit', '')[:40]} |")
        lines.append(f"| Accounts | {self.snapshot.get('accounts', 0):,} |")
        lines.append(f"| Classified | {self.snapshot.get('classified', 0):,} |")
        lines.append(f"| UNKNOWN | {self.snapshot.get('unknown', 0):,} |")
        lines.append(f"| Coverage | {self.snapshot.get('coverage', 0)}% |")
        lines.append(f"| Variants | {self.snapshot.get('variant_count', 0):,} |")
        lines.append(f"| Concepts | {self.snapshot.get('concept_count', 0)} |")
        lines.append("")

        drift_keys = ["coverage_drift", "accuracy_drift", "precision_drift",
                       "recall_drift", "f1_drift", "parser_confidence_drift"]
        significant = {k: self.drift.get(k, 0) for k in drift_keys if self.drift.get(k, 0) != 0}
        if significant:
            lines.append("## Drift Detected")
            lines.append("")
            lines.append("| Metric | Delta |")
            lines.append("|---|---|")
            for k, v in significant.items():
                emoji = "↑" if v > 0 else "↓"
                lines.append(f"| {k} | {emoji} {v} |")
            lines.append("")

        lines.append("## Regressions Summary")
        lines.append("")
        lines.append(f"**Total Regressions:** {self.regressions.get('total_regressions', 0)}")
        lines.append(f"**Improvements:** {self.regressions.get('improvements', 0)}")
        lines.append(f"**Degradations:** {self.regressions.get('degradations', 0)}")
        lines.append(f"**CRITICAL:** {self.regressions.get('critical_count', 0)}")
        lines.append(f"**HIGH:** {self.regressions.get('high_count', 0)}")
        lines.append(f"**MEDIUM:** {self.regressions.get('medium_count', 0)}")
        lines.append("")

        if self.alerts:
            lines.append("## Active Alerts")
            lines.append("")
            lines.append("| ID | Severity | Category | Description |")
            lines.append("|---|---|---|---|")
            for a in self.alerts[:10]:
                lines.append(f"| {a.get('alert_id', '')[:30]} | {a.get('severity', '')} | "
                             f"{a.get('category', '')} | {a.get('description', '')[:80]} |")
            lines.append("")

        lines.append("## Top Regressions")
        lines.append("")
        findings = self.regressions.get("findings", [])
        degs = [f for f in findings if "improvement" not in f.get("description", "").lower()]
        if degs:
            lines.append("| Type | Severity | Delta | Description |")
            lines.append("|---|---|---|---|")
            for f in sorted(degs, key=lambda x: -abs(x.get("delta", 0)))[:5]:
                lines.append(f"| {f.get('type', '')} | {f.get('severity', '')} | "
                             f"{f.get('delta', 0)} | {f.get('description', '')[:80]} |")
        else:
            lines.append("No regressions detected.")
        lines.append("")

        imps = [f for f in findings if "improvement" in f.get("description", "").lower()]
        if imps:
            lines.append("## Top Improvements")
            lines.append("")
            lines.append("| Type | Delta | Description |")
            lines.append("|---|---|---|")
            for f in sorted(imps, key=lambda x: -abs(x.get("delta", 0)))[:5]:
                lines.append(f"| {f.get('type', '')} | {f.get('delta', 0)} | "
                             f"{f.get('description', '')[:80]} |")
            lines.append("")

        is_safe = (
            self.regressions.get("critical_count", 0) == 0
            and self.regressions.get("high_count", 0) == 0
        )
        lines.append("## Deployment Safety")
        lines.append("")
        if is_safe:
            lines.append("**SAFE** — No critical or high regressions detected.")
        else:
            lines.append("**UNSAFE** — Critical or high regressions detected. Review before deployment.")
        lines.append("")
        lines.append("---")
        lines.append("*No production files were modified. Monitoring mode only.*")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    def generate_statistics_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "snapshot": {
                "snapshot_id": self.snapshot.get("snapshot_id", ""),
                "timestamp": self.snapshot.get("timestamp", ""),
                "accounts": self.snapshot.get("accounts", 0),
                "classified": self.snapshot.get("classified", 0),
                "unknown": self.snapshot.get("unknown", 0),
                "coverage": self.snapshot.get("coverage", 0),
                "unknown_rate": self.snapshot.get("unknown_rate", 0),
                "variant_count": self.snapshot.get("variant_count", 0),
            },
            "drift": {k: v for k, v in self.drift.items()
                       if k not in ("before_snapshot", "after_snapshot")},
            "regressions": {
                "total": self.regressions.get("total_regressions", 0),
                "improvements": self.regressions.get("improvements", 0),
                "degradations": self.regressions.get("degradations", 0),
            },
            "alerts_count": len(self.alerts),
            "deployment_safe": (
                self.regressions.get("critical_count", 0) == 0
                and self.regressions.get("high_count", 0) == 0
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return out
