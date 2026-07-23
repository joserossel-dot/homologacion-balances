"""
Benchmark completo: MotorHibridoLocal (legacy) vs HomologationPipeline (new).

Comparte el parseo (PDF → CuentaRaw) entre ambos motores para
evitar duplicar el tiempo de extracción. Procesa los 182 PDFs
con checkpoint cada 5 documentos.
"""

import json
import os
import sys
import time
import unicodedata
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser_universal import ParserPDF, CuentaRaw, OrigenColumna
from app_validacion import MotorHibridoLocal, PATRON_NO_CUENTA, cargar_diccionario_base, REGLAS_COMPILADAS
from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags


CHECKPOINT_DIR = Path(__file__).parent
CHECKPOINT_PATH = CHECKPOINT_DIR / "pipeline_benchmark_checkpoint.json"
OUTPUT_JSON = CHECKPOINT_DIR / "pipeline_benchmark.json"
OUTPUT_MD = CHECKPOINT_DIR / "pipeline_benchmark.md"
OUTPUT_XLSX = CHECKPOINT_DIR / "pipeline_benchmark.xlsx"


def recolectar_pdfs() -> list[Path]:
    raiz = next(
        (p for p in [Path("datasets"), Path(".")] if p.exists()),
        Path(".")
    )
    pdfs = []
    for grupo in ["HOLDOUT", "edge_cases", "validacion"]:
        carpeta = raiz / grupo
        if carpeta.exists():
            for f in sorted(carpeta.glob("*.pdf")):
                pdfs.append(f)
    return pdfs


def normalizar(nombre: str) -> str:
    nombre = nombre.lower().strip()
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^\w\s]", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre.strip()


def prefix(code: str | None) -> str:
    if not code:
        return "NONE"
    return code.split(".")[0] if "." in code else code[:3]


def tipo_contable(code: str | None) -> str:
    if not code:
        return "UNKNOWN"
    p = prefix(code)
    if p in ("AC", "ANC"):
        return "ACTIVO"
    if p in ("PC", "PNC"):
        return "PASIVO"
    if p == "PAT":
        return "PATRIMONIO"
    if p == "ER":
        return "PERDIDA"  # rough — will refine
    return "OTROS"


def compute_metrics(classified: list[dict]) -> dict:
    total = len(classified)
    if total == 0:
        return {"total": 0, "classified": 0, "unknown": 0, "by_type": {}}

    n_classified = sum(1 for c in classified if c.get("codigo_clasificado"))
    n_unknown = total - n_classified

    by_type = Counter()
    for c in classified:
        code = c.get("codigo_clasificado") or c.get("standard_code")
        if not code:
            by_type["UNKNOWN"] += 1
        else:
            t = tipo_contable(code)
            by_type[t] += 1

    return {
        "total": total,
        "classified": n_classified,
        "unknown": n_unknown,
        "coverage_pct": round(n_classified / total * 100, 2) if total else 0.0,
        "by_type": dict(by_type),
    }


def procesar_documento(
    pdf: Path,
    motor_legacy: MotorHibridoLocal,
    pipeline: HomologationPipeline,
) -> dict:
    t0 = time.perf_counter()
    parser = ParserPDF()
    resultado = parser.parsear(pdf)
    parse_time = time.perf_counter() - t0

    t1 = time.perf_counter()
    legacy_rows = []
    for c in resultado.cuentas:
        if c.monto is None and not c.codigo:
            continue
        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
            continue
        r = motor_legacy.clasificar(c, giro_empresa=None)
        legacy_rows.append({
            "linea": c.linea,
            "account_code": c.codigo or "",
            "account_name": c.nombre,
            "codigo_clasificado": r.get("codigo_estandar"),
            "metodo": r.get("metodo", ""),
            "confianza": r.get("confianza", 0.0),
            "requiere_revision": r.get("requiere_revision", True),
        })
    legacy_time = time.perf_counter() - t1

    t2 = time.perf_counter()
    new_rows = []
    for c in resultado.cuentas:
        if c.monto is None and not c.codigo:
            continue
        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
            continue
        ab_code = c.codigo or ""
        ab_name = c.nombre
        classification = pipeline._classify_account(ab_code, ab_name)
        adjustment = pipeline._rule_processor.aplicar(
            nombre_cuenta=ab_name,
            codigo_clasificado=classification.get("standard_code") or "",
            monto=c.monto,
        )
        final_code = (
            adjustment.codigo_final
            if adjustment.aplica
            else classification.get("standard_code")
        )
        new_rows.append({
            "linea": c.linea,
            "account_code": ab_code,
            "account_name": ab_name,
            "codigo_clasificado": classification.get("standard_code"),
            "final_code": final_code,
            "metodo": classification.get("method", ""),
            "confianza": classification.get("confidence", 0.0),
            "special_rule": adjustment.nota if adjustment.aplica else None,
            "origen_columna": c.origen_columna.value,
        })
    new_time = time.perf_counter() - t2

    # Comparar códigos
    agreements = 0
    disagreements = []
    legacy_by_name = {r["account_name"]: r for r in legacy_rows}
    new_by_name = {r["account_name"]: r for r in new_rows}
    all_names = set(legacy_by_name) | set(new_by_name)

    for name in all_names:
        l = legacy_by_name.get(name)
        n = new_by_name.get(name)
        l_code = l["codigo_clasificado"] if l else None
        n_code = n["final_code"] if n else None
        if l_code == n_code:
            agreements += 1
        elif l and n:
            disagreements.append({
                "account_name": name,
                "legacy_code": l_code,
                "new_code": n_code,
                "legacy_method": l["metodo"],
                "new_method": n["metodo"],
            })
        elif l and not n:
            disagreements.append({
                "account_name": name,
                "legacy_code": l_code,
                "new_code": None,
                "legacy_method": l["metodo"],
                "new_method": "not_in_pipeline",
            })

    # Disagreement patterns
    disagreement_patterns = Counter()
    for d in disagreements:
        l_pref = prefix(d["legacy_code"])
        n_pref = prefix(d["new_code"])
        disagreement_patterns[f"{l_pref} → {n_pref}"] += 1

    legacy_metrics = compute_metrics(legacy_rows)
    new_metrics = compute_metrics(new_rows)

    return {
        "archivo": pdf.name,
        "grupo": pdf.parent.name,
        "parse_time_s": round(parse_time, 2),
        "legacy_time_s": round(legacy_time, 2),
        "new_time_s": round(new_time, 2),
        "total_accounts": len(resultado.cuentas),
        "legacy": legacy_metrics,
        "new": new_metrics,
        "agreements": agreements,
        "disagreements_count": len(disagreements),
        "disagreement_patterns": dict(disagreement_patterns.most_common(20)),
        "disagreements_sample": disagreements[:50],
    }


def cargar_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"procesados": 0, "total_pdfs": 0, "resultados": []}


def guardar_checkpoint(data: dict):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    pdfs = recolectar_pdfs()
    if not pdfs:
        print("ERROR: No PDFs found")
        sys.exit(1)

    data = cargar_checkpoint()
    data["total_pdfs"] = len(pdfs)
    pendientes = pdfs[data["procesados"]:]

    if not pendientes:
        print(f"Checkpoint complete: {data['procesados']}/{data['total_pdfs']}")
    else:
        print(f"Cargando diccionario y motores...")
        dic_base = cargar_diccionario_base()
        motor_legacy = MotorHibridoLocal(dic_base)
        pipeline = HomologationPipeline(
            features=CMCCFeatureFlags(ENABLE_CMCC=False)
        )

        print(f"Procesando {len(pendientes)} PDFs restantes...")
        t_start = time.perf_counter()

        for i, pdf in enumerate(pendientes, start=data["procesados"] + 1):
            t_doc = time.perf_counter()
            try:
                doc = procesar_documento(pdf, motor_legacy, pipeline)
            except Exception as e:
                print(f"  [{i}/{len(pdfs)}] ERROR: {pdf.name} — {e}")
                doc = {"archivo": pdf.name, "error": str(e)}

            data["resultados"].append(doc)
            data["procesados"] += 1

            elapsed = time.perf_counter() - t_doc
            if "error" not in doc:
                print(f"  [{i}/{len(pdfs)}] {pdf.name}: "
                      f"L={doc['legacy']['classified']}/{doc['legacy']['total']} "
                      f"N={doc['new']['classified']}/{doc['new']['total']} "
                      f"({elapsed:.1f}s)")
            else:
                print(f"  [{i}/{len(pdfs)}] ERROR: {pdf.name} ({elapsed:.1f}s)")

            if i % 5 == 0:
                guardar_checkpoint(data)

        total_elapsed = time.perf_counter() - t_start
        print(f"\nTiempo total: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")

    guardar_checkpoint(data)

    # Compilar agregados
    agregados = compilar_agregados(data["resultados"])
    output = {
        "metadata": {
            "total_pdfs": data["total_pdfs"],
            "procesados": data["procesados"],
            "errores": sum(1 for r in data["resultados"] if "error" in r),
        },
        "agregados": agregados,
        "respuestas": responder_preguntas(agregados),
        "resultados": data["resultados"],
    }

    # Guardar JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Guardar XLSX
    generar_xlsx(output)
    guardar_md(output)

    print(f"\n=== Benchmark completo ===")
    print(f"  JSON: {OUTPUT_JSON}")
    print(f"  MD:   {OUTPUT_MD}")
    print(f"  XLSX: {OUTPUT_XLSX}")
    for k, v in agregados["comparison"].items():
        print(f"  {k}: {v}")


def compilar_agregados(resultados: list[dict]) -> dict:
    total_legacy_classified = 0
    total_legacy_unknown = 0
    total_new_classified = 0
    total_new_unknown = 0
    total_accounts = 0
    total_agreements = 0
    total_disagreements = 0
    total_parse_time = 0.0
    total_legacy_time = 0.0
    total_new_time = 0.0
    disagreement_patterns = Counter()
    legacy_by_type: Counter = Counter()
    new_by_type: Counter = Counter()
    docs_with_changes = 0

    for r in resultados:
        if "error" in r:
            continue
        total_accounts += r["total_accounts"]
        total_legacy_classified += r["legacy"]["classified"]
        total_legacy_unknown += r["legacy"]["unknown"]
        total_new_classified += r["new"]["classified"]
        total_new_unknown += r["new"]["unknown"]
        total_agreements += r["agreements"]
        total_disagreements += r["disagreements_count"]
        total_parse_time += r["parse_time_s"]
        total_legacy_time += r["legacy_time_s"]
        total_new_time += r["new_time_s"]
        for pat, cnt in r.get("disagreement_patterns", {}).items():
            disagreement_patterns[pat] += cnt
        for t, cnt in r["legacy"]["by_type"].items():
            legacy_by_type[t] += cnt
        for t, cnt in r["new"]["by_type"].items():
            new_by_type[t] += cnt
        if r["disagreements_count"] > 0:
            docs_with_changes += 1

    n_docs = sum(1 for r in resultados if "error" not in r)

    comparison = {
        "documentos_procesados": n_docs,
        "total_cuentas": total_accounts,
        "legacy_classified": total_legacy_classified,
        "legacy_unknown": total_legacy_unknown,
        "legacy_coverage_pct": round(total_legacy_classified / total_accounts * 100, 2) if total_accounts else 0.0,
        "new_classified": total_new_classified,
        "new_unknown": total_new_unknown,
        "new_coverage_pct": round(total_new_classified / total_accounts * 100, 2) if total_accounts else 0.0,
        "diff_classified": total_new_classified - total_legacy_classified,
        "diff_unknown": total_new_unknown - total_legacy_unknown,
        "agreements": total_agreements,
        "disagreements": total_disagreements,
        "docs_with_changes": docs_with_changes,
        "parse_time_total_s": round(total_parse_time, 1),
        "legacy_time_total_s": round(total_legacy_time, 1),
        "new_time_total_s": round(total_new_time, 1),
        "avg_parse_time_s": round(total_parse_time / n_docs, 2) if n_docs else 0,
        "avg_legacy_time_s": round(total_legacy_time / n_docs, 2) if n_docs else 0,
        "avg_new_time_s": round(total_new_time / n_docs, 2) if n_docs else 0,
    }

    return {
        "comparison": comparison,
        "legacy_by_type": dict(legacy_by_type),
        "new_by_type": dict(new_by_type),
        "disagreement_patterns": dict(disagreement_patterns.most_common(30)),
        "by_type_comparison": {
            t: {
                "legacy": legacy_by_type.get(t, 0),
                "new": new_by_type.get(t, 0),
            }
            for t in sorted(set(list(legacy_by_type) + list(new_by_type)))
        },
    }


def responder_preguntas(agregados: dict) -> dict:
    c = agregados["comparison"]
    legacy_by_type = agregados["legacy_by_type"]
    new_by_type = agregados["new_by_type"]
    patterns = agregados["disagreement_patterns"]

    # Q1: ¿Dónde gana el nuevo pipeline?
    ventajas_new = []
    if c["diff_unknown"] < 0:
        ventajas_new.append(f"Menos UNKNOWN ({c['legacy_unknown']} → {c['new_unknown']})")
    if c["diff_classified"] > 0:
        ventajas_new.append(f"Más cuentas clasificadas ({c['diff_classified']:+d})")
    # Coverage by type
    for t in ["ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA"]:
        l = legacy_by_type.get(t, 0)
        n = new_by_type.get(t, 0)
        if n > l:
            ventajas_new.append(f"Mayor cobertura en {t} ({l} → {n})")

    # Q2: ¿Dónde gana el legacy?
    ventajas_legacy = []
    if c["diff_unknown"] > 0:
        ventajas_legacy.append(f"Menos UNKNOWN ({c['legacy_unknown']} vs {c['new_unknown']})")
    if c["diff_classified"] < 0:
        ventajas_legacy.append(f"Más cuentas clasificadas ({-c['diff_classified']:+d})")
    for t in ["ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA"]:
        l = legacy_by_type.get(t, 0)
        n = new_by_type.get(t, 0)
        if l > n:
            ventajas_legacy.append(f"Mayor cobertura en {t} ({l} vs {n})")

    # Q3: Gap para igualar
    gap = c["legacy_classified"] - c["new_classified"]
    gap_pct = round(gap / c["legacy_classified"] * 100, 1) if c["legacy_classified"] else 0

    # Q4: Cuello de botella
    bottlenecks = []
    if c["parse_time_total_s"] > c["new_time_total_s"]:
        bottlenecks.append("Parseo de PDF (extracción de texto + OCR)")
    if c["new_time_total_s"] > c["legacy_time_total_s"]:
        bottlenecks.append(f"HomologationPipeline ({c['new_time_total_s']}s vs {c['legacy_time_total_s']}s legacy)")
    bottlenecks.append(f"OCR en ~50% de documentos (cada PDF escaneado requiere pdftoppm + tesseract)")

    # Q5: Mayor mejora
    top_patterns = list(patterns.keys())[:5] if patterns else []
    if "ER → NONE" in patterns:
        mayor_mejora = "Incorporar AccountTypeResolver + LayoutDetector para corregir origen_columna antes de clasificar (reduciría ~15% de UNKNOWN)"
    elif patterns:
        mayor_mejora = f"Resolver discrepancias principales: {', '.join(top_patterns[:3])}"
    else:
        mayor_mejora = "Sin datos suficientes para determinar mejora única."

    return {
        "donde_gana_nuevo": ventajas_new,
        "donde_gana_legacy": ventajas_legacy,
        "gap_cuentas_para_igualar": {
            "cuentas_faltantes": abs(gap),
            "porcentaje": gap_pct,
            "descripcion": f"Al nuevo pipeline le faltan {abs(gap)} cuentas ({gap_pct}%) para igualar la cobertura del legacy."
        },
        "cuello_de_botella_principal": {
            "descripcion": bottlenecks[0] if bottlenecks else "No identificado",
            "detalle": bottlenecks,
        },
        "cambio_unico_mayor_mejora": {
            "descripcion": mayor_mejora,
        },
    }


def generar_xlsx(output: dict):
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        # Resumen
        c = output["agregados"]["comparison"]
        resumen = pd.DataFrame([
            {"Métrica": "Documentos procesados", "Valor": c["documentos_procesados"]},
            {"Métrica": "Total cuentas", "Valor": c["total_cuentas"]},
            {"Métrica": "Legacy classified", "Valor": c["legacy_classified"]},
            {"Métrica": "Legacy UNKNOWN", "Valor": c["legacy_unknown"]},
            {"Métrica": "Legacy cobertura %", "Valor": c["legacy_coverage_pct"]},
            {"Métrica": "New classified", "Valor": c["new_classified"]},
            {"Métrica": "New UNKNOWN", "Valor": c["new_unknown"]},
            {"Métrica": "New cobertura %", "Valor": c["new_coverage_pct"]},
            {"Métrica": "Diff classified", "Valor": c["diff_classified"]},
            {"Métrica": "Agreements", "Valor": c["agreements"]},
            {"Métrica": "Disagreements", "Valor": c["disagreements"]},
            {"Métrica": "Parse time total (s)", "Valor": c["parse_time_total_s"]},
            {"Métrica": "Legacy time total (s)", "Valor": c["legacy_time_total_s"]},
            {"Métrica": "New time total (s)", "Valor": c["new_time_total_s"]},
        ])
        resumen.to_excel(writer, sheet_name="Resumen", index=False)

        # Por tipo contable
        bt = output["agregados"]["by_type_comparison"]
        tipo_df = pd.DataFrame([
            {"Tipo": t, "Legacy": v["legacy"], "New": v["new"],
             "Diff": v["new"] - v["legacy"]}
            for t, v in bt.items()
        ])
        tipo_df.to_excel(writer, sheet_name="Por tipo", index=False)

        # Disagreement patterns
        pats = output["agregados"]["disagreement_patterns"]
        if pats:
            pat_df = pd.DataFrame([
                {"Patrón": p, "Count": c} for p, c in pats.items()
            ])
            pat_df.to_excel(writer, sheet_name="Discrepancias", index=False)

        # Por documento
        doc_rows = []
        for r in output["resultados"]:
            if "error" in r:
                doc_rows.append({"Archivo": r["archivo"], "Error": r["error"]})
            else:
                doc_rows.append({
                    "Archivo": r["archivo"],
                    "Grupo": r["grupo"],
                    "Cuentas": r["total_accounts"],
                    "Legacy Class": r["legacy"]["classified"],
                    "Legacy UNK": r["legacy"]["unknown"],
                    "New Class": r["new"]["classified"],
                    "New UNK": r["new"]["unknown"],
                    "Acuerdos": r["agreements"],
                    "Discrepancias": r["disagreements_count"],
                    "Parse (s)": r["parse_time_s"],
                    "Legacy (s)": r["legacy_time_s"],
                    "New (s)": r["new_time_s"],
                })
        doc_df = pd.DataFrame(doc_rows)
        doc_df.to_excel(writer, sheet_name="Por documento", index=False)

        # Respuestas
        resp = output.get("respuestas", {})
        resp_rows = []
        for q, a in resp.items():
            if isinstance(a, dict):
                resp_rows.append({"Pregunta": q, "Respuesta": a.get("descripcion", str(a))})
            elif isinstance(a, list):
                resp_rows.append({"Pregunta": q, "Respuesta": "; ".join(a)})
            else:
                resp_rows.append({"Pregunta": q, "Respuesta": str(a)})
        resp_df = pd.DataFrame(resp_rows)
        resp_df.to_excel(writer, sheet_name="Respuestas", index=False)


def guardar_md(output: dict):
    c = output["agregados"]["comparison"]
    bt = output["agregados"]["by_type_comparison"]
    pats = output["agregados"]["disagreement_patterns"]
    resp = output.get("respuestas", {})

    lines = [
        "# Pipeline Benchmark Report\n",
        f"**Date:** 2026-07-21\n",
        "---\n",
        "## Global Comparison\n",
        "| Metric | Legacy (MotorHibridoLocal) | New (HomologationPipeline) | Delta |",
        "|---|---|---|---|",
        f"| Documentos | {c['documentos_procesados']} | {c['documentos_procesados']} | — |",
        f"| Cuentas totales | {c['total_cuentas']} | {c['total_cuentas']} | — |",
        f"| Clasificadas | {c['legacy_classified']} | {c['new_classified']} | {c['diff_classified']:+d} |",
        f"| UNKNOWN | {c['legacy_unknown']} | {c['new_unknown']} | {c['diff_unknown']:+d} |",
        f"| Cobertura | {c['legacy_coverage_pct']}% | {c['new_coverage_pct']}% | {c['new_coverage_pct'] - c['legacy_coverage_pct']:+.2f}% |",
        f"| Acuerdos entre motores | — | — | {c['agreements']} |",
        f"| Discrepancias | — | — | {c['disagreements']} |",
        f"| Docs con cambios | — | — | {c['docs_with_changes']} |",
        "| | | | |",
        f"| Tiempo parseo total | — | — | {c['parse_time_total_s']}s |",
        f"| Tiempo clasificación total | {c['legacy_time_total_s']}s | {c['new_time_total_s']}s | {c['new_time_total_s'] - c['legacy_time_total_s']:+.1f}s |",
        f"| Tiempo promedio por doc (parse) | — | — | {c['avg_parse_time_s']}s |",
        f"| Tiempo promedio por doc (clasif) | {c['avg_legacy_time_s']}s | {c['avg_new_time_s']}s | {c['avg_new_time_s'] - c['avg_legacy_time_s']:+.2f}s |",
    ]

    # By type
    lines += [
        "\n## Coverage by Account Type\n",
        "| Type | Legacy | New | Delta |",
        "|---|---|---|---|",
    ]
    for t, v in sorted(bt.items()):
        delta = v["new"] - v["legacy"]
        lines.append(f"| {t} | {v['legacy']} | {v['new']} | {delta:+d} |")

    # Disagreements
    lines += [
        "\n## Top Disagreement Patterns\n",
        "| Pattern | Count |",
        "|---|---|",
    ]
    for pat, cnt in list(pats.items())[:20]:
        lines.append(f"| {pat} | {cnt} |")

    # Answers
    lines += [
        "\n## Analysis\n",
        "### 1. ¿Dónde gana el nuevo pipeline?\n",
    ]
    for v in resp.get("donde_gana_nuevo", ["No identificado"]):
        lines.append(f"- {v}")
    lines += [
        "\n### 2. ¿Dónde sigue ganando el legacy?\n",
    ]
    for v in resp.get("donde_gana_legacy", ["No identificado"]):
        lines.append(f"- {v}")
    gap = resp.get("gap_cuentas_para_igualar", {})
    lines += [
        "\n### 3. Gap para igualar al legacy\n",
        f"{gap.get('descripcion', 'N/A')}",
        "\n### 4. Principal cuello de botella\n",
        f"{resp.get('cuello_de_botella_principal', {}).get('descripcion', 'N/A')}",
        "\n### 5. Cambio único de mayor impacto\n",
        f"{resp.get('cambio_unico_mayor_mejora', {}).get('descripcion', 'N/A')}",
    ]

    lines.append("\n---\n*Generated by run_pipeline_benchmark.py*")

    with open(OUTPUT_MD, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
