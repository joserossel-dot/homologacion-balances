#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path

from evidence.evidence_serializer import convert_shadow_to_evidences
from evidence.evidence_report import compute_coverage, generate_audit_report

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SHADOW_PATH = Path("reports/semantic_shadow/shadow_data.json")
EVIDENCE_PATH = Path("reports/evidence")
OUTPUT_EVIDENCE = EVIDENCE_PATH / "evidence_data.json"


def main() -> None:
    log.info("=== Evidence Layer Audit ===\n")

    EVIDENCE_PATH.mkdir(parents=True, exist_ok=True)

    log.info("1. Converting shadow data to AccountEvidence...")
    evidences = convert_shadow_to_evidences(
        str(SHADOW_PATH),
        evidence_path=str(OUTPUT_EVIDENCE),
    )
    log.info(f"   Created {len(evidences)} AccountEvidence objects")

    log.info("\n2. Computing coverage...")
    coverage = compute_coverage(evidences)
    log.info(f"   Total: {coverage['total']}")
    log.info(f"   Complete: {coverage['complete']} ({coverage['complete_pct']}%)")
    log.info(f"   Avg coverage score: {coverage['avg_coverage_score']}%")
    log.info("")
    for field, info in sorted(coverage["fields"].items()):
        log.info(f"   {field:25s} {info['pct']:6.1f}%")

    log.info("\n3. Missing fields (top 10):")
    for field, count in coverage.get("top_missing_fields", [])[:10]:
        log.info(f"   - {field}: {count}")

    log.info("\n4. Generating reports...")
    paths = generate_audit_report(evidences, EVIDENCE_PATH)
    for name, p in paths.items():
        log.info(f"   {name}: {p}")

    log.info(f"\n   Evidence data: {OUTPUT_EVIDENCE}")
    log.info("\n=== Evidence Layer Audit Complete ===")


if __name__ == "__main__":
    main()
