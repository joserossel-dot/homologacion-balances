#!/usr/bin/env python3
"""freeze_pq0.py — Cierra oficialmente el Baseline PQ-0 del Parser Quality Program.

Espera a que la auditoría de los 608 PDFs termine y congela el estado inicial:

  FASE 1  Copia los resultados a reports/parser_quality/baselines/PQ0_*
          (dataset, findings, report, pareto). Inmutables a partir de aquí.
  FASE 2  tools/parser_quality_compare.py  (PQ0 vs auditoría actual,
          nota "Baseline inicial (sin comparación previa).")
  FASE 3  tools/parser_quality_gate.py     (registra PASS inicial)
          -> reports/parser_quality/PQ0_gate.md
  FASE 4  reports/parser_quality/PARSER_BASELINE.md  (metadata completa)
  FASE 5  reports/parser_quality/HISTORY.md  (entrada PQ-0 acumulativa)

No modifica parser, Runtime, Learning ni benchmark.
Uso:
    python3 reports/parser_quality/freeze_pq0.py [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PQ_DIR = Path(__file__).resolve().parent
BASELINES = PQ_DIR / "baselines"
CHECKPOINT = PQ_DIR / "_parser_quality_checkpoint.json"

sys.path.insert(0, str(REPO / "tools"))

from parser_quality_common import (  # noqa: E402
    coverage,
    count_by_type,
    load_dataset,
    load_findings,
    timing,
)

TOTAL_PDFS = 608
POLL_SECONDS = 30
NOTA_INICIAL = "Baseline inicial (sin comparación previa)."


# ─────────────────────────────────────────────────────────────────────────────
# Espera de la auditoría
# ─────────────────────────────────────────────────────────────────────────────

def _checkpoint_rows() -> int:
    try:
        d = json.load(open(CHECKPOINT, encoding="utf-8"))
        return len(d.get("rows", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return 0


def _audit_running() -> bool:
    try:
        out = subprocess.run(["pgrep", "-f", "audit_parser_quality"],
                             capture_output=True, text=True)
        return out.returncode == 0
    except FileNotFoundError:
        return True  # sin pgrep, asumir vivo


def esperar_auditoria(tiempo_max: float = 6 * 3600) -> bool:
    t0 = time.time()
    while time.time() - t0 < tiempo_max:
        rows = _checkpoint_rows()
        terminado = rows >= TOTAL_PDFS and not _audit_running()
        print(f"  audit: {rows}/{TOTAL_PDFS} PDFs, corriendo={_audit_running()}")
        if terminado:
            time.sleep(5)  # margen para la escritura final de reportes
            return True
        time.sleep(POLL_SECONDS)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# FASE 1 — congelar baseline
# ─────────────────────────────────────────────────────────────────────────────

def congelar_baseline() -> Path:
    BASELINES.mkdir(parents=True, exist_ok=True)
    b = BASELINES / "PQ0"
    b.mkdir(exist_ok=True)
    mapeo = {
        "parser_quality_dataset.csv": "PQ0_dataset.csv",
        "parser_quality_findings.csv": "PQ0_findings.csv",
        "parser_quality_report.md": "PQ0_report.md",
        "parser_quality_pareto.md": "PQ0_pareto.md",
    }
    for src, dst in mapeo.items():
        shutil.copy2(PQ_DIR / src, b / dst)
    # prueba de inmutabilidad inicial: snapshot de hashes
    hashes = {}
    for _, dst in mapeo.items():
        hashes[dst] = _sha(b / dst)
    (b / "_PQ0_hashes.json").write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  baseline congelado en: {b}")
    return b


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# FASE 2 — diff inicial
# ─────────────────────────────────────────────────────────────────────────────

def generar_diff(baseline: Path) -> Path:
    out = PQ_DIR / "parser_quality_diff.md"
    cmd = [sys.executable, str(REPO / "tools" / "parser_quality_compare.py"),
           "--baseline", str(baseline), "--current", str(PQ_DIR),
           "-o", str(out), "--nota", NOTA_INICIAL,
           "--baseline-dataset", "PQ0_dataset.csv",
           "--baseline-findings", "PQ0_findings.csv"]
    subprocess.run(cmd, check=True)
    print(f"  diff -> {out}")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# FASE 3 — gate inicial
# ─────────────────────────────────────────────────────────────────────────────

def generar_gate(baseline: Path) -> Path:
    out = PQ_DIR / "PQ0_gate.md"
    cmd = [sys.executable, str(REPO / "tools" / "parser_quality_gate.py"),
           "--baseline", str(baseline), "--current", str(PQ_DIR),
           "--baseline-dataset", "PQ0_dataset.csv",
           "--baseline-findings", "PQ0_findings.csv"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    salida = r.stdout or r.stderr
    estado = "PASS" if "RESULTADO: PASS" in salida else "FAIL"
    texto = [
        "# PQ-0 — Quality Gate (estado inicial)", "",
        f"**Resultado:** {estado}", "",
        "```",
        salida.strip(),
        "```",
        "",
    ]
    out.write_text("\n".join(texto) + "\n", encoding="utf-8")
    print(f"  gate -> {out} ({estado})")
    return out


# ─────────────────────────────────────────────────────────────────────────────
# FASE 4 — PARSER_BASELINE.md
# ─────────────────────────────────────────────────────────────────────────────

def commit_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, cwd=REPO).stdout.strip()
    except Exception:
        return "desconocido"


def metadata() -> dict:
    ds = load_dataset(PQ_DIR)
    fd = load_findings(PQ_DIR)
    rows = list(ds.values())
    cov = coverage(rows)
    tim = timing(rows)
    por_tipo = count_by_type(fd)
    pareto = sorted(por_tipo.items(), key=lambda x: -x[1])
    total_find = sum(n for _, n in pareto)
    acum = 0.0
    par = []
    for t, n in pareto:
        acum += n / total_find * 100 if total_find else 0
        par.append((t, n, acum))

    bench_dir = REPO / "benchmark"
    bench_files = {}
    for f in ("dataset_manifest.csv", "benchmark_results.csv", "benchmark_summary.md"):
        p = bench_dir / f
        if p.exists():
            bench_files[f] = _sha(p)

    return {
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "commit": commit_sha(),
        "pdfs": len(rows),
        "total_hallazgos": total_find,
        "por_tipo": por_tipo,
        "pareto": par,
        "cobertura": cov,
        "tiempos": tim,
        "benchmark": bench_files,
        "version_parser": "no semver (identificado por commit SHA)",
        "version_runtime": "gold_standard/runtime_manager.py RUNTIME_SCHEMA_VERSION=1.0",
        "version_learning": "no semver (identificado por commit SHA)",
        "paquete": "carpeta-tributaria 0.1.0 (pyproject.toml)",
    }


def escribir_baseline_doc(m: dict) -> Path:
    path = PQ_DIR / "PARSER_BASELINE.md"
    par = m["pareto"]
    cov, tim = m["cobertura"], m["tiempos"]
    L = [
        "# PARSER BASELINE — PQ-0", "",
        "Baseline oficial del Parser Quality Program. Estado inicial del proyecto.", "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Fecha | {m['fecha']} |",
        f"| Commit SHA | `{m['commit']}` |",
        f"| Cantidad de PDFs | {m['pdfs']} |",
        f"| Total de hallazgos | {m['total_hallazgos']} |",
        "",
        "## Distribución Pareto", "",
        "| Problema | Conteo | % | Acumulado % |",
        "|---|---|---|---|",
    ]
    total = m["total_hallazgos"] or 1
    for t, n, a in par:
        L.append(f"| {t} | {n} | {n/total*100:.1f}% | {a:.1f}% |")
    L += [
        "", "## Cobertura acumulada", "",
        f"- Código: {cov['pct_con_codigo']:.1f}% | Monto: {cov['pct_con_monto']:.1f}% | Combinada: {cov['cobertura_combinada']:.1f}%",
        "",
        "## Tiempos", "",
        f"- Promedio: {tim['promedio_ms']/1000:.1f}s | Mediana: {(tim['mediana_ms'] or 0)/1000:.1f}s | Total: {tim['total_ms']/1000:.1f}s",
        "",
        "## Benchmark congelado", "",
        "| Archivo | SHA256 |",
        "|---|---|",
    ]
    for f, h in m["benchmark"].items():
        L.append(f"| `{f}` | `{h[:16]}…` |")
    L += [
        "", "## Versiones", "",
        f"- Parser: {m['version_parser']}",
        f"- Runtime: {m['version_runtime']}",
        f"- Learning: {m['version_learning']}",
        f"- Paquete: {m['paquete']}",
        "", "> Estos archivos son inmutables. NO deben volver a modificarse.",
        "",
    ]
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"  baseline doc -> {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# FASE 5 — HISTORY.md
# ─────────────────────────────────────────────────────────────────────────────

def escribir_history(m: dict) -> Path:
    path = PQ_DIR / "HISTORY.md"
    if path.exists():
        historial = path.read_text(encoding="utf-8")
    else:
        historial = "# Parser Quality — Historial de baselines y sprints\n\n"
    if "PQ-0" in historial:
        return path  # ya registrado

    por_tipo = sorted(m["por_tipo"].items(), key=lambda x: -x[1])
    top = ", ".join(f"{t} ({n})" for t, n in por_tipo[:5])
    cov = m["cobertura"]
    entrada = f"""## PQ-0 (baseline inicial)

- **Fecha:** {m['fecha']}
- **Commit:** `{m['commit']}`
- **Cantidad de PDFs:** {m['pdfs']}
- **Principales problemas:** {top or 'sin hallazgos'}
- **Cobertura:** código {cov['pct_con_codigo']:.1f}% | monto {cov['pct_con_monto']:.1f}% | combinada {cov['cobertura_combinada']:.1f}%
- **Total hallazgos:** {m['total_hallazgos']}
- **Observaciones:** Congelamiento oficial del estado inicial. Sin comparación previa.

---
"""
    historial = historial.rstrip() + "\n\n" + entrada
    path.write_text(historial, encoding="utf-8")
    print(f"  history -> {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Congela el Baseline PQ-0")
    ap.add_argument("--force", action="store_true",
                    help="no esperar a la auditoría (para pruebas)")
    args = ap.parse_args()

    if not args.force:
        print("Esperando que la auditoría de 608 PDFs termine...")
        if not esperar_auditoria():
            print("ERROR: la auditoría no terminó en el tiempo máximo")
            sys.exit(1)

    print("FASE 1 — congelando baseline PQ-0")
    baseline = congelar_baseline()

    print("FASE 2 — diff inicial")
    generar_diff(baseline)

    print("FASE 3 — quality gate")
    generar_gate(baseline)

    print("FASE 4 — PARSER_BASELINE.md")
    m = metadata()
    escribir_baseline_doc(m)

    print("FASE 5 — HISTORY.md")
    escribir_history(m)

    print("\nBaseline PQ-0 CERRADO. Archivos inmutables en baselines/PQ0/.")


if __name__ == "__main__":
    main()