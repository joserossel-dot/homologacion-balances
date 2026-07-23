from __future__ import annotations

import logging

from models.account_balance import AccountBalance
from models.account_amounts import AccountAmounts
from models.account_nature import AccountNature
from semantic.semantic_account import SemanticAccount
from semantic.semantic_catalog import SemanticCatalog
from semantic.semantic_context import SemanticContext
from semantic.semantic_engine import SemanticEngine
from semantic.semantic_rules import SemanticRule, build_rules

logging.disable(logging.CRITICAL)


def _make_account(
    name: str = "",
    code: str = "",
    nature: AccountNature = AccountNature.UNKNOWN,
    assets: float | None = None,
    liabilities: float | None = None,
    losses: float | None = None,
    profits: float | None = None,
    balance_debit: float | None = None,
    balance_credit: float | None = None,
) -> AccountBalance:
    return AccountBalance(
        account_code=code,
        account_name=name,
        amounts=AccountAmounts(
            assets=assets,
            liabilities=liabilities,
            losses=losses,
            profits=profits,
            balance_debit=balance_debit,
            balance_credit=balance_credit,
        ),
        nature=nature,
    )


# ---------------------------------------------------------------------------
# SemanticAccount
# ---------------------------------------------------------------------------

def test_semantic_account_defaults():
    sa = SemanticAccount()
    assert sa.semantic_type == "unknown"
    assert sa.financial_statement == "unknown"
    assert sa.economic_nature == "unknown"
    assert sa.presentation == "unknown"
    assert sa.expected_side == "unknown"
    assert sa.parent_category == "unknown"
    assert sa.contra_account_type is None
    assert sa.confidence == 0.0
    assert sa.matched_rule == ""
    assert sa.observations == ""


def test_semantic_account_full_creation():
    sa = SemanticAccount(
        semantic_type="contra_asset",
        financial_statement="balance_sheet",
        economic_nature="credit",
        presentation="non_current",
        expected_side="credit",
        parent_category="propiedad_planta_equipo",
        contra_account_type="depreciation",
        confidence=0.95,
        matched_rule="depreciacion_acumulada",
        observations="Depreciación acumulada",
    )
    assert sa.semantic_type == "contra_asset"
    assert sa.confidence == 0.95
    assert sa.contra_account_type == "depreciation"


def test_semantic_account_to_dict():
    sa = SemanticAccount(
        semantic_type="asset",
        confidence=0.9,
        matched_rule="iva_credito_fiscal",
    )
    d = sa.to_dict()
    assert d["semantic_type"] == "asset"
    assert d["confidence"] == 0.9
    assert d["matched_rule"] == "iva_credito_fiscal"
    assert d["contra_account_type"] is None


# ---------------------------------------------------------------------------
# SemanticCatalog
# ---------------------------------------------------------------------------

def test_catalog_get_known_type():
    info = SemanticCatalog.get("asset")
    assert info is not None
    assert info.category_group == "activo"
    assert "NIC" in info.ifrs_reference


def test_catalog_get_unknown_type():
    info = SemanticCatalog.get("nonexistent")
    assert info is None


def test_catalog_all_types():
    types = SemanticCatalog.all_types()
    assert "contra_asset" in types
    assert "expense" in types
    assert "asset" in types
    assert "liability" in types
    assert "unknown" in types


def test_catalog_contra_asset():
    info = SemanticCatalog.get("contra_asset")
    assert info is not None
    assert info.description == "Cuenta de valuación que reduce el saldo de un activo"


# ---------------------------------------------------------------------------
# SemanticContext
# ---------------------------------------------------------------------------

def test_context_infers_column_from_amounts():
    acct = _make_account(name="Test", assets=1000)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "activo"
    assert ctx.balance_side == "deudor"


def test_context_infers_liability_column():
    acct = _make_account(name="Test", liabilities=500)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "pasivo"
    assert ctx.balance_side == "acreedor"


def test_context_infers_loss_column():
    acct = _make_account(name="Test", losses=300)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "perdida"
    assert ctx.balance_side == "deudor"


def test_context_infers_profit_column():
    acct = _make_account(name="Test", profits=200)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "ganancia"
    assert ctx.balance_side == "acreedor"


def test_context_infers_balance_debit():
    acct = _make_account(name="Test", balance_debit=150)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "deudor"
    assert ctx.balance_side == "deudor"


def test_context_infers_balance_credit():
    acct = _make_account(name="Test", balance_credit=250)
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "acreedor"
    assert ctx.balance_side == "acreedor"


def test_context_unknown_column():
    acct = _make_account(name="Test")
    ctx = SemanticContext.from_account(acct)
    assert ctx.source_column == "unknown"
    assert ctx.balance_side == "unknown"


def test_context_code_first_digit():
    acct = _make_account(name="Test", code="1234")
    ctx = SemanticContext.from_account(acct)
    assert ctx.code_first_digit() == "1"
    assert ctx.code_prefix(2) == "12"


def test_context_code_empty():
    acct = _make_account(name="Test", code="")
    ctx = SemanticContext.from_account(acct)
    assert ctx.code_first_digit() == ""
    assert ctx.code_prefix() == ""


def test_context_from_account_static():
    acct = _make_account(name="X", assets=100)
    ctx = SemanticContext.from_account(acct)
    assert isinstance(ctx, SemanticContext)
    assert ctx.account is acct


# ---------------------------------------------------------------------------
# SemanticRule and build_rules
# ---------------------------------------------------------------------------

def test_build_rules_returns_sorted():
    rules = build_rules()
    assert len(rules) >= 10
    priorities = [r.priority for r in rules]
    assert priorities == sorted(priorities)


def test_build_rules_contains_all_named_rules():
    rules = build_rules()
    names = {r.name for r in rules}
    expected = {
        "depreciacion_acumulada",
        "amortizacion_acumulada",
        "depreciacion_del_ejercicio",
        "amortizacion_del_ejercicio",
        "iva_credito_fiscal",
        "iva_debito_fiscal",
        "provision_vacaciones",
        "gasto_por_vacaciones",
        "anticipo_proveedores",
        "anticipos_de_clientes",
    }
    assert expected.issubset(names)


def test_custom_rule():
    def always_match(ctx: SemanticContext) -> SemanticAccount | None:
        return SemanticAccount(
            semantic_type="custom",
            confidence=1.0,
            matched_rule="custom_rule",
        )

    rule = SemanticRule(name="custom_rule", priority=1, evaluate=always_match)
    ctx = SemanticContext.from_account(_make_account(name="anything"))
    result = rule.evaluate(ctx)
    assert result is not None
    assert result.semantic_type == "custom"
    assert result.matched_rule == "custom_rule"


def test_custom_rule_no_match():
    def never_match(ctx: SemanticContext) -> SemanticAccount | None:
        return None

    rule = SemanticRule(name="no_match", priority=99, evaluate=never_match)
    ctx = SemanticContext.from_account(_make_account(name="anything"))
    result = rule.evaluate(ctx)
    assert result is None


# ---------------------------------------------------------------------------
# Individual rules — Depreciación Acumulada
# ---------------------------------------------------------------------------

def test_depreciacion_acumulada_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"
    assert result.contra_account_type == "depreciation"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "credit"
    assert result.parent_category == "propiedad_planta_equipo"
    assert result.confidence == 0.95


def test_depreciacion_acumulada_variant():
    engine = SemanticEngine()
    acct = _make_account(name="DEPREC ACUMULADA", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_depreciacion_acumulada_en_pasivo():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_depreciacion_acumulada_en_perdidas_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "contra_asset"


def test_depreciacion_acumulada_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Caja General", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "contra_asset"


# ---------------------------------------------------------------------------
# Individual rules — Amortización Acumulada
# ---------------------------------------------------------------------------

def test_amortizacion_acumulada_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Amortización Acumulada", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"
    assert result.contra_account_type == "amortization"
    assert result.financial_statement == "balance_sheet"
    assert result.parent_category == "activos_intangibles"


def test_amortizacion_acumulada_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Amortiz Acumulada", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"
    assert result.contra_account_type == "amortization"


def test_amortizacion_acumulada_en_perdidas_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Amortización Acumulada", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "contra_asset"


# ---------------------------------------------------------------------------
# Individual rules — Depreciación del Ejercicio
# ---------------------------------------------------------------------------

def test_depreciacion_del_ejercicio_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación del Ejercicio", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"
    assert result.financial_statement == "income_statement"
    assert result.expected_side == "debit"
    assert result.presentation == "operating"


def test_depreciacion_ejercicio_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Ejercicio", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"


def test_depreciacion_del_ejercicio_en_activo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación del Ejercicio", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "expense"


# ---------------------------------------------------------------------------
# Individual rules — Amortización del Ejercicio
# ---------------------------------------------------------------------------

def test_amortizacion_del_ejercicio_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Amortización del Ejercicio", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"
    assert result.financial_statement == "income_statement"
    assert result.expected_side == "debit"


def test_amortizacion_ejercicio_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Amortización Ejercicio", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"


# ---------------------------------------------------------------------------
# Individual rules — IVA Crédito Fiscal
# ---------------------------------------------------------------------------

def test_iva_credito_fiscal_matches():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Crédito Fiscal", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "debit"
    assert result.parent_category == "activo_corriente"


def test_credito_fiscal_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Crédito Fiscal IVA", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"


def test_iva_credito_sin_fiscal():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Crédito", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"


def test_iva_credito_en_pasivo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Crédito Fiscal", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "asset"


# ---------------------------------------------------------------------------
# Individual rules — IVA Débito Fiscal
# ---------------------------------------------------------------------------

def test_iva_debito_fiscal_matches():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Débito Fiscal", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "credit"
    assert result.parent_category == "pasivo_corriente"


def test_debito_fiscal_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Débito Fiscal IVA", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_iva_debito_sin_fiscal():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Débito", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_iva_debito_en_activo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Débito Fiscal", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "liability"


# ---------------------------------------------------------------------------
# Individual rules — Provisión Vacaciones
# ---------------------------------------------------------------------------

def test_provision_vacaciones_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Provisión Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "credit"
    assert result.parent_category == "pasivo_corriente"


def test_provision_para_vacaciones():
    engine = SemanticEngine()
    acct = _make_account(name="Provisión para Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_provision_vacaciones_en_perdidas_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Provisión Vacaciones", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "liability"


# ---------------------------------------------------------------------------
# Individual rules — Gasto por Vacaciones
# ---------------------------------------------------------------------------

def test_gasto_por_vacaciones_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Gasto por Vacaciones", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"
    assert result.financial_statement == "income_statement"
    assert result.expected_side == "debit"
    assert result.presentation == "operating"
    assert result.parent_category == "gastos_operacionales"


def test_gasto_vacaciones_variant():
    engine = SemanticEngine()
    acct = _make_account(name="Gasto Vacaciones", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "expense"


def test_gasto_vacaciones_en_pasivo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Gasto por Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "expense"


# ---------------------------------------------------------------------------
# Individual rules — Anticipo Proveedores
# ---------------------------------------------------------------------------

def test_anticipo_proveedores_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo Proveedores", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "debit"
    assert result.parent_category == "activo_corriente"


def test_anticipo_a_proveedores():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo a Proveedores", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"


def test_anticipos_proveedores():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipos Proveedores", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"


def test_anticipo_proveedores_en_pasivo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo Proveedores", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "asset"


# ---------------------------------------------------------------------------
# Individual rules — Anticipos de Clientes
# ---------------------------------------------------------------------------

def test_anticipos_de_clientes_matches():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipos de Clientes", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"
    assert result.financial_statement == "balance_sheet"
    assert result.expected_side == "credit"
    assert result.parent_category == "pasivo_corriente"


def test_anticipo_clientes():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo Clientes", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_anticipo_de_clientes():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo de Clientes", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_anticipos_de_clientes_en_activo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipos de Clientes", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type != "liability"


# ---------------------------------------------------------------------------
# SemanticEngine — edge cases
# ---------------------------------------------------------------------------

def test_engine_no_match_returns_unknown():
    engine = SemanticEngine()
    acct = _make_account(name="ZZ Top Corporation", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"
    assert result.confidence == 0.0
    assert result.matched_rule == "no_match"


def test_engine_case_insensitive():
    engine = SemanticEngine()
    acct = _make_account(name="DEPRECIACIÓN ACUMULADA", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_engine_with_custom_rules():
    def custom_match(ctx: SemanticContext) -> SemanticAccount | None:
        if "custom" in ctx.account.account_name.lower():
            return SemanticAccount(
                semantic_type="custom_type",
                confidence=0.8,
                matched_rule="custom_rule",
            )
        return None

    custom_rule = SemanticRule(name="custom_rule", priority=1, evaluate=custom_match)
    engine = SemanticEngine(rules=[custom_rule])
    acct = _make_account(name="custom account")
    result = engine.interpret(acct)
    assert result.semantic_type == "custom_type"
    assert result.matched_rule == "custom_rule"


def test_engine_empty_rules():
    engine = SemanticEngine(rules=[])
    acct = _make_account(name="whatever")
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"
    assert result.matched_rule == "no_match"


def test_engine_priority_ordering():
    call_order: list[str] = []

    def rule_a(ctx: SemanticContext) -> SemanticAccount | None:
        call_order.append("a")
        return None

    def rule_b(ctx: SemanticContext) -> SemanticAccount | None:
        call_order.append("b")
        return SemanticAccount(semantic_type="found_b", matched_rule="b")

    def rule_c(ctx: SemanticContext) -> SemanticAccount | None:
        call_order.append("c")
        return None

    rules = [
        SemanticRule(name="c", priority=30, evaluate=rule_c),
        SemanticRule(name="a", priority=10, evaluate=rule_a),
        SemanticRule(name="b", priority=20, evaluate=rule_b),
    ]
    engine = SemanticEngine(rules=rules)
    acct = _make_account(name="test")
    result = engine.interpret(acct)
    assert result.semantic_type == "found_b"
    assert call_order == ["a", "b"]


def test_engine_returns_first_match_not_best():
    call_order: list[str] = []

    def first(ctx: SemanticContext) -> SemanticAccount | None:
        call_order.append("first")
        return SemanticAccount(semantic_type="first_match", matched_rule="first")

    def second(ctx: SemanticContext) -> SemanticAccount | None:
        call_order.append("second")
        return SemanticAccount(semantic_type="second_match", matched_rule="second")

    rules = [
        SemanticRule(name="first", priority=10, evaluate=first),
        SemanticRule(name="second", priority=20, evaluate=second),
    ]
    engine = SemanticEngine(rules=rules)
    acct = _make_account(name="test")
    result = engine.interpret(acct)
    assert result.semantic_type == "first_match"
    assert call_order == ["first"]


def test_engine_with_code():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada", code="1.2.3", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


# ---------------------------------------------------------------------------
# Ambiguous cases
# ---------------------------------------------------------------------------

def test_depreciacion_sola_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_depreciacion_acumulada_edificio():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada Edificio", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_depreciacion_maquinaria_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Maquinaria", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_iva_solo_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="IVA", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_iva_credito():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Crédito", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "asset"


def test_iva_debito():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Débito", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "liability"


def test_resultado_ejercicio_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Resultado del Ejercicio", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_resultado_acumulado_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Resultado Acumulado", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_utilidad_ejercicio_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Utilidad del Ejercicio", profits=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_utilidad_retenida_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Utilidad Retenida", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


# ---------------------------------------------------------------------------
# Column awareness — rules that check acceptable_columns
# ---------------------------------------------------------------------------

def test_contra_asset_rejected_in_perdidas():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_expense_rejected_in_activo():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación del Ejercicio", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_iva_credito_rejected_in_pasivo():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Crédito Fiscal", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_iva_debito_rejected_in_activo():
    engine = SemanticEngine()
    acct = _make_account(name="IVA Débito Fiscal", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_provision_rejected_in_perdidas():
    engine = SemanticEngine()
    acct = _make_account(name="Provisión Vacaciones", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_gasto_vacaciones_rejected_in_pasivo():
    engine = SemanticEngine()
    acct = _make_account(name="Gasto por Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_anticipo_proveedores_rejected_in_pasivo():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo Proveedores", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_anticipos_clientes_rejected_in_activo():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipos de Clientes", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


# ---------------------------------------------------------------------------
# Forbidden keyword tests
# ---------------------------------------------------------------------------

def test_depreciacion_acumulada_with_ejercicio_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación Acumulada del Ejercicio", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_depreciacion_ejercicio_with_acumulada_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación del Ejercicio Acumulada", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_provision_vacaciones_with_gasto_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Gasto Provisión Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_anticipo_proveedores_with_clientes_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="Anticipo a Proveedores y Clientes", assets=1000)
    result = engine.interpret(acct)
    # "clientes" is forbidden for anticipo_proveedores
    assert result.semantic_type == "unknown"


# ---------------------------------------------------------------------------
# Vacaciones alone should not match
# ---------------------------------------------------------------------------

def test_vacaciones_alone_does_not_match():
    engine = SemanticEngine()
    acct = _make_account(name="Vacaciones", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


# ---------------------------------------------------------------------------
# Reproduction tests for real-world DEPRECIACION ACUMULADA cases
# These reproduce exact account names found in the actual dataset
# that were NOT being classified by the production pipeline.
# Root cause: missing dictionary entries + accent normalization mismatch
# ---------------------------------------------------------------------------

def test_depreciacion_acumulada_real_case_no_accent():
    engine = SemanticEngine()
    acct = _make_account(name="DEPRECIACION ACUMULADA", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"
    assert result.contra_account_type == "depreciation"
    assert result.matched_rule == "depreciacion_acumulada"


def test_depreciacion_acumulada_real_case_with_accent():
    engine = SemanticEngine()
    acct = _make_account(name="DEPRECIACIÓN ACUMULADA", liabilities=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"
    assert result.contra_account_type == "depreciation"


def test_depreciacion_acumulada_real_case_capitalized():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciacion Acumulada", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_depreciacion_acumulada_with_suffix():
    engine = SemanticEngine()
    acct = _make_account(name="Depreciación acumulada maquinaria", assets=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "contra_asset"


def test_depreciacion_acumulada_real_case_in_profit_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="DEPRECIACION ACUMULADA", profits=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


def test_depreciacion_acumulada_real_case_in_loss_no_match():
    engine = SemanticEngine()
    acct = _make_account(name="DEPRECIACIÓN ACUMULADA", losses=1000)
    result = engine.interpret(acct)
    assert result.semantic_type == "unknown"


# ---------------------------------------------------------------------------
# Pipeline integration reproduction test:
# Verifies that the dictionary fix correctly classifies bare DEPRECIACION ACUMULADA
# through HomologationPipeline._classify_account (dictionary exact match)
# ---------------------------------------------------------------------------

def test_pipeline_classifies_depreciacion_acumulada():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp._classify_account("", "DEPRECIACION ACUMULADA")
    assert result.get("standard_code") == "ANC.01", f"Expected ANC.01, got {result}"
    assert result.get("method") == "dictionary_exact", f"Expected dictionary_exact, got {result}"


def test_pipeline_classifies_depreciacion_acumulada_accent():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp._classify_account("", "DEPRECIACIÓN ACUMULADA")
    assert result.get("standard_code") == "ANC.01", f"Expected ANC.01, got {result}"
    assert result.get("method") == "dictionary_exact"


def test_pipeline_classifies_depreciacion_acumulada_capitalized():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp._classify_account("", "Depreciacion Acumulada")
    assert result.get("standard_code") == "ANC.01", f"Expected ANC.01, got {result}"
    assert result.get("method") == "dictionary_exact"


# ---------------------------------------------------------------------------
# Shadow Mode Integration Tests
# ---------------------------------------------------------------------------

def test_shadow_semantic_engine_in_pipeline():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    assert hasattr(hp, "_semantic_engine")
    assert hp._semantic_engine is not None


def test_shadow_result_in_classified():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    classified = result.get("classified", [])
    assert len(classified) > 0
    for acct in classified:
        assert "semantic_result" in acct
        sr = acct["semantic_result"]
        for key in ("semantic_type", "financial_statement", "economic_nature",
                     "expected_side", "confidence", "matched_rule", "observations"):
            assert key in sr, f"Missing key {key} in semantic_result"


def test_shadow_does_not_alter_pipeline_output():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    for acct in result.get("classified", []):
        for key in ("method", "standard_code", "final_code", "confidence", "reason", "nature"):
            assert key in acct, f"Pipeline output missing {key}"
            original_keys = {"account_code", "account_name", "nature", "classification_amount",
                              "standard_code", "final_code", "confidence", "method",
                              "reason", "special_rule", "source_file", "source_page"}
        assert "semantic_result" in acct, "semantic_result should be present"
        assert acct.get("method") != "", "method should not be empty"


def test_shadow_metrics_in_summary():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    for key in ("semantic_total", "semantic_matches", "semantic_unknown", "semantic_confidence_avg"):
        assert key in result, f"Missing metric {key} in summary"
    assert result["semantic_total"] > 0
    assert result["semantic_total"] == result["semantic_matches"] + result["semantic_unknown"]
    assert 0.0 <= result["semantic_confidence_avg"] <= 1.0


def test_shadow_metrics_counting():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    classified = result.get("classified", [])
    actual_matches = sum(1 for a in classified if a["semantic_result"]["semantic_type"] != "unknown")
    actual_unknown = sum(1 for a in classified if a["semantic_result"]["semantic_type"] == "unknown")
    assert result["semantic_matches"] == actual_matches, (
        f"semantic_matches {result['semantic_matches']} != actual {actual_matches}"
    )
    assert result["semantic_unknown"] == actual_unknown, (
        f"semantic_unknown {result['semantic_unknown']} != actual {actual_unknown}"
    )


def test_shadow_no_classified_still_has_metrics():
    from pipeline.homologation_pipeline import HomologationPipeline
    from pathlib import Path
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/BALANCE CLASIFICADO CENTRAL 2019.pdf")
    assert result["semantic_total"] == 0
    assert result["semantic_matches"] == 0
    assert result["semantic_unknown"] == 0
    assert result["semantic_confidence_avg"] == 0.0


def test_shadow_semantic_detects_pipeline_unclassified():
    from pipeline.homologation_pipeline import HomologationPipeline
    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    semantic_but_not_pipeline = [
        a for a in result.get("classified", [])
        if a["semantic_result"]["semantic_type"] != "unknown"
        and a.get("standard_code") is None
    ]
    for a in semantic_but_not_pipeline:
        assert a["method"] == "unclassified"


def test_shadow_report_data_integrity():
    from pipeline.homologation_pipeline import HomologationPipeline
    from reports.semantic_shadow_report import build_shadow_report
    from pathlib import Path
    import tempfile
    import shutil

    hp = HomologationPipeline()
    result = hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf")
    tmp = Path(tempfile.mkdtemp())
    try:
        report_path = build_shadow_report([result], output_dir=str(tmp / "shadow"))
        assert Path(report_path).exists()
        content = Path(report_path).read_text()
        assert "Shadow Report" in content
        assert "Semantic Engine" in content
        assert "Resumen General" in content
        assert "Top Reglas Semánticas" in content
        # Verify real data appears in report
        has_rule = False
        for a in result.get("classified", []):
            rule = a.get("semantic_result", {}).get("matched_rule", "")
            if rule and rule != "":
                has_rule = True
                assert rule in content, f"Rule {rule} not found in report"
        if has_rule:
            assert "Top Reglas Semánticas" in content
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_shadow_report_with_multiple_files():
    from pipeline.homologation_pipeline import HomologationPipeline
    from reports.semantic_shadow_report import build_shadow_report
    from pathlib import Path
    import tempfile
    import shutil

    hp = HomologationPipeline()
    results = [
        hp.process("datasets/edge_cases/2018 01 15 Balance OPE simplificado.pdf"),
        hp.process("datasets/edge_cases/BALANCE CLASIFICADO AICSA 2019.pdf"),
    ]
    tmp = Path(tempfile.mkdtemp())
    try:
        report_path = build_shadow_report(results, output_dir=str(tmp / "shadow_multi"))
        assert Path(report_path).exists()
        content = Path(report_path).read_text()
        assert "Archivos procesados" in content
        assert str(len(results)) in content
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


def test_shadow_report_with_no_data():
    from reports.semantic_shadow_report import build_shadow_report
    from pathlib import Path
    import tempfile
    import shutil

    tmp = Path(tempfile.mkdtemp())
    try:
        report_path = build_shadow_report([], output_dir=str(tmp / "shadow_empty"))
        assert Path(report_path).exists()
        content = Path(report_path).read_text()
        assert "0" in content
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


# ---------------------------------------------------------------------------
# Run guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    this = sys.modules[__name__]
    passed = 0
    failed = 0
    for name in sorted(dir(this)):
        if name.startswith("test_"):
            try:
                getattr(this, name)()
                print(f"  \u2713 {name}")
                passed += 1
            except Exception as e:
                print(f"  \u2717 {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
