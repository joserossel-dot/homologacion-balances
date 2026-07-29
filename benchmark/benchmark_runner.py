"""
benchmark_runner.py — Benchmark independiente de certificación.

Procesa datasets/HOLDOUT/ con HomologationPipeline y mide:

  - tiempo de procesamiento por archivo
  - cuentas detectadas / homologadas / ignoradas / desconocidas
  - errores y warnings
  - distribución de métodos de clasificación
  - precisión de extracción y homologación

Uso:
    python3 benchmark/benchmark_runner.py

Salida:
    benchmark/benchmark_results.csv
    benchmark/dataset_manifest.csv
    benchmark/benchmark_summary.md
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger("benchmark")

BENCHMARK_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCHMARK_DIR.parent
HOLDOUT_DIR = REPO_DIR / "datasets" / "HOLDOUT"
RESULTS_CSV = BENCHMARK_DIR / "benchmark_results.csv"
MANIFEST_CSV = BENCHMARK_DIR / "dataset_manifest.csv"
SUMMARY_MD = BENCHMARK_DIR / "benchmark_summary.md"

sys.path.insert(0, str(REPO_DIR))


def build_manifest() -> list[dict[str, Any]]:
    """Construye el manifiesto del dataset HOLDOUT."""
    files = sorted(HOLDOUT_DIR.glob("*.pdf"))
    manifest: list[dict[str, Any]] = []
    for f in files:
        stat = f.stat()
        manifest.append({
            "archivo": f.name,
            "ruta": str(f.relative_to(REPO_DIR)),
            "tamano_bytes": stat.st_size,
            "tamano_kb": round(stat.st_size / 1024, 1),
            "tipo": f.suffix.lower().lstrip("."),
        })
    return manifest


def save_manifest(manifest: list[dict[str, Any]]) -> None:
    with open(MANIFEST_CSV, "w", newline="", encoding="utf-8") as f:
        if not manifest:
            f.write("archivo,ruta,tamano_bytes,tamano_kb,tipo\n")
            return
        writer = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        writer.writeheader()
        writer.writerows(manifest)
    logger.info("Manifiesto escrito: %s", MANIFEST_CSV)


def save_results(results: list[dict[str, Any]]) -> None:
    fieldnames = [
        "archivo",
        "tiempo_procesamiento_s",
        "cuentas_detectadas",
        "cuentas_homologadas",
        "cuentas_ignoradas",
        "cuentas_desconocidas",
        "errores",
        "warnings",
        "precision_extraccion",
        "precision_homologacion",
        "learning_hits",
        "metodo_codigo",
        "metodo_diccionario_exacto",
        "metodo_diccionario_fuzzy",
        "metodo_regex",
        "metodo_semantico",
        "metodo_learning_exact",
        "metodo_learning_fuzzy",
        "metodo_decision_agree",
        "metodo_decision_sm_high",
        "metodo_decision_regex",
        "metodo_decision_conflict",
        "metodo_decision_unknown",
        "metodo_unclassified",
        "confianza_promedio",
        "cuentas_alta_confianza",
        "cuentas_media_confianza",
        "cuentas_baja_confianza",
        "requirio_ocr",
    ]
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    logger.info("Resultados escritos: %s", RESULTS_CSV)


def process_file(pdf_path: Path) -> dict[str, Any]:
    """Procesa un archivo y retorna métricas."""
    from pipeline.homologation_pipeline import HomologationPipeline

    start = time.perf_counter()
    errores: list[str] = []
    warnings_list: list[str] = []
    result: dict[str, Any] = {}

    try:
        hp = HomologationPipeline()
        result = hp.process(pdf_path)
    except Exception as e:
        tb = traceback.format_exc()
        errores.append(f"{type(e).__name__}: {e}")
        errores.append(tb)

    elapsed = round(time.perf_counter() - start, 3)

    accounts_total = result.get("accounts_total", 0)
    accounts_classified = result.get("accounts_classified", 0)
    accounts_ignored = result.get("accounts_ignored", 0)
    accounts_unknown = result.get("accounts_without_dictionary_match", 0)
    learning_hits = result.get("learning_hits", 0)
    semantic_matches = result.get("semantic_matches", 0)

    classified_list = result.get("classified", [])
    if result.get("advertencias"):
        warnings_list = result["advertencias"]
    if result.get("warnings"):
        for w in result["warnings"]:
            if w not in warnings_list:
                warnings_list.append(w)

    method_counts: Counter[str] = Counter()
    confidences: list[float] = []
    for c in classified_list:
        m = c.get("method", "unknown")
        method_counts[m] += 1
        conf = c.get("confidence", 0.0)
        if isinstance(conf, (int, float)):
            confidences.append(conf)

    # Distribución de métodos normalizada
    metodo_codigo = sum(
        v for k, v in method_counts.items() if k == "code"
    )
    metodo_diccionario_exacto = sum(
        v for k, v in method_counts.items() if k == "dictionary_exact"
    )
    metodo_diccionario_fuzzy = sum(
        v for k, v in method_counts.items() if k == "dictionary_fuzzy"
    )
    metodo_regex = sum(
        v for k, v in method_counts.items() if k.startswith("regex")
    )
    metodo_semantico = sum(
        v for k, v in method_counts.items() if k.startswith("semantic")
    )
    metodo_learning_exact = sum(
        v for k, v in method_counts.items() if k == "learning_exact"
    )
    metodo_learning_fuzzy = sum(
        v for k, v in method_counts.items() if k == "learning_fuzzy"
    )
    metodo_decision_agree = sum(
        v for k, v in method_counts.items() if k == "decision_agree"
    )
    metodo_decision_sm_high = sum(
        v for k, v in method_counts.items() if k == "decision_sm_high"
    )
    metodo_decision_regex = sum(
        v for k, v in method_counts.items() if k == "decision_regex_exact"
    )
    metodo_decision_conflict = sum(
        v for k, v in method_counts.items() if k == "decision_conflict"
    )
    metodo_decision_unknown = sum(
        v for k, v in method_counts.items() if k == "decision_unknown"
    )
    metodo_unclassified = accounts_unknown

    # Precisión de extracción: cuentas con confianza >= 0.7
    alta_confianza = sum(1 for c in confidences if c >= 0.7) if confidences else 0
    media_confianza = sum(1 for c in confidences if 0.4 <= c < 0.7) if confidences else 0
    baja_confianza = sum(1 for c in confidences if c < 0.4) if confidences else 0
    confianza_prom = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    extraction_precision = round(alta_confianza / accounts_classified, 4) if accounts_classified else 0.0
    homologation_precision = round(accounts_classified / accounts_total, 4) if accounts_total else 0.0

    return {
        "archivo": pdf_path.name,
        "tiempo_procesamiento_s": elapsed,
        "cuentas_detectadas": accounts_total,
        "cuentas_homologadas": accounts_classified,
        "cuentas_ignoradas": accounts_ignored,
        "cuentas_desconocidas": accounts_unknown,
        "errores": " | ".join(errores),
        "warnings": " | ".join(warnings_list),
        "precision_extraccion": extraction_precision,
        "precision_homologacion": homologation_precision,
        "learning_hits": learning_hits,
        "metodo_codigo": metodo_codigo,
        "metodo_diccionario_exacto": metodo_diccionario_exacto,
        "metodo_diccionario_fuzzy": metodo_diccionario_fuzzy,
        "metodo_regex": metodo_regex,
        "metodo_semantico": metodo_semantico,
        "metodo_learning_exact": metodo_learning_exact,
        "metodo_learning_fuzzy": metodo_learning_fuzzy,
        "metodo_decision_agree": metodo_decision_agree,
        "metodo_decision_sm_high": metodo_decision_sm_high,
        "metodo_decision_regex": metodo_decision_regex,
        "metodo_decision_conflict": metodo_decision_conflict,
        "metodo_decision_unknown": metodo_decision_unknown,
        "metodo_unclassified": metodo_unclassified,
        "confianza_promedio": confianza_prom,
        "cuentas_alta_confianza": alta_confianza,
        "cuentas_media_confianza": media_confianza,
        "cuentas_baja_confianza": baja_confianza,
        "requirio_ocr": result.get("requirio_ocr", False),
    }


def generate_summary(results: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> str:
    """Genera el reporte benchmark_summary.md."""
    n_files = len(results)

    total_detectadas = sum(r["cuentas_detectadas"] for r in results)
    total_homologadas = sum(r["cuentas_homologadas"] for r in results)
    total_ignoradas = sum(r["cuentas_ignoradas"] for r in results)
    total_desconocidas = sum(r["cuentas_desconocidas"] for r in results)
    total_learning_hits = sum(r["learning_hits"] for r in results)
    total_errores = sum(1 for r in results if r["errores"])
    total_warnings = sum(1 for r in results if r["warnings"])

    total_time = round(sum(r["tiempo_procesamiento_s"] for r in results), 3)
    avg_time = round(total_time / n_files, 3) if n_files else 0.0

    # Agregar métodos
    all_methods: Counter[str] = Counter()
    method_labels = {
        "metodo_codigo": "code",
        "metodo_diccionario_exacto": "dictionary_exact",
        "metodo_diccionario_fuzzy": "dictionary_fuzzy",
        "metodo_regex": "regex",
        "metodo_semantico": "semantic",
        "metodo_learning_exact": "learning_exact",
        "metodo_learning_fuzzy": "learning_fuzzy",
        "metodo_decision_agree": "decision_agree",
        "metodo_decision_sm_high": "decision_sm_high",
        "metodo_decision_regex": "decision_regex_exact",
        "metodo_decision_conflict": "decision_conflict",
        "metodo_decision_unknown": "decision_unknown",
        "metodo_unclassified": "unclassified",
    }
    for row_key, label in method_labels.items():
        total = sum(r.get(row_key, 0) for r in results)
        if total > 0:
            all_methods[label] = total

    # Agregar precisiones promedio
    extractions = [r["precision_extraccion"] for r in results if r["cuentas_homologadas"] > 0]
    homologations = [r["precision_homologacion"] for r in results if r["cuentas_detectadas"] > 0]
    avg_extraction = round(sum(extractions) / len(extractions), 4) if extractions else 0.0
    avg_homologation = round(sum(homologations) / len(homologations), 4) if homologations else 0.0

    # Confianza promedio global
    all_confidences: list[float] = []
    for r in results:
        cp = r.get("confianza_promedio", 0)
        if cp > 0 and r["cuentas_homologadas"] > 0:
            all_confidences.append(cp)
    global_avg_conf = round(sum(all_confidences) / len(all_confidences), 4) if all_confidences else 0.0

    lines: list[str] = []
    lines.append("# Benchmark Summary — Certificación")
    lines.append("")
    lines.append(f"**Fecha:** 2026-07-26")
    lines.append(f"**Pipeline:** HomologationPipeline")
    lines.append(f"**Dataset:** datasets/HOLDOUT/ ({n_files} archivos)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Métricas globales")
    lines.append("")
    lines.append(f"| Métrica | Valor |")
    lines.append(f"|---------|-------|")
    lines.append(f"| Archivos procesados | {n_files} |")
    lines.append(f"| Tiempo total | {total_time}s |")
    lines.append(f"| Tiempo promedio por archivo | {avg_time}s |")
    lines.append(f"| Cuentas detectadas | {total_detectadas} |")
    lines.append(f"| Cuentas homologadas | {total_homologadas} |")
    lines.append(f"| Cuentas ignoradas (sin movimiento) | {total_ignoradas} |")
    lines.append(f"| Cuentas desconocidas (sin clasificar) | {total_desconocidas} |")
    lines.append(f"| Learning hits (Gold Standard) | {total_learning_hits} |")
    lines.append(f"| Archivos con errores | {total_errores} |")
    lines.append(f"| Archivos con warnings | {total_warnings} |")
    lines.append(f"| Precisión extracción promedio (confianza >= 0.7) | {avg_extraction:.2%} |")
    lines.append(f"| Precisión homologación promedio | {avg_homologation:.2%} |")
    lines.append(f"| Confianza promedio global | {global_avg_conf:.4f} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Distribución de métodos de clasificación")
    lines.append("")
    lines.append(f"| Método | Cuentas | % |")
    lines.append(f"|--------|---------|---|")
    classified_total = sum(v for k, v in all_methods.items() if k != "unclassified")
    unknown_total = all_methods.get("unclassified", 0)
    total_clasificaciones = classified_total + unknown_total
    for method in sorted(all_methods.keys()):
        cnt = all_methods[method]
        pct = round(cnt / total_clasificaciones * 100, 1) if total_clasificaciones else 0.0
        lines.append(f"| {method} | {cnt} | {pct}% |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Resultados por archivo")
    lines.append("")
    lines.append("| Archivo | Tiempo (s) | Detectadas | Homologadas | Ignoradas | Unknown | Learning Hits | Confianza Prom |")
    lines.append("|---------|-----------|-----------|-------------|-----------|---------|--------------|--------------|")
    for r in sorted(results, key=lambda x: x["archivo"]):
        lines.append(
            f"| {r['archivo']} | {r['tiempo_procesamiento_s']} | {r['cuentas_detectadas']} "
            f"| {r['cuentas_homologadas']} | {r['cuentas_ignoradas']} | {r['cuentas_desconocidas']} "
            f"| {r['learning_hits']} | {r['confianza_promedio']} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Archivos con errores")
    lines.append("")
    errores_list = [r for r in results if r["errores"]]
    if errores_list:
        for r in errores_list:
            lines.append(f"- **{r['archivo']}**: {r['errores']}")
    else:
        lines.append("Ningún archivo generó errores.")
    lines.append("")
    lines.append("## Archivos con warnings")
    lines.append("")
    warnings_list = [r for r in results if r["warnings"]]
    if warnings_list:
        for r in warnings_list:
            lines.append(f"- **{r['archivo']}**: {r['warnings']}")
    else:
        lines.append("Ningún archivo generó warnings.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Manifiesto del dataset")
    lines.append("")
    lines.append(f"| Archivo | Tamaño (KB) |")
    lines.append(f"|---------|------------|")
    for m in manifest:
        lines.append(f"| {m['archivo']} | {m['tamano_kb']} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("_Benchmark ejecutado con benchmark/benchmark_runner.py_")

    return "\n".join(lines)


def main() -> None:
    logger.info("=== Benchmark de Certificación ===")
    logger.info("Dataset: %s", HOLDOUT_DIR)

    # 1. Build manifest
    manifest = build_manifest()
    save_manifest(manifest)
    logger.info("Manifiesto: %d archivos", len(manifest))

    # 2. Process each file
    results: list[dict[str, Any]] = []
    files = sorted(HOLDOUT_DIR.glob("*.pdf"))
    for i, pdf_path in enumerate(files, 1):
        logger.info("[%d/%d] Procesando: %s", i, len(files), pdf_path.name)
        row = process_file(pdf_path)
        results.append(row)
        logger.info(
            "  → %d cuentas, %d homologadas, %d desconocidas, %.3fs",
            row["cuentas_detectadas"],
            row["cuentas_homologadas"],
            row["cuentas_desconocidas"],
            row["tiempo_procesamiento_s"],
        )

    # 3. Save results
    save_results(results)

    # 4. Generate summary
    summary = generate_summary(results, manifest)
    SUMMARY_MD.write_text(summary, encoding="utf-8")
    logger.info("Summary escrito: %s", SUMMARY_MD)

    # 5. Print quick summary
    total_detectadas = sum(r["cuentas_detectadas"] for r in results)
    total_homologadas = sum(r["cuentas_homologadas"] for r in results)
    total_time = round(sum(r["tiempo_procesamiento_s"] for r in results), 3)
    errors = sum(1 for r in results if r["errores"])
    warnings = sum(1 for r in results if r["warnings"])
    print()
    print("=" * 60)
    print("BENCHMARK COMPLETADO")
    print("=" * 60)
    print(f"  Archivos:        {len(results)}")
    print(f"  Tiempo total:    {total_time}s")
    print(f"  Cuentas totales: {total_detectadas}")
    print(f"  Homologadas:     {total_homologadas}")
    print(f"  Archivos error:  {errors}")
    print(f"  Archivos warn:   {warnings}")
    print(f"  Resultados:      {RESULTS_CSV}")
    print(f"  Summary:         {SUMMARY_MD}")
    print("=" * 60)


if __name__ == "__main__":
    main()
