from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["CMCC_ENABLE_CMCC"] = "false"
os.environ["CMCC_ENABLE_CMCC_SHADOW"] = "false"
os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "false"

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags
from validation.dataset_manager import DatasetManager
from review.cmcc_review_models import ReviewCMCC

REPORTS_DIR = Path("reports/cmcc_review_pipeline")
GS_DB_PATH = "gold_standard.db"
CMCC_THRESHOLD = 0.95

_print = lambda *a, **k: print(*a, **k, flush=True)


def _infer_company(source_file: str) -> str:
    name = Path(source_file).stem
    name = re.sub(r"^\d+\s*", "", name)
    name = re.sub(r"\s*\d{4}.*$", "", name)
    return name.strip()[:60] or "unknown"


def _infer_layout(source_file: str) -> str:
    lower = source_file.lower()
    if "balance" in lower and "8 columnas" in lower:
        return "8_columnas"
    if "tributario" in lower:
        return "tributario"
    if "pre-balance" in lower or "pre balance" in lower:
        return "pre_balance"
    if "consolidado" in lower:
        return "consolidado"
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return "excel"
    return "pdf_estandar"


def extract_review_queue(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract REVIEW_CMCC entries from pipeline result."""
    queue = []
    for acct in pipeline_result.get("classified", []):
        if acct.get("standard_code") is not None:
            continue
        cmcc_detail = acct.get("cmcc_detail") or acct.get("cmcc_shadow")
        if cmcc_detail is None:
            continue
        score = float(cmcc_detail.get("score", 0.0))
        if score != 1.0:
            continue
        source_file = acct.get("source_file", "")
        account_name = acct.get("account_name", "")
        company = _infer_company(source_file)
        layout = _infer_layout(source_file)
        entry = ReviewCMCC.from_pipeline_account(
            account_name=account_name,
            source_file=source_file,
            cmcc_detail=cmcc_detail,
            company=company,
            layout=layout,
        )
        queue.append(entry.to_dict())
    return queue


def run_pipeline_for_review(
    features: CMCCFeatureFlags, label: str, limit: int = 0
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run pipeline and extract review queue + summary."""
    pipeline = HomologationPipeline(str(GS_DB_PATH), features=features)
    manager = DatasetManager("datasets")
    all_files = manager.discover()

    if limit > 0:
        all_files = all_files[:limit]

    _print(f"  [{label}] Processing {len(all_files)} files...")

    all_accounts: list[dict[str, Any]] = []
    total_unknown = 0
    total_classified = 0
    total_accounts = 0
    method_counter: Counter = Counter()
    t0 = time.perf_counter()

    for i, dfile in enumerate(all_files):
        try:
            result = pipeline.process(str(dfile.path))
        except Exception as e:
            _print(f"    ERROR {dfile.path.name}: {e}")
            continue

        total_accounts += result.get("accounts_total", 0)
        total_classified += result.get("accounts_classified", 0)
        total_unknown += result.get("accounts_without_dictionary_match", 0)
        for acct in result.get("classified", []):
            all_accounts.append(acct)
            method_counter[acct.get("method", "unknown")] += 1

    elapsed = time.perf_counter() - t0

    review_queue = extract_review_queue({"classified": all_accounts})

    summary = {
        "label": label,
        "files": len(all_files),
        "total_accounts": total_accounts,
        "total_classified": total_classified,
        "total_unknown": total_unknown,
        "total_review": len(review_queue),
        "coverage_pct": round(total_classified / max(total_accounts, 1) * 100, 2),
        "unknown_pct": round(total_unknown / max(total_accounts, 1) * 100, 2),
        "review_pct_of_unknown": round(
            len(review_queue) / max(total_unknown, 1) * 100, 2
        ),
        "elapsed_seconds": round(elapsed, 3),
        "method_distribution": dict(method_counter.most_common()),
    }

    return review_queue, summary


def compute_statistics(
    review_queue: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, Any]:
    total_review = len(review_queue)
    total_unknown = summary["total_unknown"]

    by_company: Counter = Counter()
    by_layout: Counter = Counter()
    by_concept: Counter = Counter()
    by_concept_name: Counter = Counter()
    by_document: Counter = Counter()
    by_method: Counter = Counter()

    for entry in review_queue:
        by_company[entry["company"]] += 1
        by_layout[entry["layout"]] += 1
        by_concept[entry["concept_code"]] += 1
        by_concept_name[entry["concept_name"]] += 1
        by_document[entry["document_id"]] += 1
        by_method[entry["matching_method"]] += 1

    return {
        "total_review": total_review,
        "total_unknown": total_unknown,
        "unknown_after_review": total_unknown - total_review,
        "review_pct": round(total_review / max(total_unknown, 1) * 100, 2),
        "num_companies": len(by_company),
        "num_concepts": len(by_concept),
        "num_layouts": len(by_layout),
        "num_documents": len(by_document),
        "top_companies": by_company.most_common(20),
        "top_concepts": by_concept.most_common(20),
        "top_concept_names": by_concept_name.most_common(20),
        "top_layouts": by_layout.most_common(20),
        "top_documents": by_document.most_common(20),
        "top_methods": by_method.most_common(10),
    }


def generate_reports(
    review_queue: list[dict[str, Any]],
    summary: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # ── 1. review_queue.xlsx ─────────────────
    df_queue = pd.DataFrame(review_queue) if review_queue else pd.DataFrame(columns=ReviewCMCC.columns())
    df_queue.to_excel(REPORTS_DIR / "review_queue.xlsx", index=False)
    paths["review_queue.xlsx"] = REPORTS_DIR / "review_queue.xlsx"

    # ── 2. review_statistics.xlsx ─────────────────
    stat_rows = [
        {"metric": "Total UNKNOWN accounts", "value": stats["total_unknown"]},
        {"metric": "Total REVIEW candidates", "value": stats["total_review"]},
        {"metric": "UNKNOWN after REVIEW", "value": stats["unknown_after_review"]},
        {"metric": "REVIEW % of UNKNOWN", "value": f"{stats['review_pct']}%"},
        {"metric": "Unique companies", "value": stats["num_companies"]},
        {"metric": "Unique concepts", "value": stats["num_concepts"]},
        {"metric": "Unique layouts", "value": stats["num_layouts"]},
        {"metric": "Unique documents", "value": stats["num_documents"]},
        {"metric": "Files processed", "value": summary["files"]},
        {"metric": "Total accounts", "value": summary["total_accounts"]},
        {"metric": "Classified accounts", "value": summary["total_classified"]},
        {"metric": "Coverage %", "value": f"{summary['coverage_pct']}%"},
        {"metric": "Elapsed (s)", "value": summary["elapsed_seconds"]},
    ]
    pd.DataFrame(stat_rows).to_excel(REPORTS_DIR / "review_statistics.xlsx", index=False)
    paths["review_statistics.xlsx"] = REPORTS_DIR / "review_statistics.xlsx"

    # ── 3. review_by_company.xlsx ─────────────────
    comp_rows = [
        {"company": company, "count": count}
        for company, count in stats["top_companies"]
    ]
    pd.DataFrame(comp_rows).to_excel(REPORTS_DIR / "review_by_company.xlsx", index=False)
    paths["review_by_company.xlsx"] = REPORTS_DIR / "review_by_company.xlsx"

    # ── 4. review_by_layout.xlsx ─────────────────
    layout_rows = [
        {"layout": layout, "count": count}
        for layout, count in stats["top_layouts"]
    ]
    pd.DataFrame(layout_rows).to_excel(REPORTS_DIR / "review_by_layout.xlsx", index=False)
    paths["review_by_layout.xlsx"] = REPORTS_DIR / "review_by_layout.xlsx"

    # ── 5. review_by_concept.xlsx ─────────────────
    code_to_name: dict[str, str] = {}
    for entry in review_queue:
        c = entry.get("concept_code", "")
        n = entry.get("concept_name", "")
        if c and c not in code_to_name:
            code_to_name[c] = n
    concept_data = []
    for code, count in stats["top_concepts"]:
        concept_data.append({
            "concept_code": code,
            "concept_name": code_to_name.get(code, ""),
            "count": count,
        })
    pd.DataFrame(concept_data).to_excel(REPORTS_DIR / "review_by_concept.xlsx", index=False)
    paths["review_by_concept.xlsx"] = REPORTS_DIR / "review_by_concept.xlsx"

    return paths


def generate_markdown(
    review_queue: list[dict[str, Any]],
    summary: dict[str, Any],
    stats: dict[str, Any],
    paths: dict[str, Path],
) -> str:
    lines: list[str] = []

    def L(*args):
        lines.extend(args)
        lines.append("")

    L("# CMCC Review Pipeline — REVIEW_CMCC Queue")
    L(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    L(f"**Configuration:** ENABLE_CMCC=True, ENABLE_CMCC_REVIEW_PIPELINE=True")
    L("---")

    # ── 1. Summary ──
    L("## 1. Summary")
    L(f"**UNKNOWN accounts:** {stats['total_unknown']}")
    L(f"**REVIEW candidates:** {stats['total_review']}")
    L(f"**UNKNOWN after REVIEW:** {stats['unknown_after_review']}")
    L(f"**REVIEW % of UNKNOWN:** {stats['review_pct']}%")
    L(f"**Files processed:** {summary['files']}")
    L(f"**Total accounts:** {summary['total_accounts']}")
    L(f"**Coverage:** {summary['coverage_pct']}%")
    L("")

    # ── 2. Per-company ──
    L("## 2. REVIEW by Company")
    L("| Company | Count |")
    L("|---|---|")
    for company, count in stats["top_companies"][:15]:
        L(f"| {company} | {count} |")
    if len(stats["top_companies"]) > 15:
        L(f"| ... and {len(stats['top_companies']) - 15} more | |")
    L("")

    # ── 3. Per-layout ──
    L("## 3. REVIEW by Layout")
    L("| Layout | Count |")
    L("|---|---|")
    for layout, count in stats["top_layouts"]:
        L(f"| {layout} | {count} |")
    L("")

    # ── 4. Per-concept ──
    L("## 4. REVIEW by Concept")
    L("| Code | Name | Count |")
    L("|---|---|---|")
    code_name_map: dict[str, str] = {}
    for entry in review_queue:
        c = entry.get("concept_code", "")
        n = entry.get("concept_name", "")
        if c and c not in code_name_map:
            code_name_map[c] = n
    for code, count in stats["top_concepts"][:20]:
        name = code_name_map.get(code, "")
        L(f"| {code} | {name} | {count} |")
    if len(stats["top_concepts"]) > 20:
        L(f"| ... and {len(stats['top_concepts']) - 20} more concepts | | |")
    L("")

    # ── 5. Per-document ──
    L("## 5. REVIEW by Document")
    L("| Document | Count |")
    L("|---|---|")
    for doc, count in stats["top_documents"][:15]:
        L(f"| {doc} | {count} |")
    if len(stats["top_documents"]) > 15:
        L(f"| ... and {len(stats['top_documents']) - 15} more | |")
    L("")

    # ── 6. Matching methods ──
    L("## 6. Matching Methods")
    L("| Method | Count |")
    L("|---|---|")
    for method, count in stats["top_methods"]:
        L(f"| {method} | {count} |")
    L("")

    # ── 7. Impact ──
    L("## 7. Impact Analysis")
    L(f"- **UNKNOWN recovery:** {stats['total_review']} of {stats['total_unknown']} UNKNOWN accounts "
      f"({stats['review_pct']}%) are safe candidates for human review.")
    L(f"- **Companies impacted:** {stats['num_companies']}")
    L(f"- **Concepts impacted:** {stats['num_concepts']}")
    L(f"- **Layouts impacted:** {stats['num_layouts']}")
    L(f"- **Documents impacted:** {stats['num_documents']}")
    L("")

    # ── 8. Traceability ──
    L("## 8. Traceability")
    L("Each REVIEW_CMCC entry (see `review_queue.xlsx`) contains:")
    L("- `account_name`: Original account name from source document")
    L("- `document_id`: Source file path")
    L("- `company`: Inferred company name")
    L("- `layout`: Inferred document layout")
    L("- `concept_code`: CMCC proposed standard code")
    L("- `concept_name`: CMCC proposed concept name")
    L("- `score`: CMCC match score (always 1.0 for REVIEW)")
    L("- `matched_variant`: The exact variant that matched")
    L("- `matching_method`: Type of match (nombre/sinonimo/abreviatura/variante)")
    L("- `evidence`: Detailed match evidence from CMCC classifier")
    L("- `decision_trace_id`: Unique trace ID for accountability")
    L("- `review_status`: Always PENDING initially")
    L("- `created_at`: Timestamp of queue entry creation")
    L("")

    # ── 9. Files ──
    L("## 9. Generated Files")
    for name, path in sorted(paths.items()):
        size = path.stat().st_size if path.exists() else 0
        L(f"- `{name}`: {size:,} bytes")
    L("")

    L("---")
    L("*REVIEW_CMCC is NOT an official classification. It is a human review queue only.*")
    L("*No production code was modified. No classifications changed.*")
    L("*Generated by `scripts/run_cmcc_review_pipeline.py`*")

    return "\n".join(lines)
