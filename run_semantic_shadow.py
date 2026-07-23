from __future__ import annotations

import csv
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logging.getLogger("pipeline").setLevel(logging.WARNING)
logging.getLogger("parser_universal").setLevel(logging.WARNING)

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager

REPORTS_DIR = Path("reports/semantic_shadow")
SHADOW_DATA_PATH = REPORTS_DIR / "shadow_data.json"
GS_DB_PATH = "gold_standard.db"
CATALOG_PATH = Path("catalogo_maestro.json")

CATEGORY_TO_SEMANTIC: dict[str, str] = {
    "activo_corriente": "asset",
    "activo_no_corriente": "asset",
    "pasivo_corriente": "liability",
    "pasivo_no_corriente": "liability",
    "patrimonio": "equity",
    "costos": "expense",
    "gastos": "expense",
    "ingresos": "revenue",
    "otros": "other",
}

CONTA_ASSET_CATEGORIES = {"activo_no_corriente"}
COMPATIBLE_CONTRA_ASSET = {"asset", "contra_asset"}

catalog: dict[str, dict[str, Any]] = {}
if CATALOG_PATH.exists():
    with open(CATALOG_PATH) as f:
        raw = json.load(f)
        if isinstance(raw, dict):
            catalog = raw
        elif isinstance(raw, list):
            for entry in raw:
                catalog[entry["codigo_estandar"]] = entry


def _code_semantic_type(code: str | None) -> str | None:
    if not code or code not in catalog:
        return None
    entry = catalog[code]
    cat = entry.get("categoria", "")
    return CATEGORY_TO_SEMANTIC.get(cat)


def _compatible(pipeline_code: str | None, sem_type: str) -> bool:
    if sem_type == "unknown":
        return True
    cat_type = _code_semantic_type(pipeline_code)
    if cat_type is None:
        return True
    if sem_type == "contra_asset":
        return cat_type in COMPATIBLE_CONTRA_ASSET
    return cat_type == sem_type


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_all() -> dict[str, Any]:
    if SHADOW_DATA_PATH.exists():
        print("Cargando datos shadow previos...")
        with open(SHADOW_DATA_PATH) as f:
            return json.load(f)

    print("Inicializando pipeline con shadow mode...")
    pipeline = HomologationPipeline(str(GS_DB_PATH))

    print("Descubriendo archivos...")
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"  Total archivos encontrados: {len(all_files)}")

    data: dict[str, Any] = {
        "files": [],
        "accounts": [],
        "errors": [],
        "generated_at": "",
        "total_elapsed": 0,
    }

    start_total = time.perf_counter()

    for i, dfile in enumerate(all_files):
        file_start = time.perf_counter()
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        print(f"  [{i+1}/{len(all_files)}] {rel_path} ... ", end="", flush=True)

        try:
            result = pipeline.process(str(dfile.path))
            elapsed = time.perf_counter() - file_start
            accounts = result.get("classified", [])
            print(f"{len(accounts)} cuentas, {elapsed:.1f}s")

            for acct in accounts:
                acct["source_group"] = dfile.group
                acct["source_path"] = rel_path
                data["accounts"].append(acct)

            data["files"].append({
                "source_file": result.get("source_file", ""),
                "path": rel_path,
                "group": dfile.group,
                "accounts_total": result["accounts_total"],
                "accounts_classified": len(accounts),
                "semantic_total": result.get("semantic_total", 0),
                "semantic_matches": result.get("semantic_matches", 0),
                "semantic_unknown": result.get("semantic_unknown", 0),
                "semantic_confidence_avg": result.get("semantic_confidence_avg", 0),
                "elapsed": round(elapsed, 3),
            })

        except Exception as e:
            elapsed = time.perf_counter() - file_start
            print(f"ERROR: {e}")
            data["errors"].append({
                "path": rel_path,
                "group": dfile.group,
                "error": str(e),
            })

    data["total_elapsed"] = round(time.perf_counter() - start_total, 3)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SHADOW_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nProcesamiento completado en {data['total_elapsed']}s")
    print(f"Datos guardados en {SHADOW_DATA_PATH}")
    return data


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(data: dict[str, Any]) -> dict[str, Any]:
    accounts = data["accounts"]
    files = data["files"]

    total_accounts = len(accounts)
    semantic_matched = [a for a in accounts if a["semantic_result"]["semantic_type"] != "unknown"]
    semantic_unknown = [a for a in accounts if a["semantic_result"]["semantic_type"] == "unknown"]

    # ---- Section 2: Value added ----
    pipeline_unclassified = [a for a in semantic_matched if a.get("standard_code") is None]

    # ---- Section 3: Coincidences ----
    learning_accounts = [a for a in accounts if a.get("method", "").startswith("learning_")]
    code_accounts = [a for a in accounts if a.get("method") == "code"]
    dict_accounts = [a for a in accounts if a.get("method", "").startswith("dictionary_")]

    def _agreement_rate(group: list[dict]) -> dict:
        total_with_semantic = [a for a in group if a["semantic_result"]["semantic_type"] != "unknown"]
        agree = sum(1 for a in total_with_semantic
                    if _compatible(a.get("standard_code"), a["semantic_result"]["semantic_type"]))
        return {
            "total": len(group),
            "with_semantic": len(total_with_semantic),
            "agree": agree,
            "disagree": len(total_with_semantic) - agree,
            "rate": round(agree / max(len(total_with_semantic), 1) * 100, 1),
        }

    # ---- Section 4: Discrepancies ----
    discrepancies = []
    for a in accounts:
        st = a["semantic_result"]["semantic_type"]
        if st == "unknown":
            continue
        code = a.get("standard_code")
        if not _compatible(code, st):
            pipeline_type = _code_semantic_type(code)
            discrepancies.append({
                "account_name": a["account_name"],
                "pipeline_code": code,
                "pipeline_method": a.get("method", ""),
                "pipeline_type": pipeline_type,
                "semantic_type": st,
                "semantic_rule": a["semantic_result"]["matched_rule"],
                "nature": a.get("nature", ""),
                "source_file": a.get("source_path", ""),
            })

    discrepancy_counter: Counter = Counter()
    for d in discrepancies:
        key = f"{d['pipeline_type']} vs {d['semantic_type']}"
        discrepancy_counter[key] += 1

    # ---- Section 5: Semantic rules analysis ----
    rule_counter: Counter = Counter()
    type_counter: Counter = Counter()
    fin_statement_counter: Counter = Counter()
    econ_nature_counter: Counter = Counter()
    for a in semantic_matched:
        sr = a["semantic_result"]
        r = sr.get("matched_rule", "no_rule")
        rule_counter[r] += 1
        type_counter[sr.get("semantic_type", "unknown")] += 1
        fin_statement_counter[sr.get("financial_statement", "unknown")] += 1
        econ_nature_counter[sr.get("economic_nature", "unknown")] += 1

    # ---- Section 6: Automatic recommendations ----
    from semantic.semantic_rules import RULES, SemanticRule
    defined_rules = {r.name for r in RULES}
    used_rules = set(rule_counter.keys())

    unused_rules = sorted(defined_rules - used_rules)
    rule_accuracy: dict[str, float] = {}
    for rule_name in used_rules:
        rule_accounts = [a for a in semantic_matched
                         if a["semantic_result"]["matched_rule"] == rule_name]
        correct = sum(1 for a in rule_accounts
                      if _compatible(a.get("standard_code"), a["semantic_result"]["semantic_type"]))
        rule_accuracy[rule_name] = round(correct / max(len(rule_accounts), 1) * 100, 1)

    low_precision_rules = {k: v for k, v in rule_accuracy.items() if v < 80}

    # Detect missing rule candidates from top unclassified names
    unclass_names = [a.get("account_name", "") for a in accounts if a.get("method") == "unclassified"]
    word_counter: Counter = Counter()
    import re
    for name in unclass_names:
        tokens = re.findall(r"\b[a-záéíóúñ]{4,}\b", name.lower())
        word_counter.update(tokens)

    known_keywords = {"depreciación", "depreciacion", "deprec", "amortización", "amortizacion",
                       "amortiz", "acumulada", "acum", "ejercicio", "iva", "crédito", "credito",
                       "débito", "debito", "provisión", "provision", "vacaciones", "gasto",
                       "anticipo", "anticipos", "proveedores", "clientes", "cliente"}
    missing_rule_candidates = [
        {"word": w, "count": c}
        for w, c in word_counter.most_common(50)
        if w not in known_keywords and c >= 10
    ]

    return {
        "section1_coverage": {
            "total_cuentas": total_accounts,
            "semantic_interpretadas": len(semantic_matched),
            "semantic_desconocidas": len(semantic_unknown),
            "porcentaje_cobertura": round(len(semantic_matched) / max(total_accounts, 1) * 100, 1),
        },
        "section2_valor_agregado": {
            "pipeline_sin_clasificar_semantic_si": len(pipeline_unclassified),
            "porcentaje": round(len(pipeline_unclassified) / max(total_accounts, 1) * 100, 1),
            "top_cuentas": [
                {"account_name": a["account_name"],
                 "semantic_type": a["semantic_result"]["semantic_type"],
                 "matched_rule": a["semantic_result"]["matched_rule"],
                 "confidence": a["semantic_result"]["confidence"]}
                for a in sorted(pipeline_unclassified,
                                key=lambda x: x["semantic_result"].get("confidence", 0),
                                reverse=True)[:200]
            ],
        },
        "section3_coincidencias": {
            "learning_vs_semantic": _agreement_rate(learning_accounts),
            "codigo_vs_semantic": _agreement_rate(code_accounts),
            "diccionario_vs_semantic": _agreement_rate(dict_accounts),
        },
        "section4_discrepancias": {
            "total": len(discrepancies),
            "por_tipo": [{"tipo": k, "cantidad": v}
                          for k, v in discrepancy_counter.most_common(50)],
            "detalle": sorted(discrepancies,
                              key=lambda x: x.get("source_file", ""))[:500],
        },
        "section5_reglas_semanticas": {
            "top_reglas": [{"regla": k, "veces": v}
                           for k, v in rule_counter.most_common(50)],
            "top_semantic_type": [{"tipo": k, "veces": v}
                                   for k, v in type_counter.most_common(20)],
            "top_financial_statement": [{"tipo": k, "veces": v}
                                         for k, v in fin_statement_counter.most_common(10)],
            "top_economic_nature": [{"tipo": k, "veces": v}
                                     for k, v in econ_nature_counter.most_common(10)],
        },
        "section6_recomendaciones": {
            "reglas_nunca_utilizadas": unused_rules,
            "reglas_baja_precision": low_precision_rules,
            "candidatos_nuevas_reglas": missing_rule_candidates[:30],
            "total_reglas_definidas": len(defined_rules),
            "total_reglas_utilizadas": len(used_rules),
        },
        "files": files,
        "accounts_count": total_accounts,
        "generated_at": data.get("generated_at", ""),
        "total_elapsed": data.get("total_elapsed", 0),
    }


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export(analysis: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    _write_metrics_json(analysis)
    _write_report_md(analysis)
    _write_discrepancies_xlsx(analysis)
    _write_opportunities_xlsx(analysis)


def _write_metrics_json(analysis: dict[str, Any]) -> None:
    path = REPORTS_DIR / "semantic_shadow_metrics.json"
    serializable = {}
    for k, v in analysis.items():
        if k in ("files",):
            continue
        serializable[k] = v
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {path}")


def _write_report_md(analysis: dict[str, Any]) -> None:
    path = REPORTS_DIR / "semantic_shadow_report.md"
    c1 = analysis["section1_coverage"]
    c2 = analysis["section2_valor_agregado"]
    c3 = analysis["section3_coincidencias"]
    c4 = analysis["section4_discrepancias"]
    c5 = analysis["section5_reglas_semanticas"]
    c6 = analysis["section6_recomendaciones"]

    md = []
    md.append("# Evaluación del Semantic Shadow")
    md.append("")
    md.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    md.append(f"Tiempo de procesamiento: {analysis.get('total_elapsed', 0)}s")
    md.append("")

    md.append("## 1. Cobertura")
    md.append("")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---|---|")
    md.append(f"| Total cuentas procesadas | {c1['total_cuentas']} |")
    md.append(f"| Semantic interpretadas | {c1['semantic_interpretadas']} |")
    md.append(f"| Semantic desconocidas | {c1['semantic_desconocidas']} |")
    md.append(f"| Porcentaje cobertura | {c1['porcentaje_cobertura']}% |")
    md.append("")

    md.append("## 2. Valor Agregado")
    md.append("")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---|---|")
    md.append(f"| Pipeline no clasificó pero Semantic sí | {c2['pipeline_sin_clasificar_semantic_si']} |")
    md.append(f"| Porcentaje del total | {c2['porcentaje']}% |")
    md.append("")
    md.append("### Top 200 cuentas donde Semantic detectó algo y Pipeline no clasificó")
    md.append("")
    if c2["top_cuentas"]:
        md.append(f"| # | Cuenta | Tipo Semántico | Regla | Confianza |")
        md.append(f"|---|---|---|---|---|")
        for i, entry in enumerate(c2["top_cuentas"][:200], 1):
            md.append(f"| {i} | {entry['account_name']} | {entry['semantic_type']} | {entry['matched_rule']} | {entry['confidence']} |")
    else:
        md.append("_No se encontraron cuentas en esta categoría._")
    md.append("")

    md.append("## 3. Coincidencias")
    md.append("")
    for label, key in [("Learning vs Semantic", "learning_vs_semantic"),
                       ("Código vs Semantic", "codigo_vs_semantic"),
                       ("Diccionario vs Semantic", "diccionario_vs_semantic")]:
        stats = c3[key]
        md.append(f"### {label}")
        md.append(f"| Métrica | Valor |")
        md.append(f"|---|---|")
        md.append(f"| Total cuentas | {stats['total']} |")
        md.append(f"| Con resultado semántico | {stats['with_semantic']} |")
        md.append(f"| Acuerdan | {stats['agree']} |")
        md.append(f"| Discrepan | {stats['disagree']} |")
        md.append(f"| Tasa de acuerdo | {stats['rate']}% |")
        md.append("")

    md.append("## 4. Discrepancias")
    md.append("")
    md.append(f"Total discrepancias: {c4['total']}")
    md.append("")
    md.append("### Por tipo")
    md.append(f"| # | Tipo | Cantidad |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(c4["por_tipo"][:20], 1):
        md.append(f"| {i} | {entry['tipo']} | {entry['cantidad']} |")
    md.append("")
    md.append(f"### Detalle (primeras 500)")
    if c4["detalle"]:
        md.append(f"| # | Cuenta | Código Pipeline | Método | Tipo Pipeline | Tipo Semantic | Regla Semantic |")
        md.append(f"|---|---|---|---|---|---|---|")
        for i, d in enumerate(c4["detalle"][:500], 1):
            md.append(f"| {i} | {d['account_name']} | {d.get('pipeline_code', '')} | {d['pipeline_method']} | {d.get('pipeline_type', '')} | {d['semantic_type']} | {d['semantic_rule']} |")
    else:
        md.append("_No se encontraron discrepancias._")
    md.append("")

    md.append("## 5. Reglas Semánticas")
    md.append("")
    md.append("### Top reglas utilizadas")
    md.append(f"| # | Regla | Veces |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(c5["top_reglas"][:30], 1):
        md.append(f"| {i} | {entry['regla']} | {entry['veces']} |")
    md.append("")
    md.append("### Top semantic_type")
    md.append(f"| # | Tipo | Veces |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(c5["top_semantic_type"][:20], 1):
        md.append(f"| {i} | {entry['tipo']} | {entry['veces']} |")
    md.append("")
    md.append("### Top financial_statement")
    md.append(f"| # | Tipo | Veces |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(c5["top_financial_statement"][:10], 1):
        md.append(f"| {i} | {entry['tipo']} | {entry['veces']} |")
    md.append("")
    md.append("### Top economic_nature")
    md.append(f"| # | Tipo | Veces |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(c5["top_economic_nature"][:10], 1):
        md.append(f"| {i} | {entry['tipo']} | {entry['veces']} |")
    md.append("")

    md.append("## 6. Recomendaciones Automáticas")
    md.append("")
    md.append(f"Total reglas definidas: {c6['total_reglas_definidas']}")
    md.append(f"Total reglas utilizadas: {c6['total_reglas_utilizadas']}")
    md.append("")
    if c6["reglas_nunca_utilizadas"]:
        md.append("### Reglas nunca utilizadas")
        md.append("")
        for rule in c6["reglas_nunca_utilizadas"]:
            md.append(f"- `{rule}`")
        md.append("")
    if c6["reglas_baja_precision"]:
        md.append("### Reglas con baja precisión (< 80%)")
        md.append(f"| Regla | Precisión |")
        md.append(f"|---|---|")
        for rule, prec in sorted(c6["reglas_baja_precision"].items(),
                                  key=lambda x: x[1]):
            md.append(f"| {rule} | {prec}% |")
        md.append("")
    if c6["candidatos_nuevas_reglas"]:
        md.append("### Candidatos a nuevas reglas (palabras frecuentes no cubiertas)")
        md.append(f"| # | Palabra | Frecuencia en no clasificadas |")
        md.append(f"|---|---|---|")
        for i, entry in enumerate(c6["candidatos_nuevas_reglas"][:30], 1):
            md.append(f"| {i} | {entry['word']} | {entry['count']} |")
        md.append("")

    md.append("---")
    md.append("*Reporte generado automáticamente. No se modificó ninguna clasificación.*")

    path.write_text("\n".join(md), encoding="utf-8")
    print(f"  MD:   {path}")


def _write_discrepancies_xlsx(analysis: dict[str, Any]) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("  XLSX (discrepancias): pandas no disponible")
        return
    path = REPORTS_DIR / "semantic_shadow_discrepancies.xlsx"
    detalle = analysis["section4_discrepancias"].get("detalle", [])
    por_tipo = analysis["section4_discrepancias"].get("por_tipo", [])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        if detalle:
            pd.DataFrame(detalle).to_excel(writer, sheet_name="Discrepancias", index=False)
        else:
            pd.DataFrame({"info": ["Sin discrepancias"]}).to_excel(writer, sheet_name="Discrepancias", index=False)
        if por_tipo:
            pd.DataFrame(por_tipo).to_excel(writer, sheet_name="Por Tipo", index=False)
        else:
            pd.DataFrame({"info": ["Sin datos"]}).to_excel(writer, sheet_name="Por Tipo", index=False)
    print(f"  XLSX: {path}")


def _write_opportunities_xlsx(analysis: dict[str, Any]) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("  XLSX (oportunidades): pandas no disponible")
        return
    path = REPORTS_DIR / "semantic_shadow_new_opportunities.xlsx"
    c2 = analysis["section2_valor_agregado"]
    c6 = analysis["section6_recomendaciones"]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        if c2["top_cuentas"]:
            pd.DataFrame(c2["top_cuentas"]).to_excel(writer, sheet_name="Pipeline no clasificó", index=False)
        else:
            pd.DataFrame({"info": ["Sin datos"]}).to_excel(writer, sheet_name="Pipeline no clasificó", index=False)
        if c6["candidatos_nuevas_reglas"]:
            pd.DataFrame(c6["candidatos_nuevas_reglas"]).to_excel(writer, sheet_name="Candidatos nuevas reglas", index=False)
        else:
            pd.DataFrame({"info": ["Sin datos"]}).to_excel(writer, sheet_name="Candidatos nuevas reglas", index=False)
        unused = [{"regla": r} for r in c6["reglas_nunca_utilizadas"]]
        if unused:
            pd.DataFrame(unused).to_excel(writer, sheet_name="Reglas nunca usadas", index=False)
        else:
            pd.DataFrame({"info": ["Sin datos"]}).to_excel(writer, sheet_name="Reglas nunca usadas", index=False)
    print(f"  XLSX: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("EVALUACIÓN DEL SEMANTIC SHADOW")
    print("=" * 60)

    data = process_all()
    print("\nAnalizando...")
    analysis = analyze(data)

    print("\nExportando reportes...")
    export(analysis)

    print(f"\nReportes generados en: {REPORTS_DIR.resolve()}")
    c1 = analysis["section1_coverage"]
    print(f"Total: {c1['total_cuentas']} cuentas | "
          f"Semantic: {c1['semantic_interpretadas']} ({c1['porcentaje_cobertura']}%) | "
          f"Pipeline sin clasificar: {analysis['section2_valor_agregado']['pipeline_sin_clasificar_semantic_si']}")
