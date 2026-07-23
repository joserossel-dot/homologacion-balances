from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge_base.account import FinancialAccount
from knowledge_base.relation import Relation
from knowledge_base.rule import Rule
from knowledge_base.synonym import SynonymEntry
from knowledge_base.repository import Repository


class Loader:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def load_from_json(self, path: str | Path) -> int:
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        count = 0

        for raw in data.get("accounts", []):
            account = FinancialAccount.from_dict(raw)
            self._repository.add_account(account)
            count += 1

        for raw in data.get("synonyms", []):
            entry = SynonymEntry.from_dict(raw)
            self._repository.add_synonym(entry)

        for raw in data.get("relations", []):
            relation = Relation.from_dict(raw)
            self._repository.add_relation(relation)

        for raw in data.get("rules", []):
            rule = Rule.from_dict(raw)
            self._repository.add_rule(rule)

        return count

    def load_from_dict(self, data: dict[str, Any]) -> int:
        count = 0

        for raw in data.get("accounts", []):
            account = FinancialAccount.from_dict(raw)
            self._repository.add_account(account)
            count += 1

        for raw in data.get("synonyms", []):
            entry = SynonymEntry.from_dict(raw)
            self._repository.add_synonym(entry)

        for raw in data.get("relations", []):
            relation = Relation.from_dict(raw)
            self._repository.add_relation(relation)

        for raw in data.get("rules", []):
            rule = Rule.from_dict(raw)
            self._repository.add_rule(rule)

        return count
