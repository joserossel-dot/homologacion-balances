from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def generate_reports(result: dict, output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    clusters = result["clusters"]
    multi = result["multi_member"]
    singletons = result["singletons"]
    high_conf = result["high_confidence"]
    needs_review = result["needs_review"]

    # ── clusters.xlsx ──
    rows = []
    for c in clusters:
        rows.append({
            "id": c.id,
            "n_members": c.n_members,
            "members": " | ".join(c.members[:10]),
            "frecuencia": c.frecuencia,
            "n_empresas": c.n_empresas,
            "n_documentos": c.n_documentos,
            "monto_acumulado": c.monto_acumulado,
            "suggested_concept": c.suggested_concept,
            "confidence": c.confidence,
        })
    cluster_df = pd.DataFrame(rows)
    cluster_df.to_excel(out / "clusters.xlsx", index=False)

    # ── concept_suggestions.xlsx ──
    sugg_rows = []
    has_concept = [c for c in clusters if c.suggested_concept and "SIN CONCEPTO" not in c.suggested_concept]
    for c in sorted(has_concept, key=lambda x: -x.confidence)[:500]:
        sugg_rows.append({
            "id": c.id,
            "members_sample": " | ".join(c.members[:5]),
            "n_members": c.n_members,
            "frecuencia": c.frecuencia,
            "suggested_concept": c.suggested_concept,
            "confidence": c.confidence,
        })
    pd.DataFrame(sugg_rows).to_excel(out / "concept_suggestions.xlsx", index=False)

    # ── high_confidence.xlsx ──
    hc_rows = []
    for c in sorted(high_conf, key=lambda x: -x.confidence):
        hc_rows.append({
            "id": c.id,
            "members": " | ".join(c.members[:10]),
            "n_members": c.n_members,
            "frecuencia": c.frecuencia,
            "n_empresas": c.n_empresas,
            "monto_acumulado": c.monto_acumulado,
            "suggested_concept": c.suggested_concept,
            "confidence": c.confidence,
        })
    pd.DataFrame(hc_rows).to_excel(out / "high_confidence.xlsx", index=False)

    # ── needs_review.xlsx ──
    nr_rows = []
    for c in sorted(needs_review, key=lambda x: -x.n_members):
        nr_rows.append({
            "id": c.id,
            "members": " | ".join(c.members[:10]),
            "n_members": c.n_members,
            "frecuencia": c.frecuencia,
            "suggested_concept": c.suggested_concept,
            "confidence": c.confidence,
        })
    pd.DataFrame(nr_rows).to_excel(out / "needs_review.xlsx", index=False)

    # ── variant_statistics.json ──
    size_dist = Counter()
    for c in clusters:
        if c.n_members >= 10:
            size_dist["10+"] += 1
        elif c.n_members >= 5:
            size_dist["5-9"] += 1
        elif c.n_members == 1:
            size_dist["1 (singleton)"] += 1
        else:
            size_dist["2-4"] += 1

    concept_counter: Counter = Counter()
    for c in clusters:
        if c.suggested_concept and "SIN CONCEPTO" not in c.suggested_concept:
            concept_counter[c.suggested_concept] += 1

    stats = {
        "total_accounts": result["total_accounts"],
        "total_clusters": result["total_clusters"],
        "multi_clusters": result["multi_clusters"],
        "singleton_count": result["singleton_count"],
        "high_confidence_count": result["high_confidence_count"],
        "needs_review_count": result["needs_review_count"],
        "cluster_size_distribution": dict(size_dist),
        "top_suggested_concepts": concept_counter.most_common(30),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    stats_path = out / "variant_statistics.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    paths = {
        "clusters": out / "clusters.xlsx",
        "concept_suggestions": out / "concept_suggestions.xlsx",
        "high_confidence": out / "high_confidence.xlsx",
        "needs_review": out / "needs_review.xlsx",
        "variant_statistics": stats_path,
    }

    # ── clusters.md ──
    _generate_markdown(result, out)

    return paths


def _generate_markdown(result: dict, out: Path) -> None:
    multi = result["multi_member"]
    high_conf = result["high_confidence"]
    needs_review = result["needs_review"]
    singletons = result["singletons"]

    lines = []
    lines.append("# Variant Discovery Report")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---|---|")
    lines.append(f"| Cuentas UNKNOWN analizadas | {result['total_accounts']:,} |")
    lines.append(f"| Clusters formados | {result['total_clusters']:,} |")
    lines.append(f"| Clusters multi-miembro | {result['multi_clusters']:,} |")
    lines.append(f"| Singletons | {result['singleton_count']:,} |")
    lines.append(f"| Alta confianza (≥0.70) | {result['high_confidence_count']:,} |")
    lines.append(f"| Necesitan revisión | {result['needs_review_count']:,} |")
    lines.append("")

    if high_conf:
        lines.append("## Top 20 — Alta Confianza")
        lines.append("")
        lines.append("| # | ID | Miembros | N | Frecuencia | Empresas | Concepto | Confianza |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for idx, c in enumerate(sorted(high_conf, key=lambda x: -x.confidence)[:20], 1):
            members_sample = " | ".join(c.members[:3])
            lines.append(
                f"| {idx} | {c.id} | {members_sample[:60]} | {c.n_members} | "
                f"{c.frecuencia} | {c.n_empresas} | {c.suggested_concept} | {c.confidence} |")
        lines.append("")

    if needs_review:
        lines.append("## Top 20 — Necesitan Revisión")
        lines.append("")
        lines.append("| # | ID | Miembros | N | Frecuencia | Confianza |")
        lines.append("|---|---|---|---|---|---|")
        for idx, c in enumerate(sorted(needs_review, key=lambda x: -x.n_members)[:20], 1):
            members_sample = " | ".join(c.members[:3])
            lines.append(
                f"| {idx} | {c.id} | {members_sample[:60]} | {c.n_members} | "
                f"{c.frecuencia} | {c.confidence} |")
        lines.append("")

    lines.append("## Estadísticas de Clusters")
    lines.append("")
    size_dist = Counter()
    for c in result["clusters"]:
        if c.n_members >= 10:
            size_dist["10+"] += 1
        elif c.n_members >= 5:
            size_dist["5-9"] += 1
        elif c.n_members == 1:
            size_dist["1 (singleton)"] += 1
        else:
            size_dist["2-4"] += 1
    for label in ["10+", "5-9", "2-4", "1 (singleton)"]:
        lines.append(f"- **{label}**: {size_dist.get(label, 0)} clusters")
    lines.append("")

    total = result["total_accounts"]
    clustered = sum(c.n_members for c in multi)
    isolated = result["singleton_count"]
    lines.append(f"- **Agrupadas**: {clustered:,} ({clustered/total*100:.1f}%)")
    lines.append(f"- **Aisladas**: {isolated:,} ({isolated/total*100:.1f}%)")
    lines.append("")

    lines.append("*Modo análisis — no se modificó ningún archivo del pipeline.*")
    lines.append("")

    (out / "clusters.md").write_text("\n".join(lines), encoding="utf-8")
