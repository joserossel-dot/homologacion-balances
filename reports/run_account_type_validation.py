"""
Valida AccountTypeResolver contra el dataset completo con checkpoint.

Procesa cada PDF una sola vez (con flag=True). Guarda checkpoint
cada 10 documentos. La resolución es O(n) en cada cuenta — CPU puro.
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import parser_universal as pu
from parser_universal import ParserPDF

CHECKPOINT_PATH = Path(__file__).parent / "account_type_validation_checkpoint.json"
OUTPUT_PATH = Path(__file__).parent / "account_type_validation.json"

ORIGENES_INTERES = [
    "activo", "pasivo", "perdida", "ganancia",
    "deudor", "acreedor", "desconocido"
]


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
    return {
        "procesados": 0,
        "total_pdfs": 0,
        "errores": [],
        "cuentas_por_documento": {},
        "distribucion_tipo_cuenta": {},
        "total_origen_columna": {},
        "total_metodos": {},
        "confianzas_por_metodo": {},
        "documentos_con_cambio_cuentas": 0,
        "cambio_cuentas_detalle": [],
    }


def guardar_checkpoint(data: dict):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def procesar_pdf(pdf: Path) -> dict:
    pu.ENABLE_ACCOUNT_TYPE_RESOLVER = False
    res_classic = ParserPDF().parsear(pdf)

    pu.ENABLE_ACCOUNT_TYPE_RESOLVER = True
    res_dynamic = ParserPDF().parsear(pdf)

    n_classic = len(res_classic.cuentas)
    n_dynamic = len(res_dynamic.cuentas)

    doc_result = {
        "grupo": pdf.parent.name,
        "archivo": pdf.name,
        "n_cuentas_classic": n_classic,
        "n_cuentas_dynamic": n_dynamic,
        "hay_cambio": n_classic != n_dynamic,
        "n_advertencias": len(res_dynamic.advertencias),
        "cuentas": [],
    }

    for c in res_dynamic.cuentas:
        cuenta_info = {
            "linea": c.linea,
            "codigo": c.codigo,
            "nombre": c.nombre,
            "origen_columna": c.origen_columna.value,
            "tipo_cuenta": c.tipo_cuenta,
        }
        doc_result["cuentas"].append(cuenta_info)

    # Extraer advertencia del resolver
    for w in res_dynamic.advertencias:
        if "AccountTypeResolver" in w:
            doc_result["advertencia_resolver"] = w

    return doc_result


def main():
    pdfs = recolectar_pdfs()
    if not pdfs:
        print("ERROR: No se encontraron PDFs en datasets/")
        sys.exit(1)

    data = cargar_checkpoint()
    data["total_pdfs"] = len(pdfs)
    pendientes = pdfs[data["procesados"]:]

    if not pendientes:
        print(f"Checkpoint completo: {data['procesados']}/{data['total_pdfs']}")
    else:
        print(f"Procesando {len(pendientes)} PDFs restantes (desde #{data['procesados'] + 1})...")
        t0 = time.perf_counter()

        for i, pdf in enumerate(pendientes, start=data["procesados"] + 1):
            t1 = time.perf_counter()
            try:
                doc = procesar_pdf(pdf)
            except Exception as e:
                data["errores"].append({"archivo": pdf.name, "error": str(e)})
                print(f"  [{i}/{len(pdfs)}] ERROR: {pdf.name} — {e}")
                data["procesados"] += 1
                if i % 5 == 0:
                    guardar_checkpoint(data)
                continue

            data["cuentas_por_documento"][pdf.name] = doc

            if doc["hay_cambio"]:
                data["documentos_con_cambio_cuentas"] += 1
                data["cambio_cuentas_detalle"].append({
                    "archivo": pdf.name,
                    "classic": doc["n_cuentas_classic"],
                    "dynamic": doc["n_cuentas_dynamic"],
                })

            for c in doc["cuentas"]:
                oc = c["origen_columna"]
                data["total_origen_columna"][oc] = data["total_origen_columna"].get(oc, 0) + 1
                tc = c["tipo_cuenta"]
                if tc:
                    data["distribucion_tipo_cuenta"][tc] = data["distribucion_tipo_cuenta"].get(tc, 0) + 1

            elapsed = time.perf_counter() - t1
            data["procesados"] += 1
            print(f"  [{i}/{len(pdfs)}] {pdf.name}: {doc['n_cuentas_dynamic']} cuentas ({elapsed:.1f}s)")

            if i % 5 == 0:
                guardar_checkpoint(data)

        print(f"\nTiempo total: {time.perf_counter() - t0:.1f}s")

    pu.ENABLE_ACCOUNT_TYPE_RESOLVER = False

    # Construir reporte final
    output = {
        "metadata": {
            "total_pdfs": data["total_pdfs"],
            "procesados": data["procesados"],
            "errores_count": len(data["errores"]),
        },
        "errores": data["errores"],
        "documentos_con_cambio_cuentas": data["documentos_con_cambio_cuentas"],
        "cambio_cuentas_detalle": data["cambio_cuentas_detalle"][:10],
        "distribucion_tipo_cuenta": dict(sorted(
            data["distribucion_tipo_cuenta"].items(),
            key=lambda x: -x[1]
        )),
        "total_origen_columna": dict(sorted(
            data["total_origen_columna"].items(),
            key=lambda x: -x[1]
        )),
        "cuentas_por_documento": {
            k: {
                "grupo": v["grupo"],
                "n_cuentas": v["n_cuentas_dynamic"],
                "n_advertencias": v["n_advertencias"],
            }
            for k, v in data["cuentas_por_documento"].items()
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en {OUTPUT_PATH}")
    print(f"  Procesados: {output['metadata']['procesados']}/{output['metadata']['total_pdfs']}")
    print(f"  Errores: {output['metadata']['errores_count']}")
    print(f"  Docs con cambio cuentas: {output['documentos_con_cambio_cuentas']}")
    print(f"  Distribución tipo_cuenta:")
    for tipo, count in output["distribucion_tipo_cuenta"].items():
        print(f"    {tipo}: {count}")


if __name__ == "__main__":
    main()
