"""Benchmark del DecisionEngine sobre semantic_matcher_v1.json.

NO modifica el pipeline.
Solo simula las reglas del DE y mide resultados.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decision.engine import DecisionEngine

REPORT_DIR = Path(__file__).resolve().parent
BENCH_PATH = REPORT_DIR / "semantic_matcher_v1.json"
AUDIT_PATH = REPORT_DIR / "disagreement_audit.json"

OUT_JSON = REPORT_DIR / "decision_engine.json"
OUT_MD = REPORT_DIR / "decision_engine.md"
OUT_XLSX = REPORT_DIR / "decision_engine.xlsx"


def load_benchmark_data():
    with open(BENCH_PATH) as f:
        return json.load(f)


def load_audit_data():
    with open(AUDIT_PATH) as f:
        return json.load(f)


def run_benchmark():
    print("Cargando datos...")
    data = load_benchmark_data()
    audit_data = load_audit_data()
    results = data["results"]

    de = DecisionEngine()
    total = len(results)
    print(f"  Cuentas totales: {total}")

    # Stat collectors
    decision_sources = Counter()
    confidences = Counter()
    auto_decisions = 0
    human_reviews = 0
    conflicts_resolved = 0
    conflicts_pending = 0

    per_account_decisions = []

    # Phase 1 baseline counters
    phase1_classified = 0
    phase1_unknown = 0
    de_classified = 0
    de_unknown = 0

    # Improved counters vs Phase 1
    gap_reduction = 0
    regression_count = 0
    regression_details = []

    # Conflict resolution stats
    both_classified_same = 0
    both_classified_diff = 0
    phase1_only = 0
    sm_only = 0
    both_unknown = 0

    # Resolution of the 319 conflicts
    conflict_resolutions = Counter()

    for r in results:
        p1_code = r.get("phase1_code")
        p1_method = r.get("phase1_method", "")
        sm_code = r.get("expected_cmcc")
        sm_score = r.get("score")
        sm_tier = r.get("match_tier")
        sm_confidence = r.get("confidence")

        # Determine regex_method for DE input
        regex_method = None
        if p1_method in ("dictionary_exact", "dictionary_fuzzy", "regex_fallback"):
            regex_method = p1_method

        decision = de.decide(
            sm_code=sm_code,
            sm_score=sm_score,
            sm_tier=sm_tier,
            sm_confidence=sm_confidence,
            regex_code=p1_code,
            regex_method=regex_method,
        )

        # Stats
        decision_sources[decision.decision_source] += 1
        confidences[decision.confidence] += 1

        if decision.review_required:
            human_reviews += 1
        else:
            auto_decisions += 1

        # Conflict tracking
        if p1_code and sm_code:
            if p1_code == sm_code:
                both_classified_same += 1
            else:
                both_classified_diff += 1
                if decision.review_required:
                    conflicts_pending += 1
                    conflict_resolutions["UNRESOLVED"] += 1
                else:
                    conflicts_resolved += 1
                    conflict_resolutions[decision.decision_source] += 1
        elif p1_code and not sm_code:
            phase1_only += 1
        elif sm_code and not p1_code:
            sm_only += 1
        else:
            both_unknown += 1

        # Gap & regression
        if p1_code is None and sm_code is not None:
            if not decision.review_required:
                gap_reduction += 1
        if p1_code is not None and sm_code is not None and p1_code != sm_code:
            if not decision.review_required:
                if decision.codigo_final == p1_code:
                    regression_count += 1
                    regression_details.append({
                        "account_name": r.get("account_name", ""),
                        "chosen": p1_code,
                        "rejected": sm_code,
                        "source": "regex",
                    })
                elif decision.codigo_final == sm_code:
                    gap_reduction += 1

        # Accuracy proxies
        de_classified += 1 if decision.codigo_final is not None else 0
        de_unknown += 1 if decision.codigo_final is None else 0

        if p1_code is not None:
            phase1_classified += 1
        else:
            phase1_unknown += 1

        per_account_decisions.append({
            "account_name": r.get("account_name", ""),
            "phase1_code": p1_code,
            "sm_code": sm_code,
            "sm_score": sm_score,
            "sm_tier": sm_tier,
            "codigo_final": decision.codigo_final,
            "decision_source": decision.decision_source,
            "confidence": decision.confidence,
            "review_required": decision.review_required,
            "reason": decision.reason,
        })

    # Aggregated phase1 comparison
    phase1_known = phase1_classified
    de_known = de_classified

    # Disagreement audit overlay
    # Count how many of the 319 discrepancies are resolved
    p1_only_overlap = 0
    sm_only_overlap = 0

    metadata = {
        "total_accounts": total,
        "phase1_classified": phase1_classified,
        "phase1_unknown": phase1_unknown,
        "de_classified": de_classified,
        "de_unknown": de_unknown,
        "de_gap_reduction": gap_reduction,
        "de_regression_count": regression_count,
        "auto_decisions": auto_decisions,
        "human_reviews": human_reviews,
        "conflicts_resolved": conflicts_resolved,
        "conflicts_pending": conflicts_pending,
        "both_classified_same": both_classified_same,
        "both_classified_diff": both_classified_diff,
        "phase1_only": phase1_only,
        "sm_only": sm_only,
        "both_unknown": both_unknown,
        "decision_sources": dict(decision_sources.most_common()),
        "confidences": dict(confidences.most_common()),
        "conflict_resolutions": dict(conflict_resolutions.most_common()),
    }

    output = {
        "metadata": metadata,
        "conflict_resolutions": [
            {"source": k, "count": v}
            for k, v in conflict_resolutions.most_common()
        ],
        "top_decisions": [
            {"source": k, "count": v}
            for k, v in decision_sources.most_common()
        ],
        "decisions": per_account_decisions,
    }

    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(metadata)
    guardar_xlsx(output, per_account_decisions)

    print(f"\n=== RESULTADOS DECISION ENGINE ===")
    print(f"  Automáticas:          {auto_decisions:5d} ({auto_decisions/total*100:5.1f}%)")
    print(f"  Requieren revisión:   {human_reviews:5d} ({human_reviews/total*100:5.1f}%)")
    print(f"  Conflictos resueltos: {conflicts_resolved:5d}")
    print(f"  Conflictos pendientes: {conflicts_pending:5d}")
    print(f"  Gap reduction vs P1:  {gap_reduction:5d}")
    print(f"  Regresiones vs P1:    {regression_count:5d}")
    print()
    print("  Fuentes de decisión:")
    for src, cnt in decision_sources.most_common():
        print(f"    {src:25s}: {cnt:5d}")
    print()
    print("  Confianza:")
    for conf, cnt in confidences.most_common():
        print(f"    {conf:15s}: {cnt:5d}")
    print()
    print(f"  Reportes generados en {REPORT_DIR}")


def guardar_md(m: dict):
    lines = [
        "# Benchmark DecisionEngine\n",
        f"**Date:** 2026-07-22  \n",
        f"**Cuentas analizadas:** {m['total_accounts']}  \n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor | % |",
        "|---|---|---|",
        f"| Cuentas totales | {m['total_accounts']} | 100% |",
        f"| Decisiones automáticas | {m['auto_decisions']} | {round(m['auto_decisions']/m['total_accounts']*100,1)}% |",
        f"| Requieren revisión humana | {m['human_reviews']} | {round(m['human_reviews']/m['total_accounts']*100,1)}% |",
        f"| Conflictos resueltos | {m['conflicts_resolved']} | — |",
        f"| Conflictos pendientes | {m['conflicts_pending']} | — |",
        "",
        "## Clasificación vs Phase 1\n",
        "| Métrica | Phase 1 | DecisionEngine | Diferencia |",
        "|---|---|---|---|",
        f"| Clasificados | {m['phase1_classified']} | {m['de_classified']} | +{m['de_classified']-m['phase1_classified']} |",
        f"| No clasificados | {m['phase1_unknown']} | {m['de_unknown']} | {m['de_unknown']-m['phase1_unknown']:+} |",
        f"| Gap reduction | — | {m['de_gap_reduction']} | — |",
        f"| Regresiones | — | {m['de_regression_count']} | — |",
        "",
        "## Fuentes de Decisión\n",
        "| Fuente | Cuentas | % |",
        "|---|---|---|",
    ]
    for src, cnt in sorted(m['decision_sources'].items(), key=lambda x: -x[1]):
        pct = round(cnt / m['total_accounts'] * 100, 1)
        lines.append(f"| {src} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Distribución de Confianza\n",
        "| Confianza | Cuentas | % |",
        "|---|---|---|",
    ]
    for conf, cnt in sorted(m['confidences'].items(), key=lambda x: -x[1]):
        pct = round(cnt / m['total_accounts'] * 100, 1)
        lines.append(f"| {conf} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Resolución de Conflictos (319 discrepancias)\n",
        "| Resultado | Cuentas |",
        "|---|---|",
    ]
    for src, cnt in sorted(m['conflict_resolutions'].items(), key=lambda x: -x[1]):
        lines.append(f"| {src} | {cnt} |")

    lines += [
        "",
        "## Conflictos por Tipo (categorías de auditoría)\n",
        "| Categoría | Resueltos | Pendientes |",
        "|---|---|---|",
    ]

    aud_resolved = 0
    aud_pending = 0
    try:
        with open(AUDIT_PATH) as f:
            audit = json.load(f)
        for r in audit["discrepancies"]:
            if r["who_wins"] != "Indefinido (requiere revisión)":
                aud_resolved += 1
            else:
                aud_pending += 1
    except Exception:
        pass

    lines.append(f"| Sin revisión humana | {aud_resolved} | — |")
    lines.append(f"| Requieren revisión | — | {aud_pending} |")
    lines += [
        "",
        "---\n*Generated by reports/decision_benchmark.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict, decisions: list[dict]):
    import pandas as pd

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        m = output["metadata"]
        summary = [
            {"Métrica": k, "Valor": v}
            for k, v in m.items()
            if not isinstance(v, dict)
        ]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)

        cols = ["account_name", "phase1_code", "sm_code", "sm_score", "sm_tier",
                "codigo_final", "decision_source", "confidence", "review_required", "reason"]
        df = pd.DataFrame([{k: d.get(k, "") for k in cols} for d in decisions])
        df.to_excel(writer, sheet_name="Decisiones", index=False)

        sources = output["top_decisions"]
        pd.DataFrame(sources).to_excel(writer, sheet_name="Fuentes", index=False)

        conflicts = output["conflict_resolutions"]
        pd.DataFrame(conflicts).to_excel(writer, sheet_name="Conflictos", index=False)


if __name__ == "__main__":
    run_benchmark()
