from __future__ import annotations

from typing import Any

from models.account_balance import AccountBalance
from models.account_nature import AccountNature


class BalanceInterpreter:
    def __init__(self, account: AccountBalance) -> None:
        self._account = account

    @property
    def nature(self) -> AccountNature:
        a = self._account.amounts
        if a.assets and a.assets > 0:
            return AccountNature.ASSET
        if a.liabilities and a.liabilities > 0:
            return AccountNature.LIABILITY
        if a.losses and a.losses > 0:
            return AccountNature.LOSS
        if a.profits and a.profits > 0:
            return AccountNature.PROFIT
        return AccountNature.UNKNOWN

    @property
    def classification_amount(self) -> float | None:
        nat = self.nature
        a = self._account.amounts
        if nat == AccountNature.ASSET:
            return a.assets
        if nat == AccountNature.LIABILITY:
            return a.liabilities
        if nat == AccountNature.LOSS:
            return a.losses
        if nat == AccountNature.PROFIT:
            return a.profits
        return None

    @property
    def requires_classification(self) -> bool:
        amt = self.classification_amount
        return amt is not None and amt > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self._account.account_code,
            "account_name": self._account.account_name,
            "nature": self.nature.value,
            "classification_amount": self.classification_amount,
            "requires_classification": self.requires_classification,
            "amounts": self._account.amounts.to_dict(),
        }
