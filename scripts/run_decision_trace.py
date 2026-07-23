#!/usr/bin/env python3
"""Run Decision Trace — build full explainability layer."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from explainability.trace_builder import TraceBuilder
from explainability.trace_report import TraceReport
from explainability.trace_exporter import TraceExporter


def main():
    builder = TraceBuilder()
    traces = builder.build_all()
    print(f"Built {len(traces)} decision traces.")

    report = TraceReport(traces)
    print(f"  Classified: {report.total_classified:,}")
    print(f"  UNKNOWN: {report.total_unknown:,}")

    exporter = TraceExporter(traces, report)
    output_dir = "reports/decision_trace"

    xlsx = exporter.export_excel(f"{output_dir}/decision_trace.xlsx")
    print(f"  {xlsx.name}: {xlsx.stat().st_size:,} bytes")

    json_path = exporter.export_json(f"{output_dir}/decision_trace.json")
    print(f"  {json_path.name}: {json_path.stat().st_size:,} bytes")

    md = exporter.export_markdown(f"{output_dir}/decision_trace.md")
    print(f"  {md.name}: {md.stat().st_size:,} bytes")

    debt = exporter.export_technical_debt(f"{output_dir}/technical_debt.md")
    print(f"  {debt.name}: {debt.stat().st_size:,} bytes")

    print("\nDone.")


if __name__ == "__main__":
    main()
