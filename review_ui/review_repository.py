from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from review_ui.review_models import ReviewDecision, DecisionStatus


class ReviewRepository:
    def __init__(self, db_path: str | Path = "review_ui/reviews.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_decisions (
                    review_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    account_name TEXT NOT NULL DEFAULT '',
                    document_id TEXT NOT NULL DEFAULT '',
                    company TEXT NOT NULL DEFAULT '',
                    current_concept TEXT NOT NULL DEFAULT '',
                    current_concept_name TEXT NOT NULL DEFAULT '',
                    suggested_concept TEXT NOT NULL DEFAULT '',
                    suggested_concept_name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    reviewer TEXT NOT NULL DEFAULT '',
                    reason TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    comments TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_decision(self, row: sqlite3.Row) -> ReviewDecision:
        return ReviewDecision(
            review_id=row["review_id"],
            trace_id=row["trace_id"],
            variant=row["variant"],
            account_name=row["account_name"],
            document_id=row["document_id"],
            company=row["company"],
            current_concept=row["current_concept"],
            current_concept_name=row["current_concept_name"],
            suggested_concept=row["suggested_concept"],
            suggested_concept_name=row["suggested_concept_name"],
            status=DecisionStatus(row["status"]),
            reviewer=row["reviewer"],
            reason=row["reason"],
            confidence=row["confidence"],
            comments=row["comments"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save(self, decision: ReviewDecision) -> None:
        d = decision.to_dict()
        d["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO review_decisions
                   (review_id, trace_id, variant, account_name, document_id,
                    company, current_concept, current_concept_name,
                    suggested_concept, suggested_concept_name,
                    status, reviewer, reason, confidence, comments,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                tuple(d.get(k) for k in self._columns()),
            )
            conn.commit()

    def get(self, review_id: str) -> ReviewDecision | None:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM review_decisions WHERE review_id = ?", (review_id,)
            )
            row = cur.fetchone()
            return self._row_to_decision(row) if row else None

    def load_by_status(self, status: DecisionStatus | None = None) -> list[ReviewDecision]:
        with self._conn() as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM review_decisions WHERE status = ? ORDER BY created_at",
                    (status.value,),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM review_decisions ORDER BY created_at"
                )
            return [self._row_to_decision(r) for r in cur.fetchall()]

    def load_pending(self) -> list[ReviewDecision]:
        return self.load_by_status(DecisionStatus.PENDING)

    def load_approved(self) -> list[ReviewDecision]:
        return self.load_by_status(DecisionStatus.APPROVED)

    def load_rejected(self) -> list[ReviewDecision]:
        return self.load_by_status(DecisionStatus.REJECTED)

    def load_reassigned(self) -> list[ReviewDecision]:
        return self.load_by_status(DecisionStatus.REASSIGNED)

    def exists(self, review_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM review_decisions WHERE review_id = ?", (review_id,)
            )
            return cur.fetchone() is not None

    def count_pending(self) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) as cnt FROM review_decisions WHERE status = 'PENDING'"
            )
            return cur.fetchone()["cnt"]

    def count_by_status(self) -> dict[str, int]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM review_decisions GROUP BY status"
            )
            return {r["status"]: r["cnt"] for r in cur.fetchall()}

    def all_decisions(self) -> list[ReviewDecision]:
        return self.load_by_status(None)

    def delete(self, review_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM review_decisions WHERE review_id = ?", (review_id,))
            conn.commit()

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM review_decisions")
            conn.commit()

    def _columns(self) -> list[str]:
        return [
            "review_id", "trace_id", "variant", "account_name", "document_id",
            "company", "current_concept", "current_concept_name",
            "suggested_concept", "suggested_concept_name",
            "status", "reviewer", "reason", "confidence", "comments",
            "created_at", "updated_at",
        ]
