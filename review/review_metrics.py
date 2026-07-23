from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from review.review_models import (
    PendingAccount,
    DashboardMetrics,
    account_to_pending,
)


LOW_CONFIDENCE_THRESHOLD: float = 0.85


def compute_score(account: PendingAccount) -> float:
    return account.score


def prioritize_accounts(accounts: list[PendingAccount]) -> list[PendingAccount]:
    scored = [(compute_score(a), a) for a in accounts]
    scored.sort(key=lambda x: -x[0])
    result = []
    for i, (s, a) in enumerate(scored, 1):
        a.priority = i
        result.append(a)
    return result


def build_pending_rows(
    shadow_accounts: list[dict],
    freq_map: dict[str, int] | None = None,
    empresa_map: dict[str, int] | None = None,
    threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> list[PendingAccount]:
    if freq_map is None:
        freq_map = _build_freq_map(shadow_accounts)
    if empresa_map is None:
        empresa_map = _build_empresa_map(shadow_accounts)

    results: list[PendingAccount] = []
    for a in shadow_accounts:
        name = a.get("account_name", "")
        method = a.get("method", "unknown")
        confidence = a.get("confidence", 0.0) or 0.0

        is_pending = (
            method in ("unclassified", "unknown", "")
            or confidence < threshold
        )
        if not is_pending:
            continue

        pa = account_to_pending(
            a,
            freq=freq_map.get(name, 1),
            num_empresas=empresa_map.get(name, 1),
        )
        results.append(pa)

    return prioritize_accounts(results)


def _build_freq_map(accounts: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for a in accounts:
        name = a.get("account_name", "")
        if name:
            counter[name] += 1
    return dict(counter)


def _build_empresa_map(accounts: list[dict]) -> dict[str, int]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for a in accounts:
        name = a.get("account_name", "")
        group = a.get("source_group", "") or a.get("source_path", "")
        if name:
            mapping[name].add(group)
    return {k: len(v) for k, v in mapping.items()}


def build_low_confidence_rows(
    shadow_accounts: list[dict],
    threshold: float = LOW_CONFIDENCE_THRESHOLD,
) -> list[dict]:
    rows: list[dict] = []
    for a in shadow_accounts:
        confidence = a.get("confidence", 0.0) or 0.0
        if confidence >= threshold:
            continue
        semantic = a.get("semantic_result", {}) or {}
        rows.append({
            "Empresa": a.get("source_group", ""),
            "Cuenta": a.get("account_name", ""),
            "Método": a.get("method", "unknown"),
            "Confidence": confidence,
            "Clasificación actual": a.get("final_code", "") or a.get("standard_code", "") or "",
            "Semantic": semantic.get("semantic_type", "unknown"),
            "Learning": a.get("method", "") == "learning",
            "Código sugerido": a.get("standard_code", "") or "",
        })
    return rows


def build_dashboard(
    shadow_accounts: list[dict],
) -> DashboardMetrics:
    total = len(shadow_accounts)
    methods = Counter(a.get("method", "unknown") for a in shadow_accounts)
    semantic_types = Counter(
        a.get("semantic_result", {}).get("semantic_type", "unknown")
        for a in shadow_accounts
    )

    classified = sum(
        1 for a in shadow_accounts
        if a.get("method") not in ("unclassified", "unknown", "", None)
    )
    unknown = sum(
        1 for a in shadow_accounts
        if a.get("method") in ("unclassified", "unknown", "", None)
    )
    learning = methods.get("learning", 0)
    semantic = sum(
        1 for a in shadow_accounts
        if a.get("semantic_result", {}).get("semantic_type", "unknown") != "unknown"
    )
    codigo = methods.get("code_exact", 0) + methods.get("code_parent", 0)
    diccionario = methods.get("dictionary_exact", 0) + methods.get("dictionary_fuzzy_high", 0) + methods.get("dictionary_fuzzy_low", 0)

    confidences = [
        a.get("confidence", 0.0) or 0.0
        for a in shadow_accounts
        if (a.get("confidence", 0.0) or 0.0) > 0.0
    ]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Top companies (source groups)
    groups = Counter(a.get("source_group", "Unknown") for a in shadow_accounts)

    # Top account names
    names = Counter(a.get("account_name", "") for a in shadow_accounts if a.get("account_name"))

    # Top amounts
    amounts: list[tuple[str, float]] = []
    for a in shadow_accounts:
        name = a.get("account_name", "")
        amt = abs(a.get("classification_amount", 0.0) or 0.0)
        if name and amt > 0:
            amounts.append((name, amt))
    amounts.sort(key=lambda x: -x[1])

    return DashboardMetrics(
        total_cuentas=total,
        clasificadas=classified,
        unknown=unknown,
        learning=learning,
        semantic=semantic,
        codigo=codigo,
        diccionario=diccionario,
        cobertura_pct=round(classified / total * 100, 1) if total else 0.0,
        confianza_promedio=round(avg_conf, 4),
        top_empresas=groups.most_common(20),
        top_cuentas=names.most_common(20),
        top_montos=amounts[:20],
        top_reglas=[
            (r, c) for r, c in sorted(
                Counter(
                    a.get("semantic_result", {}).get("matched_rule", "no_match")
                    for a in shadow_accounts
                    if a.get("semantic_result", {}).get("matched_rule") not in ("no_match", "", None)
                ).most_common(20)
            )
        ],
    )
