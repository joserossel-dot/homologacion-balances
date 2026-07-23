#!/usr/bin/env python3
"""STRESS TEST: Parser v1 vs Parser Core 2.0 en TODOS los documentos.

Busca sistemáticamente diferencias.  No modifica código.  No corrige nada.

Salida en reports/parser_stress_test/:
  parser_stress_test.xlsx       — resultados por documento
  differences.xlsx              — solo documentos con diferencias
  false_positive_cases.xlsx     — casos donde v1 falló pero v2 acertó
  candidate_improvements.xlsx   — oportunidades de mejora
  parser_stress_test.md         — reporte completo
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("stress_test")

OUTPUT_DIR = Path("reports/parser_stress_test")
TIMEOUT_SECONDS = 120  # por documento


@dataclass
class ComparisonResult:
    file_name: str
    group: str
    file_type: str  # pdf | xlsx | xls

    # Cuentas
    v1_accounts: int
    v2_accounts: int
    accounts_match: bool

    # Diferencias detalladas
    only_in_v1: int
    only_in_v2: int
    name_diffs: int
    code_diffs: int
    amount_diffs: int
    column_diffs: int

    # Tiempos
    v1_time_seconds: float
    v2_time_seconds: float

    # Detección
    v1_format: str
    v2_format: str
    v1_separator: str
    v2_separator: str
    v1_used_ocr: bool
    v2_used_ocr: bool

    # Layout detection (v2 only)
    layout_columns: str
    layout_confidence: float
    layout_source: str

    # DocumentAssessment (precomputado)
    da_parser_confidence: float
    da_layout_confidence: float
    da_ocr_confidence: float
    da_contamination_rate: float
    da_header_quality: float

    # Diferencia clasificada
    verdict: str = ""  # BUG_V1 | BUG_V2 | TIE | INDETERMINATE | TIMEOUT
    verdict_reason: str = ""
    details: str = ""


def _make_key(a) -> tuple:
    if hasattr(a, "line"):
        amt = round(a.amount or 0, 2)
        return (a.line, a.name, amt)
    amt = round((a.monto or 0), 2)
    return (a.linea, a.nombre, amt)


def _name_key(a) -> tuple:
    n = a.name if hasattr(a, "name") else a.nombre
    return n.strip().lower()


def _col_str(a) -> str:
    if hasattr(a, "column_origin"):
        return a.column_origin
    return a.origen_columna.value if a.origen_columna else "?"


def _compare_accounts(v1_list, v2_list) -> dict:
    """Compara dos listas de cuentas y retorna estadísticas de diferencias."""
    keys1 = {_make_key(c): c for c in v1_list}
    keys2 = {_make_key(c): c for c in v2_list}

    shared_keys = set(keys1.keys()) & set(keys2.keys())
    only_v1_keys = set(keys1.keys()) - set(keys2.keys())
    only_v2_keys = set(keys2.keys()) - set(keys1.keys())

    name_diffs = 0
    code_diffs = 0
    amount_diffs = 0
    column_diffs = 0

    for k in shared_keys:
        a1 = keys1[k]
        a2 = keys2[k]

        n1 = a1.name if hasattr(a1, "name") else a1.nombre
        n2 = a2.name if hasattr(a2, "name") else a2.nombre
        if n1.strip().lower() != n2.strip().lower():
            name_diffs += 1

        c1 = a1.code if hasattr(a1, "code") else a1.codigo
        c2 = a2.code if hasattr(a2, "code") else a2.codigo
        if (c1 or "") != (c2 or ""):
            code_diffs += 1

        amt1 = a1.amount if hasattr(a1, "amount") else a1.monto
        amt2 = a2.amount if hasattr(a2, "amount") else a2.monto
        if (amt1 or 0) != (amt2 or 0):
            amount_diffs += 1

        col1 = _col_str(a1)
        col2 = _col_str(a2)
        if col1 != col2:
            column_diffs += 1

    return {
        "only_in_v1": len(only_v1_keys),
        "only_in_v2": len(only_v2_keys),
        "name_diffs": name_diffs,
        "code_diffs": code_diffs,
        "amount_diffs": amount_diffs,
        "column_diffs": column_diffs,
        "accounts_match": (len(only_v1_keys) == 0 and len(only_v2_keys) == 0
                           and name_diffs == 0 and code_diffs == 0
                           and amount_diffs == 0 and column_diffs == 0),
    }


def _classify_verdict(d: ComparisonResult, diff: dict) -> str:
    """Clasifica la diferencia encontrada."""
    if d.v1_accounts == 0 and d.v2_accounts == 0:
        return "TIE", "Ambos devuelven 0 cuentas (documento sin parsear)"
    if d.v1_accounts == d.v2_accounts and diff["accounts_match"]:
        return "TIE", "Resultados idénticos"

    # Timeout cases
    if d.v1_time_seconds >= TIMEOUT_SECONDS * 0.9:
        return "TIMEOUT", "Parser v1 excedió timeout"
    if d.v2_time_seconds >= TIMEOUT_SECONDS * 0.9:
        return "TIMEOUT", "Parser v2 excedió timeout"

    # Analizar diferencias
    total_diffs = (diff["only_in_v1"] + diff["only_in_v2"]
                   + diff["name_diffs"] + diff["code_diffs"]
                   + diff["amount_diffs"] + diff["column_diffs"])

    if total_diffs == 0:
        return "TIE", "Resultados idénticos"

    # Si v2 omite cuentas que v1 encuentra → posible BUG en v2
    if diff["only_in_v2"] > 0 and diff["only_in_v1"] == 0:
        return "BUG_V2", f"v2 incluye {diff['only_in_v2']} cuentas que v1 no encuentra"

    if diff["only_in_v1"] > 0 and diff["only_in_v2"] == 0:
        return "BUG_V1", f"v1 incluye {diff['only_in_v1']} cuentas que v2 no encuentra"

    # Si hay diferencias en montos o columnas
    if diff["amount_diffs"] > 0 or diff["column_diffs"] > 0:
        return "INDETERMINATE", f"{diff['amount_diffs']} montos distintos, {diff['column_diffs']} columnas distintas"

    if diff["name_diffs"] > 0 or diff["code_diffs"] > 0:
        return "INDETERMINATE", f"{diff['name_diffs']} nombres distintos, {diff['code_diffs']} códigos distintos"

    return "INDETERMINATE", f"{total_diffs} diferencias sin clasificar"


def run_stress_test() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from parser_universal import ParserPDF as ParserV1, FormatoCodigo
    from parsers.pdf_parser import ParserCore2

    v1 = ParserV1()
    v2 = ParserCore2()

    # ── Descubrir todos los documentos ──
    docs: list[tuple[str, Path]] = []
    for group_dir in sorted(Path("datasets").iterdir()):
        if not group_dir.is_dir() or group_dir.name.startswith("."):
            continue
        for f in sorted(group_dir.iterdir()):
            if f.suffix.lower() in (".pdf", ".xlsx", ".xls"):
                docs.append((group_dir.name, f))

    logger.info("=== STRESS TEST: %d documentos ===", len(docs))

    # ── Cargar DocumentAssessment ──
    da_path = Path("reports/document_metrics/document_metrics.xlsx")
    da_map: dict[str, dict[str, Any]] = {}
    if da_path.exists():
        da_df = pd.read_excel(da_path)
        for _, row in da_df.iterrows():
            fn = str(row.get("source_file", "")).strip()
            if fn:
                da_map[fn] = {
                    "parser_confidence": float(row.get("parser_confidence", 0) or 0),
                    "layout_confidence": float(row.get("layout_confidence", 0) or 0),
                    "ocr_confidence": float(row.get("ocr_confidence", 0) or 0),
                    "contamination_rate": float(row.get("contamination_rate", 0) or 0),
                    "header_quality": float(row.get("header_quality", 0) or 0),
                }

    results: list[ComparisonResult] = []
    diff_results: list[ComparisonResult] = []
    fp_results: list[ComparisonResult] = []
    improve_results: list[ComparisonResult] = []

    verdict_counter: Counter = Counter()
    total_v1_time = 0.0
    total_v2_time = 0.0
    docs_with_diffs = 0

    for idx, (group, fpath) in enumerate(docs):
        logger.info("[%d/%d] %s/%s", idx + 1, len(docs), group, fpath.name)

        da = da_map.get(fpath.name, {})
        ft = fpath.suffix.lower().lstrip(".")

        # ── Parser v1 ──
        t1 = time.perf_counter()
        try:
            r1 = v1.parsear(fpath)
            t1e = time.perf_counter() - t1
        except Exception as e:
            t1e = time.perf_counter() - t1
            r1 = None
            logger.warning("  v1 ERROR: %s", e)

        # ── Parser v2 ──
        t2 = time.perf_counter()
        try:
            r2 = v2.parse(fpath)
            t2e = time.perf_counter() - t2
        except Exception as e:
            t2e = time.perf_counter() - t2
            r2 = None
            logger.warning("  v2 ERROR: %s", e)

        total_v1_time += t1e
        total_v2_time += t2e

        # Extraer datos
        v1_acc = len(r1.cuentas) if r1 else 0
        v2_acc = len(r2.accounts) if r2 else 0
        v1_fmt = r1.formato_codigo.value if r1 else "?"
        v2_fmt = r2.format if r2 else "?"
        v1_sep = r1.separador_miles if r1 else "?"
        v2_sep = r2.thousands_sep if r2 else "?"
        v1_ocr = r1.requirio_ocr if r1 else False
        v2_ocr = r2.used_ocr if r2 else False

        # Layout v2
        layout_cols = ""
        layout_conf = 0.0
        layout_src = "n/a"
        if r2 and r2.layout:
            layout_cols = ", ".join(r2.layout.columns)
            layout_conf = r2.layout.confidence
            layout_src = r2.layout.source

        # Comparación detallada
        if r1 and r2:
            diff = _compare_accounts(r1.cuentas, r2.accounts)
        else:
            diff = {
                "only_in_v1": 0, "only_in_v2": 0,
                "name_diffs": 0, "code_diffs": 0,
                "amount_diffs": 0, "column_diffs": 0,
                "accounts_match": (r1 is None and r2 is None),
            }

        cr = ComparisonResult(
            file_name=fpath.name,
            group=group,
            file_type=ft,
            v1_accounts=v1_acc,
            v2_accounts=v2_acc,
            accounts_match=diff["accounts_match"],
            only_in_v1=diff["only_in_v1"],
            only_in_v2=diff["only_in_v2"],
            name_diffs=diff["name_diffs"],
            code_diffs=diff["code_diffs"],
            amount_diffs=diff["amount_diffs"],
            column_diffs=diff["column_diffs"],
            v1_time_seconds=round(t1e, 3),
            v2_time_seconds=round(t2e, 3),
            v1_format=v1_fmt,
            v2_format=v2_fmt,
            v1_separator=v1_sep,
            v2_separator=v2_sep,
            v1_used_ocr=v1_ocr,
            v2_used_ocr=v2_ocr,
            layout_columns=layout_cols,
            layout_confidence=layout_conf,
            layout_source=layout_src,
            da_parser_confidence=da.get("parser_confidence", 0),
            da_layout_confidence=da.get("layout_confidence", 0),
            da_ocr_confidence=da.get("ocr_confidence", 0),
            da_contamination_rate=da.get("contamination_rate", 0),
            da_header_quality=da.get("header_quality", 0),
        )

        verdict, reason = _classify_verdict(cr, diff)
        cr.verdict = verdict
        cr.verdict_reason = reason

        verdict_counter[verdict] += 1
        results.append(cr)

        if verdict != "TIE":
            docs_with_diffs += 1
            diff_results.append(cr)

            if verdict in ("BUG_V1",):
                fp_results.append(cr)
            if verdict in ("BUG_V2", "INDETERMINATE"):
                improve_results.append(cr)

        # Log rápidos
        if not diff["accounts_match"]:
            logger.warning("  DIFERENCIA: v1=%d v2=%d | solo_v1=%d solo_v2=%d "
                           "nom=%d cod=%d mto=%d col=%d | %s",
                           v1_acc, v2_acc, diff["only_in_v1"], diff["only_in_v2"],
                           diff["name_diffs"], diff["code_diffs"],
                           diff["amount_diffs"], diff["column_diffs"], verdict)

    # ── Resumen ──
    logger.info("")
    logger.info("=== STRESS TEST COMPLETADO ===")
    logger.info("Documentos: %d", len(docs))
    logger.info("Tiempo v1: %.1fs | v2: %.1fs", total_v1_time, total_v2_time)
    logger.info("Documentos con diferencias: %d/%d", docs_with_diffs, len(docs))
    logger.info("Veredictos: %s", dict(verdict_counter.most_common()))

    # ── Generar reportes ──
    _save_reports(results, diff_results, fp_results, improve_results, verdict_counter, docs, total_v1_time, total_v2_time)

    # ── Mostrar documentos con diferencias ──
    if diff_results:
        logger.info("")
        logger.info("=== DOCUMENTOS CON DIFERENCIAS ===")
        for d in diff_results:
            logger.info("  %s [%s]: %s", d.file_name, d.verdict, d.verdict_reason)


def _save_reports(
    results: list[ComparisonResult],
    diffs: list[ComparisonResult],
    fps: list[ComparisonResult],
    improvements: list[ComparisonResult],
    verdict_counter: Counter,
    docs: list[tuple[str, Path]],
    total_v1_time: float,
    total_v2_time: float,
) -> None:
    # ── 1. Stress test completo ──
    rows = [asdict(r) for r in results]
    df_all = pd.DataFrame(rows)
    df_all.to_excel(OUTPUT_DIR / "parser_stress_test.xlsx", index=False)

    # ── 2. Diferencias ──
    if diffs:
        df_diff = pd.DataFrame([asdict(r) for r in diffs])
        df_diff.to_excel(OUTPUT_DIR / "differences.xlsx", index=False)

    # ── 3. False positives (BUG_V1) ──
    if fps:
        df_fp = pd.DataFrame([asdict(r) for r in fps])
        df_fp.to_excel(OUTPUT_DIR / "false_positive_cases.xlsx", index=False)

    # ── 4. Candidate improvements ──
    if improvements:
        df_imp = pd.DataFrame([asdict(r) for r in improvements])
        df_imp.to_excel(OUTPUT_DIR / "candidate_improvements.xlsx", index=False)

    # ── 5. Reporte markdown ──
    _write_md(results, diffs, fps, improvements, verdict_counter, docs,
              total_v1_time, total_v2_time)

    logger.info("Reportes → %s", OUTPUT_DIR)


def _write_md(
    results: list[ComparisonResult],
    diffs: list[ComparisonResult],
    fps: list[ComparisonResult],
    improvements: list[ComparisonResult],
    verdict_counter: Counter,
    docs: list[tuple[str, Path]],
    total_v1_time: float,
    total_v2_time: float,
) -> None:
    lines: list[str] = []
    L = lambda *a: lines.extend(a)

    total_accounts_v1 = sum(r.v1_accounts for r in results)
    total_accounts_v2 = sum(r.v2_accounts for r in results)
    exact_matches = sum(1 for r in results if r.verdict == "TIE")
    pct = round(exact_matches / len(results) * 100, 1) if results else 0

    # Casos más difíciles (por diferencias)
    hard = sorted(diffs, key=lambda r: (
        r.only_in_v1 + r.only_in_v2 + r.name_diffs + r.code_diffs +
        r.amount_diffs + r.column_diffs
    ), reverse=True) if diffs else []

    L("# Stress Test: Parser v1 vs Parser Core 2.0", "")
    L(f"**Fecha:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", "")
    L(f"**Documentos analizados:** {len(docs)}", "")
    L("", "---", "")

    L("## Resumen global", "", "| Métrica | Valor |", "|---------|-------|")
    L(f"| Total documentos | {len(results)} |")
    L(f"| Tiempo total v1 | {total_v1_time:.1f}s |")
    L(f"| Tiempo total v2 | {total_v2_time:.1f}s |")
    L(f"| Cuentas v1 | {total_accounts_v1} |")
    L(f"| Cuentas v2 | {total_accounts_v2} |")
    L(f"| Resultados idénticos (TIE) | {exact_matches}/{len(results)} ({pct}%) |")
    L(f"| Documentos con diferencias | {len(diffs)} |")
    L("")

    L("## Veredictos", "",
      "| Veredicto | Cantidad |", "|-----------|----------|")
    for v, c in verdict_counter.most_common():
        L(f"| {v} | {c} |")
    L("")

    if diffs:
        L("## Documentos con diferencias", "")
        L("| Archivo | Grupo | v1 | v2 | solo_v1 | solo_v2 | montos | cols | Veredicto |", 
          "|---------|-------|----|----|---------|---------|--------|------|------------|")
        for d in diffs:
            L(f"| {d.file_name} | {d.group} | {d.v1_accounts} | {d.v2_accounts} | "
              f"{d.only_in_v1} | {d.only_in_v2} | {d.amount_diffs} | {d.column_diffs} | "
              f"{d.verdict} |")
        L("")

        # Top 10 hardest
        L("## Top 10 casos más diferentes", "")
        for d in hard[:10]:
            total_diffs = (d.only_in_v1 + d.only_in_v2 + d.name_diffs +
                          d.code_diffs + d.amount_diffs + d.column_diffs)
            L(f"1. **{d.file_name}** ({d.group})")
            L(f"   - v1={d.v1_accounts} cuentas, v2={d.v2_accounts} cuentas")
            L(f"   - Diferencias: {total_diffs} totales")
            L(f"   - Veredicto: {d.verdict} — {d.verdict_reason}")
            L(f"   - DA: PC={d.da_parser_confidence:.2f} LC={d.da_layout_confidence:.2f} "
              f"CR={d.da_contamination_rate:.2f}")
            L("")

    # Casos duros por DocumentAssessment
    hard_da = sorted(results, key=lambda r: (
        (1 - r.da_parser_confidence) * 0.3 +
        (1 - r.da_layout_confidence) * 0.3 +
        r.da_contamination_rate * 0.4
    ), reverse=True)[:20]

    L("## Top 20 casos más difíciles (DocumentAssessment)", "",
      "| Archivo | Grupo | PC | LC | CR | v1 | v2 | Verdict |",
      "|---------|-------|----|----|----|----|----|---------|")
    for d in hard_da:
        L(f"| {d.file_name[:45]} | {d.group} | {d.da_parser_confidence:.2f} | "
          f"{d.da_layout_confidence:.2f} | {d.da_contamination_rate:.2f} | "
          f"{d.v1_accounts} | {d.v2_accounts} | {d.verdict} |")
    L("")

    # Conclusión
    L("## Conclusión", "")
    if len(diffs) == 0:
        L("**NO se encontraron diferencias entre Parser v1 y Parser Core 2.0.**")
        L("")
        L("En los {} documentos analizados, ambos parsers produjeron resultados idénticos "
          "en número de cuentas, nombres, códigos, montos y asignación de columnas.".format(len(results)))
        L("")
        L("Parser Core 2.0 NO es superior en capacidad de parseo. "
          "Su valor está en la arquitectura modular, las métricas (ParseMetrics, LayoutDetector), "
          "la configuración externalizada y la preparación para OCR pluggable — "
          "pero el output de parseo es el mismo porque v2 envuelve las mismas funciones de extracción.")
        L("")
        L("### ¿Qué falta para que v2 sea superior?")
        L("")
        L("1. **LayoutDetector integrado** — hoy es informativo; debe modificar la asignación de columnas")
        L("2. **Mejor OCR** — interfaz preparada pero sin implementación alternativa real")
        L("3. **Parseo paralelo** — estructura lista pero sin threading")
        L("4. **Caché de OCR** — config listo pero sin implementación")
        L("5. **Validación post-parseo** — usar ParseMetrics para rechazar/alertar")
    else:
        L(f"**Se encontraron {len(diffs)} documentos con diferencias.**")
        L("")
        veredicts = Counter(r.verdict for r in diffs)
        for v, c in veredicts.most_common():
            L(f"- {v}: {c}")
        L("")
        L("Ver archivos differences.xlsx y candidate_improvements.xlsx para detalle.")

    L("", "---", "")
    L(f"*Generado por `scripts/run_parser_stress_test.py`*")
    L("*Parser v1 = parser_universal.ParserPDF | Parser v2 = parsers.ParserCore2*")
    L("*No se modificó parser_universal.py. No se afectó producción.*")
    L("*No se escribieron nuevas funcionalidades. No se optimizó.*")

    (OUTPUT_DIR / "parser_stress_test.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_stress_test()
