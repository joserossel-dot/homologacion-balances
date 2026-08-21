from __future__ import annotations

from typing import Any

from .models import (
    MonetaryCoverage, CoverageIssue, CoverageSeverity,
    family_from_code, FAMILY_ORDER,
)


class MonetaryCoverageCalculator:
    """Calcula cobertura monetaria: Monto explicado / Monto total.

    Para cada familia financiera (Activo, Pasivo, Patrimonio, Resultado,
    Ingresos, Costos, Gastos) se calcula:
    - total_amount: monto total de la familia
    - explained_amount: suma de montos de cuentas clasificadas en esa familia
    - coverage_pct: explained / total
    """

    def compute(
        self,
        classified: list[dict[str, Any]],
        total_by_family: dict[str, float] | None = None,
    ) -> tuple[MonetaryCoverage, list[CoverageIssue]]:
        issues: list[CoverageIssue] = []

        amounts_by_family: dict[str, float] = {}
        for acct in classified:
            code = acct.get("final_code") or acct.get("standard_code") or ""
            family = family_from_code(code)
            amount = float(acct.get("classification_amount", 0) or 0)
            if family not in amounts_by_family:
                amounts_by_family[family] = 0.0
            amounts_by_family[family] += amount

        if total_by_family is None:
            total_by_family = self._infer_totals_from_accounts(
                classified, amounts_by_family,
            )

        by_family: dict[str, dict[str, float]] = {}
        total_amount = 0.0
        explained_amount = 0.0

        for family in FAMILY_ORDER:
            total = total_by_family.get(family, 0.0)
            explained = amounts_by_family.get(family, 0.0)
            total_amount += total
            explained_amount += explained

            if total > 0:
                coverage = explained / total
            else:
                coverage = 1.0

            by_family[family] = {
                "total": round(total, 2),
                "explained": round(explained, 2),
                "coverage_pct": round(coverage, 4),
            }

            if total > 0 and coverage < 0.95:
                issues.append(CoverageIssue(
                    issue_type="unexplained_amount",
                    severity=CoverageSeverity.HIGH if coverage < 0.8 else CoverageSeverity.MEDIUM,
                    monetary_impact=round(total - explained, 2),
                    document_impact=round(1.0 - coverage, 4),
                    detail=f"Familia {family}: {round(total - explained, 2)} no explicado ({round(coverage * 100, 2)}%)",
                    family=family,
                ))

        overall_coverage = (
            explained_amount / total_amount if total_amount > 0 else 1.0
        )

        monetary = MonetaryCoverage(
            total_amount=total_amount,
            explained_amount=explained_amount,
            coverage_pct=overall_coverage,
            by_family=by_family,
        )

        return monetary, issues

    def _infer_totals_from_accounts(
        self,
        classified: list[dict[str, Any]],
        amounts_by_family: dict[str, float],
    ) -> dict[str, float]:
        total_by_family: dict[str, float] = {}
        for acct in classified:
            code = acct.get("final_code") or acct.get("standard_code") or ""
            family = family_from_code(code)
            amount = float(acct.get("classification_amount", 0) or 0)
            if family not in total_by_family:
                total_by_family[family] = 0.0
            total_by_family[family] += amount
        return total_by_family

    def compute_from_ctx(
        self,
        classified: list[dict[str, Any]],
        validation_data: Any = None,
        structure_data: Any = None,
    ) -> tuple[MonetaryCoverage, list[CoverageIssue]]:
        total_by_family: dict[str, float] = {}

        if validation_data is not None:
            subtotal_validation = getattr(validation_data, "subtotal_validation", None)
            if subtotal_validation:
                for sv in subtotal_validation:
                    name = getattr(sv, "account_name", "") or ""
                    expected = float(getattr(sv, "expected", 0) or 0)
                    family = self._family_from_subtotal_name(name)
                    if family and expected > 0:
                        total_by_family[family] = expected

        if structure_data is not None and not total_by_family:
            sections = getattr(structure_data, "sections", []) or []
            tree = getattr(structure_data, "tree", None)
            if tree:
                for section in sections:
                    section_name = section.get("name", "") if isinstance(section, dict) else getattr(section, "name", "")
                    family = self._family_from_section_name(section_name)
                    total_amount = self._sum_section_amounts(tree, section)
                    if family and total_amount > 0:
                        if family not in total_by_family or total_by_family[family] == 0:
                            total_by_family[family] = total_amount

        return self.compute(classified, total_by_family or None)

    def _family_from_subtotal_name(self, name: str) -> str | None:
        name_lower = name.lower()
        for keyword, family in [
            ("total activo", "Activo"),
            ("total pasivo", "Pasivo"),
            ("total patrimonio", "Patrimonio"),
            ("total resultado", "Resultado"),
            ("total ingresos", "Ingresos"),
            ("total costos", "Costos"),
            ("total gastos", "Gastos"),
        ]:
            if keyword in name_lower:
                return family
        return None

    def _family_from_section_name(self, name: str) -> str | None:
        if not name:
            return None
        name_lower = name.lower()
        for keyword, family in [
            ("activo", "Activo"),
            ("pasivo", "Pasivo"),
            ("patrimonio", "Patrimonio"),
            ("resultado", "Resultado"),
            ("ingresos", "Ingresos"),
            ("costos", "Costos"),
            ("gastos", "Gastos"),
        ]:
            if keyword in name_lower:
                return family
        return None

    def _sum_section_amounts(self, tree: Any, section: Any) -> float:
        try:
            nodes = getattr(tree, "nodes", []) or []
            section_name = section.get("name", "") if isinstance(section, dict) else getattr(section, "name", "")
            if not section_name:
                return 0.0
            total = 0.0
            for node in nodes:
                node_section = getattr(node, "section", "") if not isinstance(node, dict) else node.get("section", "")
                if node_section and node_section.lower() == section_name.lower():
                    amount = float(getattr(node, "amount", 0) or 0) if not isinstance(node, dict) else float(node.get("amount", 0) or 0)
                    total += amount
            return total
        except Exception:
            return 0.0
