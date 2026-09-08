"""Contrato de reportes locales emitidos por una ejecución."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ReportRecord:
    report_id: str
    execution_id: str
    file_name: str
    media_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    definitive: bool
    created_at: datetime


@runtime_checkable
class LocalReportRepository(Protocol):
    def save(
        self,
        content: bytes,
        *,
        execution_id: str,
        file_name: str,
        media_type: str,
        definitive: bool,
    ) -> ReportRecord: ...

    def read(self, report_id: str) -> bytes: ...

    def list_for_execution(self, execution_id: str) -> list[ReportRecord]: ...
