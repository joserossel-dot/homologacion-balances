"""FASE 18B — CMCC Threshold Calibration.

Processes all UNKNOWN accounts from cached audit data, runs CMCC on each,
and evaluates thresholds from 0.85 to 1.00 without any pipeline changes.
"""
from __future__ import annotations
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from pipeline.cmcc_classifier import CMCCClassifier

REPORTS_DIR = Path("reports/cmcc_calibration")
CACHE_PATH = REPORTS_DIR / "calibration_data.json"
AUDIT_PATH = Path("reports/audit/audit_data.json")

THRESHOLDS = [1.00, 0.99, 0.98, 0.97, 0.95, 0.90, 0.85]


def _infer_group(path: str) -> str:
    if "entrenamiento" in path:
        return "entrenamiento"
    if "validacion" in path:
        return "validacion"
    if "edge_cases" in path:
        return "edge_cases"
    if "corruptos" in path:
        return "corruptos"
    return "other"


def _extract_company(filename: str) -> str:
    name = Path(filename).stem
    name = re.sub(r"\s+", " ", name)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\b\d{4}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    parts = name.split()
    if not parts:
        return filename
    if parts[0].lower() in ("balance", "balances", "eeff", "pre", "prelimiar",
                             "resumen", "bALANCE"):
        parts = parts[1:]
    return " ".join(parts[:4]).strip() or filename


# ─── Phase 1: Collect ──────────────────────────────────────────────

def collect_all(force: bool = False) -> list[dict]:
    if CACHE_PATH.exists() and not force:
        print(f"Loading cached data from {CACHE_PATH}...")
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cached = json.load(f)
        print(f"  {len(cached)} rows loaded")
        return cached

    print("Loading audit data...")
    with open(AUDIT_PATH, "r", encoding="utf-8") as f:
        audit = json.load(f)

    accounts = audit.get("accounts", [])
    unclassified = [a for a in accounts if a.get("method") == "unclassified"]
    print(f"  Total accounts: {len(accounts)}, UNKNOWN: {len(unclassified)}")

    print("Initializing CMCC classifier...")
    cmcc = CMCCClassifier()

    all_rows: list[dict] = []
    t_start = time.time()
    batch_size = 500

    for i, acct in enumerate(unclassified):
        name = acct.get("account_name", "")
        source_path = acct.get("source_path", acct.get("source_file", ""))
        is_ocr = source_path.lower().endswith(".pdf")
        group = _infer_group(source_path)
        company = _extract_company(source_path)

        cmcc_result = cmcc.classify(name)

        all_rows.append({
            "file": Path(source_path).name,
            "source_path": source_path,
            "group": group,
            "company": company,
            "file_type": "pdf" if is_ocr else "excel",
            "is_ocr": is_ocr,
            "account_name": name,
            "nature": acct.get("nature", ""),
            "cmcc_code": cmcc_result.get("code"),
            "cmcc_concept": cmcc_result.get("concept"),
            "cmcc_score": cmcc_result.get("score", 0.0),
            "cmcc_method": cmcc_result.get("method"),
            "cmcc_variant": cmcc_result.get("matched_variant"),
            "cmcc_evidence": " | ".join(cmcc_result.get("evidence", [])),
        })

        if (i + 1) % 1000 == 0:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (len(unclassified) - i - 1) / rate
            print(f"  [{i+1}/{len(unclassified)}] {rate:.0f} rows/s, "
                  f"ETA {eta:.0f}s")

    total_elapsed = time.time() - t_start
    print(f"Collected {len(all_rows)} rows in {total_elapsed:.1f}s "
          f"({len(all_rows)/total_elapsed:.0f} rows/s)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_rows, f)
    print(f"Cache saved to {CACHE_PATH}")
    return all_rows


# ─── Phase 2: Analyze ──────────────────────────────────────────────

def analyze(rows: list[dict]) -> dict:
    total = len(rows)
    valid = rows  # no errors in this path
    total_unknown = len(valid)

    concept_by_code = {r["cmcc_code"]: r["cmcc_concept"]
                       for r in valid if r["cmcc_code"]}

    threshold_data: dict[float, dict] = {}
    for t in THRESHOLDS:
        matched = [r for r in valid if r["cmcc_score"] >= t]
        recovered = len(matched)

        groups = Counter(r["group"] for r in matched)
        file_types = Counter(r["file_type"] for r in matched)
        ocr = Counter(r["is_ocr"] for r in matched)
        nature = Counter(r["nature"] for r in matched)
        methods = Counter(r["cmcc_method"] for r in matched if r["cmcc_method"])
        companies = Counter(r["company"] for r in matched)

        codes = Counter(r["cmcc_code"] for r in matched if r["cmcc_code"])
        concepts = Counter(r["cmcc_concept"] for r in matched if r["cmcc_concept"])
        variants = Counter(r["cmcc_variant"] for r in matched if r["cmcc_variant"])

        by_score = []
        for lo, hi in [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85),
                        (0.85, 0.90), (0.90, 0.95), (0.95, 0.99), (0.99, 1.0), (1.0, 1.01)]:
            cnt = sum(1 for r in valid if lo <= r["cmcc_score"] < hi)
            by_score.append({"range": f"{lo:.2f}-{hi:.2f}", "count": cnt})

        threshold_data[t] = {
            "recovered": recovered,
            "pct": round(recovered / total_unknown * 100, 2) if total_unknown else 0,
            "remaining_unknown": total_unknown - recovered,
            "concepts": len(concepts),
            "top_concepts": concepts.most_common(20),
            "top_codes": codes.most_common(20),
            "top_variants": variants.most_common(20),
            "top_groups": groups.most_common(10),
            "top_file_types": file_types.most_common(5),
            "top_natures": nature.most_common(5),
            "top_methods": methods.most_common(10),
            "top_companies": companies.most_common(20),
            "ocr_count": ocr.get(True, 0),
            "native_count": ocr.get(False, 0),
            "by_score": by_score,
        }

    return {
        "total_rows": total,
        "total_unknown": total_unknown,
        "thresholds": threshold_data,
        "concept_by_code": concept_by_code,
        "all_valid": valid,
    }


# ─── Phase 3: Reports ──────────────────────────────────────────────

def generate_reports(analysis: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    valid = analysis["all_valid"]
    total_unknown = analysis["total_unknown"]
    td = analysis["thresholds"]
    cbc = analysis["concept_by_code"]

    # ── threshold_comparison.xlsx ──
    comp = []
    for t in THRESHOLDS:
        d = td[t]
        comp.append({
            "threshold": t,
            "recovered": d["recovered"],
            "pct": d["pct"],
            "remaining_unknown": d["remaining_unknown"],
            "distinct_concepts": d["concepts"],
            "ocr": d["ocr_count"],
            "native": d["native_count"],
        })
    pd.DataFrame(comp).to_excel(REPORTS_DIR / "threshold_comparison.xlsx",
                                index=False)

    # ── threshold_curve.xlsx ──
    curve = []
    for t in THRESHOLDS:
        for bucket in td[t]["by_score"]:
            curve.append({
                "threshold": t,
                "score_range": bucket["range"],
                "count": bucket["count"],
            })
    pd.DataFrame(curve).to_excel(REPORTS_DIR / "threshold_curve.xlsx",
                                 index=False)

    # ── score_distribution.xlsx ──
    sd = []
    for lo, hi, label in [(0.0, 0.5, "0-0.5 (muy bajo)"),
                           (0.5, 0.7, "0.5-0.7 (bajo)"),
                           (0.7, 0.85, "0.7-0.85 (dudoso)"),
                           (0.85, 0.90, "0.85-0.90 (revisable)"),
                           (0.90, 0.95, "0.90-0.95 (bueno)"),
                           (0.95, 1.0, "0.95-1.0 (muy bueno)"),
                           (1.0, 1.01, "1.0 (exacto)")]:
        cnt = sum(1 for r in valid if lo <= r["cmcc_score"] < hi)
        pct = round(cnt / total_unknown * 100, 1) if total_unknown else 0
        sd.append({"rango": label, "cuentas": cnt, "porcentaje": pct})
    pd.DataFrame(sd).to_excel(REPORTS_DIR / "score_distribution.xlsx",
                              index=False)

    # ── threshold_examples.xlsx ──
    ex = []
    for t in THRESHOLDS:
        matched = [r for r in valid if r["cmcc_score"] >= t]
        for r in matched[:5]:
            ex.append({
                "threshold": t,
                "account": r["account_name"],
                "score": r["cmcc_score"],
                "code": r["cmcc_code"],
                "concept": r["cmcc_concept"],
                "variant": r["cmcc_variant"],
                "file": r["file"],
                "group": r["group"],
                "ocr": r["is_ocr"],
            })
    pd.DataFrame(ex).to_excel(REPORTS_DIR / "threshold_examples.xlsx",
                              index=False)

    # ── company_breakdown.xlsx ──
    comp_info = []
    for r in valid:
        comp_info.append({
            "company": r["company"],
            "file": r["file"],
            "score": r["cmcc_score"],
            "code": r["cmcc_code"],
            "group": r["group"],
            "ocr": r["is_ocr"],
        })
    cdf = pd.DataFrame(comp_info)
    if not cdf.empty:
        cg = cdf.groupby("company").agg(
            total_unknown=("score", "count"),
            avg_score=("score", "mean"),
            max_score=("score", "max"),
            recovered=("score", lambda x: (x >= 0.90).sum()),
            recovery_pct=("score", lambda x:
                round((x >= 0.90).sum() / len(x) * 100, 1)),
            files=("file", lambda x: x.nunique()),
        ).reset_index().sort_values("total_unknown", ascending=False)
    else:
        cg = pd.DataFrame()
    cg.to_excel(REPORTS_DIR / "company_breakdown.xlsx", index=False)

    # ── layout_breakdown.xlsx ──
    lay_info = []
    for r in valid:
        lay_info.append({
            "layout": r["group"],
            "file": r["file"],
            "score": r["cmcc_score"],
            "recovered": r["cmcc_score"] >= 0.90,
        })
    ldf = pd.DataFrame(lay_info)
    if not ldf.empty:
        lg = ldf.groupby("layout").agg(
            total_unknown=("file", "count"),
            recovered=("recovered", "sum"),
            recovery_pct=("recovered", lambda x:
                round(x.sum() / len(x) * 100, 1)),
            avg_score=("score", "mean"),
            files=("file", lambda x: x.nunique()),
        ).reset_index().sort_values("total_unknown", ascending=False)
    else:
        lg = pd.DataFrame()
    lg.to_excel(REPORTS_DIR / "layout_breakdown.xlsx", index=False)

    # ── ocr_breakdown.xlsx ──
    ocr_info = []
    for r in valid:
        ocr_info.append({
            "tipo": "ocr" if r["is_ocr"] else "nativo",
            "file": r["file"],
            "score": r["cmcc_score"],
            "recovered": r["cmcc_score"] >= 0.90,
        })
    odf = pd.DataFrame(ocr_info)
    if not odf.empty:
        og = odf.groupby("tipo").agg(
            total_unknown=("file", "count"),
            recovered=("recovered", "sum"),
            recovery_pct=("recovered", lambda x:
                round(x.sum() / len(x) * 100, 1)),
            avg_score=("score", "mean"),
            files=("file", lambda x: x.nunique()),
        ).reset_index()
    else:
        og = pd.DataFrame()
    og.to_excel(REPORTS_DIR / "ocr_breakdown.xlsx", index=False)

    print("Excel reports generated.")

    _generate_markdown(td, total_unknown, cbc, valid)


def _generate_markdown(td: dict, total_unknown: int,
                        cbc: dict, valid: list) -> None:
    ocr_total = sum(1 for r in valid if r["is_ocr"])
    native_total = sum(1 for r in valid if not r["is_ocr"])

    # Threshold that maximizes raw recovery
    q1_threshold = max(THRESHOLDS, key=lambda t: td[t]["recovered"])
    q1 = td[q1_threshold]

    # Threshold that maximizes precision (≥0.95)
    high_conf = [t for t in THRESHOLDS if t >= 0.95]
    best_precision_t = max(high_conf, key=lambda t: td[t]["recovered"])
    bp = td[best_precision_t]

    lines = []
    lines.append("# CMCC Calibration Report")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append(f"Total UNKNOWN analizados: **{total_unknown:,}**")
    lines.append(f"OCR: {ocr_total} | Nativo: {native_total}")
    lines.append("")

    # Threshold table
    lines.append("## Comparación de Umbrales")
    lines.append("")
    lines.append("| Threshold | Recuperados | % | Restantes | Conceptos | OCR | Nativo |")
    lines.append("|---|---|---|---|---|---|---|")
    for t in THRESHOLDS:
        d = td[t]
        lines.append(
            f"| {t:.2f} | {d['recovered']:,} | {d['pct']}% | "
            f"{d['remaining_unknown']:,} | {d['concepts']} | "
            f"{d['ocr_count']:,} | {d['native_count']:,} |")
    lines.append("")

    # Score distribution
    lines.append("## Distribución de Scores")
    lines.append("")
    lines.append("| Rango | Cuentas | % |")
    lines.append("|---|---|---|")
    for bucket in td[0.85]["by_score"]:
        pct = round(bucket["count"] / total_unknown * 100, 1) if total_unknown else 0
        lines.append(f"| {bucket['range']} | {bucket['count']:,} | {pct}% |")
    lines.append("")

    # Top concepts at threshold 0.90
    lines.append("## Top Códigos Recuperados (threshold 0.90)")
    lines.append("")
    lines.append("| # | Código | Concepto | Veces |")
    lines.append("|---|---|---|---|")
    for idx, (code, cnt) in enumerate(td[0.90]["top_codes"][:15], 1):
        concept = cbc.get(code, code)
        lines.append(f"| {idx} | {code} | {concept} | {cnt:,} |")
    lines.append("")

    # Top variants
    lines.append("## Top Variantes Usadas (threshold 0.90)")
    lines.append("")
    lines.append("| # | Variante | Veces |")
    lines.append("|---|---|---|")
    for idx, (var, cnt) in enumerate(td[0.90]["top_variants"][:15], 1):
        lines.append(f"| {idx} | {var[:80]} | {cnt:,} |")
    lines.append("")

    # Layout breakdown
    lines.append("## Recuperación por Layout")
    lines.append("")
    lines.append("| Layout | UNKNOWN | Recuperados (≥0.90) | % |")
    lines.append("|---|---|---|---|")
    for group, cnt in td[0.90]["top_groups"]:
        total_in = sum(1 for r in valid if r["group"] == group)
        pct = round(cnt / total_in * 100, 1) if total_in else 0
        lines.append(f"| {group} | {total_in:,} | {cnt:,} | {pct}% |")
    lines.append("")

    # OCR vs Native
    lines.append("## OCR vs Nativo")
    lines.append("")
    lines.append("| Tipo | UNKNOWN | Recuperados (≥0.90) | % |")
    lines.append("|---|---|---|---|")
    ocr_rec = td[0.90]["ocr_count"]
    native_rec = td[0.90]["native_count"]
    ocr_pct = round(ocr_rec / ocr_total * 100, 1) if ocr_total else 0
    native_pct = round(native_rec / native_total * 100, 1) if native_total else 0
    lines.append(f"| OCR | {ocr_total:,} | {ocr_rec:,} | {ocr_pct}% |")
    lines.append(f"| Nativo | {native_total:,} | {native_rec:,} | {native_pct}% |")
    lines.append("")

    # Curve
    lines.append("## Curva de Recuperación")
    lines.append("")
    lines.append("| Threshold | Recuperados | % |")
    lines.append("|---|---|---|")
    for t in THRESHOLDS:
        lines.append(f"| {t:.2f} | {td[t]['recovered']:,} | {td[t]['pct']}% |")
    lines.append("")

    # Answers
    lines.append("## Conclusiones")
    lines.append("")

    lines.append("### 1. ¿Cuál threshold maximiza recuperación?")
    lines.append(f"**{q1_threshold:.2f}** — recupera **{q1['recovered']:,}** cuentas "
                 f"({q1['pct']}% del total UNKNOWN).")
    lines.append("")

    review = [r for r in valid if 0.70 <= r["cmcc_score"] < 0.90]
    lines.append("### 2. ¿Cuál threshold mantiene mayor precisión esperada?")
    lines.append(f"**{best_precision_t:.2f}** — recupera **{bp['recovered']:,}** cuentas "
                 f"({bp['pct']}%) con alta confianza (≥95%).")
    lines.append("")

    lines.append("### 3. ¿Cuántas cuentas nuevas se clasificarían?")
    for t in [0.95, 0.90, 0.85]:
        lines.append(f"- **Threshold {t:.2f}**: {td[t]['recovered']:,} cuentas nuevas")
    lines.append("")

    lines.append("### 4. ¿Cuántas quedarían en REVIEW?")
    lines.append(f"**{len(review):,}** cuentas en zona dudosa (0.70-0.90) "
                 f"requerirían revisión manual.")
    lines.append("")

    lines.append("### 5. ¿Cuántas seguirían UNKNOWN?")
    for t in [1.0, 0.95, 0.90, 0.85]:
        lines.append(f"- **Threshold {t:.2f}**: {td[t]['remaining_unknown']:,} UNKNOWN persistentes")
    lines.append("")

    lines.append("### 6. ¿Qué conceptos dominan?")
    for idx, (code, cnt) in enumerate(td[0.90]["top_codes"][:5], 1):
        concept = cbc.get(code, code)
        lines.append(f"{idx}. **{concept}** ({code}): {cnt:,} veces")
    lines.append("")

    lines.append("### 7. ¿Qué layouts recuperan más?")
    for group, cnt in td[0.90]["top_groups"][:3]:
        total_in = sum(1 for r in valid if r["group"] == group)
        pct = round(cnt / total_in * 100, 1) if total_in else 0
        lines.append(f"- **{group}**: {cnt:,}/{total_in:,} ({pct}%)")
    lines.append("")

    lines.append("### 8. ¿Qué porcentaje corresponde a OCR?")
    ocr_pct = round(ocr_total / total_unknown * 100, 1) if total_unknown else 0
    ocr_rec_pct = round(td[0.90]["ocr_count"] / ocr_total * 100, 1) if ocr_total else 0
    lines.append(f"- **{ocr_pct}%** del total UNKNOWN son OCR ({ocr_total:,} cuentas)")
    lines.append(f"- Recuperación OCR al threshold 0.90: **{ocr_rec_pct}%**")
    lines.append("")

    lines.append("### 9. Recomendación final")
    dudosos = len(review)
    lines.append(
        f"**Threshold recomendado: {best_precision_t:.2f}**\n\n"
        f"- Recupera **{bp['recovered']:,}** cuentas ({bp['pct']}% del total UNKNOWN)\n"
        f"- Deja **{bp['remaining_unknown']:,}** UNKNOWN persistentes\n"
        f"- Hay **{dudosos:,}** casos en zona dudosa para revisión manual\n"
        f"- Balance óptimo entre recuperación y precisión esperada\n"
        f"- Activación solo en shadow mode — sin impacto en clasificación oficial")
    lines.append("")

    (REPORTS_DIR / "cmcc_calibration.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print("cmcc_calibration.md generated.")


def main():
    print("=" * 60)
    print("FASE 18B — CMCC Threshold Calibration")
    print("=" * 60)

    force = "--force" in sys.argv
    rows = collect_all(force=force)
    print(f"\nAnalyzing {len(rows):,} rows...")
    analysis = analyze(rows)
    generate_reports(analysis)

    d = analysis["thresholds"]
    print(f"\nThreshold comparison:")
    for t in THRESHOLDS:
        print(f"  {t:.2f}: {d[t]['recovered']:>6,} ({d[t]['pct']:>5.1f}%)")

    print(f"\nAll reports in: {REPORTS_DIR.resolve()}")
    for p in sorted(REPORTS_DIR.iterdir()):
        sz = p.stat().st_size
        if p.name.endswith(".md"):
            print(f"  {p.name} ({sz:,} bytes)")
        elif p.name.endswith(".xlsx"):
            print(f"  {p.name} ({sz:,} bytes)")

    # Print answers directly
    print()
    print("=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    total = analysis["total_unknown"]
    review = len([r for r in analysis["all_valid"]
                  if 0.70 <= r["cmcc_score"] < 0.90])
    for rec_t in [0.98, 0.95, 0.90]:
        rec = d[rec_t]
        print(f"\nThreshold {rec_t:.2f}:")
        print(f"  Recupera: {rec['recovered']:,} ({rec['pct']}%)")
        print(f"  Quedan UNKNOWN: {rec['remaining_unknown']:,}")
        print(f"  REVIEW (0.70-0.90): {review:,}")


if __name__ == "__main__":
    main()
