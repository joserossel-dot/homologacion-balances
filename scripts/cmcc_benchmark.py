"""SPRINT 26.1 — CMCC Benchmark: before/after comparison.

Compares pipeline performance with CMCC disabled vs CMCC enabled.
Measures coverage, UNKNOWN reduction, accuracy, and execution time.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags
from validation.dataset_manager import DatasetManager

REPORTS_DIR = Path("reports/cmcc_benchmark")
GS_DB_PATH = "gold_standard.db"


def _run_pipeline(features: CMCCFeatureFlags, label: str) -> dict[str, Any]:
    pipeline = HomologationPipeline(str(GS_DB_PATH), features=features)
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    print(f"  [{label}] Processing {len(all_files)} files...")

    total_accounts = 0
    total_classified = 0
    total_unknown = 0
    method_counter: Counter = Counter()
    total_time = 0.0

    for i, dfile in enumerate(all_files):
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        doc_start = time.perf_counter()
        try:
            result = pipeline.process(str(dfile.path))
            doc_elapsed = time.perf_counter() - doc_start
            total_time += doc_elapsed

            total_accounts += result.get("accounts_total", 0)
            total_classified += result.get("accounts_classified", 0)
            total_unknown += result.get("accounts_without_dictionary_match", 0)

            for acct in result.get("classified", []):
                method_counter[acct.get("method", "unknown")] += 1

            print(f"    [{i+1}/{len(all_files)}] {rel_path[:60]} "
                  f"({doc_elapsed:.2f}s)")
        except Exception as e:
            print(f"    [{i+1}/{len(all_files)}] ERROR: {e}")

    return {
        "label": label,
        "files_processed": len(all_files),
        "total_accounts": total_accounts,
        "total_classified": total_classified,
        "total_unknown": total_unknown,
        "coverage_pct": round(total_classified / max(total_accounts, 1) * 100, 2),
        "unknown_pct": round(total_unknown / max(total_accounts, 1) * 100, 2),
        "total_time_seconds": round(total_time, 3),
        "method_distribution": dict(method_counter.most_common()),
        "feature_flags": features.to_dict(),
    }


def run_benchmark() -> dict[str, Any]:
    print("=" * 70)
    print("SPRINT 26.1 — CMCC Benchmark: Before / After")
    print("=" * 70)
    print()

    # Baseline: CMCC disabled
    disabled = CMCCFeatureFlags(
        ENABLE_CMCC=False, ENABLE_CMCC_SHADOW=False, ENABLE_CMCC_PRODUCTION=False,
    )
    baseline = _run_pipeline(disabled, "BASELINE (CMCC disabled)")

    print()

    # Shadow: CMCC shadow only
    shadow = CMCCFeatureFlags(
        ENABLE_CMCC=True, ENABLE_CMCC_SHADOW=True, ENABLE_CMCC_PRODUCTION=False,
    )
    shadow_result = _run_pipeline(shadow, "SHADOW (CMCC shadow only)")

    print()

    # Production: CMCC can classify (score >= 0.95)
    production = CMCCFeatureFlags(
        ENABLE_CMCC=True, ENABLE_CMCC_SHADOW=False, ENABLE_CMCC_PRODUCTION=True,
        CMCC_THRESHOLD=0.95,
    )
    prod_result = _run_pipeline(production, "PRODUCTION (CMCC enabled, threshold=0.95)")

    print()

    # Compare results
    print("=" * 70)
    print("BENCHMARK COMPARISON")
    print("=" * 70)
    print()
    print(f"{'Metric':<40} {'BASELINE':<15} {'SHADOW':<15} {'PRODUCTION':<15}")
    print(f"{'-'*40} {'-'*15} {'-'*15} {'-'*15}")
    print(f"{'Accounts':<40} {baseline['total_accounts']:<15} {shadow_result['total_accounts']:<15} {prod_result['total_accounts']:<15}")
    print(f"{'Classified':<40} {baseline['total_classified']:<15} {shadow_result['total_classified']:<15} {prod_result['total_classified']:<15}")
    print(f"{'UNKNOWN':<40} {baseline['total_unknown']:<15} {shadow_result['total_unknown']:<15} {prod_result['total_unknown']:<15}")
    print(f"{'Coverage %':<40} {baseline['coverage_pct']:<15} {shadow_result['coverage_pct']:<15} {prod_result['coverage_pct']:<15}")
    print(f"{'UNKNOWN %':<40} {baseline['unknown_pct']:<15} {shadow_result['unknown_pct']:<15} {prod_result['unknown_pct']:<15}")
    print(f"{'Time (s)':<40} {baseline['total_time_seconds']:<15} {shadow_result['total_time_seconds']:<15} {prod_result['total_time_seconds']:<15}")

    delta_covered = prod_result["total_classified"] - baseline["total_classified"]
    delta_unknown = baseline["total_unknown"] - prod_result["total_unknown"]
    delta_coverage = prod_result["coverage_pct"] - baseline["coverage_pct"]
    print()
    print(f"{'Improvement':<40} {'':<15} {'':<15} {'':<15}")
    print(f"{'  New classifications':<40} {'':<15} {'':<15} {delta_covered:<15}")
    print(f"{'  UNKNOWN reduction':<40} {'':<15} {'':<15} {delta_unknown:<15}")
    print(f"{'  Coverage gain (pp)':<40} {'':<15} {'':<15} {delta_coverage:<15}")

    comparison = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "shadow": shadow_result,
        "production": prod_result,
        "improvement": {
            "new_classifications": delta_covered,
            "unknown_reduction": delta_unknown,
            "coverage_gain_pp": round(delta_coverage, 2),
        },
    }

    return comparison


def save_reports(data: dict[str, Any]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "cmcc_benchmark.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport saved: {path.resolve()}")

    md_path = REPORTS_DIR / "cmcc_benchmark.md"
    lines = [
        "# CMCC Benchmark: Before / After",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "## Feature Flag Configuration",
        "",
        "| Flag | Baseline | Shadow | Production |",
        "|---|---|---|---|",
    ]
    flag_names = ["ENABLE_CMCC", "ENABLE_CMCC_SHADOW", "ENABLE_CMCC_PRODUCTION", "ENABLE_CMCC_ROLLBACK", "CMCC_THRESHOLD"]
    for fn in flag_names:
        b = data["baseline"]["feature_flags"].get(fn, "")
        s = data["shadow"]["feature_flags"].get(fn, "")
        p = data["production"]["feature_flags"].get(fn, "")
        lines.append(f"| {fn} | {b} | {s} | {p} |")

    lines.extend([
        "",
        "## Results",
        "",
        "| Metric | Baseline | Shadow | Production |",
        "|---|---|---|---|",
        f"| Accounts | {data['baseline']['total_accounts']} | {data['shadow']['total_accounts']} | {data['production']['total_accounts']} |",
        f"| Classified | {data['baseline']['total_classified']} | {data['shadow']['total_classified']} | {data['production']['total_classified']} |",
        f"| UNKNOWN | {data['baseline']['total_unknown']} | {data['shadow']['total_unknown']} | {data['production']['total_unknown']} |",
        f"| Coverage | {data['baseline']['coverage_pct']}% | {data['shadow']['coverage_pct']}% | {data['production']['coverage_pct']}% |",
        f"| UNKNOWN Rate | {data['baseline']['unknown_pct']}% | {data['shadow']['unknown_pct']}% | {data['production']['unknown_pct']}% |",
        f"| Time (s) | {data['baseline']['total_time_seconds']} | {data['shadow']['total_time_seconds']} | {data['production']['total_time_seconds']} |",
        "",
        "## Improvements (Baseline → Production)",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| New classifications | {data['improvement']['new_classifications']} |",
        f"| UNKNOWN reduction | {data['improvement']['unknown_reduction']} |",
        f"| Coverage gain (pp) | {data['improvement']['coverage_gain_pp']} |",
        "",
        "## Method Distribution (Production)",
        "",
        "| Method | Count |",
        "|---|---|",
    ])
    for method, count in sorted(data["production"]["method_distribution"].items()):
        lines.append(f"| {method} | {count} |")

    lines.extend(["", "---", "*No production code was modified. Benchmark only.*"])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report saved: {md_path.resolve()}")


def main():
    data = run_benchmark()
    save_reports(data)

    print()
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"  Baseline coverage:  {data['baseline']['coverage_pct']}%")
    print(f"  Production coverage: {data['production']['coverage_pct']}%")
    print(f"  Gain:                {data['improvement']['coverage_gain_pp']}pp")
    print(f"  New classifications: {data['improvement']['new_classifications']}")
    print(f"  Reports:             {REPORTS_DIR.resolve()}")


if __name__ == "__main__":
    main()
