"""run_extractors.py — Selección de extractor especializado (Sprint 34).

Para cada documento PDF ejecuta el flujo COMPLETO del Parser Universal y
muestra QUÉ extractor fue seleccionado (anotación pura). NO modifica la
extracción: el resultado es exactamente el mismo con o sin esta tool.

Uso:
    python -m tools.run_extractors "datasets/validacion/BALANCE 2016.pdf"
    python -m tools.run_extractors pdf1.pdf pdf2.pdf
    python -m tools.run_extractors --dir datasets --limit 5 --suffix .pdf
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from parser_universal import ParserPDF

BASE_DIR = Path(__file__).resolve().parent.parent


def _info_text(info: Optional[dict]) -> str:
    if not info:
        return "n/d (análisis documental no disponible)"
    fallback = "SÍ (delegó al Parser Universal)" if info["fallback_used"] else "NO"
    return (
        f"    Familia detectada : {info.get('family_id', 'DESCONOCIDO')}\n"
        f"    Confidence        : {info.get('confidence', 0.0):.2f}\n"
        f"    Extractor         : {info.get('display_name', '?')} "
        f"({info.get('extractor_id', '?')})\n"
        f"    Fallback          : {fallback}\n"
        f"    Razón             : {info.get('reason', '')}\n"
        f"    Tiempo de decisión: {info.get('elapsed_ms', 0)} ms"
    )


def procesar(path: Path) -> int:
    t0 = time.perf_counter()
    resultado = ParserPDF().parsear(path)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    print("=" * 60)
    print(f"Documento           : {path}")
    print(f"Número de cuentas   : {len(resultado.cuentas)}")
    print(f"Tiempo total        : {elapsed_ms} ms")
    print("-" * 60)
    print(_info_text(resultado.extractor_info))
    print("=" * 60)
    print()
    return len(resultado.cuentas)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Selección de extractor (anotación) sin modificar la extracción.",
    )
    parser.add_argument("archivos", nargs="*", help="PDFs a procesar")
    parser.add_argument("--dir", type=str, default=None,
                        help="Procesar todos los archivos de un directorio")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limitar el número de archivos")
    parser.add_argument("--suffix", type=str, default=".pdf",
                        help="Sufijo a filtrar (default: .pdf)")
    args = parser.parse_args()

    archivos: list[Path] = []
    if args.dir:
        root = Path(args.dir)
        if not root.exists():
            print(f"Directorio no encontrado: {root}")
            return 1
        archivos = sorted(
            p for p in root.rglob(f"*{args.suffix}")
            if "desktop.ini" not in p.name.lower()
        )
    else:
        archivos = [Path(a) for a in args.archivos]

    if not archivos:
        print("No hay archivos para procesar. Usa rutas o --dir.")
        return 1

    if args.limit:
        archivos = archivos[: args.limit]

    total_cuentas = 0
    for path in archivos:
        if not path.exists():
            print(f"Archivo no existe: {path}\n")
            continue
        total_cuentas += procesar(path)

    print(f"{len(archivos)} documento(s), {total_cuentas} cuenta(s) en total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
