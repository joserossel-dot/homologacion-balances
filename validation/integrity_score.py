from __future__ import annotations
from .models import (
    IntegrityScore,
    SubtotalResult,
    EquationResult,
    HierarchyTree,
)


def compute_extraction_score(hierarchy_tree: HierarchyTree) -> float:
    total = hierarchy_tree.total_accounts
    if total == 0:
        return 100.0

    empty_name = sum(1 for n in hierarchy_tree.all_nodes if not n.account_name.strip())
    zero_amount = sum(1 for n in hierarchy_tree.all_nodes if n.amount == 0.0)

    penalty_name = min(empty_name / total * 50, 50)
    penalty_zero = min(zero_amount / total * 30, 30)

    score = max(0, 100 - penalty_name - penalty_zero)
    return round(score, 1)


def compute_classification_score(
    hierarchy_tree: HierarchyTree,
    total_classified: int,
    total_ignored: int,
) -> float:
    total = hierarchy_tree.total_accounts
    if total == 0:
        return 100.0

    classified_ratio = total_classified / max(total, 1)
    ignored_ratio = total_ignored / max(total, 1)

    score = classified_ratio * 100 - ignored_ratio * 50
    score = max(0, min(100, score))
    return round(score, 1)


def compute_hierarchy_score(hierarchy_tree: HierarchyTree) -> float:
    total = hierarchy_tree.total_accounts
    if total == 0:
        return 100.0

    orphans = len(hierarchy_tree.roots)
    total_nodes = len(hierarchy_tree.all_nodes)

    if total_nodes <= 1:
        return 80.0

    if orphans > 1:
        orphan_penalty = min((orphans - 1) / total_nodes * 100, 50)
    else:
        orphan_penalty = 0.0

    has_depth = any(n.level > 0 for n in hierarchy_tree.all_nodes)
    depth_score = 20 if has_depth else 0

    section_count = len(set(n.naturaleza for n in hierarchy_tree.all_nodes if n.naturaleza))
    section_score = min(section_count * 5, 20)

    score = max(0, 100 - orphan_penalty + depth_score + section_score)
    score = min(100, score)
    return round(score, 1)


def compute_subtotal_score(subtotal_results: list[SubtotalResult]) -> float:
    if not subtotal_results:
        return 100.0

    passed = sum(1 for r in subtotal_results if r.passed)
    total = len(subtotal_results)

    base_score = passed / total * 100

    avg_diff = sum(abs(r.difference) for r in subtotal_results if not r.passed) / max(total, 1)
    diff_penalty = min(avg_diff / 1000 * 10, 15)

    score = max(0, base_score - diff_penalty)
    return round(score, 1)


def compute_equation_score(equation_results: list[EquationResult]) -> float:
    if not equation_results:
        return 100.0

    passed = sum(1 for r in equation_results if r.passed)
    total = len(equation_results)

    score = passed / total * 100
    return round(score, 1)


def compute_integrity_score(
    hierarchy_tree: HierarchyTree,
    subtotal_results: list[SubtotalResult],
    equation_results: list[EquationResult],
    total_classified: int = 0,
    total_ignored: int = 0,
) -> IntegrityScore:
    score = IntegrityScore()

    score.extraction_score = compute_extraction_score(hierarchy_tree)
    score.classification_score = compute_classification_score(
        hierarchy_tree, total_classified, total_ignored,
    )
    score.hierarchy_score = compute_hierarchy_score(hierarchy_tree)
    score.subtotal_score = compute_subtotal_score(subtotal_results)
    score.equation_score = compute_equation_score(equation_results)
    score.compute_overall()

    return score
