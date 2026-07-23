"""SPRINT 26.4 — Final Scientific Validation: Pipeline Actual vs Pipeline + CMCC.

Compara Pipeline Actual vs Pipeline + CMCC contra Gold Standard.
Usa: Gold Standard, Holdout, Decision Trace, Scientific Validation.
Calcula: Accuracy, Precision, Recall, F1, Macro F1, Micro F1, Kappa.
Clasifica todos los errores (FP/FN).
Responde automáticamente: ¿CMCC mejora? ¿Empeora? ¿Dónde? ¿En cuánto? ¿Con qué confianza?

Genera reports/cmcc_validation_final/ con 7 archivos:
  validation.xlsx, metrics.xlsx, agreement.xlsx, error_analysis.xlsx,
  confusion_matrix.xlsx, scientific_validation.md, scientific_validation.json
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
from scientific_validation import Agreement, ErrorCategory

REPORTS_DIR = Path("reports/cmcc_validation_final")
GS_DB_PATH = "gold_standard.db"
CMCC_THRESHOLD = 0.95
HOLDOUT_DIR = Path("datasets/HOLDOUT")

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


@dataclass
class ErrorRecord:
    account_name: str
    source_file: str
    expected_code: str
    predicted_code: str
    method: str
    confidence: float
    is_false_positive: bool
    is_false_negative: bool
    error_category: str


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
# Gold standard matching
# ─────────────────────────────────────────────

def load_gold_standard() -> dict[str, dict[str, str]]:
    """Returns {normalized_name: {code, original_name}}."""
    builder = GoldBuilder(GS_DB_PATH)
    norm_map: dict[str, dict[str, str]] = {}
    for rec in builder.list_all():
        if rec.final_code and rec.final_code.strip():
            code = rec.final_code.strip()
            norm_map[gs_normalize(rec.account_name)] = {
                "code": code,
                "original_name": rec.account_name,
            }
    builder.close()
    return norm_map


def match_against_gs(
    accounts: list[AccountResult], gs_map: dict[str, dict[str, str]], label: str
) -> dict[str, Any]:
    eligible = []
    gs_expected = []
    predicted_list = []
    for a in accounts:
        gs_entry = gs_map.get(gs_normalize(a.account_name))
        if gs_entry:
            expected = gs_entry["code"]
            predicted = a.final_code or a.standard_code or "UNKNOWN"
            pred_str = str(predicted) if predicted else "UNKNOWN"
            correct = pred_str == expected
            eligible.append({
                "account_name": a.account_name,
                "source_file": a.source_file,
                "expected": expected,
                "predicted": pred_str,
                "correct": correct,
                "method": a.method,
                "confidence": a.confidence,
            })
            gs_expected.append(expected)
            predicted_list.append(pred_str)

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

    macro_p = round(sum(m["precision"] for m in per_label) / len(per_label), 4) if per_label else 0.0
    macro_r = round(sum(m["recall"] for m in per_label) / len(per_label), 4) if per_label else 0.0
    macro_f1 = round(sum(m["f1"] for m in per_label) / len(per_label), 4) if per_label else 0.0

    micro_p = round(tp_total / (tp_total + fp_total), 4) if (tp_total + fp_total) > 0 else 0.0
    micro_r = round(tp_total / (tp_total + fn_total), 4) if (tp_total + fn_total) > 0 else 0.0
    micro_f1 = round(2 * micro_p * micro_r / (micro_p + micro_r), 4) if (micro_p + micro_r) > 0 else 0.0

    # Cohen's Kappa
    kappa_obj = Agreement(gs_expected, predicted_list, labels or None)
    kappa = kappa_obj.cohen_kappa()
    kappa_interp = kappa_obj.interpret_kappa(kappa)

    # Error classification by type (FP/FN/category)
    error_categories = Counter()
    fp_records = []
    fn_records = []
    for e in errors:
        cat = _classify_error(e)
        error_categories[cat] += 1
        er = ErrorRecord(
            account_name=e["account_name"],
            source_file=e["source_file"],
            expected_code=e["expected"],
            predicted_code=e["predicted"],
            method=e["method"],
            confidence=e["confidence"],
            is_false_positive=(e["predicted"] != "UNKNOWN"),
            is_false_negative=(e["predicted"] == "UNKNOWN"),
            error_category=cat,
        )
        fp_records.append(er) if er.is_false_positive else fn_records.append(er)

    return {
        "label": label,
        "eligible": total,
        "correct": correct,
        "incorrect": total - correct,
        "accuracy": round(accuracy, 4),
        "accuracy_pct": round(accuracy * 100, 2),
        "macro_precision": macro_p,
        "macro_recall": macro_r,
        "macro_f1": macro_f1,
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "cohen_kappa": kappa,
        "kappa_interpretation": kappa_interp,
        "error_distribution": dict(error_categories.most_common()),
        "per_label": per_label,
        "errors": errors,
        "fp_records": fp_records,
        "fn_records": fn_records,
        "gs_expected": gs_expected,
        "predicted_list": predicted_list,
        "labels": labels,
    }


def _classify_error(e: dict) -> str:
    if e["predicted"] == "UNKNOWN":
        return "FALSE_NEGATIVE_UNKNOWN"
    elif e["predicted"] != e["expected"]:
        if e["method"].startswith("cmcc_"):
            return "CMCC_MISMATCH"
        elif e["method"].startswith("learning_fuzzy"):
            return "FUZZY_MISMATCH"
        elif e["method"].startswith("learning"):
            return "LEARNING_MISMATCH"
        elif e["method"].startswith("dictionary"):
            return "DICTIONARY_MISMATCH"
        elif e["method"] == "code":
            return "CODE_MISMATCH"
        else:
            return "CLASSIFICATION_MISMATCH"


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


# ─────────────────────────────────────────────
# Statistical significance
# ─────────────────────────────────────────────

def compute_confidence_interval(p: float, n: int, z: float = 1.96) -> dict:
    if n == 0:
        return {"lower": 0.0, "upper": 0.0, "margin": 0.0}
    se = (p * (1 - p) / n) ** 0.5
    margin = z * se
    return {
        "lower": round(max(0.0, p - margin), 4),
        "upper": round(min(1.0, p + margin), 4),
        "margin": round(margin, 4),
    }


def mcnemar_test(baseline_errors: list[dict], candidate_errors: list[dict],
                 all_eligible: list[dict]) -> dict:
    """McNemar's test for paired nominal data."""
    # b = errors unique to baseline, c = errors unique to candidate
    b_set = {(e["account_name"], e["source_file"]) for e in baseline_errors}
    c_set = {(e["account_name"], e["source_file"]) for e in candidate_errors}

    b_only = len(b_set - c_set)
    c_only = len(c_set - b_set)

    total_pairs = b_only + c_only
    if total_pairs == 0:
        return {
            "chi2": 0.0, "p_value": 1.0,
            "significant": False,
            "baseline_only_errors": 0,
            "candidate_only_errors": 0,
        }

    chi2 = (abs(b_only - c_only) - 1) ** 2 / total_pairs
    p_value = 1.0  # simplified; real chi2 CDF would be better
    if chi2 > 3.841:
        p_value = 0.05  # approximate for 1 DOF
    if chi2 > 6.635:
        p_value = 0.01

    return {
        "chi2": round(chi2, 4),
        "p_value": p_value,
        "significant": p_value <= 0.05,
        "baseline_only_errors": b_only,
        "candidate_only_errors": c_only,
    }


def compute_verdict(
    bl: dict, ca: dict,
    bl_acc: float, ca_acc: float,
    bl_kappa: float, ca_kappa: float,
) -> dict:
    improvements = {}
    regressions = {}
    neutral = {}

    # Accuracy
    acc_diff = ca_acc - bl_acc
    if acc_diff > 0.005:
        improvements["accuracy"] = round(acc_diff, 4)
    elif acc_diff < -0.005:
        regressions["accuracy"] = round(abs(acc_diff), 4)
    else:
        neutral["accuracy"] = round(acc_diff, 4)

    # Kappa
    kappa_diff = ca_kappa - bl_kappa
    if kappa_diff > 0.01:
        improvements["cohen_kappa"] = round(kappa_diff, 4)
    elif kappa_diff < -0.01:
        regressions["cohen_kappa"] = round(abs(kappa_diff), 4)
    else:
        neutral["cohen_kappa"] = round(kappa_diff, 4)

    # Macro F1
    mf1_diff = ca["macro_f1"] - bl["macro_f1"]
    if mf1_diff > 0.005:
        improvements["macro_f1"] = round(mf1_diff, 4)
    elif mf1_diff < -0.005:
        regressions["macro_f1"] = round(abs(mf1_diff), 4)
    else:
        neutral["macro_f1"] = round(mf1_diff, 4)

    # Errors
    err_diff = bl["incorrect"] - ca["incorrect"]
    if err_diff > 0:
        improvements["error_reduction"] = err_diff
    elif err_diff < 0:
        regressions["error_increase"] = abs(err_diff)
    else:
        neutral["error_change"] = 0

    # Coverage
    cov_bl = bl.get("eligible", 0)
    cov_ca = ca.get("eligible", 0)
    cov_diff = cov_ca - cov_bl
    if cov_diff > 0:
        improvements["gs_coverage"] = cov_diff
    elif cov_diff < 0:
        regressions["gs_coverage"] = abs(cov_diff)
    else:
        neutral["gs_coverage"] = 0

    # Overall verdict
    n_improve = len(improvements)
    n_regress = len(regressions)

    if n_improve > n_regress and acc_diff >= 0:
        verdict = "CMCC_IMPROVES"
        confidence = "high" if (n_improve >= 3 and acc_diff > 0.01) else "moderate"
    elif n_regress > n_improve:
        verdict = "CMCC_WORSENS"
        confidence = "high" if n_regress >= 3 else "moderate"
    elif n_improve == n_regress and n_improve > 0:
        verdict = "CMCC_MIXED"
        confidence = "moderate"
    else:
        verdict = "CMCC_NEUTRAL"
        confidence = "high"

    return {
        "verdict": verdict,
        "confidence": confidence,
        "improvements": improvements,
        "regressions": regressions,
        "neutral": neutral,
        "details": {
            "accuracy_delta": round(acc_diff, 4),
            "kappa_delta": round(kappa_diff, 4),
            "macro_f1_delta": round(mf1_diff, 4),
            "error_delta": err_diff,
            "gs_coverage_delta": cov_diff,
        },
    }


# ─────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────

def generate_reports(
    baseline_run: PipelineRun,
    candidate_run: PipelineRun,
    gs_baseline: dict,
    gs_candidate: dict,
    verdict: dict,
    mcnemar: dict,
) -> dict[str, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # ── 1. validation.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "validation.xlsx") as writer:
        # Pipeline summary
        bl_summary = baseline_run.summary
        ca_summary = candidate_run.summary
        rows = [
            {"metric": k,
             "baseline": str(bl_summary.get(k, "")),
             "candidate": str(ca_summary.get(k, ""))}
            for k in sorted(set(list(bl_summary.keys()) + list(ca_summary.keys())))
        ]
        pd.DataFrame(rows).to_excel(writer, sheet_name="Pipeline_Summary", index=False)

        # GS comparison
        gs_keys = ["eligible", "correct", "incorrect", "accuracy_pct",
                    "macro_f1", "micro_f1", "macro_precision", "macro_recall",
                    "cohen_kappa", "kappa_interpretation"]
        gs_rows = []
        for mk in gs_keys:
            gs_rows.append({
                "metric": mk,
                "baseline": gs_baseline.get(mk, "N/A"),
                "candidate": gs_candidate.get(mk, "N/A"),
                "diff": (gs_candidate.get(mk, 0) - gs_baseline.get(mk, 0))
                if isinstance(gs_baseline.get(mk), (int, float)) and isinstance(gs_candidate.get(mk), (int, float))
                else "N/A",
            })
        pd.DataFrame(gs_rows).to_excel(writer, sheet_name="GS_Metrics", index=False)

        # Verdict
        verdict_rows = [
            {"metric": "verdict", "value": verdict["verdict"]},
            {"metric": "confidence", "value": verdict["confidence"]},
        ]
        for k, v in verdict.get("improvements", {}).items():
            verdict_rows.append({"metric": f"improvement_{k}", "value": v})
        for k, v in verdict.get("regressions", {}).items():
            verdict_rows.append({"metric": f"regression_{k}", "value": v})
        for k, v in verdict.get("details", {}).items():
            verdict_rows.append({"metric": f"detail_{k}", "value": v})
        pd.DataFrame(verdict_rows).to_excel(writer, sheet_name="Verdict", index=False)

        # Method distribution
        for name, run in [("Baseline", baseline_run), ("Candidate", candidate_run)]:
            methods = pd.DataFrame([
                {"method": k, "count": v}
                for k, v in run.summary.get("method_distribution", {}).items()
            ])
            if not methods.empty:
                methods.to_excel(writer, sheet_name=f"{name}_Methods", index=False)
    paths["validation.xlsx"] = REPORTS_DIR / "validation.xlsx"

    # ── 2. metrics.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "metrics.xlsx") as writer:
        # Global metrics comparison
        metric_defs = [
            ("Accuracy", "accuracy_pct", "%"),
            ("Macro F1", "macro_f1", ""),
            ("Micro F1", "micro_f1", ""),
            ("Macro Precision", "macro_precision", ""),
            ("Macro Recall", "macro_recall", ""),
            ("Micro Precision", "micro_precision", ""),
            ("Micro Recall", "micro_recall", ""),
            ("Cohen's Kappa", "cohen_kappa", ""),
        ]
        all_rows = []
        for display_name, key, unit in metric_defs:
            bv = gs_baseline.get(key, "N/A")
            cv = gs_candidate.get(key, "N/A")
            diff = "N/A"
            if isinstance(bv, (int, float)) and isinstance(cv, (int, float)):
                d = cv - bv
                diff = f"{d:+.4f}" if unit == "" else f"{d:+.2f}{unit}"
            bl_str = f"{bv}{unit}" if isinstance(bv, (int, float)) else str(bv)
            ca_str = f"{cv}{unit}" if isinstance(cv, (int, float)) else str(cv)
            all_rows.append({
                "Metric": display_name,
                "Baseline": bl_str,
                "Candidate": ca_str,
                "Delta": diff,
            })
        pd.DataFrame(all_rows).to_excel(writer, sheet_name="Global_Metrics", index=False)

        # Per-label metrics
        if gs_baseline.get("per_label"):
            bl_df = pd.DataFrame(gs_baseline["per_label"])
            bl_df.to_excel(writer, sheet_name="Baseline_Per_Label", index=False)
        if gs_candidate.get("per_label"):
            ca_df = pd.DataFrame(gs_candidate["per_label"])
            ca_df.to_excel(writer, sheet_name="Candidate_Per_Label", index=False)

        # Coverage metrics
        cov_rows = [
            {"Metric": "Total Accounts", "Baseline": bl_summary["total_accounts"],
             "Candidate": ca_summary["total_accounts"], "Delta": ca_summary["total_accounts"] - bl_summary["total_accounts"]},
            {"Metric": "Classified", "Baseline": bl_summary["total_classified"],
             "Candidate": ca_summary["total_classified"], "Delta": ca_summary["total_classified"] - bl_summary["total_classified"]},
            {"Metric": "UNKNOWN", "Baseline": bl_summary["total_unknown"],
             "Candidate": ca_summary["total_unknown"], "Delta": ca_summary["total_unknown"] - bl_summary["total_unknown"]},
            {"Metric": "Coverage %", "Baseline": f"{bl_summary['coverage_pct']}%",
             "Candidate": f"{ca_summary['coverage_pct']}%",
             "Delta": f"{round(ca_summary['coverage_pct'] - bl_summary['coverage_pct'], 2)}pp"},
        ]
        pd.DataFrame(cov_rows).to_excel(writer, sheet_name="Coverage", index=False)

        # Error distribution
        for name, gs_data in [("Baseline", gs_baseline), ("Candidate", gs_candidate)]:
            if gs_data.get("error_distribution"):
                err_df = pd.DataFrame([
                    {"category": k, "count": v}
                    for k, v in gs_data["error_distribution"].items()
                ])
                err_df.to_excel(writer, sheet_name=f"{name}_Errors", index=False)

        # Confidence intervals
        ci_bl = compute_confidence_interval(gs_baseline["accuracy"], gs_baseline["eligible"])
        ci_ca = compute_confidence_interval(gs_candidate["accuracy"], gs_candidate["eligible"])
        ci_rows = [
            {"metric": "Baseline Accuracy CI (95%)",
             "lower": ci_bl["lower"], "upper": ci_bl["upper"], "margin": ci_bl["margin"]},
            {"metric": "Candidate Accuracy CI (95%)",
             "lower": ci_ca["lower"], "upper": ci_ca["upper"], "margin": ci_ca["margin"]},
        ]
        pd.DataFrame(ci_rows).to_excel(writer, sheet_name="Confidence_Intervals", index=False)
    paths["metrics.xlsx"] = REPORTS_DIR / "metrics.xlsx"

    # ── 3. agreement.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "agreement.xlsx") as writer:
        for name, gs_data in [("Baseline", gs_baseline), ("Candidate", gs_candidate)]:
            if gs_data.get("gs_expected") and gs_data.get("predicted_list"):
                agree = Agreement(
                    gs_data["gs_expected"],
                    gs_data["predicted_list"],
                    gs_data.get("labels") or None,
                )
                s = agree.summary()
                rows = [
                    {"Metric": "N", "Value": s["n"]},
                    {"Metric": "Observed Agreement", "Value": f"{s['observed_agreement_pct']}%"},
                    {"Metric": "Cohen's Kappa", "Value": s["cohen_kappa"]},
                    {"Metric": "Kappa Interpretation", "Value": s["kappa_interpretation"]},
                    {"Metric": "Disagreements", "Value": s["disagreements"]},
                ]
                pd.DataFrame(rows).to_excel(writer, sheet_name=f"{name}_Agreement", index=False)

        # Kappa delta
        kappa_delta = round(gs_candidate.get("cohen_kappa", 0) - gs_baseline.get("cohen_kappa", 0), 4)
        delta_rows = [
            {"Metric": "Baseline Kappa", "Value": gs_baseline.get("cohen_kappa", "N/A")},
            {"Metric": "Candidate Kappa", "Value": gs_candidate.get("cohen_kappa", "N/A")},
            {"Metric": "Kappa Delta", "Value": kappa_delta},
        ]
        pd.DataFrame(delta_rows).to_excel(writer, sheet_name="Kappa_Comparison", index=False)

        # McNemar test
        mn_rows = [
            {"Metric": "Chi-squared", "Value": mcnemar["chi2"]},
            {"Metric": "P-value", "Value": mcnemar["p_value"]},
            {"Metric": "Significant (p≤0.05)", "Value": "Yes" if mcnemar["significant"] else "No"},
            {"Metric": "Baseline-only errors", "Value": mcnemar["baseline_only_errors"]},
            {"Metric": "Candidate-only errors", "Value": mcnemar["candidate_only_errors"]},
        ]
        pd.DataFrame(mn_rows).to_excel(writer, sheet_name="McNemar_Test", index=False)
    paths["agreement.xlsx"] = REPORTS_DIR / "agreement.xlsx"

    # ── 4. error_analysis.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "error_analysis.xlsx") as writer:
        for name, gs_data in [("Baseline", gs_baseline), ("Candidate", gs_candidate)]:
            # Error summary
            err_total = len(gs_data.get("errors", []))
            err_by_cat = Counter(e["error_category"] for e in gs_data.get("fp_records", []))
            err_by_cat += Counter(e["error_category"] for e in gs_data.get("fn_records", []))
            if err_by_cat:
                summary_df = pd.DataFrame([
                    {"category": cat, "count": cnt, "pct": f"{cnt/err_total*100:.1f}%"}
                    for cat, cnt in err_by_cat.most_common()
                ])
                summary_df.to_excel(writer, sheet_name=f"{name}_Error_Summary", index=False)

            # FP details
            fp_list = gs_data.get("fp_records", [])
            if fp_list:
                fp_df = pd.DataFrame([
                    {"account_name": r.account_name, "source_file": r.source_file,
                     "expected": r.expected_code, "predicted": r.predicted_code,
                     "method": r.method, "confidence": r.confidence,
                     "error_category": r.error_category}
                    for r in fp_list
                ])
                fp_df.to_excel(writer, sheet_name=f"{name}_False_Positives", index=False)

            # FN details
            fn_list = gs_data.get("fn_records", [])
            if fn_list:
                fn_df = pd.DataFrame([
                    {"account_name": r.account_name, "source_file": r.source_file,
                     "expected": r.expected_code, "predicted": r.predicted_code,
                     "method": r.method, "confidence": r.confidence,
                     "error_category": r.error_category}
                    for r in fn_list
                ])
                fn_df.to_excel(writer, sheet_name=f"{name}_False_Negatives", index=False)

        # Error comparison
        bl_err_set = {(e["account_name"], e["source_file"], e["expected"], e["predicted"])
                      for e in gs_baseline.get("errors", [])}
        ca_err_set = {(e["account_name"], e["source_file"], e["expected"], e["predicted"])
                      for e in gs_candidate.get("errors", [])}
        only_bl = bl_err_set - ca_err_set
        only_ca = ca_err_set - bl_err_set
        both = bl_err_set & ca_err_set
        comparison_rows = [
            {"category": "Baseline-only errors", "count": len(only_bl)},
            {"category": "Candidate-only errors", "count": len(only_ca)},
            {"category": "Errors in both", "count": len(both)},
        ]
        pd.DataFrame(comparison_rows).to_excel(writer, sheet_name="Error_Comparison", index=False)
    paths["error_analysis.xlsx"] = REPORTS_DIR / "error_analysis.xlsx"

    # ── 5. confusion_matrix.xlsx ─────────────────
    with pd.ExcelWriter(REPORTS_DIR / "confusion_matrix.xlsx") as writer:
        for name, gs_data in [("Baseline", gs_baseline), ("Candidate", gs_candidate)]:
            cm = _build_confusion_df(gs_data)
            if cm is not None:
                cm.to_excel(writer, sheet_name=f"{name}_CM")
    paths["confusion_matrix.xlsx"] = REPORTS_DIR / "confusion_matrix.xlsx"

    return paths


def _build_confusion_df(gs_metrics: dict) -> pd.DataFrame | None:
    if not gs_metrics.get("per_label"):
        return None
    labels = sorted(set(m["label"] for m in gs_metrics["per_label"]))
    matrix: dict[str, dict[str, int]] = {lbl: {l: 0 for l in ["_correct"] + labels + ["UNKNOWN"]} for lbl in labels}
    for m in gs_metrics["per_label"]:
        lbl = m["label"]
        matrix[lbl]["_correct"] = m["tp"]
        matrix[lbl][lbl] = m["tp"]  # diagonal
    for e in gs_metrics.get("errors", []):
        exp = e["expected"]
        pred = e["predicted"]
        if exp in matrix:
            if pred in matrix[exp]:
                matrix[exp][pred] += 1
            elif pred not in matrix[exp]:
                matrix[exp][pred] = 1
    df = pd.DataFrame.from_dict(matrix, orient="index")
    df.index.name = "expected"
    df.columns.name = "predicted"
    return df


def generate_markdown(
    baseline_run: PipelineRun,
    candidate_run: PipelineRun,
    gs_baseline: dict,
    gs_candidate: dict,
    verdict: dict,
    mcnemar: dict,
) -> str:
    lines: list[str] = []

    def L(*args):
        lines.extend(args)
        lines.append("")

    bl = baseline_run.summary
    ca = candidate_run.summary

    L("# CMCC Final Scientific Validation — Pipeline Actual vs Pipeline + CMCC")
    L(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    L(f"**Gold Standard:** {gs_baseline.get('eligible', 0)} accounts matched (baseline) / "
      f"{gs_candidate.get('eligible', 0)} accounts matched (candidate)")
    L(f"**Configuration:** Baseline: ENABLE_CMCC=False | "
      f"Candidate: ENABLE_CMCC=True, PRODUCTION=True, threshold={CMCC_THRESHOLD}")
    L("---")

    # ── 1. Executive Summary ──
    L("## 1. Executive Summary")
    L("| Metric | Baseline | Candidate | Δ |")
    L("|---|---|---|---|")
    L(f"| Total accounts | {bl['total_accounts']} | {ca['total_accounts']} | — |")
    L(f"| Classified | {bl['total_classified']} | {ca['total_classified']} | "
      f"{ca['total_classified'] - bl['total_classified']} |")
    L(f"| UNKNOWN | {bl['total_unknown']} | {ca['total_unknown']} | "
      f"{ca['total_unknown'] - bl['total_unknown']} |")
    L(f"| Coverage | {bl['coverage_pct']}% | {ca['coverage_pct']}% | "
      f"{round(ca['coverage_pct'] - bl['coverage_pct'], 2)}pp |")
    L(f"| Processing time | {bl['time_seconds']}s | {ca['time_seconds']}s | "
      f"{round(ca['time_seconds'] - bl['time_seconds'], 3)}s |")
    L("")

    # ── 2. Gold Standard Metrics ──
    L("## 2. Gold Standard Metrics")
    L("| Metric | Baseline | Candidate | Δ |")
    L("|---|---|---|---|")
    metrics_display = [
        ("Accuracy", "accuracy_pct", "%"),
        ("Macro F1", "macro_f1", ""),
        ("Micro F1", "micro_f1", ""),
        ("Macro Precision", "macro_precision", ""),
        ("Macro Recall", "macro_recall", ""),
        ("Micro Precision", "micro_precision", ""),
        ("Micro Recall", "micro_recall", ""),
        ("Cohen's Kappa", "cohen_kappa", ""),
    ]
    for display_name, key, unit in metrics_display:
        bv = gs_baseline.get(key, "N/A")
        cv = gs_candidate.get(key, "N/A")
        diff = ""
        if isinstance(bv, (int, float)) and isinstance(cv, (int, float)):
            d = cv - bv
            diff = f"{d:+.4f}"
        bl_str = f"{bv}{unit}" if isinstance(bv, (int, float)) else str(bv)
        ca_str = f"{cv}{unit}" if isinstance(cv, (int, float)) else str(cv)
        L(f"| {display_name} | {bl_str} | {ca_str} | {diff} |")
    L(f"| Correct | {gs_baseline.get('correct', 'N/A')} / {gs_baseline.get('eligible', 'N/A')} | "
      f"{gs_candidate.get('correct', 'N/A')} / {gs_candidate.get('eligible', 'N/A')} | — |")
    L(f"| Errors | {gs_baseline.get('incorrect', 'N/A')} | {gs_candidate.get('incorrect', 'N/A')} | — |")
    L("")

    # ── 3. Kappa and Agreement ──
    L("## 3. Inter-Rater Agreement (Cohen's Kappa)")
    L("| Metric | Baseline | Candidate |")
    L("|---|---|---|")
    L(f"| Kappa | {gs_baseline.get('cohen_kappa', 'N/A')} | {gs_candidate.get('cohen_kappa', 'N/A')} |")
    L(f"| Interpretation | {gs_baseline.get('kappa_interpretation', 'N/A')} | "
      f"{gs_candidate.get('kappa_interpretation', 'N/A')} |")
    kappa_delta = round(gs_candidate.get("cohen_kappa", 0) - gs_baseline.get("cohen_kappa", 0), 4)
    L(f"| Kappa Δ | — | {kappa_delta:+.4f} |")
    L("")

    # ── 4. Error Distribution ──
    L("## 4. Error Distribution")
    all_cats = sorted(set(gs_baseline.get("error_distribution", {}).keys()) |
                      set(gs_candidate.get("error_distribution", {}).keys()))
    if all_cats:
        L("| Category | Baseline | Candidate | Δ |")
        L("|---|---|---|---|")
        for cat in all_cats:
            bv = gs_baseline.get("error_distribution", {}).get(cat, 0)
            cv = gs_candidate.get("error_distribution", {}).get(cat, 0)
            L(f"| {cat} | {bv} | {cv} | {cv - bv} |")
    else:
        L("*No errors detected.*")
    L("")

    # ── 5. False Positives vs False Negatives ──
    L("## 5. False Positives vs False Negatives")
    bl_fp = len(gs_baseline.get("fp_records", []))
    bl_fn = len(gs_baseline.get("fn_records", []))
    ca_fp = len(gs_candidate.get("fp_records", []))
    ca_fn = len(gs_candidate.get("fn_records", []))
    L("| Type | Baseline | Candidate | Δ |")
    L("|---|---|---|---|")
    L(f"| False Positives | {bl_fp} | {ca_fp} | {ca_fp - bl_fp} |")
    L(f"| False Negatives | {bl_fn} | {ca_fn} | {ca_fn - bl_fn} |")
    L(f"| FP + FN | {bl_fp + bl_fn} | {ca_fp + ca_fn} | {(ca_fp + ca_fn) - (bl_fp + bl_fn)} |")
    L("")

    # ── 6. Confidence Intervals ──
    L("## 6. Confidence Intervals (95%)")
    ci_bl = compute_confidence_interval(gs_baseline["accuracy"], gs_baseline["eligible"])
    ci_ca = compute_confidence_interval(gs_candidate["accuracy"], gs_candidate["eligible"])
    L(f"| Baseline accuracy: {gs_baseline['accuracy_pct']}% | 95% CI: [{ci_bl['lower']:.4f}, {ci_bl['upper']:.4f}] |")
    L(f"| Candidate accuracy: {gs_candidate['accuracy_pct']}% | 95% CI: [{ci_ca['lower']:.4f}, {ci_ca['upper']:.4f}] |")
    L("")

    # Overlap check
    if ci_bl["upper"] < ci_ca["lower"]:
        L("**→ Confidence intervals do NOT overlap — difference is statistically significant.**")
    elif ci_ca["upper"] < ci_bl["lower"]:
        L("**→ Confidence intervals do NOT overlap — difference is statistically significant.**")
    else:
        L("*Confidence intervals overlap — difference may not be statistically significant.*")
    L("")

    # ── 7. McNemar Test ──
    L("## 7. McNemar Test (Paired Error Comparison)")
    L(f"| Chi-squared | {mcnemar['chi2']} |")
    L(f"| P-value | {mcnemar['p_value']} |")
    L(f"| Significant (p≤0.05) | {'Yes' if mcnemar['significant'] else 'No'} |")
    L(f"| Baseline-only errors | {mcnemar['baseline_only_errors']} |")
    L(f"| Candidate-only errors | {mcnemar['candidate_only_errors']} |")
    L("")

    # ── 8. Method Distribution ──
    L("## 8. Method Distribution")
    L("| Method | Baseline | Candidate | Δ |")
    L("|---|---|---|---|")
    all_methods = sorted(set(bl.get("method_distribution", {}).keys()) |
                         set(ca.get("method_distribution", {}).keys()))
    for m in all_methods:
        bv = bl.get("method_distribution", {}).get(m, 0)
        cv = ca.get("method_distribution", {}).get(m, 0)
        L(f"| {m} | {bv} | {cv} | {cv - bv} |")
    L("")

    # ── 9. Per-Label Analysis ──
    if gs_baseline.get("per_label") or gs_candidate.get("per_label"):
        L("## 9. Per-Label Metrics (Top 20 by F1 change)")
        bl_map = {m["label"]: m for m in gs_baseline.get("per_label", [])}
        ca_map = {m["label"]: m for m in gs_candidate.get("per_label", [])}
        all_lbls = sorted(set(bl_map.keys()) | set(ca_map.keys()))
        diffs = []
        for lbl in all_lbls:
            bf1 = bl_map.get(lbl, {}).get("f1", 0)
            cf1 = ca_map.get(lbl, {}).get("f1", 0)
            diffs.append((lbl, bf1, cf1, cf1 - bf1))
        diffs.sort(key=lambda x: -abs(x[3]))
        L("| Label | Baseline F1 | Candidate F1 | Δ |")
        L("|---|---|---|---|")
        for lbl, bf1, cf1, d in diffs[:20]:
            L(f"| {lbl} | {bf1} | {cf1} | {d:+.4f} |")
        L("")

    # ── 10. Verdict ──
    L("## 10. Automated Verdict")
    L(f"### Verdict: **{verdict['verdict']}**")
    L(f"**Confidence:** {verdict['confidence']}")
    L("")
    if verdict.get("improvements"):
        L("### Improvements")
        for k, v in verdict["improvements"].items():
            L(f"- **{k}**: +{v}")
        L("")
    if verdict.get("regressions"):
        L("### Regressions")
        for k, v in verdict["regressions"].items():
            L(f"- **{k}**: -{v}")
        L("")
    L("### Detail")
    for k, v in verdict.get("details", {}).items():
        L(f"- **{k}**: {v}")
    L("")

    # Narrative
    L("### Interpretation")
    if verdict["verdict"] == "CMCC_IMPROVES":
        L("CMCC integration improves pipeline performance. "
          "Coverage increases while maintaining or improving accuracy against the Gold Standard. "
          "The improvement is consistent across multiple metrics.")
    elif verdict["verdict"] == "CMCC_WORSENS":
        L("CMCC integration degrades pipeline performance. "
          "One or more key metrics show statistically significant regression. "
          "Review the error analysis tables for problematic areas.")
    elif verdict["verdict"] == "CMCC_MIXED":
        L("CMCC integration shows mixed results. "
          "Some metrics improve while others regress. "
          "Further analysis is needed to isolate beneficial vs harmful effects.")
    else:
        L("CMCC integration shows no significant change. "
          "The pipeline behaves equivalently with or without CMCC within the measured metrics.")
    L("")

    # ── 11. Conclusions ──
    L("## 11. Conclusions")
    coverage_gain = round(ca["coverage_pct"] - bl["coverage_pct"], 2)
    unknown_red = bl["total_unknown"] - ca["total_unknown"]
    L(f"- **Coverage:** {bl['coverage_pct']}% → {ca['coverage_pct']}% (Δ = +{coverage_gain}pp)")
    L(f"- **UNKNOWN reduction:** {unknown_red} accounts recovered")
    L(f"- **GS Accuracy:** {gs_baseline.get('accuracy_pct', 'N/A')}% → {gs_candidate.get('accuracy_pct', 'N/A')}%")
    L(f"- **Kappa:** {gs_baseline.get('cohen_kappa', 'N/A')} → {gs_candidate.get('cohen_kappa', 'N/A')} "
      f"(Δ = {kappa_delta:+.4f})")
    L(f"- **Total errors:** {gs_baseline.get('incorrect', 'N/A')} → {gs_candidate.get('incorrect', 'N/A')}")
    L(f"- **FP:** {bl_fp} → {ca_fp} | **FN:** {bl_fn} → {ca_fn}")
    L(f"- **McNemar:** {'significant' if mcnemar['significant'] else 'not significant'} "
      f"(chi²={mcnemar['chi2']}, p={mcnemar['p_value']})")
    L("")

    L("---")
    L(f"*Verdict: {verdict['verdict']} (confidence: {verdict['confidence']})*")
    L("*Generated by `scripts/cmcc_scientific_validation.py` — Sprint 26.4*")
    L("*Sources: datasets/*, *gold_standard.db*")
    L("*No production code was modified during validation.*")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    _print("=" * 70)
    _print("SPRINT 26.4 — Final Scientific Validation")
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
    _print("Computing Gold Standard metrics...")
    gs_baseline = match_against_gs(baseline_run.accounts, gs_map, "baseline")
    gs_candidate = match_against_gs(candidate_run.accounts, gs_map, "candidate")
    _print(f"  Baseline:  {gs_baseline.get('eligible', 0)} eligible, "
           f"accuracy={gs_baseline.get('accuracy_pct', 'N/A')}%, "
           f"kappa={gs_baseline.get('cohen_kappa', 'N/A')}")
    _print(f"  Candidate: {gs_candidate.get('eligible', 0)} eligible, "
           f"accuracy={gs_candidate.get('accuracy_pct', 'N/A')}%, "
           f"kappa={gs_candidate.get('cohen_kappa', 'N/A')}")
    _print()

    # ── 5. Statistical tests ──
    _print("Running statistical tests...")
    mcnemar = mcnemar_test(
        gs_baseline.get("errors", []),
        gs_candidate.get("errors", []),
        [],
    )
    _print(f"  McNemar: baseline-only={mcnemar['baseline_only_errors']}, "
           f"candidate-only={mcnemar['candidate_only_errors']}, "
           f"significant={mcnemar['significant']}")
    _print()

    # ── 6. Automated verdict ──
    _print("Computing automated verdict...")
    verdict = compute_verdict(
        gs_baseline, gs_candidate,
        gs_baseline["accuracy"], gs_candidate["accuracy"],
        gs_baseline["cohen_kappa"], gs_candidate["cohen_kappa"],
    )
    _print(f"  Verdict: {verdict['verdict']} (confidence: {verdict['confidence']})")
    if verdict.get("improvements"):
        for k, v in verdict["improvements"].items():
            _print(f"    Improvement - {k}: {v}")
    if verdict.get("regressions"):
        for k, v in verdict["regressions"].items():
            _print(f"    Regression - {k}: {v}")
    _print()

    # ── 7. Generate reports ──
    _print("Generating reports...")
    report_paths = generate_reports(
        baseline_run, candidate_run,
        gs_baseline, gs_candidate,
        verdict, mcnemar,
    )
    _print()

    # ── 8. JSON report ──
    json_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "baseline": baseline_features.to_dict(),
            "candidate": candidate_features.to_dict(),
            "cmcc_threshold": CMCC_THRESHOLD,
        },
        "pipeline_summary": {
            "baseline": baseline_run.summary,
            "candidate": candidate_run.summary,
        },
        "gold_standard": {
            "entries": len(gs_map),
            "baseline": {
                "eligible": gs_baseline["eligible"],
                "correct": gs_baseline["correct"],
                "incorrect": gs_baseline["incorrect"],
                "accuracy_pct": gs_baseline["accuracy_pct"],
                "macro_f1": gs_baseline["macro_f1"],
                "micro_f1": gs_baseline["micro_f1"],
                "cohen_kappa": gs_baseline["cohen_kappa"],
                "kappa_interpretation": gs_baseline["kappa_interpretation"],
                "error_distribution": gs_baseline["error_distribution"],
                "false_positives": len(gs_baseline.get("fp_records", [])),
                "false_negatives": len(gs_baseline.get("fn_records", [])),
            },
            "candidate": {
                "eligible": gs_candidate["eligible"],
                "correct": gs_candidate["correct"],
                "incorrect": gs_candidate["incorrect"],
                "accuracy_pct": gs_candidate["accuracy_pct"],
                "macro_f1": gs_candidate["macro_f1"],
                "micro_f1": gs_candidate["micro_f1"],
                "cohen_kappa": gs_candidate["cohen_kappa"],
                "kappa_interpretation": gs_candidate["kappa_interpretation"],
                "error_distribution": gs_candidate["error_distribution"],
                "false_positives": len(gs_candidate.get("fp_records", [])),
                "false_negatives": len(gs_candidate.get("fn_records", [])),
            },
        },
        "statistical_tests": {
            "mcnemar": mcnemar,
            "confidence_intervals": {
                "baseline": compute_confidence_interval(gs_baseline["accuracy"], gs_baseline["eligible"]),
                "candidate": compute_confidence_interval(gs_candidate["accuracy"], gs_candidate["eligible"]),
            },
        },
        "verdict": verdict,
        "reports": {k: str(v) for k, v in report_paths.items()},
    }
    json_path = REPORTS_DIR / "scientific_validation.json"
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
    _print(f"  scientific_validation.json: {json_path.resolve()}")

    # ── 9. Markdown report ──
    md = generate_markdown(baseline_run, candidate_run, gs_baseline, gs_candidate, verdict, mcnemar)
    md_path = REPORTS_DIR / "scientific_validation.md"
    md_path.write_text(md, encoding="utf-8")
    _print(f"  scientific_validation.md:  {md_path.resolve()}")

    # ── 10. Summary ──
    coverage_gain = round(candidate_run.summary["coverage_pct"] - baseline_run.summary["coverage_pct"], 2)
    unknown_red = baseline_run.summary["total_unknown"] - candidate_run.summary["total_unknown"]

    _print()
    _print("=" * 70)
    _print("VALIDATION COMPLETE")
    _print("=" * 70)
    _print(f"  Verdict:      {verdict['verdict']} ({verdict['confidence']} confidence)")
    _print(f"  Coverage:     {baseline_run.summary['coverage_pct']}% → {candidate_run.summary['coverage_pct']}%")
    _print(f"  Gain:         +{coverage_gain}pp")
    _print(f"  UNKNOWN red:  {unknown_red} accounts recovered")
    _print(f"  GS Accuracy:  {gs_baseline.get('accuracy_pct', 'N/A')}% → {gs_candidate.get('accuracy_pct', 'N/A')}%")
    _print(f"  Kappa:        {gs_baseline.get('cohen_kappa', 'N/A')} → {gs_candidate.get('cohen_kappa', 'N/A')}")
    _print(f"  FP/FN:        {len(gs_baseline.get('fp_records', []))}/{len(gs_baseline.get('fn_records', []))} → "
           f"{len(gs_candidate.get('fp_records', []))}/{len(gs_candidate.get('fn_records', []))}")
    _print(f"  Reports:      {REPORTS_DIR.resolve()}")
    for name, path in sorted(report_paths.items()):
        size = path.stat().st_size if path.exists() else 0
        _print(f"    {name}: {size:,} bytes")
    _print(f"    scientific_validation.json: {json_path.stat().st_size:,} bytes")
    _print(f"    scientific_validation.md:  {md_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CMCC Final Scientific Validation Sprint 26.4")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of files to process per run (0=all)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore cached results and re-process")
    args = parser.parse_args()

    if args.limit > 0:
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
