from __future__ import annotations

import re
from typing import Any

from patterns.pattern_catalog import AccountingPattern


class PatternBuilder:
    def build(
        self,
        pattern_id: str,
        family: str,
        description: str,
        priority: int,
        confidence: float,
        regex_pattern: str,
        *,
        keywords_forbidden: list[str] | None = None,
        examples: list[str] | None = None,
        negative_examples: list[str] | None = None,
        semantic_type: str = "",
        standard_code: str = "",
        financial_statement: str = "",
        economic_nature: str = "",
        expected_side: str = "",
        contra_account: str = "",
        learnable: bool = True,
    ) -> AccountingPattern:
        compiled = re.compile(regex_pattern, re.IGNORECASE)
        return AccountingPattern(
            pattern_id=pattern_id,
            family=family,
            description=description,
            priority=priority,
            confidence=confidence,
            regex=compiled,
            keywords_forbidden=keywords_forbidden or [],
            examples=examples or [],
            negative_examples=negative_examples or [],
            semantic_type=semantic_type,
            standard_code=standard_code,
            financial_statement=financial_statement,
            economic_nature=economic_nature,
            expected_side=expected_side,
            contra_account=contra_account,
            learnable=learnable,
        )

    def from_dict(self, data: dict[str, Any]) -> AccountingPattern:
        return self.build(
            pattern_id=data["pattern_id"],
            family=data["family"],
            description=data.get("description", ""),
            priority=data.get("priority", 99),
            confidence=data.get("confidence", 0.7),
            regex_pattern=data.get("regex", data.get("regex_pattern", "")),
            keywords_forbidden=data.get("keywords_forbidden"),
            examples=data.get("examples"),
            negative_examples=data.get("negative_examples"),
            semantic_type=data.get("semantic_type", ""),
            standard_code=data.get("standard_code", ""),
            financial_statement=data.get("financial_statement", ""),
            economic_nature=data.get("economic_nature", ""),
            expected_side=data.get("expected_side", ""),
            contra_account=data.get("contra_account", ""),
            learnable=data.get("learnable", True),
        )

    def validate_pattern(
        self, pattern: AccountingPattern
    ) -> list[str]:
        errors: list[str] = []
        if not pattern.pattern_id:
            errors.append("pattern_id is required")
        if not pattern.family:
            errors.append("family is required")
        if not pattern.regex.pattern:
            errors.append("regex pattern is required")
        if pattern.confidence < 0 or pattern.confidence > 1:
            errors.append("confidence must be between 0 and 1")
        if not pattern.description:
            errors.append("description is required")
        return errors

    def test_pattern_on_examples(
        self,
        pattern: AccountingPattern,
        normalizer: Any = None,
    ) -> dict[str, list[str]]:
        from patterns.pattern_normalizer import PatternNormalizer
        norm = normalizer or PatternNormalizer()
        results: dict[str, list[str]] = {
            "passed": [],
            "failed_positive": [],
            "failed_negative": [],
        }
        for ex in pattern.examples:
            normalized = norm.normalize(ex)
            if pattern.regex.search(normalized):
                results["passed"].append(ex)
            else:
                results["failed_positive"].append(ex)
        for ex in pattern.negative_examples:
            normalized = norm.normalize(ex)
            forbidden = pattern.keywords_forbidden
            from patterns.pattern_matcher import PatternMatcher
            matcher = PatternMatcher(norm)
            match = matcher.match(ex, pattern)
            if match is None:
                results["passed"].append(ex)
            else:
                results["failed_negative"].append(ex)
        return results
