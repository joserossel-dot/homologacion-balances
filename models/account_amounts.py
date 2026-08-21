from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


@dataclass
class AccountAmounts:
    debit: float | None = None
    credit: float | None = None
    balance_debit: float | None = None
    balance_credit: float | None = None
    assets: float | None = None
    liabilities: float | None = None
    losses: float | None = None
    profits: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountAmounts:
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
