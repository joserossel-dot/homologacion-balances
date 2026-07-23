from __future__ import annotations

from dataclasses import dataclass

from models.account_balance import AccountBalance
from models.account_nature import AccountNature


@dataclass
class SemanticContext:
    account: AccountBalance
    source_column: str = "unknown"
    balance_side: str = "unknown"

    def __post_init__(self) -> None:
        if self.source_column == "unknown":
            self.source_column = self._infer_source_column()
        if self.balance_side == "unknown":
            self.balance_side = self._infer_balance_side()

    @staticmethod
    def from_account(account: AccountBalance) -> SemanticContext:
        return SemanticContext(account=account)

    def _infer_source_column(self) -> str:
        a = self.account.amounts
        if a.assets is not None:
            return "activo"
        if a.liabilities is not None:
            return "pasivo"
        if a.losses is not None:
            return "perdida"
        if a.profits is not None:
            return "ganancia"
        if a.balance_debit is not None:
            return "deudor"
        if a.balance_credit is not None:
            return "acreedor"
        return "unknown"

    def _infer_balance_side(self) -> str:
        col = self.source_column
        if col in ("activo", "perdida", "deudor"):
            return "deudor"
        if col in ("pasivo", "ganancia", "acreedor"):
            return "acreedor"
        return "unknown"

    def code_first_digit(self) -> str:
        code = self.account.account_code
        if code and len(code) > 0:
            return code[0]
        return ""

    def code_prefix(self, length: int = 2) -> str:
        code = self.account.account_code
        if code and len(code) >= length:
            return code[:length]
        return code if code else ""
