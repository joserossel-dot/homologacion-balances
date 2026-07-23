from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge_base.repository import Repository
from knowledge_base.version import VERSION


class Exporter:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": {
                "version": VERSION,
                "total_accounts": self._repository.count_accounts(),
                "total_synonyms": self._repository.synonyms.count(),
                "total_relations": self._repository.relations.count(),
                "total_rules": self._repository.rules.count(),
            },
            "accounts": [
                a.to_dict() for a in self._repository.list_accounts()
            ],
            "synonyms": [
                e.to_dict() for e in self._repository.synonyms.all_entries()
            ],
            "relations": [
                r.to_dict() for r in self._repository.relations.all_relations()
            ],
            "rules": [
                r.to_dict() for r in self._repository.rules.all_rules()
            ],
        }

    def to_json(self, path: str | Path, indent: int = 2) -> str:
        path = Path(path)
        data = self.to_dict()
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        path.write_text(content, encoding="utf-8")
        return content
