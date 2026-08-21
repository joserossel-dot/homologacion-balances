from __future__ import annotations

from pathlib import Path
from typing import Any

from document_context import DocumentContext
from document_context.models import ExecutionData


class ReviewAdapter:
    def __init__(self, db_path: str | Path = "review_workspace/review.db"):
        self._db_path = Path(db_path)

    def run(self, ctx: DocumentContext) -> DocumentContext:
        unclassified = []
        classified = ctx.get_custom("classified", [])
        for c in classified:
            if c.get("standard_code") is None:
                unclassified.append(c)

        ctx.set_custom("review_queue", unclassified)
        ctx.set_custom("review_count", len(unclassified))

        exec_data = ExecutionData(
            review_required=len(unclassified) > 0,
            status="reviewed" if len(unclassified) == 0 else "has_pending",
        )
        ctx.set_execution(exec_data, module="review_adapter")

        ctx.mark_reviewed(module="review_adapter")

        return ctx
