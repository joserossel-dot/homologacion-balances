from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from gold_standard.models import GoldRecord


class GoldExporter:
    @staticmethod
    def to_csv(records: list[GoldRecord], output_path: str | Path) -> None:
        path = Path(output_path)
        fields = [
            "source_file", "account_code_original", "account_name",
            "account_nature", "suggested_code", "suggested_confidence",
            "final_code", "reviewer", "review_date", "comments",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_dict())

    @staticmethod
    def to_json(records: list[GoldRecord], output_path: str | Path, indent: int = 2) -> None:
        path = Path(output_path)
        data = [r.to_dict() for r in records]
        path.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def to_jsonl(records: list[GoldRecord], output_path: str | Path) -> None:
        path = Path(output_path)
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
