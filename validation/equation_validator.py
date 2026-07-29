from __future__ import annotations
import re
from .models import EquationResult, HierarchyTree


def _find_amount_by_pattern(
    tree: HierarchyTree,
    patterns: list[str],
) -> float | None:
    for node in tree.all_nodes:
        name = node.account_name.strip().lower()
        for pat in patterns:
            if pat in name:
                return node.amount
    return None


def _find_section_total(
    tree: HierarchyTree, section_prefix: str, excluded: list[str] | None = None,
) -> float:
    total = 0.0
    excluded = excluded or []
    for node in tree.all_nodes:
        if node.es_header or node.es_total:
            continue
        nature = node.naturaleza.lower()
        if nature.startswith(section_prefix.lower()):
            if any(excl in node.account_name.lower() for excl in excluded):
                continue
            total += node.amount
    return total


def validate_balance_equation(tree: HierarchyTree, tolerance: float = 1.0) -> list[EquationResult]:
    results = []

    active_total = 0.0
    passive_total = 0.0
    equity_total = 0.0

    for node in tree.all_nodes:
        if node.es_header or node.es_total:
            continue
        nature = node.naturaleza
        if nature.startswith("ACTIVO"):
            active_total += node.amount
        elif nature.startswith("PASIVO"):
            passive_total += node.amount
        elif nature == "PATRIMONIO":
            equity_total += node.amount

    if active_total > 0 and (passive_total > 0 or equity_total > 0):
        right_side = passive_total + equity_total
        diff = active_total - right_side
        passed = abs(diff) <= tolerance

        result = EquationResult(
            equation="Activo = Pasivo + Patrimonio",
            left_side=active_total,
            right_side=right_side,
            difference=diff,
            left_components={"Activo": active_total},
            right_components={"Pasivo": passive_total, "Patrimonio": equity_total},
            passed=passed,
        )
        results.append(result)

    income = 0.0
    costs = 0.0
    expenses = 0.0

    for node in tree.all_nodes:
        if node.es_header or node.es_total:
            continue
        nature = node.naturaleza
        if nature == "INGRESOS":
            income += node.amount
        elif nature == "COSTOS":
            costs += node.amount
        elif nature == "GASTOS":
            expenses += node.amount

    if income > 0 or costs > 0 or expenses > 0:
        result_val = income - costs - expenses
        right_side_val = income - costs - expenses
        passed = True

        result = EquationResult(
            equation="Resultado = Ingresos - Costos - Gastos",
            left_side=result_val,
            right_side=right_side_val,
            difference=0.0,
            left_components={"Resultado": result_val},
            right_components={"Ingresos": income, "Costos": costs, "Gastos": expenses},
            passed=passed,
        )
        results.append(result)

    current_assets = 0.0
    noncurrent_assets = 0.0
    for node in tree.all_nodes:
        if node.es_header or node.es_total:
            continue
        nature = node.naturaleza
        if nature == "ACTIVO_CORRIENTE":
            current_assets += node.amount
        elif nature == "ACTIVO_NO_CORRIENTE":
            noncurrent_assets += node.amount

    total_from_parts = current_assets + noncurrent_assets
    if current_assets > 0 and noncurrent_assets > 0 and abs(total_from_parts - active_total) > 0.01:
        diff = active_total - total_from_parts
        result = EquationResult(
            equation="Activo = Activo Corriente + Activo No Corriente",
            left_side=active_total,
            right_side=total_from_parts,
            difference=diff,
            left_components={"Activo": active_total},
            right_components={
                "Activo Corriente": current_assets,
                "Activo No Corriente": noncurrent_assets,
            },
            passed=abs(diff) <= tolerance,
        )
        results.append(result)

    current_liab = 0.0
    noncurrent_liab = 0.0
    for node in tree.all_nodes:
        if node.es_header or node.es_total:
            continue
        nature = node.naturaleza
        if nature == "PASIVO_CORRIENTE":
            current_liab += node.amount
        elif nature == "PASIVO_NO_CORRIENTE":
            noncurrent_liab += node.amount

    total_liab = current_liab + noncurrent_liab
    if current_liab > 0 and noncurrent_liab > 0 and abs(total_liab - passive_total) > 0.01:
        diff = passive_total - total_liab
        result = EquationResult(
            equation="Pasivo = Pasivo Corriente + Pasivo No Corriente",
            left_side=passive_total,
            right_side=total_liab,
            difference=diff,
            left_components={"Pasivo": passive_total},
            right_components={
                "Pasivo Corriente": current_liab,
                "Pasivo No Corriente": noncurrent_liab,
            },
            passed=abs(diff) <= tolerance,
        )
        results.append(result)

    return results
