from __future__ import annotations

import csv
import json
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager
from learning.engine import LearningEngine
from gold_standard.storage import GoldStorage as GoldStandardStorage

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logging.getLogger("pipeline").setLevel(logging.WARNING)
logging.getLogger("parser_universal").setLevel(logging.WARNING)

REPORTS_DIR = Path("reports/audit")
AUDIT_DATA_PATH = REPORTS_DIR / "audit_data.json"
GS_DB_PATH = "gold_standard.db"
CATALOG_PATH = Path("catalogo_maestro.json")

STANDARD_NAMES: dict[str, str] = {}
if CATALOG_PATH.exists():
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)
        if isinstance(catalog, list):
            for entry in catalog:
                STANDARD_NAMES[entry["codigo_estandar"]] = entry["nombre_estandar"]
        elif isinstance(catalog, dict):
            for code, info in catalog.items():
                STANDARD_NAMES[code] = info.get("nombre_estandar", info.get("name", code))


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def process_all_files() -> dict[str, Any]:
    if AUDIT_DATA_PATH.exists():
        print("Cargando datos de auditoría previos...")
        with open(AUDIT_DATA_PATH) as f:
            return json.load(f)

    print("Inicializando pipeline...")
    pipeline = HomologationPipeline(str(GS_DB_PATH))

    print("Descubriendo archivos...")
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"  Total archivos encontrados: {len(all_files)}")

    data: dict[str, Any] = {
        "files": [],
        "accounts": [],
        "ignored": [],
        "errors": [],
        "pipeline_errors": [],
    }

    start_total = time.perf_counter()

    for i, dfile in enumerate(all_files):
        file_start = time.perf_counter()
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        print(f"  [{i+1}/{len(all_files)}] {rel_path} ... ", end="", flush=True)

        try:
            result = pipeline.process(str(dfile.path))
            elapsed = time.perf_counter() - file_start
            result["group"] = dfile.group
            result["file_type"] = dfile.file_type
            result["elapsed"] = round(elapsed, 3)
            print(f"{result['accounts_total']} cuentas, {result['elapsed']:.1f}s")

            file_entry = {
                "source_file": result["source_file"],
                "path": rel_path,
                "group": dfile.group,
                "file_type": dfile.file_type,
                "accounts_total": result["accounts_total"],
                "accounts_classified": result["accounts_classified"],
                "accounts_ignored": result["accounts_ignored"],
                "accounts_unclassified": result["accounts_without_dictionary_match"],
                "learning_hits": result["learning_hits"],
                "learning_exact": result["learning_exact"],
                "learning_fuzzy": result["learning_fuzzy"],
                "fallback_classifier": result["fallback_classifier"],
                "elapsed": result["elapsed"],
            }
            data["files"].append(file_entry)

            for acct in result.get("classified", []):
                acct["source_group"] = dfile.group
                acct["source_path"] = rel_path
                data["accounts"].append(acct)

            for ign in result.get("ignored", []):
                ign["source_path"] = rel_path
                ign["source_group"] = dfile.group
                data["ignored"].append(ign)

        except Exception as e:
            elapsed = time.perf_counter() - file_start
            print(f"ERROR: {e}")
            data["pipeline_errors"].append({
                "path": rel_path,
                "group": dfile.group,
                "error": str(e),
                "elapsed": round(elapsed, 3),
            })

    total_elapsed = time.perf_counter() - start_total
    data["total_elapsed"] = round(total_elapsed, 3)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nProcesamiento completado en {total_elapsed:.1f}s")
    print(f"Datos guardados en {AUDIT_DATA_PATH}")
    return data


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _classify(source: str) -> str:
    if source.startswith("learning_exact"):
        return "Learning Exact"
    if source.startswith("learning_fuzzy"):
        return "Learning Fuzzy"
    if source == "code":
        return "Código"
    if source == "dictionary_exact":
        return "Diccionario Exact"
    if source == "dictionary_fuzzy":
        return "Diccionario Fuzzy"
    if source == "unclassified":
        return "Sin clasificar"
    return source


def _company_name(path: str) -> str:
    name = Path(path).stem
    name = re.sub(r"\s+", " ", name)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\b\d{4}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    parts = name.split()
    if not parts:
        return path
    if parts[0].lower() in ("balance", "balances", "eeff", "pre", "prelimiar",
                             "resumen", "balance", "eeff", "bALANCE"):
        parts = parts[1:]
    return " ".join(parts[:4]).strip() or name


def _tokenize(name: str) -> list[str]:
    name = name.lower().strip()
    name = re.sub(r"[(),.;:¿?¡!\"'/-]", " ", name)
    tokens = [t for t in name.split() if len(t) > 2 and not t.isdigit()]
    return tokens


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    accounts = data["accounts"]
    files = data["files"]
    ignored = data["ignored"]
    pipeline_errors = data["pipeline_errors"]

    # 1. Totals
    total_docs = len(files) + len(pipeline_errors)
    files_ok = len(files)
    files_err = len(pipeline_errors)
    total_accounts = len(accounts)
    total_ignored = len(ignored)

    # 2. Method distribution
    method_counts: dict[str, int] = defaultdict(int)
    for a in accounts:
        m = a.get("method", "unknown")
        method_counts[_classify(m)] += 1

    learning_exact = sum(1 for a in accounts if a.get("method") == "learning_exact")
    learning_fuzzy = sum(1 for a in accounts if a.get("method") == "learning_fuzzy")
    code_hits = sum(1 for a in accounts if a.get("method") == "code")
    dict_exact = sum(1 for a in accounts if a.get("method") == "dictionary_exact")
    dict_fuzzy = sum(1 for a in accounts if a.get("method") == "dictionary_fuzzy")
    unclassified = sum(1 for a in accounts if a.get("method") == "unclassified")

    # 3. Top 100 unclassified
    unclass_list = [a for a in accounts if a.get("method") == "unclassified"]
    unclass_by_name: dict[str, dict[str, Any]] = {}
    for a in unclass_list:
        name = a.get("account_name", "").strip()
        if not name:
            continue
        if name not in unclass_by_name:
            unclass_by_name[name] = {
                "name": name,
                "frequency": 0,
                "companies": set(),
                "files": set(),
                "natures": Counter(),
            }
        entry = unclass_by_name[name]
        entry["frequency"] += 1
        company = _company_name(a.get("source_path", ""))
        entry["companies"].add(company)
        entry["files"].add(a.get("source_path", ""))
        entry["natures"][a.get("nature", "unknown")] += 1

    top_unclassified = sorted(unclass_by_name.values(),
                              key=lambda x: x["frequency"], reverse=True)[:100]

    for entry in top_unclassified:
        entry["companies"] = sorted(entry["companies"])[:5]
        entry["files"] = sorted(entry["files"])[:5]
        entry["top_nature"] = entry["natures"].most_common(1)[0][0] if entry["natures"] else ""

    # 4. Top 100 learning rules
    learning_accounts = [a for a in accounts
                         if a.get("method", "").startswith("learning_")]
    learning_by_source: dict[str, dict[str, Any]] = {}
    for a in learning_accounts:
        reason = a.get("reason", "")
        code = a.get("standard_code", "")
        key = f"{code}|{reason}"
        if key not in learning_by_source:
            learning_by_source[key] = {
                "standard_code": code,
                "standard_name": STANDARD_NAMES.get(code, ""),
                "reason": reason,
                "count": 0,
                "examples": [],
            }
        entry = learning_by_source[key]
        entry["count"] += 1
        if len(entry["examples"]) < 3:
            entry["examples"].append(a.get("account_name", ""))

    top_learning = sorted(learning_by_source.values(),
                          key=lambda x: x["count"], reverse=True)[:100]

    # 5. Top 100 standard codes
    code_counts: Counter = Counter()
    for a in accounts:
        code = a.get("standard_code")
        if code:
            code_counts[code] += 1

    top_codes = []
    for code, count in code_counts.most_common(100):
        top_codes.append({
            "code": code,
            "name": STANDARD_NAMES.get(code, ""),
            "count": count,
        })

    # 6. Companies with highest unclassified rate
    company_stats: dict[str, dict[str, Any]] = {}
    for f in files:
        company = _company_name(f.get("source_file", ""))
        if company not in company_stats:
            company_stats[company] = {"total": 0, "classified": 0, "unclassified": 0,
                                       "files": set()}
        company_stats[company]["total"] += f.get("accounts_classified", 0) + f.get("accounts_unclassified", 0)
        company_stats[company]["classified"] += f.get("accounts_classified", 0)
        company_stats[company]["unclassified"] += f.get("accounts_unclassified", 0)
        company_stats[company]["files"].add(f.get("source_file", ""))

    company_rates = []
    for company, st in company_stats.items():
        total = st["total"]
        if total > 0:
            pct = round(st["unclassified"] / total * 100, 1)
        else:
            pct = 0
        company_rates.append({
            "company": company,
            "total_accounts": total,
            "classified": st["classified"],
            "unclassified": st["unclassified"],
            "unclassified_pct": pct,
            "files": len(st["files"]),
        })
    company_rates.sort(key=lambda x: x["unclassified_pct"], reverse=True)

    # 7. Most frequent words in unclassified
    word_counter: Counter = Counter()
    for a in unclass_list:
        name = a.get("account_name", "")
        for token in _tokenize(name):
            word_counter[token] += 1

    top_words = [{"word": w, "count": c} for w, c in word_counter.most_common(100)]

    # 8. Potential synonyms (words appearing in multiple unclassified names)
    unclass_names = list(unclass_by_name.keys())
    word_to_names: dict[str, set[str]] = defaultdict(set)
    for name in unclass_names:
        for token in _tokenize(name):
            word_to_names[token].add(name)

    potential_synonyms = []
    for word, names in sorted(word_to_names.items(), key=lambda x: len(x[1]), reverse=True):
        if len(names) >= 3 and word_counter.get(word, 0) >= 5:
            potential_synonyms.append({
                "word": word,
                "count": word_counter.get(word, 0),
                "names_count": len(names),
                "example_names": sorted(names)[:5],
            })

    # 9. Potential new standard accounts
    potential_new = []
    for name, info in sorted(unclass_by_name.items(),
                              key=lambda x: x[1]["frequency"], reverse=True):
        if info["frequency"] >= 3:
            tokens = _tokenize(name)
            potential_new.append({
                "name": name,
                "frequency": info["frequency"],
                "companies_count": len(info["companies"]),
                "tokens": tokens,
            })

    # 10. Gold Standard conflicts
    learning_engine = LearningEngine(str(GS_DB_PATH))
    conflicts = _detect_gs_conflicts(learning_engine, accounts)

    # 11. Method distribution from data
    method_distribution = {
        "Learning Exact": learning_exact,
        "Learning Fuzzy": learning_fuzzy,
        "Código": code_hits,
        "Diccionario Exact": dict_exact,
        "Diccionario Fuzzy": dict_fuzzy,
        "Sin clasificar": unclassified,
    }

    return {
        "totals": {
            "documentos_procesados": files_ok,
            "documentos_con_error": files_err,
            "total_documentos": total_docs,
            "total_cuentas": total_accounts,
            "cuentas_ignoradas": total_ignored,
        },
        "method_distribution": method_distribution,
        "classifiable_total": total_accounts,
        "classified_total": total_accounts - unclassified,
        "unclassified_total": unclassified,
        "classification_rate": round((total_accounts - unclassified) / max(total_accounts, 1) * 100, 1),
        "top_unclassified": top_unclassified[:100],
        "top_learning": top_learning[:100],
        "top_codes": top_codes[:100],
        "company_rates": company_rates,
        "top_words": top_words[:100],
        "potential_synonyms": potential_synonyms[:50],
        "potential_new_accounts": potential_new[:30],
        "gold_standard_conflicts": conflicts,
        "files": files,
        "pipeline_errors": pipeline_errors,
    }


def _detect_gs_conflicts(learning_engine: LearningEngine,
                          accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    gs_records: list[dict[str, Any]] = []

    try:
        storage = GoldStandardStorage(GS_DB_PATH)
        gs_records = storage.list_all()
    except Exception:
        pass

    if not gs_records:
        return [{"note": "Gold Standard vacío — no se detectaron conflictos"}]

    name_to_gs: dict[str, list[dict]] = defaultdict(list)
    for rec in gs_records:
        name_to_gs[rec.get("original_name", "").lower().strip()].append(rec)

    account_to_codes: dict[str, set[str]] = defaultdict(set)
    for a in accounts:
        name = a.get("account_name", "").lower().strip()
        code = a.get("standard_code")
        if name and code:
            account_to_codes[name].add(code)

    for name, gs_list in name_to_gs.items():
        gs_codes = set(r.get("standard_code") for r in gs_list)
        pipeline_codes = account_to_codes.get(name, set())
        if gs_codes and pipeline_codes and gs_codes != pipeline_codes:
            conflicts.append({
                "account_name": name,
                "gs_codes": sorted(gs_codes),
                "pipeline_codes": sorted(pipeline_codes),
                "mismatch": True,
            })

    return conflicts[:50]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _write_markdown(analysis: dict[str, Any], path: Path) -> None:
    t = analysis["totals"]
    md = []
    md.append("# Auditoría Completa del Homologador")
    md.append(f"\nGenerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    md.append("")

    md.append("## 1. Resumen General")
    md.append(f"| Métrica | Valor |")
    md.append(f"|---|---|")
    md.append(f"| Documentos procesados | {t['documentos_procesados']} |")
    md.append(f"| Documentos con error | {t['documentos_con_error']} |")
    md.append(f"| Total documentos | {t['total_documentos']} |")
    md.append(f"| Total cuentas (con saldo) | {t['total_cuentas']} |")
    md.append(f"| Cuentas ignoradas (solo movimiento) | {t['cuentas_ignoradas']} |")
    md.append(f"| Clasificadas | {analysis['classified_total']} |")
    md.append(f"| Sin clasificar | {analysis['unclassified_total']} |")
    md.append(f"| Tasa de clasificación | {analysis['classification_rate']}% |")
    md.append(f"| Tiempo total | {data.get('total_elapsed', 0):.1f}s |")
    md.append("")

    md.append("## 2. Distribución por Método de Clasificación")
    md.append(f"| Método | Cuentas | Porcentaje |")
    md.append(f"|---|---|---|")
    method_dist = analysis["method_distribution"]
    total = sum(method_dist.values()) or 1
    for method in ["Learning Exact", "Learning Fuzzy", "Código", "Diccionario Exact",
                   "Diccionario Fuzzy", "Sin clasificar"]:
        cnt = method_dist.get(method, 0)
        pct = round(cnt / total * 100, 1)
        md.append(f"| {method} | {cnt} | {pct}% |")
    md.append("")

    md.append("## 3. Top 100 Cuentas Sin Clasificar")
    md.append(f"| # | Nombre | Frecuencia | Empresas | Naturaleza |")
    md.append(f"|---|---|---|---|---|")
    for i, entry in enumerate(analysis["top_unclassified"][:100], 1):
        companies = ", ".join(entry.get("companies", [])[:3])
        md.append(f"| {i} | {entry['name']} | {entry['frequency']} | {companies} | {entry.get('top_nature', '')} |")
    md.append("")

    md.append("## 4. Top 100 Reglas del Learning Más Utilizadas")
    md.append(f"| # | Código | Nombre Estándar | Veces | Ejemplo |")
    md.append(f"|---|---|---|---|---|")
    for i, entry in enumerate(analysis["top_learning"][:100], 1):
        example = entry.get("examples", [""])[0] if entry.get("examples") else ""
        md.append(f"| {i} | {entry['standard_code']} | {entry.get('standard_name', '')} | {entry['count']} | {example} |")
    md.append("")

    md.append("## 5. Top 100 Códigos Estándar Más Utilizados")
    md.append(f"| # | Código | Nombre | Veces |")
    md.append(f"|---|---|---|---|")
    for i, entry in enumerate(analysis["top_codes"][:100], 1):
        md.append(f"| {i} | {entry['code']} | {entry.get('name', '')} | {entry['count']} |")
    md.append("")

    md.append("## 6. Empresas con Mayor % de Cuentas Sin Clasificar")
    md.append(f"| # | Empresa | Total Cuentas | Clasificadas | Sin Clasificar | % |")
    md.append(f"|---|---|---|---|---|---|")
    for i, entry in enumerate(analysis["company_rates"][:50], 1):
        md.append(f"| {i} | {entry['company']} | {entry['total_accounts']} | {entry['classified']} | {entry['unclassified']} | {entry['unclassified_pct']}% |")
    md.append("")

    md.append("## 7. Palabras Más Frecuentes en Cuentas Sin Clasificar")
    md.append(f"| # | Palabra | Frecuencia |")
    md.append(f"|---|---|---|")
    for i, entry in enumerate(analysis["top_words"][:50], 1):
        md.append(f"| {i} | {entry['word']} | {entry['count']} |")
    md.append("")

    md.append("## 8. Posibles Sinónimos No Incorporados")
    md.append(f"| # | Palabra | Frecuencia | Cuentas distintas | Ejemplos |")
    md.append(f"|---|---|---|---|---|")
    for i, entry in enumerate(analysis["potential_synonyms"][:30], 1):
        examples = ", ".join(entry.get("example_names", [])[:3])
        md.append(f"| {i} | {entry['word']} | {entry['count']} | {entry['names_count']} | {examples} |")
    md.append("")

    md.append("## 9. Posibles Nuevas Cuentas Estándar para el Catálogo")
    md.append(f"| # | Nombre | Frecuencia | Empresas | Posibles Tokens |")
    md.append(f"|---|---|---|---|---|")
    for i, entry in enumerate(analysis["potential_new_accounts"][:20], 1):
        tokens = ", ".join(entry.get("tokens", [])[:5])
        md.append(f"| {i} | {entry['name']} | {entry['frequency']} | {entry['companies_count']} | {tokens} |")
    md.append("")

    conflicts = analysis.get("gold_standard_conflicts", [])
    md.append("## 10. Conflictos del Gold Standard")
    if conflicts and "note" in conflicts[0]:
        md.append(f"_{conflicts[0]['note']}_")
    else:
        md.append(f"| # | Cuenta | Códigos GS | Códigos Pipeline |")
        md.append(f"|---|---|---|---|")
        for i, c in enumerate(conflicts[:30], 1):
            md.append(f"| {i} | {c['account_name']} | {', '.join(c['gs_codes'])} | {', '.join(c['pipeline_codes'])} |")
    md.append("")

    # 11. Executive summary with prioritized improvements
    md.append("## 11. Informe Ejecutivo — Prioridades de Mejora")
    priorities = _build_priorities(analysis)
    for p in priorities:
        md.append(f"### {p['priority']}. {p['title']} (Impacto: {p['impact']})")
        md.append(f"{p['description']}")
        md.append(f"- **Evidencia:** {p['evidence']}")
        md.append(f"- **Acción sugerida:** {p['action']}")
        md.append("")

    path.write_text("\n".join(md), encoding="utf-8")
    print(f"  Markdown: {path}")


def _build_priorities(analysis: dict[str, Any]) -> list[dict[str, str]]:
    pct = analysis["classification_rate"]
    unclassified_count = analysis["unclassified_total"]
    total = analysis["classifiable_total"]
    top_unclass = analysis["top_unclassified"][:10]
    top_words = analysis["top_words"][:10]
    method_dist = analysis["method_distribution"]
    conflicts = analysis.get("gold_standard_conflicts", [])

    priorities = []

    priorities.append({
        "priority": "1",
        "title": f"Aumentar cobertura del diccionario ({pct}% clasificado)",
        "impact": "CRÍTICO",
        "description": f"Solo {pct}% de las cuentas se clasifican automáticamente. "
                       f"{unclassified_count} cuentas de {total} quedan sin clasificar.",
        "evidence": f"Métodos: Learning Exact {method_dist.get('Learning Exact', 0)}, "
                    f"Learning Fuzzy {method_dist.get('Learning Fuzzy', 0)}, "
                    f"Código {method_dist.get('Código', 0)}, "
                    f"Diccionario Exact {method_dist.get('Diccionario Exact', 0)}, "
                    f"Diccionario Fuzzy {method_dist.get('Diccionario Fuzzy', 0)}.",
        "action": "Incorporar las cuentas sin clasificar más frecuentes al diccionario y al Gold Standard. "
                  "Priorizar las que aparecen en múltiples empresas.",
    })

    word_evidence = ", ".join([f"'{w['word']}' ({w['count']}x)" for w in top_words[:5]])
    priorities.append({
        "priority": "2",
        "title": "Crear reglas semánticas para términos frecuentes",
        "impact": "ALTO",
        "description": f"Palabras como {word_evidence} aparecen repetidamente en cuentas sin clasificar. "
                       "Estos términos son candidatos para nuevas reglas semánticas.",
        "evidence": f"Top palabras: {word_evidence}.",
        "action": "Analizar las 50 palabras más frecuentes y crear reglas semánticas para los patrones detectados.",
    })

    if unclassified_count > 0:
        top_name = top_unclass[0]["name"] if top_unclass else "N/A"
        top_freq = top_unclass[0]["frequency"] if top_unclass else 0
        priorities.append({
            "priority": "3",
            "title": f"Priorizar carga de cuentas más frecuentes al Gold Standard",
            "impact": "ALTO",
            "description": f"La cuenta '{top_name}' aparece {top_freq} veces sin clasificar. "
                           "Agregar estas cuentas al Gold Standard permitiría clasificación inmediata "
                           "por learning_exact.",
            "evidence": f"Top cuenta sin clasificar: '{top_name}' ({top_freq} ocurrencias).",
            "action": "Agregar las 100 cuentas sin clasificar más frecuentes al Gold Standard.",
        })

    if method_dist.get("Learning Exact", 0) == 0 and method_dist.get("Learning Fuzzy", 0) == 0:
        priorities.append({
            "priority": "4",
            "title": "Poblar el Gold Standard (0 hits de learning)",
            "impact": "ALTO",
            "description": "El motor de aprendizaje no tuvo ningún acierto. "
                           "El Gold Standard está vacío o las cuentas no coinciden con ningún registro.",
            "evidence": "Learning Exact: 0, Learning Fuzzy: 0.",
            "action": "Poblar gold_standard.db con al menos 500 registros de cuentas clasificadas manualmente.",
        })

    if conflicts and "note" not in conflicts[0]:
        priorities.append({
            "priority": "5",
            "title": f"Resolver {len(conflicts)} conflictos del Gold Standard",
            "impact": "MEDIO",
            "description": "Existen discrepancias entre el Gold Standard y las clasificaciones actuales "
                           "del pipeline para las mismas cuentas.",
            "evidence": f"{len(conflicts)} conflictos detectados.",
            "action": "Revisar y armonizar las clasificaciones en conflicto.",
        })

    priorities.append({
        "priority": "6",
        "title": "Incorporar sinónimos al diccionario",
        "impact": "MEDIO",
        "description": f"Se detectaron {len(analysis.get('potential_synonyms', []))} términos que aparecen "
                       "en múltiples cuentas sin clasificar y podrían ser sinónimos no incorporados.",
        "evidence": f"{len(analysis.get('potential_synonyms', []))} candidatos a sinónimos.",
        "action": "Agregar los términos más frecuentes como sinónimos en el diccionario.",
    })

    return priorities


def _write_csv(analysis: dict[str, Any], name: str, rows: list[dict], path: Path) -> None:
    if not rows:
        (path / f"{name}.csv").write_text("(sin datos)", encoding="utf-8")
        return
    filepath = path / f"{name}.csv"
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  CSV: {filepath}")


def _write_excel(analysis: dict[str, Any], path: Path) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("  Excel: pandas no disponible, saltando")
        return

    filepath = path / "audit_completo.xlsx"
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        # Overview
        overview = pd.DataFrame([
            {"Métrica": k, "Valor": v}
            for k, v in {
                "Documentos OK": analysis["totals"]["documentos_procesados"],
                "Documentos con error": analysis["totals"]["documentos_con_error"],
                "Cuentas totales": analysis["totals"]["total_cuentas"],
                "Clasificadas": analysis["classified_total"],
                "Sin clasificar": analysis["unclassified_total"],
                "Tasa clasificación": f"{analysis['classification_rate']}%",
            }.items()
        ])
        overview.to_excel(writer, sheet_name="Resumen", index=False)

        # Method distribution
        method_df = pd.DataFrame([
            {"Método": k, "Cuentas": v}
            for k, v in analysis["method_distribution"].items()
        ])
        method_df.to_excel(writer, sheet_name="Métodos", index=False)

        # Unclassified top
        if analysis["top_unclassified"]:
            u_df = pd.DataFrame(analysis["top_unclassified"])
            cols = [c for c in ["name", "frequency", "companies", "files", "top_nature"]
                    if c in u_df.columns]
            u_df[cols].to_excel(writer, sheet_name="Sin Clasificar Top", index=False)

        # Top codes
        if analysis["top_codes"]:
            pd.DataFrame(analysis["top_codes"]).to_excel(
                writer, sheet_name="Códigos Estándar", index=False)

        # Learning top
        if analysis["top_learning"]:
            pd.DataFrame(analysis["top_learning"]).to_excel(
                writer, sheet_name="Learning Top", index=False)

        # Company rates
        if analysis["company_rates"]:
            pd.DataFrame(analysis["company_rates"]).to_excel(
                writer, sheet_name="Empresas", index=False)

        # Top words
        if analysis["top_words"]:
            pd.DataFrame(analysis["top_words"]).to_excel(
                writer, sheet_name="Palabras Frecuentes", index=False)

        # Potential synonyms
        if analysis["potential_synonyms"]:
            ps_df = pd.DataFrame(analysis["potential_synonyms"])
            if "example_names" in ps_df.columns:
                ps_df["example_names"] = ps_df["example_names"].apply(
                    lambda x: ", ".join(x) if isinstance(x, list) else x)
            ps_df.to_excel(writer, sheet_name="Sinónimos Potenciales", index=False)

        # Potential new accounts
        if analysis["potential_new_accounts"]:
            pd.DataFrame(analysis["potential_new_accounts"]).to_excel(
                writer, sheet_name="Nuevas Cuentas", index=False)

        # Conflicts
        if analysis["gold_standard_conflicts"]:
            c_df = pd.DataFrame(analysis["gold_standard_conflicts"])
            c_df.to_excel(writer, sheet_name="Conflictos GS", index=False)

    print(f"  Excel: {filepath}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("AUDITORÍA COMPLETA DEL HOMOLOGADOR")
    print("=" * 60)

    data = process_all_files()
    print("\nAnalizando datos...")
    analysis = analyze(data)

    print("\nGenerando reportes...")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    _write_markdown(analysis, REPORTS_DIR / "audit_report.md")

    _write_csv(analysis, "top_unclassified",
               [{k: v for k, v in e.items() if k != "files"}
                for e in analysis["top_unclassified"]],
               REPORTS_DIR)
    _write_csv(analysis, "top_learning", analysis["top_learning"], REPORTS_DIR)
    _write_csv(analysis, "top_codes", analysis["top_codes"], REPORTS_DIR)
    _write_csv(analysis, "company_rates", analysis["company_rates"], REPORTS_DIR)
    _write_csv(analysis, "top_words", analysis["top_words"], REPORTS_DIR)
    _write_csv(analysis, "potential_synonyms",
               [{"word": e["word"], "count": e["count"], "names_count": e["names_count"]}
                for e in analysis["potential_synonyms"]],
               REPORTS_DIR)
    _write_csv(analysis, "potential_new_accounts",
               [{"name": e["name"], "frequency": e["frequency"]}
                for e in analysis["potential_new_accounts"]],
               REPORTS_DIR)

    _write_excel(analysis, REPORTS_DIR)

    # Save analysis JSON
    analysis_json = {k: v for k, v in analysis.items()
                     if k not in ("top_unclassified", "top_learning", "top_codes",
                                  "company_rates", "top_words", "potential_synonyms",
                                  "potential_new_accounts", "gold_standard_conflicts",
                                  "files")}
    serializable = {}
    for k, v in analysis_json.items():
        if isinstance(v, set):
            serializable[k] = list(v)
        elif isinstance(v, Counter):
            serializable[k] = dict(v)
        else:
            serializable[k] = v
    with open(REPORTS_DIR / "analysis.json", "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)

    print(f"\nReportes generados en: {REPORTS_DIR.resolve()}")
    print("Archivos:")
    for p in sorted(REPORTS_DIR.iterdir()):
        size = p.stat().st_size
        print(f"  {p.name} ({size:,} bytes)")
