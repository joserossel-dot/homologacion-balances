#!/usr/bin/env python3
"""Sprint 27.1 — REVIEW_CMCC Review Pipeline.

Crea la cola de revisión humana para cuentas UNKNOWN con CMCC score == 1.0.
NO modifica clasificaciones oficiales.
NO toca producción.
Feature Flag: ENABLE_CMCC_REVIEW_PIPELINE

Genera reports/cmcc_review_pipeline/:
  review_queue.xlsx
  review_statistics.xlsx
  review_by_company.xlsx
  review_by_layout.xlsx
  review_by_concept.xlsx
  review_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["CMCC_ENABLE_CMCC"] = "false"
os.environ["CMCC_ENABLE_CMCC_SHADOW"] = "false"
os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "false"

from pipeline.features import CMCCFeatureFlags
from review.cmcc_review_pipeline import (
    run_pipeline_for_review,
    compute_statistics,
    generate_reports,
    generate_markdown,
)

REPORTS_DIR = Path("reports/cmcc_review_pipeline")
_print = lambda *a, **k: print(*a, **k, flush=True)


def main():
    _print("=" * 70)
    _print("SPRINT 27.1 — REVIEW_CMCC Pipeline")
    _print("Safe human review queue for UNKNOWN accounts")
    _print("=" * 70)
    _print()

    parser = argparse.ArgumentParser(description="CMCC Review Pipeline")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of files (0=all)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore cached pipeline results")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    features = CMCCFeatureFlags(
        ENABLE_CMCC=True,
        ENABLE_CMCC_SHADOW=True,
        ENABLE_CMCC_PRODUCTION=False,
        ENABLE_CMCC_REVIEW_PIPELINE=True,
    )

    t0 = time.perf_counter()

    review_queue, summary = run_pipeline_for_review(
        features, "REVIEW_CMCC", limit=args.limit,
    )

    elapsed = time.perf_counter() - t0

    _print(f"  Files: {summary['files']}")
    _print(f"  UNKNOWN: {summary['total_unknown']}")
    _print(f"  REVIEW candidates: {summary['total_review']}")
    _print()

    if not review_queue:
        _print("No REVIEW candidates found. All UNKNOWN accounts have score < 1.0.")
        _print()

    stats = compute_statistics(review_queue, summary)

    _print("Statistics:")
    _print(f"  REVIEW / UNKNOWN: {stats['review_pct']}%")
    _print(f"  Companies: {stats['num_companies']}")
    _print(f"  Concepts: {stats['num_concepts']}")
    _print(f"  Layouts: {stats['num_layouts']}")
    _print(f"  Documents: {stats['num_documents']}")
    _print()

    _print("Generating reports...")
    report_paths = generate_reports(review_queue, summary, stats)

    md = generate_markdown(review_queue, summary, stats, report_paths)
    md_path = REPORTS_DIR / "review_summary.md"
    md_path.write_text(md, encoding="utf-8")
    report_paths["review_summary.md"] = md_path

    _print()
    _print("=" * 70)
    _print("REVIEW PIPELINE COMPLETE")
    _print("=" * 70)
    _print(f"  Elapsed: {elapsed:.1f}s")
    _print(f"  UNKNOWN: {stats['total_unknown']} → REVIEW: {stats['total_review']} "
           f"({stats['review_pct']}%)")
    for name, path in sorted(report_paths.items()):
        size = path.stat().st_size if path.exists() else 0
        _print(f"    {name}: {size:,} bytes")

    json_path = REPORTS_DIR / "review_pipeline.json"
    json_data = {
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "configuration": features.to_dict(),
        "summary": summary,
        "statistics": stats,
        "elapsed_seconds": round(elapsed, 3),
    }
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    _print(f"    review_pipeline.json: {json_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
