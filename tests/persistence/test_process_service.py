from __future__ import annotations

import json

import pytest

from persistence import PersistenceSettings, build_persistence
from persistence.contracts import (
    AuthenticatedActor,
    AuthorizationDenied,
    LocalProcessPersistence,
    ProcessPersistenceError,
    ProcessScope,
)
from persistence.local import LocalProcessPersistenceService


def _actor(org: str = "org-1", actor_id: str = "analyst-1"):
    return AuthenticatedActor(
        actor_id=actor_id,
        display_name="Analista Uno",
        organization_id=org,
        roles=frozenset({"analyst"}),
        provider_subject=f"subject-{actor_id}",
    )


def _settings(tmp_path):
    catalog = tmp_path / "catalog.json"
    dictionary = tmp_path / "dictionary.json"
    catalog.write_text(json.dumps({
        "AC.01": {
            "codigo_estandar": "AC.01", "nombre_estandar": "Caja y Bancos",
            "categoria": "activo_corriente", "tipo_estado": "situacion",
            "naturaleza": "activo",
        },
    }), encoding="utf-8")
    dictionary.write_text("[]", encoding="utf-8")
    return PersistenceSettings(
        mode="local", local_root=tmp_path / "runtime",
        catalog_seed=catalog, dictionary_seed=dictionary,
    )


def test_process_round_trip_survives_restart_with_scope_audit_and_report(tmp_path):
    settings = _settings(tmp_path)
    bundle = build_persistence(settings)
    service = bundle.processes
    assert isinstance(service, LocalProcessPersistence)
    assert service is not None
    actor = _actor()
    started = service.start(
        b"%PDF-1.7\nclassified balance",
        original_name="../../balance.pdf",
        media_type="application/pdf",
        scope=ProcessScope("selected", (5, 6, 7), ("2024", "2023")),
        actor=actor,
        application_version="c70e60e",
    )
    assert started.execution.status == "running"
    assert started.execution.metadata == {
        "organization_id": "org-1", "actor_id": "analyst-1",
        "page_mode": "selected", "selected_pages": [5, 6, 7],
        "periods": ["2024", "2023"],
    }
    correction = service.record_correction(
        started.execution.execution_id,
        actor=actor,
        correction_id="row:42",
        classification_code="ANC.01.01",
    )
    assert correction.actor_id == "analyst-1"
    assert correction.details["organization_id"] == "org-1"
    reviewed = service.mark_review(started.execution.execution_id, actor=actor)
    assert reviewed.execution.status == "review"
    completed = service.complete_with_report(
        started.execution.execution_id,
        b"xlsx-result",
        actor=actor,
        file_name="resultado.xlsx",
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    assert completed.execution.status == "completed"
    assert len(completed.reports) == 1

    reopened = build_persistence(settings)
    assert reopened.processes is not None
    recovered = reopened.processes.get(
        completed.execution.execution_id, actor=actor,
    )
    assert recovered is not None
    assert recovered.execution.status == "completed"
    assert recovered.document.sha256 == completed.document.sha256
    assert recovered.reports == completed.reports
    assert reopened.processes.read_definitive_report(
        recovered.execution.execution_id,
        recovered.reports[0].report_id,
        actor=actor,
    ) == b"xlsx-result"
    actions = {
        event.action for event in reopened.processes.list_audit(
            recovered.execution.execution_id, actor=actor,
        )
    }
    assert actions == {
        "PROCESS_CREATED", "CORRECTION_RECORDED",
        "PROCESS_REVIEW_STARTED", "DEFINITIVE_REPORT_STAGED",
    }


def test_process_access_is_isolated_by_organization(tmp_path):
    bundle = build_persistence(_settings(tmp_path))
    assert bundle.processes is not None
    owner = _actor()
    foreign = _actor("org-2", "analyst-2")
    process = bundle.processes.start(
        b"pdf", original_name="balance.pdf", media_type="application/pdf",
        scope=ProcessScope("all", (), ("2024",)), actor=owner,
        application_version="test-1",
    )
    for operation in (
        lambda: bundle.processes.get(process.execution.execution_id, actor=foreign),
        lambda: bundle.processes.list_audit(
            process.execution.execution_id, actor=foreign,
        ),
        lambda: bundle.processes.record_correction(
            process.execution.execution_id, actor=foreign,
            correction_id="row:1", classification_code="AC.01",
        ),
    ):
        with pytest.raises(AuthorizationDenied):
            operation()


class _FailingAudit:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.fail_action = None

    def append(self, event):
        if event.action == self.fail_action:
            raise OSError("injected audit failure")
        return self.wrapped.append(event)

    def list_for_subject(self, *args, **kwargs):
        return self.wrapped.list_for_subject(*args, **kwargs)


class _FailingExecutionCreate:
    def create(self, **_kwargs):
        raise OSError("injected execution failure")


def test_report_partial_failure_is_compensated_and_not_downloadable(tmp_path):
    bundle = build_persistence(_settings(tmp_path))
    assert all((bundle.documents, bundle.executions, bundle.audit, bundle.reports))
    audit = _FailingAudit(bundle.audit)
    service = LocalProcessPersistenceService(
        documents=bundle.documents,
        executions=bundle.executions,
        audit=audit,
        reports=bundle.reports,
    )
    actor = _actor()
    process = service.start(
        b"pdf", original_name="balance.pdf", media_type="application/pdf",
        scope=ProcessScope("all", (), ("2024",)), actor=actor,
        application_version="test-1",
    )
    audit.fail_action = "DEFINITIVE_REPORT_STAGED"
    with pytest.raises(ProcessPersistenceError) as raised:
        service.complete_with_report(
            process.execution.execution_id, b"report", actor=actor,
            file_name="report.xlsx", media_type="application/octet-stream",
        )
    assert raised.value.stage == "report_finalize"
    assert raised.value.report_id is not None
    assert raised.value.compensated is True
    persisted = service.get(process.execution.execution_id, actor=actor)
    assert persisted is not None and persisted.execution.status == "failed"
    assert persisted.execution.error_code == "REPORT_FINALIZATION_FAILED"
    assert len(persisted.reports) == 1
    with pytest.raises(AuthorizationDenied, match="no es descargable"):
        service.read_definitive_report(
            process.execution.execution_id, raised.value.report_id, actor=actor,
        )


def test_execution_create_failure_identifies_orphan_for_reconciliation(tmp_path):
    bundle = build_persistence(_settings(tmp_path))
    assert all((bundle.documents, bundle.audit, bundle.reports))
    service = LocalProcessPersistenceService(
        documents=bundle.documents,
        executions=_FailingExecutionCreate(),
        audit=bundle.audit,
        reports=bundle.reports,
    )
    with pytest.raises(ProcessPersistenceError) as raised:
        service.start(
            b"pdf", original_name="balance.pdf", media_type="application/pdf",
            scope=ProcessScope("all", (), ("2024",)), actor=_actor(),
            application_version="test-1",
        )
    assert raised.value.stage == "execution_create"
    assert raised.value.document_id is not None
    assert raised.value.execution_id is None
    events = bundle.audit.list_for_subject(
        "document", raised.value.document_id,
    )
    assert [event.action for event in events] == [
        "DOCUMENT_ORPHAN_REQUIRES_RECONCILIATION",
    ]


@pytest.mark.parametrize(
    "scope",
    [
        ProcessScope("selected", (), ("2024",)),
        ProcessScope("all", (1,), ("2024",)),
        ProcessScope("selected", (2, 1), ("2024",)),
        ProcessScope("selected", (1,), ()),
        ProcessScope("selected", (1,), ("2024", "2023", "2022")),
    ],
)
def test_invalid_scope_fails_before_writing_document(tmp_path, scope):
    bundle = build_persistence(_settings(tmp_path))
    assert bundle.processes is not None
    with pytest.raises(ValueError):
        bundle.processes.start(
            b"pdf", original_name="balance.pdf", media_type="application/pdf",
            scope=scope, actor=_actor(), application_version="test-1",
        )
    assert list((tmp_path / "runtime" / "documents").glob("*")) == []
