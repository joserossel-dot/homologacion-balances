#!/usr/bin/env python3
"""
Runner del Pattern Engine — FASE 15A.

Carga shadow_data.json, ejecuta el motor de patrones sobre cuentas
no clasificadas, y genera reportes en reports/patterns/.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from patterns.pattern_engine import PatternEngine
from patterns.pattern_report import PatternReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DEFAULT_SHADOW = Path("reports/semantic_shadow/shadow_data.json")
DEFAULT_OUTPUT = Path("reports/patterns")


def main(
    shadow_path: str | Path = DEFAULT_SHADOW,
    output_dir: str | Path = DEFAULT_OUTPUT,
) -> None:
    sp = Path(shadow_path)
    if not sp.exists():
        log.error("Shadow data not found: %s", sp)
        sys.exit(1)

    log.info("=== Pattern Engine Analysis ===")
    log.info("Loading shadow data from %s", sp)
    engine = PatternEngine()
    t0 = time.time()
    results, coverage = engine.load_and_analyze(sp)
    elapsed = time.time() - t0

    log.info("Analyzed %d accounts in %.2fs", len(results), elapsed)
    log.info(
        "Coverage on unclassified: %.1f%% (%d/%d)",
        coverage["coverage_unclassified_pct"],
        coverage["matched_unclassified"],
        coverage["total_unclassified"],
    )
    log.info(
        "Top families: %s",
        dict(
            list(coverage["family_counts"].items())[:5]
        ),
    )

    report = PatternReport(output_dir)
    paths = report.generate_all(results, coverage)

    log.info("Reports generated:")
    for name, path in paths.items():
        log.info("  %s: %s", name, path)

    print("\n=== Resumen Pattern Engine ===")
    print(f"  Cuentas analizadas:     {coverage['total_accounts']}")
    print(f"  No clasificadas:        {coverage['total_unclassified']}")
    print(f"  Matched (todas):        {coverage['matched_all']}")
    print(
        f"  Matched (no clasificadas): "
        f"{coverage['matched_unclassified']}"
    )
    print(
        f"  Cobertura no clasificadas: "
        f"{coverage['coverage_unclassified_pct']}%"
    )
    print(
        f"  Cobertura total:         "
        f"{coverage['coverage_all_pct']}%"
    )
    print(f"  Tiempo:                  {elapsed:.2f}s")
    print(f"  Reportes en:             {output_dir}")
    print(f"  Familias activas:        {len(coverage['family_counts'])}")
    print()


if __name__ == "__main__":
    main()
