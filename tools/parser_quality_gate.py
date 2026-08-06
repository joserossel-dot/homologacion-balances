#!/usr/bin/env python3
"""parser_quality_gate.py — Quality Gate del Parser Quality Program.

Compara la ejecución "current" contra una "baseline" y FALLA en cualquiera de:

  1. AUMENTA cualquier tipo de error.
  2. DISMINUYE la cobertura de extracción.
  3. Aparecen NUEVOS PDFs con errores críticos (procesados con errores).
  4. CAMBIA el benchmark congelado (conjunto de PDFs del dominio distinto
     y/o el archivo de resultados del benchmark difiere de la referencia).
  5. Aparecen NUEVAS regresiones (un tipo de problema que antes no existía
     en un PDF aparece en la ejecución actual).

Salida:
    PASS   -> exit 0
    FAIL   -> exit 1, indicando exactamente qué condición(es) fallaron.

Uso:
    python3 tools/parser_quality_gate.py \
        --baseline DIR_BASE \
        [--current DIR_ACTUAL]            # default: reports/parser_quality
        [--benchmark-baseline FILE] [--benchmark-current FILE]

SOLO MEDICIÓN: no modifica parser_universal.py, extractores, Learning ni Runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser_quality_common import (  # noqa: E402
    count_by_type,
    coverage,
    load_dataset,
    load_findings,
    per_file_by_type,
)

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CURRENT = REPO_DIR / "reports" / "parser_quality"


class GateResult:
    def __init__(self) -> None:
        self.fallos: list[str] = []
        self.passed: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.fallos


def _marcar(r: GateResult, condicion: str, ok: bool, msg_ok: str, msg_fail: str) -> None:
    if ok:
        r.passed.append(f"[{condicion}] {msg_ok}")
    else:
        r.fallos.append(f"[{condicion}] {msg_fail}")


def _errores(row) -> int:
    try:
        return int(float(row.get("errores", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _criticos(rows) -> set[str]:
    return {r["archivo"] for r in rows if _errores(r) > 0}


def _regresiones(b_find, c_find) -> list[dict]:
    b_per = per_file_by_type(b_find)
    c_per = per_file_by_type(c_find)
    out = []
    for archivo, tipos in c_per.items():
        bt = b_per.get(archivo, Counter())
        for tipo, n in tipos.items():
            if bt.get(tipo, 0) == 0 and n > 0:
                out.append({"archivo": archivo, "tipo": tipo, "n": n})
    return out


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def evaluar(baseline_dir: Path, current_dir: Path,
            benchmark_baseline: Path | None = None,
            benchmark_current: Path | None = None,
            baseline_dataset: str = "parser_quality_dataset.csv",
            baseline_findings: str = "parser_quality_findings.csv",
            current_dataset: str = "parser_quality_dataset.csv",
            current_findings: str = "parser_quality_findings.csv") -> GateResult:
    r = GateResult()

    b_dataset = load_dataset(baseline_dir, baseline_dataset)
    c_dataset = load_dataset(current_dir, current_dataset)
    b_find = load_findings(baseline_dir, baseline_findings)
    c_find = load_findings(current_dir, current_findings)

    b_rows = list(b_dataset.values())
    c_rows = list(c_dataset.values())

    if not b_rows or not c_rows:
        r.fallos.append("[VACIO] baseline o current sin datos")
        return r

    # ── 1. Aumenta cualquier tipo de error ─────────────────────────────────
    b_types, c_types = count_by_type(b_find), count_by_type(c_find)
    subidas = sorted(
        (t, b_types.get(t, 0), c_types.get(t, 0))
        for t in set(c_types)
        if c_types[t] > b_types.get(t, 0)
    )
    _marcar(r, "TIPOS_SUBEN", not subidas,
            "ningún tipo de error aumentó",
            "aumentó al menos un tipo de error")
    for t, b, c in subidas:
        r.fallos.append(f"[TIPOS_SUBEN] {t}: {b} → {c}")

    # ── 2. Disminuye la cobertura ──────────────────────────────────────────
    b_cov, c_cov = coverage(b_rows), coverage(c_rows)
    delta = c_cov["cobertura_combinada"] - b_cov["cobertura_combinada"]
    _marcar(r, "COBERTURA_BAJA", delta >= -1e-9,
            f"cobertura combinada {b_cov['cobertura_combinada']:.1f}% → {c_cov['cobertura_combinada']:.1f}%",
            f"cobertura combinada bajó: {b_cov['cobertura_combinada']:.1f}% → {c_cov['cobertura_combinada']:.1f}%")

    # ── 3. Nuevos PDFs con errores críticos ────────────────────────────────
    bcrit, ccrit = _criticos(b_rows), _criticos(c_rows)
    nuevos = sorted(set(ccrit) - set(bcrit))
    _marcar(r, "NUEVOS_PDFS_CRITICOS", not nuevos,
            "no hay PDFs críticos nuevos",
            "aparecen PDFs con errores críticos nuevos")
    for p in nuevos:
        r.fallos.append(f"[NUEVOS_PDFS_CRITICOS] {p}")

    # ── 4. Cambia el benchmark congelado (dominio) ─────────────────────────
    bset, cset = set(b_dataset), set(c_dataset)
    misma_dominio = bset == cset
    _marcar(r, "BENCHMARK_CAMBIADO", misma_dominio,
            "conjunto de PDFs del dominio idéntico",
            "el conjunto de PDFs del dominio cambió")
    if not misma_dominio:
        r.fallos.append(
            f"[BENCHMARK_CAMBIADO] faltan {len(bset - cset)} / aparecen {len(cset - bset)}"
        )

    if benchmark_baseline and benchmark_current:
        if _hash(benchmark_baseline) != _hash(benchmark_current):
            r.fallos.append("[BENCHMARK_CAMBIADO] benchmark_results difiere del baseline")

    # ── 5. Nuevas regresiones (tipo que era 0 -> ahora >0 por archivo) ─────
    regresiones = _regresiones(b_find, c_find)
    _marcar(r, "NUEVAS_REGRESIONES", not regresiones,
            "no hay regresiones nuevas por archivo",
            "aparecen regresiones nuevas por archivo")
    for det in regresiones[:20]:
        r.fallos.append(f"[REGRESION] {det['archivo']}: {det['tipo']}")

    return r


def main():
    ap = argparse.ArgumentParser(description="Quality Gate del Parser Quality Program")
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    ap.add_argument("--benchmark-baseline", type=Path, default=None)
    ap.add_argument("--benchmark-current", type=Path, default=None)
    ap.add_argument("--baseline-dataset", type=str, default="parser_quality_dataset.csv")
    ap.add_argument("--baseline-findings", type=str, default="parser_quality_findings.csv")
    ap.add_argument("--current-dataset", type=str, default="parser_quality_dataset.csv")
    ap.add_argument("--current-findings", type=str, default="parser_quality_findings.csv")
    args = ap.parse_args()

    try:
        res = evaluar(args.baseline, args.current,
                      args.benchmark_baseline, args.benchmark_current,
                      baseline_dataset=args.baseline_dataset,
                      baseline_findings=args.baseline_findings,
                      current_dataset=args.current_dataset,
                      current_findings=args.current_findings)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    if res.fallos:
        for msg in res.fallos:
            print(f"FAIL: {msg}")
        print("\nRESULTADO: FAIL")
        sys.exit(1)

    for msg in res.passed:
        print(f"PASS: {msg}")
    print("\nRESULTADO: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()