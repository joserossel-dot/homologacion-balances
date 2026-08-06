#!/usr/bin/env python3
"""parser_quality_compare.py — Compara dos ejecuciones del Parser Quality Program.

Compara los CSV de dos auditorías:
  - parser_quality_dataset.csv
  - parser_quality_findings.csv

y genera reports/parser_quality/parser_quality_diff.md con:

  - variación por tipo de error
  - variación por PDF (mejorados / empeorados)
  - cobertura acumulada (Pareto)
  - tiempo promedio / total
  - Pareto antes / después

Uso:
    python3 tools/parser_quality_compare.py \
        --baseline DIR_BASE \
        --current  DIR_NUEVO \
        [-o reports/parser_quality/parser_quality_diff.md]

SOLO MEDICIÓN: no modifica parser_universal.py, extractores, Learning ni Runtime.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser_quality_common import (  # noqa: E402
    coverage,
    count_by_type,
    load_dataset,
    load_findings,
    per_file_findings,
    timing,
)

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_DIR / "reports" / "parser_quality" / "parser_quality_diff.md"


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo
# ─────────────────────────────────────────────────────────────────────────────

def _dif_tipos(b: Counter, c: Counter) -> list[dict]:
    out = []
    for t in sorted(set(b) | set(c)):
        bv, cv = b.get(t, 0), c.get(t, 0)
        out.append({"tipo": t, "base": bv, "current": cv, "delta": cv - bv})
    return sorted(out, key=lambda r: -abs(r["delta"]))


def _movidos(b_find, c_find) -> list[tuple[str, int, int]]:
    bf = per_file_findings(b_find)
    cf = per_file_findings(c_find)
    mov = []
    for p in sorted(set(bf) | set(cf)):
        b, c = bf.get(p, 0), cf.get(p, 0)
        if b != c:
            mov.append((p, b, c))
    return sorted(mov, key=lambda t: -(t[2] - t[1]))


def _pareto(cnt: Counter) -> list[tuple[str, int, float]]:
    items = sorted(cnt.items(), key=lambda x: -x[1])
    total = sum(n for _, n in items) or 1
    acum = 0.0
    res = []
    for t, n in items:
        acum += n / total * 100
        res.append((t, n, acum))
    return res


def _top95(par: list[tuple[str, int, float]]) -> list[list]:
    total = sum(n for _, n, _ in par) or 1
    out = []
    accum = 0.0
    for t, n, a in par:
        accum += n / total * 100
        out.append([t, n, f"{n / total * 100:.1f}%", f"{accum:.1f}%"])
        if accum >= 95.0:
            break
    return out


def _sig(delta: int, base: int) -> str:
    if delta == 0:
        return "0"
    if base == 0:
        return "nuevo"
    return f"{delta:+d} ({delta / base * 100:+.1f}%)"


# ─────────────────────────────────────────────────────────────────────────────
# Markdown
# ─────────────────────────────────────────────────────────────────────────────

def _md(titulo: str, header: list[str], filas: list[list]) -> list[str]:
    ncols = len(header)
    sep = "|---" * ncols + "|"
    out = ["", f"### {titulo}", "", "| " + " | ".join(header) + " |", sep]
    for r in filas:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    out.append("")
    return out


def generar_diff(baseline_dir: Path, current_dir: Path, nota: str = "",
                 baseline_dataset: str = "parser_quality_dataset.csv",
                 baseline_findings: str = "parser_quality_findings.csv",
                 current_dataset: str = "parser_quality_dataset.csv",
                 current_findings: str = "parser_quality_findings.csv") -> str:
    b_dataset = load_dataset(baseline_dir, baseline_dataset)
    c_dataset = load_dataset(current_dir, current_dataset)
    b_find = load_findings(baseline_dir, baseline_findings)
    c_find = load_findings(current_dir, current_findings)
    b_rows = list(b_dataset.values())
    c_rows = list(c_dataset.values())

    b_types, c_types = count_by_type(b_find), count_by_type(c_find)
    b_cov, c_cov = coverage(b_rows), coverage(c_rows)
    b_t, c_t = timing(b_rows), timing(c_rows)
    b_par, c_par = _pareto(b_types), _pareto(c_types)
    dif_tipos = _dif_tipos(b_types, c_types)
    mov = _movidos(b_find, c_find)

    L: list[str] = [
        "# Parser Quality — Diff de auditoría", "",
        f"**Baseline:** `{baseline_dir}` ({len(b_rows)} docs)", "",
        f"**Current:** `{current_dir}` ({len(c_rows)} docs)", "",
        f"**Fecha:** {time.strftime('%Y-%m-%d %H:%M')}", "",
    ]
    if nota:
        L += ["> " + nota.replace("\n", " "), ""]

    L += _md("Variación por tipo de error",
             ["Tipo", "Baseline", "Current", "Variación"],
             [[r["tipo"], r["base"], r["current"], _sig(r["delta"], r["base"])] for r in dif_tipos])

    L += _md("PDFs mejorados (menos hallazgos)",
             ["Archivo", "Baseline", "Current"],
             [[p, b, c] for p, b, c in mov if c < b])

    L += _md("PDFs empeorados (más hallazgos)",
             ["Archivo", "Baseline", "Current"],
             [[p, b, c] for p, b, c in mov if c > b])

    L += _md("Variación por PDF (solo con cambio)",
             ["Archivo", "Baseline", "Current", "Variación"],
             [[p, b, c, _sig(c - b, b)] for p, b, c in mov])

    L += _md("Cobertura acumulada (Pareto) — antes",
             ["Problema", "Conteo", "Acumulado"],
             [[t, n, f"{a:.1f}%"] for t, n, a in b_par])

    L += _md("Cobertura acumulada (Pareto) — después",
             ["Problema", "Conteo", "Acumulado"],
             [[t, n, f"{a:.1f}%"] for t, n, a in c_par])

    L += _md("Top 10 → 95% (después)",
             ["Problema", "Conteo", "%", "Acumulado"],
             _top95(c_par))

    L += _md("Tiempo (s)",
             ["Métrica", "Baseline", "Current"],
             [
                 ["Promedio", f"{b_t['promedio_ms'] / 1000:.1f}", f"{c_t['promedio_ms'] / 1000:.1f}"],
                 ["Mediana", f"{(b_t['mediana_ms'] or 0) / 1000:.1f}", f"{(c_t['mediana_ms'] or 0) / 1000:.1f}"],
                 ["Total", f"{b_t['total_ms'] / 1000:.1f}", f"{c_t['total_ms'] / 1000:.1f}"],
             ])

    L += [
        "## Notas de cobertura", "",
        f"- **Baseline:** código {b_cov['pct_con_codigo']:.1f}% | monto {b_cov['pct_con_monto']:.1f}% | combinada {b_cov['cobertura_combinada']:.1f}%",
        f"- **Current:**  código {c_cov['pct_con_codigo']:.1f}% | monto {c_cov['pct_con_monto']:.1f}% | combinada {c_cov['cobertura_combinada']:.1f}%",
        "",
    ]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Compara dos ejecuciones del Parser Quality Program")
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--current", required=True, type=Path)
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--nota", type=str, default="",
                    help="nota de encabezado (p.ej. 'Baseline inicial (sin comparación previa).')")
    ap.add_argument("--baseline-dataset", type=str, default="parser_quality_dataset.csv")
    ap.add_argument("--baseline-findings", type=str, default="parser_quality_findings.csv")
    ap.add_argument("--current-dataset", type=str, default="parser_quality_dataset.csv")
    ap.add_argument("--current-findings", type=str, default="parser_quality_findings.csv")
    args = ap.parse_args()

    md = generar_diff(args.baseline, args.current, nota=args.nota,
                      baseline_dataset=args.baseline_dataset,
                      baseline_findings=args.baseline_findings,
                      current_dataset=args.current_dataset,
                      current_findings=args.current_findings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md + "\n", encoding="utf-8")
    print(f"Diff generado: {args.out}")


if __name__ == "__main__":
    main()