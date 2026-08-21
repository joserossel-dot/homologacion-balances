"""Preflight seguro para la persistencia Neon y el pipeline operativo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from persistence.neon_store import NeonKnowledgeStore
from pipeline.homologation_pipeline import HomologationPipeline

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
    checks = {
        "neon": True,
        "catalog_entries": stats["catalog_entries"],
        "dictionary_entries": stats["dictionary_entries"],
        "pipeline_dictionary_entries": len(pipeline._dictionary),
        "history_accessible": isinstance(store.dictionary_history(1), list),
        "conflicts_accessible": isinstance(store.conflicts(), list),
    }
    ok = (
        checks["catalog_entries"] >= 62
        and checks["dictionary_entries"] >= 876
        and checks["pipeline_dictionary_entries"] == checks["dictionary_entries"]
    )
    print(json.dumps(checks, ensure_ascii=False, sort_keys=True))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
