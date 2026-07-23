"""
Valida AccountTypeFilter contra el dataset completo.

Compara pipeline con flag OFF vs ON: cobertura, UNKNOWN, falsos positivos.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.features import CMCCFeatureFlags
from pipeline.homologation_pipeline import HomologationPipeline

CHECKPOINT_PATH = Path(__file__).parent / "account_type_filter_checkpoint.json"
OUTPUT_PATH = Path(__file__).parent / "account_type_validation_filter.json"


def recolectar_pdfs() -> list[Path]:
    raiz = next(
        (p for p in [Path("datasets"), Path(".")] if p.exists()),
        Path(".")
    )
    pdfs = []
    for grupo in ["HOLDOUT", "edge_cases", "validacion"]:
        carpeta = raiz / grupo
        if carpeta.exists():
            pdfs.extend(sorted(carpeta.glob("*.pdf")))
    return pdfs


def cargar_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"procesados": 0, "total_pdfs": 0, "resultados": []}


def guardar_checkpoint(data: dict):
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    pdfs = recolectar_pdfs()
    if not pdfs:
        print("ERROR: No se encontraron PDFs")
        sys.exit(1)

    data = cargar_checkpoint()
    data["total_pdfs"] = len(pdfs)
    pendientes = pdfs[data["procesados"]:]

    if pendientes:
        print(f"Procesando {len(pendientes)} PDFs restantes...")
        t0 = time.perf_counter()

        for i, pdf in enumerate(pendientes, start=data["procesados"] + 1):
            t1 = time.perf_counter()
            try:
                # OFF
                hp_off = HomologationPipeline()
                res_off = hp_off.process(pdf)

                # ON
                hp_on = HomologationPipeline(
                    features=CMCCFeatureFlags(ENABLE_ACCOUNT_TYPE_FILTER=True)
                )
                res_on = hp_on.process(pdf)

                # Comparar
                off_classified = {c["account_name"]: c for c in res_off["classified"]}
                on_classified = {c["account_name"]: c for c in res_on["classified"]}

                filtered = res_on.get("tipo_filtered", 0)
                unk_off = sum(1 for c in res_off["classified"] if c["standard_code"] is None)
                unk_on = sum(1 for c in res_on["classified"] if c["standard_code"] is None)

                # Detectar cambios específicos
                code_changes = []
                for name, c_off in off_classified.items():
                    c_on = on_classified.get(name)
                    if c_on and c_off["standard_code"] != c_on["standard_code"]:
                        code_changes.append({
                            "account_name": name,
                            "code_off": c_off["standard_code"],
                            "code_on": c_on["standard_code"],
                            "method_off": c_off["method"],
                            "method_on": c_on["method"],
                        })

                doc_result = {
                    "archivo": pdf.name,
                    "grupo": pdf.parent.name,
                    "total_off": res_off["accounts_total"],
                    "classified_off": res_off["accounts_classified"],
                    "classified_on": res_on["accounts_classified"],
                    "unk_off": unk_off,
                    "unk_on": unk_on,
                    "tipo_filtered": filtered,
                    "code_changes": code_changes[:20],  # top 20 per doc
                    "n_code_changes": len(code_changes),
                }
                data["resultados"].append(doc_result)

            except Exception as e:
                print(f"  [{i}/{len(pdfs)}] ERROR: {pdf.name} — {e}")
                data["resultados"].append({
                    "archivo": pdf.name,
                    "error": str(e),
                })

            elapsed = time.perf_counter() - t1
            data["procesados"] += 1
            print(f"  [{i}/{len(pdfs)}] {pdf.name} ({elapsed:.1f}s)")

            if i % 10 == 0:
                guardar_checkpoint(data)

        print(f"\nTiempo total: {time.perf_counter() - t0:.1f}s")

    guardar_checkpoint(data)

    # Compilar estadísticas
    total_classified_off = 0
    total_classified_on = 0
    total_unk_off = 0
    total_unk_on = 0
    total_tipo_filtered = 0
    total_code_changes = 0
    docs_with_changes = 0
    all_code_changes: list[dict] = []
    method_off_counter: Counter = Counter()
    method_on_counter: Counter = Counter()

    for r in data["resultados"]:
        if "error" in r:
            continue
        total_classified_off += r["classified_off"]
        total_classified_on += r["classified_on"]
        total_unk_off += r["unk_off"]
        total_unk_on += r["unk_on"]
        total_tipo_filtered += r["tipo_filtered"]
        total_code_changes += r["n_code_changes"]
        if r["n_code_changes"] > 0:
            docs_with_changes += 1
        for c in r.get("code_changes", []):
            all_code_changes.append(c)

    # Pattern summary of changes
    change_patterns: Counter = Counter()
    for c in all_code_changes:
        off = c["code_off"] or "UNK"
        on = c["code_on"] or "UNK"
        off_pref = off.split(".")[0] if off != "UNK" else "UNK"
        on_pref = on.split(".")[0] if on != "UNK" else "UNK"
        change_patterns[f"{off_pref} → {on_pref}"] += 1

    output = {
        "metadata": {
            "total_pdfs": data["total_pdfs"],
            "procesados": data["procesados"],
            "errores": sum(1 for r in data["resultados"] if "error" in r),
        },
        "summary": {
            "total_classified_off": total_classified_off,
            "total_classified_on": total_classified_on,
            "total_unk_off": total_unk_off,
            "total_unk_on": total_unk_on,
            "total_tipo_filtered": total_tipo_filtered,
            "total_code_changes": total_code_changes,
            "docs_with_changes": docs_with_changes,
            "coverage_change": f"{total_classified_on - total_classified_off:+d}",
            "unk_change": f"{total_unk_on - total_unk_off:+d}",
        },
        "change_patterns": dict(change_patterns.most_common(30)),
        "docs_with_changes_detail": [
            r for r in data["resultados"]
            if r.get("n_code_changes", 0) > 0
        ],
        "code_changes_sample": all_code_changes[:100],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n=== Resultados guardados en {OUTPUT_PATH} ===")
    print(f"  Procesados: {output['metadata']['procesados']}/{output['metadata']['total_pdfs']}")
    print(f"  Errores: {output['metadata']['errores']}")
    print(f"  Classified OFF: {total_classified_off}")
    print(f"  Classified ON:  {total_classified_on}")
    print(f"  UNKNOWN OFF:    {total_unk_off}")
    print(f"  UNKNOWN ON:     {total_unk_on}")
    print(f"  Tipo filtered:  {total_tipo_filtered}")
    print(f"  Code changes:   {total_code_changes}")
    print(f"  Docs w/ changes:{docs_with_changes}")
    print(f"  Top change patterns:")
    for pat, cnt in change_patterns.most_common(10):
        print(f"    {pat}: {cnt}")


if __name__ == "__main__":
    main()
