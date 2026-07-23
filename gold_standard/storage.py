from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from gold_standard.models import GoldRecord


_SCHEMA = """
CREATE TABLE IF NOT EXISTS gold_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file     TEXT NOT NULL DEFAULT '',
    account_code_original TEXT NOT NULL DEFAULT '',
    account_name    TEXT NOT NULL DEFAULT '',
    account_nature  TEXT NOT NULL DEFAULT '',
    suggested_code  TEXT NOT NULL DEFAULT '',
    suggested_confidence REAL NOT NULL DEFAULT 0.0,
    final_code      TEXT NOT NULL DEFAULT '',
    reviewer        TEXT NOT NULL DEFAULT '',
    review_date     TEXT NOT NULL DEFAULT '',
    comments        TEXT NOT NULL DEFAULT '',
    usage_count     INTEGER NOT NULL DEFAULT 1,
    last_used       TEXT NOT NULL DEFAULT ''
);
"""


class GoldStorage:
    def __init__(self, db_path: str | Path = "gold_standard.db") -> None:
        self._path = Path(db_path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        existing = set()
        for row in self._conn.execute("PRAGMA table_info(gold_records)").fetchall():
            existing.add(row["name"])
        for col, dtype in [("usage_count", "INTEGER NOT NULL DEFAULT 1"),
                           ("last_used", "TEXT NOT NULL DEFAULT ''")]:
            if col not in existing:
                self._conn.execute(f"ALTER TABLE gold_records ADD COLUMN {col} {dtype}")

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> GoldRecord:
        return GoldRecord(
            source_file=row["source_file"],
            account_code_original=row["account_code_original"],
            account_name=row["account_name"],
            account_nature=row["account_nature"],
            suggested_code=row["suggested_code"],
            suggested_confidence=row["suggested_confidence"],
            final_code=row["final_code"],
            reviewer=row["reviewer"],
            review_date=row["review_date"],
            comments=row["comments"],
            usage_count=row["usage_count"],
            last_used=row["last_used"],
        )

    def _record_to_dict(self, record: GoldRecord) -> dict[str, Any]:
        d = record.to_dict()
        d.pop("review_date", None)
        return d
