from __future__ import annotations

import pytest

from adapters.account_adapter import AccountAdapter
from interpreters.balance_interpreter import BalanceInterpreter
from models.account_amounts import AccountAmounts
from models.account_balance import AccountBalance
from models.account_nature import AccountNature
from parser_universal import CuentaRaw, OrigenColumna


class TestBalanceInterpreter:
    def test_zero_asset_nature(self):
        amounts = AccountAmounts(assets=0.0)
        account = AccountBalance(
            account_code="1.01.01",
            account_name="Caja",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.ASSET
        assert interp.classification_amount == 0.0

    def test_zero_liability_nature(self):
        amounts = AccountAmounts(liabilities=0.0)
        account = AccountBalance(
            account_code="2.01.01",
            account_name="Proveedores",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.LIABILITY
        assert interp.classification_amount == 0.0

    def test_zero_loss_nature(self):
        amounts = AccountAmounts(losses=0.0)
        account = AccountBalance(
            account_code="4.01.01",
            account_name="Gastos",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.LOSS
        assert interp.classification_amount == 0.0

    def test_zero_profit_nature(self):
        amounts = AccountAmounts(profits=0.0)
        account = AccountBalance(
            account_code="5.01.01",
            account_name="Ingresos",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.PROFIT
        assert interp.classification_amount == 0.0

    def test_none_amounts(self):
        amounts = AccountAmounts()
        account = AccountBalance(
            account_code="",
            account_name="Sin datos",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.UNKNOWN
        assert interp.classification_amount is None

    def test_positive_asset(self):
        amounts = AccountAmounts(assets=100.0)
        account = AccountBalance(
            account_code="1.01.01",
            account_name="Caja",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.ASSET
        assert interp.classification_amount == 100.0

    def test_positive_liability(self):
        amounts = AccountAmounts(liabilities=500.0)
        account = AccountBalance(
            account_code="2.01.01",
            account_name="Proveedores",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.LIABILITY
        assert interp.classification_amount == 500.0

    def test_positive_loss(self):
        amounts = AccountAmounts(losses=200.0)
        account = AccountBalance(
            account_code="4.01.01",
            account_name="Gastos",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.LOSS
        assert interp.classification_amount == 200.0

    def test_positive_profit(self):
        amounts = AccountAmounts(profits=300.0)
        account = AccountBalance(
            account_code="5.01.01",
            account_name="Ingresos",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.PROFIT
        assert interp.classification_amount == 300.0

    def test_negative_asset_preserves_nature(self):
        amounts = AccountAmounts(assets=-50.0)
        account = AccountBalance(
            account_code="1.01.01",
            account_name="Caja",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.ASSET
        assert interp.classification_amount == -50.0

    def test_field_precedence_asset_wins(self):
        amounts = AccountAmounts(assets=100.0, liabilities=200.0)
        account = AccountBalance(
            account_code="1.01.01",
            account_name="Mixed",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.ASSET

    def test_field_precedence_liability_wins_when_asset_none(self):
        amounts = AccountAmounts(assets=None, liabilities=200.0)
        account = AccountBalance(
            account_code="2.01.01",
            account_name="Mixed",
            amounts=amounts,
        )
        interp = BalanceInterpreter(account)
        assert interp.nature == AccountNature.LIABILITY

    def test_requires_classification_false_for_zero(self):
        amounts = AccountAmounts(assets=0.0)
        account = AccountBalance(account_name="Caja", amounts=amounts)
        interp = BalanceInterpreter(account)
        assert interp.requires_classification is False

    def test_requires_classification_true_for_positive(self):
        amounts = AccountAmounts(assets=100.0)
        account = AccountBalance(account_name="Caja", amounts=amounts)
        interp = BalanceInterpreter(account)
        assert interp.requires_classification is True


class TestAccountAdapterWithZero:
    def test_adapter_sets_assets_zero(self):
        cuenta_raw = CuentaRaw(
            linea=1,
            codigo="1.01.01",
            nombre="Caja",
            monto=0.0,
            origen_columna=OrigenColumna.ACTIVO,
        )
        ab = AccountAdapter.from_cuenta_raw(cuenta_raw)
        assert ab.amounts.assets == 0.0
        assert ab.amounts.liabilities is None
        assert ab.amounts.losses is None
        assert ab.amounts.profits is None

    def test_adapter_sets_none(self):
        cuenta_raw = CuentaRaw(
            linea=2,
            codigo=None,
            nombre="Sin monto",
            monto=None,
            origen_columna=OrigenColumna.ACTIVO,
        )
        ab = AccountAdapter.from_cuenta_raw(cuenta_raw)
        assert ab.amounts.assets is None

    def test_full_flow_clientes_venta(self):
        import pipeline.homologation_pipeline as hp_module

        cuenta_raw = CuentaRaw(
            linea=1,
            codigo="1.01.05.02",
            nombre="Clientes por venta de Suministros",
            monto=0.0,
            origen_columna=OrigenColumna.ACTIVO,
        )

        ab = AccountAdapter.from_cuenta_raw(cuenta_raw)
        interp = BalanceInterpreter(ab)

        assert interp.nature == AccountNature.ASSET
        assert interp.classification_amount is not None
        assert interp.classification_amount == 0.0

        hp = hp_module.HomologationPipeline()
        classification = hp._classify_account(ab.account_code, ab.account_name)

        assert classification is not None
        assert classification.get("standard_code") == "AC.03"
        assert classification.get("confidence", 0.0) > 0.0
