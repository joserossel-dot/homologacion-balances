"""SPRINT 26.3 — Official Benchmark: Pipeline Actual vs Pipeline + CMCC.

Comparación científica completa entre:
  - Baseline: ENABLE_CMCC=False (pipeline actual)
  - Candidate: ENABLE_CMCC=True, ENABLE_CMCC_PRODUCTION=True, threshold=0.95

Genera reports/cmcc_benchmark/ con 8 archivos:
  benchmark.xlsx, metrics.xlsx, confusion_matrix.xlsx,
  concept_comparison.xlsx, layout_comparison.xlsx, company_comparison.xlsx,
  benchmark.md, benchmark.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
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
from gold_standard.builder import GoldBuilder
from validation.dataset_manager import DatasetManager
from learning.exact_match import normalize_name as gs_normalize

REPORTS_DIR = Path("reports/cmcc_benchmark")
GS_DB_PATH = "gold_standard.db"
CMCC_THRESHOLD = 0.95

_print = lambda *a, **k: print(*a, **k, flush=True)


# ─────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────

@dataclass
class AccountResult:
    source_file: str
    account_code: str
    account_name: str
    nature: str
    standard_code: str | None
    final_code: str | None
    confidence: float
    method: str
    reason: str
    cmcc_score: float
    cmcc_code: str | None
    cmcc_concept: str | None
    is_unknown: bool = False

    @classmethod
    def from_pipeline(cls, acct: dict) -> AccountResult:
        standard = acct.get("standard_code")
        final = acct.get("final_code")
        method = str(acct.get("method", "")).strip()
        confidence = float(acct.get("confidence", 0.0))
        cmcc_detail = acct.get("cmcc_detail") or acct.get("cmcc_shadow") or {}
        if isinstance(cmcc_detail, dict):
            cmcc_score = float(cmcc_detail.get("score", 0.0))
            cmcc_code = cmcc_detail.get("code")
            cmcc_concept = cmcc_detail.get("concept")
        else:
            cmcc_score = 0.0
            cmcc_code = None
            cmcc_concept = None
        return cls(
            source_file=str(acct.get("source_file", "")),
            account_code=str(acct.get("account_code", "")),
            account_name=str(acct.get("account_name", "")),
            nature=str(acct.get("nature", "")),
            standard_code=standard,
            final_code=final,
            confidence=confidence,
            method=method,
            reason=str(acct.get("reason", "")),
            cmcc_score=cmcc_score,
            cmcc_code=cmcc_code,
            cmcc_concept=cmcc_concept,
            is_unknown=(method == "unclassified" or final is None),
        )


@dataclass
class PipelineRun:
    label: str
    accounts: list[AccountResult]
    summary: dict[str, Any]
    elapsed: float


# ─────────────────────────────────────────────
# Pipeline execution
# ─────────────────────────────────────────────

def run_pipeline(features: CMCCFeatureFlags, label: str) -> PipelineRun:
    cache_dir = REPORTS_DIR / "cache" / label.lower().replace(" ", "_")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_meta = cache_dir / "_metadata.json"

    if cache_meta.exists():
        _print(f"  [{label}] Loading from cache ({cache_dir})...")
        metadata = json.loads(cache_meta.read_text(encoding="utf-8"))
        all_accounts = []
        for acct_file in sorted(cache_dir.glob("account_*.json")):
            acct_data = json.loads(acct_file.read_text(encoding="utf-8"))
            all_accounts.append(AccountResult(**acct_data))
        return PipelineRun(
            label=label, accounts=all_accounts,
            summary=metadata["summary"], elapsed=metadata["elapsed"],
        )

    pipeline = HomologationPipeline(str(GS_DB_PATH), features=features)
    manager = DatasetManager("datasets")
    all_files = manager.discover()
    _print(f"  [{label}] Processing {len(all_files)} files...")

    all_accounts: list[AccountResult] = []
    total_accounts = 0
    total_classified = 0
    total_unknown = 0
    method_counter: Counter = Counter()
    total_time = 0.0

    for i, dfile in enumerate(all_files):
        rel_path = str(dfile.path.relative_to(Path("datasets").resolve()))
        doc_start = time.perf_counter()
        try:
            result = pipeline.process(str(dfile.path))
            doc_elapsed = time.perf_counter() - doc_start
            total_time += doc_elapsed

            total_accounts += result.get("accounts_total", 0)
            total_classified += result.get("accounts_classified", 0)
            total_unknown += result.get("accounts_without_dictionary_match", 0)

            for acct in result.get("classified", []):
                ar = AccountResult.from_pipeline(acct)
                all_accounts.append(ar)
                method_counter[ar.method] += 1

                _print(f"    [{i+1}/{len(all_files)}] {rel_path[:60]} ({doc_elapsed:.2f}s)")
        except Exception as e:
            _print(f"    [{i+1}/{len(all_files)}] ERROR: {e}")

        if (i + 1) % 25 == 0:
            _save_cache(cache_dir, all_accounts, {
                "summary": {
                    "label": label,
                    "files": len(all_files),
                    "total_accounts": total_accounts,
                    "total_classified": total_classified,
                    "total_unknown": total_unknown,
                    "coverage_pct": round(total_classified / max(total_accounts, 1) * 100, 2),
                    "unknown_pct": round(total_unknown / max(total_accounts, 1) * 100, 2),
                    "method_distribution": dict(method_counter.most_common()),
                    "time_seconds": round(total_time, 3),
                },
                "elapsed": total_time,
            })

    summary = {
        "label": label,
        "files": len(all_files),
        "total_accounts": total_accounts,
        "total_classified": total_classified,
        "total_unknown": total_unknown,
        "coverage_pct": round(total_classified / max(total_accounts, 1) * 100, 2),
        "unknown_pct": round(total_unknown / max(total_accounts, 1) * 100, 2),
        "method_distribution": dict(method_counter.most_common()),
        "time_seconds": round(total_time, 3),
    }
    _save_cache(cache_dir, all_accounts, {"summary": summary, "elapsed": total_time})
    return PipelineRun(label=label, accounts=all_accounts, summary=summary, elapsed=total_time)


def _save_cache(cache_dir: Path, accounts: list[AccountResult], metadata: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for idx, acct in enumerate(accounts):
        (cache_dir / f"account_{idx:06d}.json").write_text(
            json.dumps(asdict(acct), ensure_ascii=False), encoding="utf-8"
        )
    (cache_dir / "_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )


# ─────────────────────────────────────────────
# Gold standard comparison
# ─────────────────────────────────────────────

def load_gold_standard() -> dict[str, str]:
    builder = GoldBuilder(GS_DB_PATH)
    norm_map: dict[str, str] = {}
    for rec in builder.list_all():
        if rec.final_code and rec.final_code.strip():
            norm_map[gs_normalize(rec.account_name)] = rec.final_code.strip()
    builder.close()
    return norm_map


def compute_metrics_vs_gs(
    accounts: list[AccountResult], gs_map: dict[str, str], label: str
) -> dict[str, Any]:
    eligible = []
    for a in accounts:
        expected = gs_map.get(gs_normalize(a.account_name))
        if expected:
            predicted = a.final_code or a.standard_code or "UNKNOWN"
            eligible.append({
                "account_name": a.account_name,
                "expected": expected,
                "predicted": str(predicted) if predicted else "UNKNOWN",
                "correct": str(predicted) == expected,
                "method": a.method,
                "confidence": a.confidence,
            })

    if not eligible:
        return {"label": label, "eligible": 0, "error": "No gold standard matches"}

    total = len(eligible)
    correct = sum(1 for e in eligible if e["correct"])
    errors = [e for e in eligible if not e["correct"]]

    accuracy = correct / total if total else 0.0

    labels = sorted(set(e["expected"] for e in eligible) |
                    set(e["predicted"] for e in eligible if e["predicted"] != "UNKNOWN"))

    per_label = []
    tp_total = fp_total = fn_total = 0
    for lbl in labels:
        tp = sum(1 for e in eligible if e["correct"] and e["expected"] == lbl)
        fp = sum(1 for e in eligible if not e["correct"] and e["predicted"] == lbl)
        fn = sum(1 for e in eligible if not e["correct"] and e["expected"] == lbl)
        tp_total += tp
        fp_total += fp
        fn_total += fn
        p = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        r = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0
        per_label.append({
            "label": lbl, "tp": tp, "fp": fp, "fn": fn,
            "precision": p, "recall": r, "f1": f1,
        })

    macro_precision = round(sum(m["precision"] for m in per_label) / len(per_label), 4) if per_label else 0.0
    macro_recall = round(sum(m["recall"] for m in per_label) / len(per_label), 4) if per_label else 0.0
    macro_f1 = round(sum(m["f1"] for m in per_label) / len(per_label), 4) if per_label else 0.0

    micro_precision = round(tp_total / (tp_total + fp_total), 4) if (tp_total + fp_total) > 0 else 0.0
    micro_recall = round(tp_total / (tp_total + fn_total), 4) if (tp_total + fn_total) > 0 else 0.0
    micro_f1 = round(2 * micro_precision * micro_recall / (micro_precision + micro_recall), 4) if (micro_precision + micro_recall) > 0 else 0.0

    error_categories = Counter()
    for e in errors:
        if e["predicted"] == "UNKNOWN":
            error_categories["UNKNOWN"] += 1
        elif e["method"].startswith("cmcc_"):
            error_categories["CMCC_MISMATCH"] += 1
        elif e["method"].startswith("learning"):
            error_categories["LEARNING_MISMATCH"] += 1
        elif e["method"].startswith("dictionary"):
            error_categories["DICTIONARY_MISMATCH"] += 1
        else:
            error_categories["OTHER"] += 1

    return {
        "label": label,
        "eligible": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": round(accuracy, 4),
        "accuracy_pct": round(accuracy * 100, 2),
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "error_distribution": dict(error_categories.most_common()),
        "per_label": per_label,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# Side-by-side comparison
# ─────────────────────────────────────────────

def compare_runs(baseline: PipelineRun, candidate: PipelineRun) -> dict[str, Any]:
    b_map = {(a.source_file, a.account_code, a.account_name): a for a in baseline.accounts}
    c_map = {(a.source_file, a.account_code, a.account_name): a for a in candidate.accounts}
    all_keys = set(b_map.keys()) | set(c_map.keys())

    changed = []
    unchanged = 0
    only_baseline = 0
    only_candidate = 0

    for key in all_keys:
        b = b_map.get(key)
        c = c_map.get(key)
        if b and c:
            b_code = b.final_code or b.standard_code
            c_code = c.final_code or c.standard_code
            if b_code != c_code:
                changed.append({
                    "source_file": key[0],
                    "account_code": key[1],
                    "account_name": key[2],
                    "baseline_code": b_code,
                    "baseline_method": b.method,
                    "baseline_confidence": b.confidence,
                    "candidate_code": c_code,
                    "candidate_method": c.method,
                    "candidate_confidence": c.confidence,
                })
            else:
                unchanged += 1
        elif b and not c:
            only_baseline += 1
        else:
            only_candidate += 1

    return {
        "total_accounts": len(all_keys),
        "changed": changed,
        "num_changed": len(changed),
        "unchanged": unchanged,
        "only_baseline": only_baseline,
        "only_candidate": only_candidate,
        "change_rate": round(len(changed) / max(len(all_keys), 1) * 100, 2),
    }


# ─────────────────────────────────────────────
# Per-dimension analysis
# ─────────────────────────────────────────────

def analyze_by_concept(accounts: list[AccountResult]) -> list[dict]:
    concept_map: dict[str, list[AccountResult]] = defaultdict(list)
    for a in accounts:
        code = a.final_code or a.standard_code or "UNKNOWN"
        concept_map[code].append(a)

    results = []
    for code, accs in sorted(concept_map.items()):
        n_unknown = sum(1 for a in accs if a.is_unknown)
        n_classified = len(accs) - n_unknown
        avg_conf = round(sum(a.confidence for a in accs if not a.is_unknown) / max(n_classified, 1), 4)
        methods = Counter(a.method for a in accs if not a.is_unknown)
        results.append({
            "concept_code": code,
            "total": len(accs),
            "classified": n_classified,
            "unknown": n_unknown,
            "coverage_pct": round(n_classified / max(len(accs), 1) * 100, 2),
            "avg_confidence": avg_conf,
            "top_methods": dict(methods.most_common(3)),
        })
    return results


def analyze_by_layout(accounts: list[AccountResult]) -> list[dict]:
    def infer_layout(source_file: str) -> str:
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

    layout_map: dict[str, list[AccountResult]] = defaultdict(list)
    for a in accounts:
        layout_map[infer_layout(a.source_file)].append(a)

    results = []
    for layout, accs in sorted(layout_map.items()):
        n_unknown = sum(1 for a in accs if a.is_unknown)
        n_classified = len(accs) - n_unknown
        avg_conf = round(sum(a.confidence for a in accs if not a.is_unknown) / max(n_classified, 1), 4)
        results.append({
            "layout": layout,
            "total": len(accs),
            "classified": n_classified,
            "unknown": n_unknown,
            "coverage_pct": round(n_classified / max(len(accs), 1) * 100, 2),
            "avg_confidence": avg_conf,
        })
    return results


def analyze_by_company(accounts: list[AccountResult]) -> list[dict]:
    def infer_company(source_file: str) -> str:
        name = Path(source_file).stem
        name = re.sub(r"^\d+\s*", "", name)
        name = re.sub(r"\s*\d{4}.*$", "", name)
        return name.strip()[:60] or "unknown"

    company_map: dict[str, list[AccountResult]] = defaultdict(list)
    for a in accounts:
        company_map[infer_company(a.source_file)].append(a)

    results = []
    for company, accs in sorted(company_map.items()):
        n_unknown = sum(1 for a in accs if a.is_unknown)
        n_classified = len(accs) - n_unknown
        results.append({
            "company": company,
            "total": len(accs),
            "classified": n_classified,
            "unknown": n_unknown,
            "coverage_pct": round(n_classified / max(len(accs), 1) * 100, 2),
        })
    return sorted(results, key=lambda x: -x["total"])


def build_confusion_matrix(gs_metrics: dict) -> pd.DataFrame:
    if not gs_metrics.get("per_label"):
        return pd.DataFrame()
    labels = sorted(set(m["label"] for m in gs_metrics["per_label"]))
    matrix: dict[str, dict[str, int]] = {lbl: {l: 0 for l in labels + ["UNKNOWN"]} for lbl in labels}
    for e in gs_metrics.get("errors", []):
        exp = e["expected"]
        pred = e["predicted"]
        if exp in matrix:
            if pred in matrix[exp]:
                matrix[exp][pred] += 1
        elif "UNKNOWN" not in matrix:
            pass
    df = pd.DataFrame.from_dict(matrix, orient="index")
    df.index.name = "expected"
    df.columns.name = "predicted"
    return df


# ─────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────

def generate_reports(
    baseline_run: PipelineRun,
    candidate_run: PipelineRun,
    gs_baseline: dict,
    gs_candidate: dict,
    comparison: dict,
) -> dict[str, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    baseline_concepts = analyze_by_concept(baseline_run.accounts)
    candidate_concepts = analyze_by_concept(candidate_run.accounts)
    baseline_layouts = analyze_by_layout(baseline_run.accounts)
    candidate_layouts = analyze_by_layout(candidate_run.accounts)
    baseline_companies = analyze_by_company(baseline_run.accounts)
    candidate_companies = analyze_by_company(candidate_run.accounts)

    # ── 1. benchmark.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "benchmark.xlsx") as writer:
        summary_rows = [
            {"metric": k,
             "baseline": str(gs_baseline.get(k, baseline_run.summary.get(k, ""))),
             "candidate": str(gs_candidate.get(k, candidate_run.summary.get(k, "")))}
            for k in sorted(set(list(gs_baseline.keys()) + list(gs_candidate.keys())))
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        change_df = pd.DataFrame(comparison.get("changed", []))
        if not change_df.empty:
            change_df.to_excel(writer, sheet_name="Changes", index=False)

        bl_methods = pd.DataFrame([
            {"method": k, "count": v}
            for k, v in baseline_run.summary.get("method_distribution", {}).items()
        ])
        bl_methods.to_excel(writer, sheet_name="Baseline_Methods", index=False)
        ca_methods = pd.DataFrame([
            {"method": k, "count": v}
            for k, v in candidate_run.summary.get("method_distribution", {}).items()
        ])
        ca_methods.to_excel(writer, sheet_name="Candidate_Methods", index=False)
    paths["benchmark.xlsx"] = REPORTS_DIR / "benchmark.xlsx"

    # ── 2. metrics.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "metrics.xlsx") as writer:
        metrics_keys = ["accuracy", "accuracy_pct", "macro_f1", "micro_f1",
                         "macro_precision", "macro_recall", "micro_precision", "micro_recall"]
        metric_rows = []
        for mk in metrics_keys:
            metric_rows.append({
                "metric": mk,
                "baseline": gs_baseline.get(mk, "N/A"),
                "candidate": gs_candidate.get(mk, "N/A"),
                "diff": (gs_candidate.get(mk, 0) - gs_baseline.get(mk, 0))
                if isinstance(gs_baseline.get(mk), (int, float)) and isinstance(gs_candidate.get(mk), (int, float))
                else "N/A",
            })
        pd.DataFrame(metric_rows).to_excel(writer, sheet_name="Global_Metrics", index=False)

        if gs_baseline.get("per_label"):
            bl_labels = pd.DataFrame(gs_baseline["per_label"])
            bl_labels.to_excel(writer, sheet_name="Baseline_Per_Label", index=False)
        if gs_candidate.get("per_label"):
            ca_labels = pd.DataFrame(gs_candidate["per_label"])
            ca_labels.to_excel(writer, sheet_name="Candidate_Per_Label", index=False)

        coverage_rows = [
            {"metric": "coverage_pct", "baseline": baseline_run.summary["coverage_pct"],
             "candidate": candidate_run.summary["coverage_pct"],
             "diff_pp": round(candidate_run.summary["coverage_pct"] - baseline_run.summary["coverage_pct"], 2)},
            {"metric": "unknown", "baseline": baseline_run.summary["total_unknown"],
             "candidate": candidate_run.summary["total_unknown"],
             "diff": candidate_run.summary["total_unknown"] - baseline_run.summary["total_unknown"]},
            {"metric": "classified", "baseline": baseline_run.summary["total_classified"],
             "candidate": candidate_run.summary["total_classified"],
             "diff": candidate_run.summary["total_classified"] - baseline_run.summary["total_classified"]},
        ]
        pd.DataFrame(coverage_rows).to_excel(writer, sheet_name="Coverage", index=False)

        if gs_baseline.get("error_distribution"):
            bl_errs = pd.DataFrame([
                {"category": k, "count": v}
                for k, v in gs_baseline["error_distribution"].items()
            ])
            bl_errs.to_excel(writer, sheet_name="Baseline_Errors", index=False)
        if gs_candidate.get("error_distribution"):
            ca_errs = pd.DataFrame([
                {"category": k, "count": v}
                for k, v in gs_candidate["error_distribution"].items()
            ])
            ca_errs.to_excel(writer, sheet_name="Candidate_Errors", index=False)
    paths["metrics.xlsx"] = REPORTS_DIR / "metrics.xlsx"

    # ── 3. confusion_matrix.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "confusion_matrix.xlsx") as writer:
        bl_cm = build_confusion_matrix(gs_baseline)
        if not bl_cm.empty:
            bl_cm.to_excel(writer, sheet_name="Baseline_CM")
        ca_cm = build_confusion_matrix(gs_candidate)
        if not ca_cm.empty:
            ca_cm.to_excel(writer, sheet_name="Candidate_CM")
    paths["confusion_matrix.xlsx"] = REPORTS_DIR / "confusion_matrix.xlsx"

    # ── 4. concept_comparison.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "concept_comparison.xlsx") as writer:
        bl_df = pd.DataFrame(baseline_concepts)
        if not bl_df.empty:
            bl_df.to_excel(writer, sheet_name="Baseline", index=False)
        ca_df = pd.DataFrame(candidate_concepts)
        if not ca_df.empty:
            ca_df.to_excel(writer, sheet_name="Candidate", index=False)

        concept_diff = []
        bl_code_map = {c["concept_code"]: c for c in baseline_concepts}
        ca_code_map = {c["concept_code"]: c for c in candidate_concepts}
        all_codes = sorted(set(bl_code_map.keys()) | set(ca_code_map.keys()))
        for code in all_codes:
            bl = bl_code_map.get(code, {})
            ca = ca_code_map.get(code, {})
            concept_diff.append({
                "concept_code": code,
                "baseline_total": bl.get("total", 0),
                "candidate_total": ca.get("total", 0),
                "baseline_coverage_pct": bl.get("coverage_pct", 0),
                "candidate_coverage_pct": ca.get("coverage_pct", 0),
                "coverage_diff_pp": round(ca.get("coverage_pct", 0) - bl.get("coverage_pct", 0), 2),
            })
        pd.DataFrame(concept_diff).to_excel(writer, sheet_name="Comparison", index=False)
    paths["concept_comparison.xlsx"] = REPORTS_DIR / "concept_comparison.xlsx"

    # ── 5. layout_comparison.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "layout_comparison.xlsx") as writer:
        bl_df = pd.DataFrame(baseline_layouts)
        if not bl_df.empty:
            bl_df.to_excel(writer, sheet_name="Baseline", index=False)
        ca_df = pd.DataFrame(candidate_layouts)
        if not ca_df.empty:
            ca_df.to_excel(writer, sheet_name="Candidate", index=False)

        layout_diff = []
        bl_lo_map = {c["layout"]: c for c in baseline_layouts}
        ca_lo_map = {c["layout"]: c for c in candidate_layouts}
        for layout in sorted(set(bl_lo_map.keys()) | set(ca_lo_map.keys())):
            bl = bl_lo_map.get(layout, {})
            ca = ca_lo_map.get(layout, {})
            layout_diff.append({
                "layout": layout,
                "baseline_total": bl.get("total", 0),
                "candidate_total": ca.get("total", 0),
                "baseline_coverage_pct": bl.get("coverage_pct", 0),
                "candidate_coverage_pct": ca.get("coverage_pct", 0),
                "coverage_diff_pp": round(ca.get("coverage_pct", 0) - bl.get("coverage_pct", 0), 2),
            })
        pd.DataFrame(layout_diff).to_excel(writer, sheet_name="Comparison", index=False)
    paths["layout_comparison.xlsx"] = REPORTS_DIR / "layout_comparison.xlsx"

    # ── 6. company_comparison.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "company_comparison.xlsx") as writer:
        bl_df = pd.DataFrame(baseline_companies)
        if not bl_df.empty:
            bl_df.to_excel(writer, sheet_name="Baseline", index=False)
        ca_df = pd.DataFrame(candidate_companies)
        if not ca_df.empty:
            ca_df.to_excel(writer, sheet_name="Candidate", index=False)

        company_diff = []
        bl_co_map = {c["company"]: c for c in baseline_companies}
        ca_co_map = {c["company"]: c for c in candidate_companies}
        for company in sorted(set(bl_co_map.keys()) | set(ca_co_map.keys())):
            bl = bl_co_map.get(company, {})
            ca = ca_co_map.get(company, {})
            company_diff.append({
                "company": company,
                "baseline_total": bl.get("total", 0),
                "candidate_total": ca.get("total", 0),
                "baseline_coverage_pct": bl.get("coverage_pct", 0),
                "candidate_coverage_pct": ca.get("coverage_pct", 0),
                "coverage_diff_pp": round(ca.get("coverage_pct", 0) - bl.get("coverage_pct", 0), 2),
            })
        pd.DataFrame(company_diff).to_excel(writer, sheet_name="Comparison", index=False)
    paths["company_comparison.xlsx"] = REPORTS_DIR / "company_comparison.xlsx"

    return paths


def generate_markdown(
    baseline_run: PipelineRun,
    candidate_run: PipelineRun,
    gs_baseline: dict,
    gs_candidate: dict,
    comparison: dict,
) -> str:
    lines: list[str] = []

    def L(*args):
        lines.extend(args)
        lines.append("")

    L("# CMCC Official Benchmark — Pipeline Actual vs Pipeline + CMCC")
    L(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    L(f"**Gold Standard:** {gs_baseline.get('eligible', 0)} accounts matched "
      f"(baseline) / {gs_candidate.get('eligible', 0)} accounts matched (candidate)")
    L(f"**Configuration:** Baseline: ENABLE_CMCC=False | "
      f"Candidate: ENABLE_CMCC=True, PRODUCTION=True, threshold={CMCC_THRESHOLD}")
    L("---")

    # ── 1. Executive summary ──
    L("## 1. Executive Summary")
    L("| Metric | Baseline | Candidate | Δ | Δ% |")
    L("|---|---|---|---|---|")
    bl = baseline_run.summary
    ca = candidate_run.summary
    L(f"| Total accounts | {bl['total_accounts']} | {ca['total_accounts']} | — | — |")
    L(f"| Classified | {bl['total_classified']} | {ca['total_classified']} | "
      f"{ca['total_classified'] - bl['total_classified']} | "
      f"{round((ca['total_classified']-bl['total_classified'])/max(bl['total_classified'],1)*100,1)}% |")
    L(f"| UNKNOWN | {bl['total_unknown']} | {ca['total_unknown']} | "
      f"{ca['total_unknown'] - bl['total_unknown']} | "
      f"{round((ca['total_unknown']-bl['total_unknown'])/max(bl['total_unknown'],1)*100,1)}% |")
    L(f"| Coverage | {bl['coverage_pct']}% | {ca['coverage_pct']}% | "
      f"{round(ca['coverage_pct']-bl['coverage_pct'],2)}pp | — |")
    L(f"| Processing time | {bl['time_seconds']}s | {ca['time_seconds']}s | "
      f"{round(ca['time_seconds']-bl['time_seconds'],3)}s | "
      f"{round((ca['time_seconds']-bl['time_seconds'])/max(bl['time_seconds'],1)*100,1)}% |")
    L("")

    # ── 2. Gold Standard metrics ──
    L("## 2. Gold Standard Metrics")
    if gs_baseline.get("eligible", 0) > 0 or gs_candidate.get("eligible", 0) > 0:
        L("| Metric | Baseline | Candidate | Δ |")
        L("|---|---|---|---|")
        for mk in ["accuracy_pct", "macro_f1", "micro_f1", "macro_precision", "macro_recall"]:
            bv = gs_baseline.get(mk, "N/A")
            cv = gs_candidate.get(mk, "N/A")
            diff = ""
            if isinstance(bv, (int, float)) and isinstance(cv, (int, float)):
                diff = f"{round(cv - bv, 4)}"
            L(f"| {mk} | {bv} | {cv} | {diff} |")
        L(f"| Correct | {gs_baseline.get('correct', 'N/A')} / {gs_baseline.get('eligible', 'N/A')} | "
          f"{gs_candidate.get('correct', 'N/A')} / {gs_candidate.get('eligible', 'N/A')} | — |")
        L(f"| Errors | {gs_baseline.get('incorrect', 'N/A')} | {gs_candidate.get('incorrect', 'N/A')} | — |")
    else:
        L("*No gold standard matches found.*")
    L("")

    # ── 3. Error distribution ──
    L("## 3. Error Distribution")
    bl_errs = gs_baseline.get("error_distribution", {})
    ca_errs = gs_candidate.get("error_distribution", {})
    all_err_cats = sorted(set(bl_errs.keys()) | set(ca_errs.keys()))
    if all_err_cats:
        L("| Category | Baseline | Candidate |")
        L("|---|---|---|")
        for cat in all_err_cats:
            L(f"| {cat} | {bl_errs.get(cat, 0)} | {ca_errs.get(cat, 0)} |")
    else:
        L("*No errors detected.*")
    L("")

    # ── 4. Side-by-side comparison ──
    L("## 4. Pipeline Comparison (All Accounts)")
    L(f"**Total accounts compared:** {comparison['total_accounts']}")
    L(f"**Changed classifications:** {comparison['num_changed']} "
      f"({comparison['change_rate']}% of total)")
    L(f"**Unchanged:** {comparison['unchanged']}")
    L("")
    if comparison["changed"]:
        L("### Changed Accounts (Top 50)")
        L("| # | Account | Baseline Code | Baseline Method | Candidate Code | Candidate Method |")
        L("|---|---|---|---|---|---|")
        for idx, ch in enumerate(comparison["changed"][:50], 1):
            L(f"| {idx} | {ch['account_name'][:50]} | {ch['baseline_code'] or 'UNKNOWN'} | "
              f"{ch['baseline_method']} | {ch['candidate_code'] or 'UNKNOWN'} | {ch['candidate_method']} |")
        if len(comparison["changed"]) > 50:
            L(f"| ... | ({len(comparison['changed']) - 50} more) | ... | ... | ... | ... |")
        L("")

    # ── 5. Method distribution ──
    L("## 5. Method Distribution")
    L("| Method | Baseline | Candidate | Δ |")
    L("|---|---|---|---|")
    bl_methods = bl.get("method_distribution", {})
    ca_methods = ca.get("method_distribution", {})
    all_methods = sorted(set(bl_methods.keys()) | set(ca_methods.keys()))
    for m in all_methods:
        bv = bl_methods.get(m, 0)
        cv = ca_methods.get(m, 0)
        L(f"| {m} | {bv} | {cv} | {cv - bv} |")
    L("")

    # ── 6. Layout comparison ──
    L("## 6. Layout Comparison")
    L("| Layout | Baseline Coverage | Candidate Coverage | Δ (pp) |")
    L("|---|---|---|---|")
    for lo in _merge_layouts(baseline_run.accounts, candidate_run.accounts):
        L(f"| {lo['layout']} | {lo['baseline_pct']}% | {lo['candidate_pct']}% | {lo['diff']} |")
    L("")

    # ── 7. Top improving / worsening concepts ──
    L("## 7. Concept Impact Analysis")
    bl_conc = {c["concept_code"]: c for c in analyze_by_concept(baseline_run.accounts)}
    ca_conc = {c["concept_code"]: c for c in analyze_by_concept(candidate_run.accounts)}
    diffs = []
    for code in sorted(set(bl_conc.keys()) | set(ca_conc.keys())):
        b = bl_conc.get(code, {}).get("coverage_pct", 0)
        c = ca_conc.get(code, {}).get("coverage_pct", 0)
        diffs.append((code, b, c, round(c - b, 2)))
    diffs.sort(key=lambda x: -x[3])

    improving = [d for d in diffs if d[3] > 0]
    worsening = [d for d in diffs if d[3] < 0]
    L(f"### Concepts that Improve ({len(improving)})")
    if improving:
        L("| Code | Baseline % | Candidate % | Δ (pp) |")
        L("|---|---|---|---|")
        for code, b, c, d in improving[:20]:
            L(f"| {code} | {b}% | {c}% | +{d} |")
    else:
        L("*No concepts improved.*")
    L("")
    L(f"### Concepts that Worsen ({len(worsening)})")
    if worsening:
        L("| Code | Baseline % | Candidate % | Δ (pp) |")
        L("|---|---|---|---|")
        for code, b, c, d in worsening[:20]:
            L(f"| {code} | {b}% | {c}% | {d} |")
    else:
        L("*No concepts worsened.*")
    L("")

    # ── 8. Conclusions ──
    L("## 8. Conclusions")
    coverage_gain = round(ca["coverage_pct"] - bl["coverage_pct"], 2)
    unknown_reduction = bl["total_unknown"] - ca["total_unknown"]
    accuracy_change = ""
    if isinstance(gs_baseline.get("accuracy"), (int, float)) and isinstance(gs_candidate.get("accuracy"), (int, float)):
        acc_diff = round(gs_candidate["accuracy"] - gs_baseline["accuracy"], 4)
        accuracy_change = f"(Δ = {acc_diff:+.4f})"
    L(f"- **Coverage:** {bl['coverage_pct']}% → {ca['coverage_pct']}% (Δ = +{coverage_gain}pp)")
    L(f"- **UNKNOWN reduction:** {unknown_reduction} accounts recovered")
    L(f"- **GS Accuracy:** {gs_baseline.get('accuracy_pct', 'N/A')}% → {gs_candidate.get('accuracy_pct', 'N/A')}% "
      f"{accuracy_change}")
    L(f"- **Changed classifications:** {comparison['num_changed']} "
      f"({comparison['change_rate']}% of total accounts)")
    L(f"- **Concepts improved:** {len(improving)} | **Concepts worsened:** {len(worsening)}")

    total_improving = sum(d[3] for d in improving)
    total_worsening = abs(sum(d[3] for d in worsening))
    L(f"- **Net coverage impact:** +{total_improving}pp concepts improved, "
      f"-{total_worsening}pp concepts worsened = +{round(total_improving - total_worsening, 2)}pp net")
    L("")

    if coverage_gain > 0 and (not gs_candidate.get("error_distribution") or
                               gs_candidate.get("accuracy", 1.0) >= gs_baseline.get("accuracy", 1.0)):
        L("### Verdict: CMCC IMPROVES PIPELINE ✅")
        L("CMCC integration increases coverage without sacrificing accuracy.")
    elif coverage_gain > 0:
        L("### Verdict: CMCC IMPROVES COVERAGE ⚠️")
        L("Coverage increases but accuracy impact requires monitoring.")
    else:
        L("### Verdict: NO SIGNIFICANT CHANGE")
        L("CMCC integration shows no measurable improvement.")

    L("---")
    L("*Generated by `scripts/cmcc_official_benchmark.py`*")
    L("*Sources: datasets/*, *gold_standard.db*")
    L("*No production code was modified during benchmarking.*")

    return "\n".join(lines)


def _merge_layouts(baseline: list[AccountResult], candidate: list[AccountResult]) -> list[dict]:
    def infer_layout(source_file: str) -> str:
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

    def coverage_by_layout(accounts: list[AccountResult]) -> dict[str, dict]:
        layout_map: dict[str, list[AccountResult]] = defaultdict(list)
        for a in accounts:
            layout_map[infer_layout(a.source_file)].append(a)
        result = {}
        for lo, accs in layout_map.items():
            n_classified = sum(1 for a in accs if not a.is_unknown)
            result[lo] = {
                "total": len(accs),
                "classified": n_classified,
                "pct": round(n_classified / max(len(accs), 1) * 100, 2),
            }
        return result

    bl = coverage_by_layout(baseline)
    ca = coverage_by_layout(candidate)
    merged = []
    for lo in sorted(set(bl.keys()) | set(ca.keys())):
        merged.append({
            "layout": lo,
            "baseline_pct": bl.get(lo, {}).get("pct", 0),
            "candidate_pct": ca.get(lo, {}).get("pct", 0),
            "diff": round(ca.get(lo, {}).get("pct", 0) - bl.get(lo, {}).get("pct", 0), 2),
        })
    return merged


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    _print("=" * 70)
    _print("SPRINT 26.3 — Official Benchmark")
    _print("Pipeline Actual vs Pipeline + CMCC")
    _print("=" * 70)
    _print()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Load gold standard ──
    _print("Loading gold standard...")
    gs_map = load_gold_standard()
    _print(f"  Gold standard: {len(gs_map)} entries")
    _print()

    # ── 2. Run baseline ──
    baseline_features = CMCCFeatureFlags(
        ENABLE_CMCC=False, ENABLE_CMCC_SHADOW=False, ENABLE_CMCC_PRODUCTION=False,
    )
    baseline_run = run_pipeline(baseline_features, "BASELINE (CMCC disabled)")
    _print()

    # ── 3. Run candidate ──
    candidate_features = CMCCFeatureFlags(
        ENABLE_CMCC=True, ENABLE_CMCC_SHADOW=False, ENABLE_CMCC_PRODUCTION=True,
        CMCC_THRESHOLD=CMCC_THRESHOLD,
    )
    candidate_run = run_pipeline(candidate_features, "CANDIDATE (CMCC production)")
    _print()

    # ── 4. Compute GS metrics ──
    gs_baseline = compute_metrics_vs_gs(baseline_run.accounts, gs_map, "baseline")
    gs_candidate = compute_metrics_vs_gs(candidate_run.accounts, gs_map, "candidate")
    _print(f"GS baseline:  {gs_baseline.get('eligible', 0)} eligible, "
           f"accuracy={gs_baseline.get('accuracy_pct', 'N/A')}%")
    _print(f"GS candidate: {gs_candidate.get('eligible', 0)} eligible, "
           f"accuracy={gs_candidate.get('accuracy_pct', 'N/A')}%")
    _print()

    # ── 5. Side-by-side comparison ──
    comparison = compare_runs(baseline_run, candidate_run)
    _print(f"Comparison: {comparison['num_changed']} changed, "
          f"{comparison['unchanged']} unchanged, "
          f"{comparison['change_rate']}% change rate")
    _print()

    # ── 6. Generate reports ──
    report_paths = generate_reports(
        baseline_run, candidate_run,
        gs_baseline, gs_candidate, comparison,
    )

    # ── 7. JSON report ──
    json_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "baseline": baseline_features.to_dict(),
            "candidate": candidate_features.to_dict(),
            "cmcc_threshold": CMCC_THRESHOLD,
        },
        "baseline_summary": baseline_run.summary,
        "candidate_summary": candidate_run.summary,
        "gold_standard": {
            "entries": len(gs_map),
            "baseline": gs_baseline,
            "candidate": gs_candidate,
        },
        "comparison": {
            "total_accounts": comparison["total_accounts"],
            "changed": comparison["num_changed"],
            "unchanged": comparison["unchanged"],
            "change_rate_pct": comparison["change_rate"],
            "num_only_baseline": comparison["only_baseline"],
            "num_only_candidate": comparison["only_candidate"],
        },
        "reports": {k: str(v) for k, v in report_paths.items()},
    }
    json_path = REPORTS_DIR / "benchmark.json"
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    _print(f"  benchmark.json: {json_path.resolve()}")

    # ── 8. Markdown report ──
    md = generate_markdown(baseline_run, candidate_run, gs_baseline, gs_candidate, comparison)
    md_path = REPORTS_DIR / "benchmark.md"
    md_path.write_text(md, encoding="utf-8")
    _print(f"  benchmark.md:    {md_path.resolve()}")

    # ── 9. Summary ──
    coverage_gain = round(candidate_run.summary["coverage_pct"] - baseline_run.summary["coverage_pct"], 2)
    unknown_red = baseline_run.summary["total_unknown"] - candidate_run.summary["total_unknown"]

    _print()
    _print("=" * 70)
    _print("BENCHMARK COMPLETE")
    _print("=" * 70)
    _print(f"  Coverage:     {baseline_run.summary['coverage_pct']}% → {candidate_run.summary['coverage_pct']}%")
    _print(f"  Gain:         +{coverage_gain}pp")
    _print(f"  UNKNOWN red:  {unknown_red} accounts recovered")
    _print(f"  GS Accuracy:  {gs_baseline.get('accuracy_pct', 'N/A')}% → {gs_candidate.get('accuracy_pct', 'N/A')}%")
    _print(f"  Changes:      {comparison['num_changed']} accounts affected")
    _print(f"  Reports:      {REPORTS_DIR.resolve()}")
    for name, path in sorted(report_paths.items()):
        size = path.stat().st_size if path.exists() else 0
        _print(f"    {name}: {size:,} bytes")
    _print(f"    benchmark.json: {json_path.stat().st_size:,} bytes")
    _print(f"    benchmark.md:  {md_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CMCC Official Benchmark Sprint 26.3")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of files to process per run (0=all)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore cached results and re-process")
    args = parser.parse_args()

    if args.limit > 0:
        import pipeline.features as fmod
        import validation.dataset_manager as dm
        original_discover = dm.DatasetManager.discover
        def limited_discover(self):
            all_f = original_discover(self)
            return all_f[:args.limit]
        dm.DatasetManager.discover = limited_discover
        _print(f"LIMITED to {args.limit} files per run")

    if args.no_cache:
        import shutil
        cache_dir = REPORTS_DIR / "cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            _print("Cache cleared")

    main()
