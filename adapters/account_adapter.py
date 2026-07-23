from __future__ import annotations

from models.account_balance import AccountBalance
from models.account_amounts import AccountAmounts
from parser_universal import CuentaRaw, OrigenColumna


_COLUMN_MAP = {
    OrigenColumna.ACTIVO: "assets",
    OrigenColumna.PASIVO: "liabilities",
    OrigenColumna.PERDIDA: "losses",
    OrigenColumna.GANANCIA: "profits",
    OrigenColumna.DEUDOR: "balance_debit",
    OrigenColumna.ACREEDOR: "balance_credit",
}


class AccountAdapter:
    @staticmethod
    def from_cuenta_raw(cuenta_raw: CuentaRaw) -> AccountBalance:
        amounts = AccountAmounts()
        target_field = _COLUMN_MAP.get(cuenta_raw.origen_columna)
        if target_field and cuenta_raw.monto is not None:
            setattr(amounts, target_field, cuenta_raw.monto)

        warnings: list[str] = []
        if cuenta_raw.es_total:
            warnings.append("detected as total/subtotal row")

        return AccountBalance(
            account_code=cuenta_raw.codigo or "",
            account_name=cuenta_raw.nombre,
            amounts=amounts,
            source_page=0,
            source_file="",
            extractor="parser_universal",
            confidence=cuenta_raw.confianza_extraccion,
            warnings=warnings,
        )

    @staticmethod
    def to_account_balance(cuenta_raw: CuentaRaw) -> AccountBalance:
        return AccountAdapter.from_cuenta_raw(cuenta_raw)
