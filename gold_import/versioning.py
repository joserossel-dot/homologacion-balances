from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gold_standard.builder import GoldBuilder


class GoldSnapshot:
    def __init__(self, db_path: str | Path = "gold_standard.db"):
        self.db_path = Path(db_path)
        self.data: dict[str, Any] = {}

    def capture(self, label: str = "") -> dict[str, Any]:
        builder = GoldBuilder(str(self.db_path))
        records = builder.list_all()
        stats = builder.statistics()
        conflicts = builder.find_conflicts()
        builder.close()

        code_dist = Counter(r.final_code for r in records if r.final_code)
        source_dist = Counter(r.source_file for r in records if r.source_file)

        self.data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": label,
            "db_path": str(self.db_path),
            "total_records": len(records),
            "reviewed_records": sum(1 for r in records if r.final_code),
            "unreviewed_records": sum(1 for r in records if not r.final_code),
            "statistics": {
                "total_records": stats.get("total_records", 0),
                "exact_hits": stats.get("exact_hits", 0),
                "conflicts": stats.get("conflicts", 0),
            },
            "conflicts": [
                {"account_name": c["account_name"], "codes": c["codes"], "code_count": c["code_count"]}
                for c in conflicts
            ],
            "code_distribution": dict(code_dist.most_common(50)),
            "source_distribution": dict(source_dist.most_common(30)),
            "unique_codes": len(code_dist),
            "unique_sources": len(source_dist),
        }
        return self.data

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return out

    @staticmethod
    def load(path: str | Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
