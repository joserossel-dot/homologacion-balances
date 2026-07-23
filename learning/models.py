from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CorrectionEntry:
    account_name: str
    corrected_code: str
    original_code: str | None = None
    reason: str = ""
    user: str = "system"
    timestamp: str = ""
    frequency: int = 1
    source_file: str | None = None
    account_code: str | None = None
    source_stage: str | None = None
    reviewed: bool = False

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")

    @property
    def key(self) -> str:
        norm_name = self.account_name.lower().strip()
        return f"{norm_name}|{self.original_code or ''}|{self.corrected_code}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_name": self.account_name,
            "original_code": self.original_code,
            "corrected_code": self.corrected_code,
            "reason": self.reason,
            "user": self.user,
            "timestamp": self.timestamp,
            "frequency": self.frequency,
            "source_file": self.source_file,
            "account_code": self.account_code,
            "source_stage": self.source_stage,
            "reviewed": self.reviewed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CorrectionEntry:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class CorrectionStats:
    total_entries: int = 0
    unique_accounts: int = 0
    top_corrections: list[dict[str, Any]] = field(default_factory=list)
    by_user: dict[str, int] = field(default_factory=dict)
    by_source_stage: dict[str, int] = field(default_factory=dict)
    by_reason: dict[str, int] = field(default_factory=dict)
    pending_review: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "unique_accounts": self.unique_accounts,
            "top_corrections": self.top_corrections[:10],
            "by_user": dict(sorted(self.by_user.items(), key=lambda x: -x[1])),
            "by_source_stage": dict(sorted(self.by_source_stage.items(), key=lambda x: -x[1])),
            "by_reason": dict(sorted(self.by_reason.items(), key=lambda x: -x[1])),
            "pending_review": self.pending_review,
        }
