from __future__ import annotations
from .models import (
    MissingAccountCandidate,
    SubtotalResult,
    EquationResult,
    AccountNode,
    HierarchyTree,
)


def detect_missing_accounts(
    subtotal_results: list[SubtotalResult],
    equation_results: list[EquationResult],
    tree: HierarchyTree,
    tolerance_pct: float = 1.0,
) -> list[MissingAccountCandidate]:
    candidates: list[MissingAccountCandidate] = []

    target_amounts: list[tuple[float, str, int]] = []

    for sr in subtotal_results:
        if not sr.passed and abs(sr.difference) > 1.0:
            target_amounts.append((abs(sr.difference), sr.account_name, sr.line_number))

    for er in equation_results:
        if not er.passed and abs(er.difference) > 1.0:
            target_amounts.append((abs(er.difference), er.equation, -1))

    if not target_amounts:
        return candidates

    for target, context, src_line in target_amounts:
        for node in tree.all_nodes:
            if node.line_number == src_line:
                continue
            if node.amount == 0.0:
                continue

            if node.amount == target:
                candidates.append(MissingAccountCandidate(
                    target_amount=target,
                    matched_amount=node.amount,
                    line_number=node.line_number,
                    account_name=node.account_name.strip(),
                    reason=f"Exact match for difference in '{context}'",
                    similarity_pct=100.0,
                ))

        for node in tree.all_nodes:
            if node.line_number == src_line:
                continue
            if node.amount == 0.0:
                continue

            if target > 0:
                ratio = min(node.amount, target) / max(node.amount, target) * 100
                if abs(ratio - 100) <= tolerance_pct and node.amount != target:
                    candidates.append(MissingAccountCandidate(
                        target_amount=target,
                        matched_amount=node.amount,
                        line_number=node.line_number,
                        account_name=node.account_name.strip(),
                        reason=f"Similar amount ({ratio:.1f}%) for difference in '{context}'",
                        similarity_pct=round(ratio, 1),
                    ))

        for node in tree.all_nodes:
            if node.line_number == src_line:
                continue
            if node.amount == 0.0:
                continue

            if abs(node.amount + target) <= max(abs(target) * 0.01, 1.0):
                candidates.append(MissingAccountCandidate(
                    target_amount=target,
                    matched_amount=node.amount,
                    line_number=node.line_number,
                    account_name=node.account_name.strip(),
                    reason=f"Negative match (sign flip) for difference in '{context}'",
                    similarity_pct=100.0,
                ))

    seen = set()
    unique: list[MissingAccountCandidate] = []
    for c in candidates:
        key = (c.line_number, round(c.matched_amount, 2))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique[:20]
