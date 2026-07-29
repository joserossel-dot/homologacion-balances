#!/usr/bin/env python3
"""
smoke_test.py — Smoke Test del Backend RC1.

Procesa un archivo PDF/Excel completo y valida:
  - DocumentContext
  - Decision
  - Coverage
  - QA
  - Validation
  - Export
  - Errores
  - Logs

Uso:
    python smoke_test.py [--file tests/data/sample.pdf]

Debe terminar con: RC1 BACKEND PASSED
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.runner import BackendRunner
from backend.backend_models import BackendResult


def find_test_file() -> Path | None:
    candidates = [
        Path("tests/data/sample.pdf"),
        Path("tests/data/balance_ejemplo.pdf"),
        Path("datasets/"),
    ]
    for c in candidates:
        if c.is_file():
            return c
        if c.is_dir():
            files = list(c.rglob("*.pdf")) + list(c.rglob("*.xlsx")) + list(c.rglob("*.xls"))
            if files:
                return files[0]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke Test RC1 Backend")
    parser.add_argument("--file", type=str, help="Archivo PDF/Excel a procesar")
    args = parser.parse_args()

    file_path: Path | None = None
    if args.file:
        file_path = Path(args.file)
    else:
        file_path = find_test_file()

    if file_path is None or not file_path.exists():
        print("ERROR: No se encontró archivo de prueba.")
        print("Usage: python smoke_test.py --file <path_to_pdf_or_excel>")
        sys.exit(1)

    print("=" * 60)
    print("RC1 BACKEND SMOKE TEST")
    print("=" * 60)
    print(f"File: {file_path}")
    print()

    tests_passed = 0
    tests_total = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal tests_passed, tests_total
        tests_total += 1
        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"  {status} | {name}")
        if not condition and detail:
            print(f"       {detail}")
        if condition:
            tests_passed += 1

    try:
        backend = BackendRunner()
        result: BackendResult = backend.run(str(file_path))
    except Exception as e:
        print(f"\n  ❌ FAIL | Pipeline execution: {e}")
        print(f"\n  RESULT: {tests_passed}/{tests_total} passed")
        print("  RC1 BACKEND FAILED")
        sys.exit(1)

    print()

    # 1. DocumentContext
    check("DocumentContext created", result.document_context is not None)
    check("DocumentContext has identity", result.document_context is not None and result.document_context.identity is not None)
    check("DocumentContext has source_file", bool(result.source_file))
    check("DocumentContext state is terminal", result.document_context is not None and result.document_context.is_terminal)

    # 2. Execution
    check("Execution completed", result.execution.status == "completed", result.execution.status)
    check("Execution has elapsed time", result.execution.elapsed_seconds > 0)
    check("No execution errors", len(result.execution.errors) == 0, str(result.execution.errors))

    # 3. Statistics
    check("Total accounts > 0", result.statistics.total_accounts > 0)
    check("Coverage >= 0", result.statistics.coverage_pct >= 0.0)
    check("Unknown >= 0", result.statistics.unknown_pct >= 0.0)
    check("Classified >= 0", result.statistics.classified >= 0)

    # 4. Decision
    check("Decisions recorded", len(result.decisions) > 0)
    check("Decision stats present", bool(result.decision_stats))

    # 5. Coverage
    check("Coverage data present", bool(result.coverage))
    if result.coverage:
        coverage_overall = result.coverage.get("overall", 0.0)
        check("Coverage has overall > 0", coverage_overall > 0, f"overall={coverage_overall}")

    # 6. QA
    check("QA data present", bool(result.qa))
    if result.qa:
        check("QA confidence >= 0", result.qa.get("confidence", {}).get("overall", 0.0) >= 0)

    # 7. Exports
    check("Export paths present", bool(result.export_paths))
    if result.export_paths:
        check("JSON result exported", "result_json" in result.export_paths)
        check("Coverage JSON exported", "coverage_json" in result.export_paths)
        check("Decisions JSON exported", "decisions_json" in result.export_paths)
        check("Logs JSON exported", "logs_json" in result.export_paths)
        check("Summary MD exported", "summary_md" in result.export_paths)
        check("Excel result exported", "result_excel" in result.export_paths)

    # 7b. Artifact files exist
    if result.export_paths:
        all_exist = all(Path(p).exists() for p in result.export_paths.values())
        check("All artifact files exist on disk", all_exist)

    # 8. Logs
    check("Logs recorded", len(result.logs) > 0)
    has_info = any(e.get("level") == "INFO" for e in result.logs)
    check("Logs contain INFO entries", has_info)

    # 9. Module timings
    check("Module timings recorded", bool(result.execution.module_timings))
    if result.execution.module_timings:
        main_module_time = result.execution.module_timings.get("pipeline_v2", 0.0)
        check("Pipeline module timed", main_module_time > 0)

    # Summary
    print()
    print("=" * 60)
    final_status = "✅ RC1 BACKEND PASSED" if tests_passed == tests_total else f"❌ RC1 BACKEND FAILED ({tests_passed}/{tests_total})"
    print(f"  {final_status}")
    print(f"  Tests: {tests_passed}/{tests_total} passed")
    print("=" * 60)

    if tests_passed != tests_total:
        sys.exit(1)


if __name__ == "__main__":
    main()
