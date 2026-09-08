from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import app_validacion as app
from persistence import PersistenceSettings, build_persistence
from persistence.contracts import AuthenticatedActor, ProcessPersistenceError


class Upload:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


@pytest.fixture
def actor() -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id="analyst-1",
        display_name="Analista Uno",
        organization_id="org-1",
        roles=frozenset({"analyst"}),
        provider_subject="oidc:analyst-1",
    )


@pytest.fixture
def process_service(tmp_path: Path):
    bundle = build_persistence(PersistenceSettings(
        mode="local",
        local_root=tmp_path / "runtime",
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    assert bundle.processes is not None
    return bundle.processes


def _install_streamlit_state(monkeypatch, *, state=None, query=None) -> None:
    monkeypatch.setattr(app.st, "session_state", state if state is not None else {})
    monkeypatch.setattr(app.st, "query_params", query if query is not None else {})


def test_scope_is_started_only_from_confirmed_state_and_recovers_from_url(
    monkeypatch, actor, process_service,
):
    content = b"synthetic-pdf-content"
    upload = Upload("balance.pdf", content)
    query = {}
    initial = {
        "document_pages": {upload.name: [2]},
        "company_periodos_seleccionados": ("2024", "2023"),
    }
    _install_streamlit_state(monkeypatch, state=initial, query=query)
    monkeypatch.setattr(app, "page_count", lambda _content: 3)
    monkeypatch.setattr(
        app, "_streamlit_process_service", lambda _actor: process_service,
    )

    app._ensure_streamlit_processes([upload], actor)

    digest = hashlib.sha256(content).hexdigest()
    execution_id = initial["process_execution_ids"][digest]
    created = process_service.get(execution_id, actor=actor)
    assert created is not None
    assert created.execution.metadata["page_mode"] == "selected"
    assert created.execution.metadata["selected_pages"] == [2]
    assert created.execution.metadata["periods"] == ["2024", "2023"]
    assert query[app.PROCESS_REGISTRY_QUERY_KEY]

    restarted = {}
    _install_streamlit_state(monkeypatch, state=restarted, query=query)
    app._restore_streamlit_process_scope([upload], actor)

    assert restarted["document_pages"] == {upload.name: [2]}
    assert restarted["company_periodos_seleccionados"] == ("2024", "2023")
    assert restarted["persisted_processes"][upload.name].execution.execution_id == execution_id


def test_manual_correction_is_audited_without_amounts_before_report(
    monkeypatch, actor, process_service,
):
    upload = Upload("balance.xlsx", b"workbook")
    state = {
        "company_periodos_seleccionados": ("2024",),
        "document_pages": {},
    }
    _install_streamlit_state(monkeypatch, state=state, query={})
    monkeypatch.setattr(
        app, "_streamlit_process_service", lambda _actor: process_service,
    )
    monkeypatch.setattr(app, "_authenticated_actor", lambda: actor)
    app._ensure_streamlit_processes([upload], actor)

    event = app._persist_streamlit_correction(
        upload.name, row_reference=7, classification_code="AC.01",
        action="classification-individual",
    )

    assert event is not None
    assert event.action == "CORRECTION_RECORDED"
    assert event.details["classification_code"] == "AC.01"
    assert "amount" not in event.details
    assert "monto" not in event.details
    current = state["persisted_processes"][upload.name]
    assert current.execution.status == "review"
    actions = [item.action for item in process_service.list_audit(
        current.execution.execution_id, actor=actor,
    )]
    assert actions == [
        "CORRECTION_RECORDED", "PROCESS_REVIEW_STARTED", "PROCESS_CREATED",
    ]


def test_confirmed_scope_change_closes_old_execution_and_starts_new_one(
    monkeypatch, actor, process_service,
):
    content = b"synthetic-pdf-content"
    digest = hashlib.sha256(content).hexdigest()
    upload = Upload("balance.pdf", content)
    state = {
        "document_pages": {upload.name: [1]},
        "company_periodos_seleccionados": ("2024",),
    }
    _install_streamlit_state(monkeypatch, state=state, query={})
    monkeypatch.setattr(app, "page_count", lambda _content: 3)
    monkeypatch.setattr(
        app, "_streamlit_process_service", lambda _actor: process_service,
    )
    app._ensure_streamlit_processes([upload], actor)
    old_id = state["process_execution_ids"][digest]

    state["document_pages"][upload.name] = [2, 3]
    state["process_scope_revisions_pending"] = {digest}
    app._ensure_streamlit_processes([upload], actor)

    new_id = state["process_execution_ids"][digest]
    assert new_id != old_id
    assert process_service.get(old_id, actor=actor).execution.status == "failed"
    new_process = process_service.get(new_id, actor=actor)
    assert new_process is not None
    assert new_process.execution.status == "running"
    assert new_process.execution.metadata["selected_pages"] == [2, 3]
    assert state["process_scope_revisions_pending"] == set()


def test_definitive_download_uses_reloaded_durable_report(
    monkeypatch, actor, process_service,
):
    upload = Upload("balance.xlsx", b"workbook")
    state = {
        "company_periodos_seleccionados": ("2024",),
        "document_pages": {},
    }
    _install_streamlit_state(monkeypatch, state=state, query={})
    monkeypatch.setattr(
        app, "_streamlit_process_service", lambda _actor: process_service,
    )
    monkeypatch.setattr(app, "_authenticated_actor", lambda: actor)
    app._ensure_streamlit_processes([upload], actor)

    assert app._persist_streamlit_definitive_report(
        upload.name, content=b"draft", report_name="draft.xlsx",
        certified=False,
    ) == b"draft"
    assert state["persisted_processes"][upload.name].execution.status == "running"

    durable = app._persist_streamlit_definitive_report(
        upload.name, content=b"certified-report", report_name="report.xlsx",
        certified=True,
    )
    assert durable == b"certified-report"
    completed = state["persisted_processes"][upload.name]
    assert completed.execution.status == "completed"
    assert len(completed.reports) == 1

    # Un rerun usa el único reporte ya completado y no crea un duplicado.
    assert app._persist_streamlit_definitive_report(
        upload.name, content=b"ignored-on-rerun", report_name="report.xlsx",
        certified=True,
    ) == b"certified-report"
    assert len(state["persisted_processes"][upload.name].reports) == 1


def test_authenticated_action_fails_closed_without_recoverable_process(
    monkeypatch, actor, process_service,
):
    _install_streamlit_state(monkeypatch, state={}, query={})
    monkeypatch.setattr(
        app, "_streamlit_process_service", lambda _actor: process_service,
    )
    monkeypatch.setattr(app, "_authenticated_actor", lambda: actor)

    with pytest.raises(ProcessPersistenceError) as error:
        app._persist_streamlit_correction(
            "missing.xlsx", row_reference=1, classification_code="AC.01",
            action="classification-individual",
        )
    assert error.value.stage == "streamlit_process_lookup"


def test_staging_without_actor_keeps_non_durable_compatibility(monkeypatch):
    _install_streamlit_state(monkeypatch, state={}, query={})
    monkeypatch.setattr(app, "_authenticated_actor", lambda: None)

    assert app._persist_streamlit_correction(
        "staging.xlsx", row_reference=1, classification_code="AC.01",
        action="classification-individual",
    ) is None
    assert app._persist_streamlit_definitive_report(
        "staging.xlsx", content=b"report", report_name="report.xlsx",
        certified=True,
    ) == b"report"
