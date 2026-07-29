"""
benchmark_before_after.py — Ciclo de aprendizaje: ANTES vs DESPUÉS.

Mide cuánto mejora el sistema después de importar revisiones humanas.

Uso:
    python3 benchmark_before_after.py --before-only
    python3 benchmark_before_after.py --apply
    python3 benchmark_before_after.py --compare

Modos:
    --before-only   Ejecuta benchmark inicial (ANTES) y guarda resultados
    --apply         Importa revisiones humanas y ejecuta benchmark final (DESPUÉS)
    --compare       Compara ANTES vs DESPUÉS y genera reporte

No modifica el pipeline. No modifica reglas de clasificación.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("benchmark_before_after")

REPO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_DIR))

from benchmark.benchmark_runner import HOLDOUT_DIR, process_file

BEFORE_JSON = REPO_DIR / "reports" / "benchmark_before.json"
AFTER_JSON = REPO_DIR / "reports" / "benchmark_after.json"
COMPARISON_MD = REPO_DIR / "reports" / "learning_cycle_validation.md"

CSV_PATH = REPO_DIR / "review_workspace" / "manual_review.csv"
GOLD_DB = REPO_DIR / "gold_standard.db"


def run_benchmark(label: str) -> list[dict[str, Any]]:
    """Ejecuta benchmark_runner.process_file sobre cada PDF en HOLDOUT."""
    pdfs = sorted(HOLDOUT_DIR.glob("*.pdf"))
    logger.info("Procesando %d PDFs (%s)...", len(pdfs), label)

    results: list[dict[str, Any]] = []
    for pdf in pdfs:
        t0 = time.time()
        r = process_file(pdf)
        elapsed = time.time() - t0
        logger.info(
            "  %-55s  detectadas=%-4d  homologadas=%-4d  unknown=%-4d  learning=%-3d  (%.1fs)",
            pdf.name,
            r["cuentas_detectadas"],
            r["cuentas_homologadas"],
            r["cuentas_desconocidas"],
            r["learning_hits"],
            elapsed,
        )
        results.append(r)

    return results


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega resultados del benchmark."""
    n = len(results)
    total_detectadas = sum(r["cuentas_detectadas"] for r in results)
    total_homologadas = sum(r["cuentas_homologadas"] for r in results)
    total_ignoradas = sum(r["cuentas_ignoradas"] for r in results)
    total_desconocidas = sum(r["cuentas_desconocidas"] for r in results)
    total_learning = sum(r["learning_hits"] for r in results)
    total_time = sum(r["tiempo_procesamiento_s"] for r in results)

    confianzas = [r["confianza_promedio"] for r in results if r["confianza_promedio"] > 0 and r["cuentas_homologadas"] > 0]
    avg_conf = round(sum(confianzas) / len(confianzas), 4) if confianzas else 0.0

    precision_hom = [r["precision_homologacion"] for r in results if r["cuentas_detectadas"] > 0]
    avg_prec_hom = round(sum(precision_hom) / len(precision_hom), 4) if precision_hom else 0.0

    method_fields = [
        "metodo_codigo", "metodo_diccionario_exacto", "metodo_diccionario_fuzzy",
        "metodo_regex", "metodo_semantico", "metodo_learning_exact",
        "metodo_learning_fuzzy", "metodo_decision_agree", "metodo_decision_sm_high",
        "metodo_decision_regex", "metodo_decision_conflict", "metodo_decision_unknown",
        "metodo_unclassified",
    ]
    methods = {f: sum(r.get(f, 0) for r in results) for f in method_fields}

    return {
        "archivos": n,
        "tiempo_total_s": round(total_time, 3),
        "tiempo_promedio_s": round(total_time / n, 3) if n else 0,
        "cuentas_detectadas": total_detectadas,
        "cuentas_homologadas": total_homologadas,
        "cuentas_ignoradas": total_ignoradas,
        "cuentas_desconocidas": total_desconocidas,
        "learning_hits": total_learning,
        "confianza_promedio": avg_conf,
        "precision_homologacion": avg_prec_hom,
        "metodos": methods,
        "por_archivo": [
            {"archivo": r["archivo"],
             "detectadas": r["cuentas_detectadas"],
             "homologadas": r["cuentas_homologadas"],
             "ignoradas": r["cuentas_ignoradas"],
             "desconocidas": r["cuentas_desconocidas"],
             "learning_hits": r["learning_hits"],
             "confianza_prom": r["confianza_promedio"],
             "tiempo_s": r["tiempo_procesamiento_s"]}
            for r in results
        ],
    }


def save_results(results: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    agg = aggregate(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(agg, f, indent=2, ensure_ascii=False)
    logger.info("Resultados guardados: %s", path)
    return agg


def load_results(path: Path) -> dict[str, Any]:
    if not path.exists():
        logger.error("No se encuentra: %s", path)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compara resultados ANTES vs DESPUÉS."""
    diff: dict[str, Any] = {}

    for key in ["cuentas_detectadas", "cuentas_homologadas", "cuentas_ignoradas",
                 "cuentas_desconocidas", "learning_hits", "confianza_promedio",
                 "precision_homologacion", "tiempo_total_s", "tiempo_promedio_s"]:
        b = before.get(key, 0)
        a = after.get(key, 0)
        diff[key] = {
            "antes": b,
            "despues": a,
            "diferencia": round(a - b, 4),
            "variacion_pct": round((a - b) / b * 100, 2) if b else 0,
        }

    methods_b = before.get("metodos", {})
    methods_a = after.get("metodos", {})
    all_methods = sorted(set(list(methods_b.keys()) + list(methods_a.keys())))
    diff["metodos"] = {}
    for m in all_methods:
        b_val = methods_b.get(m, 0)
        a_val = methods_a.get(m, 0)
        diff["metodos"][m] = {
            "antes": b_val,
            "despues": a_val,
            "diferencia": a_val - b_val,
        }

    # Clasificaciones nuevas: total homologadas después - homologadas antes
    diff["nuevas_clasificaciones"] = diff["cuentas_homologadas"]["diferencia"]

    # UNKNOWN después vs antes
    diff["unknown_reducidos"] = -diff["cuentas_desconocidas"]["diferencia"]

    return diff


def generar_reporte_md(before: dict[str, Any], after: dict[str, Any],
                       diff: dict[str, Any]) -> str:
    """Genera el reporte learning_cycle_validation.md."""
    lines: list[str] = []
    lines.append("# Learning Cycle Validation")
    lines.append("")
    lines.append("**Ciclo de Aprendizaje:** Revisión humana de cuentas UNKNOWN → Gold Standard → Re-evaluación")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Metodología")
    lines.append("")
    lines.append("1. Ejecutar benchmark sobre HOLDOUT (20 archivos) → métricas ANTES")
    lines.append("2. Exportar cuentas UNKNOWN a CSV de revisión manual")
    lines.append("3. Importar revisiones humanas aprobadas al Gold Standard (`gold_standard.db`)")
    lines.append("4. Re-ejecutar benchmark sobre HOLDOUT → métricas DESPUÉS")
    lines.append("5. Comparar ANTES vs DESPUÉS")
    lines.append("")
    lines.append("No se modificó el pipeline, el parser, reglas de clasificación ni diccionarios.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Dataset")
    lines.append("")
    lines.append("| Atributo | Valor |")
    lines.append("|----------|-------|")
    lines.append(f"| Dataset | `datasets/HOLDOUT/` |")
    lines.append(f"| Archivos | {before.get('archivos', 0)} PDFs |")
    lines.append("| Propósito | Benchmark de certificación (no entrenamiento) |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. Benchmark Inicial (ANTES)")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Cuentas detectadas | {before.get('cuentas_detectadas', 0)} |")
    lines.append(f"| Cuentas homologadas | {before.get('cuentas_homologadas', 0)} |")
    lines.append(f"| Cuentas UNKNOWN | {before.get('cuentas_desconocidas', 0)} |")
    lines.append(f"| Cuentas ignoradas | {before.get('cuentas_ignoradas', 0)} |")
    lines.append(f"| Learning hits | {before.get('learning_hits', 0)} |")
    lines.append(f"| Confianza promedio | {before.get('confianza_promedio', 0)} |")
    lines.append(f"| Precisión homologación | {before.get('precision_homologacion', 0):.2%} |")
    lines.append(f"| Tiempo total | {before.get('tiempo_total_s', 0)}s |")
    lines.append(f"| Tiempo promedio | {before.get('tiempo_promedio_s', 0)}s |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Benchmark Posterior (DESPUÉS)")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Cuentas detectadas | {after.get('cuentas_detectadas', 0)} |")
    lines.append(f"| Cuentas homologadas | {after.get('cuentas_homologadas', 0)} |")
    lines.append(f"| Cuentas UNKNOWN | {after.get('cuentas_desconocidas', 0)} |")
    lines.append(f"| Cuentas ignoradas | {after.get('cuentas_ignoradas', 0)} |")
    lines.append(f"| Learning hits | {after.get('learning_hits', 0)} |")
    lines.append(f"| Confianza promedio | {after.get('confianza_promedio', 0)} |")
    lines.append(f"| Precisión homologación | {after.get('precision_homologacion', 0):.2%} |")
    lines.append(f"| Tiempo total | {after.get('tiempo_total_s', 0)}s |")
    lines.append(f"| Tiempo promedio | {after.get('tiempo_promedio_s', 0)}s |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Diferencias (DESPUÉS - ANTES)")
    lines.append("")
    lines.append("| Métrica | ANTES | DESPUÉS | Diferencia | Variación |")
    lines.append("|---------|-------|---------|------------|-----------|")
    for key, label in [
        ("cuentas_homologadas", "Cuentas homologadas"),
        ("cuentas_desconocidas", "Cuentas UNKNOWN"),
        ("learning_hits", "Learning hits"),
        ("confianza_promedio", "Confianza promedio"),
        ("precision_homologacion", "Precisión homologación"),
        ("tiempo_total_s", "Tiempo total"),
    ]:
        d = diff.get(key, {})
        antes = d.get("antes", 0)
        despues = d.get("despues", 0)
        diff_val = d.get("diferencia", 0)
        var_pct = d.get("variacion_pct", 0)
        if isinstance(antes, float):
            lines.append(f"| {label} | {antes:.4f} | {despues:.4f} | {diff_val:+.4f} | {var_pct:+.2f}% |")
        else:
            lines.append(f"| {label} | {antes} | {despues} | {diff_val:+d} | {var_pct:+.2f}% |")
    lines.append("")
    lines.append("### Distribución de métodos")
    lines.append("")
    lines.append("| Método | ANTES | DESPUÉS | Diferencia |")
    lines.append("|--------|-------|---------|------------|")
    methods_diff = diff.get("metodos", {})
    for m in sorted(methods_diff.keys()):
        d = methods_diff[m]
        b = d.get("antes", 0)
        a = d.get("despues", 0)
        dif = d.get("diferencia", 0)
        if b > 0 or a > 0:
            lines.append(f"| {m} | {b} | {a} | {dif:+d} |")
    lines.append("")
    lines.append(f"**Clasificaciones nuevas:** {diff.get('nuevas_clasificaciones', 0)}")
    lines.append("")
    lines.append(f"**UNKNOWN reducidos:** {diff.get('unknown_reducidos', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Conclusiones")
    lines.append("")
    lines.append("Esta sección será completada al finalizar el ciclo completo de revisión humana.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Reporte generado por benchmark_before_after.py*")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ciclo de aprendizaje: ANTES vs DESPUÉS")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--before-only", action="store_true", help="Ejecuta benchmark ANTES")
    group.add_argument("--apply", action="store_true", help="Importa revisiones y ejecuta benchmark DESPUÉS")
    group.add_argument("--compare", action="store_true", help="Compara ANTES vs DESPUÉS")
    args = parser.parse_args()

    if args.before_only:
        logger.info("=" * 60)
        logger.info("BENCHMARK INICIAL (ANTES)")
        logger.info("=" * 60)
        results = run_benchmark("ANTES")
        agg = save_results(results, BEFORE_JSON)
        logger.info("")
        logger.info("RESUMEN ANTES:")
        logger.info("  Homologadas:  %d", agg["cuentas_homologadas"])
        logger.info("  UNKNOWN:      %d", agg["cuentas_desconocidas"])
        logger.info("  Learning:     %d", agg["learning_hits"])
        logger.info("  Confianza:    %.4f", agg["confianza_promedio"])
        logger.info("  Tiempo total: %.1fs", agg["tiempo_total_s"])

    if args.apply:
        logger.info("=" * 60)
        logger.info("IMPORTANDO REVISIONES HUMANAS")
        logger.info("=" * 60)
        from review_workspace.import_manual_review import validar_csv, detectar_duplicados, importar, actualizar_review_db

        if not CSV_PATH.exists():
            logger.error("CSV no encontrado: %s", CSV_PATH)
            logger.error("Ejecute primero la Fase 1+2 para generar el CSV")
            sys.exit(1)

        filas = validar_csv(CSV_PATH)
        if not filas:
            sys.exit(1)

        filas_no_dup = detectar_duplicados(filas)
        omitidos = len(filas) - len(filas_no_dup)

        if not filas_no_dup:
            logger.info("No hay revisiones nuevas para importar.")
            sys.exit(0)

        r_gs = importar(str(GOLD_DB), filas_no_dup)
        r_db = actualizar_review_db(filas_no_dup)
        logger.info("Importados: %d a gold_standard.db, %d actualizados en review.db",
                     r_gs["importados"], r_db["actualizados"])

        if r_gs["importados"] == 0:
            logger.info("No se importaron revisiones. Omitiendo benchmark DESPUÉS.")
            sys.exit(0)

        logger.info("")
        logger.info("=" * 60)
        logger.info("BENCHMARK FINAL (DESPUÉS)")
        logger.info("=" * 60)
        results = run_benchmark("DESPUÉS")
        agg = save_results(results, AFTER_JSON)
        logger.info("")
        logger.info("RESUMEN DESPUÉS:")
        logger.info("  Homologadas:  %d", agg["cuentas_homologadas"])
        logger.info("  UNKNOWN:      %d", agg["cuentas_desconocidas"])
        logger.info("  Learning:     %d", agg["learning_hits"])
        logger.info("  Confianza:    %.4f", agg["confianza_promedio"])
        logger.info("  Tiempo total: %.1fs", agg["tiempo_total_s"])

    if args.compare:
        logger.info("=" * 60)
        logger.info("COMPARACIÓN ANTES vs DESPUÉS")
        logger.info("=" * 60)
        before = load_results(BEFORE_JSON)
        after = load_results(AFTER_JSON)
        diff = compare(before, after)

        logger.info("")
        logger.info("DIFERENCIAS:")
        logger.info("  Homologadas:  %+d (%+.2f%%)",
                     diff["cuentas_homologadas"]["diferencia"],
                     diff["cuentas_homologadas"]["variacion_pct"])
        logger.info("  UNKNOWN:      %+d (%+.2f%%)",
                     diff["cuentas_desconocidas"]["diferencia"],
                     diff["cuentas_desconocidas"]["variacion_pct"])
        logger.info("  Learning:     %+d (%+.2f%%)",
                     diff["learning_hits"]["diferencia"],
                     diff["learning_hits"]["variacion_pct"])
        logger.info("  Confianza:    %+.4f (%+.2f%%)",
                     diff["confianza_promedio"]["diferencia"],
                     diff["confianza_promedio"]["variacion_pct"])
        logger.info("  Nuevas clasificaciones: %+d", diff["nuevas_clasificaciones"])
        logger.info("  UNKNOWN reducidos:      %+d", diff["unknown_reducidos"])

        md = generar_reporte_md(before, after, diff)
        COMPARISON_MD.parent.mkdir(parents=True, exist_ok=True)
        with open(COMPARISON_MD, "w") as f:
            f.write(md)
        logger.info("Reporte generado: %s", COMPARISON_MD)


if __name__ == "__main__":
    main()
