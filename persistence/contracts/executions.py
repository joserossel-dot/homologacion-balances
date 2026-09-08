"""Contrato de ejecuciones del procesamiento documental."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable


ExecutionStatus = Literal[
    "pending", "running", "review", "completed", "failed", "cancelled",
]


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    execution_id: str
    document_id: str
    status: ExecutionStatus
    application_version: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LocalExecutionRepository(Protocol):
    def create(
        self,
        *,
        document_id: str,
        application_version: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRecord: ...

    def get_execution(self, execution_id: str) -> ExecutionRecord | None: ...

    def list_executions(self) -> list[ExecutionRecord]: ...

    def set_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        *,
        error_code: str | None = None,
        expected_status: ExecutionStatus | None = None,
    ) -> ExecutionRecord: ...
