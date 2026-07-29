from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_context import DocumentContext


@dataclass
class ExecutionMetrics:
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    elapsed_seconds: float = 0.0
    module_timings: dict[str, float] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"

    @property
    def success(self) -> bool:
        return self.status == "completed" and not self.errors


@dataclass
class BackendStatistics:
    total_accounts: int = 0
    classified: int = 0
    unclassified: int = 0
    ignored: int = 0
    coverage_pct: float = 0.0
    unknown_pct: float = 0.0
    learning_hits: int = 0
    decision_types: dict[str, int] = field(default_factory=dict)
    qa_approved: bool = False
    qa_confidence: float = 0.0
    qa_risk: float = 0.0
    validation_score: float = 0.0
    integrity_score: float = 0.0
    conflicts: int = 0
    human_review_required: int = 0


@dataclass
class BackendResult:
    document_context: DocumentContext | None = None
    coverage: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    decision_stats: dict[str, Any] = field(default_factory=dict)
    qa: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    review: dict[str, Any] = field(default_factory=dict)
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    statistics: BackendStatistics = field(default_factory=BackendStatistics)
    logs: list[dict[str, Any]] = field(default_factory=list)
    export_paths: dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    pipeline_version: str = "2.0.0-rc1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "pipeline_version": self.pipeline_version,
            "execution": {
                "status": self.execution.status,
                "start_time": self.execution.start_time.isoformat(),
                "end_time": self.execution.end_time.isoformat() if self.execution.end_time else None,
                "elapsed_seconds": self.execution.elapsed_seconds,
                "module_timings": self.execution.module_timings,
                "errors": self.execution.errors,
                "success": self.execution.success,
            },
            "statistics": {
                "total_accounts": self.statistics.total_accounts,
                "classified": self.statistics.classified,
                "unclassified": self.statistics.unclassified,
                "ignored": self.statistics.ignored,
                "coverage_pct": self.statistics.coverage_pct,
                "unknown_pct": self.statistics.unknown_pct,
                "learning_hits": self.statistics.learning_hits,
                "decision_types": self.statistics.decision_types,
                "qa_approved": self.statistics.qa_approved,
                "qa_confidence": self.statistics.qa_confidence,
                "qa_risk": self.statistics.qa_risk,
                "validation_score": self.statistics.validation_score,
                "integrity_score": self.statistics.integrity_score,
                "conflicts": self.statistics.conflicts,
                "human_review_required": self.statistics.human_review_required,
            },
            "coverage": self.coverage,
            "decisions": self.decisions,
            "decision_stats": self.decision_stats,
            "qa": self.qa,
            "validation": self.validation,
            "review": self.review,
            "export_paths": self.export_paths,
            "logs": self.logs,
        }
