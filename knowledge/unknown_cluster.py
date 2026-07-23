from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from rapidfuzz.fuzz import token_set_ratio


UNKNOWN_METHODS = frozenset({"unclassified", "unknown", ""})


def load_unclassified(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    accounts = data.get("accounts", [])
    return [
        a for a in accounts
        if a.get("method") in UNKNOWN_METHODS or a.get("final_code") is None
    ]


def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[á]", "a", name)
    name = re.sub(r"[é]", "e", name)
    name = re.sub(r"[í]", "i", name)
    name = re.sub(r"[ó]", "o", name)
    name = re.sub(r"[ú]", "u", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def cluster_accounts(
    accounts: list[dict],
    *,
    threshold: float = 70.0,
    min_cluster_size: int = 2,
) -> dict[str, dict]:
    normalized: list[tuple[str, str, dict]] = []
    for a in accounts:
        raw = a.get("account_name", "")
        norm = normalize_name(raw)
        if norm:
            normalized.append((raw, norm, a))

    clusters: dict[str, dict] = {}
    cluster_id = 0
    assigned: set[int] = set()

    for i, (raw_i, norm_i, acct_i) in enumerate(normalized):
        if i in assigned:
            continue
        members = [acct_i]
        assigned.add(i)
        for j, (raw_j, norm_j, acct_j) in enumerate(normalized):
            if j in assigned:
                continue
            score = token_set_ratio(norm_i, norm_j)
            if score >= threshold:
                members.append(acct_j)
                assigned.add(j)

        if len(members) >= min_cluster_size:
            cid = f"cluster_{cluster_id:04d}"
            cluster_id += 1
            norm_samples = [normalize_name(m.get("account_name", "")) for m in members]
            clusters[cid] = {
                "cluster_id": cid,
                "size": len(members),
                "members": members,
                "representative": _pick_representative(members, norm_samples),
                "normalized_samples": list(dict.fromkeys(norm_samples)),
                "source_files": list(dict.fromkeys(
                    m.get("source_path", "") or m.get("source_file", "")
                    for m in members
                )),
            }

    return clusters


def _pick_representative(members: list[dict], norm_samples: list[str]) -> str:
    counter: Counter = Counter()
    for n in norm_samples:
        words = n.split()
        counter.update(words)
    common_words = [w for w, _ in counter.most_common(5)]
    if common_words:
        return " ".join(common_words)
    return members[0].get("account_name", "")


def summarize_clusters(clusters: dict[str, dict]) -> list[dict]:
    rows = []
    for cid, info in sorted(clusters.items()):
        count_classified = sum(
            1 for m in info["members"]
            if m.get("final_code") is not None and m.get("method") not in UNKNOWN_METHODS
        )
        natures = list(dict.fromkeys(
            m.get("nature") for m in info["members"] if m.get("nature")
        )) if any(m.get("nature") for m in info["members"]) else []
        rows.append({
            "cluster_id": cid,
            "size": info["size"],
            "representative": info["representative"],
            "count_classified_elsewhere": count_classified,
            "unique_natures": natures,
            "num_files": len(info.get("source_files", [])),
            "normalized_variants": info["normalized_samples"],
            "source_files": info.get("source_files", []),
        })
    return rows
