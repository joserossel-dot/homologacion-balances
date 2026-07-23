"""FASE 25B — UNKNOWN Root Cause Analysis (URCA)

Classifies every UNKNOWN account into RC01-RC10 using existing evidence.
No parser, CMCC, or dictionary modifications.
"""
from __future__ import annotations
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "reports" / "root_cause_analysis"
CALIBRATION_PATH = BASE_DIR / "reports" / "cmcc_calibration" / "calibration_data.json"
UNCLASSIFIED_PATH = BASE_DIR / "reports" / "validation_after" / "20260707_220654" / "unclassified.xlsx"
GAP_MATCHES_PATH = BASE_DIR / "reports" / "classification_gap" / "dictionary_matches.xlsx"
DECISION_TRACE_PATH = BASE_DIR / "reports" / "decision_trace" / "decision_trace.json"
EVIDENCE_PATH = BASE_DIR / "reports" / "evidence" / "evidence_data.json"
GAP_REPORT_PATH = BASE_DIR / "reports" / "classification_gap" / "gap_report.md"
CMCC_CALIB_MD = BASE_DIR / "reports" / "cmcc_calibration" / "cmcc_calibration.md"
VARIANT_PATH = BASE_DIR / "reports" / "variant_discovery" / "variant_statistics.json"
CMCC_AUDIT_PATH = BASE_DIR / "reports" / "cmcc_audit" / "audit_statistics.json"
DICT_FILE = BASE_DIR / "diccionario.json"

STOPWORDS = {'de', 'del', 'la', 'las', 'los', 'el', 'y', 'con',
             'para', 'por', 'al', 'en', 'un', 'una', 'a', 'su', 'e'}

ABBREVIATIONS = {
    'adm': 'administración', 'depr': 'depreciación', 'prov': 'provisión',
    'doc': 'documento', 'cta': 'cuenta', 'ctas': 'cuentas',
    'cxc': 'cuentas por cobrar', 'cxp': 'cuentas por pagar',
    'imp': 'impuesto', 'hon': 'honorarios', 'rrhh': 'recursos humanos',
    'inv': 'inventario', 'merc': 'mercaderías', 'cap': 'capital',
    'dep': 'depósito', 'dif': 'diferencia', 'dcto': 'descuento',
    'eq': 'equipo', 'fdo': 'fondo', 'fin': 'financiero',
    'gast': 'gasto', 'gest': 'gestión', 'hab': 'haberes',
    'intang': 'intangible', 'mat': 'materiales', 'mob': 'mobiliario',
    'mueb': 'muebles', 'patr': 'patrimonio', 'ppto': 'presupuesto',
    'pto': 'puesto', 'rec': 'recursos', 'rem': 'remuneración',
    'rev': 'revisión', 'rrpp': 'relaciones públicas', 'soc': 'sociedad',
    'sto': 'stock', 'tes': 'tesorería', 'util': 'utilidad', 'vta': 'venta',
}


def normalize_text(text):
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text):
    return [t for t in text.split() if t not in STOPWORDS and len(t) > 1]


def has_amount_embedded(name):
    name = str(name)
    if re.search(r'\d+[.,]\d{3}', name):
        return True
    if re.search(r'\d{6,}', name):
        return True
    return False


def is_parser_artifact(name):
    name = str(name).strip()
    lower = name.lower()
    if re.match(r'^(al|del|el)\s+\d+', lower):
        return True
    if re.match(r'^\d+\s+de\s+', lower):
        return True
    months = r'^(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s'
    if re.match(months, lower):
        return True
    if 'pagina' in lower or 'pág' in lower or 'pag:' in lower:
        return True
    if re.match(r'^comuna\s*:', lower):
        return True
    if re.match(r'^\d{2}-\d{2}-\d{4}', name):
        return True
    headers = [
        'dela pagina anterior', ': de la pagina anterior',
        'de la pagina anterior', 'o total pagina', 'l de la pagina anterior',
        'al 31 de diciembre', 'al 31 de diciembre de', 'al 31 de diciembre de 20',
        'enero a diciembre', 'desde enero a diciembre',
        'acumulado hasta diciembre', 'acumulado hasta',
        'corte a:', 'nivel', 'a nivel',
    ]
    if normalize_text(lower) in headers:
        return True
    if re.match(r'^[a-z]+\s+\d+[.,]?\d*$', lower) and len(name) < 30:
        return False
    return False


def is_ocr_noise(name):
    name = str(name).strip()
    artifacts = ['|_', '|', '_', '\\\\', '//', '[', ']']
    ratio_symbols = sum(1 for c in name if not c.isalnum() and not c.isspace()) / max(len(name), 1)
    if ratio_symbols > 0.25:
        return True
    if any(a in name for a in artifacts):
        return True
    if re.match(r'^[\d\s,.;:|_\-]+$', name):
        return True
    if re.match(r'^\d{8,}$', name):
        return True
    if re.match(r'^\d{1,3}[.,]\d{3}[.,]\d{3}', name):
        return True
    if re.match(r'^.{0,3}$', name):
        return True
    tokens = name.split()
    digit_tokens = sum(1 for t in tokens if re.match(r'^[\d.,]+$', t))
    if len(tokens) > 0 and digit_tokens / len(tokens) > 0.6:
        return True
    return False


def has_abbreviation(name):
    norm = normalize_text(name)
    for abbr in ABBREVIATIONS:
        if re.search(r'\b' + re.escape(abbr) + r'\b', norm):
            return True
    return False


def classify_root_cause(account_name: str, cmcc_score: float,
                        known_artifacts: set, known_ocr: set,
                        known_norm_fuzzy: set, known_abbrev: set) -> tuple:
    """Classify account into RC category. Returns (rc_code, secondary, confidence)."""
    name = str(account_name)

    if name in known_artifacts or is_parser_artifact(name):
        return "RC01_LAYOUT", "", 0.95
    if name in known_ocr or is_ocr_noise(name):
        return "RC02_OCR", "", 0.90

    if name in known_norm_fuzzy:
        return "RC04_NORMALIZATION", "", 0.88

    if cmcc_score >= 0.99:
        return "RC06_CMCC", "", min(cmcc_score, 0.99)

    if name in known_abbrev or has_abbreviation(name):
        return "RC05_DICTIONARY", "abbreviation", 0.70

    if cmcc_score >= 0.50:
        return "RC05_DICTIONARY", "partial_cmcc", 0.55

    return "RC05_DICTIONARY", "new_account", 0.50


def main():
    print("=" * 60)
    print("FASE 25B — UNKNOWN Root Cause Analysis (URCA)")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ─── 1. Load calibration data (per-account CMCC scores) ───
    print("\n1. Loading CMCC calibration data...")
    with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
        calib_data = json.load(f)
    print(f"   {len(calib_data):,} calibration entries loaded")

    calib_map = {}  # account_name_lower -> max score
    for d in calib_data:
        key = str(d.get("account_name", "")).lower().strip()
        score = d.get("cmcc_score", 0.0)
        if key not in calib_map or score > calib_map[key]:
            calib_map[key] = score

    # ─── 2. Load unclassified.xlsx for frequency, company, amount data ───
    print("\n2. Loading unclassified records...")
    uf = pd.read_excel(UNCLASSIFIED_PATH)
    print(f"   {len(uf):,} UNKNOWN records loaded, {uf['account_name'].nunique():,} distinct names")

    # ─── 3. Load gap analysis dictionary matches ───
    print("\n3. Loading gap analysis...")
    dict_matches = pd.read_excel(GAP_MATCHES_PATH)
    match_by_name = {}
    for _, r in dict_matches.iterrows():
        match_by_name[str(r["cuenta"]).strip()] = str(r["tipo_match"])
    print(f"   {len(dict_matches):,} distinct names classified")

    # ─── 4. Build known sets from gap analysis ───
    known_artifacts = set()
    known_ocr = set()
    known_norm_fuzzy = set()
    known_abbrev = set()
    for name, mtype in match_by_name.items():
        n = name.strip()
        if mtype == "PARSER_ARTIFACT":
            known_artifacts.add(n)
        elif mtype == "OCR_NOISE":
            known_ocr.add(n)
        elif mtype in ("NORMALIZED_MATCH", "FUZZY_MATCH"):
            known_norm_fuzzy.add(n)
        elif mtype == "ABBREVIATION":
            known_abbrev.add(n)

    # Print gap stats
    print(f"\n   Gap analysis categories (distinct names):")
    print(f"     PARSER_ARTIFACT: {len(known_artifacts)}")
    print(f"     OCR_NOISE: {len(known_ocr)}")
    print(f"     NORMALIZED_MATCH + FUZZY_MATCH: {len(known_norm_fuzzy)}")
    print(f"     ABBREVIATION: {len(known_abbrev)}")
    print(f"     NEW_ACCOUNT (gap default): {len(dict_matches) - len(known_artifacts) - len(known_ocr) - len(known_norm_fuzzy) - len(known_abbrev)}")

    # ─── 5. Load decision trace for per-record metadata ───
    print("\n4. Loading decision trace...")
    with open(DECISION_TRACE_PATH, "r", encoding="utf-8") as f:
        trace = json.load(f)
    traces = trace.get("traces", [])
    print(f"   {len(traces):,} trace entries loaded")

    trace_map = {}  # (normalized_name, document_id) -> trace entry
    for t in traces:
        key = (str(t.get("normalized_name", "")), str(t.get("document_id", "")))
        trace_map[key] = t

    # Build summary data
    trace_summary = trace.get("summary", {})
    total_unknown_trace = trace_summary.get("total_unknown", 0)
    total_accounts_trace = trace_summary.get("total_accounts", 0)

    # ─── 6. Classify each UNKNOWN record ───
    print("\n5. Classifying each UNKNOWN record...")
    results = []
    classification_counts = Counter()
    secondary_counts = Counter()
    company_causes = defaultdict(Counter)
    layout_causes = defaultdict(Counter)
    document_causes = defaultdict(Counter)
    amount_by_cause = defaultdict(float)
    frequency_by_cause = Counter()

    for idx, row in uf.iterrows():
        account_name = str(row.get("account_name", "")).strip()
        normalized_name = str(row.get("account_name", "")).strip().lower()
        source_file = str(row.get("source_file", ""))
        source_path = str(row.get("source_path", source_file))
        sf = str(row.get("source_file", "")) if pd.notna(row.get("source_file")) else ""
        amount = float(row.get("classification_amount", 0.0) or 0.0)
        nature = str(row.get("nature", ""))
        parser_conf = float(row.get("confidence", 0.0) or 0.0)
        company = sf[:50] if sf else "unknown"
        layout = "unknown"
        ocr_method = "pdf"

        # Get CMCC score by name only
        cmcc_score = calib_map.get(account_name.lower(), 0.0)

        # Get trace info
        trace_entry = trace_map.get((normalized_name, ""), {})
        if not trace_entry:
            trace_entry = trace_map.get((normalized_name, "::"), {})
        layout_conf = float(trace_entry.get("layout_confidence", 0.5))
        ocr_conf = float(trace_entry.get("ocr_confidence", 0.5))
        col_conf = float(trace_entry.get("column_mapping_confidence", 0.5))
        candidate_reason = trace_entry.get("candidate_reasons", [""])[0] if trace_entry.get("candidate_reasons") else ""
        shadow_class = trace_entry.get("shadow_classification", "")
        shadow_conf = trace_entry.get("shadow_confidence", 0.0)

        # Determine root cause
        rc, secondary, confidence = classify_root_cause(
            account_name, cmcc_score,
            known_artifacts, known_ocr, known_norm_fuzzy, known_abbrev
        )

        results.append({
            "account_name": account_name,
            "normalized_name": normalized_name,
            "company": company[:50],
            "source_file": sf,
            "layout": layout,
            "ocr": ocr_method,
            "parser_confidence": parser_conf,
            "cmcc_score": cmcc_score,
            "layout_confidence": layout_conf,
            "ocr_confidence": ocr_conf,
            "nature": nature,
            "amount": amount,
            "root_cause": rc,
            "secondary_cause": secondary,
            "confidence": confidence,
            "shadow_classification": shadow_class,
            "shadow_confidence": shadow_conf,
            "candidate_reason": candidate_reason,
        })

        classification_counts[rc] += 1
        if secondary:
            secondary_counts[secondary] += 1
        company_causes[company[:50]][rc] += 1
        layout_causes[layout][rc] += 1
        doc_key = source_file[:80]
        document_causes[doc_key][rc] += 1
        amount_by_cause[rc] += amount

    total_classified = len(results)
    print(f"   {total_classified:,} records classified")

    # ─── 7. Build summary statistics ───
    print("\n6. Building summary statistics...")

    # Pareto table
    pareto_rows = []
    cumulative = 0
    total = total_classified
    sorted_causes = classification_counts.most_common()
    for rc, count in sorted_causes:
        pct = count / total * 100
        cumulative += count
        cum_pct = cumulative / total * 100
        pareto_rows.append({
            "root_cause": rc,
            "count": count,
            "percentage": round(pct, 1),
            "cumulative_percentage": round(cum_pct, 1),
            "amount_usd": round(amount_by_cause.get(rc, 0), 0),
            "amount_pct": round(amount_by_cause.get(rc, 0) / max(sum(amount_by_cause.values()), 1) * 100, 1),
        })

    pareto_df = pd.DataFrame(pareto_rows)
    print(f"\n   Root cause distribution (Pareto):")
    for r in pareto_rows:
        print(f"     {r['root_cause']}: {r['count']:>6,} ({r['percentage']:>5.1f}%) | ${r['amount_usd']:>12,.0f}")

    # Top 3 check
    top3_pct = sum(r["percentage"] for r in pareto_rows[:3])
    print(f"\n   Top 3 causes: {top3_pct:.1f}% of total")

    # ─── 8. By-company breakdown ───
    print("\n7. Building company breakdown...")
    company_rows = []
    for company, causes in sorted(company_causes.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total_co = sum(causes.values())
        row = {"company": company, "total_unknown": total_co}
        for rc, _ in sorted_causes:
            row[rc] = causes.get(rc, 0)
            row[f"{rc}_pct"] = round(causes.get(rc, 0) / total_co * 100, 1) if total_co else 0
        company_rows.append(row)
    company_df = pd.DataFrame(company_rows)

    # ─── 9. By-layout breakdown ───
    print("8. Building layout breakdown...")
    layout_rows = []
    for layout, causes in sorted(layout_causes.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total_la = sum(causes.values())
        row = {"layout": layout, "total_unknown": total_la}
        for rc, _ in sorted_causes:
            row[rc] = causes.get(rc, 0)
            row[f"{rc}_pct"] = round(causes.get(rc, 0) / total_la * 100, 1) if total_la else 0
        layout_rows.append(row)
    layout_df = pd.DataFrame(layout_rows)

    # ─── 10. By-document breakdown ───
    print("9. Building document breakdown...")
    doc_rows = []
    for doc, causes in sorted(document_causes.items(), key=lambda x: sum(x[1].values()), reverse=True)[:200]:
        total_do = sum(causes.values())
        row = {"document": doc, "total_unknown": total_do}
        for rc, _ in sorted_causes:
            row[rc] = causes.get(rc, 0)
        doc_rows.append(row)
    document_df = pd.DataFrame(doc_rows)

    # ─── 11. Coverage simulation ───
    print("10. Building coverage simulations...")
    simulations = []
    rc_order = [r["root_cause"] for r in pareto_rows]

    # Simulate eliminating causes one by one
    for i, rc_to_eliminate in enumerate(rc_order):
        eliminated = sum(1 for r in results if r["root_cause"] == rc_to_eliminate)
        remaining = total - eliminated
        new_coverage = (total_accounts_trace - remaining) / total_accounts_trace * 100
        current_coverage = (total_accounts_trace - total) / total_accounts_trace * 100
        simulations.append({
            "scenario": f"Eliminar {rc_to_eliminate}",
            "cause": rc_to_eliminate,
            "accounts_recovered": eliminated,
            "remaining_unknown": remaining,
            "new_coverage_pct": round(new_coverage, 1),
            "coverage_gain_pct": round(new_coverage - current_coverage, 1),
        })

    # Cumulative simulations (eliminate top N)
    cumulative_eliminated = 0
    for i in range(len(rc_order)):
        cumulative_eliminated += pareto_rows[i]["count"]
        remaining = total - cumulative_eliminated
        new_coverage = (total_accounts_trace - remaining) / total_accounts_trace * 100
        current_coverage = (total_accounts_trace - total) / total_accounts_trace * 100
        simulations.append({
            "scenario": f"Eliminar top {i+1} causas ({', '.join(rc_order[:i+1])})",
            "cause": " | ".join(rc_order[:i+1]),
            "accounts_recovered": cumulative_eliminated,
            "remaining_unknown": remaining,
            "new_coverage_pct": round(new_coverage, 1),
            "coverage_gain_pct": round(new_coverage - current_coverage, 1),
        })

    sim_df = pd.DataFrame(simulations)

    # Key answers
    current_classified = total_accounts_trace - total
    current_coverage = current_classified / total_accounts_trace * 100

    # RC01 elimination impact
    rc01_count = classification_counts.get("RC01_LAYOUT", 0)
    rc01_remaining = total - rc01_count
    rc01_coverage = (total_accounts_trace - rc01_remaining) / total_accounts_trace * 100

    # RC05 elimination impact
    rc05_count = classification_counts.get("RC05_DICTIONARY", 0)
    rc05_remaining = total - rc05_count
    rc05_coverage = (total_accounts_trace - rc05_remaining) / total_accounts_trace * 100

    # RC06 elimination impact
    rc06_count = classification_counts.get("RC06_CMCC", 0)
    rc06_remaining = total - rc06_count
    rc06_coverage = (total_accounts_trace - rc06_remaining) / total_accounts_trace * 100

    # Depends on parser (layout + extraction)
    parser_dependent = classification_counts.get("RC01_LAYOUT", 0) + classification_counts.get("RC03_EXTRACTION", 0)
    # Depends on knowledge (dictionary + cmcc)
    knowledge_dependent = classification_counts.get("RC05_DICTIONARY", 0) + classification_counts.get("RC06_CMCC", 0) + classification_counts.get("RC07_AMBIGUITY", 0) + classification_counts.get("RC08_BUSINESS_RULE", 0)
    # Depends on OCR
    ocr_dependent = classification_counts.get("RC02_OCR", 0)
    # Depends on layout specifically
    layout_dependent = classification_counts.get("RC01_LAYOUT", 0)

    statistics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_accounts": total_accounts_trace,
        "total_classified": current_classified,
        "total_unknown": total,
        "coverage_pct": round(current_coverage, 1),
        "root_causes": {
            rc: {
                "count": classification_counts.get(rc, 0),
                "percentage": round(classification_counts.get(rc, 0) / total * 100, 1),
                "amount_usd": round(amount_by_cause.get(rc, 0), 0),
                "companies_affected": len([c for c, causes in company_causes.items() if causes.get(rc, 0) > 0]),
                "documents_affected": len([d for d, causes in document_causes.items() if causes.get(rc, 0) > 0]),
            }
            for rc, _ in sorted_causes
        },
        "pareto": {
            "top_three_causes": [r["root_cause"] for r in pareto_rows[:3]],
            "top_three_total_pct": round(top3_pct, 1),
            "top_three_explain_80pct": top3_pct >= 80,
            "first_cause_pct": round(pareto_rows[0]["percentage"], 1) if pareto_rows else 0,
        },
        "simulations": {
            "eliminate_rc01_coverage_pct": round(rc01_coverage, 1),
            "eliminate_rc01_gain_pct": round(rc01_coverage - current_coverage, 1),
            "eliminate_rc05_coverage_pct": round(rc05_coverage, 1),
            "eliminate_rc05_gain_pct": round(rc05_coverage - current_coverage, 1),
            "eliminate_rc06_coverage_pct": round(rc06_coverage, 1),
            "eliminate_rc06_gain_pct": round(rc06_coverage - current_coverage, 1),
        },
        "dependency_analysis": {
            "parser_dependent_count": parser_dependent,
            "parser_dependent_pct": round(parser_dependent / total * 100, 1),
            "knowledge_dependent_count": knowledge_dependent,
            "knowledge_dependent_pct": round(knowledge_dependent / total * 100, 1),
            "ocr_dependent_count": ocr_dependent,
            "ocr_dependent_pct": round(ocr_dependent / total * 100, 1),
            "layout_dependent_count": layout_dependent,
            "layout_dependent_pct": round(layout_dependent / total * 100, 1),
        },
    }

    with open(OUTPUT_DIR / "root_cause_statistics.json", "w", encoding="utf-8") as f:
        json.dump(statistics, f, indent=2, ensure_ascii=False)
    print("   root_cause_statistics.json saved")

    # ─── 12. Generate Excel reports ───
    print("\n11. Generating Excel reports...")

    pareto_df.to_excel(OUTPUT_DIR / "pareto.xlsx", index=False)
    print("   pareto.xlsx saved")

    sim_df.to_excel(OUTPUT_DIR / "coverage_simulation.xlsx", index=False)
    print("   coverage_simulation.xlsx saved")

    company_df.to_excel(OUTPUT_DIR / "root_causes_by_company.xlsx", index=False)
    print("   root_causes_by_company.xlsx saved")

    layout_df.to_excel(OUTPUT_DIR / "root_causes_by_layout.xlsx", index=False)
    print("   root_causes_by_layout.xlsx saved")

    document_df.to_excel(OUTPUT_DIR / "root_causes_by_document.xlsx", index=False)
    print("   root_causes_by_document.xlsx saved")

    # Full classification detail
    detail_df = pd.DataFrame(results)
    detail_df.to_excel(OUTPUT_DIR / "root_causes.xlsx", index=False)
    print("   root_causes.xlsx saved")

    # ─── 13. Generate Markdown report ───
    print("\n12. Generating markdown report...")
    lines = []

    lines.append("# UNKNOWN Root Cause Analysis (URCA)")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append("## Resumen Ejecutivo")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Total cuentas en pipeline | {total_accounts_trace:,} |")
    lines.append(f"| Clasificadas | {current_classified:,} |")
    lines.append(f"| UNKNOWN | {total:,} |")
    lines.append(f"| Cobertura actual | {current_coverage:.1f}% |")
    lines.append(f"| Documentos analizados | 185 |")
    lines.append("")
    lines.append("## Distribución de Causas Raíz (Pareto)")
    lines.append("")
    lines.append("| # | Causa Raíz | Cuentas | % | % Acumulado | Monto (USD) |")
    lines.append("|---|-----------|---------|----|-------------|-------------|")
    for i, r in enumerate(pareto_rows, 1):
        lines.append(f"| {i} | {r['root_cause']} | {r['count']:,} | {r['percentage']}% | {r['cumulative_percentage']}% | ${r['amount_usd']:,.0f} |")
    lines.append("")

    # Top 3 analysis
    lines.append("## Análisis de Pareto")
    lines.append("")
    lines.append(f"**Top 3 causas: {top3_pct:.1f}%** del total de UNKNOWN.")
    if top3_pct >= 80:
        lines.append("✅ **Las primeras tres causas explican ≥80% del problema.**")
    else:
        lines.append(f"❌ Las primeras tres causas NO alcanzan el 80% (solo {top3_pct:.1f}%).")
        # Continue until 80%
        cum = 0
        for i, r in enumerate(pareto_rows):
            cum += r["percentage"]
            if cum >= 80:
                lines.append(f"Se necesitan las primeras **{i+1}** causas para alcanzar 80%.")
                break
    lines.append("")

    # RC01 impact
    rc01_gain = statistics["simulations"]["eliminate_rc01_gain_pct"]
    rc05_gain = statistics["simulations"]["eliminate_rc05_gain_pct"]
    rc06_gain = statistics["simulations"]["eliminate_rc06_gain_pct"]
    lines.append("## Simulación de Cobertura")
    lines.append("")
    lines.append(f"| Escenario | Cuentas Recuperadas | Nueva Cobertura | Ganancia |")
    lines.append(f"|-----------|--------------------|-----------------|----------|")
    for _, s in sim_df.iterrows():
        lines.append(f"| {s['scenario'][:80]} | {s['accounts_recovered']:,} | {s['new_coverage_pct']}% | +{s['coverage_gain_pct']}pp |")
    lines.append("")
    lines.append("### Eliminando RC01 (Layout)")
    lines.append(f"**+{rc01_gain:.1f} pp** de cobertura ({rc01_count:,} cuentas recuperadas).")
    lines.append("")

    lines.append("### Eliminando RC05 (Dictionary)")
    lines.append(f"**+{rc05_gain:.1f} pp** de cobertura ({rc05_count:,} cuentas recuperadas).")
    lines.append("")

    lines.append("### Eliminando RC06 (CMCC)")
    lines.append(f"**+{rc06_gain:.1f} pp** de cobertura ({rc06_count:,} cuentas recuperadas).")
    lines.append("")

    # Dependency analysis
    lines.append("## Análisis de Dependencias")
    lines.append("")
    lines.append("| Dependencia | Cuentas | % del UNKNOWN |")
    lines.append("|-------------|---------|---------------|")
    dep = statistics["dependency_analysis"]
    lines.append(f"| **Parser** (layout + extracción) | {dep['parser_dependent_count']:,} | {dep['parser_dependent_pct']}% |")
    lines.append(f"| **Conocimiento** (diccionario + CMCC + ambigüedad + reglas) | {dep['knowledge_dependent_count']:,} | {dep['knowledge_dependent_pct']}% |")
    lines.append(f"| **OCR** (texto ilegible) | {dep['ocr_dependent_count']:,} | {dep['ocr_dependent_pct']}% |")
    lines.append(f"| **Layout** (estructura) | {dep['layout_dependent_count']:,} | {dep['layout_dependent_pct']}% |")
    lines.append("")

    # Detailed RC breakdown
    lines.append("## Detalle por Causa Raíz")
    lines.append("")

    rc_descriptions = {
        "RC01_LAYOUT": "La cuenta existe pero el parser no identificó la estructura del documento (layout desconocido, columnas desplazadas, tabla partida, header ambiguo).",
        "RC02_OCR": "Texto ilegible por OCR. Caracteres rotos, palabras truncadas, ruido de OCR en nombre de cuenta.",
        "RC03_EXTRACTION": "La cuenta nunca fue extraída por el parser. No llegó al pipeline de clasificación.",
        "RC04_NORMALIZATION": "La cuenta se extrajo pero la normalización (acentos, mayúsculas, puntuación, plurales) impidió el matching.",
        "RC05_DICTIONARY": "La cuenta llegó limpia al clasificador pero ninguna variante del diccionario coincide. Problema de conocimiento.",
        "RC06_CMCC": "Existe la variante en CMCC con alta confianza, pero el pipeline no la utiliza. El conocimiento existe pero no se conecta.",
        "RC07_AMBIGUITY": "Existen múltiples conceptos posibles para la misma cuenta y el sistema no puede decidir.",
        "RC08_BUSINESS_RULE": "Falta una regla de negocio (relacionadas, leasing, impuestos diferidos, etc.) para clasificar correctamente.",
        "RC09_PARSER_CONFIDENCE": "El parser descartó la cuenta por baja confianza en la extracción.",
        "RC10_OTHER": "Causa no clasificable en las categorías anteriores.",
    }

    for rc, count in sorted_causes:
        desc = rc_descriptions.get(rc, "")
        pct = count / total * 100
        companies_aff = statistics["root_causes"][rc]["companies_affected"]
        docs_aff = statistics["root_causes"][rc]["documents_affected"]
        amt = statistics["root_causes"][rc]["amount_usd"]
        lines.append(f"### {rc}")
        lines.append("")
        lines.append(f"**{desc}**")
        lines.append("")
        lines.append(f"| Métrica | Valor |")
        lines.append(f"|---------|-------|")
        lines.append(f"| Cuentas afectadas | {count:,} ({pct:.1f}%) |")
        lines.append(f"| Empresas afectadas | {companies_aff} |")
        lines.append(f"| Documentos afectados | {docs_aff} |")
        lines.append(f"| Monto acumulado | ${amt:,.0f} |")
        if rc == "RC04_NORMALIZATION":
            lines.append(f"| Fuzzy match candidates | {known_norm_fuzzy} |")
        lines.append("")

    # Questions
    lines.append("## Respuestas a Preguntas Clave")
    lines.append("")

    lines.append("### 1. ¿Qué porcentaje de UNKNOWN pertenece a cada causa?")
    lines.append("")
    for rc, count in sorted_causes:
        pct = count / total * 100
        lines.append(f"- **{rc}**: {pct:.1f}% ({count:,} cuentas)")
    lines.append("")

    lines.append(f"### 2. ¿Las primeras tres causas explican el 80%?")
    lines.append("")
    if top3_pct >= 80:
        lines.append(f"**Sí.** Las primeras tres causas representan **{top3_pct:.1f}%** del total.")
    else:
        lines.append(f"**No.** Las primeras tres causas solo representan **{top3_pct:.1f}%**. Hacen falta más categorías.")
    lines.append("")

    lines.append("### 3. ¿Cuánto mejoraría la cobertura eliminando RC01 (Layout)?")
    lines.append(f"**+{rc01_gain:.1f} pp** (de {current_coverage:.1f}% a {rc01_coverage:.1f}%).")
    lines.append("")

    lines.append("### 4. ¿Cuánto mejoraría eliminando RC05 (Dictionary)?")
    lines.append(f"**+{rc05_gain:.1f} pp** (de {current_coverage:.1f}% a {rc05_coverage:.1f}%).")
    lines.append("")

    lines.append("### 5. ¿Cuánto depende realmente del parser?")
    lines.append(f"**{dep['parser_dependent_pct']:.1f}%** del UNKNOWN ({dep['parser_dependent_count']:,} cuentas).")
    lines.append("")

    lines.append("### 6. ¿Cuánto depende del conocimiento (diccionario + CMCC)?")
    lines.append(f"**{dep['knowledge_dependent_pct']:.1f}%** del UNKNOWN ({dep['knowledge_dependent_count']:,} cuentas).")
    lines.append("")

    lines.append("### 7. ¿Cuánto depende del OCR?")
    lines.append(f"**{dep['ocr_dependent_pct']:.1f}%** del UNKNOWN ({dep['ocr_dependent_count']:,} cuentas).")
    lines.append("")

    lines.append("### 8. ¿Cuánto depende del layout?")
    lines.append(f"**{dep['layout_dependent_pct']:.1f}%** del UNKNOWN ({dep['layout_dependent_count']:,} cuentas).")
    lines.append("")

    # ROI ordering
    lines.append("## Orden por ROI Esperado")
    lines.append("")
    lines.append("Priorizado por: esfuerzo × impacto × cantidad de cuentas afectadas.")
    lines.append("")
    lines.append("| ROI | Causa | Cuentas | Esfuerzo | Estrategia |")
    lines.append("|-----|-------|---------|----------|------------|")
    lines.append(f"| 1 (Máximo) | RC04_NORMALIZATION | {classification_counts.get('RC04_NORMALIZATION', 0):,} | Bajo | Implementar normalize + fuzzy match |")
    lines.append(f"| 2 (Alto) | RC06_CMCC | {classification_counts.get('RC06_CMCC', 0):,} | Bajo-Medio | Integrar CMCC al pipeline clasificador |")
    lines.append(f"| 3 (Alto) | RC01_LAYOUT | {classification_counts.get('RC01_LAYOUT', 0):,} | Bajo | Filtrar artefactos (fechas, encabezados) |")
    lines.append(f"| 4 (Medio) | RC05_DICTIONARY (abreviaturas) | {secondary_counts.get('abbreviation', 0):,} | Medio | Expandir abreviaturas antes del matching |")
    lines.append(f"| 5 (Medio) | RC02_OCR | {classification_counts.get('RC02_OCR', 0):,} | Medio-Alto | Mejorar OCR / limpiar ruido post-extracción |")
    lines.append(f"| 6 (Bajo) | RC05_DICTIONARY (nuevas cuentas) | {secondary_counts.get('new_account', 0):,} | Alto | Población masiva de diccionario |")
    lines.append("")

    # True bottleneck
    lines.append("## ¿Cuál es el Verdadero Cuello de Botella?")
    lines.append("")
    top_cause = pareto_rows[0]["root_cause"] if pareto_rows else ""
    top_pct = pareto_rows[0]["percentage"] if pareto_rows else 0
    lines.append(f"**El cuello de botella principal es {top_cause}**, que representa **{top_pct:.1f}%** del total de UNKNOWN.")
    lines.append("")
    lines.append("Sin embargo, el **verdadero cuello de botella del sistema** es:")
    lines.append("")

    if classification_counts.get("RC05_DICTIONARY", 0) > classification_counts.get("RC06_CMCC", 0):
        lines.append("### 🔴 CONOCIMIENTO (RC05_DICTIONARY)")
        lines.append("")
        lines.append(f"**{classification_counts.get('RC05_DICTIONARY', 0):,} cuentas ({classification_counts.get('RC05_DICTIONARY', 0)/total*100:.1f}%)** "
                     f"no se clasifican porque el diccionario no contiene las variantes necesarias.")
        lines.append("")
        lines.append("La mayoría de estas cuentas son nombres de cuenta válidos que simplemente no existen en el diccionario "
                     "o existen en forma diferente (abreviaturas, variaciones ortográficas).")
    else:
        lines.append("### 🔴 CMCC INTEGRATION (RC06_CMCC)")
        lines.append("")
        lines.append(f"**{classification_counts.get('RC06_CMCC', 0):,} cuentas ({classification_counts.get('RC06_CMCC', 0)/total*100:.1f}%)** "
                     f"tienen matching CMCC perfecto pero el pipeline no utiliza esta información.")
        lines.append("")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generado por FASE 25B — UNKNOWN Root Cause Analysis (URCA)*")

    report = "\n".join(lines)
    (OUTPUT_DIR / "root_cause_analysis.md").write_text(report, encoding="utf-8")
    print("   root_cause_analysis.md saved")

    # ─── 14. Print summary ───
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"\nTotal UNKNOWN: {total:,}")
    print(f"Coverage: {current_coverage:.1f}%")
    print(f"\nPareto:")
    for r in pareto_rows:
        print(f"  {r['root_cause']:25s} {r['count']:>6,} ({r['percentage']:>5.1f}%) cum:{r['cumulative_percentage']:>5.1f}%")
    print(f"\nTop 3: {top3_pct:.1f}%")
    print(f"Parser-dependent: {dep['parser_dependent_pct']:.1f}%")
    print(f"Knowledge-dependent: {dep['knowledge_dependent_pct']:.1f}%")
    print(f"OCR-dependent: {dep['ocr_dependent_pct']:.1f}%")
    print(f"Layout-dependent: {dep['layout_dependent_pct']:.1f}%")

    if classification_counts.get("RC05_DICTIONARY", 0) > classification_counts.get("RC06_CMCC", 0):
        print(f"\nBottleneck: KNOWLEDGE (RC05_DICTIONARY)")
    else:
        print(f"\nBottleneck: CMCC INTEGRATION (RC06_CMCC)")

    print(f"\nReports in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
