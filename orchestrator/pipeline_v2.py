from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from document_context import DocumentContext

from adapters import (
    SIEAdapter,
    DIEAdapter,
    ParserAdapter,
    KBAdapter,
    ValidationAdapter,
    ReviewAdapter,
    DecisionAdapter,
)
from coverage_engine import CoverageAdapter
from self_qa_engine import SelfQAAdapter


class HomologationPipelineV2:
    def __init__(
        self,
        db_path: str | Path = "gold_standard.db",
        decision_weights: dict[str, float] | None = None,
        coverage_weights: dict[str, float] | None = None,
        qa_gate_thresholds: dict[str, float] | None = None,
    ):
        self._db_path = Path(db_path)
        self._adapter_sie = SIEAdapter()
        self._adapter_die = DIEAdapter()
        self._adapter_parser = ParserAdapter()
        self._adapter_kb = KBAdapter(db_path=str(self._db_path))
        self._adapter_decision = DecisionAdapter(weights=decision_weights)
        self._adapter_validation = ValidationAdapter()
        self._adapter_review = ReviewAdapter()
        self._adapter_coverage = CoverageAdapter(weights=coverage_weights)
        self._adapter_sqa = SelfQAAdapter(gate_thresholds=qa_gate_thresholds)

    def process(self, pdf_path: str | Path) -> DocumentContext:
        ctx = DocumentContext(source_file=str(pdf_path))

        ctx = self._adapter_sie.run(ctx)
        ctx = self._adapter_die.run(ctx)
        ctx = self._adapter_parser.run(ctx)
        ctx = self._adapter_kb.run(ctx)
        ctx = self._adapter_decision.run(ctx)
        ctx = self._adapter_validation.run(ctx)
        ctx = self._adapter_review.run(ctx)
        ctx = self._adapter_coverage.run(ctx)
        ctx = self._adapter_sqa.run(ctx)
        ctx.complete(module="pipeline_v2")

        return ctx

    def process_to_dict(self, pdf_path: str | Path) -> dict[str, Any]:
        start = time.perf_counter()
        ctx = self.process(pdf_path)
        elapsed = time.perf_counter() - start

        result = KBAdapter.extract_v1_summary(ctx)
        result["elapsed_seconds_v2"] = round(elapsed, 3)
        result["dce_state"] = ctx.state.value
        result["dce_events"] = len(ctx.events)
        result["dce_snapshots"] = len(ctx.snapshots)
        result["dce_document_id"] = ctx.document_id
        result["decisions"] = ctx.get_custom("decisions", [])
        result["decision_stats"] = ctx.get_custom("decision_stats", {})

        return result
