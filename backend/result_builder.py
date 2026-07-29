from __future__ import annotations

from pathlib import Path
from typing import Any

from document_context import DocumentContext

from backend.backend_models import BackendResult, BackendStatistics, ExecutionMetrics


class ResultBuilder:
    def build(self, ctx: DocumentContext, metrics: ExecutionMetrics,
              logs: list[dict[str, Any]], export_paths: dict[str, str]) -> BackendResult:
        result = BackendResult(
            document_context=ctx,
            source_file=ctx.source_file,
            execution=metrics,
            logs=logs,
            export_paths=export_paths,
            coverage=ctx.get_custom("coverage", {}),
            decisions=ctx.get_custom("decisions", []),
            decision_stats=ctx.get_custom("decision_stats", {}),
            qa=ctx.get_custom("self_qa", {}),
            validation=self._extract_validation(ctx),
            review=self._extract_review(ctx),
            statistics=self._build_statistics(ctx),
        )
        return result

    def _extract_validation(self, ctx: DocumentContext) -> dict[str, Any]:
        val = ctx.validation
        if val is not None:
            return val.to_dict() if hasattr(val, "to_dict") else {"raw": str(val)}
        return {}

    def _extract_review(self, ctx: DocumentContext) -> dict[str, Any]:
        return {
            "pending": len(ctx.get_custom("review_queue", [])),
            "queue": ctx.get_custom("review_queue", []),
        }

    def _build_statistics(self, ctx: DocumentContext) -> BackendStatistics:
        stats = BackendStatistics()

        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])
        all_accounts = classified + ignored

        stats.total_accounts = len(all_accounts)
        stats.classified = len(classified)
        stats.ignored = len(ignored)
        stats.unclassified = sum(
            1 for c in classified if c.get("standard_code") is None
        )

        coverage_data = ctx.get_custom("coverage", {}) or {}
        if isinstance(coverage_data, dict):
            stats.coverage_pct = coverage_data.get("overall", 0.0) or 0.0
        else:
            stats.coverage_pct = getattr(coverage_data, "overall", 0.0) or 0.0

        total = stats.total_accounts or 1
        stats.unknown_pct = stats.unclassified / total

        stats.learning_hits = sum(
            1 for c in classified if c.get("method", "").startswith("learning_")
        )

        decision_stats = ctx.get_custom("decision_stats", {}) or {}
        if isinstance(decision_stats, dict):
            stats.decision_types = {
                k: v for k, v in decision_stats.items()
                if isinstance(v, int) and not k.startswith("_")
            }
            stats.conflicts = decision_stats.get("conflicts_detected", 0)

        qa = ctx.get_custom("self_qa", {}) or {}
        if isinstance(qa, dict):
            stats.qa_approved = qa.get("approval_state") in ("APPROVED", "approved")
            stats.qa_confidence = qa.get("confidence", {}).get("overall", 0.0) if isinstance(qa.get("confidence"), dict) else 0.0
            stats.qa_risk = qa.get("risk", {}).get("total_risk", 0.0) if isinstance(qa.get("risk"), dict) else 0.0

        stats.human_review_required = sum(
            1 for c in classified if c.get("confidence", 1.0) < 0.85
        )

        return stats
