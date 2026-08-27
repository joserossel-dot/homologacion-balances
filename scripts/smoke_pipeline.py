"""Ejecuta manualmente el pipeline operativo sobre un balance local.

Este script reemplaza al simulador historico ``test_orquestador.py``, que
dependia de ``db_repository`` y ``src.core.orquestador``. Ninguno de esos
componentes coordina la aplicacion operativa actual.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.homologation_pipeline import HomologationPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Procesa un PDF o Excel con el pipeline operativo.",
    )
    parser.add_argument("documento", type=Path, help="Ruta del balance")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("gold_standard.db"),
        help="Base local de aprendizaje usada cuando corresponde.",
    )
    args = parser.parse_args()

    if not args.documento.is_file():
        parser.error(f"No existe el documento: {args.documento}")

    resultado = HomologationPipeline(db_path=args.db_path).process(
        args.documento,
    )
    resumen = {
        clave: valor
        for clave, valor in resultado.items()
        if clave not in {"classified", "ignored", "cmcc_review_queue"}
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
