from __future__ import annotations

from typing import Any


SEMANTIC_TYPE_MAP: dict[str, dict[str, str]] = {
    "asset": {
        "financial_statement": "balance_sheet",
        "economic_nature": "debit",
        "presentation": "current",
        "expected_side": "debit",
        "parent_category": "activo_corriente",
    },
    "liability": {
        "financial_statement": "balance_sheet",
        "economic_nature": "credit",
        "presentation": "current",
        "expected_side": "credit",
        "parent_category": "pasivo_corriente",
    },
    "equity": {
        "financial_statement": "balance_sheet",
        "economic_nature": "credit",
        "presentation": "non_current",
        "expected_side": "credit",
        "parent_category": "patrimonio",
    },
    "revenue": {
        "financial_statement": "income_statement",
        "economic_nature": "credit",
        "presentation": "operating",
        "expected_side": "credit",
        "parent_category": "ingresos_operacionales",
    },
    "expense": {
        "financial_statement": "income_statement",
        "economic_nature": "debit",
        "presentation": "operating",
        "expected_side": "debit",
        "parent_category": "gastos_operacionales",
    },
    "contra_asset": {
        "financial_statement": "balance_sheet",
        "economic_nature": "credit",
        "presentation": "non_current",
        "expected_side": "credit",
        "parent_category": "propiedad_planta_equipo",
    },
    "contra_liability": {
        "financial_statement": "balance_sheet",
        "economic_nature": "debit",
        "presentation": "current",
        "expected_side": "debit",
        "parent_category": "pasivo_corriente",
    },
    "contra_equity": {
        "financial_statement": "balance_sheet",
        "economic_nature": "debit",
        "presentation": "non_current",
        "expected_side": "debit",
        "parent_category": "patrimonio",
    },
}

NATURE_TO_EXPECTED: dict[str, str] = {
    "deudora": "asset",
    "acreedora": "liability",
    "profit": "revenue",
    "loss": "expense",
}

COLUMN_MAP: dict[str, str] = {
    "asset": "activo",
    "liability": "pasivo",
    "revenue": "ganancia",
    "expense": "perdida",
}

NEXT_PRIORITY: int = 60


def generate_rule_for_candidate(candidate: dict) -> dict[str, Any]:
    semantic_type = candidate.get("suggested_semantic_type", "unknown")
    keywords = candidate.get("suggested_keywords", [])
    if not keywords:
        return {"error": "no keywords", "code": ""}

    type_config = SEMANTIC_TYPE_MAP.get(semantic_type, SEMANTIC_TYPE_MAP["asset"])
    dominant_nature = candidate.get("dominant_nature", "")

    rule_name = _build_rule_name(keywords, semantic_type)
    priority = _compute_priority(candidate)

    kw_groups = _build_keyword_groups(keywords)
    forbidden = _infer_forbidden(keywords, semantic_type)
    column = COLUMN_MAP.get(semantic_type, "activo")

    code = _render_rule_code(
        rule_name=rule_name,
        priority=priority,
        keywords=keywords,
        required_keywords=kw_groups,
        forbidden_keywords=forbidden,
        column=column,
        semantic_type=semantic_type,
        financial_statement=type_config["financial_statement"],
        economic_nature=type_config["economic_nature"],
        presentation=type_config["presentation"],
        expected_side=type_config["expected_side"],
        parent_category=type_config["parent_category"],
        base_confidence=0.90,
        observations=_build_observations(keywords, semantic_type),
    )

    return {
        "rule_name": rule_name,
        "priority": priority,
        "suggested_semantic_type": semantic_type,
        "keywords": keywords,
        "keyword_groups": kw_groups,
        "forbidden_keywords": forbidden,
        "acceptable_column": column,
        "code": code,
        "size": candidate.get("size", 0),
        "confidence_score": candidate.get("confidence_score", 0.0),
        "examples": _get_examples(candidate),
    }


def _build_rule_name(keywords: list[str], semantic_type: str) -> str:
    base = "_".join(keywords[:2])
    if len(base) > 40:
        base = base[:40]
    return base


def _compute_priority(candidate: dict) -> int:
    global NEXT_PRIORITY
    p = NEXT_PRIORITY
    NEXT_PRIORITY += 10
    return p


def _build_keyword_groups(keywords: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    for kw in keywords:
        group = _expand_keyword(kw)
        if group:
            groups.append(group)
    if not groups:
        groups = [keywords]
    return groups


def _expand_keyword(kw: str) -> list[str]:
    kw_lower = kw.lower()
    forms = {kw_lower}

    if kw_lower.endswith("s"):
        forms.add(kw_lower[:-1])
    if not kw_lower.endswith("s"):
        forms.add(kw_lower + "s")

    vowel_to_accent = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
    for c, accented in vowel_to_accent.items():
        if c in kw_lower:
            forms.add(kw_lower.replace(c, accented))
        if accented in kw_lower:
            forms.add(kw_lower.replace(accented, c))

    return list(forms)


def _infer_forbidden(keywords: list[str], semantic_type: str) -> list[str]:
    forbidden: list[str] = []
    if semantic_type in ("asset",):
        forbidden = ["acumulada", "acum"]
    elif semantic_type in ("liability",):
        forbidden = ["acumulada", "acum"]
    return forbidden


def _build_observations(keywords: list[str], semantic_type: str) -> str:
    desc = {
        "asset": "Activo",
        "liability": "Pasivo",
        "revenue": "Ingreso",
        "expense": "Gasto",
        "contra_asset": "Cuenta complementaria de activo",
        "equity": "Patrimonio",
    }
    label = desc.get(semantic_type, semantic_type)
    return f"{label} detectado por palabras clave: {', '.join(keywords)}"


def _get_examples(candidate: dict) -> list[dict]:
    source_files = candidate.get("source_files", [])
    return source_files[:3]


def _render_rule_code(
    rule_name: str,
    priority: int,
    keywords: list[str],
    required_keywords: list[list[str]],
    forbidden_keywords: list[str],
    column: str,
    semantic_type: str,
    financial_statement: str,
    economic_nature: str,
    presentation: str,
    expected_side: str,
    parent_category: str,
    base_confidence: float,
    observations: str,
) -> str:
    lines: list[str] = []
    lines.append(f"    _context_rule(")
    lines.append(f'        name="{rule_name}",')
    lines.append(f"        priority={priority},")
    lines.append(f"        required_keywords={_format_kw_groups(required_keywords)},")
    if forbidden_keywords:
        lines.append(f"        forbidden_keywords={forbidden_keywords},")
    lines.append(f'        acceptable_columns=["{column}"],')
    lines.append(f'        semantic_type="{semantic_type}",')
    lines.append(f'        financial_statement="{financial_statement}",')
    lines.append(f'        economic_nature="{economic_nature}",')
    lines.append(f'        presentation="{presentation}",')
    lines.append(f'        expected_side="{expected_side}",')
    lines.append(f'        parent_category="{parent_category}",')
    lines.append(f"        base_confidence={base_confidence},")
    lines.append(f'        observations="{observations}",')
    lines.append(f"    ),")
    return "\n".join(lines)


def _format_kw_groups(groups: list[list[str]]) -> str:
    inner = ", ".join(repr(g) for g in groups)
    return f"[{inner}]"
