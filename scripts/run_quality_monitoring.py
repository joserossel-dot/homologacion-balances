#!/usr/bin/env python3
"""Run Continuous Quality Monitoring — capture snapshot and detect drift."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quality_monitoring import (
    QualitySnapshot,
    DriftDetector,
    RegressionDetector,
    AlertEngine,
    QualityDashboard,
    QualityReports,
)


def main():
    snap = QualitySnapshot()
    data = snap.capture()
    print(f"Snapshot: {data['accounts']} accounts, {data['coverage']}% coverage, {data['unknown']} UNKNOWN")

    snapshots_dir = Path("reports/quality_monitoring/snapshots")
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snapshots_dir / f"{data['snapshot_id']}.json"
    snap.save(snap_path)
    print(f"Saved: {snap_path}")

    previous = None
    stored = sorted(snapshots_dir.glob("*.json"))
    for sp in stored:
        if sp.name != snap_path.name:
            try:
                previous = QualitySnapshot.load(sp)
            except Exception:
                pass

    if previous:
        drift = DriftDetector(previous, data)
        drift_summary = drift.summary()
        reg = RegressionDetector(previous, data, drift_summary)
        reg_summary = reg.summary()
        alerts = AlertEngine()
        alert_list = alerts.evaluate(drift_summary, previous, data)
    else:
        drift_summary = {}
        reg_summary = {"total_regressions": 0, "improvements": 0, "degradations": 0,
                        "critical_count": 0, "high_count": 0, "medium_count": 0,
                        "low_count": 0, "findings": []}
        alert_list = []

    dashboard = QualityDashboard(data, drift_summary, reg_summary, [a.to_dict() for a in alert_list])
    db_data = dashboard.to_dict()

    reports = QualityReports(data, drift_summary, reg_summary,
                              [a.to_dict() for a in alert_list], db_data)

    output_dir = "reports/quality_monitoring"
    files = {
        "quality_history": reports.generate_history(f"{output_dir}/quality_history.xlsx", [data] if previous else None),
        "quality_snapshots": reports.generate_snapshots(f"{output_dir}/quality_snapshots.xlsx"),
        "drift_analysis": reports.generate_drift_analysis(f"{output_dir}/drift_analysis.xlsx"),
        "regression_analysis": reports.generate_regression_analysis(f"{output_dir}/regression_analysis.xlsx"),
        "alert_history": reports.generate_alert_history(f"{output_dir}/alert_history.xlsx"),
        "quality_dashboard": reports.generate_dashboard(f"{output_dir}/quality_dashboard.xlsx"),
        "quality_monitoring_md": reports.generate_markdown(f"{output_dir}/quality_monitoring.md"),
        "quality_statistics": reports.generate_statistics_json(f"{output_dir}/quality_statistics.json"),
    }

    print(f"\nAll outputs generated in {output_dir}/")
    for name, path in files.items():
        size = path.stat().st_size
        print(f"  {name}: {path.name} ({size:,} bytes)")

    if previous:
        print(f"\n  Coverage drift: {drift_summary.get('coverage_drift', 0)} pp")
        print(f"  UNKNOWN drift: {drift_summary.get('unknown_drift', 0)}")
        print(f"  Regressions: {reg_summary.get('total_regressions', 0)}")
        print(f"  Alerts: {len(alert_list)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
