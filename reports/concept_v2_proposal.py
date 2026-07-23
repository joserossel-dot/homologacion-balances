"""Genera propuesta de conceptos v2 analizando los 6995 UNKNOWN.

No modifica el catálogo actual.
Solo genera evidencia y propuesta.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPORT_DIR = Path(__file__).resolve().parent
BENCH_PATH = REPORT_DIR / "semantic_matcher_v1.json"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "concept_catalog.json"

OUT_JSON = REPORT_DIR / "concept_catalog_v2_proposal.json"
OUT_MD = REPORT_DIR / "concept_catalog_v2_proposal.md"
OUT_XLSX = REPORT_DIR / "concept_catalog_v2_proposal.xlsx"


def load_results():
    with open(BENCH_PATH) as f:
        return json.load(f)["results"]


def load_catalog():
    with open(CATALOG_PATH) as f:
        return json.load(f)


# ── Concept proposals ──────────────────────────────────────────────
# Each proposal defines a pattern to match, target code, type,
# and expected incremental coverage over existing SM concepts.

PROPOSALS = [
    # (name, code, type, regex_pattern, expected_incremental_coverage)
    ("DEUDORES_VARIOS", "AC.03", "ACTIVO",
     r'deudore?s?\s*(varios?|div[eo]rsos?)?', 103),
    ("SUELDOS", "PC.06", "PASIVO",
     r'\bsueldos?\b', 79),
    ("IVA", "AC.07", "ACTIVO",
     r'\biva\b', 71),
    ("REAJUSTE", "ER.11", "PERDIDA",
     r'\breajuste', 63),
    ("ACTIVO_FIJO", "ANC.01", "ACTIVO",
     r'activ\w*\s*fij', 46),
    ("ACREEDORES_VARIOS", "PC.08", "PASIVO",
     r'acreedore?s?\s*(varios?|div[eo]rsos?)?', 40),
    ("LINEA_CREDITO", "PC.02", "PASIVO",
     r'l[íi]nea\s*(de\s*)?cr[eé]dit', 37),
    ("LEASING", "ANC.03", "ACTIVO",
     r'\bleas', 36),
    ("COMISIONES", "PC.06", "PASIVO",
     r'comisiones?', 29),
    ("HONORARIOS", "PC.06", "PASIVO",
     r'\bhonorarios?\b', 29),
    ("PPM", "AC.07", "ACTIVO",
     r'\bppm\b', 29),
    ("CONSTRUCCIONES", "ANC.01", "ACTIVO",
     r'construccion', 27),
    ("FONDOS_MUTUOS", "ANC.04", "ACTIVO",
     r'fondos?\s*mutuo', 27),
    ("PATENTES", "ER.04", "PERDIDA",
     r'patente\w*\s*(municipal|comercial)?', 25),
    ("TARJETA_CREDITO", "PC.02", "PASIVO",
     r'tarjeta\s*(de\s*)?cr[eé]dit', 24),
    ("IMPUESTOS_DIFERIDOS", "AC.07", "ACTIVO",
     r'impuestos?\s*diferidos?', 22),
    ("CAPACITACION", "ER.04", "PERDIDA",
     r'capacitaci[oó]n', 16),
    ("INMUEBLES", "ANC.01", "ACTIVO",
     r'inmuebl', 13),
    ("HERRAMIENTAS", "ANC.05", "ACTIVO",
     r'herramient', 12),
    ("DIFERENCIA_CAMBIO", "ER.05", "PERDIDA",
     r'diferencia?\s*cambi', 9),
    ("PRESTAMO_HIPOTECARIO", "PNC.01", "PASIVO",
     r'(pr[eé]stamo|cr[eé]dito)\s*hipotec', 8),
    ("CAPITAL_SOCIAL", "PAT.01", "PATRIMONIO",
     r'capital\s*social', 8),
    ("ANTICIPOS", "AC.07", "ACTIVO",
     r'anticipos?\s*(proveedor|cliente)', 7),
    ("MANO_OBRA", "ER.04", "PERDIDA",
     r'mano\s*de\s*obra', 5),
    ("RESULTADO_EJERCICIO", "ER.11", "PERDIDA",
     r'resultad\w*\s*(ejercicio|del\s*ejercicio)', 6),
    ("INSTALACIONES", "ANC.03", "ACTIVO",
     r'instalaciones?', 4),
    ("PRESTAMO_BANCARIO", "PC.02", "PASIVO",
     r'pr[eé]stamo\s*bancar', 3),
    ("GASTOS_GENERALES", "ER.04", "PERDIDA",
     r'gastos?\s*(gral\.?|generales?)\b', 5),
    ("MATERIA_PRIMA", "AC.05", "ACTIVO",
     r'materia\s*prima', 1),
    ("SUBSIDIO", "ER.01", "GANANCIA",
     r'subsidio|subvencion', 1),
]

# ── OCR variants that can expand existing concepts ────────────────
OCR_EXPANSIONS = [
    ("DEPRECIACION", r'\bdep\b(?!(art|ar|artam|artament|osito|osita|artamento|artid|artamento))', 147),
    ("IMPUESTOS", r'\bimpto\b|\bimpt[oó]\b', 85),
    ("PRESTAMOS", r'\bptmo\b', 31),
    ("CUENTA_CONTABLE", r'\bcta\b', 214),
    ("CLIENTES", r'\bcte\b', 122),
    ("BANCOS", r'\bb[co]n?[co]\b', 228),
]

# ── Parser artifacts (for info, not proposed as concepts) ─────────
PARSER_ISSUES = [
    (r'\b(19|20)\d{2}\b', "Año/periodo en nombre"),
    (r'\b(ltda|spa|eirl|sa)\b', "Razón social en nombre"),
    (r'\bpreparaci[oó]n\b', "Preparación EEFF"),
    (r'\bplantaci[oó]n\b', "Plantilla/template"),
    (r'\bhabilitaci[oó]n\b', "Habilitación"),
    (r'\badministraci[oó]n\b(?!.*(gasto|ingreso))', "Administración general"),
    (r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', "Mes en nombre"),
    (r'\bdesde\b', "Inicio período"),
    (r'\bp[áa]gina\b', "Página"),
    (r'\b0{2,4}\b', "Ceros filler"),
]


def run():
    results = load_results()
    catalog = load_catalog()

    existing_concept_names = {c["name"] for c in catalog["concepts"]}

    unknown = [r for r in results if r.get("expected_cmcc") is None and r.get("phase1_code") is None]
    total_unknown = len(unknown)
    print(f"UNKNOWN total: {total_unknown}")

    # ── Evaluate each proposal ──
    proposal_results = []
    seen_accounts: set[str] = set()
    cumulative = 0

    for name, code, acct_type, pat_str, expected_incr in PROPOSALS:
        pat = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
        matching = [
            r for r in unknown
            if re.search(pat, r["account_name"])
        ]
        actual_count = len(matching)
        # Only count accounts not already covered by higher-priority proposals
        new_accounts = [
            r["account_name"] for r in matching
            if r["account_name"] not in seen_accounts
        ]
        incremental = len(new_accounts)
        seen_accounts.update(new_accounts)
        cumulative += incremental

        if incremental >= 1:
            samples = list(set(m["account_name"] for m in matching))[:3]
            is_new_concept = name not in existing_concept_names
            proposal_results.append({
                "proposed_name": name,
                "target_code": code,
                "target_type": acct_type,
                "pattern": pat_str,
                "total_matches": actual_count,
                "incremental": incremental,
                "incremental_pct": round(incremental / total_unknown * 100, 1),
                "cumulative": cumulative,
                "cumulative_pct": round(cumulative / total_unknown * 100, 1),
                "new_concept": is_new_concept,
                "samples": samples,
                "type": "new_concept" if is_new_concept else "expansion",
            })

    # ── OCR expansions ──
    ocr_results = []
    ocr_seen: set[str] = set()
    for concept_name, pat_str, expected in OCR_EXPANSIONS:
        pat = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
        matching = [
            r for r in unknown
            if re.search(pat, r["account_name"])
        ]
        new_accounts = [
            r["account_name"] for r in matching
            if r["account_name"] not in seen_accounts
        ]
        incremental = len(new_accounts)
        ocr_seen.update(new_accounts)
        if incremental >= 1:
            samples = list(set(m["account_name"] for m in matching))[:3]
            ocr_results.append({
                "concept_name": concept_name,
                "pattern": pat_str,
                "total_matches": len(matching),
                "incremental": incremental,
                "incremental_pct": round(incremental / total_unknown * 100, 1),
                "samples": samples,
            })

    # ── Parser issues ──
    parser_results = []
    parser_seen: set[str] = set()
    for pat_str, label in PARSER_ISSUES:
        pat = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
        matching = [
            r for r in unknown
            if re.search(pat, r["account_name"])
        ]
        new_accounts = [
            r["account_name"] for r in matching
            if r["account_name"] not in parser_seen
        ]
        parser_seen.update(new_accounts)
        if len(matching) >= 10:
            parser_results.append({
                "issue": label,
                "pattern": pat_str,
                "accounts": len(matching),
                "pct": round(len(matching) / total_unknown * 100, 1),
                "incremental": len(new_accounts),
            })

    # ── Summary stats ──
    total_new_concepts = sum(1 for p in proposal_results if p["new_concept"])
    total_expansions = sum(1 for p in proposal_results if not p["new_concept"])
    concept_recovered = cumulative
    ocr_recovered = sum(o["incremental"] for o in ocr_results)
    total_recovered = concept_recovered + ocr_recovered
    remaining = total_unknown - total_recovered

    metadata = {
        "total_unknown": total_unknown,
        "concept_proposals": len(proposal_results),
        "new_concepts": total_new_concepts,
        "concept_expansions": total_expansions,
        "ocr_expansions": len(ocr_results),
        "parser_issues": len(parser_results),
        "recovered_by_new_concepts": concept_recovered,
        "recovered_by_ocr": ocr_recovered,
        "total_recoverable": total_recovered,
        "total_recoverable_pct": round(total_recovered / total_unknown * 100, 1),
        "remaining_after_v2": remaining,
        "remaining_after_v2_pct": round(remaining / total_unknown * 100, 1),
    }

    output = {
        "metadata": metadata,
        "proposals": proposal_results,
        "ocr_expansions": ocr_results,
        "parser_issues": parser_results,
    }

    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(metadata, proposal_results, ocr_results, parser_results)
    guardar_xlsx(metadata, proposal_results, ocr_results, parser_results)

    print(f"\n=== PROPUESTA CATÁLOGO V2 ===")
    print(f"  UNKNOWN actuales:        {total_unknown}")
    print(f"  Nuevos conceptos:        {total_new_concepts}")
    print(f"  Expansiones de existentes: {total_expansions}")
    print(f"  Expansiones OCR:         {len(ocr_results)}")
    print(f"  Recuperable total:       {total_recovered} ({metadata['total_recoverable_pct']}%)")
    print(f"  Remanente tras v2:       {remaining} ({metadata['remaining_after_v2_pct']}%)")
    print()
    print("  Top 10 nuevos conceptos:")
    for p in proposal_results[:10]:
        bar = "█" * max(1, int(p["incremental_pct"] * 3))
        status = "NUEVO" if p["new_concept"] else "EXPAN"
        print(f"    {p['proposed_name'][:25]:25s} → {p['target_code']:10s} | +{p['incremental']:4d} ({p['incremental_pct']:4.1f}%) [{status}] {bar}")
    print()
    print("  OCR expansions:")
    for o in ocr_results:
        print(f"    {o['concept_name'][:25]:25s} → +{o['incremental']:4d} ({o['incremental_pct']:.1f}%)")
    print()
    print(f"  Reportes en {REPORT_DIR}")


def guardar_md(md: dict, proposals: list[dict], ocr: list[dict], parser: list[dict]):
    lines = [
        "# Propuesta Concept Catalog v2\n",
        f"**Date:** 2026-07-22  \n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| UNKNOWN actuales | {md['total_unknown']} |",
        f"| Nuevos conceptos propuestos | {md['new_concepts']} |",
        f"| Expansiones de conceptos existentes | {md['concept_expansions']} |",
        f"| Expansiones OCR | {md['ocr_expansions']} |",
        f"| Recuperable total | {md['total_recoverable']} ({md['total_recoverable_pct']}%) |",
        f"| Remanente tras v2 | {md['remaining_after_v2']} ({md['remaining_after_v2_pct']}%) |",
        "",
        "## Nuevos Conceptos Propuestos\n",
        "| # | Concepto | Código | Incremental | % | Acumulado | % Acum | Muestra |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(proposals, 1):
        if not p["new_concept"]:
            continue
        samples = "; ".join(p["samples"][:2])
        lines.append(
            f"| {i} | {p['proposed_name']} | {p['target_code']} | "
            f"{p['incremental']} | {p['incremental_pct']}% | "
            f"{p['cumulative']} | {p['cumulative_pct']}% | {samples} |"
        )

    lines += [
        "",
        "## Expansiones de Conceptos Existentes\n",
        "| # | Concepto | Código | Incremental | % | Muestra |",
        "|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(proposals, 1):
        if p["new_concept"]:
            continue
        samples = "; ".join(p["samples"][:2])
        lines.append(
            f"| {i} | {p['proposed_name']} | {p['target_code']} | "
            f"{p['incremental']} | {p['incremental_pct']}% | {samples} |"
        )

    lines += [
        "",
        "## Expansiones OCR (mejorar conceptos existentes)\n",
        "| Concepto | Patrón | Incremental | % | Muestra |",
        "|---|---|---|---|---|",
    ]
    for o in ocr:
        samples = "; ".join(o["samples"][:2])
        lines.append(
            f"| {o['concept_name']} | `{o['pattern']}` | {o['incremental']} | "
            f"{o['incremental_pct']}% | {samples} |"
        )

    lines += [
        "",
        "## Problemas de Parser (no recuperables con conceptos)\n",
        "| Problema | Cuentas | % |",
        "|---|---|---|",
    ]
    for p in parser:
        lines.append(f"| {p['issue']} | {p['accounts']} | {p['pct']}% |")

    lines += [
        "",
        "## Cobertura Acumulada Esperada (top 20)\n",
        "| # | Concepto | Incremental | % | Acumulado | % Acum |",
        "|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(proposals[:20], 1):
        lines.append(
            f"| {i} | {p['proposed_name']} | {p['incremental']} | "
            f"{p['incremental_pct']}% | {p['cumulative']} | {p['cumulative_pct']}% |"
        )

    lines += [
        "",
        "---\n*Generated by reports/concept_v2_proposal.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(md: dict, proposals: list[dict], ocr: list[dict], parser: list[dict]):
    import pandas as pd

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        summary = [
            {"Métrica": k, "Valor": v}
            for k, v in md.items() if not isinstance(v, (dict, list))
        ]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)

        cols = ["proposed_name", "target_code", "target_type", "incremental",
                "incremental_pct", "cumulative", "cumulative_pct",
                "new_concept", "samples"]
        df = pd.DataFrame([{k: p.get(k, "") for k in cols} for p in proposals])
        df.to_excel(writer, sheet_name="Propuestas", index=False)

        pd.DataFrame(ocr).to_excel(writer, sheet_name="OCR_Expansiones", index=False)
        pd.DataFrame(parser).to_excel(writer, sheet_name="Parser_Issues", index=False)


if __name__ == "__main__":
    run()
