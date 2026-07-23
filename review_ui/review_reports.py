from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from review_ui.review_models import ReviewDecision, DecisionStatus


REPORTS_DIR = Path("reports/human_review")


def generate_reports(
    decisions: list[ReviewDecision],
    stats: dict[str, Any],
    output_dir: str | Path = REPORTS_DIR,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    df_all = pd.DataFrame([d.to_dict() for d in decisions]) if decisions else pd.DataFrame(columns=ReviewDecision.columns())
    df_all.to_excel(output_dir / "review_queue.xlsx", index=False)
    paths["review_queue.xlsx"] = output_dir / "review_queue.xlsx"

    approved = [d for d in decisions if d.status == DecisionStatus.APPROVED]
    if approved:
        pd.DataFrame([d.to_dict() for d in approved]).to_excel(output_dir / "approved.xlsx", index=False)
    else:
        pd.DataFrame(columns=ReviewDecision.columns()).to_excel(output_dir / "approved.xlsx", index=False)
    paths["approved.xlsx"] = output_dir / "approved.xlsx"

    rejected = [d for d in decisions if d.status == DecisionStatus.REJECTED]
    if rejected:
        pd.DataFrame([d.to_dict() for d in rejected]).to_excel(output_dir / "rejected.xlsx", index=False)
    else:
        pd.DataFrame(columns=ReviewDecision.columns()).to_excel(output_dir / "rejected.xlsx", index=False)
    paths["rejected.xlsx"] = output_dir / "rejected.xlsx"

    reassigned = [d for d in decisions if d.status == DecisionStatus.REASSIGNED]
    if reassigned:
        pd.DataFrame([d.to_dict() for d in reassigned]).to_excel(output_dir / "reassigned.xlsx", index=False)
    else:
        pd.DataFrame(columns=ReviewDecision.columns()).to_excel(output_dir / "reassigned.xlsx", index=False)
    paths["reassigned.xlsx"] = output_dir / "reassigned.xlsx"

    stat_rows = [
        {"metric": k.replace("_", " ").title(), "value": v}
        for k, v in stats.items()
        if not isinstance(v, list)
    ]
    pd.DataFrame(stat_rows).to_excel(output_dir / "review_statistics.xlsx", index=False)
    paths["review_statistics.xlsx"] = output_dir / "review_statistics.xlsx"

    md = _generate_markdown(decisions, stats, paths)
    (output_dir / "review_summary.md").write_text(md, encoding="utf-8")
    paths["review_summary.md"] = output_dir / "review_summary.md"

    json_path = output_dir / "review.json"
    json_path.write_text(
        json.dumps(_serializable_stats(stats, decisions), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["review.json"] = json_path

    return paths


def _generate_markdown(
    decisions: list[ReviewDecision],
    stats: dict[str, Any],
    paths: dict[str, Path],
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = []

    def L(*a):
        lines.extend(a); lines.append("")

    L("# Human Review Report — Sprint 27.3")
    L(f"**Generated:** {now}")
    L(f"**Total decisions:** {stats['total_decisions']}")
    L("---", "*Shadow mode. No dictionary writes.*", "")

    L("## 1. Summary")
    L(f"- **Pending:** {stats['pending']}")
    L(f"- **Approved:** {stats['approved']} ({stats['approval_rate']}%)")
    L(f"- **Rejected:** {stats['rejected']} ({stats['rejection_rate']}%)")
    L(f"- **Reassigned:** {stats['reassigned']} ({stats['reassignment_rate']}%)")
    L(f"- **Unique variants reviewed:** {stats['unique_variants_reviewed']}")
    L(f"- **Unique concepts impacted:** {stats['unique_concepts_impacted']}")
    L(f"- **Unique reviewers:** {stats['unique_reviewers']}")
    L(f"- **Avg confidence:** {stats['avg_confidence']}", "")

    L("## 2. Concept Distribution")
    L("| Concept | Decisions |")
    L("|---|---|")
    for concept, count in stats.get("top_concepts", []):
        L(f"| {concept} | {count} |")
    L("")

    L("## 3. Reviewer Distribution")
    L("| Reviewer | Decisions |")
    L("|---|---|")
    for reviewer, count in stats.get("top_reviewers", []):
        L(f"| {reviewer} | {count} |")
    L("")

    L("## 4. Company Distribution")
    L("| Company | Decisions |")
    L("|---|---|")
    for company, count in stats.get("top_companies", []):
        L(f"| {company} | {count} |")
    L("")

    L("## 5. Generated Files")
    for name, p in paths.items():
        size = p.stat().st_size if p.exists() else 0
        L(f"- `{name}` ({size:,} bytes)")
    L("")

    L("---", "**Sprint 27.3 complete.** Shadow mode. No production modifications.")
    return "\n".join(lines)


def _serializable_stats(stats: dict[str, Any], decisions: list[ReviewDecision]) -> dict[str, Any]:
    safe = {}
    for k, v in stats.items():
        if isinstance(v, list):
            safe[k] = [list(item) if isinstance(item, tuple) else item for item in v]
        else:
            safe[k] = v
    safe["decisions"] = [
        {"review_id": d.review_id, "variant": d.variant, "status": d.status.value}
        for d in decisions
    ]
    return safe
