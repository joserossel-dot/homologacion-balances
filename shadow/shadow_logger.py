from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ShadowLogger:
    def __init__(self, log_dir: str | Path = "logs/shadow") -> None:
        self._dir = Path(log_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")

    def log(
        self,
        source_file: str,
        comparisons: list[dict[str, Any]],
        match_rate: float,
    ) -> str:
        record_id = self._next_id()
        path = self._dir / f"{record_id}.json"
        data = {
            "id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_file": source_file,
            "accounts_total": len(comparisons),
            "shadow_match_rate": round(match_rate, 4),
            "comparisons": comparisons,
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return str(path)

    def build_comparison(
        self,
        account_name: str,
        account_code: str,
        legacy_code: str | None,
        legacy_confidence: float,
        new_code: str | None,
        new_confidence: float,
        new_method: str,
        learning_hit: bool,
    ) -> dict[str, Any]:
        match = legacy_code == new_code
        return {
            "account_name": account_name,
            "account_code": account_code,
            "legacy_code": legacy_code,
            "legacy_confidence": legacy_confidence,
            "new_code": new_code,
            "new_confidence": new_confidence,
            "new_method": new_method,
            "learning_hit": learning_hit,
            "match": match,
        }
