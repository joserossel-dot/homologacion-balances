from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str = ""
    rule_type: str = "validation"
    severity: str = "error"
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "active": self.active,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        return cls(
            rule_id=data["rule_id"],
            name=data["name"],
            description=data.get("description", ""),
            rule_type=data.get("rule_type", "validation"),
            severity=data.get("severity", "error"),
            active=data.get("active", True),
            metadata=data.get("metadata", {}),
        )


class RuleManager:
    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def add(self, rule: Rule) -> None:
        self._rules[rule.rule_id] = rule

    def remove(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    def find_by_type(self, rule_type: str) -> list[Rule]:
        return [r for r in self._rules.values() if r.rule_type == rule_type]

    def all_rules(self) -> list[Rule]:
        return list(self._rules.values())

    def count(self) -> int:
        return len(self._rules)
