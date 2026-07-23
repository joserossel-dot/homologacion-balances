#!/usr/bin/env python3
"""Benchmark comparativo: Parser v1 vs Parser Core 2.0.

Ejecuta ambos parsers en paralelo sobre los documentos HOLDOUT,
compara resultados y genera reporte.

Uso:
  PYTHONPATH=. python3 scripts/run_parser_benchmark.py
  PYTHONPATH=. python3 scripts/run_parser_benchmark.py --documents 5  (solo primeros 5)
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("benchmark")

HOLDOUT_DIR = Path("datasets/HOLDOUT")
OUTPUT_DIR = Path("reports/parser_benchmark")


@dataclass
class DocComparison:
    file_name: str
    v1_accounts: int
    v2_accounts: int
    accounts_match: bool
    account_diffs: list[dict]
    v1_time: float
    v2_time: float
    v1_format: str
    v2_format: str
    v1_ocr: bool
    v2_ocr: bool
    v1_advertencias: list[str]
    v2_warnings: list[str]
    layout_detected: str
    layout_confidence: float
    speedup: float


def _account_key(a) -> tuple:
    """Clave para comparar cuentas entre versiones."""
    amt = a.amount if hasattr(a, "amount") else getattr(a, "monto", 0)
    if amt is None:
        amt = 0.0
    return (a.line if hasattr(a, "line") else getattr(a, "linea", 0),
            a.name if hasattr(a, "name") else getattr(a, "nombre", ""),
            round(amt, 2))


def _account_to_dict(a) -> dict:
    if hasattr(a, "line"):
        return {"line": a.line, "code": a.code, "name": a.name,
                "amount": a.amount, "origin": a.column_origin,
                "total": a.is_total, "conf": round(a.extraction_confidence, 2)}
    return {"line": a.linea, "code": a.codigo, "name": a.nombre,
            "amount": a.monto, "origin": a.origen_columna.value if a.origen_columna else "?",
            "total": a.es_total, "conf": round(a.confianza_extraccion, 2)}


def run_benchmark(max_docs: int | None = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Inicializar parsers
    from parser_universal import ParserPDF as ParserV1
    from parsers.pdf_parser import ParserCore2

    v1 = ParserV1()
    v2 = ParserCore2()

    # Listar PDFs
    pdfs = sorted([p for p in HOLDOUT_DIR.iterdir() if p.suffix.lower() == ".pdf"])
    if max_docs:
        pdfs = pdfs[:max_docs]

    logger.info("Benchmark: %s documentos", len(pdfs))

    comparisons: list[DocComparison] = []
    total_v1_time = 0.0
    total_v2_time = 0.0
    total_v1_accounts = 0
    total_v2_accounts = 0
    matching_docs = 0
    exact_match_accounts = 0
    total_accounts_v1 = 0
    total_accounts_v2 = 0
    layout_confidences: list[float] = []
    method_v2_accounts: Counter = Counter()

    for pdf in pdfs:
        logger.info("  %s ...", pdf.name)

        # ── Parser v1 ──
        t1 = time.perf_counter()
        r1 = v1.parsear(pdf)
        t1 = time.perf_counter() - t1

        # ── Parser v2 ──
        t2 = time.perf_counter()
        r2 = v2.parse(pdf)
        t2 = time.perf_counter() - t2

        total_v1_time += t1
        total_v2_time += t2

        # Comparar
        n1 = len(r1.cuentas)
        n2 = len(r2.accounts)
        total_v1_accounts += n1
        total_v2_accounts += n2

        # Comparar cuentas
        keys1 = {_account_key(c): c for c in r1.cuentas}
        keys2 = {_account_key(c): c for c in r2.accounts}

        shared = set(keys1.keys()) & set(keys2.keys())
        only_v1 = set(keys1.keys()) - set(keys2.keys())
        only_v2 = set(keys2.keys()) - set(keys1.keys())

        exact_match_accounts += len(shared)
        total_accounts_v1 += len(keys1)
        total_accounts_v2 += len(keys2)

        accounts_match = (n1 == n2 and not only_v1 and not only_v2)

        if accounts_match:
            matching_docs += 1

        # Diffs detallados (muestra)
        diffs: list[dict] = []
        for k in list(only_v1)[:10]:
            c = keys1[k]
            diffs.append({"type": "v1_only", "account": _account_to_dict(c)})
        for k in list(only_v2)[:10]:
            c = keys2[k]
            diffs.append({"type": "v2_only", "account": _account_to_dict(c)})

        # Layout
        layout_detected = r2.layout.columns if r2.layout else []
        layout_conf = r2.layout.confidence if r2.layout else 0.0
        layout_confidences.append(layout_conf)

        # Métodos v2
        for acct in r2.accounts:
            method_v2_accounts[acct.column_origin] += 1

        speedup = round(t1 / t2, 2) if t2 > 0 else 0

        comparisons.append(DocComparison(
            file_name=pdf.name,
            v1_accounts=n1,
            v2_accounts=n2,
            accounts_match=accounts_match,
            account_diffs=diffs,
            v1_time=round(t1, 3),
            v2_time=round(t2, 3),
            v1_format=r1.formato_codigo.value,
            v2_format=r2.format,
            v1_ocr=r1.requirio_ocr,
            v2_ocr=r2.used_ocr,
            v1_advertencias=r1.advertencias,
            v2_warnings=r2.warnings,
            layout_detected=", ".join(layout_detected) if layout_detected else "fallback",
            layout_confidence=layout_conf,
            speedup=speedup,
        ))

    # ── Métricas globales ──
    elapsed = total_v1_time + total_v2_time
    v1_avg = total_v1_time / len(pdfs) if pdfs else 0
    v2_avg = total_v2_time / len(pdfs) if pdfs else 0
    avg_layout_conf = sum(layout_confidences) / len(layout_confidences) if layout_confidences else 0
    doc_match_rate = matching_docs / len(pdfs) * 100 if pdfs else 0

    total_shared = exact_match_accounts
    total_only_v1 = total_accounts_v1 - exact_match_accounts
    total_only_v2 = total_accounts_v2 - exact_match_accounts
    account_overlap = total_shared / max(total_accounts_v1 + total_accounts_v2 - total_shared, 1) * 100

    summary = {
        "documents": len(pdfs),
        "total_time_v1_seconds": round(total_v1_time, 1),
        "total_time_v2_seconds": round(total_v2_time, 1),
        "avg_time_v1_seconds": round(v1_avg, 3),
        "avg_time_v2_seconds": round(v2_avg, 3),
        "speedup_avg": round(v1_avg / v2_avg, 2) if v2_avg > 0 else 0,
        "total_accounts_v1": total_accounts_v1,
        "total_accounts_v2": total_accounts_v2,
        "shared_accounts": total_shared,
        "v1_only_accounts": total_only_v1,
        "v2_only_accounts": total_only_v2,
        "account_overlap_pct": round(account_overlap, 1),
        "documents_matching_exact": matching_docs,
        "doc_match_rate_pct": round(doc_match_rate, 1),
        "avg_layout_confidence": round(avg_layout_conf, 2),
        "layout_sources": dict(Counter(d.layout_detected for d in comparisons).most_common()),
        "v2_column_distribution": dict(method_v2_accounts.most_common()),
    }

    # ── Guardar ──
    json_path = OUTPUT_DIR / "parser_benchmark.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = OUTPUT_DIR / "parser_benchmark.md"
    _write_report(md_path, summary, comparisons)

    xlsx_path = OUTPUT_DIR / "parser_benchmark.xlsx"
    rows = [asdict(d) for d in comparisons]
    for r in rows:
        r["account_diffs"] = json.dumps(r["account_diffs"], ensure_ascii=False)
    pd.DataFrame(rows).to_excel(xlsx_path, index=False)

    logger.info("")
    logger.info("=== BENCHMARK COMPLETADO ===")
    logger.info("Documentos: %d", len(pdfs))
    logger.info("Tiempo v1: %.1fs | v2: %.1fs | speedup: %.2fx", total_v1_time, total_v2_time, summary["speedup_avg"])
    logger.info("Cuentas v1: %d | v2: %d | overlap: %.1f%%", total_accounts_v1, total_accounts_v2, account_overlap)
    logger.info("Docs coinciden exactamente: %d/%d (%.0f%%)", matching_docs, len(pdfs), doc_match_rate)
    logger.info("Reportes → %s", OUTPUT_DIR)


def _write_report(path: Path, summary: dict, comparisons: list[DocComparison]) -> None:
    L = lambda *a: lines.extend(a)
    lines: list[str] = []
    L("# Benchmark: Parser v1 vs Parser Core 2.0", "")
    L(f"**Fecha:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}", "")
    L(f"**Documentos:** {summary['documents']} PDFs del Holdout", "")
    L("", "---", "")

    L("## Resumen global", "", "| Métrica | Valor |", "|---------|-------|")
    L(f"| Tiempo total v1 | {summary['total_time_v1_seconds']}s |")
    L(f"| Tiempo total v2 | {summary['total_time_v2_seconds']}s |")
    L(f"| Promedio v1 | {summary['avg_time_v1_seconds']}s |")
    L(f"| Promedio v2 | {summary['avg_time_v2_seconds']}s |")
    L(f"| Speedup medio | {summary['speedup_avg']}x |")
    L(f"| Total cuentas v1 | {summary['total_accounts_v1']} |")
    L(f"| Total cuentas v2 | {summary['total_accounts_v2']} |")
    L(f"| Cuentas compartidas | {summary['shared_accounts']} ({summary['account_overlap_pct']}%) |")
    L(f"| Solo en v1 | {summary['v1_only_accounts']} |")
    L(f"| Solo en v2 | {summary['v2_only_accounts']} |")
    L(f"| Docs con match exacto | {summary['documents_matching_exact']}/{summary['documents']} ({summary['doc_match_rate_pct']}%) |")
    L(f"| Confianza layout promedio | {summary['avg_layout_confidence']} |")
    L("")

    L("## Distribución de layouts detectados (v2)", "",
      "| Layout | Documentos |",
      "|--------|------------|")
    for layout, count in summary["layout_sources"].items():
        L(f"| {layout} | {count} |")
    L("")

    L("## Columnas asignadas (v2)", "",
      "| Columna | Cuentas |",
      "|---------|---------|")
    for col, cnt in summary["v2_column_distribution"].items():
        L(f"| {col} | {cnt} |")
    L("")

    L("## Resultados por documento", "",
      "| Documento | v1 cuentas | v2 cuentas | Match | v1 seg | v2 seg | Speedup | Layout | Conf |",
      "|-----------|-----------|-----------|-------|--------|--------|---------|--------|------|")
    for d in comparisons:
        match = "✓" if d.accounts_match else "✗"
        lu = d.layout_detected[:20] if d.layout_detected != "fallback" else "─"
        lc = f"{d.layout_confidence:.0%}" if d.layout_confidence > 0 else "─"
        L(f"| {d.file_name} | {d.v1_accounts} | {d.v2_accounts} | {match} | "
          f"{d.v1_time:.2f} | {d.v2_time:.2f} | {d.speedup:.2f}x | {lu} | {lc} |")
    L("")

    # Documentos con diferencias
    non_matching = [d for d in comparisons if not d.accounts_match]
    if non_matching:
        L("## Diferencias detectadas", "")
        for d in non_matching:
            L(f"### {d.file_name}", "")
            L(f"- v1: {d.v1_accounts} cuentas, v2: {d.v2_accounts} cuentas")
            L(f"- Layout: {d.layout_detected} (conf: {d.layout_confidence})")
            for diff in d.account_diffs[:5]:
                a = diff["account"]
                L(f"  - {diff['type']}: [{a['code'] or ''}] {a['name'][:40]} monto={a['amount']}")
            if len(d.account_diffs) > 5:
                L(f"  - ... y {len(d.account_diffs) - 5} más")
            L("")

    L("---", "")
    L(f"*Generado por `scripts/run_parser_benchmark.py`*")
    L("*Parser v1 = parser_universal.ParserPDF | Parser v2 = parsers.ParserCore2*")
    L("*No se modificó parser_universal.py. No se afectó producción.*")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Reporte → %s", path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=int, default=None, help="Número de documentos a procesar")
    args = parser.parse_args()
    run_benchmark(args.documents)
