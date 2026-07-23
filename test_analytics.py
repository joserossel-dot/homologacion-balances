"""
Comprehensive tests for analytics/ modules:
  - unclassified_analyzer.py
  - learning_dashboard.py
  - benchmark_dashboard.py
  - coverage_report.py
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

logging.disable(logging.CRITICAL)

# ═══════════════════════════════════════════
# Imports
# ═══════════════════════════════════════════

from analytics.unclassified_analyzer import UnclassifiedAnalyzer, _normalize_name
from analytics.learning_dashboard import LearningDashboard
from analytics.benchmark_dashboard import BenchmarkDashboard
from analytics.coverage_report import CoverageReport
from validation.validation_session import ValidationSession


# ═══════════════════════════════════════════
# _normalize_name
# ═══════════════════════════════════════════


def test_normalize_name_lowercases():
    assert _normalize_name("Banco Santander") == "banco santander"


def test_normalize_name_strips_accents():
    assert _normalize_name("Préstamo") == "prestamo"


def test_normalize_name_removes_special_chars():
    assert _normalize_name("Cta.Cte.") == "cta cte"


def test_normalize_name_collapses_spaces():
    assert _normalize_name("  Banco   Santander  ") == "banco santander"


def test_normalize_name_empty():
    assert _normalize_name("") == ""


# ═══════════════════════════════════════════
# UnclassifiedAnalyzer
# ═══════════════════════════════════════════


def _make_session(
    accounts: list[dict] | None = None,
    files: list[dict] | None = None,
) -> ValidationSession:
    s = ValidationSession()
    if accounts:
        s.processed_accounts = list(accounts)
    if files:
        s.processed_files = list(files)
    return s


def test_unclassified_analyzer_empty_session():
    s = _make_session()
    a = UnclassifiedAnalyzer(s)
    result = a.analyze()
    assert result["total_unclassified"] == 0
    assert result["total_accounts"] == 0
    assert result["unique_names"] == 0


def test_unclassified_analyzer_counts():
    s = _make_session([
        {"account_name": "Caja", "standard_code": "AC.01", "method": "code"},
        {"account_name": "Banco", "standard_code": None, "method": "unclassified"},
        {"account_name": "Proveedores", "standard_code": None, "method": "unclassified"},
        {"account_name": "Banco", "standard_code": None, "method": "unclassified"},
    ])
    a = UnclassifiedAnalyzer(s)
    result = a.analyze()
    assert result["total_unclassified"] == 3
    assert result["total_accounts"] == 4
    assert result["unique_names"] == 2
    assert result["unclassified_pct"] == 75.0


def test_unclassified_analyzer_top():
    s = _make_session([
        {"account_name": f"Cuenta_{i}", "standard_code": None, "method": "unclassified",
         "source_file": f"file_{i % 3}.pdf", "account_code": f"C{i}"}
        for i in range(20)
    ])
    a = UnclassifiedAnalyzer(s)
    top = a.top_unclassified(10)
    assert len(top) == 10
    assert all(t["frequency"] == 1 for t in top)
    assert all(t["files_count"] == 1 for t in top)


def test_unclassified_analyzer_export_excel():
    s = _make_session([
        {"account_name": "Test", "standard_code": None, "method": "unclassified"},
        {"account_name": "Otra", "standard_code": None, "method": "unclassified"},
    ])
    a = UnclassifiedAnalyzer(s)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    try:
        result = a.export_excel(path)
        assert Path(result).exists()
    finally:
        Path(path).unlink(missing_ok=True)


# ═══════════════════════════════════════════
# LearningDashboard
# ═══════════════════════════════════════════


def test_learning_dashboard_summary_empty_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = LearningDashboard(db_path)
        s = d.summary()
        assert s["total_records"] == 0
        assert s["avg_usage_count"] == 0.0
        d.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_learning_dashboard_top_learned_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = LearningDashboard(db_path)
        top = d.top_learned(10)
        assert top == []
        d.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_learning_dashboard_growth_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = LearningDashboard(db_path)
        growth = d.growth_over_time()
        assert growth == []
        d.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_learning_dashboard_conflicts_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = LearningDashboard(db_path)
        assert d.conflicts == []
        d.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_learning_dashboard_coverage_without_session():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        d = LearningDashboard(db_path)
        cov = d.coverage_by_company()
        assert cov == [{"total_gs_records": 0}]
        d.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════
# BenchmarkDashboard
# ═══════════════════════════════════════════


def test_benchmark_empty_gs():
    s = _make_session([
        {"account_name": "Caja", "final_code": "AC.01", "method": "code"},
    ])
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        b = BenchmarkDashboard(db_path)
        result = b.evaluate(s)
        assert result["total_gs_records"] == 0
        assert "error" in result
        b.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_benchmark_no_overlap():
    s = _make_session([
        {"account_name": "NoExiste", "final_code": "XX.01", "method": "code"},
    ])
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from gold_standard.models import GoldRecord
        from gold_standard.builder import GoldBuilder
        gb = GoldBuilder(db_path)
        gb.add_record(GoldRecord(
            account_name="Caja", final_code="AC.01",
            suggested_code="AC.01", suggested_confidence=0.98,
        ))
        gb.close()

        b = BenchmarkDashboard(db_path)
        result = b.evaluate(s)
        assert result["gs_covered_accounts"] == 0
        b.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_benchmark_exact_match():
    s = _make_session([
        {"account_name": "Caja", "final_code": "AC.01", "method": "learning_exact"},
        {"account_name": "Banco", "final_code": "AC.02", "method": "code"},
    ])
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from gold_standard.models import GoldRecord
        from gold_standard.builder import GoldBuilder
        gb = GoldBuilder(db_path)
        gb.add_record(GoldRecord(
            account_name="Caja", final_code="AC.01",
            suggested_code="AC.01", suggested_confidence=0.98,
        ))
        gb.add_record(GoldRecord(
            account_name="Banco", final_code="AC.02",
            suggested_code="AC.02", suggested_confidence=0.98,
        ))
        gb.close()

        b = BenchmarkDashboard(db_path)
        result = b.evaluate(s)
        assert result["gs_covered_accounts"] == 2
        assert result["exact_matches"] == 2
        assert result["accuracy"] == 1.0
        assert result["learning_accuracy"] == 1.0
        assert result["non_learning_accuracy"] == 1.0
        b.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_benchmark_partial_match():
    s = _make_session([
        {"account_name": "Caja", "final_code": "AC.01", "method": "learning_exact"},
        {"account_name": "Banco", "final_code": "AC.99", "method": "code"},
    ])
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from gold_standard.models import GoldRecord
        from gold_standard.builder import GoldBuilder
        gb = GoldBuilder(db_path)
        gb.add_record(GoldRecord(
            account_name="Caja", final_code="AC.01",
            suggested_code="AC.01", suggested_confidence=0.98,
        ))
        gb.add_record(GoldRecord(
            account_name="Banco", final_code="AC.02",
            suggested_code="AC.02", suggested_confidence=0.98,
        ))
        gb.close()

        b = BenchmarkDashboard(db_path)
        result = b.evaluate(s)
        assert result["gs_covered_accounts"] == 2
        assert result["exact_matches"] == 1
        assert result["accuracy"] == 0.5
        b.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_benchmark_compare_legacy():
    legacy = {
        "accounts_classified": 100, "accounts_unclassified": 400,
        "learning_hits": 0, "dictionary_hits": 80, "code_hits": 20,
        "fuzzy_hits": 10, "processing_time": 100.0, "avg_time": 5.0,
    }
    new_m = {
        "accounts_classified": 150, "accounts_unclassified": 350,
        "learning_hits": 50, "dictionary_hits": 50, "code_hits": 15,
        "fuzzy_hits": 5, "processing_time": 90.0, "avg_time": 4.5,
    }
    diff = BenchmarkDashboard.compare_legacy(legacy, new_m)
    assert diff["accounts_classified_delta"] == 50
    assert diff["learning_hits_delta"] == 50
    assert diff["processing_time_delta"] == -10.0


def test_benchmark_load_metrics(tmp_path):
    metrics = {"test": 123}
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    loaded = BenchmarkDashboard.load_metrics(report_dir)
    assert loaded["test"] == 123


def test_benchmark_load_metrics_not_found(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        BenchmarkDashboard.load_metrics(tmp_path / "nonexistent")


# ═══════════════════════════════════════════
# CoverageReport
# ═══════════════════════════════════════════


def _make_metrics(**overrides) -> dict:
    base = {
        "total_documents": 10,
        "pdf_count": 9,
        "excel_count": 1,
        "accounts_total": 1000,
        "accounts_classified": 300,
        "accounts_unclassified": 700,
        "learning_hits": 200,
        "dictionary_hits": 80,
        "code_hits": 20,
        "fuzzy_hits": 30,
        "parser_errors": 0,
        "processing_time": 120.0,
        "avg_time": 12.0,
        "p95_time": 30.0,
        "files_by_group": {"validacion": 10},
        "methods_distribution": {
            "unclassified": 700,
            "learning_exact": 180,
            "learning_fuzzy": 20,
            "dictionary_exact": 50,
            "dictionary_fuzzy": 30,
            "code": 20,
        },
    }
    base.update(overrides)
    return base


def test_coverage_report_empty_session():
    s = _make_session()
    m = _make_metrics()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cr = CoverageReport(s, m, db_path)
        text = cr.generate()
        assert "# Coverage Report" in text
        assert "## Resumen General" in text
        assert "## Distribución de Métodos" in text
        assert "## Recomendaciones Automáticas" in text
        assert "ALTA PRIORIDAD" in text  # 70% unclassified
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_coverage_report_high_coverage_no_warnings():
    s = _make_session()
    m = _make_metrics(
        accounts_total=1000,
        accounts_classified=950,
        accounts_unclassified=50,
        methods_distribution={
            "unclassified": 50,
            "learning_exact": 800,
            "learning_fuzzy": 100,
            "dictionary_exact": 30,
            "dictionary_fuzzy": 10,
            "code": 10,
        },
    )
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cr = CoverageReport(s, m, db_path)
        text = cr.generate()
        assert "BUENO" in text  # learning_pct > 50%
        assert "ALTA PRIORIDAD" not in text  # unclassified < 50%
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_coverage_report_save(tmp_path):
    s = _make_session()
    m = _make_metrics()
    out = tmp_path / "test_coverage.md"
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cr = CoverageReport(s, m, db_path)
        result = cr.save(str(out))
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "# Coverage Report" in content
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_coverage_report_top_unclassified():
    s = _make_session([
        {"account_name": f"SinClasif_{i}", "standard_code": None,
         "method": "unclassified", "source_file": f"file_{i%5}.pdf"}
        for i in range(30)
    ] + [
        {"account_name": "Clasificada", "standard_code": "AC.01", "method": "code"},
    ])
    m = _make_metrics(
        accounts_total=31, accounts_unclassified=30,
        methods_distribution={
            "unclassified": 30, "learning_exact": 0, "learning_fuzzy": 0,
            "dictionary_exact": 1, "dictionary_fuzzy": 0, "code": 0,
        },
    )
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cr = CoverageReport(s, m, db_path)
        text = cr.generate()
        assert "sinclasif_0" in text
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_coverage_report_gs_stats_displayed():
    s = _make_session()
    m = _make_metrics()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        from gold_standard.models import GoldRecord
        from gold_standard.builder import GoldBuilder
        gb = GoldBuilder(db_path)
        gb.add_record(GoldRecord(
            account_name="Test", final_code="T.01",
            suggested_code="T.01", suggested_confidence=0.98,
            reviewer="test",
        ))
        gb.close()

        cr = CoverageReport(s, m, db_path)
        text = cr.generate()
        assert "Gold Standard" in text
        assert "Registros totales" in text
    finally:
        Path(db_path).unlink(missing_ok=True)
