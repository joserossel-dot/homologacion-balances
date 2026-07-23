#!/usr/bin/env python3
"""Inspect PDFs in a folder and save structural metadata to JSON.

Usage:
    python3 inspect_pdf.py <folder>
    python3 inspect_pdf.py <single.pdf>
"""

import json
import os
import re
import sys

import pdfplumber


# ---------------------------------------------------------------------------
# Account-code pattern constants (mirrors parser_universal.py)
# ---------------------------------------------------------------------------
PATRON_GUION = re.compile(r"\d+(-\d+){2,}")
PATRON_PUNTO = re.compile(r"\d+(\.\d+){2,}")
PATRON_COMPACTO = re.compile(r"\d{6,10}")
PATRON_CODIGO_LINEA = re.compile(
    r"^\s*(\d+(?:[-.]\d+){2,}|\d{6,10})\s+"
)
PATRON_RUT = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}[-][\dkK])\b")
PATRON_PERIODO = re.compile(
    r"(?:desde|from|del?)\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}"
    r"\s*(?:hasta|to|al|a)\s+\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}",
    re.IGNORECASE,
)
PATRON_TOTAL = re.compile(
    r"^(total(es)?|sub-?total(es)?|sumas?\s?iguales?|resultado)\b",
    re.IGNORECASE,
)

# Accounting header terms to count (accent-insensitive)
ACCOUNTING_HEADERS = [
    ("activo", re.compile(r"\bactivo\b", re.IGNORECASE)),
    ("pasivo", re.compile(r"\bpasivo\b", re.IGNORECASE)),
    ("patrimonio", re.compile(r"\bpatrimonio\b", re.IGNORECASE)),
    ("débito", re.compile(r"\bd[eé]bito\b", re.IGNORECASE)),
    ("crédito", re.compile(r"\bcr[eé]dito\b", re.IGNORECASE)),
    ("saldo", re.compile(r"\bsaldo\b", re.IGNORECASE)),
    ("resultado", re.compile(r"\bresultado\b", re.IGNORECASE)),
]


def find_pdfs(root: str) -> list[str]:
    if os.path.isfile(root) and root.lower().endswith(".pdf"):
        return [root]
    pdfs = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                pdfs.append(os.path.join(dirpath, fn))
    return sorted(pdfs)


def page_orientation(page) -> str:
    w, h = page.width, page.height
    if abs(w - h) < 2:
        return "square"
    return "landscape" if w > h else "portrait"


def page_size_str(page) -> str:
    return f"{page.width:.1f} x {page.height:.1f}"


def all_text(pdf, pages) -> str:
    lines = []
    for page in pages:
        t = page.extract_text()
        if t:
            lines.append(t)
    return "\n".join(lines)


def detect_account_code_pattern(text: str) -> str | None:
    hits = {"guion": 0, "punto": 0, "compacto": 0}
    for line in text.splitlines():
        line = line.strip()
        if PATRON_GUION.search(line):
            hits["guion"] += 1
        if PATRON_PUNTO.search(line):
            hits["punto"] += 1
        if PATRON_COMPACTO.match(line.split()[0] if line else ""):
            hits["compacto"] += 1
    total = sum(hits.values())
    if total == 0:
        return None
    return max(hits, key=hits.get)


def extract_headers(page, text: str) -> list[str]:
    """Return non-data lines from the top of the first page."""
    lines = text.splitlines()
    headers = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            headers.append(stripped)
            continue
        if PATRON_CODIGO_LINEA.match(stripped):
            break
        if PATRON_TOTAL.match(stripped):
            break
        headers.append(stripped)
    return headers


def count_numeric_columns(text: str) -> int:
    """Estimate the maximum number of numeric columns in any data line."""
    max_cols = 0
    for line in text.splitlines():
        stripped = line.strip()
        if PATRON_CODIGO_LINEA.match(stripped):
            parts = stripped.split()
            nums = sum(1 for p in parts[1:] if re.match(r"^-?[\d,.]+$", p))
            max_cols = max(max_cols, nums)
    return max_cols


# ---------------------------------------------------------------------------
# New structural-metric helpers
# ---------------------------------------------------------------------------


def extract_table_details(pages) -> list[dict]:
    details = []
    for page in pages:
        for t in page.find_tables():
            details.append({
                "page": page.page_number,
                "rows": len(t.rows),
                "cols": len(t.columns),
            })
    return details


def extract_numeric_x_coordinates(pages) -> list[float]:
    coords = []
    for page in pages:
        for w in page.extract_words():
            if re.match(r"^-?[\d,.]+$", w["text"]):
                coords.append(w["x0"])
    return coords


def analyze_numeric_columns(x_coords: list[float], tolerance: float = 5.0) -> dict:
    if not x_coords:
        return {"average_position": None, "distinct_alignments": 0}
    avg = sum(x_coords) / len(x_coords)
    sorted_x = sorted(set(x_coords))
    clusters = 1
    for i in range(1, len(sorted_x)):
        if sorted_x[i] - sorted_x[i - 1] > tolerance:
            clusters += 1
    return {"average_position": round(avg, 1), "distinct_alignments": clusters}


def count_accounting_headers(text: str) -> dict:
    counts = {}
    for label, pattern in ACCOUNTING_HEADERS:
        counts[label] = len(pattern.findall(text))
    return counts


def analyze_account_codes(text: str, pattern_type: str | None) -> dict:
    if pattern_type is None:
        return {
            "detected_pattern": None,
            "average_length": None,
            "separator": None,
            "total_matches": 0,
        }

    sep_map = {"guion": "-", "punto": ".", "compacto": None}
    pat_map = {"guion": PATRON_GUION, "punto": PATRON_PUNTO}
    sep = sep_map.get(pattern_type)
    codes = []

    if pattern_type == "compacto":
        for line in text.splitlines():
            first = line.strip().split()[0] if line.strip() else ""
            m = PATRON_COMPACTO.match(first)
            if m:
                codes.append(m.group())
    else:
        pat = pat_map[pattern_type]
        for line in text.splitlines():
            for m in pat.finditer(line):
                codes.append(m.group())

    total = len(codes)
    avg_len = round(sum(len(c) for c in codes) / total, 1) if total else None
    return {
        "detected_pattern": pattern_type,
        "average_length": avg_len,
        "separator": sep,
        "total_matches": total,
    }


def inspect_pdf(path: str) -> dict | None:
    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages
            total_pages = len(pages)

            if total_pages == 0:
                return {
                    "filename": path,
                    "page_count": 0,
                    "error": "empty PDF",
                }

            ori = page_orientation(pages[0])
            size = page_size_str(pages[0])
            text = all_text(pdf, pages)
            has_text = bool(text.strip())

            total_tables = sum(len(p.find_tables()) for p in pages)
            total_images = sum(len(p.images) for p in pages)

            first_20 = (pages[0].extract_text() or "").splitlines()[:20]
            headers = extract_headers(pages[0], pages[0].extract_text() or "")
            code_pat = detect_account_code_pattern(text)
            num_cols = count_numeric_columns(text)

            # --- New structural metrics (appended, existing fields unchanged) ---
            table_details = extract_table_details(pages)
            x_coords = extract_numeric_x_coordinates(pages)
            num_col_analysis = analyze_numeric_columns(x_coords)
            header_counts = count_accounting_headers(text)
            code_analysis = analyze_account_codes(text, code_pat)

            # Normalise headers: None if empty list
            first_headers = headers if headers and any(h.strip() for h in headers) else None

            return {
                "filename": path,
                "page_count": total_pages,
                "page_orientation": ori,
                "page_size": size,
                "has_selectable_text": has_text,
                "tables_detected": total_tables,
                "images_detected": total_images,
                "first_headers_found": first_headers,
                "account_code_pattern": code_pat,
                "numeric_columns_detected": num_cols,
                "first_20_lines": first_20,
                # New fields
                "table_details": table_details,
                "numeric_x_coordinates": x_coords,
                "numeric_column_analysis": num_col_analysis,
                "accounting_header_counts": header_counts,
                "account_code_analysis": code_analysis,
            }
    except Exception as exc:
        return {
            "filename": path,
            "page_count": 0,
            "error": str(exc),
        }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 inspect_pdf.py <folder-or-pdf>", file=sys.stderr)
        sys.exit(1)

    target = sys.argv[1]
    if not os.path.exists(target):
        print(f"error: {target} not found", file=sys.stderr)
        sys.exit(1)

    pdfs = find_pdfs(target)
    if not pdfs:
        print("error: no PDF files found", file=sys.stderr)
        sys.exit(1)

    results = []
    for i, path in enumerate(pdfs):
        print(f"[{i + 1}/{len(pdfs)}] {path}", file=sys.stderr)
        rec = inspect_pdf(path)
        results.append(rec)

    out_path = "inspection_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone — {len(results)} PDFs written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
