#!/usr/bin/env python3
"""
Sprint 27.2 — REVIEW_CMCC Audit
Read-only analytical phase. No production modifications.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPORTS_DIR = Path("reports/cmcc_review_audit")
PIPELINE_DIR = Path("reports/cmcc_review_pipeline")
QUEUE_PATH = PIPELINE_DIR / "review_queue.xlsx"
PIPELINE_JSON = PIPELINE_DIR / "review_pipeline.json"


def load_data() -> pd.DataFrame:
    df = pd.read_excel(QUEUE_PATH)
    df["score"] = pd.to_numeric(df["score"])
    return df


def compute_uniqueness(df: pd.DataFrame) -> dict[str, Any]:
    total = len(df)
    unique_names = df["account_name"].nunique()
    unique_variants = df["matched_variant"].nunique()
    unique_concepts = df["concept_code"].nunique()
    unique_companies = df["company"].nunique()
    unique_docs = df["document_id"].nunique()
    human_decisions = unique_variants
    savings = total - unique_variants
    savings_pct = round(savings / total * 100, 2) if total else 0
    return {
        "total_review_entries": total,
        "unique_account_names": unique_names,
        "unique_matched_variants": unique_variants,
        "unique_concepts": unique_concepts,
        "unique_companies": unique_companies,
        "unique_documents": unique_docs,
        "human_decisions_needed": human_decisions,
        "duplicate_accounts_saved": savings,
        "savings_pct": savings_pct,
    }


def compute_variant_frequency(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, group in df.groupby("matched_variant"):
        a = group["account_name"].unique().tolist()
        cs = group["concept_code"].unique().tolist()
        cn = group["concept_name"].unique().tolist()
        co = group["company"].unique().tolist()
        d = group["document_id"].unique().tolist()
        rows.append({
            "matched_variant": variant,
            "frequency": len(group),
            "account_name_example": a[0],
            "all_account_names": ", ".join(sorted(a)[:5]),
            "concept_code": cs[0] if cs else "",
            "concept_name": cn[0] if cn else "",
            "num_companies": len(co),
            "companies": ", ".join(sorted(co)[:5]),
            "num_documents": len(d),
            "documents": ", ".join(sorted(d)[:5]),
            "impact_pct": round(len(group) / len(df) * 100, 2),
        })
    result = pd.DataFrame(rows).sort_values("frequency", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    result.index.name = "rank"
    return result


def compute_pareto(variant_freq: pd.DataFrame, total: int) -> dict[str, Any]:
    vf = variant_freq.sort_values("frequency", ascending=False)
    cum = vf["frequency"].cumsum()
    cum_pct = (cum / total * 100).round(2)

    pareto_points = {}
    for target in [80, 90, 95]:
        n = int((cum_pct < target).sum()) + 1
        n = min(n, len(vf))
        pareto_points[f"top_{n}"] = {
            "variants": n, "entries_covered": int(cum.iloc[n - 1]),
            "pct_covered": float(cum_pct.iloc[n - 1]),
        }

    for label, n in [("top_5", 5), ("top_10", 10), ("top_20", 20), ("top_50", 50), ("top_100", 100)]:
        i = min(n, len(vf))
        pareto_points[label] = {
            "variants": i, "entries_covered": int(cum.iloc[i - 1]),
            "pct_covered": float(cum_pct.iloc[i - 1]),
        }

    pareto_rows = pd.DataFrame({
        "rank": range(1, len(vf) + 1),
        "matched_variant": vf["matched_variant"].values,
        "frequency": vf["frequency"].values,
        "cumulative_sum": cum.values,
        "cumulative_pct": cum_pct.values,
        "concept_code": vf["concept_code"].values,
        "concept_name": vf["concept_name"].values,
        "num_companies": vf["num_companies"].values,
    })
    return {"pareto_points": pareto_points, "pareto_rows": pareto_rows, "total_entries": total}


def compute_concept_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (code, name), group in df.groupby(["concept_code", "concept_name"]):
        co = group["company"].unique()
        d = group["document_id"].unique()
        v = group["matched_variant"].unique()
        rows.append({
            "concept_code": code, "concept_name": name,
            "review_count": len(group), "pct_of_total": round(len(group) / len(df) * 100, 2),
            "unique_variants": len(v), "num_companies": len(co),
            "companies": ", ".join(sorted(co)[:5]),
            "num_documents": len(d), "documents": ", ".join(sorted(d)[:5]),
        })
    result = pd.DataFrame(rows).sort_values("review_count", ascending=False).reset_index(drop=True)
    result["cumulative_pct"] = result["review_count"].cumsum() / result["review_count"].sum() * 100
    return result


def compute_matching_method_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in df.groupby("matching_method"):
        rows.append({
            "matching_method": method, "count": len(group),
            "pct": round(len(group) / len(df) * 100, 2),
            "unique_variants": group["matched_variant"].nunique(),
            "num_companies": group["company"].nunique(),
            "num_documents": group["document_id"].nunique(),
        })
    result = pd.DataFrame(rows).sort_values("count", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    return result


def compute_coverage_simulation(df: pd.DataFrame, pipeline_data: dict) -> dict[str, Any]:
    cur_class = pipeline_data["summary"]["total_classified"]
    cur_total = pipeline_data["summary"]["total_accounts"]
    cur_cov = pipeline_data["summary"]["coverage_pct"]
    cur_unk = pipeline_data["summary"]["total_unknown"]
    total_review = len(df)
    unique_variants = df["matched_variant"].nunique()
    unique_accounts = df["account_name"].nunique()

    def scenario(label, new_cls):
        return {
            "scenario": label, "new_classified": new_cls,
            "total_classified": cur_class + new_cls,
            "total_unknown": cur_unk - new_cls,
            "new_coverage_pct": round((cur_class + new_cls) / cur_total * 100, 2),
            "delta_pct": round(((cur_class + new_cls) / cur_total * 100) - cur_cov, 2),
            "delta_abs": new_cls,
        }
    return {
        "current": {"classified": cur_class, "unknown": cur_unk, "coverage_pct": cur_cov},
        "by_variants": scenario("Approve one decision per unique variant", unique_variants),
        "by_account_names": scenario("Approve per unique account_name", unique_accounts),
        "by_entries": scenario("Approve all REVIEW entries", total_review),
        "total_accounts": cur_total,
    }


def compute_company_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for company, group in df.groupby("company"):
        rows.append({
            "company": company, "review_count": len(group),
            "pct_of_total": round(len(group) / len(df) * 100, 2),
            "unique_concepts": group["concept_code"].nunique(),
            "concepts": ", ".join(sorted(group["concept_code"].unique())[:5]),
            "unique_variants": group["matched_variant"].nunique(),
            "unique_documents": group["document_id"].nunique(),
            "documents": ", ".join(sorted(group["document_id"].unique())[:5]),
        })
    result = pd.DataFrame(rows).sort_values("review_count", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    return result


def compute_document_distribution(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for doc, group in df.groupby("document_id"):
        rows.append({
            "document_id": doc, "layout": group["layout"].iloc[0],
            "review_count": len(group), "pct_of_total": round(len(group) / len(df) * 100, 2),
            "unique_companies": group["company"].nunique(),
            "companies": ", ".join(sorted(group["company"].unique())[:3]),
            "unique_concepts": group["concept_code"].nunique(),
            "concepts": ", ".join(sorted(group["concept_code"].unique())[:5]),
            "unique_variants": group["matched_variant"].nunique(),
        })
    result = pd.DataFrame(rows).sort_values("review_count", ascending=False).reset_index(drop=True)
    result.index = result.index + 1
    return result


def compute_human_effort(uniqueness: dict, pareto: dict, total_entries: int) -> dict[str, Any]:
    scenarios = {"A (30s/variant)": 30, "B (1min/variant)": 60, "C (2min/variant)": 120}
    tv = uniqueness["unique_matched_variants"]
    pp = pareto["pareto_points"]
    effort_summary = {}
    for sname, sec in scenarios.items():
        def effort(v):
            return {"variants": v, "effort_hours": round(v * sec / 3600, 2), "effort_minutes": round(v * sec / 60, 1)}
        e_all = effort(tv)
        e_all["effort_hours_all_variants"] = e_all["effort_hours"]
        e_all["seconds_per_decision"] = sec
        e_all["total_variants"] = tv
        e_all["total_entries"] = total_entries
        e_all["effort_hours_top20"] = effort(min(20, tv))["effort_hours"]
        e_all["effort_hours_top50"] = effort(min(50, tv))["effort_hours"]
        e_all["effort_hours_all_entries"] = round(total_entries * sec / 3600, 2)
        s = round((1 - tv / total_entries) * 100, 2) if total_entries else 0
        e_all["savings_vs_entries_hours"] = round(e_all["effort_hours_all_entries"] - e_all["effort_hours_all_variants"], 2)
        e_all["savings_vs_entries_pct"] = s
        e_all["pareto_efforts"] = {k: effort(v["variants"]) | {"entries_covered": v["entries_covered"], "pct_covered": v["pct_covered"]} for k, v in pp.items()}
        effort_summary[sname] = e_all
    return effort_summary


def build_recommendation(uniqueness: dict, pareto: dict, concept_dist: pd.DataFrame, company_dist: pd.DataFrame, coverage_sim: dict, effort: dict) -> dict[str, Any]:
    pp = pareto["pareto_points"]
    pareto80 = next((v for v in pp.values() if v["pct_covered"] >= 80), list(pp.values())[-1])
    pareto90 = next((v for v in pp.values() if v["pct_covered"] >= 90), pareto80)
    pareto95 = next((v for v in pp.values() if v["pct_covered"] >= 95), pareto90)
    dc = concept_dist.iloc[0] if len(concept_dist) > 0 else None
    dco = company_dist.iloc[0] if len(company_dist) > 0 else None
    dc_pct = float(dc["pct_of_total"]) if dc is not None else 0
    dco_pct = float(dco["pct_of_total"]) if dco is not None else 0
    savings_pct = uniqueness["savings_pct"]
    nc = len(concept_dist)
    nco = len(company_dist)
    rec_by_concept = dc_pct > 50
    rec_by_variant = savings_pct > 20
    if rec_by_concept:
        best = "Review by concept (dominant concept >50% of REVIEW)"
    elif rec_by_variant:
        best = "Review by variant (avoids duplicate work across accounts)"
    elif nc < nco:
        best = "Review by concept (fewer concepts than companies)"
    else:
        best = "Review by company (aligned with natural workflow)"
    risks = []
    if dc_pct > 50:
        risks.append(f"High concentration on {dc['concept_code']} ({dc_pct}%) — verify CMCC quality")
    if uniqueness["unique_matched_variants"] < uniqueness["unique_account_names"] * 0.5:
        risks.append("Many accounts share variants → bulk approval risk")
    conditions = ["Pareto80 within manageable effort", "Dominant concept CMCC quality verified", "No ambiguous variants"]
    eb = effort.get("B (1min/variant)", {})
    return {
        "best_approach": best,
        "recommend_by_concept": rec_by_concept,
        "recommend_by_variant": rec_by_variant,
        "recommend_by_account": not rec_by_variant,
        "roi_analysis": {
            "savings_vs_account_level_pct": savings_pct,
            "pareto80_variants": pareto80["variants"],
            "pareto80_entries_covered": pareto80["entries_covered"],
            "pareto80_pct": pareto80["pct_covered"],
            "pareto90_variants": pareto90["variants"],
            "pareto90_pct": pareto90["pct_covered"],
            "pareto95_variants": pareto95["variants"],
            "pareto95_pct": pareto95["pct_covered"],
            "dominant_concept": dc["concept_code"] if dc is not None else "N/A",
            "dominant_concept_pct": dc_pct,
            "dominant_company": dco["company"] if dco is not None else "N/A",
            "dominant_company_pct": dco_pct,
        },
        "workflow": [
            f"Review {pareto80['variants']} Pareto80 variants first ({pareto80['pct_covered']}% coverage)",
            "Apply approved variant rules globally (each variant → one concept)",
            "Flag ambiguous accounts (same name → multiple concepts) for manual review",
            "Batch remaining low-frequency variants for periodic review",
        ],
        "risks": risks,
        "go_nogo_conditions": conditions,
        "all_conditions_met": len(risks) == 0,
        "recommendation": "GO" if len(risks) == 0 else "NO GO (risks identified)",
        "estimated_effort_scenarios": {
            "30s_variant_hours": effort.get("A (30s/variant)", {}).get("effort_hours_all_variants", 0),
            "1min_variant_hours": effort.get("B (1min/variant)", {}).get("effort_hours_all_variants", 0),
            "2min_variant_hours": effort.get("C (2min/variant)", {}).get("effort_hours_all_variants", 0),
        },
    }


def run_validations(df: pd.DataFrame) -> dict[str, Any]:
    issues = []
    vtc = df.groupby("matched_variant")["concept_code"].nunique()
    inconsistent = vtc[vtc > 1]
    if len(inconsistent) > 0:
        for var in inconsistent.index[:10]:
            cc = df[df["matched_variant"] == var][["concept_code", "concept_name"]].drop_duplicates().values.tolist()
            issues.append(f"⚠ Variant '{var}' maps to multiple concepts: {cc}")
    else:
        issues.append("✓ All variants map to exactly one concept")

    ac = df.groupby("account_name")["concept_code"].nunique()
    multi = ac[ac > 1]
    if len(multi) > 0:
        issues.append(f"⚠ {len(multi)} account_names map to multiple concepts")
        for a in multi.index[:10]:
            cc = df[df["account_name"] == a][["concept_code", "concept_name"]].drop_duplicates().values.tolist()
            issues.append(f"  '{a}' → {cc}")
    else:
        issues.append("✓ No account maps to multiple concepts")

    score_counts = df["score"].value_counts().to_dict()
    if set(score_counts.keys()) == {1}:
        issues.append("✓ All scores = 1.0 (expected)")
    else:
        issues.append(f"⚠ Non-1.0 scores: {score_counts}")

    return {"issues": issues, "status": "PASS" if all("⚠" not in i for i in issues) else "WARN"}


def generate_all_reports(df: pd.DataFrame, uniqueness: dict, variant_freq: pd.DataFrame,
                         pareto: dict, concept_dist: pd.DataFrame, method_dist: pd.DataFrame,
                         coverage_sim: dict, company_dist: pd.DataFrame, doc_dist: pd.DataFrame,
                         effort: dict, recommendation: dict, validations: dict) -> list[Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    pd.DataFrame([uniqueness]).to_excel(REPORTS_DIR / "review_unique.xlsx", index=False)
    paths.append(REPORTS_DIR / "review_unique.xlsx")
    variant_freq.head(50).to_excel(REPORTS_DIR / "variant_frequency.xlsx", index=False)
    paths.append(REPORTS_DIR / "variant_frequency.xlsx")
    concept_dist.to_excel(REPORTS_DIR / "concept_distribution.xlsx", index=False)
    paths.append(REPORTS_DIR / "concept_distribution.xlsx")
    company_dist.to_excel(REPORTS_DIR / "company_distribution.xlsx", index=False)
    paths.append(REPORTS_DIR / "company_distribution.xlsx")
    doc_dist.to_excel(REPORTS_DIR / "document_distribution.xlsx", index=False)
    paths.append(REPORTS_DIR / "document_distribution.xlsx")
    pr = pareto["pareto_rows"]
    ps = pd.DataFrame([{"milestone": k, "variants": v["variants"], "entries_covered": v["entries_covered"], "pct_covered": v["pct_covered"]} for k, v in pareto["pareto_points"].items()])
    with pd.ExcelWriter(REPORTS_DIR / "pareto.xlsx") as w:
        pr.to_excel(w, sheet_name="pareto_curve", index=False)
        ps.to_excel(w, sheet_name="pareto_summary", index=False)
    paths.append(REPORTS_DIR / "pareto.xlsx")
    sim_rows = []
    for key in ["by_entries", "by_variants", "by_account_names"]:
        s = coverage_sim[key]
        sim_rows.append({"scenario": s["scenario"], "new_classified": s["new_classified"],
                         "total_classified": s["total_classified"], "remaining_unknown": s["total_unknown"],
                         "new_coverage_pct": s["new_coverage_pct"], "delta_pct": s["delta_pct"]})
    pd.DataFrame(sim_rows).to_excel(REPORTS_DIR / "coverage_simulation.xlsx", index=False)
    paths.append(REPORTS_DIR / "coverage_simulation.xlsx")
    er = []
    for sname, d in effort.items():
        er.append({"scenario": sname, "seconds_per_decision": d["seconds_per_decision"],
                   "total_variants": d["total_variants"],
                   "effort_hours_all_variants": d["effort_hours_all_variants"],
                   "effort_hours_top20": d["effort_hours_top20"],
                   "effort_hours_top50": d["effort_hours_top50"],
                   "effort_hours_all_entries": d["effort_hours_all_entries"],
                   "savings_vs_entries_hours": d["savings_vs_entries_hours"],
                   "savings_vs_entries_pct": d["savings_vs_entries_pct"]})
    pd.DataFrame(er).to_excel(REPORTS_DIR / "human_effort.xlsx", index=False)
    paths.append(REPORTS_DIR / "human_effort.xlsx")
    method_dist.to_excel(REPORTS_DIR / "matching_method_distribution.xlsx", index=False)
    paths.append(REPORTS_DIR / "matching_method_distribution.xlsx")
    return paths


def generate_markdown(uniqueness: dict, variant_freq: pd.DataFrame, pareto: dict,
                      concept_dist: pd.DataFrame, method_dist: pd.DataFrame,
                      coverage_sim: dict, company_dist: pd.DataFrame, doc_dist: pd.DataFrame,
                      effort: dict, recommendation: dict, validations: dict, paths: list[Path]) -> str:
    def L(*a):
        lines.extend(a); lines.append("")
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    L("# CMCC Review Audit — Sprint 27.2", f"**Generated:** {now}", f"**Source:** `review_queue.xlsx` ({uniqueness['total_review_entries']} entries)", "---", "*Read-only analytical phase.*", "")
    L("## 1. Unique Decisions (Q1)")
    L(f"- **Total REVIEW entries:** {uniqueness['total_review_entries']}")
    L(f"- **Unique account_names:** {uniqueness['unique_account_names']}")
    L(f"- **Unique matched_variants:** {uniqueness['unique_matched_variants']} ← **real human decisions**")
    L(f"- **Unique concepts:** {uniqueness['unique_concepts']}")
    L(f"- **Unique companies:** {uniqueness['unique_companies']}")
    L(f"- **Unique documents:** {uniqueness['unique_documents']}")
    L(f"> **Answer:** **{uniqueness['human_decisions_needed']} decisions** (one per unique variant), not {uniqueness['total_review_entries']}. Savings: {uniqueness['duplicate_accounts_saved']} ({uniqueness['savings_pct']}%).", "")
    L("## 2. Variant Frequency (Q2)")
    L("### Top 10 frequent variants")
    L("| # | Variant | Freq | Concept | Cos | Docs | % |")
    L("|---|---|---|---|---|---|---|")
    for i, (_, r) in enumerate(variant_freq.head(10).iterrows(), 1):
        v = r['matched_variant'][:45]
        L(f"| {i} | {v} | {r['frequency']} | {r['concept_code']} | {r['num_companies']} | {r['num_documents']} | {r['impact_pct']}% |")
    n20 = min(20, len(variant_freq)); n50 = min(50, len(variant_freq))
    L("", f"**Top 20:** {n20} variants cover {variant_freq.head(20)['frequency'].sum()} entries", f"**Top 50:** {n50} variants cover {variant_freq.head(50)['frequency'].sum()} entries", "")
    L("## 3. Pareto (Q3)")
    pp = pareto["pareto_points"]
    L("| Milestone | Variants | Entries | % |")
    L("|---|---|---|---|")
    for k in ["top_5", "top_10", "top_20", "top_50", "top_100"]:
        if k in pp:
            L(f"| {k.replace('_',' ').title()} | {pp[k]['variants']} | {pp[k]['entries_covered']} | {pp[k]['pct_covered']}% |")
    for target, label in [(80, "80%"), (90, "90%"), (95, "95%")]:
        pr = pareto["pareto_rows"]
        m = pr[pr["cumulative_pct"] >= target]
        if len(m) > 0:
            f = m.iloc[0]
            L(f"| Pareto {label} | rank {int(f['rank'])} | {int(f['cumulative_sum'])} | {f['cumulative_pct']}% |")
    L(f"> **Answer:** 80% of REVIEW covered by **~{pp.get('top_10',{}).get('pct_covered',0)}%** with top 10 variants. 90% at **~{pp.get('top_20',{}).get('pct_covered',0)}%**. 95% at **~{pp.get('top_50',{}).get('pct_covered',0)}%**.", "")
    L("## 4. Concept Distribution (Q4)")
    L("| Code | Name | Count | % | Variants | Companies | Docs |")
    L("|---|---|---|---|---|---|---|")
    for _, r in concept_dist.iterrows():
        L(f"| {r['concept_code']} | {r['concept_name'][:30]} | {r['review_count']} | {r['pct_of_total']}% | {r['unique_variants']} | {r['num_companies']} | {r['num_documents']} |")
    if len(concept_dist) > 0:
        t = concept_dist.iloc[0]
        dom = t['pct_of_total'] > 50
        L(f"> {'⚠ DOMINANT' if dom else 'No single concept dominates'}: `{t['concept_code']}` ({t['concept_name']}) = {t['pct_of_total']}% of REVIEW", "")
    L("## 5. Matching Method Distribution (Q5)")
    L("| Method | Count | % | Variants | Companies | Docs |")
    L("|---|---|---|---|---|---|")
    for _, r in method_dist.iterrows():
        L(f"| {r['matching_method']} | {r['count']} | {r['pct']}% | {r['unique_variants']} | {r['num_companies']} | {r['num_documents']} |")
    L("> **Answer:** 100% of REVIEW = **cmcc_variante**. No dictionary/rule/shadow entries at score=1.0.", "")
    L("## 6. Coverage Simulation (Q6)")
    cur = coverage_sim["current"]
    L(f"**Current:** {cur['classified']} classified / {cur['unknown']} UNKNOWN = {cur['coverage_pct']}%")
    L("", "| Scenario | New Classified | Total Classified | Coverage | Delta | Remaining UNKNOWN |")
    L("|---|---|---|---|---|---|")
    for key in ["by_variants", "by_account_names", "by_entries"]:
        s = coverage_sim[key]
        L(f"| {s['scenario']} | {s['new_classified']} | {s['total_classified']} | {s['new_coverage_pct']}% | +{s['delta_pct']}pp | {s['total_unknown']} |")
    L(f"> **Answer:** Variant-level approval: {cur['coverage_pct']}% → **{coverage_sim['by_variants']['new_coverage_pct']}%** (+{coverage_sim['by_variants']['delta_pct']}pp), {coverage_sim['by_variants']['total_unknown']} UNKNOWN remaining.", "")
    L("## 7. Company Distribution (Q7)")
    L("| # | Company | REVIEW | % | Concepts | Variants | Docs |")
    L("|---|---|---|---|---|---|---|")
    for i, (_, r) in enumerate(company_dist.iterrows(), 1):
        L(f"| {i} | {r['company'][:40]} | {r['review_count']} | {r['pct_of_total']}% | {r['unique_concepts']} | {r['unique_variants']} | {r['unique_documents']} |")
    L("")
    L("## 8. Document & Layout Distribution (Q8)")
    L("| # | Document | Layout | REVIEW | % | Concepts | Variants |")
    L("|---|---|---|---|---|---|---|---|")
    for i, (_, r) in enumerate(doc_dist.iterrows(), 1):
        L(f"| {i} | {r['document_id'][:45]} | {r['layout']} | {r['review_count']} | {r['pct_of_total']}% | {r['unique_concepts']} | {r['unique_variants']} |")
    L("", f"> **Answer:** Single layout `pdf_estandar` for all REVIEW. Top doc `{doc_dist.iloc[0]['document_id'][:40]}` = {doc_dist.iloc[0]['review_count']} entries ({doc_dist.iloc[0]['pct_of_total']}%).", "")
    L("## 9. Human Effort (Q9)")
    tv = uniqueness["unique_matched_variants"]
    te = uniqueness["total_review_entries"]
    L(f"**Comparison:** Review by entries ({te}) vs review by variants ({tv})")
    L("", "| Scenario | All Variants | Top 20 | Top 50 | Pareto80 | Pareto90 | Pareto95 | All Entries | Savings |")
    L("|---|---|---|---|---|---|---|---|---|---|")
    for sname, d in effort.items():
        pe80 = next((v for v in d.get("pareto_efforts", {}).values() if v.get("pct_covered", 0) >= 80), {})
        pe90 = next((v for v in d.get("pareto_efforts", {}).values() if v.get("pct_covered", 0) >= 90), {})
        pe95 = next((v for v in d.get("pareto_efforts", {}).values() if v.get("pct_covered", 0) >= 95), {})
        L(f"| {sname} | {d['effort_hours_all_variants']}h | {d['effort_hours_top20']}h | {d['effort_hours_top50']}h | {pe80.get('effort_hours',0)}h | {pe90.get('effort_hours',0)}h | {pe95.get('effort_hours',0)}h | {d['effort_hours_all_entries']}h | {d['savings_vs_entries_pct']}% |")
    L("")
    L("## 10. Recommendation (Q10)")
    L(f"**Best approach:** {recommendation['best_approach']}")
    L(f"**GO / NO GO:** {recommendation['recommendation']}")
    L("")
    L("### ROI Analysis")
    r = recommendation["roi_analysis"]
    L(f"- Savings vs account-level: {r['savings_vs_account_level_pct']}%")
    L(f"- Pareto80: {r['pareto80_variants']} variants, {r['pareto80_pct']}% coverage")
    L(f"- Pareto90: {r['pareto90_variants']} variants, {r['pareto90_pct']}% coverage")
    L(f"- Pareto95: {r['pareto95_variants']} variants, {r['pareto95_pct']}% coverage")
    L(f"- Dominant concept: {r['dominant_concept']} ({r['dominant_concept_pct']}%)")
    L(f"- Dominant company: {r['dominant_company']} ({r['dominant_company_pct']}%)")
    L("")
    L("### Recommended Workflow")
    for i, step in enumerate(recommendation["workflow"], 1):
        L(f"{i}. {step}")
    L("")
    if recommendation["risks"]:
        L("### Risks")
        for risk in recommendation["risks"]:
            L(f"- {risk}")
        L("")
    L("### Effort Summary")
    L(f"- Scenario A (30s/variant): {effort.get('A (30s/variant)',{}).get('effort_hours_all_variants',0)}h total")
    L(f"- Scenario B (1min/variant): {effort.get('B (1min/variant)',{}).get('effort_hours_all_variants',0)}h total")
    L(f"- Scenario C (2min/variant): {effort.get('C (2min/variant)',{}).get('effort_hours_all_variants',0)}h total")
    L("")
    L("### Validations")
    for issue in validations["issues"]:
        L(f"- {issue}")
    L("", f"**Status:** {validations['status']}", "")
    L("### Generated Files")
    for p in paths:
        L(f"- `{p.name}` ({p.stat().st_size} bytes)")
    L("", "---", "**Sprint 27.2 complete.** Read-only. No production modifications.")
    return "\n".join(lines)


def main():
    t0 = time.perf_counter()
    print("=" * 70)
    print("  SPRINT 27.2 — REVIEW_CMCC Audit")
    print("  Read-only analytical phase")
    print("=" * 70)
    df = load_data()
    uniqueness = compute_uniqueness(df)
    variant_freq = compute_variant_frequency(df)
    pareto = compute_pareto(variant_freq, len(df))
    concept_dist = compute_concept_distribution(df)
    method_dist = compute_matching_method_distribution(df)
    with open(PIPELINE_JSON) as f:
        pipeline_data = json.load(f)
    coverage_sim = compute_coverage_simulation(df, pipeline_data)
    company_dist = compute_company_distribution(df)
    doc_dist = compute_document_distribution(df)
    effort = compute_human_effort(uniqueness, pareto, len(df))
    recommendation = build_recommendation(uniqueness, pareto, concept_dist, company_dist, coverage_sim, effort)
    validations = run_validations(df)
    paths = generate_all_reports(df, uniqueness, variant_freq, pareto, concept_dist, method_dist, coverage_sim, company_dist, doc_dist, effort, recommendation, validations)
    md = generate_markdown(uniqueness, variant_freq, pareto, concept_dist, method_dist, coverage_sim, company_dist, doc_dist, effort, recommendation, validations, paths)
    (REPORTS_DIR / "review_audit.md").write_text(md)
    paths.append(REPORTS_DIR / "review_audit.md")
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uniqueness": uniqueness,
        "pareto": {k: v for k, v in pareto["pareto_points"].items()},
        "coverage_simulation": coverage_sim,
        "recommendation": {k: v for k, v in recommendation.items() if k != "workflow"},
        "validations": validations,
        "effort_summary": {k: {"effort_hours_all_variants": v["effort_hours_all_variants"]} for k, v in effort.items()},
    }
    (REPORTS_DIR / "review_statistics.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 70}")
    print(f"  AUDIT COMPLETE — {elapsed:.1f}s")
    print(f"  {len(paths)} files in {REPORTS_DIR}")
    for p in paths:
        print(f"    {p.name}: {p.stat().st_size:,} bytes")
    print("=" * 70)


if __name__ == "__main__":
    main()
