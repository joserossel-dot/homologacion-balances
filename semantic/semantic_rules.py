from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from models.account_nature import AccountNature
from semantic.semantic_account import SemanticAccount
from semantic.semantic_context import SemanticContext


RuleFn = Callable[[SemanticContext], SemanticAccount | None]


@dataclass
class SemanticRule:
    name: str
    priority: int
    evaluate: RuleFn


def _context_rule(
    name: str,
    priority: int,
    required_keywords: list[list[str]],
    forbidden_keywords: list[str] | None = None,
    acceptable_columns: list[str] | None = None,
    expected_nature: AccountNature | None = None,
    expected_balance_side: str | None = None,
    expected_code_prefix: str | None = None,
    semantic_type: str = "unknown",
    financial_statement: str = "unknown",
    economic_nature: str = "unknown",
    presentation: str = "unknown",
    expected_side: str = "unknown",
    parent_category: str = "unknown",
    contra_account_type: str | None = None,
    base_confidence: float = 0.9,
    confidence_modifier: float = 0.0,
    observations: str = "",
) -> SemanticRule:
    def evaluate(ctx: SemanticContext) -> SemanticAccount | None:
        name_lower = ctx.account.account_name.lower()

        for group in required_keywords:
            if not any(kw.lower() in name_lower for kw in group):
                return None

        if forbidden_keywords:
            for kw in forbidden_keywords:
                if kw.lower() in name_lower:
                    return None

        if acceptable_columns is not None:
            if ctx.source_column not in acceptable_columns:
                return None

        if expected_nature is not None:
            if ctx.account.nature != expected_nature:
                return None

        if expected_balance_side is not None:
            if ctx.balance_side != expected_balance_side:
                return None

        if expected_code_prefix is not None:
            if not ctx.account.account_code.startswith(expected_code_prefix):
                return None

        final_confidence = min(max(base_confidence + confidence_modifier, 0.0), 1.0)

        return SemanticAccount(
            semantic_type=semantic_type,
            financial_statement=financial_statement,
            economic_nature=economic_nature,
            presentation=presentation,
            expected_side=expected_side,
            parent_category=parent_category,
            contra_account_type=contra_account_type,
            confidence=final_confidence,
            matched_rule=name,
            observations=observations,
        )

    return SemanticRule(name=name, priority=priority, evaluate=evaluate)


RULES: list[SemanticRule] = [
    _context_rule(
        name="depreciacion_acumulada",
        priority=10,
        required_keywords=[["depreciación", "depreciacion", "deprec"], ["acumulada", "acum"]],
        forbidden_keywords=["ejercicio"],
        acceptable_columns=["activo", "pasivo"],
        semantic_type="contra_asset",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="non_current",
        expected_side="credit",
        parent_category="propiedad_planta_equipo",
        contra_account_type="depreciation",
        base_confidence=0.95,
        observations="Depreciación acumulada de propiedades, planta y equipo",
    ),
    _context_rule(
        name="amortizacion_acumulada",
        priority=11,
        required_keywords=[["amortización", "amortizacion", "amortiz"], ["acumulada", "acum"]],
        forbidden_keywords=["ejercicio"],
        acceptable_columns=["activo", "pasivo"],
        semantic_type="contra_asset",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="non_current",
        expected_side="credit",
        parent_category="activos_intangibles",
        contra_account_type="amortization",
        base_confidence=0.95,
        observations="Amortización acumulada de activos intangibles",
    ),
    _context_rule(
        name="depreciacion_del_ejercicio",
        priority=20,
        required_keywords=[["depreciación", "depreciacion", "deprec"], ["ejercicio"]],
        forbidden_keywords=["acumulada", "acum"],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.95,
        observations="Gasto por depreciación del periodo",
    ),
    _context_rule(
        name="amortizacion_del_ejercicio",
        priority=21,
        required_keywords=[["amortización", "amortizacion", "amortiz"], ["ejercicio"]],
        forbidden_keywords=["acumulada", "acum"],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.95,
        observations="Gasto por amortización del periodo",
    ),
    _context_rule(
        name="iva_credito_fiscal",
        priority=30,
        required_keywords=[["iva"], ["crédito", "credito"]],
        forbidden_keywords=["débito", "debito"],
        acceptable_columns=["activo"],
        semantic_type="asset",
        financial_statement="balance_sheet",
        economic_nature="debit",
        presentation="current",
        expected_side="debit",
        parent_category="activo_corriente",
        base_confidence=0.95,
        observations="IVA Crédito Fiscal - derecho a recuperar IVA",
    ),
    _context_rule(
        name="iva_debito_fiscal",
        priority=31,
        required_keywords=[["iva"], ["débito", "debito"]],
        forbidden_keywords=["crédito", "credito"],
        acceptable_columns=["pasivo"],
        semantic_type="liability",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="current",
        expected_side="credit",
        parent_category="pasivo_corriente",
        base_confidence=0.95,
        observations="IVA Débito Fiscal - obligación por IVA devengado",
    ),
    _context_rule(
        name="provision_vacaciones",
        priority=40,
        required_keywords=[["provisión", "provision"], ["vacaciones"]],
        forbidden_keywords=["gasto"],
        acceptable_columns=["pasivo"],
        semantic_type="liability",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="current",
        expected_side="credit",
        parent_category="pasivo_corriente",
        base_confidence=0.95,
        observations="Provisión por obligaciones de vacaciones del personal",
    ),
    _context_rule(
        name="gasto_por_vacaciones",
        priority=41,
        required_keywords=[["gasto"], ["vacaciones"]],
        forbidden_keywords=["provisión", "provision"],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.95,
        observations="Gasto por vacaciones del personal",
    ),
    _context_rule(
        name="anticipo_proveedores",
        priority=50,
        required_keywords=[["anticipo", "anticipos"], ["proveedores"]],
        forbidden_keywords=["clientes", "cliente"],
        acceptable_columns=["activo"],
        semantic_type="asset",
        financial_statement="balance_sheet",
        economic_nature="debit",
        presentation="current",
        expected_side="debit",
        parent_category="activo_corriente",
        base_confidence=0.95,
        observations="Anticipos entregados a proveedores",
    ),
    _context_rule(
        name="anticipos_de_clientes",
        priority=51,
        required_keywords=[["anticipo", "anticipos"], ["clientes", "cliente"]],
        forbidden_keywords=["proveedores"],
        acceptable_columns=["pasivo"],
        semantic_type="liability",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="current",
        expected_side="credit",
        parent_category="pasivo_corriente",
        base_confidence=0.95,
        observations="Anticipos recibidos de clientes",
    ),
]


def build_rules() -> list[SemanticRule]:
    return sorted(RULES, key=lambda r: r.priority)
