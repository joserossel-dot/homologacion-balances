from __future__ import annotations

from collections import Counter


def suggest_rules(clusters: dict[str, dict]) -> list[dict]:
    candidates: list[dict] = []
    for cid, info in clusters.items():
        members = info.get("members", [])
        if not members:
            continue

        norm = info.get("representative", "")
        size = info["size"]
        source_files = info.get("source_files", [])

        known_members = [m for m in members if m.get("method") not in ("unclassified", "", None)]
        known_codes = [m.get("final_code") for m in known_members if m.get("final_code")]

        natures = [m.get("nature") for m in members if m.get("nature")]
        if not natures:
            continue
        dominant_nature = Counter(natures).most_common(1)[0][0]

        semantic_type = _infer_semantic_type(dominant_nature)
        if not semantic_type:
            continue

        keywords = _extract_keywords(norm)
        if not keywords:
            continue

        financial_statement = "balance_sheet" if semantic_type in (
            "asset", "liability", "equity", "contra_asset", "contra_equity",
            "contra_liability",
        ) else "income_statement"

        economic_nature = "debit" if semantic_type in (
            "asset", "expense", "contra_equity", "contra_liability",
        ) else "credit"

        candidates.append({
            "cluster_id": cid,
            "representative": norm,
            "size": size,
            "num_files": len(source_files) if source_files else 0,
            "dominant_nature": dominant_nature,
            "suggested_semantic_type": semantic_type,
            "suggested_financial_statement": financial_statement,
            "suggested_economic_nature": economic_nature,
            "suggested_keywords": keywords,
            "num_known_classifications": len(known_members),
            "known_codes": known_codes[:5],
            "source_files": source_files[:5],
            "confidence_score": _compute_confidence(size, known_members, semantic_type),
        })

    candidates.sort(key=lambda c: c["confidence_score"], reverse=True)
    return candidates


def _infer_semantic_type(nature: str) -> str | None:
    mapping = {
        "deudora": "asset",
        "acreedora": "liability",
        "profit": "revenue",
        "loss": "expense",
    }
    return mapping.get(nature)


def _extract_keywords(text: str) -> list[str]:
    stop_words = {
        "de", "la", "el", "en", "por", "del", "las", "los", "al", "con",
        "su", "para", "una", "un", "y", "e", "o", "a", "que", "es", "se",
        "no", "lo", "le", "cuenta", "0000", "000",
    }
    words = text.split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _compute_confidence(
    size: int,
    known_members: list,
    semantic_type: str,
) -> float:
    score = 0.0
    if size >= 10:
        score += 0.3
    elif size >= 5:
        score += 0.2
    elif size >= 3:
        score += 0.1

    ratio = len(known_members) / max(size, 1)
    if ratio >= 0.5:
        score += 0.4
    elif ratio >= 0.2:
        score += 0.2

    if semantic_type in ("asset", "liability"):
        score += 0.2
    elif semantic_type in ("expense", "revenue"):
        score += 0.1

    return round(min(score, 1.0), 2)
