from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from quality_monitoring import (
    QualitySnapshot,
    DriftDetector,
    RegressionDetector,
    AlertEngine,
    AlertSeverity,
    QualityDashboard,
    QualityReports,
)


def make_snapshot_a() -> dict:
    return {
        "snapshot_id": "snap_a",
        "timestamp": "2024-01-01T00:00:00",
        "git_commit": "abc123",
        "coverage": 80.0,
        "accuracy": 85.0,
        "precision": 82.0,
        "recall": 78.0,
        "macro_f1": 0.80,
        "micro_f1": 0.82,
        "unknown": 200,
        "unknown_rate": 20.0,
        "accounts": 1000,
        "classified": 800,
        "documents": 50,
        "average_parser_confidence": 0.85,
        "average_document_confidence": 0.82,
        "variant_count": 3000,
        "concept_count": 52,
        "shadow_count": 140,
        "layout_distribution": {"validacion": 600, "edge_cases": 400},
        "ocr_distribution": {"pdf": 800, "excel": 200},
        "decision_distribution": {"exact": 500, "fuzzy": 200, "dictionary": 100},
        "unknown_distribution": {"reason1": 100, "reason2": 100},
    }


def make_snapshot_b() -> dict:
    return {
        "snapshot_id": "snap_b",
        "timestamp": "2024-06-01T00:00:00",
        "git_commit": "def456",
        "coverage": 75.0,
        "accuracy": 80.0,
        "precision": 78.0,
        "recall": 74.0,
        "macro_f1": 0.76,
        "micro_f1": 0.78,
        "unknown": 300,
        "unknown_rate": 30.0,
        "accounts": 1000,
        "classified": 700,
        "documents": 55,
        "average_parser_confidence": 0.80,
        "average_document_confidence": 0.78,
        "variant_count": 3100,
        "concept_count": 52,
        "shadow_count": 160,
        "layout_distribution": {"validacion": 550, "edge_cases": 450},
        "ocr_distribution": {"pdf": 850, "excel": 150},
        "decision_distribution": {"exact": 450, "fuzzy": 180, "dictionary": 100, "shadow": 70},
        "unknown_distribution": {"reason1": 150, "reason2": 150},
    }


class TestQualitySnapshot:
    def test_capture_with_real_data(self):
        snap = QualitySnapshot("test_snap")
        data = snap.capture()
        assert data["snapshot_id"] == "test_snap"
        assert data["accounts"] >= 10000
        assert data["coverage"] > 0

    def test_save_and_load(self, tmp_path):
        snap = QualitySnapshot("snap_001")
        data = snap.capture()
        p = tmp_path / "snap.json"
        snap.save(p)
        assert p.exists()
        loaded = QualitySnapshot.load(p)
        assert loaded["snapshot_id"] == "snap_001"

    def test_has_all_fields(self):
        snap = QualitySnapshot("s1")
        data = snap.capture()
        required = ["snapshot_id", "timestamp", "coverage", "unknown",
                     "classified", "accounts", "variant_count", "concept_count",
                     "decision_distribution", "layout_distribution"]
        for f in required:
            assert f in data, f"Missing field: {f}"


class TestDriftDetector:
    def test_coverage_drift_negative(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        assert d.coverage_drift() == -5.0

    def test_coverage_drift_positive(self):
        d = DriftDetector(make_snapshot_b(), make_snapshot_a())
        assert d.coverage_drift() == 5.0

    def test_unknown_drift(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        assert d.unknown_drift() == 100

    def test_accuracy_drift(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        assert d.accuracy_drift() == -5.0

    def test_parser_confidence_drift(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        assert d.parser_confidence_drift() == -0.05

    def test_no_drift(self):
        a = make_snapshot_a()
        d = DriftDetector(a, a)
        assert d.coverage_drift() == 0.0
        assert d.unknown_drift() == 0

    def test_decision_drift(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        dd = d.decision_distribution_drift()
        assert "shadow" in dd
        assert dd["shadow"] == 70

    def test_layout_drift(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        ld = d.layout_distribution_drift()
        assert "validacion" in ld
        assert ld["validacion"] == -50

    def test_summary(self):
        d = DriftDetector(make_snapshot_a(), make_snapshot_b())
        s = d.summary()
        assert s["coverage_drift"] == -5.0
        assert s["unknown_drift"] == 100


class TestRegressionDetector:
    def test_detects_more_unknown(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        findings = reg.regressions()
        types = [f["type"] for f in findings]
        assert "MORE_UNKNOWN" in types

    def test_detects_coverage_drop(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        findings = reg.regressions()
        types = [f["type"] for f in findings]
        assert "COVERAGE_DROP" in types

    def test_detects_accuracy_drop(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        findings = reg.regressions()
        types = [f["type"] for f in findings]
        assert "ACCURACY_DROP" in types

    def test_improvements_identified(self):
        better = make_snapshot_a()  # 80% cov, 200 UNKNOWN
        worse = make_snapshot_b()   # 75% cov, 300 UNKNOWN
        drift = DriftDetector(worse, better).summary()
        reg = RegressionDetector(worse, better, drift)
        imps = reg.improvements()
        assert len(imps) > 0

    def test_summary(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        s = reg.summary()
        assert s["total_regressions"] >= 3
        assert s["degradations"] >= 3

    def test_no_regression_when_identical(self):
        a = make_snapshot_a()
        drift = DriftDetector(a, a).summary()
        reg = RegressionDetector(a, a, drift)
        assert reg.regressions() == []


class TestAlertEngine:
    def test_coverage_drop_triggers_alert(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        engine = AlertEngine({"coverage_drop_pct": 2.0})
        alerts = engine.evaluate(drift, a, b)
        codes = [a.category for a in alerts]
        assert "coverage" in codes

    def test_unknown_increase_triggers_alert(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        engine = AlertEngine({"unknown_increase_abs": 50, "unknown_increase_pct": 5.0})
        alerts = engine.evaluate(drift, a, b)
        codes = [a.category for a in alerts]
        assert "unknown" in codes

    def test_no_alerts_when_identical(self):
        a = make_snapshot_a()
        drift = DriftDetector(a, a).summary()
        engine = AlertEngine()
        alerts = engine.evaluate(drift, a, a)
        assert alerts == []

    def test_alert_to_dict(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        engine = AlertEngine({"coverage_drop_pct": 1.0})
        alerts = engine.evaluate(drift, a, b)
        if alerts:
            d = alerts[0].to_dict()
            assert "alert_id" in d
            assert "severity" in d

    def test_severity_enum(self):
        assert AlertSeverity.INFO.value == "INFO"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"
        assert len(AlertSeverity) == 5


class TestQualityDashboard:
    def test_to_dict(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        engine = AlertEngine({"coverage_drop_pct": 1.0})
        alerts = [a.to_dict() for a in engine.evaluate(drift, a, b)]
        db = QualityDashboard(a, drift, reg.summary(), alerts)
        d = db.to_dict()
        assert "current_snapshot" in d
        assert "drift" in d
        assert "regressions" in d
        assert "alerts" in d

    def test_changed_metrics(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        db = QualityDashboard(a, drift, reg.summary(), [])
        cm = db.changed_metrics()
        assert len(cm) > 0

    def test_top_regressions(self):
        a, b = make_snapshot_a(), make_snapshot_b()
        drift = DriftDetector(a, b).summary()
        reg = RegressionDetector(a, b, drift)
        db = QualityDashboard(a, drift, reg.summary(), [])
        tr = db.top_regressions()
        assert len(tr) > 0

    def test_top_improvements(self):
        better = make_snapshot_a()
        worse = make_snapshot_b()
        drift = DriftDetector(worse, better).summary()
        reg = RegressionDetector(worse, better, drift)
        db = QualityDashboard(better, drift, reg.summary(), [])
        ti = db.top_improvements()
        assert len(ti) > 0


class TestQualityReports:
    def test_generate_history(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {}, {
            "total_regressions": 0, "improvements": 0, "degradations": 0,
            "critical_count": 0, "high_count": 0, "medium_count": 0,
            "low_count": 0, "findings": [],
        }, [], {})
        p = r.generate_history(tmp_path / "history.xlsx", [make_snapshot_a()])
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) >= 1

    def test_generate_snapshots(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {}, {
            "total_regressions": 0, "improvements": 0, "degradations": 0,
            "critical_count": 0, "high_count": 0, "medium_count": 0,
            "low_count": 0, "findings": [],
        }, [], {})
        p = r.generate_snapshots(tmp_path / "snaps.xlsx")
        assert p.exists()

    def test_generate_drift_analysis(self, tmp_path):
        drift = {"coverage_drift": -2.0, "unknown_drift": 100, "decision_drift": {"a": 5}}
        r = QualityReports(make_snapshot_a(), drift, {
            "total_regressions": 0, "improvements": 0, "degradations": 0,
            "critical_count": 0, "high_count": 0, "medium_count": 0,
            "low_count": 0, "findings": [],
        }, [], {})
        p = r.generate_drift_analysis(tmp_path / "drift.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) > 0

    def test_generate_regression_analysis(self, tmp_path):
        reg = {"total_regressions": 2, "improvements": 0, "degradations": 2,
               "critical_count": 0, "high_count": 1, "medium_count": 1,
               "low_count": 0, "findings": [
                   {"type": "MORE_UNKNOWN", "metric": "unknown", "before": 100, "after": 200,
                    "delta": 100, "severity": "HIGH", "description": "UNKNOWN up"},
               ]}
        r = QualityReports(make_snapshot_a(), {}, reg, [], {})
        p = r.generate_regression_analysis(tmp_path / "reg.xlsx")
        assert p.exists()

    def test_generate_alert_history(self, tmp_path):
        alerts = [{"alert_id": "A1", "timestamp": "ts", "severity": "HIGH", "category": "coverage",
                   "metric": "coverage", "before_value": 80, "after_value": 75, "delta": -5,
                   "threshold": 2.0, "description": "Coverage dropped", "snapshot_before": "",
                   "snapshot_after": ""}]
        r = QualityReports(make_snapshot_a(), {}, {
            "total_regressions": 0, "improvements": 0, "degradations": 0,
            "critical_count": 0, "high_count": 0, "medium_count": 0,
            "low_count": 0, "findings": [],
        }, alerts, {})
        p = r.generate_alert_history(tmp_path / "alerts.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 1

    def test_generate_dashboard(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {}, {
            "total_regressions": 1, "improvements": 0, "degradations": 1,
            "critical_count": 0, "high_count": 1, "medium_count": 0,
            "low_count": 0, "findings": [{"type": "MORE_UNKNOWN", "metric": "unknown",
                                           "before": 100, "after": 200, "delta": 100,
                                           "severity": "HIGH", "description": "UNKNOWN up"}],
        }, [], {})
        p = r.generate_dashboard(tmp_path / "dash.xlsx")
        assert p.exists()

    def test_generate_markdown(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {"coverage_drift": -2.0, "accuracy_drift": -3.0}, {
            "total_regressions": 2, "improvements": 0, "degradations": 2,
            "critical_count": 1, "high_count": 1, "medium_count": 0,
            "low_count": 0, "findings": [
                {"type": "ACCURACY_DROP", "metric": "accuracy", "before": 85, "after": 80,
                 "delta": -5, "severity": "CRITICAL", "description": "Accuracy dropped"},
            ],
        }, [], {})
        p = r.generate_markdown(tmp_path / "report.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Continuous Quality Monitoring" in text
        assert "Drift Detected" in text
        assert "Regressions" in text
        assert "SAFE" in text or "UNSAFE" in text

    def test_generate_markdown_unsafe(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {"coverage_drift": -5.0}, {
            "total_regressions": 2, "improvements": 0, "degradations": 2,
            "critical_count": 1, "high_count": 1, "medium_count": 0,
            "low_count": 0, "findings": [
                {"type": "ACCURACY_DROP", "metric": "accuracy", "before": 85, "after": 70,
                 "delta": -15, "severity": "CRITICAL", "description": "Accuracy dropped"},
            ],
        }, [], {})
        p = r.generate_markdown(tmp_path / "report.md")
        text = p.read_text(encoding="utf-8")
        assert "UNSAFE" in text

    def test_generate_statistics_json(self, tmp_path):
        r = QualityReports(make_snapshot_a(), {"coverage_drift": -2.0}, {
            "total_regressions": 1, "improvements": 0, "degradations": 1,
            "critical_count": 0, "high_count": 0, "medium_count": 0,
            "low_count": 0, "findings": [],
        }, [], {})
        p = r.generate_statistics_json(tmp_path / "stats.json")
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert "snapshot" in data
        assert "deployment_safe" in data


class TestRunner:
    def test_import(self):
        from scripts import run_quality_monitoring
        assert hasattr(run_quality_monitoring, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_quality_monitoring")
        assert mod is not None
