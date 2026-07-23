from __future__ import annotations

from models.account_balance import AccountBalance
from semantic.semantic_account import SemanticAccount
from semantic.semantic_context import SemanticContext
from semantic.semantic_rules import SemanticRule, build_rules


class SemanticEngine:
    def __init__(self, rules: list[SemanticRule] | None = None) -> None:
        self._rules = sorted(rules, key=lambda r: r.priority) if rules is not None else build_rules()

    def interpret(self, account: AccountBalance) -> SemanticAccount:
        ctx = SemanticContext.from_account(account)
        for rule in self._rules:
            result = rule.evaluate(ctx)
            if result is not None:
                return result
        return SemanticAccount(
            semantic_type="unknown",
            financial_statement="unknown",
            economic_nature="unknown",
            presentation="unknown",
            expected_side="unknown",
            parent_category="unknown",
            contra_account_type=None,
            confidence=0.0,
            matched_rule="no_match",
            observations="No se aplicó ninguna regla semántica",
        )
