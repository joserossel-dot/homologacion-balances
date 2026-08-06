#!/usr/bin/env python3
"""parser_quality_common.py — Helpers compartidos del Parser Quality Program.

Carga y resume las salidas del auditor (reports/parser_quality):
  - parser_quality_dataset.csv   (una fila por PDF)
  - parser_quality_findings.csv  (una fila por problema detectado)

Utilizado por tools/parser_quality_compare.py (FASE 2) y
tools/parser_quality_gate.py (FASE 3).

SOLO LECTURA: no modifica ninguna lógica del parser.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Optional

DATASET_NAME = "parser_quality_dataset.csv"
FINDINGS_NAME = "parser_quality_findings.csv"

# Columnas de tiempo disponibles (mayor prioridad primero).
TIME_COLS = ("tiempo_total_ms", "tiempo_extraccion_ms", "tiempo_parse_ms")


# ─────────────────────────────────────────────────────────────────────────────
# Carga
# ─────────────────────────────────────────────────────────────────────────────

def _read_dict(path: Path) -> list[dict[str, Any]]:
    rows: list = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("archivo"):
                rows.append(r)
    return rows


def load_dataset(directory: Path, dataset_name: str = DATASET_NAME) -> dict[str, dict[str, Any]]:
    p = directory / dataset_name
    if not p.exists():
        raise FileNotFoundError(f"No existe dataset: {p}")
    rows = _read_dict(p)
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        # Clave única por ruta completa (si existe) para no colapsar PDFs
        # que comparten nombre de archivo en carpetas distintas.
        clave = r.get("path") or r.get("archivo", "")
        if clave:
            out[clave] = r
    return out


def load_findings(directory: Path, findings_name: str = FINDINGS_NAME) -> list[dict[str, Any]]:
    p = directory / findings_name
    if not p.exists():
        raise FileNotFoundError(f"No existe findings: {p}")
    return _read_dict(p)


def _as_int(row: dict, key: str) -> int:
    try:
        return int(float(row.get(key, 0) or 0))
    except (TypeError, ValueError):
        return 0


def _as_float(row: dict, key: str) -> float:
    try:
        return float(row.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Métricas agregadas
# ─────────────────────────────────────────────────────────────────────────────

def count_by_type(findings: list[dict[str, Any]]) -> Counter:
    """Problemas contados por tipo."""
    c: Counter = Counter()
    for f in findings:
        c[f.get("tipo", "DESCONOCIDO")] += 1
    return c


def per_file_findings(findings: list[dict[str, Any]]) -> Counter:
    """Hallazgos por archivo."""
    c: Counter = Counter()
    for f in findings:
        c[f.get("archivo", "")] += 1
    return c


def per_file_by_type(findings: list[dict[str, Any]]) -> dict[str, Counter]:
    """Hallazgos por (archivo -> Counter de tipos)."""
    out: dict[str, Counter] = {}
    for f in findings:
        per = out.setdefault(f.get("archivo", ""), Counter())
        per[f.get("tipo", "DESCONOCIDO")] += 1
    return out


def coverage(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Cobertura de extracción global (% cuentas con código / con monto)."""
    n = sum(_as_int(r, "n_cuentas") for r in rows)
    cc = sum(_as_int(r, "cuentas_con_codigo") for r in rows)
    cm = sum(_as_int(r, "cuentas_con_monto") for r in rows)
    pct_c = (cc / n * 100) if n else 0.0
    pct_m = (cm / n * 100) if n else 0.0
    combined = (pct_c + pct_m) / 2.0
    return {
        "cuentas": n,
        "con_codigo": cc,
        "con_monto": cm,
        "pct_con_codigo": pct_c,
        "pct_con_monto": pct_m,
        "cobertura_combinada": combined,
    }


def timing(rows: list[dict[str, Any]]) -> dict[str, float]:
    vals = []
    for r in rows:
        for key in TIME_COLS:
            v = _as_float(r, key)
            if v:
                vals.append(v)
                break
    n = len(vals)
    return {
        "n": n,
        "total_ms": sum(vals),
        "promedio_ms": (sum(vals) / n) if n else 0.0,
        "mediana_ms": _mediana(vals),
    }


def _mediana(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    m = len(s) // 2
    if len(s) % 2 == 1:
        return s[m]
    return (s[m - 1] + s[m]) / 2.0