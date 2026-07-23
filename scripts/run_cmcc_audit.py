#!/usr/bin/env python3
"""Run CMCC Coverage Audit."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.cmcc_audit.auditor import CMCCAuditor


def main():
    auditor = CMCCAuditor()
    auditor.load()
    print(f"Loaded {len(auditor.entries)} concept statistics.")
    print(f"Total UNKNOWN in audit: {auditor.total_unknown}")

    reports = auditor.generate_reports("reports/cmcc_audit")
    print(f"\nAll outputs generated in reports/cmcc_audit/")
    for name, path in reports.items():
        size = path.stat().st_size
        print(f"  {name}: {path.name} ({size:,} bytes)")

    if hasattr(auditor, "answers"):
        print("\n--- Key Answers ---")
        a = auditor.answers
        print(f"Top 5 concentration: {a.get('q2_top5_pct', '?')}%")
        print(f"Top 10 concentration: {a.get('q3_top10_pct', '?')}%")
        print(f"Top 20 concentration: {a.get('q4_top20_pct', '?')}%")
        print(f"UNKNOWN disappearing via clusters: {a.get('q5_unknown_disappear_no_parser', '?')}")
        print("Done.")


if __name__ == "__main__":
    main()
