#!/usr/bin/env python3
"""Run Scientific Validation Framework — build gold standard infrastructure."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scientific_validation import (
    GoldStandardCase,
    ValidationResult,
    ErrorCategory,
    ValidationDataset,
    Agreement,
    Metrics,
    ValidationReports,
)


def main():
    dataset = ValidationDataset()
    output_dir = "reports/scientific_validation"

    template = dataset.generate_template(f"{output_dir}/gold_standard_template.xlsx")
    print(f"Gold Standard template: {template} ({template.stat().st_size:,} bytes)")

    traces = []
    trace_path = Path("reports/decision_trace/decision_trace.json")
    if trace_path.exists():
        import json
        with open(trace_path) as f:
            td = json.load(f)
        traces = td.get("traces", [])

    results = dataset.build_results_from_traces(traces)
    print(f"Built {len(results)} validation results from traces.")

    dataset.export_excel(f"{output_dir}/validation_dataset.xlsx")
    dataset.export_json(f"{output_dir}/validation_dataset.json")

    metrics = Metrics(dataset.results)

    agreement = None

    reports = ValidationReports.generate_all(dataset, metrics, agreement, output_dir)

    print(f"\nAll outputs generated in {output_dir}/")
    for name, path in reports.items():
        size = path.stat().st_size
        print(f"  {name}: {path.name} ({size:,} bytes)")

    s = metrics.summary()
    if s["total"] > 0:
        print(f"\n  Accuracy: {s['accuracy_pct']}%")
        print(f"  Macro F1: {s['macro_f1']}")
        print(f"  Micro F1: {s['micro_f1']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
