"""Benchmark del ConfidenceEngine sobre semantic_matcher_v1.json.

Combina señales existentes (SM score, tier, Regex, DecisionEngine)
y genera distribución 0-100.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from confidence.engine import ConfidenceEngine

REPORT_DIR = Path(__file__).resolve().parent
BENCH_PATH = REPORT_DIR / "semantic_matcher_v1.json"
DE_PATH = REPORT_DIR / "decision_engine.json"
AUDIT_PATH = REPORT_DIR / "disagreement_audit.json"

OUT_JSON = REPORT_DIR / "confidence_engine.json"
OUT_MD = REPORT_DIR / "confidence_engine.md"
OUT_XLSX = REPORT_DIR / "confidence_engine.xlsx"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def run_benchmark():
    print("Cargando datos...")
    bench = load_json(BENCH_PATH)
    de_data = load_json(DE_PATH)
    results = bench["results"]
    decisions = de_data["decisions"]

    ce = ConfidenceEngine()
    total = len(results)
    print(f"  Cuentas: {total}")

    score_dist = Counter()
    label_dist = Counter()
    per_account = []

    for i, (r, d) in enumerate(zip(results, decisions)):
        sm_score = r.get("score")
        sm_tier = r.get("match_tier")
        p1_code = r.get("phase1_code")
        sm_code = r.get("expected_cmcc")
        de_source = d.get("decision_source", "BOTH_UNKNOWN")

        # Regex score: from REGLAS_REGEX confidence for matched code
        regex_score = None
        regex_method = None
        if p1_code:
            from app_validacion import REGLAS_REGEX
            # Find the regex with highest confidence for this code
            best_conf = 0.0
            for pat_str, code, conf in REGLAS_REGEX:
                if code == p1_code and conf > best_conf:
                    best_conf = conf
                    regex_method = d.get("reason", "").startswith(("Regex", "Patrón"))
            regex_score = best_conf if best_conf > 0 else 0.88
            # Determine method
            p1_method = r.get("phase1_method", "")
            if p1_method in ("dictionary_exact", "dictionary_fuzzy", "regex_fallback"):
                regex_method = p1_method
            else:
                regex_method = "regex_fallback"

        # Type compatibility: infer from code prefix vs standard prefix logic
        codigo_final = d.get("codigo_final")
        type_compatible = True  # default - we don't have account type in data
        if codigo_final and sm_code and codigo_final != sm_code:
            # See if DE chose Regex over SM despite type mismatch
            pass

        # Determine dict method
        dict_method = None
        if regex_method in ("dictionary_exact", "dictionary_fuzzy"):
            dict_method = regex_method

        cr = ce.compute(
            sm_score=sm_score,
            sm_tier=sm_tier,
            regex_score=regex_score,
            regex_method=regex_method,
            decision_source=de_source,
            type_compatible=type_compatible,
            dict_method=dict_method,
        )

        score_dist[cr.score] += 1
        label_dist[cr.label] += 1

        per_account.append({
            "account_name": r.get("account_name", ""),
            "sm_code": sm_code,
            "sm_score": sm_score,
            "sm_tier": sm_tier,
            "regex_code": p1_code,
            "de_source": de_source,
            "de_codigo_final": codigo_final,
            "confidence_score": cr.score,
            "confidence_label": cr.label,
            "breakdown": cr.breakdown.to_dict(),
        })

    # Distribution by buckets
    buckets = {"0-20 (UNKNOWN)": 0, "21-40 (LOW)": 0, "41-60 (MEDIUM)": 0,
               "61-80 (HIGH)": 0, "81-100 (VERY_HIGH)": 0}
    for score, cnt in score_dist.items():
        if score <= 20:
            buckets["0-20 (UNKNOWN)"] += cnt
        elif score <= 40:
            buckets["21-40 (LOW)"] += cnt
        elif score <= 60:
            buckets["41-60 (MEDIUM)"] += cnt
        elif score <= 80:
            buckets["61-80 (HIGH)"] += cnt
        else:
            buckets["81-100 (VERY_HIGH)"] += cnt

    metadata = {
        "total_accounts": total,
        "avg_score": round(sum(score * cnt for score, cnt in score_dist.items()) / total, 2),
        "median_score": _median_from_dist(score_dist, total),
        "label_distribution": dict(label_dist.most_common()),
        "bucket_distribution": buckets,
    }

    output = {
        "metadata": metadata,
        "score_distribution": [{"score": s, "count": c} for s, c in sorted(score_dist.items())],
        "decisions": per_account,
    }

    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(metadata, label_dist, buckets)
    guardar_xlsx(output, per_account)

    print(f"\n=== CONFIDENCE ENGINE ===")
    print(f"  Score promedio: {metadata['avg_score']}")
    print(f"  Mediana:        {metadata['median_score']}")
    print()
    print("  Distribución por label:")
    for lbl, cnt in label_dist.most_common():
        pct = round(cnt / total * 100, 1)
        print(f"    {lbl:15s}: {cnt:5d} ({pct:5.1f}%)")
    print()
    print("  Buckets:")
    for bucket, cnt in buckets.items():
        pct = round(cnt / total * 100, 1)
        print(f"    {bucket:25s}: {cnt:5d} ({pct:5.1f}%)")
    print(f"\n  Reportes en {REPORT_DIR}")


def _median_from_dist(dist: Counter, total: int) -> float:
    sorted_scores = sorted(dist.keys())
    cum = 0
    mid = total // 2
    for s in sorted_scores:
        cum += dist[s]
        if cum > mid:
            return float(s)
    return 0.0


def guardar_md(metadata: dict, label_dist: Counter, buckets: dict):
    lines = [
        "# Benchmark ConfidenceEngine\n",
        f"**Date:** 2026-07-22  \n",
        f"**Cuentas analizadas:** {metadata['total_accounts']}  \n",
        "---\n",
        "## Resumen\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Cuentas totales | {metadata['total_accounts']} |",
        f"| Score promedio | {metadata['avg_score']} |",
        f"| Mediana | {metadata['median_score']} |",
        "",
        "## Distribución por Label\n",
        "| Label | Cuentas | % |",
        "|---|---|---|",
    ]
    for lbl, cnt in label_dist.most_common():
        pct = round(cnt / metadata['total_accounts'] * 100, 1)
        lines.append(f"| {lbl} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Distribución por Bucket\n",
        "| Bucket | Cuentas | % |",
        "|---|---|---|",
    ]
    for bucket, cnt in sorted(buckets.items()):
        pct = round(cnt / metadata['total_accounts'] * 100, 1)
        lines.append(f"| {bucket} | {cnt} | {pct}% |")

    lines += [
        "",
        "## Score Distribution (10-point buckets)\n",
        "| Rango | Cuentas |",
        "|---|---|",
    ]
    dist_10 = Counter()
    for lbl, cnt in label_dist.most_common():
        _ = cnt
    from collections import Counter as _C
    # Not available here, compute from metadata
    lines += [
        "",
        "---\n*Generated by reports/confidence_benchmark.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict, decisions: list[dict]):
    import pandas as pd

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        m = output["metadata"]
        summary = [
            {"Métrica": "Cuentas totales", "Valor": m["total_accounts"]},
            {"Métrica": "Score promedio", "Valor": m["avg_score"]},
            {"Métrica": "Mediana", "Valor": m["median_score"]},
        ]
        for lbl, cnt in m["label_distribution"].items():
            summary.append({"Métrica": f"Label {lbl}", "Valor": cnt})
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)

        cols = ["account_name", "confidence_score", "confidence_label",
                "de_source", "sm_score", "sm_tier", "sm_code", "regex_code"]
        df = pd.DataFrame([{k: d.get(k, "") for k in cols} for d in decisions])
        df.to_excel(writer, sheet_name="Decisiones", index=False)

        # Score distribution
        dist = output["score_distribution"]
        pd.DataFrame(dist).to_excel(writer, sheet_name="Distribucion", index=False)

        # Labels
        pd.DataFrame(
            [{"Label": k, "Cuentas": v} for k, v in m["label_distribution"].items()]
        ).to_excel(writer, sheet_name="Labels", index=False)


if __name__ == "__main__":
    run_benchmark()
