"""Detección y cuarentena recuperable de artefactos locales inconsistentes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable
from uuid import uuid4

from persistence.contracts import (
    AuthenticatedActor,
    LocalAuditRepository,
    LocalExecutionRepository,
    audit_event_for_actor,
    require_role,
)
from persistence.local.files import FileDocumentRepository, FileReportRepository
from persistence.local.locking import exclusive_file_lock


MIN_TEMPORARY_AGE_HOURS = 1
MAX_TEMPORARY_AGE_HOURS = 24 * 365
MIN_QUARANTINE_RETENTION_DAYS = 1
MAX_QUARANTINE_RETENTION_DAYS = 3650


def _validate_policy(
    *, temporary_min_age_hours: int, quarantine_retention_days: int,
) -> None:
    if not MIN_TEMPORARY_AGE_HOURS <= temporary_min_age_hours <= MAX_TEMPORARY_AGE_HOURS:
        raise ValueError(
            "temporary_min_age_hours debe estar entre 1 y 8760"
        )
    if not (
        MIN_QUARANTINE_RETENTION_DAYS
        <= quarantine_retention_days
        <= MAX_QUARANTINE_RETENTION_DAYS
    ):
        raise ValueError(
            "quarantine_retention_days debe estar entre 1 y 3650"
        )


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    kind: str
    path: Path | None
    organization_id: str | None
    subject_type: str
    subject_id: str
    repairable: bool


@dataclass(frozen=True, slots=True)
class ReconciliationScan:
    scanned_at: datetime
    findings: tuple[ReconciliationFinding, ...]
    retention_due: int

    def aggregate(self) -> dict[str, object]:
        counts = Counter(item.kind for item in self.findings)
        return {
            "mode": "read_only",
            "scanned_at": self.scanned_at.isoformat(),
            "finding_count": len(self.findings),
            "counts": dict(sorted(counts.items())),
            "repairable_known_organization": sum(
                item.repairable and bool(item.organization_id)
                for item in self.findings
            ),
            "unknown_organization": sum(
                not bool(item.organization_id) for item in self.findings
            ),
            "quarantine_retention_due": self.retention_due,
        }


class LocalRuntimeReconciler:
    """Escanea sin modificar y mueve sólo artefactos recuperables autorizados."""

    def __init__(
        self, root: str | Path, *, executions: LocalExecutionRepository,
        audit: LocalAuditRepository,
    ) -> None:
        self.root = Path(root).resolve()
        self.documents = FileDocumentRepository(self.root / "documents")
        self.reports = FileReportRepository(self.root / "reports")
        self.executions = executions
        self.audit = audit
        self.quarantine_root = self.root / "quarantine"

    def scan(
        self, *, temporary_min_age_hours: int = 24,
        quarantine_retention_days: int = 90,
        now: datetime | None = None,
    ) -> ReconciliationScan:
        _validate_policy(
            temporary_min_age_hours=temporary_min_age_hours,
            quarantine_retention_days=quarantine_retention_days,
        )
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        executions = {item.execution_id: item for item in self.executions.list_executions()}
        document_references = {item.document_id for item in executions.values()}
        document_orgs: dict[str, str | None] = {}
        findings: list[ReconciliationFinding] = []

        document_root = self.root / "documents"
        if document_root.exists():
            for directory in sorted(path for path in document_root.iterdir() if path.is_dir()):
                document_id = directory.name
                try:
                    record = self.documents.get(document_id)
                except Exception:
                    findings.append(ReconciliationFinding(
                        "invalid_document_metadata", directory, None,
                        "document", document_id, False,
                    ))
                    continue
                if record is None:
                    continue
                organization_id = str(record.metadata.get("organization_id") or "") or None
                document_orgs[document_id] = organization_id
                if document_id not in document_references:
                    findings.append(ReconciliationFinding(
                        "orphan_document", directory, organization_id,
                        "document", document_id, bool(organization_id),
                    ))
                try:
                    self.documents.read(document_id)
                except Exception:
                    findings.append(ReconciliationFinding(
                        "invalid_document_hash", directory, organization_id,
                        "document", document_id, bool(organization_id),
                    ))

        for execution in executions.values():
            try:
                document = self.documents.get(execution.document_id)
            except Exception:
                document = None
            if document is None:
                organization_id = str(
                    execution.metadata.get("organization_id") or ""
                ) or None
                findings.append(ReconciliationFinding(
                    "execution_without_document", None, organization_id,
                    "execution", execution.execution_id, False,
                ))

        report_root = self.root / "reports"
        if report_root.exists():
            for execution_directory in sorted(
                path for path in report_root.iterdir() if path.is_dir()
            ):
                execution_id = execution_directory.name
                execution = executions.get(execution_id)
                organization_id = (
                    str(execution.metadata.get("organization_id") or "") or None
                    if execution else None
                )
                try:
                    records = self.reports.list_for_execution(execution_id)
                except Exception:
                    findings.append(ReconciliationFinding(
                        "invalid_report_metadata", execution_directory,
                        organization_id, "execution", execution_id, False,
                    ))
                    continue
                for record in records:
                    report_path = execution_directory / record.report_id
                    if execution is None:
                        findings.append(ReconciliationFinding(
                            "report_without_execution", report_path, None,
                            "report", record.report_id, False,
                        ))
                    try:
                        self.reports.read(record.report_id)
                    except Exception:
                        findings.append(ReconciliationFinding(
                            "invalid_report_hash", report_path, organization_id,
                            "report", record.report_id, bool(organization_id),
                        ))

        cutoff = moment - timedelta(hours=temporary_min_age_hours)
        managed_roots = [self.root / name for name in ("documents", "reports", "knowledge")]
        for managed_root in managed_roots:
            if not managed_root.exists():
                continue
            for path in managed_root.rglob("*.tmp"):
                try:
                    modified = datetime.fromtimestamp(
                        path.stat().st_mtime, timezone.utc,
                    )
                except FileNotFoundError:  # puede desaparecer durante el escaneo
                    continue
                if modified > cutoff:
                    continue
                organization_id = self._organization_for_path(
                    path, executions, document_orgs,
                )
                findings.append(ReconciliationFinding(
                    "stale_temporary", path, organization_id,
                    "temporary", hashlib.sha256(
                        str(path.relative_to(self.root)).encode("utf-8")
                    ).hexdigest()[:24], bool(organization_id),
                ))

        retention_due = self._retention_due(
            moment=moment, retention_days=quarantine_retention_days,
        )
        return ReconciliationScan(moment, tuple(findings), retention_due)

    def quarantine(
        self, *, actor: AuthenticatedActor,
        temporary_min_age_hours: int = 24,
        quarantine_retention_days: int = 90,
        now: datetime | None = None,
    ) -> dict[str, object]:
        require_role(actor, "admin")
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        scan = self.scan(
            temporary_min_age_hours=temporary_min_age_hours,
            quarantine_retention_days=quarantine_retention_days,
            now=moment,
        )
        case_id = uuid4().hex
        case_root = self.quarantine_root / "cases" / case_id
        manifest_path = case_root / "manifest.json"
        candidates = self._deduplicated_candidates(scan.findings, actor.organization_id)
        audit_only = [
            item for item in scan.findings
            if item.kind == "execution_without_document"
            and item.organization_id == actor.organization_id
        ]
        if not candidates and not audit_only:
            return {
                "mode": "repair",
                "status": "no_action",
                "quarantined": 0,
                "audited_only": 0,
                "unresolved": len(scan.findings),
                "retention_days": quarantine_retention_days,
            }
        manifest: dict[str, object] = {
            "case_id": case_id,
            "status": "moving",
            "organization_id": actor.organization_id,
            "actor_id": actor.actor_id,
            "created_at": moment.isoformat(),
            "retention_days": quarantine_retention_days,
            "retain_until": (
                moment + timedelta(days=quarantine_retention_days)
            ).isoformat(),
            "entries": [],
        }
        moved: list[tuple[Path, Path, ReconciliationFinding]] = []
        case_root.mkdir(parents=True, exist_ok=False)
        self._write_json_atomic(manifest_path, manifest)
        with exclusive_file_lock(self.quarantine_root / ".reconciliation.lock"):
            try:
                self.audit.append(audit_event_for_actor(
                    actor,
                    occurred_at=datetime.now(timezone.utc),
                    action="RUNTIME_RECONCILIATION_STARTED",
                    subject_type="runtime",
                    subject_id=actor.organization_id,
                    details={
                        "case_id": case_id,
                        "candidate_count": len(candidates),
                        "audit_only_count": len(audit_only),
                        "finding_counts": scan.aggregate()["counts"],
                    },
                ))
                for finding in candidates:
                    assert finding.path is not None
                    source = self._safe_existing_path(finding.path)
                    relative = source.relative_to(self.root)
                    destination = case_root / "payload" / relative
                    digest = self._digest_path(source)
                    self._audit(actor, "ARTIFACT_QUARANTINE_REQUESTED", finding, case_id)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
                    moved.append((source, destination, finding))
                    self._audit(actor, "ARTIFACT_QUARANTINED", finding, case_id)
                    manifest["entries"].append({
                        "kind": finding.kind,
                        "subject_type": finding.subject_type,
                        "subject_id": finding.subject_id,
                        "original_path": str(relative),
                        "quarantine_path": str(destination.relative_to(self.root)),
                        "digest": digest,
                    })
                    self._write_json_atomic(manifest_path, manifest)
                for finding in audit_only:
                    self._audit(
                        actor, "EXECUTION_MISSING_DOCUMENT_DETECTED", finding, case_id,
                    )
                manifest["status"] = "quarantined"
                self._write_json_atomic(manifest_path, manifest)
                self.audit.append(audit_event_for_actor(
                    actor,
                    occurred_at=datetime.now(timezone.utc),
                    action="RUNTIME_RECONCILIATION_COMPLETED",
                    subject_type="runtime",
                    subject_id=actor.organization_id,
                    details={
                        "case_id": case_id,
                        "quarantined_count": len(moved),
                        "audited_only_count": len(audit_only),
                    },
                ))
            except Exception:
                for source, destination, _finding in reversed(moved):
                    if destination.exists() and not source.exists():
                        source.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(destination, source)
                manifest["status"] = "rolled_back"
                self._write_json_atomic(manifest_path, manifest)
                try:
                    self.audit.append(audit_event_for_actor(
                        actor,
                        occurred_at=datetime.now(timezone.utc),
                        action="RUNTIME_RECONCILIATION_ROLLED_BACK",
                        subject_type="runtime",
                        subject_id=actor.organization_id,
                        details={"case_id": case_id},
                    ))
                except Exception:
                    pass
                raise
        return {
            "mode": "repair",
            "case_id": case_id,
            "quarantined": len(moved),
            "audited_only": len(audit_only),
            "unresolved": len(scan.findings) - len(candidates) - len(audit_only),
            "retention_days": quarantine_retention_days,
        }

    def restore(
        self, case_id: str, *, actor: AuthenticatedActor,
    ) -> dict[str, object]:
        require_role(actor, "admin")
        if len(case_id) != 32 or any(char not in "0123456789abcdef" for char in case_id):
            raise ValueError("case_id inválido")
        case_root = self.quarantine_root / "cases" / case_id
        manifest_path = case_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("organization_id") != actor.organization_id:
            raise PermissionError("Caso fuera de la organización del actor")
        if manifest.get("status") != "quarantined":
            raise ValueError("El caso no está disponible para restauración")
        restored: list[tuple[Path, Path, dict[str, str]]] = []
        with exclusive_file_lock(self.quarantine_root / ".reconciliation.lock"):
            try:
                self.audit.append(audit_event_for_actor(
                    actor,
                    occurred_at=datetime.now(timezone.utc),
                    action="RUNTIME_RESTORE_STARTED",
                    subject_type="runtime",
                    subject_id=actor.organization_id,
                    details={"case_id": case_id},
                ))
                for entry in reversed(manifest.get("entries", [])):
                    source = self._contained(entry["quarantine_path"])
                    destination = self._contained(entry["original_path"])
                    if destination.exists():
                        raise FileExistsError(
                            "La ruta original ya existe; restauración detenida"
                        )
                    if self._digest_path(source) != entry["digest"]:
                        raise ValueError("Checksum de cuarentena inválido")
                    finding = ReconciliationFinding(
                        entry["kind"], destination, actor.organization_id,
                        entry["subject_type"], entry["subject_id"], True,
                    )
                    self._audit(actor, "ARTIFACT_RESTORE_REQUESTED", finding, case_id)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)
                    restored.append((source, destination, entry))
                    self._audit(actor, "ARTIFACT_RESTORED", finding, case_id)
                manifest["status"] = "restored"
                manifest["restored_at"] = datetime.now(timezone.utc).isoformat()
                manifest["restored_by"] = actor.actor_id
                self._write_json_atomic(manifest_path, manifest)
                self.audit.append(audit_event_for_actor(
                    actor,
                    occurred_at=datetime.now(timezone.utc),
                    action="RUNTIME_RESTORE_COMPLETED",
                    subject_type="runtime",
                    subject_id=actor.organization_id,
                    details={
                        "case_id": case_id,
                        "restored_count": len(restored),
                    },
                ))
            except Exception:
                for source, destination, _entry in reversed(restored):
                    if destination.exists() and not source.exists():
                        source.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(destination, source)
                try:
                    self.audit.append(audit_event_for_actor(
                        actor,
                        occurred_at=datetime.now(timezone.utc),
                        action="RUNTIME_RESTORE_ROLLED_BACK",
                        subject_type="runtime",
                        subject_id=actor.organization_id,
                        details={"case_id": case_id},
                    ))
                except Exception:
                    pass
                raise
        return {"mode": "restore", "case_id": case_id, "restored": len(restored)}

    def _organization_for_path(self, path, executions, document_orgs):
        relative = path.relative_to(self.root)
        if len(relative.parts) >= 2 and relative.parts[0] == "documents":
            return document_orgs.get(relative.parts[1])
        if len(relative.parts) >= 2 and relative.parts[0] == "reports":
            execution = executions.get(relative.parts[1])
            if execution:
                return str(execution.metadata.get("organization_id") or "") or None
        return None

    @staticmethod
    def _deduplicated_candidates(findings, organization_id):
        priorities = {
            "invalid_document_hash": 30, "invalid_report_hash": 30,
            "orphan_document": 20, "stale_temporary": 10,
        }
        selected: dict[Path, ReconciliationFinding] = {}
        for finding in findings:
            if (
                not finding.repairable or finding.organization_id != organization_id
                or finding.path is None or finding.kind not in priorities
            ):
                continue
            key = finding.path.resolve()
            current = selected.get(key)
            if current is None or priorities[finding.kind] > priorities[current.kind]:
                selected[key] = finding
        return sorted(selected.values(), key=lambda item: str(item.path))

    def _retention_due(self, *, moment: datetime, retention_days: int) -> int:
        count = 0
        cases = self.quarantine_root / "cases"
        if not cases.exists():
            return 0
        for manifest_path in cases.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                created = datetime.fromisoformat(manifest["created_at"])
                retain_until_raw = manifest.get("retain_until")
                retain_until = (
                    datetime.fromisoformat(retain_until_raw)
                    if retain_until_raw
                    else created + timedelta(days=retention_days)
                )
                if (
                    manifest.get("status") == "quarantined"
                    and retain_until <= moment
                ):
                    count += 1
            except Exception:
                count += 1
        return count

    def _contained(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        candidate.relative_to(self.root)
        return candidate

    def _safe_existing_path(self, path: Path) -> Path:
        """Rechaza escapes y enlaces antes de mover o calcular hashes."""
        absolute = path.absolute()
        absolute.relative_to(self.root)
        relative = absolute.relative_to(self.root)
        cursor = self.root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ValueError("No se concilian enlaces simbólicos")
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(self.root)
        return resolved

    @staticmethod
    def _digest_path(path: Path) -> str:
        digest = hashlib.sha256()
        if path.is_symlink():
            raise ValueError("No se calculan hashes de enlaces simbólicos")
        if path.is_file():
            digest.update(path.read_bytes())
            return digest.hexdigest()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            if child.is_symlink():
                raise ValueError("No se calculan hashes de enlaces simbólicos")
            digest.update(str(child.relative_to(path)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return digest.hexdigest()

    def _audit(self, actor, action, finding, case_id):
        self.audit.append(audit_event_for_actor(
            actor, occurred_at=datetime.now(timezone.utc), action=action,
            subject_type=finding.subject_type, subject_id=finding.subject_id,
            details={"case_id": case_id, "finding_kind": finding.kind},
        ))

    def _write_json_atomic(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
