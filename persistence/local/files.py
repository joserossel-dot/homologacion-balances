"""Repositorios de archivos locales con verificación de integridad."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from uuid import uuid4

from persistence.contracts.documents import DocumentRecord
from persistence.contracts.reports import ReportRecord


_SAFE_ID = re.compile(r"^[a-f0-9]{32}$")


def _validated_id(value: str, field: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} inválido")
    return value


def _base_name(value: str) -> str:
    return Path(value.replace("\\", "/")).name


def _contained_path(root: Path, storage_key: str) -> Path:
    candidate = (root / storage_key).resolve()
    resolved_root = root.resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("storage_key fuera del repositorio") from exc
    return candidate


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_metadata(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    _write_bytes_atomic(path, payload)


class FileDocumentRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(
        self,
        content: bytes,
        *,
        original_name: str,
        media_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentRecord:
        document_id = uuid4().hex
        directory = self.root / document_id
        content_path = directory / "document.bin"
        digest = hashlib.sha256(content).hexdigest()
        record = DocumentRecord(
            document_id=document_id,
            original_name=_base_name(original_name),
            media_type=media_type,
            size_bytes=len(content),
            sha256=digest,
            storage_key=str(content_path.relative_to(self.root)),
            created_at=_utc_now(),
            metadata=dict(metadata or {}),
        )
        _write_bytes_atomic(content_path, content)
        serialized = asdict(record)
        serialized["created_at"] = record.created_at.isoformat()
        _write_metadata(directory / "metadata.json", serialized)
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        _validated_id(document_id, "document_id")
        metadata_path = self.root / document_id / "metadata.json"
        if not metadata_path.exists():
            return None
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        if _validated_id(raw["document_id"], "document_id") != document_id:
            raise ValueError("Metadatos documentales inconsistentes")
        _contained_path(self.root, raw["storage_key"])
        return DocumentRecord(
            document_id=raw["document_id"],
            original_name=raw["original_name"],
            media_type=raw["media_type"],
            size_bytes=int(raw["size_bytes"]),
            sha256=raw["sha256"],
            storage_key=raw["storage_key"],
            created_at=datetime.fromisoformat(raw["created_at"]),
            metadata=dict(raw.get("metadata", {})),
        )

    def read(self, document_id: str) -> bytes:
        record = self.get(document_id)
        if record is None:
            raise KeyError(document_id)
        content = _contained_path(self.root, record.storage_key).read_bytes()
        if hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError(f"Integridad documental inválida: {document_id}")
        return content


class FileReportRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(
        self,
        content: bytes,
        *,
        execution_id: str,
        file_name: str,
        media_type: str,
        definitive: bool,
    ) -> ReportRecord:
        _validated_id(execution_id, "execution_id")
        report_id = uuid4().hex
        directory = self.root / execution_id / report_id
        content_path = directory / "report.bin"
        record = ReportRecord(
            report_id=report_id,
            execution_id=execution_id,
            file_name=_base_name(file_name),
            media_type=media_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_key=str(content_path.relative_to(self.root)),
            definitive=bool(definitive),
            created_at=_utc_now(),
        )
        _write_bytes_atomic(content_path, content)
        serialized = asdict(record)
        serialized["created_at"] = record.created_at.isoformat()
        _write_metadata(directory / "metadata.json", serialized)
        return record

    def read(self, report_id: str) -> bytes:
        record = self._find(report_id)
        if record is None:
            raise KeyError(report_id)
        content = _contained_path(self.root, record.storage_key).read_bytes()
        if hashlib.sha256(content).hexdigest() != record.sha256:
            raise ValueError(f"Integridad de reporte inválida: {report_id}")
        return content

    def list_for_execution(self, execution_id: str) -> list[ReportRecord]:
        _validated_id(execution_id, "execution_id")
        directory = self.root / execution_id
        if not directory.exists():
            return []
        records = [
            self._load_metadata(path, expected_execution_id=execution_id)
            for path in directory.glob("*/metadata.json")
        ]
        return sorted(records, key=lambda item: item.created_at)

    def _find(self, report_id: str) -> ReportRecord | None:
        _validated_id(report_id, "report_id")
        for path in self.root.glob(f"*/{report_id}/metadata.json"):
            return self._load_metadata(path, expected_report_id=report_id)
        return None

    def _load_metadata(
        self,
        path: Path,
        *,
        expected_execution_id: str | None = None,
        expected_report_id: str | None = None,
    ) -> ReportRecord:
        raw = json.loads(path.read_text(encoding="utf-8"))
        report_id = _validated_id(raw["report_id"], "report_id")
        execution_id = _validated_id(raw["execution_id"], "execution_id")
        if expected_execution_id and execution_id != expected_execution_id:
            raise ValueError("Metadatos de reporte inconsistentes")
        if expected_report_id and report_id != expected_report_id:
            raise ValueError("Metadatos de reporte inconsistentes")
        _contained_path(self.root, raw["storage_key"])
        return ReportRecord(
            report_id=report_id,
            execution_id=execution_id,
            file_name=raw["file_name"],
            media_type=raw["media_type"],
            size_bytes=int(raw["size_bytes"]),
            sha256=raw["sha256"],
            storage_key=raw["storage_key"],
            definitive=bool(raw["definitive"]),
            created_at=datetime.fromisoformat(raw["created_at"]),
        )
