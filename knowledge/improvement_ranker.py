from __future__ import annotations

from collections import defaultdict


def rank_improvements(
    rule_candidates: list[dict],
    synonyms: list[dict],
    total_unclassified: int,
) -> list[dict]:
    ranked: list[dict] = []

    for c in rule_candidates:
        score = c.get("confidence_score", 0.0)
        size = c.get("size", 0)
        weighted = round(score * size, 1)
        ranked.append({
            "type": "new_semantic_rule",
            "description": f"Nueva regla: '{c['suggested_keywords'][0] if c['suggested_keywords'] else c['representative']}' -> {c['suggested_semantic_type']}",
            "representative": c["representative"],
            "cluster_size": size,
            "confidence": score,
            "weighted_impact": weighted,
            "priority": 0,
            "action": f"Crear regla semántica con keywords={c['suggested_keywords']}, tipo={c['suggested_semantic_type']}, estado_financiero={c['suggested_financial_statement']}",
        })

    syn_groups_added: set[str] = set()
    for s in synonyms:
        label = s["group_label"]
        if label in syn_groups_added:
            continue
        syn_groups_added.add(label)
        nv = s.get("num_variants", 0)
        impact = min(nv * 10, 100)
        ranked.append({
            "type": "dictionary_synonyms",
            "description": f"Grupo de sinónimos: '{label}' ({nv} variantes)",
            "representative": label,
            "cluster_size": nv,
            "confidence": 0.7,
            "weighted_impact": round(0.7 * impact, 1),
            "priority": 0,
            "action": f"Agregar variantes de '{label}' al diccionario: {s['variants'][:5]}...",
        })

    ranked.sort(key=lambda x: (x["weighted_impact"], x["confidence"]), reverse=True)

    for i, item in enumerate(ranked, 1):
        item["priority"] = i

    return ranked
