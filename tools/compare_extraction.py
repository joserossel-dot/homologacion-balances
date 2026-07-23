#!/usr/bin/env python3
"""Compare extracted AccountingRecord list against the original PDF.

Scans PDF tables independently (without calling any extractor),
cross-references against the extraction JSON, and reports:

  - every extracted record (page, code, name)
  - basic quality counts
  - account-code gaps in the extraction
  - rows present in the PDF but missing from the extraction

Usage:
    python3 tools/compare_extraction.py <pdf> <extraction.json>
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.accounting_record import AccountingRecord


# ---------------------------------------------------------------------------
# Account-code patterns (mirrors table_extractor)
# ---------------------------------------------------------------------------
PAT_GUION = re.compile(r"(\d+(?:-\d+){2,})")
PAT_PUNTO = re.compile(r"(\d+(?:\.\d+){2,})")
PAT_COMPACTO = re.compile(r"(\d{6,10})")


# ---------------------------------------------------------------------------
# Row-filtering keywords (mirrors table_extractor)
# ---------------------------------------------------------------------------
KW_HEADER = {
    "cuenta", "cta.", "cta", "codigo", "cod.",
    "contable", "descripcion", "descripción", "nombre", "detalle", "glosa",
    "debe", "debito", "débito", "débitos", "debitos",
    "haber", "credito", "crédito", "créditos", "creditos",
    "deudor", "saldo deudor", "acreedor", "saldo acreedor",
}
KW_TOTAL = {
    "total", "subtotal", "sub-total", "suma", "sumas",
    "utilidad del ejercicio", "totales iguales",
    "totales", "utilidad (perdida)",
    "utilidad", "subtotales", "total general",
    "resultado", "pérdidas / ganancias", "utilidad (perdida)",
    "resultado del ejercicio", "utilidad/perdida",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PdfRow:
    page: int
    table: int
    row: int
    cells: list[str]
    code: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_code(text: str) -> str | None:
    for pat in (PAT_GUION, PAT_PUNTO, PAT_COMPACTO):
        m = pat.search(text)
        if m:
            return m.group(1)
    return None


def _is_header_row(cells: list[str]) -> bool:
    cleaned = [c.strip().lower() for c in cells if c and c.strip()]
    if len(cleaned) < 2:
        return False
    matches = sum(1 for w in cleaned if any(kw in w for kw in KW_HEADER))
    return matches >= 2


def _is_total_row(cells: list[str]) -> bool:
    first = cells[0].strip().lower() if cells and cells[0] else ""
    return any(kw in first for kw in KW_TOTAL)


def _is_empty_row(cells: list[str]) -> bool:
    return all(not c or c.strip() in ("", "None") for c in cells)


# ---------------------------------------------------------------------------
# PDF scanner (naive, independent of any extractor)
# ---------------------------------------------------------------------------

def scan_pdf(pdf_path: str) -> list[PdfRow]:
    """Scan PDF tables and return rows that look like account data."""
    pdf_rows: list[PdfRow] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table_idx, table in enumerate(tables):
                for row_idx, row in enumerate(table):
                    cells = [str(c) if c is not None else "" for c in row]

                    if _is_empty_row(cells):
                        continue
                    if _is_header_row(cells):
                        continue
                    if _is_total_row(cells):
                        continue

                    code = ""
                    for cell in cells:
                        found = extract_code(cell)
                        if found:
                            code = found
                            break

                    pdf_rows.append(PdfRow(
                        page=page_idx + 1,
                        table=table_idx,
                        row=row_idx,
                        cells=cells,
                        code=code,
                    ))
    return pdf_rows


# ---------------------------------------------------------------------------
# Load extraction
# ---------------------------------------------------------------------------

def load_extraction(path: str) -> list[AccountingRecord]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("error: extraction JSON must be a list", file=sys.stderr)
        sys.exit(1)
    return [AccountingRecord.from_dict(item) for item in data]


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare(pdf_rows: list[PdfRow],
            records: list[AccountingRecord]) -> dict[str, Any]:
    """Compare PDF rows against extracted records.

    Matching is done primarily by account code (since most extractors
    do not populate source_table / source_row).  Rows found in the PDF
    whose code does not appear in the extraction are flagged.
    """

    # Build set of codes that were actually extracted
    extracted_codes: set[str] = set()
    for rec in records:
        if rec.account_code:
            extracted_codes.add(rec.account_code)

    # Also build position index for extractors that DO populate position
    extracted_positions: set[tuple[int, int, int]] = set()
    for rec in records:
        extracted_positions.add((rec.source_page, rec.source_table, rec.source_row))

    missing_by_code: list[PdfRow] = []
    codes_only_in_pdf: set[str] = set()

    for pr in pdf_rows:
        if not pr.code:
            continue
        # Check code match
        if pr.code in extracted_codes:
            continue
        # Check position match (fallback)
        if (pr.page, pr.table, pr.row) in extracted_positions:
            continue
        codes_only_in_pdf.add(pr.code)
        missing_by_code.append(pr)

    return {
        "missing_by_code": missing_by_code,
        "codes_only_in_pdf": sorted(codes_only_in_pdf),
    }


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def _code_sort_key(code: str) -> tuple[int, ...]:
    for sep in ("-", ".", " "):
        if sep in code:
            parts = code.split(sep)
            try:
                return tuple(int(p) for p in parts)
            except ValueError:
                continue
    try:
        return (int(code),)
    except ValueError:
        return (0,)


def _pad(parts: list[str], idx: int, value: int) -> str:
    """Format *value* with the same width as *parts[idx]*."""
    width = len(parts[idx])
    return str(value).zfill(width)


def detect_code_gaps(codes: list[str]) -> list[str]:
    """Report gaps between consecutive account codes."""
    valid = sorted(set(c for c in codes if c), key=_code_sort_key)
    if len(valid) < 2:
        return []

    gaps: list[str] = []
    for i in range(len(valid) - 1):
        cur = valid[i]
        nxt = valid[i + 1]

        for sep in ("-", ".", " "):
            if sep not in cur or sep not in nxt:
                continue
            cur_parts = cur.split(sep)
            nxt_parts = nxt.split(sep)
            if len(cur_parts) != len(nxt_parts) or cur_parts[:-1] != nxt_parts[:-1]:
                continue
            try:
                cur_last = int(cur_parts[-1])
                nxt_last = int(nxt_parts[-1])
                if nxt_last - cur_last > 1:
                    full_parts = cur_parts[:]
                    missing = []
                    for n in range(cur_last + 1, nxt_last):
                        full_parts[-1] = _pad(cur_parts, -1, n)
                        missing.append(sep.join(full_parts))
                    gaps.append(f"{cur} \u2192 {nxt}: missing {', '.join(missing)}")
            except ValueError:
                continue
            break
        else:
            # No known hierarchical separator — treat as flat number
            try:
                cv = int(cur)
                nv = int(nxt)
                if nv - cv > 1:
                    missing = [str(n).zfill(len(cur)) for n in range(cv + 1, nv)]
                    gaps.append(f"{cur} \u2192 {nxt}: missing {', '.join(missing)}")
            except ValueError:
                pass

    return gaps


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(pdf_path: str,
                    records: list[AccountingRecord],
                    pdf_rows: list[PdfRow],
                    output_path: str) -> None:
    pdf_name = Path(pdf_path).name
    total = len(records)
    codes = [r.account_code for r in records if r.account_code]
    names = [r.account_name for r in records if r.account_name]

    code_counts = Counter(codes)
    duplicated = sum(1 for c, n in code_counts.items() if n > 1)
    no_code = sum(1 for r in records if not r.account_code)
    no_name = sum(1 for r in records if not r.account_name)

    gaps = detect_code_gaps(codes)
    comparison = compare(pdf_rows, records)

    lines: list[str] = [
        "# Extraction Comparison Report",
        "",
        f"**PDF:** {pdf_name}",
        f"**Records extracted:** {total}",
        "",
        "## Summary",
        "",
        f"- **Extracted records:** {total}",
        f"- **Duplicated records (by code):** {duplicated}",
        f"- **Records without code:** {no_code}",
        f"- **Records without name:** {no_name}",
        "",
    ]

    if gaps:
        lines += [
            "## Suspicious Code Gaps",
            "",
        ]
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    missing = comparison["missing_by_code"]
    if missing:
        lines += [
            f"## Rows in PDF Not Found in Extraction ({len(missing)})",
            "",
            "| Page | Table | Row | Code | Raw |",
            "|------|-------|-----|------|-----|",
        ]
        for pr in missing[:50]:
            raw = " ".join(pr.cells[:3])
            if len(raw) > 60:
                raw = raw[:57] + "..."
            lines.append(f"| {pr.page} | {pr.table} | {pr.row} | {pr.code or '-'} | {raw} |")
        if len(missing) > 50:
            lines.append(f"| ... | ... | ... | ... | *{len(missing) - 50} more rows* |")
        lines.append("")

    lines += [
        "## All Extracted Records",
        "",
        "| # | Page | Code | Name |",
        "|---|------|------|------|",
    ]
    for i, rec in enumerate(records, 1):
        code = rec.account_code or "-"
        name = rec.account_name or "-"
        lines.append(f"| {i} | {rec.source_page} | {code} | {name} |")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python3 tools/compare_extraction.py <pdf> <extraction.json>",
              file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    extraction_path = sys.argv[2]

    if not Path(pdf_path).exists():
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    if not Path(extraction_path).exists():
        print(f"error: extraction file not found: {extraction_path}", file=sys.stderr)
        sys.exit(1)

    records = load_extraction(extraction_path)
    print(f"Loaded {len(records)} extracted records", file=sys.stderr)

    pdf_rows = scan_pdf(pdf_path)
    print(f"Scanned {len(pdf_rows)} potential account rows from PDF", file=sys.stderr)

    output_path = "comparison_report.md"
    generate_report(pdf_path, records, pdf_rows, output_path)
    print(f"Report written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
