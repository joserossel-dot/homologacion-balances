"""Contrato append-only para eventos auditables locales."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: int | None
    occurred_at: datetime
    actor_id: str | None
    action: str
    subject_type: str
    subject_id: str
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LocalAuditRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_for_subject(
        self,
        subject_type: str,
        subject_id: str,
        *,
        limit: int = 100,
    ) -> list[AuditEvent]: ...
