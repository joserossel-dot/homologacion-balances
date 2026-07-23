#!/usr/bin/env python3
"""Table-based account extractor for F02 PDFs.

Extracts accounting records from native PDFs with detected tables.

Usage:
    python3 table_extractor.py <pdf>
"""

import json
import re
import sys
import time
from pathlib import Path

import pdfplumber


# ---------------------------------------------------------------------------
# Header-keyword mappings  (lowercase, single words for flexibility)
# ---------------------------------------------------------------------------
KW_ACCOUNT = {"cuenta", "cta.", "cta", "codigo", "cod."}
KW_NAME = {"contable", "descripcion", "descripción", "nombre", "detalle",
           "glosa"}
KW_DEBIT = {"debe", "debito", "débito", "débitos", "debitos"}
KW_CREDIT = {"haber", "credito", "crédito", "créditos", "creditos"}
KW_BAL_DEBIT = {"deudor", "saldo deudor"}
KW_BAL_CREDIT = {"acreedor", "saldo acreedor"}
KW_TOTAL = {"total", "subtotal", "sub-total", "suma", "sumas",
            "utilidad del ejercicio", "totales iguales",
            "totales", "utilidad (perdida)",
            "utilidad", "subtotales", "total general",
            "resultado"}
KW_TOTAL_EXTRA = {"pérdidas / ganancias", "utilidad (perdida)",
                  "resultado del ejercicio", "utilidad/perdida"}

# Account-code patterns
PAT_GUION = re.compile(r"(\d+(?:-\d+){2,})")
PAT_PUNTO = re.compile(r"(\d+(?:\.\d+){2,})")
PAT_COMPACTO = re.compile(r"(\d{6,10})")


# ---------------------------------------------------------------------------
# Numeric normalisation
# ---------------------------------------------------------------------------

def _detect_thousands_sep(samples: list[str]) -> str | None:
    """Heuristic: return the thousands-separator character used in samples."""
    comma_groups = 0
    dot_groups = 0
    for s in samples:
        s = s.strip().lstrip("-")
        if "," in s:
            parts = s.split(",")
            if all(len(p) == 3 for p in parts[:-1]) and len(parts[-1]) in (0, 2, 3):
                comma_groups += 1
        if "." in s:
            parts = s.split(".")
            if all(len(p) == 3 for p in parts[:-1]) and len(parts[-1]) in (0, 2, 3):
                dot_groups += 1
    if comma_groups > dot_groups:
        return ","
    if dot_groups > comma_groups:
        return "."
    # Ambiguous — check last-separator pattern
    for s in samples:
        s = s.strip().lstrip("-")
        if "," in s and "." in s:
            return "."  # period groups, comma decimal (e.g. 1.234,56)
        if s.count(",") > 1:
            return ","
        if s.count(".") > 1:
            return "."
    return None


def normalise_number(raw: str) -> float | None:
    raw = raw.strip()
    if not raw or raw in ("-", ""):
        return None
    # Remove spaces (used as thousands separator sometimes)
    raw = raw.replace(" ", "")
    # Detect thousands separator
    sep = _detect_thousands_sep([raw])
    if sep == ",":
        raw = raw.replace(",", "")
    elif sep == ".":
        raw = raw.replace(".", "").replace(",", ".")
    else:
        # No clear separator — try both
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

def _is_header_row(row: list[str | None]) -> bool:
    cleaned = [str(c).strip().lower() for c in row if c and str(c).strip()]
    if not cleaned:
        return False
    keywords = KW_ACCOUNT | KW_NAME | KW_DEBIT | KW_CREDIT | \
               KW_BAL_DEBIT | KW_BAL_CREDIT
    matches = sum(1 for w in cleaned if any(kw in w for kw in keywords))
    return matches >= 2


def _is_total_row(row: list[str | None]) -> bool:
    first = str(row[0]).strip().lower() if row and row[0] else ""
    if any(kw in first for kw in KW_TOTAL):
        return True
    if any(kw in first for kw in KW_TOTAL_EXTRA):
        return True
    # Rows where the first cell has no numeric data AND no code pattern
    # but subsequent cells have numeric values → structural row
    return False


def _is_empty_row(row: list[str | None]) -> bool:
    return all(c is None or str(c).strip() in ("", "None") for c in row)


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

def _map_columns(header_row: list[str]) -> dict[str, int]:
    """Map header labels to 0-based column indices."""
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        label = str(cell).strip().lower() if cell else ""
        if any(kw in label for kw in KW_ACCOUNT):
            mapping.setdefault("account", idx)
        if any(kw in label for kw in KW_NAME):
            mapping.setdefault("name", idx)
        if any(kw in label for kw in KW_DEBIT):
            mapping.setdefault("debit", idx)
        if any(kw in label for kw in KW_CREDIT):
            mapping.setdefault("credit", idx)
        if any(kw in label for kw in KW_BAL_DEBIT):
            mapping.setdefault("balance_debit", idx)
        if any(kw in label for kw in KW_BAL_CREDIT):
            mapping.setdefault("balance_credit", idx)
    return mapping


def _find_header_row(table: list[list]) -> tuple[int, int]:
    """Return (header_start, header_end) row indices.

    Handles both single-row and two-row headers.
    """
    end = 0
    for i, row in enumerate(table):
        if _is_header_row(row):
            end = i + 1  # consume this row
            # Peek ahead: if next row also looks like header, include it
            if i + 1 < len(table) and _is_header_row(table[i + 1]):
                end = i + 2
            return (i, end)
    return (0, 0)


# ---------------------------------------------------------------------------
# Code / name splitting
# ---------------------------------------------------------------------------

def _extract_code_and_name(cell: str, table_code_pat: str | None
                            ) -> tuple[str | None, str]:
    """Split a combined cell like '1-01-01-01 CAJA CHICA'.

    Returns (code, name).
    """
    cell = cell.strip()
    if not cell:
        return (None, "")

    # Try known patterns
    for pat in (PAT_GUION, PAT_PUNTO, PAT_COMPACTO):
        m = pat.search(cell)
        if m:
            code = m.group(1)
            name = cell[:m.start()].strip() + " " + cell[m.end():].strip()
            name = name.strip()
            if not name:
                name = code  # code-only cell
            return (code, name)

    # Fallback: split on first space, check if first token is numeric
    parts = cell.split(maxsplit=1)
    if len(parts) == 2 and parts[0].replace(".", "").replace("-", "").isdigit():
        return (parts[0], parts[1])
    return (None, cell)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract(pdf_path: str) -> list[dict]:
    records: list[dict] = []
    pages_processed = 0
    tables_detected = 0
    rows_extracted = 0
    rows_discarded = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages_processed += 1
            tables = page.extract_tables()
            tables_detected += len(tables)

            for table in tables:
                if len(table) < 2:
                    continue

                hdr_start, hdr_end = _find_header_row(table)
                if hdr_end == 0:
                    # No header found — treat entire table as data
                    hdr_end = 0

                # Build column mapping from the last header row
                header_labels = table[hdr_end - 1] if hdr_end > 0 else []
                col_map = _map_columns(header_labels)

                # Detect if code and name are merged (same column index)
                code_col = col_map.get("account")
                name_col = col_map.get("name")
                merged = (name_col is None or name_col == code_col)
                if merged and code_col is not None:
                    name_col = code_col

                # Fallback positional mapping if header matching failed
                if not col_map:
                    ncols = len(table[0]) if table else 0
                    if ncols == 10:
                        code_col, name_col = 0, 1
                        col_map = {"debit": 2, "credit": 3,
                                   "balance_debit": 4, "balance_credit": 5}
                    else:
                        code_col, name_col = 0, 0
                        col_map = {"debit": 1, "credit": 2,
                                   "balance_debit": 3, "balance_credit": 4}

                # Detect code pattern from first data rows
                code_pat = None
                for ri in range(hdr_end, min(hdr_end + 5, len(table))):
                    row = table[ri]
                    if not row or _is_empty_row(row):
                        continue
                    val = str(row[code_col]).strip() if code_col is not None and code_col < len(row) else ""
                    if PAT_GUION.search(val):
                        code_pat = "guion"
                        break
                    if PAT_PUNTO.search(val):
                        code_pat = "punto"
                        break
                    if PAT_COMPACTO.match(val.split()[0] if val else ""):
                        code_pat = "compacto"
                        break

                # Process data rows
                for ri in range(hdr_end, len(table)):
                    row = table[ri]
                    if _is_empty_row(row):
                        rows_discarded += 1
                        continue
                    if _is_total_row(row):
                        rows_discarded += 1
                        continue

                    raw_code_name = str(row[code_col]).strip() if code_col is not None and code_col < len(row) else ""
                    if not raw_code_name:
                        rows_discarded += 1
                        continue

                    if merged:
                        code, name = _extract_code_and_name(raw_code_name, code_pat)
                    else:
                        code_cell = str(row[code_col]).strip() if code_col is not None and code_col < len(row) else ""
                        name_cell = str(row[name_col]).strip() if name_col is not None and name_col < len(row) else ""
                        code, _ = _extract_code_and_name(code_cell, code_pat)
                        name = name_cell

                    def _get(col_key: str):
                        idx = col_map.get(col_key)
                        if idx is None or idx >= len(row):
                            return None
                        return normalise_number(str(row[idx]) if row[idx] else "")

                    debit = _get("debit")
                    credit = _get("credit")
                    bal_debit = _get("balance_debit")
                    bal_credit = _get("balance_credit")

                    record = {
                        "account_code": code or "",
                        "account_name": (name or "").replace("None", "").strip(),
                        "debit": debit,
                        "credit": credit,
                        "balance_debit": bal_debit,
                        "balance_credit": bal_credit,
                        "source_page": page.page_number,
                        "confidence": 1.0,
                    }
                    records.append(record)
                    rows_extracted += 1

    metadata = {
        "pages_processed": pages_processed,
        "tables_detected": tables_detected,
        "rows_extracted": rows_extracted,
        "rows_discarded": rows_discarded,
    }
    return records, metadata


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 table_extractor.py <pdf>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not Path(path).exists():
        print(f"error: {path} not found", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    records, meta = extract(path)
    elapsed = time.time() - t0

    print(f"pages processed   : {meta['pages_processed']}", file=sys.stderr)
    print(f"tables detected   : {meta['tables_detected']}", file=sys.stderr)
    print(f"rows extracted    : {meta['rows_extracted']}", file=sys.stderr)
    print(f"rows discarded    : {meta['rows_discarded']}", file=sys.stderr)
    print(f"execution time    : {elapsed:.2f}s", file=sys.stderr)

    with open("table_extraction.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Output written to table_extraction.json ({len(records)} records)", file=sys.stderr)


if __name__ == "__main__":
    main()
