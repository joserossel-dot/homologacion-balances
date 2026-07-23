from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any

from models.account_amounts import AccountAmounts
from models.account_nature import AccountNature


@dataclass
class AccountBalance:
    account_code: str = ""
    account_name: str = ""
    amounts: AccountAmounts = field(default_factory=AccountAmounts)
    nature: AccountNature = AccountNature.UNKNOWN
    source_page: int = 0
    source_file: str = ""
    extractor: str = ""
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "amounts":
                result[f.name] = value.to_dict()
            elif f.name == "nature":
                result[f.name] = value.value
            elif f.name == "warnings" and not value:
                result[f.name] = []
            else:
                result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountBalance:
        amounts_data = data.pop("amounts", {}) if isinstance(data.get("amounts"), dict) else {}
        nature_val = data.pop("nature", None) if isinstance(data.get("nature"), str) else None
        valid_keys = {f.name for f in fields(cls)} - {"amounts", "nature"}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        instance = cls(**filtered)
        instance.amounts = AccountAmounts.from_dict(amounts_data)
        if nature_val:
            try:
                instance.nature = AccountNature(nature_val)
            except ValueError:
                instance.nature = AccountNature.UNKNOWN
        return instance
