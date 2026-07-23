from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gold_standard.models import GoldRecord
from gold_standard.storage import GoldStorage


class GoldBuilder:
    def __init__(self, db_path: str | Path = "gold_standard.db") -> None:
        self._storage = GoldStorage(db_path)

    @property
    def storage(self) -> GoldStorage:
        return self._storage

    def close(self) -> None:
        self._storage.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_record(self, record: GoldRecord) -> int:
        if not record.review_date:
            record.review_date = datetime.now(timezone.utc).isoformat()
        if not record.last_used:
            record.last_used = record.review_date
        conn = self._storage.connection
        cursor = conn.execute(
            """
            INSERT INTO gold_records
                (source_file, account_code_original, account_name, account_nature,
                 suggested_code, suggested_confidence, final_code,
                 reviewer, review_date, comments, usage_count, last_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.source_file,
                record.account_code_original,
                record.account_name,
                record.account_nature,
                record.suggested_code,
                record.suggested_confidence,
                record.final_code,
                record.reviewer,
                record.review_date,
                record.comments,
                record.usage_count,
                record.last_used,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def add_or_update(self, record: GoldRecord) -> int:
        existing = self.find_by_name_and_code(record.account_name, record.final_code)
        if existing is not None:
            existing.increment_usage()
            self.update_record(existing.id, existing)
            return existing.id
        return self.add_record(record)

    def find_by_name_and_code(self, account_name: str, final_code: str) -> GoldRecord | None:
        conn = self._storage.connection
        cursor = conn.execute(
            "SELECT * FROM gold_records WHERE account_name = ? AND final_code = ? ORDER BY id LIMIT 1",
            (account_name, final_code),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        rec = self._storage._row_to_record(row)
        rec.id = row["id"]
        return rec

    def find_by_name(self, account_name: str) -> list[GoldRecord]:
        conn = self._storage.connection
        cursor = conn.execute(
            "SELECT * FROM gold_records WHERE account_name = ? ORDER BY id", (account_name,)
        )
        return [self._storage._row_to_record(row) for row in cursor.fetchall()]

    def find_conflicts(self) -> list[dict[str, Any]]:
        conn = self._storage.connection
        cursor = conn.execute(
            """
            SELECT account_name, COUNT(DISTINCT final_code) as code_count,
                   GROUP_CONCAT(DISTINCT final_code) as codes,
                   COUNT(*) as total_versions
            FROM gold_records
            WHERE final_code != ''
            GROUP BY account_name
            HAVING code_count > 1
            ORDER BY code_count DESC, total_versions DESC
            """
        )
        results = []
        for row in cursor.fetchall():
            results.append({
                "account_name": row["account_name"],
                "code_count": row["code_count"],
                "codes": row["codes"],
                "total_versions": row["total_versions"],
            })
        return results

    def update_record(self, record_id: int, record: GoldRecord) -> bool:
        conn = self._storage.connection
        cursor = conn.execute(
            """
            UPDATE gold_records SET
                source_file = ?,
                account_code_original = ?,
                account_name = ?,
                account_nature = ?,
                suggested_code = ?,
                suggested_confidence = ?,
                final_code = ?,
                reviewer = ?,
                review_date = ?,
                comments = ?,
                usage_count = ?,
                last_used = ?
            WHERE id = ?
            """,
            (
                record.source_file,
                record.account_code_original,
                record.account_name,
                record.account_nature,
                record.suggested_code,
                record.suggested_confidence,
                record.final_code,
                record.reviewer,
                record.review_date,
                record.comments,
                record.usage_count,
                record.last_used,
                record_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0

    def find_record(self, record_id: int) -> GoldRecord | None:
        conn = self._storage.connection
        cursor = conn.execute(
            "SELECT * FROM gold_records WHERE id = ?", (record_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._storage._row_to_record(row)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_pending(self) -> list[GoldRecord]:
        conn = self._storage.connection
        cursor = conn.execute(
            "SELECT * FROM gold_records WHERE final_code = '' ORDER BY id"
        )
        return [self._storage._row_to_record(row) for row in cursor.fetchall()]

    def list_all(self) -> list[GoldRecord]:
        conn = self._storage.connection
        cursor = conn.execute("SELECT * FROM gold_records ORDER BY id")
        return [self._storage._row_to_record(row) for row in cursor.fetchall()]

    def statistics(self) -> dict[str, Any]:
        conn = self._storage.connection
        total = conn.execute("SELECT COUNT(*) FROM gold_records").fetchone()[0]
        exact = conn.execute(
            "SELECT COUNT(*) FROM gold_records WHERE final_code != '' AND suggested_code = final_code"
        ).fetchone()[0]
        conflicts = len(self.find_conflicts())
        return {
            "total_records": total,
            "exact_hits": exact,
            "conflicts": conflicts,
        }

    def top_learned(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._storage.connection
        cursor = conn.execute(
            """
            SELECT account_name, final_code, usage_count, last_used
            FROM gold_records
            WHERE final_code != ''
            ORDER BY usage_count DESC, last_used DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
