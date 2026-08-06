from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from parser_quality_common import (  # noqa: E402
    coverage,
    count_by_type,
    load_dataset,
    load_findings,
    per_file_findings,
    timing,
)
from parser_quality_compare import generar_diff  # noqa: E402
from parser_quality_gate import evaluar  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

DATASET_HEADER = [
    "archivo", "grupo", "n_cuentas", "cuentas_con_codigo",
    "cuentas_con_monto", "totales_detectados", "tiempo_extraccion_ms",
    "tiempo_total_ms", "errores",
]
FINDINGS_HEADER = ["archivo", "grupo", "tipo", "linea", "codigo", "nombre", "raw"]


def _wcsv(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _make_run(root: Path, name: str, dataset, findings) -> Path:
    d = root / name
    _wcsv(d / "parser_quality_dataset.csv", DATASET_HEADER, dataset)
    _wcsv(d / "parser_quality_findings.csv", FINDINGS_HEADER, findings)
    return d


@pytest.fixture
def runs(tmp_path: Path):
    base = _make_run(tmp_path, "base", [
        ["A.pdf", "HOLDOUT", 100, 80, 60, 5, 1000, 1000, 0],
        ["B.pdf", "HOLDOUT", 50, 40, 30, 2, 2000, 2000, 0],
        ["C.pdf", "HOLDOUT", 30, 20, 10, 1, 500, 500, 0],
    ], [
        ["A.pdf", "HOLDOUT", "SIMBOLO_RESIDUAL", 1, "", "x $", ""],
        ["A.pdf", "HOLDOUT", "HEADER_GHOST", 2, "", "RUT", ""],
        ["B.pdf", "HOLDOUT", "CODIGO_PERDIDO", 1, "", "y", ""],
    ])
    # Regresión: tipo nuevo por archivo, PDF crítico nuevo, dominio crece,
    # cobertura baja, un tipo sube.
    bad = _make_run(tmp_path, "bad", [
        ["A.pdf", "HOLDOUT", 100, 85, 60, 5, 900, 900, 0],
        ["B.pdf", "HOLDOUT", 50, 40, 30, 2, 2100, 2100, 0],
        ["C.pdf", "HOLDOUT", 30, 20, 10, 1, 500, 500, 0],
        ["D.pdf", "HOLDOUT", 10, 0, 0, 0, 400, 400, 1],
    ], [
        ["A.pdf", "HOLDOUT", "SIMBOLO_RESIDUAL", 1, "", "x $", ""],
        ["B.pdf", "HOLDOUT", "CODIGO_PERDIDO", 1, "", "y", ""],
        ["B.pdf", "HOLDOUT", "MONTO_PARTIDO", 2, "", "z", "3 .000"],
        ["D.pdf", "HOLDOUT", "ERROR_OCR", 0, "", "Ã", ""],
    ])
    # Mejora limpia: mismo dominio, sin tipo que suba, cobertura sube.
    good = _make_run(tmp_path, "good", [
        ["A.pdf", "HOLDOUT", 100, 85, 65, 5, 900, 900, 0],
        ["B.pdf", "HOLDOUT", 50, 40, 30, 2, 1800, 1800, 0],
        ["C.pdf", "HOLDOUT", 30, 20, 10, 1, 500, 500, 0],
    ], [
        ["A.pdf", "HOLDOUT", "SIMBOLO_RESIDUAL", 1, "", "x $", ""],
        ["B.pdf", "HOLDOUT", "CODIGO_PERDIDO", 1, "", "y", ""],
    ])
    return base, bad, good


# ─────────────────────────────────────────────────────────────────────────────
# parser_quality_common
# ─────────────────────────────────────────────────────────────────────────────

def test_load_dataset(runs):
    base, _, _ = runs
    ds = load_dataset(base)
    assert set(ds) == {"A.pdf", "B.pdf", "C.pdf"}
    assert ds["A.pdf"]["n_cuentas"] == "100"


def test_load_findings(runs):
    base, _, _ = runs
    f = load_findings(base)
    assert len(f) == 3
    assert count_by_type(f)["SIMBOLO_RESIDUAL"] == 1


def test_per_file_findings(runs):
    base, _, _ = runs
    f = load_findings(base)
    assert per_file_findings(f)["A.pdf"] == 2


def test_coverage(runs):
    base, _, _ = runs
    cov = coverage(list(load_dataset(base).values()))
    assert cov["cuentas"] == 180
    assert cov["pct_con_codigo"] == pytest.approx(140 / 180 * 100)
    assert cov["cobertura_combinada"] == pytest.approx(
        (cov["pct_con_codigo"] + cov["pct_con_monto"]) / 2
    )


def test_timing(runs):
    base, _, _ = runs
    t = timing(list(load_dataset(base).values()))
    assert t["total_ms"] == 3500
    assert t["promedio_ms"] == pytest.approx(3500 / 3)
    assert t["mediana_ms"] == 1000


# ─────────────────────────────────────────────────────────────────────────────
# parser_quality_compare
# ─────────────────────────────────────────────────────────────────────────────

def test_diff_contains_sections(runs):
    base, bad, _ = runs
    md = generar_diff(base, bad)
    for seccion in [
        "Variación por tipo de error",
        "PDFs mejorados",
        "PDFs empeorados",
        "Variación por PDF",
        "Cobertura acumulada (Pareto) — antes",
        "Cobertura acumulada (Pareto) — después",
        "Top 10",
        "Tiempo",
    ]:
        assert seccion in md


def test_diff_detects_improvements(runs):
    base, _, good = runs
    md = generar_diff(base, good)
    assert "PDFs mejorados" in md
    # A bajó de 2 hallazgos a 1
    assert "A.pdf" in md


# ─────────────────────────────────────────────────────────────────────────────
# parser_quality_gate
# ─────────────────────────────────────────────────────────────────────────────

def test_gate_fails_on_regression(runs):
    base, bad, _ = runs
    res = evaluar(base, bad)
    assert not res.ok
    msgs = "\n".join(res.fallos)
    for cond in ["TIPOS_SUBEN", "COBERTURA_BAJA", "NUEVOS_PDFS_CRITICOS",
                 "BENCHMARK_CAMBIADO", "NUEVAS_REGRESIONES"]:
        assert cond in msgs, f"falta condición {cond} en:\n{msgs}"


def test_gate_passes_on_clean_improvement(runs):
    base, _, good = runs
    res = evaluar(base, good)
    assert res.ok
    assert len(res.fallos) == 0


def test_gate_detects_benchmark_change(runs, tmp_path):
    base, bad, _ = runs
    # bad tiene dominio distinto (aparece D.pdf) -> BENCHMARK_CAMBIADO
    res = evaluar(base, bad)
    assert any("BENCHMARK_CAMBIADO" in f for f in res.fallos)


def test_gate_benchmark_hash(runs, tmp_path):
    base, _, good = runs
    a = tmp_path / "b1.json"
    b = tmp_path / "b2.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{1}", encoding="utf-8")
    res = evaluar(base, good, benchmark_baseline=a, benchmark_current=b)
    assert any("BENCHMARK_CAMBIADO" in f for f in res.fallos)


# ─────────────────────────────────────────────────────────────────────────────
# CLI exit codes
# ─────────────────────────────────────────────────────────────────────────────

def test_gate_cli_pass(runs):
    base, _, good = runs
    r = subprocess.run(
        [sys.executable, str(REPO / "tools" / "parser_quality_gate.py"),
         "--baseline", str(base), "--current", str(good)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert "RESULTADO: PASS" in r.stdout


def test_gate_cli_fail(runs):
    base, bad, _ = runs
    r = subprocess.run(
        [sys.executable, str(REPO / "tools" / "parser_quality_gate.py"),
         "--baseline", str(base), "--current", str(bad)],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "RESULTADO: FAIL" in r.stdout


def test_compare_cli(runs, tmp_path):
    base, _, good = runs
    out = tmp_path / "diff.md"
    r = subprocess.run(
        [sys.executable, str(REPO / "tools" / "parser_quality_compare.py"),
         "--baseline", str(base), "--current", str(good), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    assert out.exists()
    assert "Variación por tipo de error" in out.read_text(encoding="utf-8")