"""SPRINT 26.2 — Full Repository Shadow Execution.

Ejecuta el pipeline completo con CMCC en Shadow sobre TODOS los balances.
No modifica clasificaciones oficiales. Genera 8 reportes en reports/cmcc_full_shadow/.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("full_shadow")

# Force CMCC + Shadow ON, Production OFF
os.environ["CMCC_ENABLE_CMCC"] = "true"
os.environ["CMCC_ENABLE_CMCC_SHADOW"] = "true"
os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "false"

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags
from validation.dataset_manager import DatasetManager

REPORTS_DIR = Path("reports/cmcc_full_shadow")
GS_DB_PATH = "gold_standard.db"
CMCC_THRESHOLD = 0.95
SHADOW_HIT_THRESHOLD = 0.90


def _company_name(path: str) -> str:
    name = Path(path).stem
    name = re.sub(r"\s+", " ", name)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\b\d{4}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    parts = name.split()
    if not parts:
        return path
    prefixes = {"balance", "balances", "eeff", "pre", "prelimiar", "resumen", "bALANCE"}
    while parts and parts[0].lower() in prefixes:
        parts = parts[1:]
    return " ".join(parts[:4]).strip() or name


def _detect_conflict_type(
    method: str, current_code: str | None, cmcc: dict[str, Any] | None
) -> str:
    if cmcc is None:
        return "sin_evidencia"
    score = cmcc.get("score", 0.0)
    cmcc_code = cmcc.get("code")
    if score == 0.0 or cmcc_code is None:
        return "sin_evidencia"
    if score < CMCC_THRESHOLD:
        return "ambiguo"
    if method == "unclassified":
        return "recovery"
    if current_code == cmcc_code:
        return "coincide"
    return "discrepa"


def _layout_type(source_file: str) -> str:
    """Infer layout type from filename heuristics."""
    lower = source_file.lower()
    if "balance" in lower and "8 columnas" in lower:
        return "8_columnas"
    if "tributario" in lower:
        return "tributario"
    if "pre-balance" in lower or "pre balance" in lower or "pre-balances" in lower:
        return "pre_balance"
    if "consolidado" in lower:
        return "consolidado"
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return "excel"
    return "pdf_estandar"


def run_shadow() -> dict[str, Any]:
    """Execute full shadow run across all repositories."""
    print("=" * 70)
    print("SPRINT 26.2 — Full Repository Shadow Execution")
    print("=" * 70)

    features = CMCCFeatureFlags.from_env()
    print(f"  Feature flags: ENABLE_CMCC={features.ENABLE_CMCC}, "
          f"SHADOW={features.ENABLE_CMCC_SHADOW}, "
          f"PRODUCTION={features.ENABLE_CMCC_PRODUCTION}")

    pipeline = HomologationPipeline(str(GS_DB_PATH), features=features)

    print("  Descubriendo archivos...")
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"  Total archivos: {len(all_files)}")

    accounts: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    concept_counter: Counter = Counter()
    company_counter: Counter = Counter()
    layout_counter: Counter = Counter()
    conflict_counter: Counter = Counter()
    method_counter_baseline: Counter = Counter()
    method_counter_cmcc: Counter = Counter()
    score_distribution: list[float] = []
    unknown_total = 0
    shadow_hits_total = 0
    total_processing_time = 0.0

    start_time = time.perf_counter()

    for i, dfile in enumerate(all_files):
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        print(f"  [{i+1}/{len(all_files)}] {rel_path} ... ", end="", flush=True)

        doc_start = time.perf_counter()
        try:
            result = pipeline.process(str(dfile.path))
            doc_elapsed = time.perf_counter() - doc_start
            total_processing_time += doc_elapsed

            file_unknown = result.get("accounts_without_dictionary_match", 0)
            file_total = result.get("accounts_total", 0)
            file_classified = result.get("accounts_classified", 0)
            file_shadow_hits = result.get("cmcc_shadow_hits", 0)
            unknown_total += file_unknown
            shadow_hits_total += file_shadow_hits

            layout = _layout_type(rel_path)
            company = _company_name(rel_path)
            print(f"{file_total} cuentas, {file_unknown} unknown, "
                  f"{file_shadow_hits} shadow hits ({doc_elapsed:.1f}s)")

            for acct in result.get("classified", []):
                method = acct.get("method", "unknown")
                current_code = acct.get("standard_code")
                cmcc_shadow = acct.get("cmcc_shadow")

                method_counter_baseline[method] += 1
                conflict = _detect_conflict_type(method, current_code, cmcc_shadow)
                conflict_counter[conflict] += 1

                cmcc_score = cmcc_shadow.get("score", 0.0) if cmcc_shadow else 0.0
                cmcc_code = cmcc_shadow.get("code") if cmcc_shadow else None
                cmcc_concept = cmcc_shadow.get("concept") if cmcc_shadow else None
                cmcc_method = cmcc_shadow.get("method", "none") if cmcc_shadow else "none"
                cmcc_variant = cmcc_shadow.get("matched_variant") if cmcc_shadow else None

                if conflict == "recovery":
                    shadow_hits_total += 1  # precise count
                    concept_counter[cmcc_concept or "SIN_CONCEPTO"] += 1
                    company_counter[company] += 1
                    layout_counter[layout] += 1
                    score_distribution.append(cmcc_score)
                    method_counter_cmcc[cmcc_method] += 1

                entry = {
                    "Cuenta": acct.get("account_name", ""),
                    "Codigo_Cuenta": acct.get("account_code", ""),
                    "Archivo": rel_path,
                    "Empresa": company,
                    "Layout": layout,
                    "Metodo_Actual": method,
                    "Codigo_Actual": current_code,
                    "Confianza_Actual": acct.get("confidence", 0.0),
                    "Codigo_CMCC": cmcc_code,
                    "Concepto_CMCC": cmcc_concept,
                    "Score_CMCC": cmcc_score,
                    "Metodo_CMCC": cmcc_method,
                    "Variante_CMCC": cmcc_variant,
                    "Tipo_Conflicto": conflict,
                }
                accounts.append(entry)

            doc_entry = {
                "Archivo": rel_path,
                "Empresa": company,
                "Layout": layout,
                "Total_Cuentas": file_total,
                "Clasificadas": file_classified,
                "UNKNOWN": file_unknown,
                "Shadow_Hits": file_shadow_hits,
                "Tiempo_Segundos": round(doc_elapsed, 3),
            }
            documents.append(doc_entry)

        except Exception as e:
            doc_elapsed = time.perf_counter() - doc_start
            print(f"ERROR: {e} ({doc_elapsed:.1f}s)")
            logger.exception("Error processing %s", rel_path)

    total_elapsed = time.perf_counter() - start_time

    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_files": len(all_files),
        "files_processed": len(documents),
        "total_accounts": sum(d["Total_Cuentas"] for d in documents),
        "total_classified": sum(d["Clasificadas"] for d in documents),
        "total_unknown": unknown_total,
        "total_shadow_hits": shadow_hits_total,
        "total_recoveries": conflict_counter.get("recovery", 0),
        "total_coincide": conflict_counter.get("coincide", 0),
        "total_discrepa": conflict_counter.get("discrepa", 0),
        "total_sin_evidencia": conflict_counter.get("sin_evidencia", 0),
        "total_ambiguo": conflict_counter.get("ambiguo", 0),
        "coverage_pct": round(
            sum(1 for a in accounts if a["Score_CMCC"] > 0) / len(accounts) * 100, 1
        ) if accounts else 0.0,
        "recovery_pct": round(
            conflict_counter.get("recovery", 0) / unknown_total * 100, 1
        ) if unknown_total > 0 else 0.0,
        "avg_cmcc_score": round(
            sum(a["Score_CMCC"] for a in accounts if a["Score_CMCC"] > 0)
            / sum(1 for a in accounts if a["Score_CMCC"] > 0), 4
        ) if any(a["Score_CMCC"] > 0 for a in accounts) else 0.0,
        "total_processing_time_seconds": round(total_processing_time, 2),
        "total_wall_time_seconds": round(total_elapsed, 2),
        "method_distribution_baseline": dict(method_counter_baseline.most_common()),
        "method_distribution_cmcc": dict(method_counter_cmcc.most_common()),
        "conflict_distribution": dict(conflict_counter.most_common()),
    }

    return {
        "accounts": accounts,
        "documents": documents,
        "stats": stats,
        "concept_counter": concept_counter,
        "company_counter": company_counter,
        "layout_counter": layout_counter,
        "conflict_counter": conflict_counter,
        "score_distribution": score_distribution,
    }


def generate_reports(data: dict[str, Any]) -> None:
    """Generate all 8 reports in reports/cmcc_full_shadow/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    accounts = data["accounts"]
    documents = data["documents"]
    stats = data["stats"]
    concept_counter = data["concept_counter"]
    company_counter = data["company_counter"]
    layout_counter = data["layout_counter"]
    conflict_counter = data["conflict_counter"]
    score_distribution = data["score_distribution"]

    df_accounts = pd.DataFrame(accounts)
    df_docs = pd.DataFrame(documents)

    # ---- 1. shadow_summary.xlsx ----
    summary_rows = [
        {"Metrica": k, "Valor": v}
        for k, v in stats.items()
        if not isinstance(v, (dict, list))
    ]
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_excel(REPORTS_DIR / "shadow_summary.xlsx", index=False)
    print(f"  shadow_summary.xlsx: {len(df_summary)} rows")

    # ---- 2. shadow_accounts.xlsx ----
    df_accounts.to_excel(REPORTS_DIR / "shadow_accounts.xlsx", index=False)
    print(f"  shadow_accounts.xlsx: {len(df_accounts)} rows")

    # ---- 3. shadow_conflicts.xlsx ----
    conflicts = df_accounts[df_accounts["Tipo_Conflicto"].isin(
        ["discrepa", "ambiguo", "recovery"]
    )].copy()
    conflicts.to_excel(REPORTS_DIR / "shadow_conflicts.xlsx", index=False)
    print(f"  shadow_conflicts.xlsx: {len(conflicts)} rows")

    # ---- 4. company_impact.xlsx ----
    company_rows = []
    for company, cnt in company_counter.most_common():
        company_accounts = [a for a in accounts if a["Empresa"] == company]
        total = len(company_accounts)
        recovered = sum(1 for a in company_accounts if a["Tipo_Conflicto"] == "recovery")
        company_rows.append({
            "Empresa": company,
            "Cuentas_Shadow": cnt,
            "Cuentas_Totales": total,
            "Recuperadas": recovered,
            "Pct_Recuperacion": round(recovered / total * 100, 1) if total else 0,
        })
    df_company = pd.DataFrame(company_rows)
    df_company.to_excel(REPORTS_DIR / "company_impact.xlsx", index=False)
    print(f"  company_impact.xlsx: {len(df_company)} rows")

    # ---- 5. layout_impact.xlsx ----
    layout_rows = []
    for layout, cnt in layout_counter.most_common():
        layout_accounts = [a for a in accounts if a["Layout"] == layout]
        total = len(layout_accounts)
        recovered = sum(1 for a in layout_accounts if a["Tipo_Conflicto"] == "recovery")
        layout_rows.append({
            "Layout": layout,
            "Cuentas_Shadow": cnt,
            "Cuentas_Totales": total,
            "Recuperadas": recovered,
            "Pct_Recuperacion": round(recovered / total * 100, 1) if total else 0,
        })
    df_layout = pd.DataFrame(layout_rows)
    df_layout.to_excel(REPORTS_DIR / "layout_impact.xlsx", index=False)
    print(f"  layout_impact.xlsx: {len(df_layout)} rows")

    # ---- 6. concept_distribution.xlsx ----
    concept_rows = [
        {"Concepto": concept, "Veces": cnt}
        for concept, cnt in concept_counter.most_common()
    ]
    df_concept = pd.DataFrame(concept_rows)
    df_concept.to_excel(REPORTS_DIR / "concept_distribution.xlsx", index=False)
    print(f"  concept_distribution.xlsx: {len(df_concept)} rows")

    # ---- 7. shadow_statistics.json ----
    stats_path = REPORTS_DIR / "shadow_statistics.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  shadow_statistics.json: written")

    # ---- 8. full_shadow.md ----
    md = _build_markdown_report(stats, accounts, documents, concept_counter,
                                 company_counter, layout_counter, conflict_counter,
                                 score_distribution)
    md_path = REPORTS_DIR / "full_shadow.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  full_shadow.md: written")

    print(f"\n  Reportes generados en: {REPORTS_DIR.resolve()}")


def _build_markdown_report(
    stats: dict, accounts: list, documents: list,
    concept_counter: Counter, company_counter: Counter,
    layout_counter: Counter, conflict_counter: Counter,
    score_distribution: list[float],
) -> str:
    lines = []
    lines.append("# SPRINT 26.2 — Full Repository Shadow Execution")
    lines.append("")
    lines.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    total_accounts = stats["total_accounts"]
    total_unknown = stats["total_unknown"]
    total_shadow = stats["total_shadow_hits"]
    total_recoveries = stats["total_recoveries"]

    lines.append("## 1. Resumen Ejecutivo")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---|---|")
    lines.append(f"| Archivos procesados | {stats['files_processed']} / {stats['total_files']} |")
    lines.append(f"| Cuentas totales | {total_accounts} |")
    lines.append(f"| Cuentas clasificadas | {stats['total_classified']} |")
    lines.append(f"| Cuentas UNKNOWN | {total_unknown} |")
    lines.append(f"| Shadow hits (score ≥ {SHADOW_HIT_THRESHOLD}) | {total_shadow} |")
    lines.append(f"| Recuperaciones (UNKNOWN → CMCC) | {total_recoveries} |")
    lines.append(f"| Cobertura CMCC (% cuentas con score > 0) | {stats['coverage_pct']}% |")
    lines.append(f"| Tasa de recuperación | {stats['recovery_pct']}% |")
    lines.append(f"| Score CMCC promedio | {stats['avg_cmcc_score']} |")
    lines.append(f"| Tiempo procesamiento total | {stats['total_processing_time_seconds']}s |")
    lines.append(f"| Tiempo pared total | {stats['total_wall_time_seconds']}s |")
    lines.append("")

    lines.append("## 2. Conflictos Detectados")
    lines.append("")
    lines.append(f"| Tipo | Cantidad | % del total |")
    lines.append(f"|---|---|---|")
    for conflict_type in ["coincide", "recovery", "discrepa", "ambiguo", "sin_evidencia"]:
        cnt = conflict_counter.get(conflict_type, 0)
        pct = round(cnt / len(accounts) * 100, 1) if accounts else 0
        lines.append(f"| {conflict_type} | {cnt} | {pct}% |")
    lines.append("")

    lines.append("## 3. Distribución de Métodos (Línea Base)")
    lines.append("")
    lines.append(f"| Método | Veces |")
    lines.append(f"|---|---|")
    for method, cnt in sorted(stats["method_distribution_baseline"].items()):
        lines.append(f"| {method} | {cnt} |")
    lines.append("")

    lines.append("## 4. Top Conceptos Recuperados")
    lines.append("")
    lines.append(f"| # | Concepto | Veces | % del total |")
    lines.append(f"|---|---|---|---|")
    for idx, (concept, cnt) in enumerate(concept_counter.most_common(30), 1):
        pct = round(cnt / total_recoveries * 100, 1) if total_recoveries else 0
        lines.append(f"| {idx} | {concept} | {cnt} | {pct}% |")
    lines.append("")

    lines.append("## 5. Empresas Más Beneficiadas")
    lines.append("")
    # Top 20 companies by recovery count
    lines.append(f"| # | Empresa | Recuperaciones | Cuentas Totales | % Recuperación |")
    lines.append(f"|---|---|---|---|---|")
    # Build company impact
    company_recovery: dict[str, dict] = {}
    for a in accounts:
        company = a["Empresa"]
        if company not in company_recovery:
            company_recovery[company] = {"total": 0, "recovered": 0}
        company_recovery[company]["total"] += 1
        if a["Tipo_Conflicto"] == "recovery":
            company_recovery[company]["recovered"] += 1
    sorted_companies = sorted(
        company_recovery.items(),
        key=lambda x: x[1]["recovered"],
        reverse=True,
    )
    for idx, (company, info) in enumerate(sorted_companies[:20], 1):
        pct = round(info["recovered"] / info["total"] * 100, 1) if info["total"] else 0
        lines.append(f"| {idx} | {company} | {info['recovered']} | {info['total']} | {pct}% |")
    lines.append("")

    lines.append("## 6. Impacto por Layout")
    lines.append("")
    lines.append(f"| Layout | Shadow Hits | Cuentas Totales | Recuperadas | % Recup. |")
    lines.append(f"|---|---|---|---|---|")
    for layout, cnt in layout_counter.most_common():
        layout_accounts = [a for a in accounts if a["Layout"] == layout]
        total = len(layout_accounts)
        recovered = sum(1 for a in layout_accounts if a["Tipo_Conflicto"] == "recovery")
        pct = round(recovered / total * 100, 1) if total else 0
        lines.append(f"| {layout} | {cnt} | {total} | {recovered} | {pct}% |")
    lines.append("")

    lines.append("## 7. Distribución de Scores CMCC")
    lines.append("")
    if score_distribution:
        bands = [
            ("0.0", "0%"),
            ("0.01 - 0.50", "low"),
            ("0.51 - 0.70", "medium_low"),
            ("0.71 - 0.90", "medium"),
            ("0.91 - 0.95", "high"),
            ("0.96 - 0.99", "very_high"),
            ("1.0", "perfect"),
        ]
        total_with_score = len(score_distribution)
        lines.append(f"| Banda | Cantidad | % |")
        lines.append(f"|---|---|---|")
        for label, _ in bands:
            if label == "0.0":
                cnt = sum(1 for s in score_distribution if s == 0.0)
            elif label == "1.0":
                cnt = sum(1 for s in score_distribution if s == 1.0)
            elif label == "0.01 - 0.50":
                cnt = sum(1 for s in score_distribution if 0.0 < s <= 0.50)
            elif label == "0.51 - 0.70":
                cnt = sum(1 for s in score_distribution if 0.50 < s <= 0.70)
            elif label == "0.71 - 0.90":
                cnt = sum(1 for s in score_distribution if 0.70 < s <= 0.90)
            elif label == "0.91 - 0.95":
                cnt = sum(1 for s in score_distribution if 0.90 < s <= 0.95)
            else:
                cnt = sum(1 for s in score_distribution if 0.95 < s < 1.0)
            pct = round(cnt / total_with_score * 100, 1) if total_with_score else 0
            lines.append(f"| {label} | {cnt} | {pct}% |")
    lines.append("")

    lines.append("## 8. Distribución por Archivo")
    lines.append("")
    lines.append(f"| # | Archivo | Layout | Cuentas | UNKNOWN | Shadow Hits | Tiempo (s) |")
    lines.append(f"|---|---|---|---|---|---|---|")
    for idx, doc in enumerate(documents[:50], 1):
        lines.append(f"| {idx} | {doc['Archivo'][:80]} | {doc['Layout']} | {doc['Total_Cuentas']} | {doc['UNKNOWN']} | {doc['Shadow_Hits']} | {doc['Tiempo_Segundos']} |")
    if len(documents) > 50:
        lines.append(f"| ... | ({len(documents) - 50} archivos más) | ... | ... | ... | ... | ... |")
    lines.append("")

    lines.append("## 9. Métodos CMCC Utilizados")
    lines.append("")
    lines.append(f"| Método CMCC | Veces |")
    lines.append(f"|---|---|")
    for method, cnt in sorted(stats["method_distribution_cmcc"].items()):
        lines.append(f"| {method} | {cnt} |")
    lines.append("")

    lines.append("## 10. Conclusiones")
    lines.append("")
    lines.append(f"- CMCC puede recuperar **{total_recoveries} cuentas UNKNOWN** "
                 f"(**{stats['recovery_pct']}%** del total de {total_unknown} UNKNOWN).")
    lines.append(f"- **{stats['total_coincide']}** cuentas donde CMCC coincide con la clasificación actual "
                 f"({round(stats['total_coincide']/total_accounts*100,1) if total_accounts else 0}%).")
    lines.append(f"- **{conflict_counter.get('discrepa', 0)}** cuentas donde CMCC discrepa con la clasificación actual.")
    lines.append(f"- **{conflict_counter.get('ambiguo', 0)}** casos ambiguos (score > 0 pero < {CMCC_THRESHOLD}).")
    lines.append(f"- **{conflict_counter.get('sin_evidencia', 0)}** cuentas sin evidencia CMCC (score = 0).")
    lines.append("")
    lines.append("---")
    lines.append("*La clasificación oficial NO fue modificada. Modo shadow únicamente.*")

    return "\n".join(lines)


def main():
    data = run_shadow()
    generate_reports(data)
    s = data["stats"]
    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)
    print(f"  Archivos:       {s['files_processed']} / {s['total_files']}")
    print(f"  Cuentas:        {s['total_accounts']}")
    print(f"  UNKNOWN:        {s['total_unknown']}")
    print(f"  Shadow hits:    {s['total_shadow_hits']}")
    print(f"  Recuperaciones: {s['total_recoveries']}")
    print(f"  Cobertura:      {s['coverage_pct']}%")
    print(f"  Recuperación:   {s['recovery_pct']}%")
    print(f"  Score prom:     {s['avg_cmcc_score']}")
    print(f"  Tiempo total:   {s['total_processing_time_seconds']}s")
    print(f"  Reportes en:    {REPORTS_DIR.resolve()}")


if __name__ == "__main__":
    main()
