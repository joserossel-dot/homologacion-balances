"""Contrato del repositorio documental local."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    document_id: str
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LocalDocumentRepository(Protocol):
    def save(
        self,
        content: bytes,
        *,
        original_name: str,
        media_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentRecord: ...

    def get(self, document_id: str) -> DocumentRecord | None: ...

    def read(self, document_id: str) -> bytes: ...
