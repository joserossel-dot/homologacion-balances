#!/usr/bin/env python3
"""Benchmark framework for evaluating accounting-balance extractors.

Accepts any extractor output as JSON (AccountingRecord[]) and produces:
  - benchmark_result.json  (machine-readable)
  - benchmark_report.md    (human-readable)

Usage:
    python3 tools/benchmark.py <pdf> <extraction.json> <expected_accounts> \\
        [--extractor NAME] [--time SECONDS] [--threshold PCT]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.accounting_record import AccountingRecord


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class QualityMetrics:
    duplicate_codes: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)
    empty_codes: int = 0
    empty_names: int = 0
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    records_with_warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_report(self) -> dict[str, Any]:
        return {
            "duplicate_account_codes": {
                "count": len(self.duplicate_codes),
                "codes": self.duplicate_codes,
            },
            "duplicate_account_names": {
                "count": len(self.duplicate_names),
                "names": self.duplicate_names,
            },
            "empty_account_codes": self.empty_codes,
            "empty_account_names": self.empty_names,
            "records_with_validation_errors": {
                "count": len(self.validation_errors),
                "details": self.validation_errors,
            },
            "records_with_warnings": {
                "count": len(self.records_with_warnings),
                "details": self.records_with_warnings,
            },
        }


@dataclass
class BenchmarkResult:
    general: dict[str, Any]
    extraction: dict[str, Any]
    quality: QualityMetrics
    statistics: dict[str, float]
    passed: bool
    extraction_rate: float
    threshold: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_pdf_page_count(pdf_path: str) -> int:
    if pdfplumber is None:
        return 0
    path = Path(pdf_path)
    if not path.exists():
        return 0
    with pdfplumber.open(str(path)) as pdf:
        return len(pdf.pages)


def load_extraction(path: str) -> list[AccountingRecord]:
    raw_path = Path(path)
    if not raw_path.exists():
        print(f"error: extraction file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("error: extraction JSON must be a list of records", file=sys.stderr)
        sys.exit(1)

    records = []
    for item in data:
        rec = AccountingRecord.from_dict(item)
        records.append(rec)
    return records


def analyze_quality(records: list[AccountingRecord]) -> QualityMetrics:
    code_counts: Counter[str] = Counter()
    name_counts: Counter[str] = Counter()
    validation_errors: list[dict[str, Any]] = []
    records_with_warnings: list[dict[str, Any]] = []
    empty_codes = 0
    empty_names = 0

    for rec in records:
        # Track empty fields
        if not rec.account_code:
            empty_codes += 1
        else:
            code_counts[rec.account_code] += 1

        if not rec.account_name:
            empty_names += 1
        else:
            name_counts[rec.account_name] += 1

        # Validation
        errs = rec.validate()
        if errs:
            validation_errors.append({
                "record_id": rec.record_id,
                "source_row": rec.source_row,
                "source_page": rec.source_page,
                "account_code": rec.account_code,
                "account_name": rec.account_name,
                "errors": errs,
            })

        # Warnings
        if rec.warnings:
            records_with_warnings.append({
                "record_id": rec.record_id,
                "source_row": rec.source_row,
                "source_page": rec.source_page,
                "account_code": rec.account_code,
                "account_name": rec.account_name,
                "warnings": rec.warnings,
            })

    # Duplicate codes (non-empty, appearing more than once)
    duplicate_codes = [code for code, count in code_counts.items() if count > 1]

    # Duplicate names (non-empty, appearing more than once)
    duplicate_names = [name for name, count in name_counts.items() if count > 1]

    return QualityMetrics(
        duplicate_codes=duplicate_codes,
        duplicate_names=duplicate_names,
        empty_codes=empty_codes,
        empty_names=empty_names,
        validation_errors=validation_errors,
        records_with_warnings=records_with_warnings,
    )


def compute_statistics(records: list[AccountingRecord]) -> dict[str, float]:
    debit_total = 0.0
    credit_total = 0.0
    balance_debit_total = 0.0
    balance_credit_total = 0.0

    for rec in records:
        if rec.debit is not None:
            debit_total += rec.debit
        if rec.credit is not None:
            credit_total += rec.credit
        if rec.balance_debit is not None:
            balance_debit_total += rec.balance_debit
        if rec.balance_credit is not None:
            balance_credit_total += rec.balance_credit

    return {
        "debit_total": round(debit_total, 2),
        "credit_total": round(credit_total, 2),
        "balance_debit_total": round(balance_debit_total, 2),
        "balance_credit_total": round(balance_credit_total, 2),
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run_benchmark(
    pdf_path: str,
    extraction_path: str,
    expected_accounts: int,
    extractor_name: str = "unknown",
    execution_time: float = 0.0,
    threshold: float = 90.0,
) -> BenchmarkResult:
    pdf_name = Path(pdf_path).name
    pages = get_pdf_page_count(pdf_path)
    records = load_extraction(extraction_path)

    total_extracted = len(records)
    extraction_rate = (total_extracted / expected_accounts * 100) if expected_accounts > 0 else 0.0
    passed = extraction_rate >= threshold

    quality = analyze_quality(records)
    stats = compute_statistics(records)

    general = {
        "pdf_name": pdf_name,
        "extractor": extractor_name,
        "execution_time_seconds": round(execution_time, 3),
        "pages": pages,
    }

    extraction = {
        "expected_accounts": expected_accounts,
        "extracted_accounts": total_extracted,
        "extraction_rate_percent": round(extraction_rate, 2),
    }

    return BenchmarkResult(
        general=general,
        extraction=extraction,
        quality=quality,
        statistics=stats,
        passed=passed,
        extraction_rate=round(extraction_rate, 2),
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Output generators
# ---------------------------------------------------------------------------

def generate_json_report(result: BenchmarkResult, output_path: str) -> None:
    quality_dict = result.quality.to_report()

    data = {
        "benchmark_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "passed": result.passed,
        "threshold_percent": result.threshold,
        "extraction_rate_percent": result.extraction_rate,
        "general": result.general,
        "extraction": result.extraction,
        "quality": quality_dict,
        "statistics": result.statistics,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_markdown_report(result: BenchmarkResult, output_path: str) -> None:
    g = result.general
    e = result.extraction
    q = result.quality
    s = result.statistics
    qd = q.to_report()

    lines = [
        "# Benchmark Report",
        "",
        "## General",
        f"- **PDF name:** {g['pdf_name']}",
        f"- **Extractor:** {g['extractor']}",
        f"- **Execution time:** {g['execution_time_seconds']}s",
        f"- **Pages:** {g['pages']}",
        "",
        "## Extraction",
        f"- **Expected accounts:** {e['expected_accounts']}",
        f"- **Extracted accounts:** {e['extracted_accounts']}",
        f"- **Extraction rate:** {e['extraction_rate_percent']}%",
        "",
        "## Quality",
        f"- **Duplicate account codes:** {qd['duplicate_account_codes']['count']}",
    ]

    if qd["duplicate_account_codes"]["codes"]:
        lines.append(f"  - Codes: {', '.join(qd['duplicate_account_codes']['codes'])}")

    lines += [
        f"- **Duplicate account names:** {qd['duplicate_account_names']['count']}",
    ]

    if qd["duplicate_account_names"]["names"]:
        lines.append(f"  - Names: {', '.join(qd['duplicate_account_names']['names'][:10])}{'...' if len(qd['duplicate_account_names']['names']) > 10 else ''}")

    lines += [
        f"- **Empty account codes:** {qd['empty_account_codes']}",
        f"- **Empty account names:** {qd['empty_account_names']}",
        f"- **Records with validation errors:** {qd['records_with_validation_errors']['count']}",
        f"- **Records with warnings:** {qd['records_with_warnings']['count']}",
        "",
        "## Statistics",
        f"- **Debit total:** {s['debit_total']:,.2f}",
        f"- **Credit total:** {s['credit_total']:,.2f}",
        f"- **Balance debit total:** {s['balance_debit_total']:,.2f}",
        f"- **Balance credit total:** {s['balance_credit_total']:,.2f}",
        "",
    ]

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def print_summary(result: BenchmarkResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(status)
    print(f"Extraction Rate : {result.extraction_rate}%")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark an extractor against expected accounts.",
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("extraction", help="Path to the extraction JSON file")
    parser.add_argument("expected", type=int, help="Expected number of accounts")
    parser.add_argument("--extractor", default="unknown", help="Extractor name")
    parser.add_argument("--time", type=float, default=0.0, help="Execution time in seconds")
    parser.add_argument("--threshold", type=float, default=90.0,
                        help="Pass threshold %% (default 90.0)")
    parser.add_argument("--out-dir", default=".",
                        help="Output directory (default: current dir)")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    result = run_benchmark(
        pdf_path=args.pdf,
        extraction_path=args.extraction,
        expected_accounts=args.expected,
        extractor_name=args.extractor,
        execution_time=args.time,
        threshold=args.threshold,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "benchmark_result.json"
    md_path = out_dir / "benchmark_report.md"

    generate_json_report(result, str(json_path))
    generate_markdown_report(result, str(md_path))

    print(f"JSON report  → {json_path}", file=sys.stderr)
    print(f"Markdown report → {md_path}", file=sys.stderr)
    print(file=sys.stderr)
    print_summary(result)


if __name__ == "__main__":
    main()
