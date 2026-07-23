"""LearningEngine — Gold Standard + Correction Queue.

Gold Standard:
  - best_match(name) → dict con source/code/confidence/matched_name
  - Consulta gold_standard.db vía SQLite

Correction Queue (infraestructura, no aprendizaje automático):
  - record() → registra corrección humana en learning_queue.json
  - get_pending() → correcciones pendientes de revisión
  - get_stats() → estadísticas del queue

No modifica el pipeline.
No aprende automáticamente.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from learning.exact_match import normalize_name
from learning.fuzzy_match import fuzzy_score
from learning.models import CorrectionEntry, CorrectionStats

logger = logging.getLogger(__name__)


class LearningEngine:
    """Gold Standard lookup + Correction queue (infraestructura).

    Dos modos:
      1. Gold Standard: consulta SQLite (best_match)
      2. Corrections: registra correcciones humanas en JSON (record)
    """

    def __init__(
        self,
        db_path: str | Path = "gold_standard.db",
        queue_path: str | Path | None = None,
    ) -> None:
        self._db_path = Path(db_path)

        if queue_path is None:
            queue_path = Path(__file__).resolve().parent.parent / "learning_queue.json"
        self._queue_path = Path(queue_path)
        self._queue: list[CorrectionEntry] = []
        self._load_queue()

        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Gold Standard
    # ------------------------------------------------------------------

    def best_match(self, account_name: str) -> dict[str, Any]:
        try:
            return self._best_match_impl(account_name)
        except Exception as e:
            logger.warning("Gold Standard lookup failed: %s", e)
            return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

    def _best_match_impl(self, account_name: str) -> dict[str, Any]:
        if not self._db_path.exists():
            return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

        conn = self._get_conn()
        norm = normalize_name(account_name)

        # 1. Exact match
        cursor = conn.execute(
            "SELECT codigo_estandar, nombre_cuenta FROM gold_standard WHERE normalized = ?",
            (norm,),
        )
        row = cursor.fetchone()
        if row is not None:
            return {
                "source": "exact",
                "code": row[0],
                "confidence": 0.98,
                "matched_name": row[1],
            }

        # 2. Fuzzy match
        cursor = conn.execute(
            "SELECT codigo_estandar, nombre_cuenta, normalized FROM gold_standard"
        )
        best_score = 0
        best_row = None
        for row in cursor.fetchall():
            score = fuzzy_score(norm, row[2])
            if score > best_score:
                best_score = score
                best_row = row

        if best_score >= 92 and best_row is not None:
            confidence = min(0.80 + (best_score - 92) * 0.01, 0.97)
            return {
                "source": "fuzzy",
                "code": best_row[0],
                "confidence": round(confidence, 4),
                "matched_name": best_row[1],
            }

        return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Correction Queue
    # ------------------------------------------------------------------

    @property
    def queue_path(self) -> Path:
        return self._queue_path

    @property
    def queue(self) -> list[CorrectionEntry]:
        return list(self._queue)

    @property
    def total_corrections(self) -> int:
        return len(self._queue)

    def record(
        self,
        account_name: str,
        corrected_code: str,
        *,
        original_code: str | None = None,
        reason: str = "",
        user: str = "system",
        source_file: str | None = None,
        account_code: str | None = None,
        source_stage: str | None = None,
        reviewed: bool = False,
    ) -> CorrectionEntry:
        now = datetime.now().isoformat(timespec="seconds")

        new_entry = CorrectionEntry(
            account_name=account_name,
            corrected_code=corrected_code,
            original_code=original_code,
            reason=reason,
            user=user,
            timestamp=now,
            source_file=source_file,
            account_code=account_code,
            source_stage=source_stage,
            reviewed=reviewed,
        )

        existing = self._find_matching(new_entry)
        if existing is not None:
            existing.frequency += 1
            existing.timestamp = now
            if reason and reason not in existing.reason:
                existing.reason = f"{existing.reason}; {reason}"
            self._save_queue()
            return existing

        self._queue.append(new_entry)
        self._save_queue()
        logger.info(
            "Correction recorded: %s %s → %s (%s)",
            account_name, original_code or "?", corrected_code, user,
        )
        return new_entry

    def record_from_decision(
        self,
        account_name: str,
        corrected_code: str,
        *,
        decision: dict[str, Any] | None = None,
        user: str = "human_reviewer",
        reason: str = "",
    ) -> CorrectionEntry:
        source_stage = None
        original_code = None
        if decision:
            source_stage = decision.get("decision_source")
            original_code = decision.get("codigo_final")
        return self.record(
            account_name=account_name,
            corrected_code=corrected_code,
            original_code=original_code,
            reason=reason or f"Human correction: {corrected_code}",
            user=user,
            source_stage=source_stage,
            reviewed=True,
        )

    def get_pending(self) -> list[CorrectionEntry]:
        return [e for e in self._queue if not e.reviewed]

    def get_by_user(self, user: str) -> list[CorrectionEntry]:
        return [e for e in self._queue if e.user == user]

    def get_by_account(self, account_name: str) -> list[CorrectionEntry]:
        norm = account_name.lower().strip()
        return [e for e in self._queue if e.account_name.lower().strip() == norm]

    def get_most_frequent(self, limit: int = 20) -> list[CorrectionEntry]:
        return sorted(self._queue, key=lambda e: -e.frequency)[:limit]

    def mark_reviewed(self, index: int) -> bool:
        if 0 <= index < len(self._queue):
            self._queue[index].reviewed = True
            self._save_queue()
            return True
        return False

    def get_stats(self) -> CorrectionStats:
        stats = CorrectionStats()
        stats.total_entries = len(self._queue)
        stats.unique_accounts = len({e.account_name.lower().strip() for e in self._queue})

        top = sorted(self._queue, key=lambda e: -e.frequency)[:10]
        stats.top_corrections = [
            {"account_name": e.account_name, "original": e.original_code,
             "corrected": e.corrected_code, "frequency": e.frequency}
            for e in top
        ]

        user_counts: Counter[str] = Counter()
        stage_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()
        for e in self._queue:
            if e.user:
                user_counts[e.user] += 1
            if e.source_stage:
                stage_counts[e.source_stage] += 1
            if e.reason:
                for r_part in e.reason.split(";"):
                    r_part = r_part.strip()
                    if r_part:
                        reason_counts[r_part] += 1
        stats.by_user = dict(user_counts)
        stats.by_source_stage = dict(stage_counts)
        stats.by_reason = dict(reason_counts)
        stats.pending_review = len(self.get_pending())

        return stats

    def import_from_disagreements(
        self, audit_path: str | Path, user: str = "system",
    ) -> int:
        import json as _json

        path = Path(audit_path)
        if not path.exists():
            logger.warning("Audit file not found: %s", audit_path)
            return 0

        with open(path) as f:
            audit = _json.load(f)

        count = 0
        for r in audit.get("discrepancies", []):
            if r.get("who_wins") == "Indefinido (requiere revisión)":
                self.record(
                    account_name=r.get("account_name", ""),
                    corrected_code="",
                    original_code=r.get("regex_code") or r.get("sm_code"),
                    reason=f"Revisión requerida: {r.get('category', '')}",
                    user=user,
                    source_stage="audit",
                    reviewed=False,
                )
                count += 1

        logger.info("Imported %d pending from %s", count, audit_path)
        return count

    # ------------------------------------------------------------------
    # Internal: queue persistence
    # ------------------------------------------------------------------

    def _find_matching(self, entry: CorrectionEntry) -> CorrectionEntry | None:
        key = entry.key
        for existing in self._queue:
            if existing.key == key:
                return existing
        return None

    def _load_queue(self) -> None:
        if self._queue_path.exists():
            try:
                with open(self._queue_path) as f:
                    raw = json.load(f)
                self._queue = [CorrectionEntry.from_dict(e) for e in raw]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load queue %s: %s", self._queue_path, e)
                self._queue = []

    def _save_queue(self) -> None:
        raw = [e.to_dict() for e in self._queue]
        with open(self._queue_path, "w") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
