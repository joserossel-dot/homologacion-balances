"""Servicio local compensable para la saga documento-ejecución-reporte."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from persistence.contracts import (
    AuthenticatedActor,
    AuditEvent,
    AuthorizationDenied,
    LocalAuditRepository,
    LocalDocumentRepository,
    LocalExecutionRepository,
    LocalReportRepository,
    PersistedProcess,
    ProcessPersistenceError,
    ProcessScope,
    audit_event_for_actor,
    require_role,
)


_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,299}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reference(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not _SAFE_REFERENCE.fullmatch(normalized):
        raise ValueError(f"{field} inválido")
    return normalized


def _validated_scope(scope: ProcessScope) -> ProcessScope:
    if scope.page_mode not in {"all", "selected"}:
        raise ValueError("page_mode inválido")
    pages = tuple(int(page) for page in scope.selected_pages)
    if any(page <= 0 for page in pages) or len(set(pages)) != len(pages):
        raise ValueError("selected_pages debe contener páginas positivas únicas")
    if tuple(sorted(pages)) != pages:
        raise ValueError("selected_pages debe estar ordenado")
    if scope.page_mode == "all" and pages:
        raise ValueError("El alcance all no acepta páginas seleccionadas")
    if scope.page_mode == "selected" and not pages:
        raise ValueError("El alcance selected exige páginas")
    periods = tuple(_reference(period, "period") for period in scope.periods)
    if not 1 <= len(periods) <= 2 or len(set(periods)) != len(periods):
        raise ValueError("periods debe contener uno o dos períodos únicos")
    return ProcessScope(scope.page_mode, pages, periods)


class LocalProcessPersistenceService:
    """Coordina repositorios locales sin afirmar atomicidad entre archivos y DB.

    Si una escritura posterior falla, la ejecución se marca `failed` cuando es
    posible y la excepción identifica cualquier archivo que requiera
    conciliación. Los reportes sólo pueden leerse mediante este servicio si la
    ejecución llegó a `completed`.
    """

    def __init__(
        self, *, documents: LocalDocumentRepository,
        executions: LocalExecutionRepository, audit: LocalAuditRepository,
        reports: LocalReportRepository,
    ) -> None:
        self.documents = documents
        self.executions = executions
        self.audit = audit
        self.reports = reports

    def start(
        self, content: bytes, *, original_name: str, media_type: str,
        scope: ProcessScope, actor: AuthenticatedActor,
        application_version: str,
    ) -> PersistedProcess:
        require_role(actor, "analyst")
        safe_scope = _validated_scope(scope)
        application_version = _reference(application_version, "application_version")
        metadata = {
            "organization_id": actor.organization_id,
            "actor_id": actor.actor_id,
            "page_mode": safe_scope.page_mode,
            "selected_pages": list(safe_scope.selected_pages),
            "periods": list(safe_scope.periods),
        }
        document = self.documents.save(
            content, original_name=original_name, media_type=media_type,
            metadata=metadata,
        )
        try:
            execution = self.executions.create(
                document_id=document.document_id,
                application_version=application_version,
                metadata=metadata,
            )
        except Exception as exc:
            self._best_effort_document_orphan_audit(document.document_id, actor)
            raise ProcessPersistenceError(
                "Documento persistido, pero no fue posible crear la ejecución",
                stage="execution_create", document_id=document.document_id,
            ) from exc
        try:
            self.audit.append(audit_event_for_actor(
                actor, occurred_at=_now(), action="PROCESS_CREATED",
                subject_type="execution", subject_id=execution.execution_id,
                details={"document_id": document.document_id},
            ))
            running = self.executions.set_status(
                execution.execution_id, "running", expected_status="pending",
            )
        except Exception as exc:
            compensated = self._best_effort_fail_execution(
                execution.execution_id, "PROCESS_START_PERSISTENCE_FAILED",
            )
            raise ProcessPersistenceError(
                "La saga de inicio no pudo completarse",
                stage="start_audit_or_status",
                document_id=document.document_id,
                execution_id=execution.execution_id,
                compensated=compensated,
            ) from exc
        return PersistedProcess(document=document, execution=running)

    def get(
        self, execution_id: str, *, actor: AuthenticatedActor,
    ) -> PersistedProcess | None:
        require_role(actor, "analyst")
        execution = self.executions.get_execution(execution_id)
        if execution is None:
            return None
        self._authorize_execution(execution, actor)
        document = self.documents.get(execution.document_id)
        if document is None:
            raise ProcessPersistenceError(
                "La ejecución referencia un documento ausente",
                stage="read_document", execution_id=execution_id,
                document_id=execution.document_id,
            )
        if document.metadata.get("organization_id") != actor.organization_id:
            raise AuthorizationDenied("Documento fuera de la organización del actor")
        reports = tuple(self.reports.list_for_execution(execution_id))
        return PersistedProcess(document=document, execution=execution, reports=reports)

    def mark_review(
        self, execution_id: str, *, actor: AuthenticatedActor,
    ) -> PersistedProcess:
        process = self._required_process(execution_id, actor)
        reviewed = self.executions.set_status(
            execution_id, "review", expected_status="running",
        )
        try:
            self.audit.append(audit_event_for_actor(
                actor, occurred_at=_now(), action="PROCESS_REVIEW_STARTED",
                subject_type="execution", subject_id=execution_id,
            ))
        except Exception as exc:
            compensated = False
            try:
                self.executions.set_status(
                    execution_id, "running", expected_status="review",
                )
                compensated = True
            except Exception:
                pass
            raise ProcessPersistenceError(
                "No fue posible auditar el inicio de revisión",
                stage="review_audit", document_id=process.document.document_id,
                execution_id=execution_id, compensated=compensated,
            ) from exc
        return PersistedProcess(
            document=process.document, execution=reviewed, reports=process.reports,
        )

    def record_correction(
        self, execution_id: str, *, actor: AuthenticatedActor,
        correction_id: str, classification_code: str,
    ) -> AuditEvent:
        process = self._required_process(execution_id, actor)
        if process.execution.status not in {"running", "review"}:
            raise ValueError("La ejecución no admite correcciones")
        return self.audit.append(audit_event_for_actor(
            actor, occurred_at=_now(), action="CORRECTION_RECORDED",
            subject_type="execution", subject_id=execution_id,
            details={
                "correction_id": _reference(correction_id, "correction_id"),
                "classification_code": _reference(
                    classification_code, "classification_code",
                ),
            },
        ))

    def complete_with_report(
        self, execution_id: str, content: bytes, *, actor: AuthenticatedActor,
        file_name: str, media_type: str,
    ) -> PersistedProcess:
        process = self._required_process(execution_id, actor)
        if process.execution.status not in {"running", "review"}:
            raise ValueError("La ejecución no admite un reporte definitivo")
        report = self.reports.save(
            content, execution_id=execution_id, file_name=file_name,
            media_type=media_type, definitive=True,
        )
        try:
            self.audit.append(audit_event_for_actor(
                actor, occurred_at=_now(), action="DEFINITIVE_REPORT_STAGED",
                subject_type="execution", subject_id=execution_id,
                details={"report_id": report.report_id, "sha256": report.sha256},
            ))
            completed = self.executions.set_status(
                execution_id, "completed",
                expected_status=process.execution.status,
            )
        except Exception as exc:
            compensated = self._best_effort_fail_execution(
                execution_id, "REPORT_FINALIZATION_FAILED",
            )
            raise ProcessPersistenceError(
                "El reporte fue escrito, pero la ejecución no quedó completada",
                stage="report_finalize",
                document_id=process.document.document_id,
                execution_id=execution_id,
                report_id=report.report_id,
                compensated=compensated,
            ) from exc
        return PersistedProcess(
            document=process.document, execution=completed,
            reports=tuple((*process.reports, report)),
        )

    def fail(
        self, execution_id: str, *, actor: AuthenticatedActor, error_code: str,
    ) -> PersistedProcess:
        process = self._required_process(execution_id, actor)
        error_code = _reference(error_code, "error_code")
        if process.execution.status not in {"pending", "running", "review"}:
            raise ValueError("La ejecución ya se encuentra en estado terminal")
        self.audit.append(audit_event_for_actor(
            actor, occurred_at=_now(), action="PROCESS_FAILURE_REQUESTED",
            subject_type="execution", subject_id=execution_id,
            details={"error_code": error_code},
        ))
        failed = self.executions.set_status(
            execution_id, "failed", error_code=error_code,
            expected_status=process.execution.status,
        )
        return PersistedProcess(
            document=process.document, execution=failed, reports=process.reports,
        )

    def list_audit(
        self, execution_id: str, *, actor: AuthenticatedActor, limit: int = 100,
    ) -> list[AuditEvent]:
        self._required_process(execution_id, actor)
        return self.audit.list_for_subject("execution", execution_id, limit=limit)

    def read_definitive_report(
        self, execution_id: str, report_id: str, *, actor: AuthenticatedActor,
    ) -> bytes:
        process = self._required_process(execution_id, actor)
        if process.execution.status != "completed":
            raise AuthorizationDenied(
                "El reporte no es descargable hasta completar la ejecución"
            )
        matching = next(
            (report for report in process.reports
             if report.report_id == report_id and report.definitive), None,
        )
        if matching is None:
            raise KeyError(report_id)
        return self.reports.read(report_id)

    def _required_process(
        self, execution_id: str, actor: AuthenticatedActor,
    ) -> PersistedProcess:
        process = self.get(execution_id, actor=actor)
        if process is None:
            raise KeyError(execution_id)
        return process

    @staticmethod
    def _authorize_execution(execution, actor: AuthenticatedActor) -> None:
        if execution.metadata.get("organization_id") != actor.organization_id:
            raise AuthorizationDenied("Ejecución fuera de la organización del actor")

    def _best_effort_fail_execution(self, execution_id: str, error_code: str) -> bool:
        try:
            current = self.executions.get_execution(execution_id)
            if current is None or current.status not in {"pending", "running", "review"}:
                return False
            self.executions.set_status(
                execution_id, "failed", error_code=error_code,
                expected_status=current.status,
            )
            return True
        except Exception:
            return False

    def _best_effort_document_orphan_audit(
        self, document_id: str, actor: AuthenticatedActor,
    ) -> None:
        try:
            self.audit.append(audit_event_for_actor(
                actor, occurred_at=_now(),
                action="DOCUMENT_ORPHAN_REQUIRES_RECONCILIATION",
                subject_type="document", subject_id=document_id,
            ))
        except Exception:
            pass
