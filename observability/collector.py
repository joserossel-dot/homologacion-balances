from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_context import DocumentContext


@dataclass
class ModuleMetrics:
    name: str = ""
    elapsed_seconds: float = 0.0
    error: str | None = None
    accounts_in: int = 0
    accounts_out: int = 0


@dataclass
class ObservabilityReport:
    run_id: str = ""
    timestamp: str = ""
    source_file: str = ""
    total_elapsed: float = 0.0
    module_timings: dict[str, float] = field(default_factory=dict)
    module_errors: list[dict[str, Any]] = field(default_factory=list)
    coverage_pct: float = 0.0
    unknown_pct: float = 0.0
    learning_hits: int = 0
    decision_types: dict[str, int] = field(default_factory=dict)
    qa_approved: bool = False
    qa_confidence: float = 0.0
    validation_score: float = 0.0
    integrity_score: float = 0.0
    conflicts: int = 0
    human_review: int = 0
    total_accounts: int = 0
    flow_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "source_file": self.source_file,
            "total_elapsed_seconds": self.total_elapsed,
            "module_timings": self.module_timings,
            "module_errors": self.module_errors,
            "coverage_pct": self.coverage_pct,
            "unknown_pct": self.unknown_pct,
            "learning_hits": self.learning_hits,
            "decision_types": self.decision_types,
            "qa_approved": self.qa_approved,
            "qa_confidence": self.qa_confidence,
            "validation_score": self.validation_score,
            "integrity_score": self.integrity_score,
            "conflicts": self.conflicts,
            "human_review": self.human_review,
            "total_accounts": self.total_accounts,
            "flow_breakdown": self.flow_breakdown,
        }


class ObservabilityCollector:
    def __init__(self):
        self._modules: dict[str, ModuleMetrics] = {}
        self._start = datetime.now(timezone.utc)
        self._source_file = ""

    def start_module(self, name: str) -> None:
        self._modules[name] = ModuleMetrics(name=name)

    def end_module(self, name: str, elapsed: float, error: str | None = None) -> None:
        if name in self._modules:
            self._modules[name].elapsed_seconds = elapsed
            self._modules[name].error = error

    def report(self, ctx: DocumentContext) -> ObservabilityReport:
        classified = ctx.get_custom("classified", [])
        ignored = ctx.get_custom("ignored", [])

        coverage_data = ctx.get_custom("coverage", {}) or {}
        coverage_pct = coverage_data.get("overall", 0.0) if isinstance(coverage_data, dict) else 0.0

        decision_stats = ctx.get_custom("decision_stats", {}) or {}
        qa = ctx.get_custom("self_qa", {}) or {}

        total = len(classified) + len(ignored)
        unclassified = sum(1 for c in classified if c.get("standard_code") is None)

        report = ObservabilityReport(
            run_id=ctx.document_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_file=ctx.source_file,
            total_elapsed=sum(m.elapsed_seconds for m in self._modules.values()),
            module_timings={n: m.elapsed_seconds for n, m in self._modules.items()},
            module_errors=[{"module": n, "error": m.error} for n, m in self._modules.items() if m.error],
            coverage_pct=coverage_pct,
            unknown_pct=unclassified / total if total else 0.0,
            learning_hits=sum(1 for c in classified if c.get("method", "").startswith("learning_")),
            decision_types={k: v for k, v in decision_stats.items() if isinstance(v, int) and not k.startswith("_")} if isinstance(decision_stats, dict) else {},
            qa_approved=qa.get("approval_state") in ("APPROVED", "approved") if isinstance(qa, dict) else False,
            qa_confidence=qa.get("confidence", {}).get("overall", 0.0) if isinstance(qa.get("confidence"), dict) else 0.0,
            conflicts=decision_stats.get("conflicts_detected", 0) if isinstance(decision_stats, dict) else 0,
            human_review=sum(1 for c in classified if c.get("confidence", 1.0) < 0.85),
            total_accounts=total,
            flow_breakdown=self._build_flow_breakdown(ctx),
        )
        return report

    def _build_flow_breakdown(self, ctx: DocumentContext) -> dict[str, Any]:
        return {
            "identity": ctx.identity.to_dict() if ctx.identity else None,
            "metadata_present": ctx.metadata is not None,
            "structure_present": ctx.structure is not None,
            "parser_present": ctx.parser is not None,
            "knowledge_present": ctx.knowledge is not None,
            "validation_present": ctx.validation is not None,
            "prediction_present": ctx.prediction is not None,
            "state": ctx.state.value if ctx.state else None,
            "events_count": len(ctx.events) if ctx.events else 0,
        }
