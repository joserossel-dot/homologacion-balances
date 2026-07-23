from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

from validation.validation_session import ValidationSession

logger = logging.getLogger(__name__)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


class UnclassifiedAnalyzer:
    def __init__(self, session: ValidationSession) -> None:
        self._session = session

    def analyze(self) -> dict[str, Any]:
        unclassified = [
            a for a in self._session.processed_accounts
            if _is_empty(a.get("standard_code"))
        ]
        total = len(self._session.processed_accounts)
        by_name: dict[str, dict[str, Any]] = {}

        for acct in unclassified:
            raw_name = acct.get("account_name", "") or ""
            norm = _normalize_name(raw_name)
            if not norm:
                continue
            if norm not in by_name:
                by_name[norm] = {
                    "normalized_name": norm,
                    "raw_names": set(),
                    "frequency": 0,
                    "companies": set(),
                    "files": set(),
                    "codes": set(),
                }
            entry = by_name[norm]
            entry["raw_names"].add(raw_name)
            entry["frequency"] += 1
            source = acct.get("source_file", acct.get("source_page", ""))
            if source:
                entry["files"].add(str(source))
            code = acct.get("account_code", "")
            if code:
                entry["codes"].add(str(code))

        sorted_names = sorted(
            by_name.values(), key=lambda x: x["frequency"], reverse=True
        )

        return {
            "total_unclassified": len(unclassified),
            "total_accounts": total,
            "unique_names": len(by_name),
            "unclassified_pct": round(len(unclassified) / total * 100, 2) if total else 0.0,
            "by_name": sorted_names,
        }

    def top_unclassified(self, n: int = 500) -> list[dict[str, Any]]:
        result = self.analyze()
        top = []
        for entry in result["by_name"][:n]:
            top.append({
                "normalized_name": entry["normalized_name"],
                "example_raw_name": next(iter(entry["raw_names"]), ""),
                "frequency": entry["frequency"],
                "companies_count": len(entry["companies"]),
                "files_count": len(entry["files"]),
                "unique_codes_count": len(entry["codes"]),
            })
        return top

    def to_dataframe(self, accounts: list[dict[str, Any]] | None = None) -> Any:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        if accounts is None:
            accounts = self.top_unclassified(500)
        return pd.DataFrame(accounts)

    def export_excel(self, path: str | Path, n: int = 500) -> Path:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        df = self.to_dataframe(self.top_unclassified(n))
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(out, index=False, sheet_name="Unclassified")
        logger.info("Unclassified report exported to: %s", out.resolve())
        return out
