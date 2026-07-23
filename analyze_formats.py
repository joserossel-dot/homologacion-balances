#!/usr/bin/env python3
"""Analyze inspection_results.json and group PDFs by structural similarity.

Produces:
    format_analysis.md — human-readable report
    format_groups.json — machine-readable group definitions

Usage:
    python3 analyze_formats.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Standard page sizes in points (width x height, portrait order)
STANDARD_SIZES = {
    (612.0, 792.0): "Letter",
    (595.0, 842.0): "A4",
    (612.0, 1008.0): "Legal",
    (842.0, 1191.0): "A3",
    (396.0, 612.0): "Half-Letter",
    (612.0, 936.0): "Folio",
}

# Patterns to strip from headers for signature generation
PAT_RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}[-][\dkK]\b")
PAT_DATE = re.compile(r"\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{1,4}")
PAT_NUM = re.compile(r"\d+")


def _round_size(w: float, h: float) -> tuple[float, float]:
    """Round to nearest 10 pt so tiny rounding differences collapse."""
    rw = round(w / 10) * 10
    rh = round(h / 10) * 10
    # Ensure portrait ordering for matching
    return (rw, rh)


def classify_page_size(w: float, h: float) -> str:
    rw, rh = _round_size(w, h)
    key = (rw, rh)
    if key in STANDARD_SIZES:
        return STANDARD_SIZES[key]
    key = (rh, rw)  # try swapped (landscape version)
    if key in STANDARD_SIZES:
        return f"{STANDARD_SIZES[key]} (landscape)"
    return f"{rw:.0f}x{rh:.0f} custom"


def bucket_value(value: int, thresholds: list[int]) -> str:
    for i, t in enumerate(thresholds):
        if value <= t:
            if i == 0:
                return f"0-{t}" if t != 0 else "0"
            prev = thresholds[i - 1]
            return f"{prev + 1}-{t}" if prev + 1 < t else str(t)
    return f"{thresholds[-1] + 1}+"


def normalize_headers(headers: list[str] | None, max_lines: int = 4) -> str:
    if not headers:
        return ""
    cleaned = []
    for line in headers[:max_lines]:
        s = line.strip().lower()
        s = PAT_RUT.sub("__RUT__", s)
        s = PAT_DATE.sub("__DATE__", s)
        s = PAT_NUM.sub("__N__", s)
        s = re.sub(r"[^a-záéíóúñü_\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            cleaned.append(s)
    return " | ".join(cleaned)


def header_signature_short(sig: str) -> str:
    """Short descriptive label from a header signature."""
    if not sig:
        return "none"
    parts = sig.split(" | ")
    labels = []
    for p in parts[:3]:
        words = p.split()
        if words:
            labels.append(words[0] if len(words) <= 3 else f"{words[0]}...")
    return " / ".join(labels) if labels else "unknown"


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

TABLE_BUCKETS = [0, 5]
IMAGE_BUCKETS = [0, 5]
NUM_COL_BUCKETS = [0, 2, 4]


def make_fingerprint(rec: dict) -> tuple:
    """Deterministic structural fingerprint for a document record."""
    ori = rec.get("page_orientation", "unknown")
    size_label = classify_page_size(
        *map(float, rec.get("page_size", "0x0").split(" x "))
    ) if rec.get("page_size") else "unknown"
    text = rec.get("has_selectable_text", False)
    tables = bucket_value(rec.get("tables_detected", 0), TABLE_BUCKETS)
    images = bucket_value(rec.get("images_detected", 0), IMAGE_BUCKETS)
    header_sig = normalize_headers(rec.get("first_headers_found"))
    code_pat = rec.get("account_code_pattern") or "none"
    num_cols = bucket_value(rec.get("numeric_columns_detected", 0), NUM_COL_BUCKETS)
    return (ori, size_label, text, tables, images, header_sig, code_pat, num_cols)


# ---------------------------------------------------------------------------
# Group building
# ---------------------------------------------------------------------------

def describe_group(records: list[dict]) -> dict:
    """Common features shared by all records in the group."""
    common = {
        "text": _common(records, "has_selectable_text"),
        "tables": _common_bucket(records, "tables_detected", TABLE_BUCKETS),
        "images": _common_bucket(records, "images_detected", IMAGE_BUCKETS),
        "orientation": _common(records, "page_orientation"),
        "page_size": _common(records, "page_size"),
        "code_pattern": _common(records, "account_code_pattern"),
        "numeric_columns": _common_bucket(records, "numeric_columns_detected", NUM_COL_BUCKETS),
        "header_signature": normalize_headers(_first_headers(records[0])),
    }
    return {k: v for k, v in common.items() if v is not None}


def _common(records: list[dict], field: str):
    vals = {r.get(field) for r in records if field in r}
    if len(vals) == 1:
        return next(iter(vals))
    return None


def _common_bucket(records: list[dict], field: str, buckets: list[int]):
    vals = {bucket_value(r.get(field, 0), buckets) for r in records}
    if len(vals) == 1:
        return next(iter(vals))
    return None


def _first_headers(rec: dict) -> list[str] | None:
    return rec.get("first_headers_found")


def load_results(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [r for r in data if "error" not in r]


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def write_markdown(groups: list[dict], total: int, output: str):
    lines = []
    lines.append("# Format Analysis Report")
    lines.append("")
    lines.append(f"- **Total PDFs analyzed:** {total}")
    lines.append(f"- **Unique structural patterns found:** {len(groups)}")
    lines.append("")

    for g in groups:
        gid = g["id"]
        docs = g["documents"]
        feat = g["common_features"]
        header_label = header_signature_short(feat.get("header_signature", ""))

        lines.append(f"## {gid}")
        lines.append("")
        lines.append(f"- **Documents:** {len(docs)}")
        lines.append(f"- **Orientation:** {feat.get('orientation', 'mixed')}")
        lines.append(f"- **Page size:** {feat.get('page_size', 'mixed')}")
        lines.append(f"- **Selectable text:** {feat.get('text', 'mixed')}")
        lines.append(f"- **Tables:** {feat.get('tables', 'mixed')}")
        lines.append(f"- **Images:** {feat.get('images', 'mixed')}")
        lines.append(f"- **Account code pattern:** {feat.get('code_pattern', 'mixed')}")
        lines.append(f"- **Numeric columns:** {feat.get('numeric_columns', 'mixed')}")
        lines.append(f"- **Header signature:** {header_label}")
        lines.append("")
        lines.append("### Documents")
        lines.append("")
        for d in docs:
            lines.append(f"- `{d}`")
        lines.append("")

    # Differences between patterns
    if len(groups) >= 2:
        lines.append("## Main Differences Between Patterns")
        lines.append("")
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                ga = groups[i]
                gb = groups[j]
                diffs = _diff_features(ga["common_features"], gb["common_features"])
                if diffs:
                    lines.append(f"- **{ga['id']} vs {gb['id']}:** {', '.join(diffs)}")
                else:
                    lines.append(f"- **{ga['id']} vs {gb['id']}:** no structural difference (possible sub-patterns)")
                lines.append("")

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _diff_features(a: dict, b: dict) -> list[str]:
    diffs = []
    for key in a:
        va = a[key]
        vb = b.get(key)
        if va is not None and vb is not None and va != vb:
            label = key.replace("_", " ").title()
            diffs.append(f"{label}: {va} vs {vb}")
    return diffs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    input_path = "inspection_results.json"
    if not os.path.exists(input_path):
        print(f"error: {input_path} not found — run inspect_pdf.py first", file=sys.stderr)
        return

    records = load_results(input_path)
    if not records:
        print("error: no valid PDF records in inspection_results.json", file=sys.stderr)
        return

    # Build groups by fingerprint
    fp_groups = defaultdict(list)
    for rec in records:
        fp = make_fingerprint(rec)
        fp_groups[fp].append(rec)

    # Sort groups by size (largest first), then by fingerprint
    sorted_groups = sorted(fp_groups.values(), key=lambda g: (-len(g), g[0].get("filename", "")))

    groups_out = []
    for idx, group_recs in enumerate(sorted_groups, start=1):
        gid = f"G{idx:02d}"
        docs = sorted(r.get("filename", "unknown") for r in group_recs)
        feat = describe_group(group_recs)
        groups_out.append({
            "id": gid,
            "documents": docs,
            "common_features": feat,
        })

    write_markdown(groups_out, len(records), "format_analysis.md")

    json_out = []
    for g in groups_out:
        json_out.append({
            "group": g["id"],
            "documents": [str(Path(d).name) for d in g["documents"]],
            "common_features": g["common_features"],
        })

    with open("format_groups.json", "w", encoding="utf-8") as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2)

    print(f"Done — {len(records)} PDFs grouped into {len(groups_out)} patterns", file=sys.stderr)
    print(f"  → format_analysis.md", file=sys.stderr)
    print(f"  → format_groups.json", file=sys.stderr)


if __name__ == "__main__":
    main()
