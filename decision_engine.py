#!/usr/bin/env python3
"""Rule-based decision engine for PDF processing strategy.

Input:
    A single JSON record from inspect_pdf.py, or a path to
    inspection_results.json (batch mode).

Output:
    JSON decision object with family, extractor, and reasons.

Usage:
    python3 decision_engine.py <record.json>
    python3 decision_engine.py inspection_results.json
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path


def decide(record: dict) -> dict:
    has_text = record.get("has_selectable_text", False)
    tables = record.get("tables_detected", 0)
    code_pat = record.get("account_code_pattern")

    reasons = []
    family = None
    extractor = None

    # Rule 1 – scanned / image-only PDF
    if has_text is False:
        family = "F01"
        extractor = "OCR"
        reasons.append("has_selectable_text is false — no machine-readable text")
        reasons.append("requires OCR to extract content")

    # Rule 2 – selectable text with detected tables
    elif has_text is True and tables > 0:
        family = "F02"
        extractor = "TABLE_EXTRACTOR"
        reasons.append(f"has_selectable_text is true with {tables} table(s) detected")
        reasons.append("table structure available for extraction")

    # Rule 3 – selectable text, no tables, but has account codes
    elif has_text is True and tables == 0 and code_pat is not None:
        family = "F03"
        extractor = "TEXT_EXTRACTOR"
        reasons.append("has_selectable_text is true, no tables, account codes present")
        reasons.append("line-by-line text extraction suitable")

    # Rule 4 – fallback
    else:
        family = "F04"
        extractor = "SEMANTIC_EXTRACTOR"
        reasons.append("no clear structural pattern detected")
        reasons.append("fallback to semantic analysis")

        if has_text is True:
            reasons.append("text is selectable but no tables or account codes found")
        else:
            reasons.append("no selectable text available")

    return {
        "family": family,
        "extractor": extractor,
        "confidence": 1.0,
        "reasons": reasons,
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 decision_engine.py <record.json | inspection_results.json>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Single record or list of records
    records = data if isinstance(data, list) else [data]

    families = Counter()
    for rec in records:
        if "error" in rec:
            continue
        decision = decide(rec)
        families[decision["family"]] += 1

    # Print summary sorted by family code
    for code in sorted(families):
        print(f"{code} : {families[code]}")


if __name__ == "__main__":
    main()
