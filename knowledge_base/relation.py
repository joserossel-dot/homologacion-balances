from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Relation:
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    bidirectional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "bidirectional": self.bidirectional,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Relation:
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=data["relation_type"],
            weight=data.get("weight", 1.0),
            bidirectional=data.get("bidirectional", False),
            metadata=data.get("metadata", {}),
        )


_RELATION_TYPES = {
    "parent_of",
    "child_of",
    "contra_of",
    "related_to",
    "similar_to",
    "depends_on",
    "adjusts",
    "alternative_to",
}


class RelationManager:
    def __init__(self) -> None:
        self._relations: list[Relation] = []

    def add(self, relation: Relation) -> None:
        if relation.relation_type not in _RELATION_TYPES:
            raise ValueError(f"Unknown relation type: {relation.relation_type}")
        self._relations.append(relation)

    def remove(self, source_id: str, target_id: str, relation_type: str) -> bool:
        before = len(self._relations)
        self._relations = [
            r for r in self._relations
            if not (r.source_id == source_id and r.target_id == target_id and r.relation_type == relation_type)
        ]
        return len(self._relations) < before

    def find(self, source_id: str, target_id: str, relation_type: str) -> Relation | None:
        for r in self._relations:
            if r.source_id == source_id and r.target_id == target_id and r.relation_type == relation_type:
                return r
        return None

    def find_by_source(self, source_id: str) -> list[Relation]:
        return [r for r in self._relations if r.source_id == source_id]

    def find_by_target(self, target_id: str) -> list[Relation]:
        return [r for r in self._relations if r.target_id == target_id]

    def find_by_type(self, relation_type: str) -> list[Relation]:
        return [r for r in self._relations if r.relation_type == relation_type]

    def find_by_account(self, account_id: str) -> list[Relation]:
        return [
            r for r in self._relations
            if r.source_id == account_id or r.target_id == account_id
        ]

    def all_relations(self) -> list[Relation]:
        return list(self._relations)

    def count(self) -> int:
        return len(self._relations)

    def supported_types(self) -> set[str]:
        return _RELATION_TYPES
