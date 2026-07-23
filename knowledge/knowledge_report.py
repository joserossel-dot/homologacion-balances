from __future__ import annotations

import json
from pathlib import Path


def generate_all_reports(
    output_dir: str | Path,
    clusters: dict[str, dict],
    cluster_summary: list[dict],
    rule_candidates: list[dict],
    synonyms: list[dict],
    ranked: list[dict],
    total_accounts: int,
    total_unclassified: int,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    paths["cluster_xlsx"] = _write_clusters_xlsx(out, cluster_summary)
    paths["rule_xlsx"] = _write_rule_candidates_xlsx(out, rule_candidates)
    paths["synonyms_xlsx"] = _write_synonyms_xlsx(out, synonyms)
    paths["priority_xlsx"] = _write_priority_xlsx(out, ranked)
    paths["report_md"] = _write_report_md(
        out, clusters, cluster_summary, rule_candidates, synonyms, ranked,
        total_accounts, total_unclassified,
    )

    return paths


def _write_clusters_xlsx(out: Path, summary: list[dict]) -> Path:
    try:
        import pandas as pd
    except ImportError:
        return out / "NO_PANDAS"

    path = out / "knowledge_clusters.xlsx"
    rows = []
    for row in summary:
        rows.append({
            "cluster_id": row.get("cluster_id", ""),
            "size": row.get("size", 0),
            "representative": row.get("representative", ""),
            "count_classified_elsewhere": row.get("count_classified_elsewhere", 0),
            "unique_natures": ", ".join(row.get("unique_natures", []) or []),
            "num_files": row.get("num_files", 0),
            "normalized_variants": "\n".join(row.get("normalized_variants", []) or []),
        })
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return path


def _write_rule_candidates_xlsx(out: Path, candidates: list[dict]) -> Path:
    try:
        import pandas as pd
    except ImportError:
        return out / "NO_PANDAS"

    path = out / "knowledge_rule_candidates.xlsx"
    rows = []
    for c in candidates:
        rows.append({
            "cluster_id": c.get("cluster_id", ""),
            "representative": c.get("representative", ""),
            "size": c.get("size", 0),
            "num_files": c.get("num_files", 0),
            "dominant_nature": c.get("dominant_nature", ""),
            "suggested_semantic_type": c.get("suggested_semantic_type", ""),
            "suggested_financial_statement": c.get("suggested_financial_statement", ""),
            "suggested_economic_nature": c.get("suggested_economic_nature", ""),
            "suggested_keywords": ", ".join(c.get("suggested_keywords", []) or []),
            "num_known_classifications": c.get("num_known_classifications", 0),
            "known_codes": ", ".join(c.get("known_codes", []) or []),
            "confidence_score": c.get("confidence_score", 0.0),
        })
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return path


def _write_synonyms_xlsx(out: Path, synonyms: list[dict]) -> Path:
    try:
        import pandas as pd
    except ImportError:
        return out / "NO_PANDAS"

    path = out / "knowledge_synonyms.xlsx"
    rows = []
    for s in synonyms:
        rows.append({
            "group_label": s.get("group_label", ""),
            "num_variants": s.get("num_variants", 0),
            "detected_by": s.get("detected_by", ""),
            "variants": "\n".join(s.get("variants", []) or []),
        })
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return path


def _write_priority_xlsx(out: Path, ranked: list[dict]) -> Path:
    try:
        import pandas as pd
    except ImportError:
        return out / "NO_PANDAS"

    path = out / "knowledge_priority.xlsx"
    rows = []
    for item in ranked:
        rows.append({
            "priority": item.get("priority", 0),
            "type": item.get("type", ""),
            "description": item.get("description", ""),
            "representative": item.get("representative", ""),
            "cluster_size": item.get("cluster_size", 0),
            "confidence": item.get("confidence", 0.0),
            "weighted_impact": item.get("weighted_impact", 0.0),
            "action": item.get("action", ""),
        })
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return path


def _write_report_md(
    out: Path, clusters: dict[str, dict], cluster_summary: list[dict],
    rule_candidates: list[dict], synonyms: list[dict],
    ranked: list[dict], total_accounts: int, total_unclassified: int,
) -> Path:
    path = out / "knowledge_report.md"
    lines: list[str] = []

    lines.append("# Knowledge Discovery Report\n")
    lines.append(f"Generado: {_now()}\n")

    lines.append("## Resumen\n")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---|---|")
    lines.append(f"| Total cuentas | {total_accounts} |")
    lines.append(f"| No clasificadas | {total_unclassified} |")
    lines.append(f"| Clusters formados | {len(clusters)} |")
    lines.append(f"| Candidatos a reglas | {len(rule_candidates)} |")
    lines.append(f"| Grupos sinónimos detectados | {len(synonyms)} |")
    lines.append(f"| Recomendaciones priorizadas | {len(ranked)} |")
    lines.append("")

    lines.append("## Clusters\n")
    if not cluster_summary:
        lines.append("_No se formaron clusters._\n")
    else:
        lines.append(f"| # | Cluster | Size | Representative | Natures | Files |")
        lines.append(f"|---|---|---|---|---|---|")
        for row in cluster_summary[:50]:
            lines.append(
                f"| {row['cluster_id']} | {row['cluster_id']} | {row['size']} | "
                f"{row['representative']} | "
                f"{', '.join(row.get('unique_natures', []) or [])} | {row.get('num_files', 0)} |"
            )
        if len(cluster_summary) > 50:
            lines.append(f"| ... | ... ({len(cluster_summary) - 50} más) | ... | ... | ... | ... |")
        lines.append("")

    lines.append("## Candidatos a Reglas Semánticas\n")
    if not rule_candidates:
        lines.append("_No se encontraron candidatos._\n")
    else:
        lines.append(
            "| # | Representative | Size | Semantic Type | Keywords | Confidence |"
        )
        lines.append(
            "|---|---|---|---|---|---|"
        )
        for i, c in enumerate(rule_candidates[:30], 1):
            kws = ", ".join(c.get("suggested_keywords", []) or [])
            lines.append(
                f"| {i} | {c['representative']} | {c['size']} | "
                f"{c['suggested_semantic_type']} | {kws} | {c['confidence_score']} |"
            )
        if len(rule_candidates) > 30:
            lines.append(f"| ... | ... ({len(rule_candidates) - 30} más) | ... | ... | ... | ... |")
        lines.append("")

    lines.append("## Sinónimos Detectados\n")
    if not synonyms:
        lines.append("_No se detectaron sinónimos._\n")
    else:
        lines.append("| # | Grupo | Variantes | Detectado por |")
        lines.append("|---|---|---|---|")
        for i, s in enumerate(synonyms, 1):
            lines.append(
                f"| {i} | {s['group_label']} | {s['num_variants']} | {s.get('detected_by', '')} |"
            )
        lines.append("")
        lines.append("### Detalle de variantes\n")
        for s in synonyms:
            lines.append(f"- **{s['group_label']}**:")
            for v in s.get("variants", [])[:10]:
                lines.append(f"  - `{v}`")
            if len(s.get("variants", [])) > 10:
                lines.append(f"  - ... y {len(s['variants']) - 10} más")
            lines.append("")

    lines.append("## Priorización de Mejoras\n")
    if not ranked:
        lines.append("_No hay mejoras priorizadas._\n")
    else:
        lines.append("| # | Tipo | Descripción | Cluster Size | Confianza | Impacto Ponderado |")
        lines.append("|---|---|---|---|---|---|")
        for item in ranked[:30]:
            lines.append(
                f"| {item['priority']} | {item['type']} | {item['description']} | "
                f"{item['cluster_size']} | {item['confidence']} | {item['weighted_impact']} |"
            )
        if len(ranked) > 30:
            lines.append(f"| ... | ... ({len(ranked) - 30} más) | ... | ... | ... | ... |")
        lines.append("")

    lines.append("## Recomendaciones Detalladas\n")
    for item in ranked[:10]:
        lines.append(f"### {item['priority']}. [{item['type']}] {item['description']}")
        lines.append(f"- **Impacto ponderado**: {item['weighted_impact']}")
        lines.append(f"- **Confianza**: {item['confidence']}")
        lines.append(f"- **Acción sugerida**: {item['action']}")
        lines.append("")

    lines.append("---\n")
    lines.append("*Reporte generado automáticamente por Knowledge Discovery Engine.*\n")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
