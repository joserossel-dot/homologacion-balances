#!/usr/bin/env python3
"""Release Governance Pipeline CLI.

Usage:
    python scripts/release_check.py [--config config/release.yml] [--skip-tests]

Executes all stages sequentially and reports deployment decision.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_pipeline import PipelineRunner, ReleaseReport


def main():
    parser = argparse.ArgumentParser(description="Release Governance Pipeline")
    parser.add_argument("--config", default="config/release.yml", help="Config file path")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test execution stage")
    args = parser.parse_args()

    runner = PipelineRunner(args.config)

    if args.skip_tests:
        cfg = runner.config
        if "stages" not in cfg:
            cfg["stages"] = {}
        cfg["stages"]["run_tests"] = False

    ctx = runner.run()

    report = ReleaseReport(runner)
    report.generate_all()

    print("\n" + "=" * 40)
    print(f"  Release {ctx.release_id}")
    print("=" * 40)

    passed = ctx.tests_passed
    failed = ctx.tests_failed
    total = passed + failed
    print(f"  Tests          {'PASS' if failed == 0 else 'FAIL'} ({passed}/{total})")

    for sr in runner.stages:
        if sr.stage_id == "STAGE_1":
            continue
        icon = "PASS" if sr.status.value == "PASS" else "FAIL" if sr.status.value in ("FAIL", "ERROR") else "WARN"
        print(f"  {sr.stage_name:<16} {icon}")

    quality = runner.context_dict.get("quality_metrics", {})
    print(f"  {'Coverage':<16} {quality.get('coverage', 'N/A')}%")
    print(f"  {'Accuracy':<16} {quality.get('accuracy', 'N/A')}")
    print(f"  {'UNKNOWN':<16} {quality.get('unknown', 'N/A')}")

    alerts = runner.context_dict.get("alerts", [])
    critical = sum(1 for a in alerts if isinstance(a, dict) and a.get("severity") == "CRITICAL")
    high = sum(1 for a in alerts if isinstance(a, dict) and a.get("severity") == "HIGH")
    print(f"  {'Critical Alerts':<16} {critical}")
    print(f"  {'High Alerts':<16} {high}")

    print(f"  {'Decision':<16} {runner.decision}")
    print("=" * 40)

    if runner.decision == "BLOCKED":
        print()
        print("  BLOCKED due to:")
        for r in runner.decision_reasons:
            if r["status"] == "FAIL":
                print(f"  - {r['reason']}")
        sys.exit(1)
    elif runner.decision == "APPROVED_WITH_WARNINGS":
        print()
        print("  Warnings:")
        for r in runner.decision_reasons:
            if r["status"] == "WARNING":
                print(f"  - {r['reason']}")
    else:
        print()
        print("  All gates passed. Release may proceed.")


if __name__ == "__main__":
    main()
