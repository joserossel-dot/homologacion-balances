"""Benchmark del SemanticMatcher v1 sobre los 182 balances.

Uso:
    python3 -m semantic.benchmark

Genera reports/semantic_matcher_v1.{json,md,xlsx}
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from semantic.matcher import SemanticMatcher

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "concept_catalog.json"
ACCOUNTS_CACHE = REPORT_DIR / "unknown_all_accounts.json"

OUT_JSON = REPORT_DIR / "semantic_matcher_v1.json"
OUT_MD = REPORT_DIR / "semantic_matcher_v1.md"
OUT_XLSX = REPORT_DIR / "semantic_matcher_v1.xlsx"


def load_accounts() -> list[dict]:
    if not ACCOUNTS_CACHE.exists():
        print(f"No se encontró {ACCOUNTS_CACHE}. Ejecuta primero analyze_unknown_pareto.py")
        sys.exit(1)
    with open(ACCOUNTS_CACHE) as f:
        return json.load(f)


def run_benchmark():
    print("Cargando catálogo...")
    matcher = SemanticMatcher(str(CATALOG_PATH))
    print(f"  {matcher.concept_count} conceptos cargados")

    accounts = load_accounts()
    print(f"  {len(accounts)} cuentas cargadas")

    # Clasificar según Phase 1 existente
    phase1_unknown = [a for a in accounts if a.get("standard_code") is None]
    phase1_classified = [a for a in accounts if a.get("standard_code") is not None]
    print(f"  Phase 1: {len(phase1_classified)} clasificadas, {len(phase1_unknown)} UNKNOWN")

    print("Ejecutando SemanticMatcher sobre todas las cuentas...")
    t0 = time.perf_counter()
    results = []
    for account in accounts:
        name = account.get("account_name", "")
        atype = account.get("tipo")
        match = matcher.match(name, atype)
        results.append({
            "account_name": name,
            "account_code": account.get("account_code", ""),
            "tipo": atype or "",
            "source_file": account.get("source_file", ""),
            "phase1_code": account.get("standard_code"),
            "phase1_method": account.get("method", ""),
            **match.to_dict(),
        })
    elapsed = time.perf_counter() - t0

    # Análisis
    total = len(results)
    sm_classified = sum(1 for r in results if not r["is_unknown"])
    sm_unknown = total - sm_classified

    # Cuentas que Phase 1 deja UNKNOWN pero SM clasifica
    phase1_unknown_count = len(phase1_unknown)
    sm_recovers = sum(1 for r in results
                      if r["phase1_code"] is None and not r["is_unknown"])
    sm_misses = sum(1 for r in results
                    if r["phase1_code"] is None and r["is_unknown"])

    gap_reduction = round(sm_recovers / phase1_unknown_count * 100, 2) if phase1_unknown_count else 0

    # Conceptos usados
    concept_counts = Counter()
    tier_counts = Counter()
    confidence_counts = Counter()
    per_concept_accounts: dict[str, list[str]] = defaultdict(list)

    for r in results:
        if not r["is_unknown"]:
            cid = r["concept_id"]
            concept_counts[cid] += 1
            tier_counts[r["match_tier"]] += 1
            confidence_counts[r["confidence"]] += 1
            per_concept_accounts[cid].append(r["account_name"])

    # Obtener nombres de conceptos
    concept_names = {}
    for c in matcher._catalog:
        concept_names[c["id"]] = c["name"]

    # Top conceptos
    top_concepts = []
    for cid, cnt in concept_counts.most_common(50):
        c = matcher.get_concept(cid)
        top_concepts.append({
            "rank": len(top_concepts) + 1,
            "concept_id": cid,
            "concept_name": concept_names.get(cid, cid),
            "total_accounts": cnt,
            "pct": round(cnt / sm_classified * 100, 2) if sm_classified else 0,
            "expected_cmcc": c["expected_cmcc_code"] if c else "",
        })

    # Comparación Phase 1 vs SemanticMatcher
    # Cuentas que Phase 1 clasifica y SM también (coincidencia de código)
    both_classified = sum(1 for r in results
                          if r["phase1_code"] is not None and not r["is_unknown"]
                          and r["phase1_code"] == r["expected_cmcc"])
    both_diff = sum(1 for r in results
                    if r["phase1_code"] is not None and not r["is_unknown"]
                    and r["phase1_code"] != r["expected_cmcc"])
    phase1_only = sum(1 for r in results
                      if r["phase1_code"] is not None and r["is_unknown"])

    # Recall estimado (sobre Phase 1 UNKNOWN)
    estimated_recall = round(sm_recovers / phase1_unknown_count * 100, 2) if phase1_unknown_count else 0

    # Precisión estimada
    # Asumimos que Tier 1-3 es 100% preciso, Tier 4-6 estimado 90%
    exact_matches = sum(1 for r in results if not r["is_unknown"] and r["match_tier"] in (1, 2, 3))
    fuzzy_matches = sum(1 for r in results if not r["is_unknown"] and r["match_tier"] in (4, 5, 6))
    estimated_precision = round(
        (exact_matches * 1.0 + fuzzy_matches * 0.90) / max(sm_classified, 1) * 100, 1
    )

    output = {
        "metadata": {
            "total_accounts": total,
            "phase1_classified": len(phase1_classified),
            "phase1_unknown": phase1_unknown_count,
            "sm_classified": sm_classified,
            "sm_unknown": sm_unknown,
            "sm_recovers_unknown": sm_recovers,
            "sm_remaining_unknown": sm_misses,
            "gap_reduction_pct": gap_reduction,
            "estimated_recall_pct": estimated_recall,
            "estimated_precision_pct": estimated_precision,
            "avg_score": round(
                sum(r["score"] for r in results if not r["is_unknown"]) / max(sm_classified, 1), 4
            ),
            "elapsed_seconds": round(elapsed, 2),
            "avg_ms_per_account": round(elapsed / total * 1000, 2),
            "concepts_used": len(concept_counts),
            "total_concepts_available": matcher.concept_count,
        },
        "top_concepts": top_concepts[:20],
        "tier_distribution": {
            str(k): v for k, v in sorted(tier_counts.items())
        },
        "confidence_distribution": dict(confidence_counts.most_common()),
        "comparison": {
            "both_classified_same_code": both_classified,
            "both_classified_different_code": both_diff,
            "phase1_only": phase1_only,
            "sm_only": sm_recovers,
            "both_unknown": sm_misses,
        },
        "results": results,
    }

    # Guardar
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(output, top_concepts)
    guardar_xlsx(output, results, top_concepts)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  BENCHMARK SEMANTICMATCHER V1")
    print(f"{'='*60}")
    print(f"  Total cuentas:          {total}")
    print(f"  Phase 1 UNKNOWN:        {phase1_unknown_count}")
    print(f"  SM clasifica:           {sm_classified} ({round(sm_classified/total*100,1)}%)")
    print(f"  SM recupera UNKNOWN:    {sm_recovers} ({gap_reduction}% del gap)")
    print(f"  SM NO recupera:         {sm_misses} UNKNOWN remanente")
    print(f"  Recall estimado:        {estimated_recall}%")
    print(f"  Precisión estimada:     {estimated_precision}%")
    print(f"  Score promedio:         {output['metadata']['avg_score']}")
    print(f"  Tiempo total:           {elapsed:.1f}s")
    print(f"  Tiempo promedio:        {output['metadata']['avg_ms_per_account']}ms/cuenta")
    print(f"  Conceptos usados:       {len(concept_counts)} de {matcher.concept_count}")
    print(f"{'='*60}")
    print(f"  Top 5 conceptos:")
    for tc in top_concepts[:5]:
        print(f"    {tc['concept_name']}: {tc['total_accounts']} cuentas")
    print(f"{'='*60}")
    print(f"  Reportes generados:")
    print(f"    {OUT_JSON}")
    print(f"    {OUT_MD}")
    print(f"    {OUT_XLSX}")


def guardar_md(output: dict, top_concepts: list[dict]):
    m = output["metadata"]
    c = output["comparison"]
    lines = [
        "# SemanticMatcher v1 — Benchmark\n",
        f"**Date:** 2026-07-22  \n",
        f"**Catalog:** {m['total_concepts_available']} concepts from concept_catalog.json  \n",
        f"**Total accounts:** {m['total_accounts']}  \n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Total cuentas | {m['total_accounts']} |",
        f"| Phase 1 clasificadas | {m['phase1_classified']} |",
        f"| Phase 1 UNKNOWN | {m['phase1_unknown']} |",
        f"| SemanticMatcher clasifica | {m['sm_classified']} ({round(m['sm_classified']/m['total_accounts']*100,1)}%) |",
        f"| SM recupera de UNKNOWN | {m['sm_recovers_unknown']} ({m['gap_reduction_pct']}% del gap) |",
        f"| SM NO recupera | {m['sm_remaining_unknown']} UNKNOWN remanente |",
        f"| Recall estimado | {m['estimated_recall_pct']}% |",
        f"| Precisión estimada | {m['estimated_precision_pct']}% |",
        f"| Score promedio | {m['avg_score']} |",
        f"| Tiempo total | {m['elapsed_seconds']}s |",
        f"| Tiempo promedio | {m['avg_ms_per_account']}ms/cuenta |",
        f"| Conceptos usados | {m['concepts_used']} de {m['total_concepts_available']} |",
        "",
        "## Comparación Phase 1 vs SemanticMatcher\n",
        "| Escenario | Cuentas | Descripción |",
        "|---|---|---|",
        f"| Ambos clasifican (mismo código) | {c['both_classified_same_code']} | Phase 1 y SM coinciden |",
        f"| Ambos clasifican (código distinto) | {c['both_classified_different_code']} | Discrepancia — revisar |",
        f"| Solo Phase 1 clasifica | {c['phase1_only']} | Phase 1 captura lo que SM no |",
        f"| Solo SM clasifica | {c['sm_only']} | SM recupera UNKNOWN de Phase 1 |",
        f"| Ambos UNKNOWN | {c['both_unknown']} | Pendiente de Human Review |",
        "",
        "## Distribución por Tier\n",
        "| Tier | Tipo | Cuentas | % |",
        "|---|---|---|---|",
    ]
    total_classified = m["sm_classified"]
    tdist = output["tier_distribution"]
    tier_names = {"1": "Keyword exacto", "2": "Sinónimo exacto", "3": "Abreviatura",
                  "4": "Fuzzy keyword", "5": "Fuzzy sinónimo", "6": "Raíz léxica"}
    for tid in ["1", "2", "3", "4", "5", "6"]:
        cnt = tdist.get(tid, 0)
        pct = round(cnt / total_classified * 100, 1) if total_classified else 0
        lines.append(f"| {tid} | {tier_names.get(tid, '?')} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Distribución por Confianza\n",
        "| Confianza | Cuentas | % |",
        "|---|---|---|",
    ]
    for conf, cnt in output["confidence_distribution"].items():
        pct = round(cnt / total_classified * 100, 1) if total_classified else 0
        lines.append(f"| {conf} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Top 20 Conceptos\n",
        "| Rank | Concepto | Cuentas | % Classified | Código CMCC |",
        "|---|---|---|---|---|",
    ]
    for tc in top_concepts[:20]:
        lines.append(
            f"| {tc['rank']} | {tc['concept_name']} | {tc['total_accounts']} | "
            f"{tc['pct']}% | {tc['expected_cmcc']} |"
        )

    lines += [
        "",
        "---\n*Generated by semantic/benchmark.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict, results: list[dict], top_concepts: list[dict]):
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        # Resumen
        m = output["metadata"]
        c = output["comparison"]
        summary = [
            {"Métrica": "Total cuentas", "Valor": m["total_accounts"]},
            {"Métrica": "Phase 1 clasificadas", "Valor": m["phase1_classified"]},
            {"Métrica": "Phase 1 UNKNOWN", "Valor": m["phase1_unknown"]},
            {"Métrica": "SM clasifica", "Valor": m["sm_classified"]},
            {"Métrica": "SM recupera de UNKNOWN", "Valor": m["sm_recovers_unknown"]},
            {"Métrica": "Gap reduction", "Valor": f"{m['gap_reduction_pct']}%"},
            {"Métrica": "Recall estimado", "Valor": f"{m['estimated_recall_pct']}%"},
            {"Métrica": "Precisión estimada", "Valor": f"{m['estimated_precision_pct']}%"},
            {"Métrica": "Score promedio", "Valor": m["avg_score"]},
            {"Métrica": "Tiempo total", "Valor": f"{m['elapsed_seconds']}s"},
            {"Métrica": "Conceptos usados", "Valor": m["concepts_used"]},
            {"Métrica": "Ambos clasifican igual", "Valor": c["both_classified_same_code"]},
            {"Métrica": "Solo SM clasifica", "Valor": c["sm_only"]},
            {"Métrica": "Ambos UNKNOWN", "Valor": c["both_unknown"]},
        ]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)

        # Por cuenta
        cols = ["account_name", "concept_id", "concept_name", "score", "confidence",
                "match_tier", "expected_cmcc", "phase1_code", "is_unknown"]
        df = pd.DataFrame([{k: r.get(k) for k in cols} for r in results])
        df.to_excel(writer, sheet_name="Resultados", index=False)

        # Top conceptos
        pd.DataFrame(top_concepts).to_excel(writer, sheet_name="Top Conceptos", index=False)

        # Distribución tiers
        pd.DataFrame([
            {"Tier": tid, "Tipo": {"1": "Keyword exacto", "2": "Sinónimo exacto",
             "3": "Abreviatura", "4": "Fuzzy keyword", "5": "Fuzzy sinónimo",
             "6": "Raíz léxica"}.get(tid, "?"), "Cuentas": cnt}
            for tid, cnt in output["tier_distribution"].items()
        ]).to_excel(writer, sheet_name="Tiers", index=False)

        # Confianza
        pd.DataFrame([
            {"Confianza": conf, "Cuentas": cnt}
            for conf, cnt in output["confidence_distribution"].items()
        ]).to_excel(writer, sheet_name="Confianza", index=False)


if __name__ == "__main__":
    run_benchmark()
