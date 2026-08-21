from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


@dataclass
class GoldRecord:
    source_file: str = ""
    account_code_original: str = ""
    account_name: str = ""
    account_nature: str = ""
    suggested_code: str = ""
    suggested_confidence: float = 0.0
    final_code: str = ""
    reviewer: str = ""
    review_date: str = ""
    comments: str = ""
    usage_count: int = 1
    last_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = {}
        for f in fields(self):
            result[f.name] = getattr(self, f.name)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldRecord:
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def increment_usage(self) -> None:
        self.usage_count = (self.usage_count or 0) + 1
        self.last_used = datetime.now(timezone.utc).isoformat()
