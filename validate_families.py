#!/usr/bin/env python3
"""Validate family classification from decision_engine.py.

Input:
    inspection_results.json

Output:
    validation_report.md — per-family analysis, inconsistencies, new family proposals

Usage:
    python3 validate_families.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Import the decision engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decision_engine


def load(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


# ---------------------------------------------------------------------------
# Inconsistency checks
# ---------------------------------------------------------------------------

def check_inconsistencies(records: list[dict]) -> list[dict]:
    flagged = []
    for rec in records:
        if "error" in rec:
            continue
        dec = decision_engine.decide(rec)
        family = dec["family"]
        issues = []

        has_text = rec.get("has_selectable_text", False)
        tables = rec.get("tables_detected", 0)
        code_pat = rec.get("account_code_pattern")

        if family == "F01" and has_text is True:
            issues.append("F01 assigned but has_selectable_text is true")
        if family == "F02" and tables == 0:
            issues.append("F02 assigned but tables_detected is 0")
        if family == "F02" and has_text is False:
            issues.append("F02 assigned but has_selectable_text is false")
        if family == "F03" and code_pat is None:
            issues.append("F03 assigned but account_code_pattern is null")
        if family == "F03" and has_text is False:
            issues.append("F03 assigned but has_selectable_text is false")
        if family == "F03" and tables > 0:
            issues.append("F03 assigned but tables_detected > 0")

        if issues:
            flagged.append({
                "filename": rec.get("filename", "unknown"),
                "family": family,
                "issues": issues,
                "record": rec,
            })
    return flagged


# ---------------------------------------------------------------------------
# Common characteristics per family
# ---------------------------------------------------------------------------

def family_characteristics(records: list[dict]) -> dict:
    grouped = defaultdict(list)
    for rec in records:
        if "error" in rec:
            continue
        dec = decision_engine.decide(rec)
        grouped[dec["family"]].append(rec)

    result = {}
    for family in sorted(grouped):
        group = grouped[family]

        ori = Counter(r.get("page_orientation", "?") for r in group)
        sizes = Counter(r.get("page_size", "?") for r in group)
        tables = Counter(r.get("tables_detected", 0) for r in group)
        images = Counter(r.get("images_detected", 0) for r in group)
        codes = Counter(r.get("account_code_pattern") or "none" for r in group)
        num_cols = Counter(r.get("numeric_columns_detected", 0) for r in group)
        text_true = sum(1 for r in group if r.get("has_selectable_text", False))
        header_terms: Counter = Counter()
        for r in group:
            hc = r.get("accounting_header_counts", {})
            for term, count in hc.items():
                if count > 0:
                    header_terms[term] += 1

        n = len(group)
        result[family] = {
            "count": n,
            "has_selectable_text": f"{text_true}/{n}",
            "orientation": _fmt_counter(ori, n),
            "page_size": _fmt_counter(sizes, n, top=2),
            "tables_detected": _fmt_counter(tables, n),
            "images_detected": _fmt_counter(images, n),
            "account_code_pattern": _fmt_counter(codes, n),
            "numeric_columns_detected": _fmt_counter(num_cols, n),
            "header_terms": _fmt_counter(header_terms, n),
            "first_reasons": decision_engine.decide(group[0])["reasons"],
        }
    return result


def _fmt_counter(c: Counter, total: int, top: int = 3) -> str:
    items = c.most_common(top)
    return ", ".join(f"{k}={v}" for k, v in items)


# ---------------------------------------------------------------------------
# Misclassification candidates
# ---------------------------------------------------------------------------

def find_misclassifications(records: list[dict]) -> list[dict]:
    """Flag documents where features suggest a different family."""
    flagged = []
    for rec in records:
        if "error" in rec:
            continue
        dec = decision_engine.decide(rec)
        family = dec["family"]
        suggestions = []

        has_text = rec.get("has_selectable_text", False)
        tables = rec.get("tables_detected", 0)
        code_pat = rec.get("account_code_pattern")

        # Determine expected family based on raw rules
        if has_text is False:
            expected = "F01"
        elif tables > 0:
            expected = "F02"
        elif code_pat is not None:
            expected = "F03"
        else:
            expected = "F04"

        if family != expected:
            suggestions.append(f"features suggest {expected} instead of {family}")

        # Additional heuristic: F01 with many images but also some text-like structure
        if family == "F01" and rec.get("images_detected", 0) == 0 and not has_text:
            suggestions.append("no images and no text — may be corrupt or empty")

        if suggestions:
            flagged.append({
                "filename": rec.get("filename", "unknown"),
                "family": family,
                "suggestions": suggestions,
                "expected": expected,
            })
    return flagged


# ---------------------------------------------------------------------------
# New-family proposal
# ---------------------------------------------------------------------------

def propose_new_families(records: list[dict]) -> list[dict]:
    """Look for clusters of 3+ F04 documents with a shared structural fingerprint."""
    f04 = []
    for rec in records:
        if "error" in rec:
            continue
        dec = decision_engine.decide(rec)
        if dec["family"] == "F04":
            f04.append(rec)

    if len(f04) < 3:
        return []

    # Build structural fingerprints within F04
    def fingerprint(rec: dict) -> tuple:
        has_text = rec.get("has_selectable_text", False)
        tables = rec.get("tables_detected", 0)
        code_pat = rec.get("account_code_pattern") or "none"
        ori = rec.get("page_orientation", "?")
        size = rec.get("page_size", "?")
        images = rec.get("images_detected", 0)
        num_cols = rec.get("numeric_columns_detected", 0)
        return (has_text, tables, code_pat, ori, size, images, num_cols)

    clusters = defaultdict(list)
    for rec in f04:
        clusters[fingerprint(rec)].append(rec)

    proposals = []
    for fp, group in clusters.items():
        if len(group) >= 3:
            has_text, tables, code_pat, ori, size, images, num_cols = fp
            proposals.append({
                "candidate_family": "F05 (proposed)",
                "count": len(group),
                "characteristics": {
                    "has_selectable_text": has_text,
                    "tables_detected": tables,
                    "account_code_pattern": None if code_pat == "none" else code_pat,
                    "orientation": ori,
                    "page_size": size,
                    "images_detected": images,
                    "numeric_columns_detected": num_cols,
                },
                "documents": [r.get("filename", "unknown") for r in group],
                "rationale": f"{len(group)} documents share identical structural features but do not match F01-F04 rules",
            })
    return proposals


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_report(records: list[dict], output: str):
    valid = [r for r in records if "error" not in r]
    total = len(valid)

    lines = []
    lines.append("# Family Validation Report")
    lines.append("")
    lines.append(f"**Total valid documents:** {total}")
    lines.append(f"**Documents with errors:** {len(records) - total}")
    lines.append("")

    # ---- 1. Documents grouped by family ----
    lines.append("## 1. Documents by Family")
    lines.append("")
    grouped = defaultdict(list)
    for rec in valid:
        dec = decision_engine.decide(rec)
        grouped[dec["family"]].append((rec, dec))

    for family in sorted(grouped):
        lines.append(f"### {family}")
        lines.append("")
        entries = grouped[family]
        for rec, dec in sorted(entries, key=lambda x: Path(x[0].get("filename", "")).name):
            fn = Path(rec.get("filename", "")).name
            lines.append(f"- `{fn}` — {dec['extractor']}")
        lines.append("")

    # ---- 2. Per-family analysis ----
    lines.append("## 2. Per-Family Analysis")
    lines.append("")

    chars = family_characteristics(valid)
    for family in sorted(chars):
        info = chars[family]
        lines.append(f"### {family}")
        lines.append("")
        lines.append(f"**Count:** {info['count']}")
        lines.append(f"**Confidence:** 1.0 (rule-based, deterministic)")
        lines.append(f"**Selectable text:** {info['has_selectable_text']}")
        lines.append(f"**Orientation:** {info['orientation']}")
        lines.append(f"**Page size:** {info['page_size']}")
        lines.append(f"**Tables:** {info['tables_detected']}")
        lines.append(f"**Images:** {info['images_detected']}")
        lines.append(f"**Code pattern:** {info['account_code_pattern']}")
        lines.append(f"**Numeric columns:** {info['numeric_columns_detected']}")
        lines.append(f"**Header terms:** {info['header_terms']}")
        lines.append("")
        lines.append("**Decision reasons (first doc):**")
        for r in info["first_reasons"]:
            lines.append(f"- {r}")
        lines.append("")

        # Misclassifications within this family
        mis = find_misclassifications(valid)
        fam_mis = [m for m in mis if m["family"] == family]
        if fam_mis:
            lines.append("**Possible misclassifications:**")
            lines.append("")
            for m in fam_mis:
                fn = Path(m["filename"]).name
                for s in m["suggestions"]:
                    lines.append(f"- `{fn}` — {s}")
            lines.append("")
        else:
            lines.append("**Possible misclassifications:** None detected")
            lines.append("")

    # ---- 3. Inconsistencies ----
    lines.append("## 3. Inconsistencies")
    lines.append("")
    inconsistencies = check_inconsistencies(valid)
    if inconsistencies:
        for inc in inconsistencies:
            fn = Path(inc["filename"]).name
            for iss in inc["issues"]:
                lines.append(f"- `{fn}` — {iss}")
    else:
        lines.append("No inconsistencies detected.")
    lines.append("")

    # ---- 4. Proposed new families ----
    lines.append("## 4. Proposed New Families")
    lines.append("")
    proposals = propose_new_families(valid)
    if proposals:
        for p in proposals:
            lines.append(f"### {p['candidate_family']}")
            lines.append("")
            lines.append(f"**Documents:** {p['count']}")
            lines.append(f"**Rationale:** {p['rationale']}")
            lines.append("")
            lines.append("**Characteristics:**")
            for k, v in p["characteristics"].items():
                lines.append(f"- {k}: {v}")
            lines.append("")
            lines.append("**Documents:**")
            for d in p["documents"]:
                lines.append(f"- `{Path(d).name}`")
            lines.append("")
    else:
        lines.append("No new families proposed (fewer than 3 documents share a unique structural fingerprint).")
        lines.append("")

    with open(output, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    input_path = "inspection_results.json"
    if not os.path.exists(input_path):
        print(f"error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    records = load(input_path)
    write_report(records, "validation_report.md")
    print("Done — validation_report.md", file=sys.stderr)


if __name__ == "__main__":
    main()
