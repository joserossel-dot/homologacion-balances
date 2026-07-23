from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_shadow_report(
    pipeline_results: list[dict[str, Any]],
    output_dir: str | Path = "reports/semantic_shadow",
) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_accounts: list[dict[str, Any]] = []
    for pr in pipeline_results:
        all_accounts.extend(pr.get("classified", []))

    total_cuentas = len(all_accounts)
    semantic_matched: list[dict[str, Any]] = [
        a for a in all_accounts
        if a.get("semantic_result", {}).get("semantic_type") != "unknown"
    ]
    semantic_unknown: list[dict[str, Any]] = [
        a for a in all_accounts
        if a.get("semantic_result", {}).get("semantic_type") == "unknown"
    ]

    rule_counter: Counter = Counter()
    type_counter: Counter = Counter()
    for a in semantic_matched:
        rule = a["semantic_result"].get("matched_rule", "no_rule")
        rule_counter[rule] += 1
        st = a["semantic_result"].get("semantic_type", "unknown")
        type_counter[st] += 1

    semantic_but_not_pipeline: list[dict[str, Any]] = [
        a for a in semantic_matched
        if a.get("standard_code") is None
    ]

    discrepancias: list[dict[str, Any]] = [
        a for a in all_accounts
        if a.get("semantic_result", {}).get("semantic_type") != "unknown"
        and a.get("method") == "unclassified"
    ]

    pipeline_classified: list[dict[str, Any]] = [
        a for a in all_accounts
        if a.get("method") != "unclassified"
    ]

    divergencias: list[dict[str, Any]] = [
        a for a in all_accounts
        if a.get("semantic_result", {}).get("semantic_type") == "unknown"
        and a.get("method") != "unclassified"
    ]

    top_confidence = sorted(
        all_accounts,
        key=lambda a: a.get("semantic_result", {}).get("confidence", 0),
        reverse=True,
    )[:10]

    low_confidence = [
        a for a in semantic_matched
        if a.get("semantic_result", {}).get("confidence", 1) < 0.8
    ]

    semantic_stats: dict[str, Any] = {}
    for pr in pipeline_results:
        for k in ("semantic_total", "semantic_matches", "semantic_unknown", "semantic_confidence_avg"):
            if k in pr:
                semantic_stats[k] = semantic_stats.get(k, 0) + (
                    pr[k] if k != "semantic_confidence_avg" else 0
                )
    if pipeline_results:
        confs = [
            pr.get("semantic_confidence_avg", 0)
            for pr in pipeline_results
            if pr.get("semantic_confidence_avg", 0) > 0
        ]
        if confs:
            semantic_stats["semantic_confidence_avg"] = round(
                sum(confs) / len(confs), 4
            )

    md: list[str] = []
    md.append("# Shadow Report — Semantic Engine")
    md.append("")
    md.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    md.append("")
    md.append("## Resumen General")
    md.append("")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---|---|")
    md.append(f"| Archivos procesados | {len(pipeline_results)} |")
    md.append(f"| Total cuentas (con saldo) | {total_cuentas} |")
    md.append(f"| Semantic reconocidas | {len(semantic_matched)} |")
    md.append(f"| Semantic desconocidas | {len(semantic_unknown)} |")
    md.append(f"| Tasa reconocimiento semántico | {round(len(semantic_matched) / max(total_cuentas, 1) * 100, 1)}% |")
    md.append("")

    md.append("## Top Reglas Semánticas Utilizadas")
    md.append("")
    md.append(f"| # | Regla | Veces | % |")
    md.append(f"|---|---|---|---|")
    total_rules = sum(rule_counter.values()) or 1
    for i, (rule, cnt) in enumerate(rule_counter.most_common(20), 1):
        md.append(f"| {i} | {rule} | {cnt} | {round(cnt / total_rules * 100, 1)}% |")
    md.append("")

    md.append("## Top Semantic Types")
    md.append("")
    md.append(f"| # | Tipo Semántico | Veces | % |")
    md.append(f"|---|---|---|---|")
    total_types = sum(type_counter.values()) or 1
    for i, (st, cnt) in enumerate(type_counter.most_common(20), 1):
        md.append(f"| {i} | {st} | {cnt} | {round(cnt / total_types * 100, 1)}% |")
    md.append("")

    md.append(f"## Cuentas donde Semantic detectó algo y Pipeline NO clasificó ({len(discrepancias)})")
    md.append("")
    if discrepancias:
        md.append(f"| # | Cuenta | Tipo Semántico | Regla | Confianza |")
        md.append(f"|---|---|---|---|---|")
        for i, a in enumerate(discrepancias[:50], 1):
            sr = a.get("semantic_result", {})
            md.append(f"| {i} | {a['account_name']} | {sr.get('semantic_type', '')} | {sr.get('matched_rule', '')} | {sr.get('confidence', 0)} |")
    else:
        md.append("_No se encontraron discrepancias — toda cuenta reconocida por Semantic fue también clasificada por el pipeline._")
    md.append("")

    md.append(f"## Cuentas donde Semantic NO reconoció pero Pipeline sí clasificó ({len(divergencias)})")
    md.append("")
    if divergencias:
        md.append(f"| # | Cuenta | Método Pipeline | Código |")
        md.append(f"|---|---|---|---|")
        for i, a in enumerate(divergencias[:50], 1):
            md.append(f"| {i} | {a['account_name']} | {a.get('method', '')} | {a.get('standard_code', '')} |")
    else:
        md.append("_No se encontraron divergencias._")
    md.append("")

    md.append("## Top 10 Cuentas con Mayor Confianza Semántica")
    md.append("")
    md.append(f"| # | Cuenta | Tipo | Regla | Confianza |")
    md.append(f"|---|---|---|---|---|")
    for i, a in enumerate(top_confidence[:10], 1):
        sr = a.get("semantic_result", {})
        md.append(f"| {i} | {a['account_name']} | {sr.get('semantic_type', '')} | {sr.get('matched_rule', '')} | {sr.get('confidence', 0)} |")
    md.append("")

    md.append("## Cuentas con Confianza Semántica Baja (< 0.8)")
    md.append("")
    if low_confidence:
        md.append(f"| # | Cuenta | Tipo | Regla | Confianza |")
        md.append(f"|---|---|---|---|---|")
        for i, a in enumerate(low_confidence[:30], 1):
            sr = a.get("semantic_result", {})
            md.append(f"| {i} | {a['account_name']} | {sr.get('semantic_type', '')} | {sr.get('matched_rule', '')} | {sr.get('confidence', 0)} |")
    else:
        md.append("_Todas las cuentas reconocidas tienen confianza ≥ 0.8._")
    md.append("")

    md.append("## Métricas por Archivo")
    md.append("")
    md.append(f"| # | Archivo | Cuentas | Semantic Match | Semantic Unknown | Conf Avg |")
    md.append(f"|---|---|---|---|---|---|")
    for i, pr in enumerate(pipeline_results, 1):
        md.append(f"| {i} | {pr.get('source_file', '')} | {pr.get('semantic_total', 0)} | {pr.get('semantic_matches', 0)} | {pr.get('semantic_unknown', 0)} | {pr.get('semantic_confidence_avg', 0)} |")
    md.append("")

    path = out / "semantic_shadow_report.md"
    path.write_text("\n".join(md), encoding="utf-8")
    print(f"  Shadow report: {path}")
    return str(path)
