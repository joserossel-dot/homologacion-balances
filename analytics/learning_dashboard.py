from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

from gold_standard.builder import GoldBuilder
from validation.validation_session import ValidationSession

logger = logging.getLogger(__name__)


class LearningDashboard:
    def __init__(self, db_path: str | Path = "gold_standard.db") -> None:
        self._builder = GoldBuilder(db_path)
        self._refresh()

    def _refresh(self) -> None:
        self._records = self._builder.list_all()
        self._stats = self._builder.statistics()
        self._conflicts = self._builder.find_conflicts()

    @property
    def conflicts(self) -> list[dict[str, Any]]:
        self._refresh()
        return list(self._conflicts)

    def close(self) -> None:
        self._builder.close()

    def summary(self) -> dict[str, Any]:
        self._refresh()
        total = self._stats["total_records"]
        if total == 0:
            return {
                "total_records": 0,
                "exact_hits": 0,
                "conflicts": 0,
                "avg_usage_count": 0.0,
                "pending_review": 0,
                "learning_exact_pct": 0.0,
                "learning_fuzzy_pct": 0.0,
            }

        usage_counts = [r.usage_count for r in self._records if r.usage_count]
        avg_usage = sum(usage_counts) / len(usage_counts) if usage_counts else 0.0
        pending = len(self._builder.list_pending())
        with_final = [r for r in self._records if r.final_code and r.suggested_code]
        exact = sum(1 for r in with_final if r.final_code == r.suggested_code)
        fuzzy = len(with_final) - exact
        total_final = len(with_final) or 1

        return {
            "total_records": total,
            "exact_hits": self._stats["exact_hits"],
            "conflicts": self._stats["conflicts"],
            "avg_usage_count": round(avg_usage, 2),
            "pending_review": pending,
            "learning_exact_pct": round(exact / total_final * 100, 2),
            "learning_fuzzy_pct": round(fuzzy / total_final * 100, 2),
        }

    def growth_over_time(self) -> list[dict[str, Any]]:
        self._refresh()
        dates: dict[str, int] = {}
        for r in self._records:
            day = r.review_date[:10] if r.review_date else "unknown"
            dates[day] = dates.get(day, 0) + 1

        cumulative = 0
        result = []
        for day in sorted(dates):
            cumulative += dates[day]
            result.append({"date": day, "new_records": dates[day], "cumulative": cumulative})
        return result

    def top_learned(self, n: int = 100) -> list[dict[str, Any]]:
        self._refresh()
        return self._builder.top_learned(n)

    def coverage_by_company(
        self, session: ValidationSession | None = None
    ) -> list[dict[str, Any]]:
        self._refresh()
        gs_names = {r.account_name for r in self._records if r.account_name}

        if session is None:
            return [{"total_gs_records": len(gs_names)}]

        company_coverage: dict[str, dict[str, Any]] = {}
        for acct in session.processed_accounts:
            source = acct.get("source_file", "unknown")
            company_coverage.setdefault(source, {
                "source_file": source,
                "total_accounts": 0,
                "classified": 0,
                "gs_matches": 0,
                "learning_hits": 0,
            })
            entry = company_coverage[source]
            entry["total_accounts"] += 1
            if acct.get("standard_code") is not None:
                entry["classified"] += 1
            if acct.get("account_name") in gs_names:
                entry["gs_matches"] += 1
            method = acct.get("method", "")
            if method.startswith("learning_"):
                entry["learning_hits"] += 1

        sorted_coverage = sorted(
            company_coverage.values(),
            key=lambda x: x["learning_hits"],
            reverse=True,
        )
        return sorted_coverage

    def to_dataframe(self, data: list[dict[str, Any]]) -> Any:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        return pd.DataFrame(data)

    def export_excel(self, path: str | Path) -> Path:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            s = self.summary()
            pd.DataFrame([s]).to_excel(writer, sheet_name="Summary", index=False)

            growth = self.growth_over_time()
            if growth:
                pd.DataFrame(growth).to_excel(writer, sheet_name="Growth", index=False)

            top = self.top_learned(100)
            if top:
                pd.DataFrame(top).to_excel(writer, sheet_name="Top100", index=False)

            conflicts = self._conflicts
            if conflicts:
                pd.DataFrame(conflicts).to_excel(writer, sheet_name="Conflicts", index=False)

        logger.info("Learning dashboard exported to: %s", out.resolve())
        return out
