"""FASE 18A — CMCC Shadow Mode: run shadow analysis and generate reports."""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager

REPORTS_DIR = Path("reports/cmcc_shadow")
GS_DB_PATH = "gold_standard.db"


def collect_shadow_data() -> tuple[list[dict], int]:
    print("Inicializando pipeline...")
    pipeline = HomologationPipeline(str(GS_DB_PATH))

    print("Descubriendo archivos...")
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"  Total archivos: {len(all_files)}")

    shadow_rows: list[dict] = []
    total_unknown = 0

    for i, dfile in enumerate(all_files):
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        print(f"  [{i+1}/{len(all_files)}] {rel_path} ... ", end="", flush=True)

        try:
            result = pipeline.process(str(dfile.path))
            file_unknown = result.get("accounts_without_dictionary_match", 0)
            total_unknown += file_unknown
            print(f"{result['accounts_total']} cuentas, {file_unknown} unknown, {result['cmcc_shadow_hits']} shadow hits")

            for acct in result.get("classified", []):
                shadow = acct.get("cmcc_shadow")
                if shadow is not None:
                    shadow_rows.append({
                        "Cuenta": acct.get("account_name", ""),
                        "Código sugerido": shadow.get("code", ""),
                        "Concepto": shadow.get("concept", ""),
                        "Score": shadow.get("score", 0.0),
                        "Método": shadow.get("method", ""),
                        "Variante utilizada": shadow.get("matched_variant", ""),
                        "Evidencia": " | ".join(shadow.get("evidence", [])),
                        "Empresa": _company_name(rel_path),
                        "Documento": rel_path,
                    })

        except Exception as e:
            print(f"ERROR: {e}")

    return shadow_rows, total_unknown


def _company_name(path: str) -> str:
    import re
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


def generate_reports(rows: list[dict], total_unknown: int) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # cmcc_shadow.xlsx
    df = pd.DataFrame(rows)
    df.to_excel(REPORTS_DIR / "cmcc_shadow.xlsx", index=False)
    print(f"  cmcc_shadow.xlsx: {len(rows)} rows")

    if not rows:
        print("  No hay shadow matches para generar reporte.")
        empty = {
            "total_shadow": 0, "avg_score": 0, "recovered": 0,
            "unknown_actual": total_unknown, "recovery_pct": 0,
            "top_concepts": [], "top_variants": [],
            "doubtful": 0, "high_confidence": 0,
        }
        REPORTS_DIR.joinpath("cmcc_shadow_report.md").write_text(
            "# CMCC Shadow Report\n\nNo se encontraron shadow matches.\n", encoding="utf-8")
        return

    total = len(rows)
    avg_score = sum(r["Score"] for r in rows) / total

    concept_counter: Counter = Counter()
    variant_counter: Counter = Counter()
    code_counter: Counter = Counter()
    method_counter: Counter = Counter()
    doubtful = [r for r in rows if 0.70 <= r["Score"] < 0.90]
    high_conf = [r for r in rows if r["Score"] >= 0.95]

    for r in rows:
        concept_counter[r["Concepto"]] += 1
        variant_counter[r["Variante utilizada"]] += 1
        code_counter[r["Código sugerido"]] += 1
        method_counter[r["Método"]] += 1

    recovered = total
    unknown_actual = total_unknown
    recovery_pct = round((recovered / unknown_actual * 100) if unknown_actual > 0 else 0, 1)

    md = []
    md.append("# CMCC Shadow Report — Integración en Shadow Mode")
    md.append("")
    md.append(f"Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    md.append("")
    md.append("## 1. UNKNOWN actuales")
    md.append(f"**{unknown_actual}** cuentas UNKNOWN sin clasificar en el pipeline oficial.")
    md.append("")
    md.append("## 2. UNKNOWN recuperables por CMCC")
    md.append(f"**{recovered}** cuentas UNKNOWN fueron recuperadas por CMCC (shadow match ≥ 0.90)")
    md.append("")
    md.append("## 3. Porcentaje de recuperación")
    md.append(f"**{recovery_pct}%** del total de UNKNOWN ({recovered} / {unknown_actual})")
    md.append("")
    concept_by_code: dict[str, str] = {}
    for r in rows:
        concept_by_code[r["Código sugerido"]] = r["Concepto"]
    md.append("## 4. Top conceptos recuperados")
    md.append("| # | Concepto | Código | Veces |")
    md.append("|---|---|---|---|")
    for idx, (code, cnt) in enumerate(code_counter.most_common(30), 1):
        md.append(f"| {idx} | {concept_by_code.get(code, '')} | {code} | {cnt} |")
    md.append("")
    md.append("## 5. Score promedio")
    md.append(f"**{avg_score:.3f}** (promedio de {total} matches)")
    md.append("")
    md.append("## 6. Top variantes usadas")
    md.append("| # | Variante | Veces |")
    md.append("|---|---|")
    for idx, (var, cnt) in enumerate(variant_counter.most_common(30), 1):
        md.append(f"| {idx} | {var[:80]} | {cnt} |")
    md.append("")
    md.append("## 7. Casos dudosos (0.70 ≤ score < 0.90)")
    md.append(f"**{len(doubtful)}** casos en zona dudosa")
    md.append("")
    md.append("## 8. Casos de alta confianza (score ≥ 0.95)")
    md.append(f"**{len(high_conf)}** casos con alta confianza")
    md.append("")
    md.append("## 9. Distribución por método")
    md.append("| Método | Veces |")
    md.append("|---|---|")
    for method, cnt in method_counter.most_common():
        md.append(f"| {method} | {cnt} |")
    md.append("")
    md.append("## 10. Resumen")
    md.append(f"- Total shadow matches: {total}")
    md.append(f"- Score promedio: {avg_score:.3f}")
    md.append(f"- Conceptos distintos: {len(concept_counter)}")
    md.append(f"- Casos dudosos: {len(doubtful)}")
    md.append(f"- Alta confianza: {len(high_conf)}")
    md.append("")
    md.append("*La clasificación oficial NO fue modificada. Modo shadow únicamente.*")

    report_path = REPORTS_DIR / "cmcc_shadow_report.md"
    report_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  {report_path.name}: written")


def main():
    print("=" * 60)
    print("FASE 18A — CMCC Shadow Mode")
    print("=" * 60)

    rows, total_unknown = collect_shadow_data()
    generate_reports(rows, total_unknown)

    print("\nReportes generados en:", REPORTS_DIR.resolve())


if __name__ == "__main__":
    main()
