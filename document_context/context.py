from __future__ import annotations

import copy
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    DocumentIdentity, DocumentMetadata, StructureData, ParserData,
    KnowledgeData, ValidationData, PredictionData, ExecutionData,
    ProcessingState, ContextSnapshot, LifecycleEvent,
)
from .lifecycle import LifecycleManager, LifecycleError
from .snapshot import SnapshotManager
from .validators import ContextValidator, ValidationIssue


class DocumentContext:
    """Único objeto de contexto que acompaña al documento desde que entra
    hasta que termina. Cada módulo lee lo que necesita y agrega su resultado.
    Nunca se elimina ni modifica información de módulos anteriores."""

    def __init__(self, source_file: str = "", document_id: str | None = None):
        self._identity = DocumentIdentity(
            document_id=document_id or _generate_id(),
            source_file=source_file,
            sha256=_compute_sha256(source_file) if source_file else "",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._metadata: DocumentMetadata | None = None
        self._structure: StructureData | None = None
        self._parser: ParserData | None = None
        self._knowledge: KnowledgeData | None = None
        self._validation: ValidationData | None = None
        self._prediction: PredictionData | None = None
        self._execution: ExecutionData | None = None
        self._custom: dict[str, Any] = {}

        self._lifecycle = LifecycleManager()
        self._snapshots = SnapshotManager()
        self._write_once: set[str] = set()

    # ─── Identity (read-only) ────────────────────────────────────────────

    @property
    def identity(self) -> DocumentIdentity:
        return self._identity

    @property
    def document_id(self) -> str:
        return self._identity.document_id

    @property
    def source_file(self) -> str:
        return self._identity.source_file

    @property
    def sha256(self) -> str:
        return self._identity.sha256

    @property
    def version(self) -> str:
        return self._identity.version

    # ─── State ───────────────────────────────────────────────────────────

    @property
    def state(self) -> ProcessingState:
        return self._lifecycle.state

    @property
    def is_terminal(self) -> bool:
        return self._lifecycle.state.is_terminal

    @property
    def can_process(self) -> bool:
        return self._lifecycle.can_transition

    @property
    def events(self) -> list[LifecycleEvent]:
        return self._lifecycle.events

    # ─── Sections (read/write-once) ──────────────────────────────────────

    @property
    def metadata(self) -> DocumentMetadata | None:
        return self._metadata

    def set_metadata(self, data: DocumentMetadata, module: str = "system") -> None:
        _check_write_once("metadata", self._write_once)
        self._metadata = data
        self._write_once.add("metadata")
        self._transition(ProcessingState.IDENTIFIED, module, "metadata set")

    @property
    def structure(self) -> StructureData | None:
        return self._structure

    def set_structure(self, data: StructureData, module: str = "system") -> None:
        _check_write_once("structure", self._write_once)
        self._structure = data
        self._write_once.add("structure")
        self._transition(ProcessingState.STRUCTURED, module, "structure set")

    @property
    def parser(self) -> ParserData | None:
        return self._parser

    def set_parser(self, data: ParserData, module: str = "system") -> None:
        _check_write_once("parser", self._write_once)
        self._parser = data
        self._write_once.add("parser")
        self._transition(ProcessingState.PARSED, module, "parser set")

    @property
    def knowledge(self) -> KnowledgeData | None:
        return self._knowledge

    def set_knowledge(self, data: KnowledgeData, module: str = "system") -> None:
        _check_write_once("knowledge", self._write_once)
        self._knowledge = data
        self._write_once.add("knowledge")
        self._transition(ProcessingState.CLASSIFIED, module, "knowledge set")

    @property
    def validation(self) -> ValidationData | None:
        return self._validation

    def set_validation(self, data: ValidationData, module: str = "system") -> None:
        _check_write_once("validation", self._write_once)
        self._validation = data
        self._write_once.add("validation")
        self._transition(ProcessingState.VALIDATED, module, "validation set")

    @property
    def prediction(self) -> PredictionData | None:
        return self._prediction

    def set_prediction(self, data: PredictionData, module: str = "system") -> None:
        _check_write_once("prediction", self._write_once)
        self._prediction = data
        self._write_once.add("prediction")

    @property
    def execution(self) -> ExecutionData | None:
        return self._execution

    def set_execution(self, data: ExecutionData, module: str = "system") -> None:
        _check_write_once("execution", self._write_once)
        self._execution = data
        self._write_once.add("execution")

    # ─── Review transition ───────────────────────────────────────────────

    def mark_reviewed(self, module: str = "review") -> None:
        self._transition(ProcessingState.REVIEWED, module, "review completed")

    def complete(self, module: str = "system") -> None:
        self._transition(ProcessingState.COMPLETED, module, "processing completed")
        self._identity.updated_at = datetime.now(timezone.utc)

    def fail(self, error: str, module: str = "system") -> None:
        try:
            self._transition(ProcessingState.FAILED, module, error)
        except LifecycleError:
            pass
        self._identity.updated_at = datetime.now(timezone.utc)

    # ─── Custom data ─────────────────────────────────────────────────────

    def set_custom(self, key: str, value: Any) -> None:
        self._custom[key] = value

    def get_custom(self, key: str, default: Any = None) -> Any:
        return self._custom.get(key, default)

    @property
    def custom_data(self) -> dict[str, Any]:
        return dict(self._custom)

    # ─── Snapshots ───────────────────────────────────────────────────────

    @property
    def snapshots(self) -> list[ContextSnapshot]:
        return self._snapshots.snapshots

    def snapshot(self, label: str) -> ContextSnapshot:
        data = self._capture_state()
        snap = self._snapshots.create(label, self._lifecycle.state, data)
        return snap

    def diff_snapshots(self, id_a: str, id_b: str) -> dict[str, Any]:
        return self._snapshots.diff(id_a, id_b)

    # ─── Internal ────────────────────────────────────────────────────────

    def _transition(self, to_state: ProcessingState, module: str, desc: str) -> None:
        snapshot = self.snapshot(f"before_{to_state.value.lower()}")
        event = self._lifecycle.transition(
            to_state=to_state,
            module=module,
            description=desc,
            snapshot_id=snapshot.snapshot_id,
        )
        self._identity.updated_at = datetime.now(timezone.utc)

    def _capture_state(self) -> dict[str, Any]:
        return {
            "identity": self._identity.to_dict(),
            "metadata": self._metadata.to_dict() if self._metadata else None,
            "structure": self._structure.to_dict() if self._structure else None,
            "parser": self._parser.to_dict() if self._parser else None,
            "knowledge": self._knowledge.to_dict() if self._knowledge else None,
            "validation": self._validation.to_dict() if self._validation else None,
            "prediction": self._prediction.to_dict() if self._prediction else None,
            "execution": self._execution.to_dict() if self._execution else None,
            "state": self._lifecycle.state.value,
            "events_count": len(self._lifecycle.events),
            "snapshots_count": len(self._snapshots.snapshots),
        }

    # ─── Validation ──────────────────────────────────────────────────────

    def validate(self) -> list[ValidationIssue]:
        return ContextValidator.validate(self)


def _check_write_once(field: str, written: set[str]) -> None:
    if field in written:
        raise WriteOnceError(f"El campo '{field}' ya fue asignado y es write-once")


def _generate_id() -> str:
    return f"ctx_{uuid.uuid4().hex[:12]}"


def _compute_sha256(file_path: str) -> str:
    try:
        import hashlib
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


class WriteOnceError(Exception):
    pass
