from __future__ import annotations

from pathlib import Path
from datetime import datetime

import pandas as pd

from split_ac01.split_engine import ClassificationResult


REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "split_ac01"


def generate_reports(
    results: list[ClassificationResult],
    statistics: dict,
    coverage: dict,
    output_dir: str | Path | None = None,
) -> dict[str, Path]:
    output_dir = Path(output_dir) if output_dir else REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    variant_mapping_path = _write_variant_mapping(results, output_dir)
    paths["variant_mapping"] = variant_mapping_path

    split_stats_path = _write_split_statistics(statistics, coverage, output_dir)
    paths["split_statistics"] = split_stats_path

    coverage_path = _write_coverage_before_after(
        statistics, coverage, results, output_dir
    )
    paths["coverage_before_after"] = coverage_path

    review_needed_path = _write_review_needed(results, output_dir)
    paths["review_needed"] = review_needed_path

    report_md_path = _write_split_report(
        statistics, coverage, results, output_dir
    )
    paths["split_report"] = report_md_path

    return paths


def _write_variant_mapping(
    results: list[ClassificationResult],
    output_dir: Path,
) -> Path:
    rows = []
    for r in results:
        rows.append({
            "variant": r.variant,
            "normalized": r.normalized,
            "original_concept": r.original_concept,
            "target_code": r.target_code or "UNCLASSIFIED",
            "target_name": r.target_name or "Sin clasificar",
            "confidence": r.confidence,
            "needs_review": "SI" if r.needs_review else "NO",
            "matched_rules": "; ".join(r.matched_rules) if r.matched_rules else "",
        })
    df = pd.DataFrame(rows)
    path = output_dir / "variant_mapping.xlsx"
    df.to_excel(path, index=False)
    return path


def _write_split_statistics(
    statistics: dict,
    coverage: dict,
    output_dir: Path,
) -> Path:
    by_concept = statistics.get("by_concept", {})
    concept_rows = []
    for code, count in sorted(by_concept.items()):
        pct = round(count / statistics["total_variants"] * 100, 2) if statistics["total_variants"] else 0.0
        concept_rows.append({
            "sub_concept": code,
            "variants": count,
            "percentage": pct,
        })

    df_concept = pd.DataFrame(concept_rows)
    confidence_rows = []
    for bucket, count in sorted(statistics.get("confidence_buckets", {}).items()):
        confidence_rows.append({
            "confidence_bucket": bucket,
            "variants": count,
        })
    df_confidence = pd.DataFrame(confidence_rows)

    rule_rows = []
    for rule, count in sorted(
        statistics.get("matched_rules", {}).items(),
        key=lambda x: -x[1],
    ):
        rule_rows.append({"rule": rule, "matches": count})
    df_rules = pd.DataFrame(rule_rows)

    path = output_dir / "split_statistics.xlsx"
    with pd.ExcelWriter(path) as writer:
        df_concept.to_excel(writer, sheet_name="by_concept", index=False)
        df_confidence.to_excel(writer, sheet_name="confidence_buckets", index=False)
        df_rules.to_excel(writer, sheet_name="matched_rules", index=False)

    return path


def _write_coverage_before_after(
    statistics: dict,
    coverage: dict,
    results: list[ClassificationResult],
    output_dir: Path,
) -> Path:
    before = coverage.get("before", {})
    after = coverage.get("after", {})

    rows = [
        {"metric": "Total variants", "before": before.get("AC.01", 0),
         "after": statistics["total_variants"]},
        {"metric": "Unique concepts", "before": 1,
         "after": after.get("sub_concepts", 0)},
        {"metric": "Auto-classified", "before": 0,
         "after": after.get("auto_classified", 0)},
        {"metric": "Needs review", "before": statistics["total_variants"],
         "after": after.get("needs_review", 0)},
    ]

    by_concept = statistics.get("by_concept", {})
    for code, count in sorted(by_concept.items()):
        label = CONCEPT_SHORT.get(code, code)
        rows.append({f"metric": f"  → {label}", "before": "-",
                     "after": count})

    df = pd.DataFrame(rows)
    path = output_dir / "coverage_before_after.xlsx"
    df.to_excel(path, index=False)
    return path


def _write_review_needed(
    results: list[ClassificationResult],
    output_dir: Path,
) -> Path:
    review = [r for r in results if r.needs_review]
    rows = []
    for r in review:
        rows.append({
            "variant": r.variant,
            "normalized": r.normalized,
            "best_guess_code": r.target_code or "UNCLASSIFIED",
            "best_guess_name": r.target_name or "Sin clasificar",
            "confidence": r.confidence,
            "matched_rules": "; ".join(r.matched_rules) if r.matched_rules else "",
            "review_reason": _review_reason(r),
        })
    df = pd.DataFrame(rows)
    path = output_dir / "review_needed.xlsx"
    df.to_excel(path, index=False)
    return path


def _review_reason(r: ClassificationResult) -> str:
    if not r.matched_rules:
        return "Sin reglas léxicas aplicables"
    if r.confidence < 0.5:
        return f"Confianza baja ({r.confidence})"
    return "Ambiguo: múltiples reglas con igual peso"


def _write_split_report(
    statistics: dict,
    coverage: dict,
    results: list[ClassificationResult],
    output_dir: Path,
) -> Path:
    by_concept = statistics.get("by_concept", {})
    after = coverage.get("after", {})

    lines = []
    lines.append("# Informe de División — AC.01 Caja y Bancos")
    lines.append("")
    lines.append(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Variantes totales AC.01: **{statistics['total_variants']}**")
    lines.append(f"- Clasificadas automáticamente: **{statistics['auto_classified']}** ({statistics['auto_classification_rate']}%)")
    lines.append(f"- Requieren revisión humana: **{statistics['needs_review']}** ({round(statistics['needs_review']/statistics['total_variants']*100, 1) if statistics['total_variants'] else 0}%)")
    lines.append("")
    lines.append("## Distribución por Sub-Concepto")
    lines.append("")
    lines.append("| Sub-Concepto | Variantes | % |")
    lines.append("|---|---|---|")
    for code in ["AC.01.01", "AC.01.02", "AC.01.03"]:
        count = by_concept.get(code, 0)
        pct = round(count / statistics['total_variants'] * 100, 1) if statistics['total_variants'] else 0
        name = CONCEPT_SHORT.get(code, code)
        lines.append(f"| {name} | {count} | {pct}% |")
    unclassified = by_concept.get("UNCLASSIFIED", 0)
    if unclassified:
        lines.append(f"| Sin clasificar | {unclassified} | {round(unclassified/statistics['total_variants']*100, 1)}% |")
    lines.append("")
    lines.append("## Mejora de Cobertura")
    lines.append("")
    lines.append(f"- Antes: 1 concepto (AC.01) cubriendo **{statistics['total_variants']}** variantes")
    lines.append(f"- Después: **{after.get('sub_concepts', 0)}** sub-conceptos")
    lines.append(f"  - {by_concept.get('AC.01.01', 0)} → AC.01.01 Caja")
    lines.append(f"  - {by_concept.get('AC.01.02', 0)} → AC.01.02 Bancos")
    lines.append(f"  - {by_concept.get('AC.01.03', 0)} → AC.01.03 Equivalentes")
    lines.append(f"  - {by_concept.get('UNCLASSIFIED', 0)} → Sin clasificar")
    lines.append("")
    lines.append("## Riesgos")
    lines.append("")
    lines.append("1. **Precisión de reglas léxicas:** Las reglas pueden generar falsos positivos en variantes que contengan palabras clave en contextos no financieros (ej. 'Caja de Compensación').")
    lines.append(f"2. **Ruido OCR:** {statistics['needs_review']} variantes ({round(statistics['needs_review']/statistics['total_variants']*100, 1)}%) no pudieron clasificarse automáticamente, probablemente debido a ruido OCR o datos mal clasificados en AC.01 original.")
    lines.append("3. **Ambigüedad semántica:** Variantes con palabras clave de múltiples sub-conceptos (ej. 'Dep. a Plazo Bancos' tiene tanto 'plazo' como 'banco').")
    lines.append("4. **Compatibilidad v1:** AC.01 sigue existiendo como padre. No se modificaron IDs ni datos existentes. Los pipelines que referencian AC.01 continúan funcionando.")
    lines.append("")

    path = output_dir / "split_report.md"
    path.write_text("\n".join(lines))
    return path


CONCEPT_SHORT = {
    "AC.01.01": "AC.01.01 Caja",
    "AC.01.02": "AC.01.02 Bancos",
    "AC.01.03": "AC.01.03 Equivalentes al Efectivo",
    "UNCLASSIFIED": "Sin clasificar",
}
