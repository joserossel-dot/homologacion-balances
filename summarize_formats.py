#!/usr/bin/env python3
"""Compute structural statistics from inspection_results.json.

Produces:
    format_statistics.md — statistical summary with outlier detection

Usage:
    python3 summarize_formats.py
"""

import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path


def load(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def dist_table(counts: Counter, total: int, label: str = "Count") -> list[str]:
    lines = [f"| {label} | Documents | % |"]
    lines.append("|---|---|---|")
    for k in sorted(counts):
        v = counts[k]
        lines.append(f"| {k} | {v} | {fmt_pct(v, total)} |")
    return lines


def compute_outlier_scores(records: list[dict]) -> list[tuple[float, str, str]]:
    """Return list of (score, reason, filename) sorted descending."""
    scores: list[tuple[float, str, str]] = []
    total = len(records)

    # --- Reference values ---
    orientations = [r.get("page_orientation", "?") for r in records]
    texts = [r.get("has_selectable_text", False) for r in records]
    page_counts = [r.get("page_count", 0) for r in records]
    table_counts = [r.get("tables_detected", 0) for r in records]
    image_counts = [r.get("images_detected", 0) for r in records]
    code_pats = [r.get("account_code_pattern") or "none" for r in records]
    num_cols = [r.get("numeric_columns_detected", 0) for r in records]

    mode_ori = Counter(orientations).most_common(1)[0][0]
    mode_text = Counter(texts).most_common(1)[0][0]
    mode_code = Counter(code_pats).most_common(1)[0][0]
    median_page = statistics.median(page_counts)
    median_table = statistics.median(table_counts)
    median_img = statistics.median(image_counts)
    median_numcol = statistics.median(num_cols)

    stdev_page = statistics.pstdev(page_counts) if len(page_counts) > 1 else 0
    stdev_table = statistics.pstdev(table_counts) if len(table_counts) > 1 else 0
    stdev_img = statistics.pstdev(image_counts) if len(image_counts) > 1 else 0
    stdev_num = statistics.pstdev(num_cols) if len(num_cols) > 1 else 0

    for r in records:
        fn = r.get("filename", "unknown")
        reasons = []
        score = 0.0

        # Orientation deviation
        ori = r.get("page_orientation", "?")
        if ori != mode_ori:
            score += 2.0
            reasons.append(f"orientation={ori} (mode={mode_ori})")

        # Text deviation
        txt = r.get("has_selectable_text", False)
        if txt != mode_text:
            score += 1.5
            reasons.append(f"text={txt} (mode={mode_text})")

        # Page count z-score
        pc = r.get("page_count", 0)
        if stdev_page > 0:
            z = abs(pc - median_page) / stdev_page
            if z > 2.0:
                score += z
                reasons.append(f"pages={pc} (z={z:.1f})")

        # Table count z-score
        tc = r.get("tables_detected", 0)
        if stdev_table > 0:
            z = abs(tc - median_table) / stdev_table
            if z > 2.0:
                score += z
                reasons.append(f"tables={tc} (z={z:.1f})")

        # Image count z-score
        ic = r.get("images_detected", 0)
        if stdev_img > 0:
            z = abs(ic - median_img) / stdev_img
            if z > 2.0:
                score += z
                reasons.append(f"images={ic} (z={z:.1f})")

        # Code pattern deviation
        cp = r.get("account_code_pattern") or "none"
        if cp != mode_code:
            score += 1.5
            reasons.append(f"code_pattern={cp} (mode={mode_code})")

        # Numeric columns z-score
        nc = r.get("numeric_columns_detected", 0)
        if stdev_num > 0:
            z = abs(nc - median_numcol) / stdev_num
            if z > 2.0:
                score += z
                reasons.append(f"num_cols={nc} (z={z:.1f})")

        if score > 0:
            reason = "; ".join(reasons[:3])
            if len(reasons) > 3:
                reason += f" (+{len(reasons)-3} more)"
            scores.append((score, reason, fn))

    scores.sort(key=lambda x: -x[0])
    return scores


def write_report(records: list[dict], output: str):
    valid = [r for r in records if "error" not in r]
    total = len(valid)

    lines = []

    lines.append("# Format Statistics Report")
    lines.append("")
    lines.append(f"**Generated from:** `inspection_results.json`")
    lines.append(f"**Total records:** {len(records)} ({len(records)-total} with errors)")
    lines.append(f"**Valid PDFs analyzed:** {total}")
    lines.append("")

    # ---- 1. Selectable text vs OCR ----
    lines.append("## 1. Selectable Text vs OCR")
    lines.append("")
    with_text = sum(1 for r in valid if r.get("has_selectable_text", False))
    needs_ocr = total - with_text
    lines.append(f"- **PDFs with selectable text:** {with_text} ({fmt_pct(with_text, total)})")
    lines.append(f"- **PDFs requiring OCR:** {needs_ocr} ({fmt_pct(needs_ocr, total)})")
    lines.append("")

    # ---- 2. Table count distribution ----
    lines.append("## 2. Table Count Distribution")
    lines.append("")
    tbl_counts: Counter = Counter(r.get("tables_detected", 0) for r in valid)
    lines.extend(dist_table(tbl_counts, total))
    lines.append("")

    # ---- 3. Page count distribution ----
    lines.append("## 3. Page Count Distribution")
    lines.append("")
    pg_counts = Counter()
    for r in valid:
        pc = r.get("page_count", 0)
        if pc <= 1:
            pg_counts["1"] += 1
        elif pc <= 3:
            pg_counts["2-3"] += 1
        elif pc <= 5:
            pg_counts["4-5"] += 1
        elif pc <= 10:
            pg_counts["6-10"] += 1
        else:
            pg_counts["11+"] += 1
    lines.extend(dist_table(pg_counts, total, "Pages"))
    lines.append("")

    # ---- 4. Account code pattern distribution ----
    lines.append("## 4. Account Code Pattern Distribution")
    lines.append("")
    code_counts: Counter = Counter()
    for r in valid:
        pat = r.get("account_code_pattern")
        code_counts[pat if pat else "none"] += 1
    lines.extend(dist_table(code_counts, total, "Pattern"))
    lines.append("")

    # ---- 5. Numeric column count distribution ----
    lines.append("## 5. Numeric Column Count Distribution")
    lines.append("")
    nc_counts: Counter = Counter()
    for r in valid:
        n = r.get("numeric_columns_detected", 0)
        if n == 0:
            nc_counts["0"] += 1
        elif n <= 2:
            nc_counts["1-2"] += 1
        elif n <= 4:
            nc_counts["3-4"] += 1
        elif n <= 6:
            nc_counts["5-6"] += 1
        else:
            nc_counts["7+"] += 1
    lines.extend(dist_table(nc_counts, total, "Columns"))
    lines.append("")

    # ---- 6. Page orientation distribution ----
    lines.append("## 6. Page Orientation Distribution")
    lines.append("")
    ori_counts: Counter = Counter(r.get("page_orientation", "?") for r in valid)
    lines.extend(dist_table(ori_counts, total, "Orientation"))
    lines.append("")

    # ---- 7. Most frequent accounting headers ----
    lines.append("## 7. Most Frequent Accounting Headers")
    lines.append("")
    all_header_counts: Counter = Counter()
    for r in valid:
        hc = r.get("accounting_header_counts", {})
        for term, count in hc.items():
            if count > 0:
                all_header_counts[term] += 1
    lines.append("| Term | Documents with term | % |")
    lines.append("|---|---|---|")
    for term, count in all_header_counts.most_common():
        lines.append(f"| {term} | {count} | {fmt_pct(count, total)} |")
    lines.append("")

    # ---- 8. Outliers ----
    lines.append("## 8. Structural Outliers")
    lines.append("")
    outliers = compute_outlier_scores(valid)
    if outliers:
        lines.append("Documents whose structural features deviate significantly from the norm.")
        lines.append("")
        lines.append("| Score | Reason | Document |")
        lines.append("|---|---|---|")
        for score, reason, fn in outliers[:15]:
            lines.append(f"| {score:.1f} | {reason} | `{Path(fn).name}` |")
        if len(outliers) > 15:
            lines.append(f"| ... | ({len(outliers)-15} more) | |")
    else:
        lines.append("No significant outliers detected.")
    lines.append("")

    # ---- 9. Error summary ----
    error_records = [r for r in records if "error" in r]
    if error_records:
        lines.append("## 9. PDFs with Errors")
        lines.append("")
        for r in error_records:
            fn = r.get("filename", "unknown")
            err = r.get("error", "unknown")
            lines.append(f"- `{Path(fn).name}` — {err}")
        lines.append("")

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    input_path = "inspection_results.json"
    if not os.path.exists(input_path):
        print(f"error: {input_path} not found", file=sys.stderr)
        return

    records = load(input_path)
    write_report(records, "format_statistics.md")
    print("Done — format_statistics.md", file=sys.stderr)


if __name__ == "__main__":
    main()
