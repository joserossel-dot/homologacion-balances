#!/usr/bin/env python3
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from review.review_package_builder import load_all_data, build_review_package

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

OUTPUT_DIR = Path("reports/review")


def main() -> None:
    log.info("=== Review Package Generator ===\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"review_package_{timestamp}.xlsx"

    log.info("1. Cargando datos...")
    data = load_all_data()
    num_accounts = len(data.get("shadow", {}).get("accounts", []))
    log.info(f"   Cuentas: {num_accounts}")

    log.info("\n2. Generando Review Package...")
    path = build_review_package(str(output_path), data)

    log.info(f"\n   Excel: {path}")

    # Quick summary
    accounts = data.get("shadow", {}).get("accounts", [])
    unclassified = sum(1 for a in accounts if a.get("method") in ("unclassified", "unknown", "", None))
    low_conf = sum(1 for a in accounts if (a.get("confidence", 0.0) or 0.0) < 0.85)
    log.info(f"\n   Resumen:")
    log.info(f"   - Total cuentas: {num_accounts}")
    log.info(f"   - No clasificadas: {unclassified}")
    log.info(f"   - Baja confianza (<0.85): {low_conf}")

    log.info("\n=== Review Package Complete ===")


if __name__ == "__main__":
    main()
