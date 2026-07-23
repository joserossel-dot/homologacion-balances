"""
Tests for analytics/dashboard.py and its integration with app_validacion.py.
"""

from __future__ import annotations

import logging

logging.disable(logging.CRITICAL)

# ═══════════════════════════════════════════
# AnalyticsDashboard
# ═══════════════════════════════════════════

from analytics.dashboard import AnalyticsDashboard


def test_analytics_dashboard_instantiates():
    d = AnalyticsDashboard()
    assert isinstance(d, AnalyticsDashboard)


def test_analytics_dashboard_render_exists():
    d = AnalyticsDashboard()
    assert hasattr(d, "render")
    assert callable(d.render)


def test_analytics_dashboard_all_methods_exist():
    expected = [
        "render",
        "_render_header",
        "_render_kpis",
        "_render_coverage",
        "_render_gold_standard",
        "_render_learning",
        "_render_unclassified",
        "_render_benchmark",
        "_render_history",
        "_render_exports",
    ]
    d = AnalyticsDashboard()
    for name in expected:
        assert hasattr(d, name), f"Missing method: {name}"
        assert callable(getattr(d, name)), f"Not callable: {name}"


def test_analytics_dashboard_render_returns_none():
    d = AnalyticsDashboard()
    result = d.render()
    assert result is None


def test_analytics_dashboard_each_method_returns_none():
    d = AnalyticsDashboard()
    private = [
        "_render_header",
        "_render_kpis",
        "_render_coverage",
        "_render_gold_standard",
        "_render_learning",
        "_render_unclassified",
        "_render_benchmark",
        "_render_history",
        "_render_exports",
    ]
    for name in private:
        result = getattr(d, name)()
        assert result is None, f"{name} should return None, got {result}"


def test_analytics_dashboard_init_with_metrics():
    metrics = {"total_documents": 10, "accounts_total": 500}
    d = AnalyticsDashboard(metrics=metrics)
    assert d._metrics == metrics
    assert d._session is None


def test_analytics_dashboard_init_with_session():
    from validation.validation_session import ValidationSession
    s = ValidationSession()
    d = AnalyticsDashboard(session=s)
    assert d._session is s
    assert d._metrics is None


def test_analytics_dashboard_render_kpis_returns_none_no_data():
    d = AnalyticsDashboard()
    result = d._render_kpis()
    assert result is None


def test_analytics_dashboard_render_kpis_caches_computed_metrics():
    import streamlit as st
    from unittest.mock import patch
    from validation.validation_session import ValidationSession

    s = ValidationSession()
    s.add_account({"account_name": "Caja", "standard_code": "AC.01", "method": "code"})
    s.add_account({"account_name": "Banco", "standard_code": None, "method": "unclassified"})
    s.add_file({"source_file": "test.pdf", "elapsed_seconds": 1.5})

    d = AnalyticsDashboard(session=s)
    assert d._metrics is None

    with patch.object(st, "columns") as mock_cols, \
         patch.object(st, "metric"), \
         patch.object(st, "caption"):
        mock_cols.return_value = [st] * 6
        d._render_kpis()
        assert d._metrics is not None
        assert "total_documents" in d._metrics
        assert d._metrics["total_documents"] == 1


def test_analytics_dashboard_render_coverage_returns_none_no_data():
    d = AnalyticsDashboard()
    result = d._render_coverage()
    assert result is None


def _make_mock_columns(n=2):
    from unittest.mock import MagicMock
    return [MagicMock(name=f"col{i}") for i in range(n)]


def _mock_columns_side_effect(spec):
    if isinstance(spec, (list, tuple)):
        n = len(spec)
    else:
        n = int(spec)
    return _make_mock_columns(n)


def test_analytics_dashboard_render_coverage_caches_computed_metrics():
    import streamlit as st
    from unittest.mock import patch
    from validation.validation_session import ValidationSession

    s = ValidationSession()
    s.add_account({"account_name": "Caja", "standard_code": "AC.01", "method": "code"})
    s.add_account({"account_name": "Banco", "standard_code": None, "method": "unclassified"})
    s.add_file({"source_file": "test.pdf", "elapsed_seconds": 1.5})

    d = AnalyticsDashboard(session=s)
    assert d._metrics is None

    with patch.object(st, "columns") as mock_cols, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "caption") as mock_cap:
        mock_cols.side_effect = _mock_columns_side_effect
        d._render_coverage()
        assert d._metrics is not None
        assert "methods_distribution" in d._metrics
        assert d._metrics["accounts_total"] == 2


def test_analytics_dashboard_render_coverage_uses_provided_metrics():
    import streamlit as st
    from unittest.mock import patch

    metrics = {
        "accounts_total": 1000,
        "accounts_unclassified": 600,
        "methods_distribution": {
            "learning_exact": 200, "learning_fuzzy": 50,
            "dictionary_exact": 80, "dictionary_fuzzy": 40,
            "code": 30, "unclassified": 600,
        },
    }
    d = AnalyticsDashboard(metrics=metrics)

    with patch.object(st, "columns") as mock_cols, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "caption") as mock_cap:
        mock_cols.side_effect = _mock_columns_side_effect
        result = d._render_coverage()
        assert result is None
        assert d._metrics is metrics


def test_analytics_dashboard_render_gold_standard_returns_none_no_data():
    d = AnalyticsDashboard()
    result = d._render_gold_standard()
    assert result is None


def test_analytics_dashboard_render_gold_standard_shows_empty_info():
    import streamlit as st
    from unittest.mock import patch, MagicMock

    mock_builder = MagicMock()
    mock_builder.statistics.return_value = {"total_records": 0, "exact_hits": 0, "conflicts": 0}
    mock_builder.list_all.return_value = []
    mock_builder.find_conflicts.return_value = []
    mock_builder.top_learned.return_value = []

    d = AnalyticsDashboard(metrics={"accounts_total": 1})

    with patch("gold_standard.builder.GoldBuilder", return_value=mock_builder), \
         patch.object(st, "info") as mock_info, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "columns") as mock_cols:
        mock_cols.side_effect = _mock_columns_side_effect
        d._render_gold_standard()
        mock_info.assert_called_once()
        assert "vacío" in mock_info.call_args[0][0]


def test_analytics_dashboard_render_gold_standard_shows_metrics():
    import streamlit as st
    from unittest.mock import patch, MagicMock
    from gold_standard.models import GoldRecord

    r1 = GoldRecord(account_name="Caja", final_code="AC.01", usage_count=10, last_used="2025-01-15T12:00:00")
    r2 = GoldRecord(account_name="Banco", final_code="AC.02", usage_count=5, last_used="2025-01-10T12:00:00")

    mock_builder = MagicMock()
    mock_builder.statistics.return_value = {"total_records": 2, "exact_hits": 1, "conflicts": 1}
    mock_builder.list_all.return_value = [r1, r2]
    mock_builder.find_conflicts.return_value = [
        {"account_name": "Caja", "code_count": 2, "codes": "AC.01,AC.07", "total_versions": 2}
    ]
    mock_builder.top_learned.return_value = [
        {"account_name": "Caja", "final_code": "AC.01", "usage_count": 10, "last_used": "2025-01-15T12:00:00"}
    ]

    d = AnalyticsDashboard(metrics={"accounts_total": 100})

    columns_calls: list = []

    def _capture_columns(spec):
        cols = _mock_columns_side_effect(spec)
        columns_calls.append(cols)
        return cols

    with patch("gold_standard.builder.GoldBuilder", return_value=mock_builder), \
         patch.object(st, "columns") as mock_cols, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "download_button") as mock_dl, \
         patch.object(st, "info") as mock_info:
        mock_cols.side_effect = _capture_columns
        d._render_gold_standard()

        mock_info.assert_not_called()
        assert mock_dl.call_count == 2
        assert len(columns_calls) >= 2
        kpi_cols = columns_calls[0]
        assert kpi_cols[0].metric.called
        assert kpi_cols[4].metric.called


def test_analytics_dashboard_render_learning_returns_none_no_data():
    d = AnalyticsDashboard()
    result = d._render_learning()
    assert result is None


def test_analytics_dashboard_render_learning_empty_returns_none():
    import streamlit as st
    from unittest.mock import patch, MagicMock

    mock_builder = MagicMock()
    mock_builder.top_learned.return_value = []

    d = AnalyticsDashboard(metrics={"accounts_total": 100})

    with patch("gold_standard.builder.GoldBuilder", return_value=mock_builder), \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "dataframe") as mock_df:
        result = d._render_learning()
        assert result is None
        mock_df.assert_not_called()


def test_analytics_dashboard_render_learning_shows_dataframe():
    import streamlit as st
    from unittest.mock import patch, MagicMock

    top_data = [
        {"account_name": "Caja", "final_code": "AC.01", "usage_count": 15, "last_used": "2025-03-01T12:00:00"},
        {"account_name": "Banco", "final_code": "AC.02", "usage_count": 10, "last_used": "2025-02-15T12:00:00"},
        {"account_name": "Clientes", "final_code": "AC.03", "usage_count": 8, "last_used": "2025-01-20T12:00:00"},
    ]
    mock_builder = MagicMock()
    mock_builder.top_learned.return_value = top_data

    d = AnalyticsDashboard(metrics={"accounts_total": 100})

    with patch("gold_standard.builder.GoldBuilder", return_value=mock_builder), \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "dataframe") as mock_df:
        result = d._render_learning()
        assert result is None
        mock_md.assert_called_once()
        mock_df.assert_called_once()
        args, kwargs = mock_df.call_args
        rows = args[0]
        assert len(rows) == 3
        assert rows[0]["Cuenta"] == "Caja"
        assert rows[0]["Código"] == "AC.01"
        assert rows[0]["Usos"] == 15
        assert rows[0]["Último Uso"] == "2025-03-01"


def test_analytics_dashboard_render_unclassified_returns_none_no_session():
    d = AnalyticsDashboard()
    result = d._render_unclassified()
    assert result is None


def test_analytics_dashboard_render_unclassified_empty_returns_none():
    import streamlit as st
    from unittest.mock import patch, MagicMock
    from validation.validation_session import ValidationSession

    s = ValidationSession()
    mock_analyzer = MagicMock()
    mock_analyzer.top_unclassified.return_value = []

    d = AnalyticsDashboard(session=s)

    with patch("analytics.unclassified_analyzer.UnclassifiedAnalyzer", return_value=mock_analyzer), \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "dataframe") as mock_df:
        result = d._render_unclassified()
        assert result is None
        mock_df.assert_not_called()


def test_analytics_dashboard_render_unclassified_shows_dataframe():
    import streamlit as st
    from unittest.mock import patch, MagicMock
    from validation.validation_session import ValidationSession

    top_data = [
        {"example_raw_name": "Caja Chica", "frequency": 25, "files_count": 8, "unique_codes_count": 0, "normalized_name": "caja chica", "companies_count": 3},
        {"example_raw_name": "Banco Estado", "frequency": 15, "files_count": 5, "unique_codes_count": 1, "normalized_name": "banco estado", "companies_count": 2},
    ]

    s = ValidationSession()
    mock_analyzer = MagicMock()
    mock_analyzer.top_unclassified.return_value = top_data

    d = AnalyticsDashboard(session=s)

    with patch("analytics.unclassified_analyzer.UnclassifiedAnalyzer", return_value=mock_analyzer), \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "dataframe") as mock_df, \
         patch.object(st, "selectbox") as mock_sb, \
         patch.object(st, "text_input") as mock_ti, \
         patch.object(st, "button") as mock_btn:
        mock_sb.return_value = "Caja Chica"
        mock_ti.return_value = ""
        mock_btn.return_value = False
        result = d._render_unclassified()
        assert result is None
        mock_df.assert_called_once()
        args, kwargs = mock_df.call_args
        rows = args[0]
        assert len(rows) == 2
        assert rows[0]["Cuenta"] == "Caja Chica"
        assert rows[0]["Frecuencia"] == 25
        assert mock_sb.called
        assert mock_ti.called


def test_analytics_dashboard_render_benchmark_returns_none_no_session():
    d = AnalyticsDashboard()
    result = d._render_benchmark()
    assert result is None


def test_analytics_dashboard_render_benchmark_empty_gs():
    import streamlit as st
    from unittest.mock import patch, MagicMock
    from validation.validation_session import ValidationSession

    mock_bench = MagicMock()
    mock_bench.evaluate.return_value = {"error": "Gold Standard is empty — cannot evaluate", "total_gs_records": 0}

    s = ValidationSession()
    d = AnalyticsDashboard(session=s)

    with patch("analytics.benchmark_dashboard.BenchmarkDashboard", return_value=mock_bench), \
         patch.object(st, "info") as mock_info, \
         patch.object(st, "markdown") as mock_md:
        result = d._render_benchmark()
        assert result is None
        mock_info.assert_called_once()


def test_analytics_dashboard_render_benchmark_shows_metrics():
    import streamlit as st
    from unittest.mock import patch, MagicMock
    from validation.validation_session import ValidationSession

    eval_result = {
        "total_gs_records": 187,
        "total_accounts_in_pipeline": 1000,
        "gs_covered_accounts": 245,
        "accuracy": 0.9347,
        "exact_matches": 229,
        "macro_precision": 0.9123,
        "macro_recall": 0.8987,
        "macro_f1": 0.9054,
        "weighted_precision": 0.9347,
        "weighted_recall": 0.9347,
        "weighted_f1": 0.9347,
        "learning_accuracy": 0.9600,
        "non_learning_accuracy": 0.8500,
        "per_code": [],
    }

    mock_bench = MagicMock()
    mock_bench.evaluate.return_value = eval_result

    s = ValidationSession()
    s.add_account({"account_name": "Caja", "final_code": "AC.01", "method": "learning_exact"})
    s.add_account({"account_name": "Banco", "final_code": "AC.02", "method": "code"})
    d = AnalyticsDashboard(session=s, metrics={"accounts_total": 2, "methods_distribution": {"learning_exact": 1, "learning_fuzzy": 0}})

    columns_calls: list = []

    def _capture_cols(spec):
        cols = _mock_columns_side_effect(spec)
        columns_calls.append(cols)
        return cols

    with patch("analytics.benchmark_dashboard.BenchmarkDashboard", return_value=mock_bench), \
         patch.object(st, "columns") as mock_cols, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "info") as mock_info:
        mock_cols.side_effect = _capture_cols
        result = d._render_benchmark()
        assert result is None
        mock_info.assert_not_called()
        assert len(columns_calls) >= 2
        top_cols = columns_calls[0]
        assert len(top_cols) == 5
        assert top_cols[0].metric.called
        assert top_cols[4].metric.called
        bottom_cols = columns_calls[1]
        assert len(bottom_cols) == 4
        assert bottom_cols[0].metric.called
        assert bottom_cols[3].metric.called
        # Verify caching: second call uses same cached result
        d._render_benchmark()
        mock_bench.evaluate.assert_called_once()


def test_analytics_dashboard_render_history_returns_none_no_dir():
    d = AnalyticsDashboard()
    result = d._render_history()
    assert result is None


def test_analytics_dashboard_render_history_shows_info_few_runs(tmp_path):
    import json, os
    import streamlit as st
    from unittest.mock import patch, MagicMock

    vdir = tmp_path / "reports" / "validation"
    vdir.mkdir(parents=True)
    (vdir / "20260706_100000").mkdir()
    (vdir / "20260706_100000" / "metrics.json").write_text(json.dumps({"total_documents": 1}))

    d = AnalyticsDashboard()
    reports_path = str(vdir)

    with patch("pathlib.Path") as mock_path_cls, \
         patch.object(st, "info") as mock_info, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "line_chart") as mock_lc, \
         patch.object(st, "bar_chart") as mock_bc:
        mock_path = MagicMock()
        mock_path_cls.return_value = mock_path
        mock_path.is_dir.return_value = True
        mock_path.iterdir.return_value = list(vdir.iterdir())
        result = d._render_history()
        assert result is None
        assert "al menos 2 ejecuciones" in mock_info.call_args[0][0]


def test_analytics_dashboard_render_history_shows_charts(tmp_path):
    import json
    import streamlit as st
    from unittest.mock import patch, MagicMock

    vdir = tmp_path / "reports" / "validation"
    vdir.mkdir(parents=True)

    for i, ts in enumerate(["20260706_100000", "20260706_110000"]):
        d = vdir / ts
        d.mkdir()
        (d / "metrics.json").write_text(json.dumps({
            "total_documents": 10 + i,
            "accounts_total": 400 + i * 100,
            "accounts_classified": 50 + i * 20,
            "accounts_unclassified": 350 + i * 80,
            "learning_hits": 0 + i * 5,
            "dictionary_hits": 40 + i * 10,
            "code_hits": 10 + i * 3,
            "fuzzy_hits": 5 + i * 2,
            "processing_time": 50.0 + i * 10,
            "avg_time": 5.0 + i * 0.5,
            "p95_time": 20.0 + i * 3,
        }))

    d = AnalyticsDashboard()

    with patch("pathlib.Path") as mock_path_cls, \
         patch.object(st, "markdown") as mock_md, \
         patch.object(st, "caption") as mock_cap, \
         patch.object(st, "line_chart") as mock_line, \
         patch.object(st, "bar_chart") as mock_bar:
        mock_path = MagicMock()
        mock_path_cls.return_value = mock_path
        mock_path.is_dir.return_value = True
        mock_path.iterdir.side_effect = lambda: list(vdir.iterdir())
        result = d._render_history()
        assert result is None
        assert mock_line.call_count >= 2
        assert mock_bar.call_count >= 1


def test_build_coverage_export_returns_bytes():
    d = AnalyticsDashboard()
    result = d._build_coverage_export()
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_learning_export_returns_none_on_error():
    from unittest.mock import patch

    d = AnalyticsDashboard()
    with patch("analytics.learning_dashboard.LearningDashboard", side_effect=ImportError):
        result = d._build_learning_export()
        assert result is None


def test_build_benchmark_export_returns_none_no_session():
    d = AnalyticsDashboard()
    result = d._build_benchmark_export()
    assert result is None


def test_build_unclassified_export_returns_none_no_session():
    d = AnalyticsDashboard()
    result = d._build_unclassified_export()
    assert result is None


def test_render_exports_shows_buttons():
    import streamlit as st
    from unittest.mock import patch, MagicMock

    d = AnalyticsDashboard()

    with patch.object(st, "markdown") as mock_md, \
         patch.object(st, "columns") as mock_cols, \
         patch.object(st, "download_button") as mock_dl:
        mock_cols.side_effect = lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, (list, tuple)) else spec)]
        result = d._render_exports()
        assert result is None
        assert mock_dl.call_count >= 1


def test_analytics_dashboard_render_kpis_uses_provided_metrics():
    import streamlit as st
    from unittest.mock import patch

    metrics = {
        "total_documents": 88, "pdf_count": 84, "excel_count": 4,
        "accounts_total": 5369, "accounts_classified": 1335,
        "accounts_unclassified": 4034, "learning_hits": 884,
        "processing_time": 650.846, "avg_time": 7.396,
    }
    d = AnalyticsDashboard(metrics=metrics)

    with patch.object(st, "columns") as mock_cols, \
         patch.object(st, "metric") as mock_metric, \
         patch.object(st, "caption") as mock_caption:
        mock_cols.return_value = [st] * 6
        result = d._render_kpis()
        assert result is None
        assert d._metrics is metrics


def test_analytics_dashboard_has_docstrings():
    d = AnalyticsDashboard()
    all_methods = ["render"] + [
        "_render_header", "_render_kpis", "_render_coverage",
        "_render_gold_standard", "_render_learning", "_render_unclassified",
        "_render_benchmark", "_render_history", "_render_exports",
    ]
    for name in all_methods:
        method = getattr(d, name)
        assert method.__doc__, f"Missing docstring on {name}"
        assert len(method.__doc__.strip()) > 0, f"Empty docstring on {name}"

# ═══════════════════════════════════════════
# app_validacion.py integration
# ═══════════════════════════════════════════


def test_analytics_dashboard_importable_from_app():
    from analytics.dashboard import AnalyticsDashboard
    d = AnalyticsDashboard()
    assert d is not None


def test_analytics_dashboard_render_does_not_raise():
    d = AnalyticsDashboard()
    try:
        d.render()
    except Exception as exc:
        assert False, f"render() raised {type(exc).__name__}: {exc}"
