from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

from gold_standard.builder import GoldBuilder
from gold_standard.models import GoldRecord
from pipeline.homologation_pipeline import HomologationPipeline

logger = logging.getLogger(__name__)


def _load_dictionary(path: str | Path = "diccionario.json") -> list[dict[str, str]]:
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# Legacy classifier adapter (mirrors MotorHibridoLocal logic)
# ------------------------------------------------------------------

def _legacy_classify(
    account_code: str,
    account_name: str,
    dictionary: list[dict[str, str]],
) -> str | None:
    from clasificador_codigo_cuenta import ClasificadorCodigo
    from rapidfuzz import fuzz, process
    import re

    code_classifier = ClasificadorCodigo()

    # 1. Code classifier
    r = code_classifier.clasificar(account_code)
    if r is not None and r.confianza >= 0.85:
        return r.codigo_estandar

    # 2. Dictionary exact
    def _norm(n: str) -> str:
        n = n.lower().strip()
        n = re.sub(r"[^\w\sñáéíóú]", " ", n)
        n = re.sub(r"\s+", " ", n)
        return n.strip()

    norm_name = _norm(account_name)
    for entry in dictionary:
        if _norm(entry["cuenta_original"]) == norm_name:
            return entry["codigo_estandar"]

    # 3. Dictionary fuzzy
    dict_items = {_norm(d["cuenta_original"]): d for d in dictionary}
    match = process.extractOne(norm_name, list(dict_items.keys()), scorer=fuzz.token_sort_ratio)
    if match and match[1] >= 90:
        return dict_items[match[0]]["codigo_estandar"]

    # 4. Regex rules (subset)
    REGLAS = [
        (r"\b(caja|banco|cuenta\s*corriente|disponible|efectivo)\b", "AC.01"),
        (r"\b(cliente|deudor.*venta|cxc)\b", "AC.03"),
        (r"\b(inventario|existencia|mercaderia)\b", "AC.05"),
        (r"\b(proveedor|acreedor.*comercial)\b", "PC.01"),
        (r"\b(obligacion.*banc|prestamo.*banc|credito.*banc)\b", "PC.02"),
        (r"\b(remuneracion|sueldo|sueldo.*pagar)\b", "PC.06"),
        (r"\b(iva.*debito|impuesto.*pagar)\b", "PC.05"),
        (r"\b(capital|aporte.*capital)\b", "PAT.01"),
        (r"\b(venta|ingreso.*operacion|ingreso.*giro)\b", "ER.01"),
        (r"\b(costo.*venta|costo.*explotacion)\b", "ER.02"),
        (r"\b(gasto.*administracion|gasto.*general)\b", "ER.04"),
        (r"\b(gasto.*venta|gasto.*comercial)\b", "ER.05"),
        (r"\b(interes|gasto.*financiero)\b", "ER.09"),
    ]
    compiled = [(re.compile(p, re.IGNORECASE | re.UNICODE), c) for p, c in REGLAS]
    for pat, code in compiled:
        if pat.search(account_name):
            return code

    return None


# ------------------------------------------------------------------
# Benchmark
# ------------------------------------------------------------------

def run_benchmark(
    gold_db: str | Path = "gold_standard.db",
    dictionary_path: str | Path = "diccionario.json",
    new_db_path: str | Path = "gold_standard_bench.db",
) -> dict[str, Any]:
    # Load gold standard
    builder = GoldBuilder(gold_db)
    records = builder.list_all()
    builder.close()

    # Load dictionary
    dictionary = _load_dictionary(dictionary_path)

    # Initialize new pipeline
    hp = HomologationPipeline(str(new_db_path))

    results: list[dict[str, Any]] = []
    legacy_correct = 0
    new_correct = 0
    legacy_wrong = 0
    new_wrong = 0

    for rec in records:
        if not rec.final_code or not rec.account_name:
            continue

        # Legacy
        legacy_result = _legacy_classify(
            rec.account_code_original, rec.account_name, dictionary
        )
        legacy_ok = legacy_result == rec.final_code
        if legacy_ok:
            legacy_correct += 1
        else:
            legacy_wrong += 1

        # New pipeline
        new_result = hp._classify_account(
            rec.account_code_original, rec.account_name
        )
        new_code = new_result.get("standard_code")
        new_ok = new_code == rec.final_code
        if new_ok:
            new_correct += 1
        else:
            new_wrong += 1

        results.append({
            "account_name": rec.account_name,
            "account_code": rec.account_code_original,
            "gold_code": rec.final_code,
            "legacy_code": legacy_result,
            "legacy_correct": legacy_ok,
            "new_code": new_code,
            "new_correct": new_ok,
            "new_method": new_result.get("method", ""),
        })

    total = len(results)
    legacy_accuracy = legacy_correct / total if total else 0.0
    new_accuracy = new_correct / total if total else 0.0
    improvement = new_accuracy - legacy_accuracy

    # Detailed analysis
    new_better = [r for r in results if not r["legacy_correct"] and r["new_correct"]]
    new_worse = [r for r in results if r["legacy_correct"] and not r["new_correct"]]
    both_wrong = [r for r in results if not r["legacy_correct"] and not r["new_correct"]]
    both_correct = [r for r in results if r["legacy_correct"] and r["new_correct"]]

    # Top errors
    legacy_errors_sorted = sorted(
        [r for r in results if not r["legacy_correct"]],
        key=lambda x: x["account_name"],
    )[:50]

    new_errors_sorted = sorted(
        [r for r in results if not r["new_correct"]],
        key=lambda x: x["account_name"],
    )[:50]

    return {
        "total": total,
        "legacy_correct": legacy_correct,
        "legacy_wrong": legacy_wrong,
        "legacy_accuracy": round(legacy_accuracy, 4),
        "new_correct": new_correct,
        "new_wrong": new_wrong,
        "new_accuracy": round(new_accuracy, 4),
        "improvement": round(improvement, 4),
        "new_better_count": len(new_better),
        "new_worse_count": len(new_worse),
        "both_wrong_count": len(both_wrong),
        "both_correct_count": len(both_correct),
        "new_better": new_better,
        "new_worse": new_worse,
        "legacy_errors_top50": legacy_errors_sorted,
        "new_errors_top50": new_errors_sorted,
    }


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

def generate_report(
    metrics: dict[str, Any],
    output_path: str | Path = "reports/benchmark/homologation_report.md",
) -> str:
    lines: list[str] = []
    lines.append("# Benchmark de Homologación")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- **Total cuentas evaluadas:** {metrics['total']}")
    lines.append("")
    lines.append("| Métrica | Legacy | New Pipeline |")
    lines.append("|---------|--------|--------------|")
    lines.append(f"| Correctas | {metrics['legacy_correct']} | {metrics['new_correct']} |")
    lines.append(f"| Incorrectas | {metrics['legacy_wrong']} | {metrics['new_wrong']} |")
    lines.append(f"| Precisión | {metrics['legacy_accuracy']:.2%} | {metrics['new_accuracy']:.2%} |")
    lines.append(f"| **Mejora** | | **{metrics['improvement']:+.2%}** |")
    lines.append("")
    lines.append("## Desglose")
    lines.append("")
    lines.append(f"- Ambos correctos: **{metrics['both_correct_count']}**")
    lines.append(f"- Nuevo mejora: **{metrics['new_better_count']}**")
    lines.append(f"- Nuevo empeora: **{metrics['new_worse_count']}**")
    lines.append(f"- Ambos incorrectos: **{metrics['both_wrong_count']}**")
    lines.append("")

    # New better
    if metrics["new_better"]:
        lines.append("## Casos donde el nuevo pipeline mejora")
        lines.append("")
        lines.append("| Cuenta | Código Original | Gold | Legacy | Nuevo | Método Nuevo |")
        lines.append("|--------|-----------------|------|--------|-------|--------------|")
        for r in metrics["new_better"][:50]:
            lines.append(
                f"| {r['account_name']} | {r['account_code']} "
                f"| {r['gold_code']} | {r['legacy_code'] or '—'} "
                f"| {r['new_code'] or '—'} | {r['new_method']} |"
            )
        lines.append("")

    # New worse
    if metrics["new_worse"]:
        lines.append("## Casos donde el nuevo pipeline empeora")
        lines.append("")
        lines.append("| Cuenta | Código Original | Gold | Legacy | Nuevo | Método Nuevo |")
        lines.append("|--------|-----------------|------|--------|-------|--------------|")
        for r in metrics["new_worse"][:50]:
            lines.append(
                f"| {r['account_name']} | {r['account_code']} "
                f"| {r['gold_code']} | {r['legacy_code'] or '—'} "
                f"| {r['new_code'] or '—'} | {r['new_method']} |"
            )
        lines.append("")

    # Top 50 legacy errors
    if metrics["legacy_errors_top50"]:
        lines.append("## Top 50 errores del motor Legacy")
        lines.append("")
        lines.append("| Cuenta | Código Original | Gold | Legacy |")
        lines.append("|--------|-----------------|------|--------|")
        for r in metrics["legacy_errors_top50"]:
            lines.append(
                f"| {r['account_name']} | {r['account_code']} "
                f"| {r['gold_code']} | {r['legacy_code'] or '—'} |"
            )
        lines.append("")

    # Top 50 new errors
    if metrics["new_errors_top50"]:
        lines.append("## Top 50 errores del New Pipeline")
        lines.append("")
        lines.append("| Cuenta | Código Original | Gold | Nuevo | Método |")
        lines.append("|--------|-----------------|------|-------|--------|")
        for r in metrics["new_errors_top50"]:
            lines.append(
                f"| {r['account_name']} | {r['account_code']} "
                f"| {r['gold_code']} | {r['new_code'] or '—'} | {r['new_method']} |"
            )
        lines.append("")

    report = "\n".join(lines)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")

    return report
