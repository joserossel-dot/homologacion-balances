#!/usr/bin/env python3
"""Run CMCC Validation Package — generate review package for accountant."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.cmcc_validation.validator import CMCCValidator


def main():
    high_confidence = "reports/variant_discovery/high_confidence.xlsx"
    concept_suggestions = "reports/variant_discovery/concept_suggestions.xlsx"
    output_dir = "reports/cmcc_validation"

    for p in [high_confidence, concept_suggestions]:
        if not Path(p).exists():
            print(f"ERROR: {p} not found. Run variant discovery first.")
            sys.exit(1)

    val = CMCCValidator(high_confidence, concept_suggestions)
    val.load()
    print(f"Loaded {val.total_entries} validation entries.")

    reports = val.generate_reports(output_dir)
    print(f"\nAll outputs generated in {output_dir}/")
    for name, path in reports.items():
        size = path.stat().st_size
        print(f"  {name}: {path.name} ({size:,} bytes)")

    print("\nDone. The accountant can now review review_package.xlsx.")


if __name__ == "__main__":
    main()
