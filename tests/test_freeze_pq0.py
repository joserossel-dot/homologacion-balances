from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "reports" / "parser_quality"))
sys.path.insert(0, str(REPO / "tools"))

import freeze_pq0  # noqa: E402

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


def _preparar_pq_dir(tmp: Path) -> Path:
    pq = tmp / "parser_quality"
    pq.mkdir(parents=True)
    _wcsv(pq / "parser_quality_dataset.csv", DATASET_HEADER, [
        ["A.pdf", "HOLDOUT", 100, 80, 60, 5, 1000, 1000, 0],
        ["B.pdf", "HOLDOUT", 50, 40, 30, 2, 2000, 2000, 0],
    ])
    _wcsv(pq / "parser_quality_findings.csv", FINDINGS_HEADER, [
        ["A.pdf", "HOLDOUT", "SIMBOLO_RESIDUAL", 1, "", "x $", ""],
        ["A.pdf", "HOLDOUT", "HEADER_GHOST", 2, "", "RUT", ""],
        ["B.pdf", "HOLDOUT", "CODIGO_PERDIDO", 1, "", "y", ""],
    ])
    (pq / "parser_quality_report.md").write_text("# report\n", encoding="utf-8")
    (pq / "parser_quality_pareto.md").write_text("# pareto\n", encoding="utf-8")
    return pq


def test_congelar_baseline(monkeypatch, tmp_path):
    pq = _preparar_pq_dir(tmp_path)
    monkeypatch.setattr(freeze_pq0, "PQ_DIR", pq)
    monkeypatch.setattr(freeze_pq0, "REPO", REPO)
    monkeypatch.setattr(freeze_pq0, "BASELINES", pq / "baselines")
    b = freeze_pq0.congelar_baseline()
    for f in ("PQ0_dataset.csv", "PQ0_findings.csv", "PQ0_report.md", "PQ0_pareto.md"):
        assert (b / f).exists()
    assert (b / "_PQ0_hashes.json").exists()


def test_generar_diff(monkeypatch, tmp_path, capsys):
    pq = _preparar_pq_dir(tmp_path)
    monkeypatch.setattr(freeze_pq0, "PQ_DIR", pq)
    monkeypatch.setattr(freeze_pq0, "REPO", REPO)
    monkeypatch.setattr(freeze_pq0, "BASELINES", pq / "baselines")
    b = freeze_pq0.congelar_baseline()
    out = freeze_pq0.generar_diff(b)
    txt = out.read_text(encoding="utf-8")
    assert "Baseline inicial (sin comparación previa)" in txt


def test_generar_gate(monkeypatch, tmp_path):
    pq = _preparar_pq_dir(tmp_path)
    monkeypatch.setattr(freeze_pq0, "PQ_DIR", pq)
    monkeypatch.setattr(freeze_pq0, "REPO", REPO)
    monkeypatch.setattr(freeze_pq0, "BASELINES", pq / "baselines")
    b = freeze_pq0.congelar_baseline()
    out = freeze_pq0.generar_gate(b)
    assert out.exists()
    assert "Resultado:** PASS" in out.read_text(encoding="utf-8")


def test_metadata_y_docs(monkeypatch, tmp_path):
    pq = _preparar_pq_dir(tmp_path)
    monkeypatch.setattr(freeze_pq0, "PQ_DIR", pq)
    monkeypatch.setattr(freeze_pq0, "REPO", REPO)
    m = freeze_pq0.metadata()
    assert m["pdfs"] == 2
    assert m["total_hallazgos"] == 3
    doc = freeze_pq0.escribir_baseline_doc(m)
    assert "PARSER BASELINE" in doc.read_text(encoding="utf-8")
    hist = freeze_pq0.escribir_history(m)
    txt = hist.read_text(encoding="utf-8")
    assert "## PQ-0 (baseline inicial)" in txt
    # idempotente: no registra dos veces
    freeze_pq0.escribir_history(m)
    assert txt.count("## PQ-0") == 1