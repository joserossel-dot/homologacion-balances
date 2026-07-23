from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from patterns.pattern_catalog import AccountingPattern, PatternCatalog
from patterns.pattern_matcher import PatternMatch, PatternMatcher
from patterns.pattern_normalizer import PatternNormalizer

log = logging.getLogger(__name__)


class PatternEngine:
    def __init__(
        self,
        catalog: PatternCatalog | None = None,
        normalizer: PatternNormalizer | None = None,
        matcher: PatternMatcher | None = None,
    ) -> None:
        self.catalog = catalog or PatternCatalog()
        self.normalizer = normalizer or PatternNormalizer()
        self.matcher = matcher or PatternMatcher(self.normalizer)
        self._patterns: list[AccountingPattern] | None = None

    @property
    def patterns(self) -> list[AccountingPattern]:
        if self._patterns is None:
            self._patterns = self.catalog.get_all()
        return self._patterns

    def analyze_account(
        self, account: dict[str, Any]
    ) -> list[PatternMatch]:
        return self.matcher.match_unclassified(account, self.patterns)

    def analyze_accounts(
        self, accounts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for acct in accounts:
            matches = self.analyze_account(acct)
            normalized = self.normalizer.normalize(
                acct.get("account_name", "")
            )
            best = self.matcher.best_match(
                acct.get("account_name", ""), self.patterns
            )
            results.append({
                "account": acct,
                "normalized_name": normalized,
                "matches": matches,
                "best_match": best,
                "total_matches": len(matches),
                "is_classified": acct.get("method", "unclassified")
                not in ("unclassified", "unknown", ""),
            })
        return results

    def compute_coverage(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        total = len(results)
        unclassified = [
            r for r in results if not r["is_classified"]
        ]
        total_unclassified = len(unclassified)
        matched_unclassified = sum(
            1 for r in unclassified if r["total_matches"] > 0
        )
        matched_all = sum(1 for r in results if r["total_matches"] > 0)
        family_counts: dict[str, int] = {}
        for r in results:
            for m in r["matches"]:
                family_counts[m.family] = family_counts.get(m.family, 0) + 1
        family_unclassified: dict[str, int] = {}
        for r in unclassified:
            for m in r["matches"]:
                family_unclassified[m.family] = (
                    family_unclassified.get(m.family, 0) + 1
                )
        return {
            "total_accounts": total,
            "total_unclassified": total_unclassified,
            "matched_all": matched_all,
            "matched_unclassified": matched_unclassified,
            "coverage_unclassified_pct": round(
                matched_unclassified / total_unclassified * 100, 2
            )
            if total_unclassified > 0
            else 0.0,
            "coverage_all_pct": round(
                matched_all / total * 100, 2
            )
            if total > 0
            else 0.0,
            "family_counts": dict(
                sorted(family_counts.items(), key=lambda x: -x[1])
            ),
            "family_unclassified": dict(
                sorted(family_unclassified.items(), key=lambda x: -x[1])
            ),
        }

    def load_shadow_data(
        self, path: str | Path
    ) -> list[dict[str, Any]]:
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("accounts", [])

    def load_and_analyze(
        self, shadow_path: str | Path
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        accounts = self.load_shadow_data(shadow_path)
        log.info("Loaded %d accounts from %s", len(accounts), shadow_path)
        results = self.analyze_accounts(accounts)
        coverage = self.compute_coverage(results)
        return results, coverage

    def get_pattern_by_id(
        self, pattern_id: str
    ) -> AccountingPattern | None:
        return self.catalog.get_by_id(pattern_id)

    def get_patterns_by_family(
        self, family: str
    ) -> list[AccountingPattern]:
        return self.catalog.get_by_family(family)

    def families_summary(self) -> list[dict]:
        return self.catalog.families_summary()
