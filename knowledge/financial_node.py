from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FinancialNode:
    code: str
    name: str
    class_: str = ""
    subclass: str = ""
    parent_code: str | None = None
    children_codes: list[str] = field(default_factory=list)
    contra_accounts: list[str] = field(default_factory=list)
    semantic_types: list[str] = field(default_factory=list)
    ifrs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    kpi_groups: list[str] = field(default_factory=list)
    presentation_order: int = 0
    is_group: bool = False
    nature: str = ""
    signo_normal: int = 1
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "class_": self.class_,
            "subclass": self.subclass,
            "parent_code": self.parent_code,
            "children_codes": list(self.children_codes),
            "contra_accounts": list(self.contra_accounts),
            "semantic_types": list(self.semantic_types),
            "ifrs": list(self.ifrs),
            "tags": list(self.tags),
            "kpi_groups": list(self.kpi_groups),
            "presentation_order": self.presentation_order,
            "is_group": self.is_group,
            "nature": self.nature,
            "signo_normal": self.signo_normal,
            "description": self.description,
        }
