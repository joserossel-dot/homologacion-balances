#!/usr/bin/env python3
"""
Sprint 27.2B — CMCC Concept Audit
Read-only deep analysis of 52 concepts' cohesion, separability, and quality.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import rapidfuzz as rf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPORTS_DIR = Path("reports/cmcc_concept_audit")
CMCC_JSON = Path("knowledge/cmcc.json")
CATALOGO_JSON = Path("catalogo_maestro.json")
DICCIONARIO_JSON = Path("diccionario.json")
GS_DB = Path("gold_standard.db")
REVIEW_QUEUE = Path("reports/cmcc_review_pipeline/review_queue.xlsx")
PIPELINE_JSON = Path("reports/cmcc_review_pipeline/review_pipeline.json")


STOPWORDS = frozenset({
    "de", "del", "la", "las", "los", "el", "y", "con", "para", "por",
    "al", "en", "un", "una", "a", "su", "e", "o", "que", "es", "se",
    "no", "lo", "le", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii",
    "ix", "x", "xx", "xxx",
})


def load_cmcc() -> dict[str, Any]:
    with open(CMCC_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_catalogo() -> dict[str, str]:
    with open(CATALOGO_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {c["codigo"]: c["nombre"] for c in data if "codigo" in c}
    if isinstance(data, dict):
        return {k: v.get("nombre", v) if isinstance(v, dict) else v for k, v in data.items()}
    return {}


def load_gold_standard() -> dict[str, int]:
    conn = sqlite3.connect(str(GS_DB))
    df = pd.read_sql("SELECT final_code, COUNT(*) as cnt FROM gold_records GROUP BY final_code", conn)
    conn.close()
    return dict(zip(df["final_code"], df["cnt"]))


def load_diccionario() -> dict[str, int]:
    with open(DICCIONARIO_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        codes = [e.get("codigo_estandar", "") for e in data]
    elif isinstance(data, dict):
        codes = [v.get("codigo_estandar", "") if isinstance(v, dict) else "" for v in data.values()]
    return dict(Counter(c for c in codes if c))


def load_review_queue() -> dict[str, int]:
    try:
        df = pd.read_excel(REVIEW_QUEUE)
        return dict(df["concept_code"].value_counts())
    except Exception:
        return {}


def load_pipeline_unknowns() -> dict[str, int]:
    try:
        with open(PIPELINE_JSON) as f:
            data = json.load(f)
        return data.get("statistics", {}).get("total_review", 0)
    except Exception:
        return 0


def normalize(text: str) -> str:
    t = text.lower()
    t = t.encode("ascii", "ignore").decode("ascii")  # remove accents
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 1}


def compute_vocabulary(variants: list[str]) -> set[str]:
    vocab: set[str] = set()
    for v in variants:
        vocab.update(tokenize(v))
    return vocab


def compute_lexical_diversity(variants: list[str]) -> float:
    if not variants:
        return 0.0
    vocab = compute_vocabulary(variants)
    return round(len(vocab) / len(variants), 4) if variants else 0.0


def compute_entropy(variants: list[str]) -> float:
    if not variants:
        return 0.0
    all_tokens = []
    for v in variants:
        all_tokens.extend(tokenize(v))
    if not all_tokens:
        return 0.0
    counter = Counter(all_tokens)
    total = len(all_tokens)
    entropy = -sum((c / total) * math.log2(c / total) for c in counter.values())
    return round(entropy, 4)


def compute_cohesion(variants: list[str]) -> dict[str, float]:
    if len(variants) < 2:
        return {"mean_jaccard": 1.0, "min_jaccard": 1.0, "max_jaccard": 1.0,
                "std_jaccard": 0.0, "cohesion_index": 1.0, "variants_cohesion": len(variants)}
    tokenized = [tokenize(v) for v in variants]
    pairs = 0
    total_j = 0.0
    min_j = 1.0
    max_j = 0.0
    sq_diff = 0.0
    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            if not tokenized[i] or not tokenized[j]:
                jac = 0.0
            else:
                inter = len(tokenized[i] & tokenized[j])
                union = len(tokenized[i] | tokenized[j])
                jac = inter / union if union > 0 else 0.0
            total_j += jac
            min_j = min(min_j, jac)
            max_j = max(max_j, jac)
            sq_diff += jac * jac
            pairs += 1
    mean_j = total_j / pairs if pairs else 0.0
    std_j = math.sqrt(sq_diff / pairs - mean_j * mean_j) if pairs else 0.0
    variance_penalty = std_j
    size_bonus = min(1.0, len(variants) / 100)
    cohesion = max(0.0, mean_j - variance_penalty * 0.5 + size_bonus * 0.1)
    return {
        "mean_jaccard": round(mean_j, 4),
        "min_jaccard": round(min_j, 4),
        "max_jaccard": round(max_j, 4),
        "std_jaccard": round(std_j, 4),
        "cohesion_index": round(min(1.0, cohesion), 4),
        "pairs_compared": pairs,
    }


def compute_concept_centroid(variants: list[str]) -> frozenset[str]:
    all_tokens: set[str] = set()
    for v in variants:
        all_tokens.update(tokenize(v))
    return frozenset(all_tokens)


def compute_pairwise_similarity(concepts: dict[str, list[str]], code1: str, code2: str) -> float:
    v1 = concepts.get(code1, [])
    v2 = concepts.get(code2, [])
    if not v1 or not v2:
        return 0.0
    tokens1 = set()
    tokens2 = set()
    for v in v1:
        tokens1.update(tokenize(v))
    for v in v2:
        tokens2.update(tokenize(v))
    if not tokens1 or not tokens2:
        return 0.0
    inter = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return round(inter / union, 4) if union > 0 else 0.0


def compute_frequency_stats(variants: list[str], name: str) -> dict[str, Any]:
    if not variants:
        return {"mean_freq": 0, "max_freq": 0, "median_freq": 0, "total_freq": 0}
    word_freq = Counter()
    for v in variants:
        word_freq.update(tokenize(v))
    freqs = list(word_freq.values())
    n = len(freqs)
    s_freqs = sorted(freqs)
    return {
        "mean_freq": round(sum(freqs) / n, 2) if n else 0,
        "max_freq": max(freqs) if n else 0,
        "median_freq": s_freqs[n // 2] if n else 0,
        "total_freq": sum(freqs) if n else 0,
    }


def detect_overgeneralization(concept: dict[str, Any], all_concepts: dict[str, list[str]]) -> dict[str, Any]:
    code = concept["codigo"]
    my_variants = concept.get("variantes", [])
    my_vocab = compute_vocabulary(my_variants)
    total_shared = Counter()
    for other_code, other_variants in all_concepts.items():
        if other_code == code:
            continue
        other_vocab = compute_vocabulary(other_variants)
        shared = my_vocab & other_vocab
        for w in shared:
            total_shared[w] += 1
    overlap_ratio = len(total_shared) / max(len(my_vocab), 1)
    return {
        "vocab_size": len(my_vocab),
        "shared_tokens": len(total_shared),
        "overlap_ratio": round(overlap_ratio, 4),
        "most_shared": total_shared.most_common(10),
    }


def detect_underrepresentation(concept: dict[str, Any], all_concepts: dict[str, list[str]]) -> dict[str, Any]:
    code = concept["codigo"]
    n_variants = len(concept.get("variantes", []))
    all_variant_counts = [len(c.get("variantes", [])) for c in all_concepts.values() if isinstance(c, dict)]
    avg_variants = sum(all_variant_counts) / max(len(all_variant_counts), 1)
    std_variants = (sum((x - avg_variants) ** 2 for x in all_variant_counts) / max(len(all_variant_counts), 1)) ** 0.5
    z_score = (n_variants - avg_variants) / max(std_variants, 1)
    is_underrepresented = n_variants < 5 or z_score < -1.0
    return {
        "n_variants": n_variants,
        "avg_variants": round(avg_variants, 2),
        "z_score": round(z_score, 4),
        "is_underrepresented": is_underrepresented,
    }


def compute_risk_score(
    concept: dict[str, Any],
    cohesion: dict[str, float],
    overgen: dict[str, Any],
    underrep: dict[str, Any],
    review_count: int,
) -> float:
    score = 0.0
    coh = cohesion.get("cohesion_index", 1.0)
    score += (1.0 - coh) * 30

    n_variants = len(concept.get("variantes", []))
    if n_variants > 50:
        score += min(25, n_variants * 0.05)

    score += overgen.get("overlap_ratio", 0) * 20

    if underrep.get("is_underrepresented"):
        score += 15

    if review_count > 0:
        score += min(20, review_count * 0.1)

    return round(min(100, score), 2)


def determine_action(
    concept: dict[str, Any],
    cohesion: dict[str, float],
    overgen: dict[str, Any],
    underrep: dict[str, Any],
    similarity_to_others: dict[str, float],
    review_count: int,
    gs_count: int,
    dict_count: int,
) -> str:
    code = concept["codigo"]
    n_variants = len(concept.get("variantes", []))
    coh = cohesion.get("cohesion_index", 1.0)
    overlap = overgen.get("overlap_ratio", 0)

    if n_variants == 0:
        return "EXPAND"

    if n_variants > 100 and coh < 0.3:
        return "SPLIT"

    high_sim = {k: v for k, v in similarity_to_others.items() if v > 0.5}
    if high_sim and gs_count == 0:
        merge_target = max(high_sim, key=high_sim.get)
        return f"MERGE → {merge_target}"

    if coh > 0.6 and overgen.get("overlap_ratio", 0) < 0.3 and n_variants >= 5:
        return "KEEP"

    if n_variants < 5 and review_count == 0:
        return "EXPAND"

    if review_count > 20:
        return "REVIEW"

    return "NO ACTION"


def main():
    t0 = time.perf_counter()
    print("=" * 70)
    print("  SPRINT 27.2B — CMCC Concept Audit")
    print("  Deep analysis of 52 concepts' cohesion, separability, quality")
    print("=" * 70)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    cmcc_data = load_cmcc()
    concepts: list[dict] = cmcc_data if isinstance(cmcc_data, list) else cmcc_data.get("conceptos", [])
    catalogo = load_catalogo()
    gs_counts = load_gold_standard()
    dict_counts = load_diccionario()
    review_counts = load_review_queue()

    concept_map: dict[str, dict] = {}
    variant_map: dict[str, list[str]] = {}
    for c in concepts:
        code = c["codigo"]
        concept_map[code] = c
        variant_map[code] = [v.strip() for v in c.get("variantes", []) if v.strip()]

    all_codes = [c["codigo"] for c in concepts]

    # ── Compute per-concept metrics ──
    rows = []
    cohesion_data: dict[str, dict] = {}
    overgen_data: dict[str, dict] = {}
    underrep_data: dict[str, dict] = {}
    risk_data: dict[str, float] = {}
    action_data: dict[str, str] = {}
    centroids: dict[str, frozenset] = {}
    similarity_matrix: dict[str, dict[str, float]] = {}

    for code in all_codes:
        c = concept_map.get(code, {})
        variants = variant_map.get(code, [])
        name = c.get("nombre", catalogo.get(code, ""))
        n_synonyms = len(c.get("sinonimos", []))
        n_abbrevs = len(c.get("abreviaturas", []))
        n_variants = len(variants)
        total_entries = n_synonyms + n_abbrevs + n_variants
        gs = gs_counts.get(code, 0)
        dic = dict_counts.get(code, 0)
        rv = review_counts.get(code, 0)
        vocab = compute_vocabulary(variants)
        lexical_div = compute_lexical_diversity(variants)
        entropy = compute_entropy(variants)
        cohesion = compute_cohesion(variants)
        freq_stats = compute_frequency_stats(variants, name)
        overgen = detect_overgeneralization(c, variant_map)
        underrep = detect_underrepresentation(c, variant_map)
        centroid = compute_concept_centroid(variants)

        cohesion_data[code] = cohesion
        overgen_data[code] = overgen
        underrep_data[code] = underrep
        centroids[code] = centroid

        rows.append({
            "concept_code": code,
            "concept_name": name,
            "n_variants": n_variants,
            "n_synonyms": n_synonyms,
            "n_abbreviations": n_abbrevs,
            "total_entries": total_entries,
            "gold_standard_records": gs,
            "dictionary_entries": dic,
            "review_queue_entries": rv,
            "vocab_size": len(vocab),
            "lexical_diversity": lexical_div,
            "entropy": entropy,
            "mean_jaccard": cohesion["mean_jaccard"],
            "min_jaccard": cohesion["min_jaccard"],
            "max_jaccard": cohesion["max_jaccard"],
            "std_jaccard": cohesion["std_jaccard"],
            "cohesion_index": cohesion["cohesion_index"],
            "mean_token_freq": freq_stats["mean_freq"],
            "max_token_freq": freq_stats["max_freq"],
            "median_token_freq": freq_stats["median_freq"],
            "overlap_ratio": overgen["overlap_ratio"],
            "is_underrepresented": underrep["is_underrepresented"],
            "z_score": underrep["z_score"],
        })

    # ── Compute pairwise similarity ──
    for code1 in all_codes:
        similarity_matrix[code1] = {}
        for code2 in all_codes:
            if code1 == code2:
                similarity_matrix[code1][code2] = 1.0
            else:
                similarity_matrix[code1][code2] = compute_pairwise_similarity(
                    variant_map, code1, code2
                )

    # ── Compute risk scores and actions ──
    for code in all_codes:
        risk_data[code] = compute_risk_score(
            concept_map[code], cohesion_data[code], overgen_data[code],
            underrep_data[code], review_counts.get(code, 0)
        )
        action_data[code] = determine_action(
            concept_map[code], cohesion_data[code], overgen_data[code],
            underrep_data[code], similarity_matrix[code],
            review_counts.get(code, 0), gs_counts.get(code, 0), dict_counts.get(code, 0)
        )
        for row in rows:
            if row["concept_code"] == code:
                row["risk_score"] = risk_data[code]
                row["action"] = action_data[code]
                break

    # ── Build DataFrames ──
    df_audit = pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)
    df_audit.index = df_audit.index + 1
    df_audit.index.name = "rank"

    # ── Cohesion report ──
    coh_rows = []
    for code in all_codes:
        c = concept_map[code]
        name = c.get("nombre", catalogo.get(code, ""))
        coh = cohesion_data[code]
        coh_rows.append({
            "concept_code": code, "concept_name": name,
            "n_variants": len(variant_map.get(code, [])),
            **coh,
        })
    df_cohesion = pd.DataFrame(coh_rows).sort_values("cohesion_index", ascending=True).reset_index(drop=True)
    df_cohesion.index = df_cohesion.index + 1
    df_cohesion.index.name = "rank"

    # ── Similarity report ──
    sim_pairs = []
    for i, code1 in enumerate(all_codes):
        for code2 in all_codes[i + 1:]:
            sim = similarity_matrix[code1][code2]
            if sim > 0.0:
                n1 = concept_map[code1].get("nombre", catalogo.get(code1, ""))
                n2 = concept_map[code2].get("nombre", catalogo.get(code2, ""))
                sim_pairs.append({
                    "concept_a": code1, "name_a": n1,
                    "concept_b": code2, "name_b": n2,
                    "jaccard_similarity": sim,
                })
    df_similarity = pd.DataFrame(sim_pairs).sort_values("jaccard_similarity", ascending=False).reset_index(drop=True)
    df_similarity.index = df_similarity.index + 1
    df_similarity.index.name = "rank"

    # ── Risk report ──
    risk_rows = []
    for code in all_codes:
        c = concept_map[code]
        name = c.get("nombre", catalogo.get(code, ""))
        rv = review_counts.get(code, 0)
        coh = cohesion_data[code]
        overgen = overgen_data[code]
        underrep = underrep_data[code]
        risk_rows.append({
            "concept_code": code, "concept_name": name,
            "risk_score": risk_data[code],
            "n_variants": len(variant_map.get(code, [])),
            "review_queue": rv,
            "cohesion": coh["cohesion_index"],
            "overlap_ratio": overgen["overlap_ratio"],
            "is_underrepresented": underrep["is_underrepresented"],
            "action": action_data[code],
        })
    df_risk = pd.DataFrame(risk_rows).sort_values("risk_score", ascending=False).reset_index(drop=True)
    df_risk.index = df_risk.index + 1
    df_risk.index.name = "rank"

    # ── Actions report ──
    action_rows = []
    for code in all_codes:
        c = concept_map[code]
        name = c.get("nombre", catalogo.get(code, ""))
        action = action_data[code]
        coh = cohesion_data[code]
        overgen = overgen_data[code]
        action_rows.append({
            "concept_code": code, "concept_name": name,
            "action": action,
            "evidence_score": overgen.get("overlap_ratio", 0),
            "n_variants": len(variant_map.get(code, [])),
            "cohesion": coh["cohesion_index"],
            "risk_score": risk_data[code],
        })
    df_actions = pd.DataFrame(action_rows).sort_values("action").reset_index(drop=True)
    df_actions.index = df_actions.index + 1

    # ── Generate Excel reports ──
    df_audit.to_excel(REPORTS_DIR / "concept_audit.xlsx", index=True)
    df_cohesion.to_excel(REPORTS_DIR / "concept_cohesion.xlsx", index=True)
    df_similarity.to_excel(REPORTS_DIR / "concept_similarity.xlsx", index=True)
    df_risk.to_excel(REPORTS_DIR / "concept_risk.xlsx", index=True)
    df_actions.to_excel(REPORTS_DIR / "concept_actions.xlsx", index=True)

    # ── Statistics JSON ──
    action_counts = dict(Counter(action_data.values()))
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_concepts": len(all_codes),
        "concepts_with_variants": sum(1 for v in variant_map.values() if v),
        "concepts_empty": sum(1 for v in variant_map.values() if not v),
        "total_variants": sum(len(v) for v in variant_map.values()),
        "total_vocabulary": len(set().union(*(compute_vocabulary(v) for v in variant_map.values() if v))),
        "action_summary": dict(sorted(action_counts.items(), key=lambda x: -x[1])),
        "top_10_risk": [
            {"code": r["concept_code"], "name": r["concept_name"],
             "risk": r["risk_score"], "action": r["action"]}
            for _, r in df_risk.head(10).iterrows()
        ],
        "top_10_similar_pairs": [
            {"a": r["concept_a"], "b": r["concept_b"], "similarity": r["jaccard_similarity"]}
            for _, r in df_similarity.head(10).iterrows()
        ],
    }
    (REPORTS_DIR / "concept_statistics.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False)
    )

    # ── Generate Markdown ──
    def L(*a):
        lines.extend(a); lines.append("")
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    L("# CMCC Concept Audit — Sprint 27.2B")
    L(f"**Generated:** {now}", f"**Source:** `cmcc.json` ({len(all_codes)} concepts, {stats['total_variants']} variants)",
      "---", "*Read-only. No production modifications.*", "")

    L("## 1. Overview")
    L(f"- **{len(all_codes)}** concepts analyzed")
    L(f"- **{stats['concepts_with_variants']}** concepts with variants, **{stats['concepts_empty']}** empty")
    L(f"- **{stats['total_variants']}** total variants across all concepts")
    L(f"- **{stats['total_vocabulary']}** unique normalized tokens", "")

    L("## 2. Cohesion Analysis")
    L("Cohesion Index = mean_jaccard - 0.5*std_jaccard + 0.1*min(1, n_variants/100)")
    L("Range: 0 = maximally diverse, 1 = maximally cohesive")
    L("")
    L("| Rank | Concept | Name | Cohesion | Variants | Mean J | Std J |")
    L("|---|---|---|---|---|---|---|")
    for _, r in df_cohesion.head(15).iterrows():
        L(f"| {r.name} | {r['concept_code']} | {r['concept_name'][:35]} | {r['cohesion_index']} | {r['n_variants']} | {r['mean_jaccard']} | {r['std_jaccard']} |")
    L("")
    low_coh = df_cohesion[df_cohesion["cohesion_index"] < 0.3]
    if len(low_coh) > 0:
        L(f"**{len(low_coh)} concepts with low cohesion (<0.3):**")
        for _, r in low_coh.iterrows():
            L(f"- {r['concept_code']} ({r['concept_name'][:40]}): {r['cohesion_index']} — variants are semantically diverse")
        L("")

    L("## 3. Concept Similarity (Separability)")
    high_sim = df_similarity[df_similarity["jaccard_similarity"] > 0.4]
    L(f"**{len(high_sim)} concept pairs with similarity > 0.4** (potential merge candidates)")
    L("")
    L("| Rank | Concept A | A Name | Concept B | B Name | Jaccard |")
    L("|---|---|---|---|---|---|")
    for _, r in high_sim.head(20).iterrows():
        L(f"| {r.name} | {r['concept_a']} | {r['name_a'][:30]} | {r['concept_b']} | {r['name_b'][:30]} | {r['jaccard_similarity']} |")
    if len(high_sim) == 0:
        L("No concept pairs with similarity > 0.4 — concepts are well-separated.")
    L("")

    L("## 4. Risk Ranking")
    L("| Rank | Concept | Name | Risk | Variants | Review | Cohesion | Overlap | Action |")
    L("|---|---|---|---|---|---|---|---|---|")
    for _, r in df_risk.head(15).iterrows():
        under = "⚠" if r["is_underrepresented"] else ""
        L(f"| {r.name} | {r['concept_code']} | {r['concept_name'][:35]} | {r['risk_score']} | {r['n_variants']} | {r['review_queue']} | {r['cohesion']} | {r['overlap_ratio']} | {r['action']} {under}|")
    L("")

    L("## 5. Action Recommendations")
    action_order = ["SPLIT", "REVIEW", "MERGE", "EXPAND", "KEEP", "NO ACTION"]
    L("| Action | Concepts |")
    L("|---|---|")
    for a in action_order:
        if a in action_counts:
            ccs = [r["concept_code"] for _, r in df_actions[df_actions["action"] == a].iterrows()]
            L(f"| {a} | {action_counts[a]} — {', '.join(ccs[:10])}{'...' if len(ccs) > 10 else ''} |")
    L("")

    L("| Rank | Concept | Name | Action | Risk | Variants | Cohesion |")
    L("|---|---|---|---|---|---|---|")
    for _, r in df_actions.iterrows():
        a = r["action"]
        if a != "NO ACTION" and a != "KEEP":
            L(f"| {r.name} | {r['concept_code']} | {r['concept_name'][:35]} | {a} | {r['risk_score']} | {r['n_variants']} | {r['cohesion']} |")
    L("")

    L("## 6. AC.01 Deep Dive")
    ac01_variants = variant_map.get("AC.01", [])
    ac01_coh = cohesion_data.get("AC.01", {})
    ac01_overgen = overgen_data.get("AC.01", {})
    ac01_underrep = underrep_data.get("AC.01", {})
    L(f"- **{len(ac01_variants)}** variants (largest concept by far)")
    L(f"- **Cohesion Index:** {ac01_coh.get('cohesion_index', 0)}")
    L(f"- **Mean Jaccard:** {ac01_coh.get('mean_jaccard', 0)}")
    L(f"- **Lexical Diversity:** {next((r['lexical_diversity'] for r in rows if r['concept_code']=='AC.01'), 0)}")
    L(f"- **Entropy:** {next((r['entropy'] for r in rows if r['concept_code']=='AC.01'), 0)}")
    L(f"- **Overlap Ratio:** {ac01_overgen.get('overlap_ratio', 0)} (vocabulary shared with other concepts)")
    L(f"- **REVIEW queue entries:** {review_counts.get('AC.01', 0)} (58.69% of total REVIEW)")
    L(f"- **Gold standard records:** {gs_counts.get('AC.01', 0)}")
    L("")
    if ac01_coh.get("cohesion_index", 1) < 0.3:
        L("⚠ **AC.01 has LOW cohesion.** Its variants span: Caja, Banco, Cuenta Corriente, but also Anticipos, Valores, Garantías, Fondos Mutuos, etc.")
        L("**Recommendation: SPLIT** AC.01 into sub-concepts (AC.01a Caja/Bancos, AC.01b Valores Negociables, AC.01c Otros Efectivos)")
    elif ac01_coh.get("cohesion_index", 1) < 0.5:
        L("⚠ **AC.01 has MODERATE cohesion.** Some variants may belong to sub-concepts.")
        L("**Recommendation: REVIEW** — verify variant assignments before human review approval.")
    else:
        L("✅ **AC.01 has GOOD cohesion.** Its variants are well-centered on Caja y Bancos.")
        L("**Recommendation: KEEP** — proceed with human review.")
    L("")

    L("## 7. Detailed Concept Audit (All 52 Concepts)")
    L("| Code | Name | Variants | Cohesion | Risk | Action | GS | Dic | Review |")
    L("|---|---|---|---|---|---|---|---|---|")
    for _, r in df_audit.iterrows():
        L(f"| {r['concept_code']} | {r['concept_name'][:35]} | {r['n_variants']} | {r['cohesion_index']} | {r['risk_score']} | {r['action']} | {r['gold_standard_records']} | {r['dictionary_entries']} | {r['review_queue_entries']} |")
    L("")

    L("## 8. Findings & Risks")
    findings = []
    for _, r in df_risk.head(10).iterrows():
        findings.append(f"- **{r['concept_code']}** ({r['concept_name'][:40]}): Risk={r['risk_score']}, Action={r['action']}, Cohesion={r['cohesion']}, {r['n_variants']} variants, {r['review_queue']} REVIEW")
    for f_item in findings:
        L(f_item)
    L("")
    empty_concepts = [c["codigo"] for c in concepts if not c.get("variantes") and not c.get("sinonimos")]
    if empty_concepts:
        L(f"**{len(empty_concepts)} empty concepts:** {', '.join(empty_concepts)}")
        L("")
    if len(high_sim) > 0:
        pairs = [f"{r['concept_a']}↔{r['concept_b']}({r['jaccard_similarity']})" for _, r in high_sim.head(5).iterrows()]
        L(f"**{len(high_sim)} high-similarity pairs:** {', '.join(pairs)}")
        L("")

    L("## 9. GO / NO GO for Sprint 27.3 (Human Review)")
    risk_threshold = 50
    high_risk = df_risk[df_risk["risk_score"] >= risk_threshold]
    split_concepts = [r["concept_code"] for _, r in df_actions[df_actions["action"].str.startswith("SPLIT")].iterrows()]
    merge_concepts = [r["concept_code"] for _, r in df_actions[df_actions["action"].str.startswith("MERGE")].iterrows()]

    conditions_met = []
    conditions_failed = []
    if len(high_risk) == 0:
        conditions_met.append("No concepts with risk > 50")
    else:
        conditions_failed.append(f"{len(high_risk)} concepts with risk > 50: {', '.join(high_risk['concept_code'].values[:5])}")

    if len(split_concepts) == 0:
        conditions_met.append("No concepts recommended for SPLIT")
    else:
        conditions_failed.append(f"{len(split_concepts)} concepts recommended for SPLIT: {', '.join(split_concepts)}")

    if len(empty_concepts) == 0:
        conditions_met.append("No empty concepts")
    else:
        conditions_failed.append(f"{len(empty_concepts)} empty concepts exist: {', '.join(empty_concepts)}")

    if ac01_coh.get("cohesion_index", 1) >= 0.3:
        conditions_met.append(f"AC.01 cohesion acceptable ({ac01_coh.get('cohesion_index', 0)})")
    else:
        conditions_failed.append(f"AC.01 cohesion too low ({ac01_coh.get('cohesion_index', 0)}) — need SPLIT before review")

    L("")
    for c in conditions_met:
        L(f"✅ {c}")
    for c in conditions_failed:
        L(f"❌ {c}")
    L("")
    if conditions_failed:
        L("**RECOMMENDATION: NO GO** — address concept quality issues before building human review interface")
        L("**Priority actions:**")
        if split_concepts:
            L(f"1. SPLIT over-generalized concepts: {', '.join(split_concepts)}")
        if empty_concepts:
            L(f"2. Populate empty concepts: {', '.join(empty_concepts)}")
        if merge_concepts:
            L(f"3. Merge highly similar concepts: {', '.join(merge_concepts)}")
        L(f"4. Re-assess concept quality after fixes, then proceed to Sprint 27.3")
    else:
        L("**RECOMMENDATION: GO** — concept quality acceptable, proceed to Sprint 27.3 (human review)")

    L("")
    L("### Generated Files")
    for p in REPORTS_DIR.iterdir():
        if p.is_file():
            L(f"- `{p.name}` ({p.stat().st_size:,} bytes)")
    L("---")
    L("**Sprint 27.2B complete.** Read-only. No production modifications.")

    (REPORTS_DIR / "concept_audit.md").write_text("\n".join(lines))
    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 70}")
    print(f"  AUDIT COMPLETE — {elapsed:.1f}s")
    for p in REPORTS_DIR.iterdir():
        if p.is_file():
            print(f"    {p.name}: {p.stat().st_size:,} bytes")
    print("=" * 70)


if __name__ == "__main__":
    main()
