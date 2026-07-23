from __future__ import annotations

from typing import Any

import pandas as pd

from interpreters.balance_interpreter import BalanceInterpreter
from models.account_balance import AccountBalance


class DataFrameMapper:
    COLUMNS = [
        "account_code",
        "account_name",
        "nature",
        "classification_amount",
        "confidence",
        "warnings",
        "source_file",
        "source_page",
    ]

    def to_dataframe(self, accounts: list[AccountBalance]) -> pd.DataFrame:
        rows: list[list[Any]] = []
        for ab in accounts:
            interp = BalanceInterpreter(ab)
            rows.append([
                ab.account_code,
                ab.account_name,
                interp.nature.value,
                interp.classification_amount,
                ab.confidence,
                "; ".join(ab.warnings) if ab.warnings else "",
                ab.source_file,
                ab.source_page,
            ])
        return pd.DataFrame(rows, columns=self.COLUMNS)
