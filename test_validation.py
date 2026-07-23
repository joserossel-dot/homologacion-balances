"""
Comprehensive tests for validation/ modules:
  - dataset_manager.py
  - validation_session.py
  - metrics_engine.py
  - report_builder.py
  - runner.py
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logging.disable(logging.CRITICAL)

# ═══════════════════════════════════════════
# DatasetManager
# ═══════════════════════════════════════════

from validation.dataset_manager import (
    DatasetManager,
    DatasetFile,
    _should_ignore,
    _infer_group,
    _detect_file_type,
    KNOWN_GROUPS,
    IGNORED_PREFIXES,
    IGNORED_SUFFIXES,
    VALID_EXTENSIONS,
)


def test_known_groups():
    assert "entrenamiento" in KNOWN_GROUPS
    assert "validacion" in KNOWN_GROUPS
    assert "edge_cases" in KNOWN_GROUPS
    assert "corruptos" in KNOWN_GROUPS
    assert len(KNOWN_GROUPS) == 4


def test_valid_extensions():
    assert ".pdf" in VALID_EXTENSIONS
    assert ".xls" in VALID_EXTENSIONS
    assert ".xlsx" in VALID_EXTENSIONS
    assert ".tmp" not in VALID_EXTENSIONS


def test_should_ignore_dotfiles():
    assert _should_ignore(".DS_Store")
    assert _should_ignore(".hidden")


def test_should_ignore_tilde_prefix():
    assert _should_ignore("~$file.xlsx")


def test_should_ignore_tmp():
    assert _should_ignore("temp.tmp")


def test_should_ignore_normal_file():
    assert not _should_ignore("balance_2024.pdf")
    assert not _should_ignore("data.xlsx")
    assert not _should_ignore("informe.xls")


def test_detect_file_type_pdf():
    assert _detect_file_type(Path("file.pdf")) == "pdf"
    assert _detect_file_type(Path("file.PDF")) == "pdf"


def test_detect_file_type_excel():
    assert _detect_file_type(Path("file.xls")) == "excel"
    assert _detect_file_type(Path("file.xlsx")) == "excel"
    assert _detect_file_type(Path("file.XLSX")) == "excel"


def test_detect_file_type_unknown():
    assert _detect_file_type(Path("file.txt")) == "unknown"
    assert _detect_file_type(Path("file.csv")) == "unknown"


def test_infer_group_from_parent_dir():
    root = Path("/datasets")
    assert _infer_group(Path("/datasets/entrenamiento/bal.pdf"), root) == "entrenamiento"
    assert _infer_group(Path("/datasets/validacion/bal.pdf"), root) == "validacion"
    assert _infer_group(Path("/datasets/edge_cases/bal.pdf"), root) == "edge_cases"
    assert _infer_group(Path("/datasets/corruptos/bal.pdf"), root) == "corruptos"


def test_infer_group_nested():
    root = Path("/datasets")
    assert _infer_group(Path("/datasets/entrenamiento/subdir/bal.pdf"), root) == "entrenamiento"


def test_infer_group_default():
    root = Path("/datasets")
    assert _infer_group(Path("/datasets/otros/bal.pdf"), root) == "validacion"


def test_infer_group_root_level():
    root = Path("/datasets")
    assert _infer_group(Path("/datasets/bal.pdf"), root) == "validacion"


def test_discover_finds_files():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "entrenamiento").mkdir()
        (d / "validacion").mkdir()
        (d / "corruptos").mkdir()
        (d / "entrenamiento" / "bal1.pdf").touch()
        (d / "validacion" / "bal2.xlsx").touch()
        (d / "corruptos" / "corrupto.pdf").touch()

        mgr = DatasetManager(d)
        files = mgr.discover()
        assert len(files) == 3


def test_discover_ignores_dotfiles():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / ".DS_Store").touch()
        (d / "bal.pdf").touch()
        mgr = DatasetManager(d)
        files = mgr.discover()
        assert len(files) == 1


def test_discover_ignores_tmp():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "temp.tmp").touch()
        (d / "~$temp.xlsx").touch()
        (d / "real.pdf").touch()
        mgr = DatasetManager(d)
        files = mgr.discover()
        assert len(files) == 1
        assert files[0].path.name == "real.pdf"


def test_discover_non_pdf_excel():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "readme.txt").touch()
        (d / "data.csv").touch()
        mgr = DatasetManager(d)
        files = mgr.discover()
        assert len(files) == 0


def test_groups_returns_dict():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "entrenamiento").mkdir()
        (d / "validacion").mkdir()
        (d / "entrenamiento" / "a.pdf").touch()
        (d / "validacion" / "b.xlsx").touch()
        mgr = DatasetManager(d)
        grps = mgr.groups()
        assert "entrenamiento" in grps
        assert "validacion" in grps
        assert len(grps["entrenamiento"]) == 1
        assert len(grps["validacion"]) == 1


def test_groups_default_group():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "subdir").mkdir()
        (d / "subdir" / "a.pdf").touch()
        mgr = DatasetManager(d)
        grps = mgr.groups()
        assert "validacion" in grps
        assert len(grps["validacion"]) == 1


def test_discover_no_directory():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "nonexistent"
        mgr = DatasetManager(d)
        files = mgr.discover()
        assert files == []


def test_dataset_file_dataclass():
    f = DatasetFile(path=Path("/a/b.pdf"), group="entrenamiento", file_type="pdf")
    assert f.path.name == "b.pdf"
    assert f.group == "entrenamiento"
    assert f.file_type == "pdf"


# ═══════════════════════════════════════════
# ValidationSession
# ═══════════════════════════════════════════

from validation.validation_session import ValidationSession


def test_session_defaults():
    s = ValidationSession()
    assert s.processed_files == []
    assert s.processed_accounts == []
    assert s.errors == []
    assert s.warnings == []
    assert s.metrics == {}
    assert s.execution_time == 0.0
    assert s.memory_peak == 0.0


def test_session_timer():
    s = ValidationSession()
    s.start_timer()
    import time
    time.sleep(0.01)
    elapsed = s.stop_timer()
    assert elapsed > 0.0
    assert s.execution_time > 0.0


def test_add_file():
    s = ValidationSession()
    s.add_file({"source_file": "test.pdf", "accounts_total": 10})
    assert len(s.processed_files) == 1


def test_add_account():
    s = ValidationSession()
    s.add_account({"account_code": "101", "method": "code"})
    assert len(s.processed_accounts) == 1


def test_add_error():
    s = ValidationSession()
    s.add_error({"category": "parser", "file": "test.pdf", "error": "parse failed"})
    assert len(s.errors) == 1


def test_add_warning():
    s = ValidationSession()
    s.add_warning({"file": "test.pdf", "warning": "low confidence"})
    assert len(s.warnings) == 1


def test_merge_file_result():
    s = ValidationSession()
    result = {
        "source_file": "test.pdf",
        "accounts_total": 10,
        "accounts_classified": 8,
        "accounts_ignored": 2,
        "accounts_without_dictionary_match": 1,
        "learning_hits": 3,
        "learning_exact": 2,
        "learning_fuzzy": 1,
        "fallback_classifier": 5,
        "elapsed_seconds": 1.5,
        "classified": [
            {"account_code": "101", "method": "code", "standard_code": "AC.01"},
            {"account_code": "102", "method": "learning_exact", "standard_code": "PC.02"},
        ],
        "ignored": [{"account_code": "999", "ignored_reason": "movement_only"}],
    }
    s.merge_file_result(result)
    assert len(s.processed_files) == 1
    assert len(s.processed_accounts) == 2
    assert s.processed_files[0]["source_file"] == "test.pdf"
    assert s.processed_files[0]["learning_hits"] == 3
    assert s.processed_accounts[0]["account_code"] == "101"


def test_counts_by_method():
    s = ValidationSession()
    s.add_account({"method": "code"})
    s.add_account({"method": "code"})
    s.add_account({"method": "learning_exact"})
    counts = s.counts_by_method()
    assert counts.get("code") == 2
    assert counts.get("learning_exact") == 1
    assert counts.get("dictionary_fuzzy", 0) == 0


def test_unclassified_accounts():
    s = ValidationSession()
    s.add_account({"account_code": "101", "standard_code": "AC.01"})
    s.add_account({"account_code": "999", "standard_code": None})
    s.add_account({"account_code": "888", "standard_code": None})
    ua = s.unclassified_accounts()
    assert len(ua) == 2
    assert ua[0]["account_code"] == "999"


def test_summary():
    s = ValidationSession()
    s.add_file({"source_file": "a.pdf"})
    s.add_file({"source_file": "b.pdf"})
    s.add_account({"account_code": "101"})
    s.add_error({"error": "err"})
    s.add_warning({"warning": "warn"})
    s.execution_time = 3.5
    sm = s.summary()
    assert sm["files_total"] == 2
    assert sm["accounts_total"] == 1
    assert sm["errors_total"] == 1
    assert sm["warnings_total"] == 1
    assert sm["execution_time"] == 3.5


# ═══════════════════════════════════════════
# MetricsEngine
# ═══════════════════════════════════════════

from validation.metrics_engine import MetricsEngine


def test_metrics_engine_empty():
    s = ValidationSession()
    m = MetricsEngine().compute(s)
    assert m["total_documents"] == 0
    assert m["accounts_total"] == 0
    assert m["accounts_classified"] == 0
    assert m["parser_errors"] == 0
    assert m["processing_time"] == 0.0
    assert m["avg_time"] == 0.0
    assert m["p95_time"] == 0.0


def test_metrics_counts():
    s = ValidationSession()
    s.merge_file_result({
        "source_file": "test.pdf",
        "accounts_total": 10,
        "accounts_classified": 8,
        "accounts_ignored": 2,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 3,
        "learning_exact": 2,
        "learning_fuzzy": 1,
        "fallback_classifier": 5,
        "elapsed_seconds": 1.5,
        "classified": [
            {"account_code": "101", "method": "code", "standard_code": "AC.01"},
            {"account_code": "102", "method": "learning_exact", "standard_code": "PC.02"},
        ],
        "ignored": [],
    })
    m = MetricsEngine().compute(s)
    assert m["total_documents"] == 1
    assert m["pdf_count"] == 1
    assert m["excel_count"] == 0
    assert m["accounts_total"] == 2
    assert m["accounts_classified"] == 2
    assert m["accounts_manual"] == 0
    assert m["learning_hits"] == 1  # from accounts: 1 learning_exact
    assert m["processing_time"] == 1.5
    assert m["dictionary_hits"] == 0
    assert m["code_hits"] == 1
    assert m["fuzzy_hits"] == 0


def test_metrics_mixed_file_types():
    s = ValidationSession()
    s.merge_file_result({
        "source_file": "a.pdf",
        "classified": [],
        "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.5,
    })
    s.merge_file_result({
        "source_file": "b.xlsx",
        "classified": [],
        "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.3,
    })
    m = MetricsEngine().compute(s)
    assert m["total_documents"] == 2
    assert m["pdf_count"] == 1
    assert m["excel_count"] == 1
    assert m["processing_time"] == 0.8
    assert m["avg_time"] == 0.4


def test_metrics_p95():
    s = ValidationSession()
    for i in range(20):
        s.merge_file_result({
            "source_file": f"{i}.pdf",
            "classified": [], "ignored": [],
            "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
            "accounts_without_dictionary_match": 0,
            "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
            "fallback_classifier": 0, "elapsed_seconds": float(i),
        })
    m = MetricsEngine().compute(s)
    assert m["total_documents"] == 20
    assert m["processing_time"] == sum(range(20))  # 190
    # sorted timings: [0..19], p95: 0.95 * 19 = 18.05, between 18 and 19
    assert 18.0 <= m["p95_time"] <= 19.0


def test_metrics_parser_errors():
    s = ValidationSession()
    s.add_error({"category": "parser", "file": "a.pdf", "error": "fail"})
    s.add_error({"category": "parser", "file": "b.pdf", "error": "fail"})
    s.add_error({"category": "general", "file": "c.pdf", "error": "oom"})
    m = MetricsEngine().compute(s)
    assert m["parser_errors"] == 2


def test_metrics_ocr_count():
    s = ValidationSession()
    s.merge_file_result({
        "source_file": "a.pdf", "ocr": True,
        "classified": [], "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.5,
    })
    s.merge_file_result({
        "source_file": "b.pdf", "ocr": False,
        "classified": [], "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.3,
    })
    m = MetricsEngine().compute(s)
    assert m["ocr_count"] == 1


def test_metrics_files_by_group():
    s = ValidationSession()
    s.merge_file_result({
        "source_file": "a.pdf", "group": "entrenamiento",
        "classified": [], "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.1,
    })
    s.merge_file_result({
        "source_file": "b.pdf", "group": "validacion",
        "classified": [], "ignored": [],
        "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
        "accounts_without_dictionary_match": 0,
        "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
        "fallback_classifier": 0, "elapsed_seconds": 0.2,
    })
    m = MetricsEngine().compute(s)
    assert m["files_by_group"]["entrenamiento"] == 1
    assert m["files_by_group"]["validacion"] == 1


# ═══════════════════════════════════════════
# ReportBuilder
# ═══════════════════════════════════════════

from validation.report_builder import ReportBuilder


def _make_sample_session() -> ValidationSession:
    s = ValidationSession()
    s.merge_file_result({
        "source_file": "test.pdf",
        "accounts_total": 10,
        "accounts_classified": 8,
        "accounts_ignored": 2,
        "accounts_without_dictionary_match": 1,
        "learning_hits": 3,
        "learning_exact": 2,
        "learning_fuzzy": 1,
        "fallback_classifier": 5,
        "elapsed_seconds": 1.5,
        "classified": [
            {"account_code": "101", "account_name": "Caja", "method": "code", "standard_code": "AC.01",
             "nature": "ASSET", "classification_amount": 1000.0, "final_code": "AC.01",
             "confidence": 0.97, "reason": "code match", "special_rule": None,
             "source_file": "test.pdf", "source_page": 1},
            {"account_code": "999", "account_name": "Raro", "method": "unclassified", "standard_code": None,
             "nature": "LIABILITY", "classification_amount": 500.0, "final_code": None,
             "confidence": 0.0, "reason": "no match", "special_rule": None,
             "source_file": "test.pdf", "source_page": 2},
        ],
        "ignored": [{"account_code": "888", "ignored_reason": "movement_only"}],
    })
    s.add_error({"category": "parser", "file": "test.pdf", "error": "page 3 parse failed"})
    s.add_warning({"file": "test.pdf", "warning": "low confidence on account 999"})
    s.execution_time = 2.0
    return s


def test_report_builds_timestamp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_run_001")
        assert out.exists()
        assert out.name == "test_run_001"


def test_report_creates_all_files():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_run_002")
        for fname in builder.expected_files():
            assert (out / fname).exists(), f"Missing: {fname}"


def test_summary_md_content():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_summary")
        content = (out / "summary.md").read_text(encoding="utf-8")
        assert "# Reporte de Validación" in content
        assert "Documentos totales:" in content
        assert "Cuentas totales:" in content
        assert "Errores de parser:" in content


def test_metrics_json_content():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_metrics")
        data = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
        assert data["total_documents"] == 1
        assert data["accounts_total"] == 2
        assert data["accounts_classified"] == 1
        assert data["accounts_manual"] == 1


def test_benchmark_csv_content():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_csv")
        content = (out / "benchmark.csv").read_text(encoding="utf-8")
        assert "source_file" in content
        assert "test.pdf" in content
        assert "accounts_total" in content


def test_timings_csv_content():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_timings")
        content = (out / "timings.csv").read_text(encoding="utf-8")
        assert "source_file" in content
        assert "elapsed_seconds" in content
        assert "1.5" in content


def test_errors_xlsx_created():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_err")
        assert (out / "errors.xlsx").exists()


def test_parser_errors_xlsx_created():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_parserr")
        assert (out / "parser_errors.xlsx").exists()


def test_unclassified_xlsx_created():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = _make_sample_session()
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_uncl")
        assert (out / "unclassified.xlsx").exists()


def test_report_no_errors_still_creates_files():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        builder = ReportBuilder(base)
        s = ValidationSession()
        s.merge_file_result({
            "source_file": "clean.pdf",
            "accounts_total": 0, "accounts_classified": 0, "accounts_ignored": 0,
            "accounts_without_dictionary_match": 0,
            "learning_hits": 0, "learning_exact": 0, "learning_fuzzy": 0,
            "fallback_classifier": 0, "elapsed_seconds": 0.1,
            "classified": [{"account_code": "101", "method": "code", "standard_code": "AC.01"}],
            "ignored": [],
        })
        m = __import__("validation.metrics_engine", fromlist=["MetricsEngine"]).MetricsEngine().compute(s)
        out = builder.build_all(s, m, timestamp="test_clean")
        for fname in builder.expected_files():
            assert (out / fname).exists()


def test_expected_files_list():
    expected = ReportBuilder.expected_files()
    assert "summary.md" in expected
    assert "metrics.json" in expected
    assert "benchmark.csv" in expected
    assert "errors.xlsx" in expected
    assert "parser_errors.xlsx" in expected
    assert "unclassified.xlsx" in expected
    assert "timings.csv" in expected


# ═══════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════

from validation.runner import process_file, _print_summary


def test_process_file_handles_missing_file():
    """process_file should not crash on non-existent files."""
    from pipeline.homologation_pipeline import HomologationPipeline
    from validation.dataset_manager import DatasetFile

    pipeline = HomologationPipeline(":memory:")
    s = ValidationSession()
    dfile = DatasetFile(path=Path("/nonexistent/bal.pdf"), group="entrenamiento", file_type="pdf")
    process_file(pipeline, dfile, s)
    # Pipeline handles gracefully — produces 0-account result
    assert len(s.processed_files) == 1
    assert s.processed_files[0]["accounts_total"] == 0


def test_print_summary_does_not_crash():
    import io
    import sys
    from pathlib import Path

    metrics = {
        "total_documents": 5,
        "pdf_count": 3,
        "excel_count": 2,
        "accounts_total": 100,
        "accounts_classified": 85,
        "accounts_manual": 15,
        "learning_hits": 10,
        "processing_time": 12.5,
    }
    report_path = Path("/tmp/test_report")
    captured = io.StringIO()
    old = sys.stdout
    sys.stdout = captured
    try:
        _print_summary(metrics, report_path)
    finally:
        sys.stdout = old
    output = captured.getvalue()
    assert "VALIDACION COMPLETADA" in output
    assert "5" in output
    assert "100" in output


# ═══════════════════════════════════════════
# Integration: full flow without real files
# ═══════════════════════════════════════════

def test_full_validation_flow():
    """End-to-end: DatasetManager discovers 4 groups correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for group in ("entrenamiento", "validacion", "edge_cases", "corruptos"):
            (d / group).mkdir()
            (d / group / f"balance_{group}.pdf").touch()

        from validation.dataset_manager import DatasetManager
        mgr = DatasetManager(d)
        files = mgr.discover()
        assert len(files) == 4
        groups = mgr.groups()
        assert "entrenamiento" in groups
        assert "validacion" in groups
        assert "edge_cases" in groups
        assert "corruptos" in groups
        assert len(groups["entrenamiento"]) == 1


def test_runner_cli_help():
    """Verify the CLI can print help without crashing."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "validation.runner", "--help"],
        capture_output=True, text=True,
        cwd=Path(__file__).resolve().parent,
    )
    assert result.returncode == 0
    assert "datasets_root" in result.stdout


if __name__ == "__main__":
    import sys
    this = sys.modules[__name__]
    passed = 0
    failed = 0
    for name in sorted(dir(this)):
        if name.startswith("test_"):
            try:
                getattr(this, name)()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
