"""Preflight seguro para la persistencia Neon y el pipeline operativo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from persistence.neon_store import NeonKnowledgeStore
from pipeline.homologation_pipeline import HomologationPipeline


EXCLUDED_STANDARD_CODE = "__EXCLUIR__"


def operational_dictionary_entries(
    entries: Sequence[Mapping[str, Any]],
) -> int:
    """Cuenta las entradas que el pipeline puede usar para homologar."""
    return sum(
        entry.get("codigo_estandar") != EXCLUDED_STANDARD_CODE
        for entry in entries
    )


def dictionary_metrics_are_consistent(
    *,
    reported_entries: int,
    persisted_entries: Sequence[Mapping[str, Any]],
    pipeline_entries: int,
) -> bool:
    """Exige que las tres métricas representen el mismo diccionario.

    ``reported_entries`` contiene todas las filas activas de Neon, mientras que
    el pipeline descarta de forma deliberada ``__EXCLUIR__``. Por eso se
    comprueba tanto el total persistido como el total operacional filtrado.
    """
    return (
        reported_entries == len(persisted_entries)
        and pipeline_entries == operational_dictionary_entries(persisted_entries)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--migrate", action="store_true",
        help="Aplica la migracion idempotente antes de validar.",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    store = NeonKnowledgeStore()
    if not store.enabled:
        print("FAIL DATABASE_URL no configurada")
        return 2
    if not store.healthcheck():
        print("FAIL Neon no responde")
        return 3
    if args.migrate:
        store.initialize()

    stats = store.learning_statistics()
    pipeline = HomologationPipeline()
    try:
        persisted_dictionary = store.load_dictionary()
    except Exception:
        print("FAIL No fue posible leer el diccionario activo desde Neon")
        return 4

    checks = {
        "neon": True,
        "catalog_entries": stats["catalog_entries"],
        "dictionary_entries": stats["dictionary_entries"],
        "operational_dictionary_entries": operational_dictionary_entries(
            persisted_dictionary
        ),
        "pipeline_dictionary_entries": len(pipeline._dictionary),
        "history_accessible": isinstance(store.dictionary_history(1), list),
        "conflicts_accessible": isinstance(store.conflicts(), list),
    }
    ok = (
        checks["catalog_entries"] >= 62
        and checks["dictionary_entries"] >= 876
        and dictionary_metrics_are_consistent(
            reported_entries=checks["dictionary_entries"],
            persisted_entries=persisted_dictionary,
            pipeline_entries=checks["pipeline_dictionary_entries"],
        )
    )
    print(json.dumps(checks, ensure_ascii=False, sort_keys=True))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
