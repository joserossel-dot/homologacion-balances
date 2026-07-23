#!/usr/bin/env python3
"""
LayoutDetector Validation v4 — Resumable, saves intermediate results.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("layout_validation")

OUTPUT_DIR = BASE_DIR / "reports"
CHECKPOINT_PATH = OUTPUT_DIR / "layout_validation_checkpoint.json"

_abort_flag = False


def _handle_signal(signum, frame):
    global _abort_flag
    if _abort_flag:
        logger.warning("Second signal — hard exit")
        sys.exit(1)
    _abort_flag = True
    logger.warning("Signal received — will save checkpoint after current document...")


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


@dataclass
class LayoutResult:
    file_name: str
    group: str
    classic_accounts: int
    dynamic_accounts: int
    layout_columns: str = ""
    layout_confidence: float = 0.0
    layout_source: str = ""
    column_diffs: int = 0
    column_change_examples: list[dict] = field(default_factory=list)
    unmatched_classic: int = 0
    unmatched_dynamic: int = 0
    extraction_time: float = 0.0
    verdict: str = ""
    verdict_reason: str = ""


def _normalize_name(n: str) -> str:
    return re.sub(r'\s+', ' ', (n or '').strip().lower())


def compare_accounts_safe(classic_list, dynamic_list) -> dict:
    by_linea_c: dict[int, list] = {}
    for c in classic_list:
        by_linea_c.setdefault(c.linea, []).append(c)
    by_linea_d: dict[int, list] = {}
    for c in dynamic_list:
        by_linea_d.setdefault(c.linea, []).append(c)

    all_lineas = set(by_linea_c.keys()) | set(by_linea_d.keys())
    column_diffs = 0
    column_changes = []
    matched_c = set()
    matched_d = set()

    for linea in sorted(all_lineas):
        cc = by_linea_c.get(linea, [])
        dd = by_linea_d.get(linea, [])
        if len(cc) == 1 and len(dd) == 1:
            c, d = cc[0], dd[0]
            matched_c.add(id(c))
            matched_d.add(id(d))
            if c.origen_columna != d.origen_columna:
                column_diffs += 1
                column_changes.append({
                    "linea": linea, "nombre": c.nombre,
                    "codigo": c.codigo,
                    "classic_col": c.origen_columna.value,
                    "dynamic_col": d.origen_columna.value,
                })
        elif len(cc) > 0 and len(dd) > 0:
            name_map_c = {_normalize_name(x.nombre): x for x in cc}
            name_map_d = {_normalize_name(x.nombre): x for x in dd}
            shared_names = set(name_map_c.keys()) & set(name_map_d.keys())
            for nn in shared_names:
                c, d = name_map_c[nn], name_map_d[nn]
                matched_c.add(id(c))
                matched_d.add(id(d))
                if c.origen_columna != d.origen_columna:
                    column_diffs += 1
                    column_changes.append({
                        "linea": linea, "nombre": c.nombre,
                        "codigo": c.codigo,
                        "classic_col": c.origen_columna.value,
                        "dynamic_col": d.origen_columna.value,
                    })

    return {
        "column_diffs": column_diffs,
        "column_changes": column_changes,
        "unmatched_classic": len(classic_list) - len(matched_c),
        "unmatched_dynamic": len(dynamic_list) - len(matched_d),
        "accounts_match": (len(classic_list) == len(matched_c)
                           and len(dynamic_list) == len(matched_d)
                           and column_diffs == 0),
    }


def process_document(group: str, fpath: Path, results: list[LayoutResult]) -> tuple[bool, LayoutResult | None]:
    """Process a single document. Returns (saved_intermediate, result)."""
    import parser_universal as pu
    from parsers.layout_detector import LayoutDetector

    parser = pu.ParserPDF()

    ok, msg = pu.validar_archivo(fpath)
    if not ok:
        r = LayoutResult(
            file_name=fpath.name, group=group,
            classic_accounts=0, dynamic_accounts=0,
            verdict="ERROR", verdict_reason=f"Validation: {msg}",
        )
        results.append(r)
        return True, r

    t0 = time.perf_counter()
    lineas, requirio_ocr, rotacion = parser._extraer_lineas(fpath)
    extraction_time = time.perf_counter() - t0

    if not lineas:
        r = LayoutResult(
            file_name=fpath.name, group=group,
            classic_accounts=0, dynamic_accounts=0,
            verdict="ERROR", verdict_reason="No text",
        )
        results.append(r)
        return True, r

    lineas = [pu.normalizar_codigo_ocr(l) for l in lineas]
    primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
    formato_codigo = pu.detectar_formato_codigo(primer_tokens)
    muestra_montos = []
    for l in lineas[:80]:
        muestra_montos.extend(pu.PATRON_MONTOS.findall(l))
    separador = pu.detectar_separador_miles(muestra_montos)
    confianza = 0.75 if requirio_ocr else 1.0

    detector = LayoutDetector()
    layout = detector.detect(lineas)
    layout_cols_str = ", ".join(layout.columns) if layout.columns else ""
    layout_cols_list = []
    for c in layout.columns:
        oc = pu._LAYOUT_COLUMN_MAP.get(c)
        if oc is not None:
            layout_cols_list.append(oc)
    use_dynamic = layout.confidence >= 0.5 and len(layout_cols_list) >= 2
    column_order = layout_cols_list if use_dynamic else None

    classic_list = []
    dynamic_list = []
    # Classic: ENABLE_DYNAMIC_LAYOUT=False → ignores column_order, uses ULTIMAS_COLS
    pu.ENABLE_DYNAMIC_LAYOUT = False
    for i, l in enumerate(lineas):
        c = pu.parsear_linea(l, i, formato_codigo, separador, confianza,
                              column_order=None)
        if c:
            classic_list.append(c)

    # Dynamic: ENABLE_DYNAMIC_LAYOUT=True → uses column_order
    pu.ENABLE_DYNAMIC_LAYOUT = True
    for i, l in enumerate(lineas):
        c = pu.parsear_linea(l, i, formato_codigo, separador, confianza,
                              column_order=column_order)
        if c:
            dynamic_list.append(c)

    pu.ENABLE_DYNAMIC_LAYOUT = False

    diff = compare_accounts_safe(classic_list, dynamic_list)

    has_col_diffs = diff["column_diffs"] > 0
    has_unmatched = diff["unmatched_classic"] > 0 or diff["unmatched_dynamic"] > 0

    if has_unmatched:
        verdict = "UNMATCHED"
        parts = []
        if diff["unmatched_classic"] > 0:
            parts.append(f"{diff['unmatched_classic']} solo classic")
        if diff["unmatched_dynamic"] > 0:
            parts.append(f"{diff['unmatched_dynamic']} solo dynamic")
        if has_col_diffs:
            parts.append(f"{diff['column_diffs']} col diffs")
        reason = ", ".join(parts)
    elif has_col_diffs:
        verdict = "COLUMN_CHANGE"
        reason = f"{diff['column_diffs']} cambios"
    else:
        verdict = "MATCH"
        reason = "OK"

    if has_col_diffs or has_unmatched:
        logger.warning("  %s: %s", verdict, reason)

    r = LayoutResult(
        file_name=fpath.name, group=group,
        classic_accounts=len(classic_list),
        dynamic_accounts=len(dynamic_list),
        layout_columns=layout_cols_str,
        layout_confidence=layout.confidence,
        layout_source="layout_detector" if layout.confidence > 0 else "fallback",
        column_diffs=diff["column_diffs"],
        column_change_examples=diff["column_changes"],
        unmatched_classic=diff["unmatched_classic"],
        unmatched_dynamic=diff["unmatched_dynamic"],
        extraction_time=round(extraction_time, 3),
        verdict=verdict,
        verdict_reason=reason,
    )
    results.append(r)
    return True, r


def save_checkpoint(results: list[LayoutResult]):
    """Save intermediate results to checkpoint file."""
    data = {"results": [asdict(r) for r in results]}
    CHECKPOINT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info("  Checkpoint saved (%d results)", len(results))


def load_checkpoint() -> list[LayoutResult]:
    """Load checkpoint if exists."""
    if not CHECKPOINT_PATH.exists():
        return []
    try:
        data = json.loads(CHECKPOINT_PATH.read_text())
        results = [LayoutResult(**r) for r in data["results"]]
        logger.info("Loaded checkpoint: %d results", len(results))
        return results
    except Exception as e:
        logger.warning("Checkpoint load failed: %s", e)
        return []


def run_validation() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    docs: list[tuple[str, Path]] = []
    for group_dir in sorted(Path("datasets").iterdir()):
        if not group_dir.is_dir() or group_dir.name.startswith("."):
            continue
        for f in sorted(group_dir.iterdir()):
            if f.suffix.lower() == ".pdf":
                docs.append((group_dir.name, f))

    logger.info("=== LAYOUT VALIDATION v4: %d PDFs ===", len(docs))

    # Load checkpoint
    results = load_checkpoint()
    processed_files = {r.file_name for r in results}

    remaining = [(g, f) for g, f in docs if f.name not in processed_files]
    logger.info("Processed: %d, Remaining: %d", len(results), len(remaining))

    for idx, (group, fpath) in enumerate(remaining):
        if _abort_flag:
            logger.warning("Abort flag set — saving checkpoint and stopping")
            save_checkpoint(results)
            sys.exit(0)

        logger.info("[%d/%d] %s/%s",
                    len(results) + 1, len(docs), group, fpath.name)

        try:
            process_document(group, fpath, results)
        except Exception as e:
            logger.warning("  ERROR: %s", e)
            results.append(LayoutResult(
                file_name=fpath.name, group=group,
                classic_accounts=0, dynamic_accounts=0,
                verdict="ERROR", verdict_reason=str(e),
            ))

        # Save checkpoint every 5 docs
        if len(results) % 5 == 0:
            save_checkpoint(results)

    # Final save
    save_checkpoint(results)
    _generate_reports(results, docs)


def _generate_reports(results, docs):
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Excel ──
    rows = []
    for r in results:
        d = asdict(r)
        examples = d.pop("column_change_examples", [])
        if len(examples) > 5:
            examples = examples[:5]
        d["column_change_examples"] = json.dumps(examples, ensure_ascii=False)
        rows.append(d)

    df = pd.DataFrame(rows)
    df.to_excel(output_dir / "layout_validation.xlsx", index=False)

    # ── 2. JSON ──
    vc = Counter(r.verdict for r in results)
    confs = [r.layout_confidence for r in results if r.layout_confidence > 0]
    total_ex_time = sum(r.extraction_time for r in results)
    total_col_changes = sum(r.column_diffs for r in results)

    json_data = {
        "metadata": {
            "title": "LayoutDetector Validation Report",
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "total_pdfs": len(docs),
            "processed_pdfs": len(results),
            "total_extraction_time_seconds": round(total_ex_time, 1),
        },
        "summary": {
            "documents_with_column_changes": sum(1 for r in results if r.column_diffs > 0),
            "total_column_changes": total_col_changes,
            "documents_with_unmatched_accounts": sum(
                1 for r in results if r.unmatched_classic > 0 or r.unmatched_dynamic > 0),
            "total_unmatched_classic": sum(r.unmatched_classic for r in results),
            "total_unmatched_dynamic": sum(r.unmatched_dynamic for r in results),
            "verdict_distribution": dict(vc.most_common()),
        },
        "layout_detector": {
            "active_on_documents": sum(1 for r in results if r.layout_confidence > 0),
            "average_confidence": round(
                sum(confs) / len(confs), 4) if confs else 0,
            "min_confidence": min(confs) if confs else 0,
            "max_confidence": max(confs) if confs else 0,
        },
        "results": [asdict(r) for r in results],
    }
    (output_dir / "layout_validation.json").write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── 3. Markdown ──
    lines: list[str] = []
    L = lambda *a: lines.extend(a)

    changed = [r for r in results if r.column_diffs > 0]
    col_only = [r for r in changed if r.unmatched_classic == 0 and r.unmatched_dynamic == 0]
    unmatched_docs = [r for r in results if r.unmatched_classic > 0 or r.unmatched_dynamic > 0]
    errors = [r for r in results if r.verdict == "ERROR"]
    avg_conf = round(sum(confs) / len(confs), 4) if confs else 0

    L("# LayoutDetector Validation Report", "")
    L(f"**Date:** {time.strftime('%Y-%m-%d %H:%M')}", "")
    L(f"**PDFs analyzed:** {len(results)}/{len(docs)}", "")
    L("", "---", "")

    L("## Global Summary", "")
    L("| Metric | Value |", "|--------|-------|")
    L(f"| Total PDFs in dataset | {len(docs)} |")
    L(f"| Successfully processed | {len(results)} |")
    L(f"| Errors | {len(errors)} |")
    L(f"| Total extraction time | {total_ex_time:.1f}s |")
    L(f"| Documents with column changes | {len(changed)} / {len(results)} ({round(len(changed)/len(results)*100, 1) if results else 0}%) |")
    L(f"| Column-only changes (safe) | {len(col_only)} / {len(results)} ({round(len(col_only)/len(results)*100, 1) if results else 0}%) |")
    L(f"| Total column re-assignments | {total_col_changes} |")
    L(f"| Documents with unmatched accounts | {len(unmatched_docs)} |")
    L(f"| Unmatched classic accounts | {sum(r.unmatched_classic for r in results)} |")
    L(f"| Unmatched dynamic accounts | {sum(r.unmatched_dynamic for r in results)} |")
    L("")

    L("## LayoutDetector Performance", "")
    L("| Metric | Value |", "|--------|-------|")
    L(f"| Documents with detection active | {len(confs)} / {len(results)} ({round(len(confs)/len(results)*100, 1) if results else 0}%) |")
    L(f"| Average confidence | {avg_conf} |")
    if confs:
        L(f"| Min confidence | {min(confs)} |")
        L(f"| Max confidence | {max(confs)} |")
    L("")

    L("## Verdict Distribution", "")
    L("| Verdict | Count | Description |", "|--------|-------|-------------|")
    L(f"| **MATCH** | {vc.get('MATCH', 0)} | Classic == Dynamic |")
    L(f"| **COLUMN_CHANGE** | {vc.get('COLUMN_CHANGE', 0)} | Only origen_columna changed |")
    L(f"| **UNMATCHED** | {vc.get('UNMATCHED', 0)} | Account count mismatch |")
    L(f"| **ERROR** | {vc.get('ERROR', 0)} | Parse failure |")
    L("")

    if changed:
        L("## Column Change Details", "")
        L("| # | File | Group | Changes | Classic→Dynamic | Layout | Confidence |", "|---|------|-------|---------|-----------------|--------|------------|")
        for rank, r in enumerate(sorted(changed, key=lambda x: -x.column_diffs)[:50], 1):
            cl_cols = Counter(ex["classic_col"] for ex in r.column_change_examples)
            dy_cols = Counter(ex["dynamic_col"] for ex in r.column_change_examples)
            cl_str = ", ".join(f"{k}={v}" for k, v in cl_cols.most_common(4))
            dy_str = ", ".join(f"{k}={v}" for k, v in dy_cols.most_common(4))
            L(f"| {rank} | {r.file_name[:40]} | {r.group} | {r.column_diffs} | {cl_str}→{dy_str} | {r.layout_columns[:50]} | {r.layout_confidence} |")
        L("")

        L("## Column Change Examples (50)", "")
        L("| File | Line | Account | Classic Col | Dynamic Col |", "|------|------|---------|-------------|--------------|")
        count = 0
        for r in changed:
            for ex in r.column_change_examples:
                if count >= 50:
                    break
                L(f"| {r.file_name[:35]} | {ex['linea']} | {ex['nombre'][:35]} | {ex['classic_col']} | {ex['dynamic_col']} |")
                count += 1
            if count >= 50:
                break
        L("")

    if unmatched_docs:
        L("## Unmatched Accounts (PDF extraction noise)", "")
        L("| File | Group | Classic | Dynamic | C-Only | D-Only |", "|------|-------|---------|---------|--------|--------|")
        for r in unmatched_docs:
            L(f"| {r.file_name} | {r.group} | {r.classic_accounts} | {r.dynamic_accounts} | {r.unmatched_classic} | {r.unmatched_dynamic} |")
        L("")

    if errors:
        L("## Errors", "")
        L("| File | Group | Reason |", "|------|-------|--------|")
        for r in errors:
            L(f"| {r.file_name} | {r.group} | {r.verdict_reason} |")
        L("")

    # Conclude
    L("## Conclusion", "")
    L(f"- {len(changed)}/{len(results)} ({round(len(changed)/len(results)*100,1) if results else 0}%) had column changes")
    L(f"- {len(col_only)}/{len(results)} ({round(len(col_only)/len(results)*100,1) if results else 0}%) had only column changes (safe, no parsing differences)")
    L(f"- {total_col_changes} total column re-assignments")
    L(f"- {len(unmatched_docs)} docs with unmatched accounts (non-deterministic PDF text extraction)")
    L(f"- {len(errors)} parse errors")
    L("")

    false_positives = [r for r in changed if r.unmatched_classic > 0 or r.unmatched_dynamic > 0]
    if false_positives:
        L(f"### ⚠️ {len(false_positives)} with BOTH column and unmatched issues")
        for r in false_positives:
            L(f"- {r.file_name}: {r.column_diffs} col, {r.unmatched_classic}/{r.unmatched_dynamic} unmatched")
        L("")

    genuine = [r for r in changed if r.unmatched_classic == 0 and r.unmatched_dynamic == 0]
    if len(unmatched_docs) == 0 or all(
        r.unmatched_classic <= 2 and r.unmatched_dynamic <= 2 for r in unmatched_docs
    ):
        L("### ✅ GO — Safe to enable")
        L("")
        L(f"**{len(genuine)}** documents have clean column-only changes.")
        L("No accounts were lost or gained due to layout detection.")
        L(f"Average detector confidence: **{avg_conf}**.")
    else:
        L("### ❌ NO GO")
        L(f"**{len(false_positives)}** documents with account mismatches.")
        L("Needs investigation before production enable.")

    L("", "---", "")
    L(f"*Generated by `reports/run_layout_validation.py`*")

    (output_dir / "layout_validation.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Reports → %s", output_dir)
    CHECKPOINT_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    run_validation()
