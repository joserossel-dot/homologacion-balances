from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from evidence.account_evidence import AccountEvidence


def compute_coverage(evidences: list[AccountEvidence]) -> dict[str, Any]:
    total = len(evidences)
    if total == 0:
        return {"total": 0}

    source_file_ok = sum(1 for e in evidences if e.source_file)
    source_page_ok = sum(1 for e in evidences if e.source_page > 0)
    company_name_ok = sum(1 for e in evidences if e.company_name)
    company_rut_ok = sum(1 for e in evidences if e.company_rut)
    year_ok = sum(1 for e in evidences if e.year)
    amounts_ok = sum(1 for e in evidences if e.has_amounts)
    context_ok = sum(1 for e in evidences if e.has_context)
    clean_name_ok = sum(1 for e in evidences if e.clean_account_name)
    method_ok = sum(1 for e in evidences if e.classification_method)
    semantic_ok = sum(1 for e in evidences if e.semantic_hit)
    final_code_ok = sum(1 for e in evidences if e.final_code)

    all_missing: list[str] = []
    for e in evidences:
        all_missing.extend(e.missing_fields())
    missing_counter = Counter(all_missing)

    scores = [e.coverage_score for e in evidences]
    avg_score = round(sum(scores) / total, 1) if scores else 0.0

    complete = sum(1 for e in evidences if e.is_complete)
    methods = Counter(e.classification_method for e in evidences)

    return {
        "total": total,
        "complete": complete,
        "complete_pct": round(complete / total * 100, 1) if total else 0.0,
        "avg_coverage_score": avg_score,
        "fields": {
            "source_file": {"ok": source_file_ok, "pct": round(source_file_ok / total * 100, 1)},
            "source_page > 0": {"ok": source_page_ok, "pct": round(source_page_ok / total * 100, 1)},
            "company_name": {"ok": company_name_ok, "pct": round(company_name_ok / total * 100, 1)},
            "company_rut": {"ok": company_rut_ok, "pct": round(company_rut_ok / total * 100, 1)},
            "year": {"ok": year_ok, "pct": round(year_ok / total * 100, 1)},
            "monetary_amounts": {"ok": amounts_ok, "pct": round(amounts_ok / total * 100, 1)},
            "context": {"ok": context_ok, "pct": round(context_ok / total * 100, 1)},
            "clean_account_name": {"ok": clean_name_ok, "pct": round(clean_name_ok / total * 100, 1)},
            "classification_method": {"ok": method_ok, "pct": round(method_ok / total * 100, 1)},
            "semantic_hit": {"ok": semantic_ok, "pct": round(semantic_ok / total * 100, 1)},
            "final_code": {"ok": final_code_ok, "pct": round(final_code_ok / total * 100, 1)},
        },
        "top_missing_fields": missing_counter.most_common(20),
        "method_breakdown": dict(methods.most_common()),
    }


def generate_audit_report(evidences: list[AccountEvidence], output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    coverage = compute_coverage(evidences)

    # -- Audit markdown --
    md_path = out / "evidence_audit.md"
    md_path.write_text(_render_audit_md(coverage, evidences[:10]), encoding="utf-8")
    paths["audit_md"] = md_path

    # -- Statistics xlsx --
    try:
        import pandas as pd
        stats_path = out / "evidence_statistics.xlsx"
        rows = []
        for field, info in coverage["fields"].items():
            rows.append({"field": field, "ok": info["ok"], "total": coverage["total"], "pct": info["pct"]})
        pd.DataFrame(rows).to_excel(stats_path, index=False)
        paths["statistics"] = stats_path

        # Missing fields
        missing_path = out / "evidence_missing_fields.xlsx"
        mrows = [{"field": f, "count": c} for f, c in coverage["top_missing_fields"]]
        pd.DataFrame(mrows).to_excel(missing_path, index=False)
        paths["missing_fields"] = missing_path

        # Context examples
        ctx_path = out / "evidence_context_examples.xlsx"
        crows = []
        for ev in evidences[:200]:
            if ev.has_context:
                crows.append({
                    "account_name": ev.original_account_name,
                    "before": ", ".join(c.get("account_name", "") for c in ev.context_before),
                    "after": ", ".join(c.get("account_name", "") for c in ev.context_after),
                    "method": ev.classification_method,
                })
        pd.DataFrame(crows).to_excel(ctx_path, index=False)
        paths["context_examples"] = ctx_path
    except ImportError:
        pass

    return paths


def _render_audit_md(coverage: dict, samples: list[AccountEvidence]) -> str:
    lines = []
    lines.append("# Evidence Layer Audit\n")
    lines.append(f"Total accounts: {coverage['total']}\n")
    lines.append(f"Complete (all core fields): {coverage['complete']} ({coverage['complete_pct']}%)\n")
    lines.append(f"Average coverage score: {coverage['avg_coverage_score']}%\n")
    lines.append("## Field Coverage\n")
    lines.append("| Field | OK | % |")
    lines.append("|---|---|---|")
    for field, info in sorted(coverage["fields"].items()):
        lines.append(f"| {field} | {info['ok']} | {info['pct']}% |")
    lines.append("")

    lines.append("## Top Missing Fields\n")
    lines.append("| Field | Missing count |")
    lines.append("|---|---|")
    for field, count in coverage.get("top_missing_fields", []):
        lines.append(f"| {field} | {count} |")
    lines.append("")

    lines.append("## Method Breakdown\n")
    lines.append("| Method | Count |")
    lines.append("|---|---|")
    for method, count in coverage.get("method_breakdown", {}).items():
        lines.append(f"| {method} | {count} |")
    lines.append("")

    lines.append("## Sample Coverage Scores\n")
    lines.append("| # | Account | Score | Missing fields |")
    lines.append("|---|---|---|---|")
    for i, ev in enumerate(samples, 1):
        missing = ev.missing_fields()
        lines.append(f"| {i} | {ev.original_account_name[:40]} | {ev.coverage_score}% | {', '.join(missing[:5])} |")
    lines.append("")

    lines.append("## Architecture\n")
    lines.append("```")
    lines.append("Parser / Extractor")
    lines.append("  ↓")
    lines.append("  AccountEvidence ←── EvidenceBuilder")
    lines.append("  ↓")
    lines.append("  Pipeline (Classification)")
    lines.append("  ↓")
    lines.append("  Semantic / Learning / Dictionary")
    lines.append("  ↓")
    lines.append("  EvidenceSerializer (to_dict / from_dict)")
    lines.append("  ↓")
    lines.append("  Shadow / Validation / Analytics / Knowledge / Review")
    lines.append("```")
    lines.append("")

    lines.append("## How to Integrate\n")
    lines.append("1. At parser output: call `evidence_builder.build_from_account_balance(account, source_file, ...)`")
    lines.append("2. Pass `AccountEvidence` object alongside `AccountBalance` through pipeline")
    lines.append("3. At each stage (learning, semantic, dictionary), update `evidence.classification_method/confidence`")
    lines.append("4. At shadow serialization: call `evidence_serializer.to_shadow_compatible(evidences)`")
    lines.append("5. For full preservation: call `evidence_serializer.save_evidence_json(evidences)`")
    lines.append("")

    lines.append("## Current State (Retrospective Audit)\n")
    lines.append("Coverage computed from existing `shadow_data.json`. All fields that are empty/missing")
    lines.append("represent information that was already lost before reaching the Review Package.")
    lines.append("With full integration at parser level, all fields would be populated.\n")
    lines.append("---\n")
    lines.append("*Generated by Evidence Layer*")
    return "\n".join(lines)
