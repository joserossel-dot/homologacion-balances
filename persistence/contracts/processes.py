"""Unidad local compensable para persistir un procesamiento documental."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from .audit import AuditEvent
from .documents import DocumentRecord
from .executions import ExecutionRecord
from .identity import AuthenticatedActor
from .reports import ReportRecord


PageScopeMode = Literal["all", "selected"]


@dataclass(frozen=True, slots=True)
class ProcessScope:
    page_mode: PageScopeMode
    selected_pages: tuple[int, ...]
    periods: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PersistedProcess:
    document: DocumentRecord
    execution: ExecutionRecord
    reports: tuple[ReportRecord, ...] = ()


class ProcessPersistenceError(RuntimeError):
    """Fallo de saga que identifica artefactos y compensación aplicada."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        document_id: str | None = None,
        execution_id: str | None = None,
        report_id: str | None = None,
        compensated: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.document_id = document_id
        self.execution_id = execution_id
        self.report_id = report_id
        self.compensated = compensated


@runtime_checkable
class LocalProcessPersistence(Protocol):
    def start(
        self, content: bytes, *, original_name: str, media_type: str,
        scope: ProcessScope, actor: AuthenticatedActor,
        application_version: str,
    ) -> PersistedProcess: ...

    def get(
        self, execution_id: str, *, actor: AuthenticatedActor,
    ) -> PersistedProcess | None: ...

    def mark_review(
        self, execution_id: str, *, actor: AuthenticatedActor,
    ) -> PersistedProcess: ...

    def record_correction(
        self, execution_id: str, *, actor: AuthenticatedActor,
        correction_id: str, classification_code: str,
    ) -> AuditEvent: ...

    def complete_with_report(
        self, execution_id: str, content: bytes, *, actor: AuthenticatedActor,
        file_name: str, media_type: str,
    ) -> PersistedProcess: ...

    def fail(
        self, execution_id: str, *, actor: AuthenticatedActor, error_code: str,
    ) -> PersistedProcess: ...

    def list_audit(
        self, execution_id: str, *, actor: AuthenticatedActor, limit: int = 100,
    ) -> list[AuditEvent]: ...

    def read_definitive_report(
        self, execution_id: str, report_id: str, *, actor: AuthenticatedActor,
    ) -> bytes: ...
