from __future__ import annotations
import re
from .models import SubtotalResult, HierarchyTree, AccountNode


SUBTOTAL_KEYWORDS = re.compile(
    r"(total\s|subtotal\s|suma\s|sumas\s)",
    re.IGNORECASE,
)

TOTAL_NAMES = re.compile(
    r"total\s+(activo|pasivo|patrimonio|ingreso|costo|gasto|"
    r"corriente|no\s+corriente|disponible|existencia|"
    r"deudor|cliente|activo|pasivo|patrimonio|"
    r"capital|resultado|activo|pasivo)|"
    r"total del|totales|subtotal",
    re.IGNORECASE,
)


def detect_subtotals(tree: HierarchyTree) -> list[AccountNode]:
    candidates = []
    for node in tree.all_nodes:
        name = node.account_name.strip()
        if SUBTOTAL_KEYWORDS.search(name) or TOTAL_NAMES.search(name):
            node.es_subtotal = True
            candidates.append(node)
        elif node.es_total:
            candidates.append(node)

    tree.subtotal_nodes = candidates
    return candidates


def _find_children_before(
    nodes: list[AccountNode],
    total_idx: int,
    prev_total_idx: int = -1,
) -> list[AccountNode]:
    children = []
    start = max(0, prev_total_idx)
    for i in range(start, total_idx):
        child = nodes[i]
        if child.es_total or child.es_subtotal:
            continue
        if child.es_header:
            continue
        if child.amount == 0.0 and child.is_leaf:
            continue
        children.append(child)
    return children


def validate_subtotals(
    tree: HierarchyTree,
    tolerance_pct: float = 1.0,
) -> list[SubtotalResult]:
    results = []
    candidates = detect_subtotals(tree)

    if not candidates:
        return results

    all_nodes_ordered = tree.all_nodes
    candidate_positions = [(all_nodes_ordered.index(c), c) for c in candidates if c.amount != 0.0]
    candidate_positions.sort(key=lambda x: x[0])

    for idx, (cand_pos, subtotal_node) in enumerate(candidate_positions):
        prev_total_pos = -1
        if idx > 0:
            prev_total_pos = candidate_positions[idx - 1][0]

        children = _find_children_before(all_nodes_ordered, cand_pos, prev_total_pos)

        if not children:
            children = _find_implicit_children(subtotal_node, tree)

        sum_children = sum(c.amount for c in children if c.amount is not None)
        reported = subtotal_node.amount

        if sum_children == 0 and reported == 0:
            continue

        diff = reported - sum_children
        pct = abs(diff) / max(abs(reported), 0.01) * 100 if reported != 0 else (100 if diff != 0 else 0)

        result = SubtotalResult(
            account_name=subtotal_node.account_name.strip(),
            account_code=subtotal_node.account_code,
            expected=reported,
            actual=sum_children,
            difference=diff,
            pct_diff=pct,
            children_count=len(children),
            children=[c.account_name.strip() for c in children],
            passed=pct <= tolerance_pct,
            line_number=subtotal_node.line_number,
        )
        results.append(result)

    return results


def _find_implicit_children(subtotal_node: AccountNode, tree: HierarchyTree) -> list[AccountNode]:
    if subtotal_node.children:
        return subtotal_node.children

    candidates = []
    section = subtotal_node.naturaleza if subtotal_node.naturaleza else ""
    name_lower = subtotal_node.account_name.lower()

    if "activo" in name_lower and "corriente" in name_lower:
        candidates = [n for n in tree.detail_nodes if n.naturaleza == "ACTIVO_CORRIENTE"]
    elif "activo" in name_lower and "no corriente" in name_lower:
        candidates = [n for n in tree.detail_nodes if n.naturaleza == "ACTIVO_NO_CORRIENTE"]
    elif "pasivo" in name_lower and "corriente" in name_lower:
        candidates = [n for n in tree.detail_nodes if n.naturaleza == "PASIVO_CORRIENTE"]
    elif "pasivo" in name_lower and "no corriente" in name_lower:
        candidates = [n for n in tree.detail_nodes if n.naturaleza == "PASIVO_NO_CORRIENTE"]
    elif "activo" in name_lower:
        candidates = tree.detail_nodes
    elif "pasivo" in name_lower:
        candidates = tree.detail_nodes

    return candidates
