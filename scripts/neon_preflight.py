"""Preflight seguro para la persistencia Neon y el pipeline operativo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from persistence.neon_store import NeonKnowledgeStore  # noqa: E402
from pipeline.homologation_pipeline import HomologationPipeline  # noqa: E402


def checks_pass(checks: dict) -> bool:
    return bool(
        checks["neon"]
        and checks["history_accessible"]
        and checks["conflicts_accessible"]
        and checks["catalog_entries"] >= 62
        and checks["dictionary_entries"] >= 876
        and checks["dictionary_entries"] == checks["loaded_dictionary_entries"]
        and checks["pipeline_dictionary_entries"]
        == checks["classifiable_dictionary_entries"]
        and checks["unknown_catalog_codes"] == 0
        and checks["protected_conflicting_dictionary_names"]
        == checks["conflicting_dictionary_names"]
    )


def dictionary_profile(
    dictionary: list[dict], catalog: dict, pipeline_entries: int,
    protected_conflicts: int,
) -> dict[str, int]:
    """Resume una unica instantanea sin publicar nombres ni datos de conexion."""
    excluded = [
        row for row in dictionary
        if row.get("codigo_estandar") == "__EXCLUIR__"
    ]
    classifiable = [
        row for row in dictionary
        if row.get("codigo_estandar") != "__EXCLUIR__"
    ]
    valid_codes = set(catalog)
    unknown_codes = {
        str(row.get("codigo_estandar") or "").strip()
        for row in classifiable
        if row.get("codigo_estandar") not in valid_codes
    }
    codes_by_name: dict[str, set[str]] = {}
    for row in classifiable:
        name = HomologationPipeline._normalize_name(
            row.get("cuenta_original", "")
        )
        code = str(row.get("codigo_estandar") or "").strip()
        if name:
            codes_by_name.setdefault(name, set()).add(code)
    conflicting_names = sum(len(codes) > 1 for codes in codes_by_name.values())
    return {
        "loaded_dictionary_entries": len(dictionary),
        "excluded_dictionary_entries": len(excluded),
        "classifiable_dictionary_entries": len(classifiable),
        "pipeline_dictionary_entries": pipeline_entries,
        "unknown_catalog_codes": len(unknown_codes),
        "conflicting_dictionary_names": conflicting_names,
        "protected_conflicting_dictionary_names": protected_conflicts,
    }

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

    catalog = store.load_catalog()
    dictionary = store.load_dictionary()
    # La misma instantanea alimenta el perfil y el pipeline. Esto evita que una
    # promocion concurrente produzca un falso descuadre entre dos lecturas.
    pipeline = HomologationPipeline(dictionary=dictionary)
    checks = {
        "neon": True,
        "catalog_entries": len(catalog),
        "dictionary_entries": len(dictionary),
        "history_accessible": isinstance(store.dictionary_history(1), list),
        "conflicts_accessible": isinstance(store.conflicts(), list),
        **dictionary_profile(
            dictionary,
            catalog,
            len(pipeline._dictionary),
            len(pipeline._ambiguous_dictionary_names),
        ),
    }
    ok = checks_pass(checks)
    print(json.dumps(checks, ensure_ascii=False, sort_keys=True))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
