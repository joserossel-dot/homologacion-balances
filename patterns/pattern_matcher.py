from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from patterns.pattern_catalog import AccountingPattern
from patterns.pattern_normalizer import PatternNormalizer


@dataclass
class PatternMatch:
    pattern_id: str
    family: str
    confidence: float
    priority: int
    matched_patterns: list[str] = field(default_factory=list)
    tokens_found: list[str] = field(default_factory=list)
    explanation: str = ""


class PatternMatcher:
    def __init__(self, normalizer: PatternNormalizer | None = None) -> None:
        self.normalizer = normalizer or PatternNormalizer()

    def match(
        self,
        account_name: str,
        pattern: AccountingPattern,
    ) -> PatternMatch | None:
        if not account_name:
            return None
        normalized = self.normalizer.normalize(account_name)

        if not normalized:
            return None

        if self._has_forbidden(normalized, pattern.keywords_forbidden):
            return None

        match = pattern.regex.search(normalized)
        if not match:
            return None

        tokens_found = self._extract_tokens(normalized, pattern.regex)
        explanation = self._build_explanation(pattern, tokens_found)

        return PatternMatch(
            pattern_id=pattern.pattern_id,
            family=pattern.family,
            confidence=pattern.confidence,
            priority=pattern.priority,
            matched_patterns=[pattern.regex.pattern],
            tokens_found=tokens_found,
            explanation=explanation,
        )

    def match_all(
        self,
        account_name: str,
        patterns: list[AccountingPattern],
    ) -> list[PatternMatch]:
        if not account_name:
            return []
        results: list[PatternMatch] = []
        for pattern in patterns:
            result = self.match(account_name, pattern)
            if result is not None:
                results.append(result)
        return results

    def best_match(
        self,
        account_name: str,
        patterns: list[AccountingPattern],
    ) -> PatternMatch | None:
        results = self.match_all(account_name, patterns)
        if not results:
            return None
        return min(results, key=lambda m: (m.priority, -m.confidence))

    def match_unclassified(
        self,
        account: dict[str, Any],
        patterns: list[AccountingPattern],
    ) -> list[PatternMatch]:
        name = account.get("account_name", "")
        if not name:
            return []
        return self.match_all(name, patterns)

    def _has_forbidden(self, normalized: str, forbidden: list[str]) -> bool:
        if not forbidden:
            return False
        upper = normalized.upper()
        for word in forbidden:
            w = word.upper()
            if re.search(rf"\b{re.escape(w)}\b", upper):
                return True
        return False

    def _extract_tokens(
        self, normalized: str, regex: re.Pattern
    ) -> list[str]:
        match = regex.search(normalized)
        if not match:
            return []
        if match.start() != match.end():
            return normalized[match.start():match.end()].split()
        for word in normalized.split():
            if regex.search(word):
                return [word]
        return []

    def _build_explanation(
        self,
        pattern: AccountingPattern,
        tokens_found: list[str],
    ) -> str:
        tokens_str = ", ".join(tokens_found) if tokens_found else "(match)"
        return (
            f"Coincide con patrón '{pattern.pattern_id}' "
            f"(familia {pattern.family}). "
            f"Tokens: {tokens_str}"
        )


def match_patterns_on_accounts(
    accounts: list[dict],
    patterns: list[AccountingPattern],
    normalizer: PatternNormalizer | None = None,
) -> dict[str, list[PatternMatch]]:
    matcher = PatternMatcher(normalizer)
    results: dict[str, list[PatternMatch]] = {}
    for i, acct in enumerate(accounts):
        key = f"account_{i}"
        name = acct.get("account_name", "")
        matches = matcher.match_all(name, patterns)
        results[key] = matches
    return results
