#!/usr/bin/env python3
"""Analyze accounts classified ONLY by MotorHibridoLocal (legacy) but NOT by HomologationPipeline.

For each such account, reports the exact mechanism that produced the legacy classification,
based on the `metodo` field returned by MotorHibridoLocal.clasificar().

Usage:
    python3 tools/analyze_legacy_gap.py
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser_universal import ParserPDF, CuentaRaw, OrigenColumna

# Import legacy classifier
from app_validacion import MotorHibridoLocal, normalizar_nombre, REGLAS_COMPILADAS

# Import new pipeline
from pipeline.homologation_pipeline import HomologationPipeline


def load_dictionary(path: str | Path = "diccionario.json") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_pdf(pdf_path: str | Path) -> list[CuentaRaw]:
    parser = ParserPDF()
    resultado = parser.parsear(Path(pdf_path))
    return resultado.cuentas


def classify_all(pdf_paths: list[str | Path]):
    dictionary = load_dictionary()
    hp = HomologationPipeline()
    motor_legacy = MotorHibridoLocal(dictionary)

    total_accounts = 0
    both_classified = 0
    both_unclassified = 0
    legacy_only = 0
    new_only = 0
    different_code = 0

    legacy_only_details = []
    different_details = []

    for pdf_path in pdf_paths:
        pdf_name = Path(pdf_path).name
        cuentas = parse_pdf(pdf_path)

        for c in cuentas:
            if c.monto is None and not c.codigo:
                continue
            if not c.codigo and re.match(r'^(total|subtotal|suma|totales)', c.nombre.strip(), re.IGNORECASE):
                continue

            total_accounts += 1

            # Legacy classification (FULL MotorHibridoLocal)
            legacy_result = motor_legacy.clasificar(c)
            legacy_code = legacy_result.get("codigo_estandar")
            legacy_method = legacy_result.get("metodo", "")
            legacy_confidence = legacy_result.get("confianza", 0.0)

            # New pipeline classification
            new_result = hp._classify_account(c.codigo or "", c.nombre)
            new_code = new_result.get("standard_code")
            new_method = new_result.get("method", "")
            new_confidence = new_result.get("confidence", 0.0)

            if legacy_code and new_code:
                if legacy_code == new_code:
                    both_classified += 1
                else:
                    different_code += 1
                    different_details.append({
                        "pdf": pdf_name,
                        "nombre": c.nombre,
                        "codigo_raw": c.codigo or "",
                        "monto": c.monto,
                        "origen_columna": c.origen_columna.value,
                        "legacy_code": legacy_code,
                        "legacy_method": legacy_method,
                        "legacy_confidence": legacy_confidence,
                        "new_code": new_code,
                        "new_method": new_method,
                        "new_confidence": new_confidence,
                    })
            elif legacy_code and not new_code:
                legacy_only += 1
                legacy_only_details.append({
                    "pdf": pdf_name,
                    "nombre": c.nombre,
                    "codigo_raw": c.codigo or "",
                    "monto": c.monto,
                    "origen_columna": c.origen_columna.value,
                    "legacy_code": legacy_code,
                    "legacy_method": legacy_method,
                    "legacy_confidence": legacy_confidence,
                })
            elif new_code and not legacy_code:
                new_only += 1
            else:
                both_unclassified += 1

    return {
        "total": total_accounts,
        "both_classified": both_classified,
        "both_unclassified": both_unclassified,
        "legacy_only": legacy_only,
        "new_only": new_only,
        "different_code": different_code,
        "legacy_only_details": legacy_only_details,
        "different_details": different_details,
        "pdfs": [str(p) for p in pdf_paths],
    }


def analyze_mechanisms(details: list[dict]) -> dict:
    """Analyze which legacy mechanisms produced classifications."""

    # Simplify method field to primary mechanism
    def primary_mechanism(method: str) -> str:
        if method.startswith("columna_ambiguo"):
            return "desambiguacion_columna_pre"
        if "+columna" in method:
            return "correccion_columna_post"
        if method.startswith("regla_regex"):
            return "regex"
        if method.startswith("regla_especial"):
            return "regla_especial"
        if method.startswith("codigo"):
            return "codigo"
        if method.startswith("diccionario_exacto"):
            return "diccionario_exacto"
        if method.startswith("diccionario_fuzzy"):
            return "diccionario_fuzzy"
        return method

    mechanism_counts = Counter()
    for d in details:
        mech = primary_mechanism(d["legacy_method"])
        mechanism_counts[mech] += 1

    # Per-regex-pattern breakdown (which specific pattern matched)
    regex_codes = Counter()
    regex_patterns: Counter[str] = Counter()
    regex_detail = []
    for d in details:
        if d["legacy_method"].startswith("regla_regex"):
            regex_codes[d["legacy_code"]] += 1
            regex_detail.append(d)
            # Determine which specific regex pattern matched (by name simulation)
            nombre_norm = normalizar_nombre(d["nombre"])
            best_pattern = "unknown"
            best_conf = 0
            for pat, cod, conf in REGLAS_COMPILADAS:
                if pat.search(nombre_norm) and conf > best_conf:
                    best_pattern = f"{cod}({pat.pattern[:30]}...)"
                    best_conf = conf
            regex_patterns[best_pattern] += 1

    # Confidence distribution
    conf_buckets = Counter()
    for d in details:
        conf = d["legacy_confidence"]
        if conf >= 0.95:
            conf_buckets["0.95-1.00"] += 1
        elif conf >= 0.85:
            conf_buckets["0.85-0.95"] += 1
        elif conf >= 0.70:
            conf_buckets["0.70-0.85"] += 1
        else:
            conf_buckets["< 0.70"] += 1

    return {
        "mechanism_counts": dict(mechanism_counts),
        "regex_by_code": dict(regex_codes),
        "regex_by_pattern": dict(regex_patterns),
        "confidence_buckets": dict(conf_buckets),
        "total": len(details),
    }


def build_pareto(mechanism_counts: dict) -> list[dict]:
    """Build Pareto table sorted by count descending, with cumulative %."""
    sorted_items = sorted(mechanism_counts.items(), key=lambda x: -x[1])
    total = sum(v for _, v in sorted_items)
    cumulative = 0
    pareto = []
    for mech, count in sorted_items:
        cumulative += count
        pareto.append({
            "mechanism": mech,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
            "cumulative_pct": round(cumulative / total * 100, 1) if total else 0,
        })
    return pareto


def generate_report(results: dict) -> str:
    lines = []

    # Summary
    lines.append("# Análisis de 61 cuentas clasificadas solo por MotorHibridoLocal\n")
    lines.append(f"**PDFs analizados:** {len(results['pdfs'])}")
    for p in results["pdfs"]:
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append(f"**Total cuentas extraídas:** {results['total']}")
    lines.append("")

    # Classification comparison
    lines.append("## Comparación de clasificación\n")
    lines.append(f"| Categoría | Cuentas | % del total |")
    lines.append(f"|-----------|---------|-------------|")
    total = results["total"]
    lines.append(f"| Ambos clasifican (mismo código) | {results['both_classified']} | {results['both_classified']/total*100:.1f}% |")
    lines.append(f"| Ambos clasifican (código diferente) | {results['different_code']} | {results['different_code']/total*100:.1f}% |")
    lines.append(f"| Solo LEGACY clasifica | {results['legacy_only']} | {results['legacy_only']/total*100:.1f}% |")
    lines.append(f"| Solo NEW clasifica | {results['new_only']} | {results['new_only']/total*100:.1f}% |")
    lines.append(f"| Ninguno clasifica | {results['both_unclassified']} | {results['both_unclassified']/total*100:.1f}% |")
    lines.append("")

    # Legacy-only analysis
    legacy_analysis = analyze_mechanisms(results["legacy_only_details"])
    lines.append(f"## Análisis de {legacy_analysis['total']} cuentas clasificadas solo por LEGACY\n")

    # Pareto by mechanism
    pareto = build_pareto(legacy_analysis["mechanism_counts"])
    lines.append("### Pareto por mecanismo\n")
    lines.append("| # | Mecanismo | Cuentas | % | % Acumulado |")
    lines.append("|---|-----------|---------|---|-------------|")
    for i, p in enumerate(pareto, 1):
        lines.append(f"| {i} | {p['mechanism']} | {p['count']} | {p['pct']}% | {p['cumulative_pct']}% |")
    lines.append("")

    # Pareto by regex target code
    lines.append("### Pareto por código regex (dentro de las cuentas solo-LEGACY)\n")
    regex_pareto = build_pareto(legacy_analysis["regex_by_code"])
    if regex_pareto:
        lines.append("| # | Código estándar | Cuentas | % | % Acumulado |")
        lines.append("|---|----------------|---------|---|-------------|")
        for i, p in enumerate(regex_pareto, 1):
            lines.append(f"| {i} | {p['mechanism']} | {p['count']} | {p['pct']}% | {p['cumulative_pct']}% |")
    else:
        lines.append("_(ninguna)_")
    lines.append("")

    # Pareto by specific regex pattern
    lines.append("### Pareto por patrón regex específico (dentro de las cuentas solo-LEGACY)\n")
    pat_pareto = build_pareto(legacy_analysis["regex_by_pattern"])
    if pat_pareto:
        lines.append("| # | Patrón regex | Código | Cuentas | % | % Acumulado |")
        lines.append("|---|--------------|--------|---------|---|-------------|")
        for i, p in enumerate(pat_pareto, 1):
            code_label = p['mechanism'].split('(')[0] if '(' in p['mechanism'] else p['mechanism']
            lines.append(f"| {i} | `{p['mechanism']}` | {code_label} | {p['count']} | {p['pct']}% | {p['cumulative_pct']}% |")
    else:
        lines.append("_(ninguna)_")
    lines.append("")

    # Confidence distribution
    lines.append("### Distribución de confianza (cuentas solo-LEGACY)\n")
    lines.append("| Rango | Cuentas | % |")
    lines.append("|-------|---------|---|")
    for bucket in ["0.95-1.00", "0.85-0.95", "0.70-0.85", "< 0.70"]:
        count = legacy_analysis["confidence_buckets"].get(bucket, 0)
        pct = count / legacy_analysis["total"] * 100 if legacy_analysis["total"] else 0
        lines.append(f"| {bucket} | {count} | {pct:.1f}% |")
    lines.append("")

    # Detailed listing
    lines.append("## Listado detallado de cuentas clasificadas solo por LEGACY\n")
    lines.append("| PDF | Nombre | Código Raw | Monto | Columna | Código LEGACY | Método LEGACY | Confianza |")
    lines.append("|-----|--------|-----------|-------|---------|---------------|--------------|----------|")
    for d in results["legacy_only_details"]:
        monto_str = f"{d['monto']:,.0f}" if d['monto'] is not None else "—"
        lines.append(f"| {d['pdf']} | {d['nombre']} | {d['codigo_raw']} | {monto_str} | {d['origen_columna']} | {d['legacy_code']} | {d['legacy_method']} | {d['legacy_confidence']:.2f} |")
    lines.append("")

    # Different-code analysis
    diff_analysis = analyze_mechanisms(results["different_details"])
    if diff_analysis["total"] > 0:
        lines.append(f"## Análisis de {diff_analysis['total']} cuentas con código DIFERENTE entre LEGACY y NEW\n")

        diff_pareto = build_pareto(diff_analysis["mechanism_counts"])
        lines.append("### Pareto por mecanismo LEGACY\n")
        lines.append("| # | Mecanismo LEGACY | Cuentas | % | % Acumulado |")
        lines.append("|---|------------------|---------|---|-------------|")
        for i, p in enumerate(diff_pareto, 1):
            lines.append(f"| {i} | {p['mechanism']} | {p['count']} | {p['pct']}% | {p['cumulative_pct']}% |")
        lines.append("")

        lines.append("### Listado detallado\n")
        lines.append("| PDF | Nombre | Raw | Columna | LEGACY | Método LEGACY | NEW | Método NEW |")
        lines.append("|-----|--------|-----|---------|--------|--------------|-----|-----------|")
        for d in results["different_details"]:
            lines.append(f"| {d['pdf']} | {d['nombre']} | {d['codigo_raw']} | {d['origen_columna']} | {d['legacy_code']} | {d['legacy_method']} | {d['new_code']} | {d['new_method']} |")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Use all HOLDOUT PDFs (19 files) for a representative sample
    base = Path("datasets/HOLDOUT")
    pdf_paths = sorted(base.glob("*.pdf"))

    if not pdf_paths:
        print("ERROR: No PDFs found in datasets/HOLDOUT/", file=sys.stderr)
        sys.exit(1)

    print("Processing PDFs...", file=sys.stderr)
    results = classify_all(pdf_paths)
    print(f"Total accounts: {results['total']}", file=sys.stderr)
    print(f"Legacy only: {results['legacy_only']}", file=sys.stderr)
    print(f"Different code: {results['different_code']}", file=sys.stderr)

    report = generate_report(results)
    output_path = "analysis_legacy_gap.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to {output_path}", file=sys.stderr)
