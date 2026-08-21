from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SemanticAccount:
    semantic_type: str = "unknown"
    financial_statement: str = "unknown"
    economic_nature: str = "unknown"
    presentation: str = "unknown"
    expected_side: str = "unknown"
    parent_category: str = "unknown"
    contra_account_type: str | None = None
    confidence: float = 0.0
    matched_rule: str = ""
    observations: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_type": self.semantic_type,
            "financial_statement": self.financial_statement,
            "economic_nature": self.economic_nature,
            "presentation": self.presentation,
            "expected_side": self.expected_side,
            "parent_category": self.parent_category,
            "contra_account_type": self.contra_account_type,
            "confidence": self.confidence,
            "matched_rule": self.matched_rule,
            "observations": self.observations,
        }
