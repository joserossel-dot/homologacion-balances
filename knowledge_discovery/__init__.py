# Knowledge Discovery package – Concept Discovery Engine (CDE).

"""Provides a single public entry point:
    run_discovery(concept_codes, data_source, **options)

The engine is **shadow‑only** – it reads raw variant data, discovers
sub‑concept clusters and writes reports under `reports/concept_discovery/`.
"""

from .concept_discovery import run_discovery

__all__ = ["run_discovery"]
