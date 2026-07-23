from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.financial_graph import FinancialGraph
from knowledge.financial_node import FinancialNode
from knowledge.financial_tree import FinancialTree
from knowledge.graph_queries import GraphQueries


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    account_name: str = ""
    expected: str = ""
    found: str = ""


class GraphValidator:
    def __init__(self, graph: FinancialGraph, tree: FinancialTree) -> None:
        self._graph = graph
        self._tree = tree
        self._queries = GraphQueries(graph, tree)

    def validate_semantic_classification(
        self,
        account_name: str,
        classified_code: str,
        source_column: str,
        semantic_type: str,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        node = self._tree.get_node(classified_code)
        if node is None:
            return issues

        contra_asset_in_income = self._check_contra_asset_in_income(
            account_name, source_column, semantic_type
        )
        issues.extend(contra_asset_in_income)

        asset_mapped_to_liability = self._check_asset_liability_mismatch(
            account_name, classified_code, source_column, semantic_type
        )
        issues.extend(asset_mapped_to_liability)

        iva_debito_en_activo = self._check_iva_debito_en_activo(
            account_name, classified_code, source_column
        )
        issues.extend(iva_debito_en_activo)

        iva_credito_en_pasivo = self._check_iva_credito_en_pasivo(
            account_name, classified_code, source_column
        )
        issues.extend(iva_credito_en_pasivo)

        utilidad_retenida_como_gasto = self._check_utilidad_retenida_como_gasto(
            account_name, classified_code, semantic_type
        )
        issues.extend(utilidad_retenida_como_gasto)

        capital_como_activo = self._check_capital_como_activo(
            account_name, classified_code, source_column
        )
        issues.extend(capital_como_activo)

        return issues

    def _check_contra_asset_in_income(
        self, account_name: str, source_column: str, semantic_type: str
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if semantic_type != "contra_asset":
            return issues
        if source_column == "perdida":
            issues.append(ValidationIssue(
                severity="error",
                code="CONTRA_ASSET_IN_INCOME",
                message="Contraactivo presentado en Estado de Resultados",
                account_name=account_name,
                expected="balance_sheet",
                found="income_statement",
            ))
        return issues

    def _check_asset_liability_mismatch(
        self,
        account_name: str,
        classified_code: str,
        source_column: str,
        semantic_type: str,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        node = self._tree.get_node(classified_code)
        if node is None:
            return issues

        if node.class_ == "activo" and source_column == "pasivo":
            issues.append(ValidationIssue(
                severity="error",
                code="ASSET_IN_LIABILITY_COLUMN",
                message=f"Activo '{node.name}' clasificado en columna de pasivo",
                account_name=account_name,
                expected="activo",
                found="pasivo",
            ))
        elif node.class_ == "pasivo" and source_column == "activo":
            issues.append(ValidationIssue(
                severity="error",
                code="LIABILITY_IN_ASSET_COLUMN",
                message=f"Pasivo '{node.name}' clasificado en columna de activo",
                account_name=account_name,
                expected="pasivo",
                found="activo",
            ))
        return issues

    def _check_iva_debito_en_activo(
        self, account_name: str, classified_code: str, source_column: str
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        name_lower = account_name.lower()
        has_iva_debito = "iva" in name_lower and ("débito" in name_lower or "debito" in name_lower)
        if not has_iva_debito:
            return issues
        if source_column == "activo":
            issues.append(ValidationIssue(
                severity="error",
                code="IVA_DEBITO_EN_ACTIVO",
                message="IVA Débito Fiscal clasificado como activo",
                account_name=account_name,
                expected="pasivo",
                found="activo",
            ))
        return issues

    def _check_iva_credito_en_pasivo(
        self, account_name: str, classified_code: str, source_column: str
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        name_lower = account_name.lower()
        has_iva_credito = "iva" in name_lower and ("crédito" in name_lower or "credito" in name_lower)
        if not has_iva_credito:
            return issues
        if source_column == "pasivo":
            issues.append(ValidationIssue(
                severity="error",
                code="IVA_CREDITO_EN_PASIVO",
                message="IVA Crédito Fiscal clasificado como pasivo",
                account_name=account_name,
                expected="activo",
                found="pasivo",
            ))
        return issues

    def _check_utilidad_retenida_como_gasto(
        self, account_name: str, classified_code: str, semantic_type: str
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        name_lower = account_name.lower()
        is_utilidad_retenida = ("utilidad" in name_lower and "retenida" in name_lower) or (
            "resultado" in name_lower and "acumulado" in name_lower
        )
        if not is_utilidad_retenida:
            return issues
        if semantic_type == "expense":
            issues.append(ValidationIssue(
                severity="error",
                code="UTILIDAD_RETENIDA_COMO_GASTO",
                message="Utilidad retenida clasificada como gasto",
                account_name=account_name,
                expected="patrimonio",
                found="gasto",
            ))
        return issues

    def _check_capital_como_activo(
        self, account_name: str, classified_code: str, source_column: str
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        name_lower = account_name.lower()
        is_capital = name_lower.strip() == "capital"
        if not is_capital:
            return issues
        if source_column == "activo":
            issues.append(ValidationIssue(
                severity="error",
                code="CAPITAL_COMO_ACTIVO",
                message="Capital presentado como activo",
                account_name=account_name,
                expected="patrimonio",
                found="activo",
            ))
        return issues
