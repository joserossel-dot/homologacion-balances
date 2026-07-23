from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SynonymEntry:
    term: str
    account_id: str
    source: str = "manual"
    confidence: float = 1.0
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "account_id": self.account_id,
            "source": self.source,
            "confidence": self.confidence,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SynonymEntry:
        return cls(
            term=data["term"],
            account_id=data["account_id"],
            source=data.get("source", "manual"),
            confidence=data.get("confidence", 1.0),
            active=data.get("active", True),
        )


class SynonymManager:
    def __init__(self) -> None:
        self._entries: list[SynonymEntry] = []

    def add(self, entry: SynonymEntry) -> None:
        existing = self.find(entry.term, entry.account_id)
        if existing is None:
            self._entries.append(entry)

    def remove(self, term: str, account_id: str) -> bool:
        before = len(self._entries)
        self._entries = [
            e for e in self._entries
            if not (e.term == term and e.account_id == account_id)
        ]
        return len(self._entries) < before

    def find(self, term: str, account_id: str) -> SynonymEntry | None:
        for e in self._entries:
            if e.term == term and e.account_id == account_id:
                return e
        return None

    def find_by_term(self, term: str) -> list[SynonymEntry]:
        return [e for e in self._entries if e.term == term and e.active]

    def find_by_account(self, account_id: str) -> list[SynonymEntry]:
        return [e for e in self._entries if e.account_id == account_id and e.active]

    def all_entries(self) -> list[SynonymEntry]:
        return list(self._entries)

    def count(self) -> int:
        return len(self._entries)

    def has_duplicates(self) -> list[tuple[str, str]]:
        seen: dict[str, list[str]] = {}
        duplicates: list[tuple[str, str]] = []
        for e in self._entries:
            key = e.term.lower().strip()
            if key in seen:
                for aid in seen[key]:
                    duplicates.append((e.term, aid))
                duplicates.append((e.term, e.account_id))
            else:
                seen[key] = []
            seen[key].append(e.account_id)
        return duplicates
