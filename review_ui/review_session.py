from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from review_ui.review_models import ReviewDecision, DecisionStatus
from review_ui.review_repository import ReviewRepository


QUEUE_PATH = Path("reports/cmcc_review_pipeline/review_queue.xlsx")


class ReviewSession:
    def __init__(self, repo: ReviewRepository | None = None):
        self.repo = repo or ReviewRepository()
        self._loaded_count = 0

    def load_pending(
        self,
        queue_path: str | Path = QUEUE_PATH,
        limit: int = 0,
        force: bool = False,
    ) -> list[ReviewDecision]:
        if not Path(queue_path).exists():
            return []

        df = pd.read_excel(queue_path)
        entries = df.to_dict("records")
        decisions: list[ReviewDecision] = []

        for entry in entries:
            decision = ReviewDecision.from_queue_entry(entry)
            if not force and self.repo.exists(decision.review_id):
                continue
            self.repo.save(decision)
            decisions.append(decision)

        self._loaded_count = len(decisions)

        if limit > 0:
            pending = self.repo.load_pending()
            return pending[:limit]

        return decisions

    def get_pending(self, limit: int = 0) -> list[ReviewDecision]:
        pending = self.repo.load_pending()
        if limit > 0:
            return pending[:limit]
        return pending

    def get_by_status(self, status: DecisionStatus) -> list[ReviewDecision]:
        return self.repo.load_by_status(status)

    def get_decision(self, review_id: str) -> ReviewDecision | None:
        return self.repo.get(review_id)

    def summary(self) -> dict[str, Any]:
        counts = self.repo.count_by_status()
        return {
            "total_loaded": self._loaded_count,
            "pending": counts.get("PENDING", 0),
            "approved": counts.get("APPROVED", 0),
            "rejected": counts.get("REJECTED", 0),
            "reassigned": counts.get("REASSIGNED", 0),
            "total_decisions": sum(counts.values()),
        }
