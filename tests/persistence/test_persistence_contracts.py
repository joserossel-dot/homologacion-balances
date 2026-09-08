from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest

from persistence.contracts import (
    AuditEvent,
    LocalAuditRepository,
    LocalDocumentRepository,
    LocalExecutionRepository,
    LocalKnowledgeRepository,
    LocalReportRepository,
    LocalUserRepository,
    TelemetryEvent,
    UserRecord,
    ValidationDecision,
)
from persistence.contracts.remote import telemetry_as_closed_payload
from persistence.local import (
    FileDocumentRepository,
    FileReportRepository,
    JsonKnowledgeRepository,
    LegacyNeonKnowledgeAdapter,
    SqliteOperationalRepository,
)


NOW = datetime(2026, 8, 29, 20, 0, tzinfo=timezone.utc)


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def test_json_knowledge_repository_loads_and_updates_atomically(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    dictionary_path = tmp_path / "dictionary.json"
    _write_json(catalog_path, {
        "AC.01": {
            "nombre_estandar": "Caja y Bancos",
            "categoria": "activo_corriente",
            "tipo_estado": "situacion",
            "naturaleza": "activo",
        },
    })
    _write_json(dictionary_path, [{
        "cuenta_original": "Banco Uno",
        "codigo_estandar": "AC.01",
        "fuente": "seed",
    }])

    repository = JsonKnowledgeRepository(catalog_path, dictionary_path)
    assert isinstance(repository, LocalKnowledgeRepository)
    assert repository.healthcheck()

    repository.save_validations([
        ValidationDecision("Banco Uno", "AC.01", "manual"),
        ValidationDecision("Banco Dos", "AC.01", "manual"),
        ValidationDecision(
            "Control no persistido", "AC.01", "manual",
            add_to_dictionary=False,
        ),
    ])

    dictionary = repository.load_dictionary()
    assert [row["cuenta_original"] for row in dictionary] == [
        "Banco Dos", "Banco Uno",
    ]
    assert dictionary[1]["fuente"] == "manual"
    assert not list(tmp_path.glob("*.tmp"))
    history = (tmp_path / "history" / "validations.jsonl").read_text(
        encoding="utf-8",
    ).splitlines()
    assert len(history) == 3
    assert json.loads(history[-1])["add_to_dictionary"] is False


def test_legacy_neon_adapter_preserves_current_call_shape() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.single = None
            self.batch = None

        def healthcheck(self):
            return True

        def load_catalog(self):
            return {"AC.01": {"nombre_estandar": "Caja y Bancos"}}

        def load_dictionary(self):
            return [{"cuenta_original": "Banco", "codigo_estandar": "AC.01"}]

        def save_validation(self, **value):
            self.single = value

        def save_validations(self, values):
            self.batch = values

        def save_catalog_entry(self, entry):
            self.catalog_entry = entry

    store = FakeStore()
    adapter = LegacyNeonKnowledgeAdapter(store)
    assert isinstance(adapter, LocalKnowledgeRepository)
    decision = ValidationDecision("Banco", "AC.01", "manual", reviewer="u1")
    adapter.save_validation(decision)
    adapter.save_validations([decision])
    adapter.save_catalog_entry({"codigo_estandar": "AC.02"})
    assert store.single["account_name"] == "Banco"
    assert store.single["reviewer"] == "u1"
    assert store.batch == [decision.as_legacy_dict()]
    assert store.catalog_entry == {"codigo_estandar": "AC.02"}


def test_json_catalog_writes_are_atomic_audited_and_conservative(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    dictionary_path = tmp_path / "dictionary.json"
    _write_json(catalog_path, {})
    _write_json(dictionary_path, [])
    repository = JsonKnowledgeRepository(catalog_path, dictionary_path)
    entry = {
        "codigo_estandar": "ER.90",
        "nombre_estandar": "Resultado no controlador",
        "categoria": "resultado",
        "tipo_estado": "resultados",
        "naturaleza": "ganancia",
    }

    repository.save_catalog_entry(entry)
    repository.save_catalog_entry(entry)
    assert repository.load_catalog()["ER.90"]["nombre_estandar"] == (
        "Resultado no controlador"
    )
    history = (tmp_path / "history" / "catalog.jsonl").read_text(
        encoding="utf-8",
    ).splitlines()
    assert len(history) == 1
    assert json.loads(history[0])["codigo_estandar"] == "ER.90"
    assert not list(tmp_path.glob("*.tmp"))

    conflicting = dict(entry, nombre_estandar="Otro nombre")
    with pytest.raises(ValueError, match="no puede redefinirse"):
        repository.save_catalog_entry(conflicting)
    assert repository.load_catalog()["ER.90"]["nombre_estandar"] == (
        "Resultado no controlador"
    )


def test_json_catalog_concurrent_inserts_do_not_lose_entries(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    dictionary_path = tmp_path / "dictionary.json"
    _write_json(catalog_path, {})
    _write_json(dictionary_path, [])
    repository = JsonKnowledgeRepository(catalog_path, dictionary_path)

    def save(index: int) -> None:
        repository.save_catalog_entry({
            "codigo_estandar": f"ER.{80 + index}",
            "nombre_estandar": f"Categoría {index}",
            "categoria": "resultado",
            "tipo_estado": "resultados",
            "naturaleza": "ganancia",
        })

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(10)))
    assert len(repository.load_catalog()) == 10
    assert len((tmp_path / "history" / "catalog.jsonl").read_text(
        encoding="utf-8",
    ).splitlines()) == 10


def test_file_document_repository_round_trip_and_integrity(tmp_path) -> None:
    repository = FileDocumentRepository(tmp_path / "documents")
    assert isinstance(repository, LocalDocumentRepository)
    content = b"%PDF-1.7\ncontenido de prueba"
    record = repository.save(
        content,
        original_name="../../balance.pdf",
        media_type="application/pdf",
        metadata={"pages": [1, 2]},
    )
    assert record.original_name == "balance.pdf"
    assert record.sha256 == hashlib.sha256(content).hexdigest()
    assert repository.read(record.document_id) == content
    assert repository.get(record.document_id) == record

    content_path = repository.root / record.storage_key
    content_path.write_bytes(b"alterado")
    with pytest.raises(ValueError, match="Integridad documental"):
        repository.read(record.document_id)
    with pytest.raises(ValueError, match="document_id inválido"):
        repository.get("../../outside")

    metadata_path = repository.root / record.document_id / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["storage_key"] = "../../outside.bin"
    _write_json(metadata_path, metadata)
    with pytest.raises(ValueError, match="fuera del repositorio"):
        repository.get(record.document_id)


def test_file_report_repository_groups_by_execution(tmp_path) -> None:
    repository = FileReportRepository(tmp_path / "reports")
    assert isinstance(repository, LocalReportRepository)
    execution_id = uuid4().hex
    report = repository.save(
        b"xlsx-content",
        execution_id=execution_id,
        file_name=r"C:\temp\reporte.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        definitive=True,
    )
    assert report.file_name == "reporte.xlsx"
    assert repository.read(report.report_id) == b"xlsx-content"
    assert repository.list_for_execution(execution_id) == [report]
    assert repository.list_for_execution(uuid4().hex) == []
    with pytest.raises(ValueError, match="execution_id"):
        repository.list_for_execution("../escape")

    metadata_path = (
        repository.root / execution_id / report.report_id / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["execution_id"] = uuid4().hex
    _write_json(metadata_path, metadata)
    with pytest.raises(ValueError, match="inconsistentes"):
        repository.list_for_execution(execution_id)


def test_sqlite_operational_repository_is_durable_and_matches_ports(tmp_path) -> None:
    database = tmp_path / "operational.db"
    repository = SqliteOperationalRepository(database)
    assert isinstance(repository, LocalExecutionRepository)
    assert isinstance(repository, LocalAuditRepository)
    assert isinstance(repository, LocalUserRepository)

    user = UserRecord("analyst-1", "Analista Uno", "analyst", True, NOW)
    assert repository.upsert(user) == user
    execution = repository.create(
        document_id=uuid4().hex,
        application_version="c70e60e",
        metadata={"selected_pages": [5, 6, 7]},
    )
    running = repository.set_status(execution.execution_id, "running")
    assert running.status == "running"
    event = repository.append(AuditEvent(
        event_id=None,
        occurred_at=NOW,
        actor_id=user.user_id,
        action="EXECUTION_STARTED",
        subject_type="execution",
        subject_id=execution.execution_id,
        details={"document_id": execution.document_id},
    ))
    assert event.event_id == 1

    reopened = SqliteOperationalRepository(database)
    assert reopened.get_execution(execution.execution_id) == running
    assert reopened.get_user(user.user_id) == user
    assert reopened.list_active() == [user]
    assert reopened.list_for_subject("execution", execution.execution_id) == [event]


def test_sqlite_status_and_roles_fail_closed(tmp_path) -> None:
    repository = SqliteOperationalRepository(tmp_path / "operational.db")
    with pytest.raises(ValueError):
        repository.set_status("missing", "failed", error_code="NOT_FOUND")
    with repository._connect() as connection:
        with pytest.raises(Exception):
            connection.execute(
                """INSERT INTO local_users
                   (user_id, display_name, role, active, created_at)
                   VALUES ('u', 'Usuario', 'owner', 1, ?)""",
                (NOW.isoformat(),),
            )


def test_sqlite_rejects_invalid_and_stale_status_transitions(tmp_path) -> None:
    repository = SqliteOperationalRepository(tmp_path / "operational.sqlite3")
    execution = repository.create(
        document_id=uuid4().hex, application_version="test",
    )
    repository.set_status(execution.execution_id, "running", expected_status="pending")
    with pytest.raises(RuntimeError, match="Conflicto"):
        repository.set_status(execution.execution_id, "review", expected_status="pending")
    repository.set_status(execution.execution_id, "completed", expected_status="running")
    with pytest.raises(ValueError, match="Transición inválida"):
        repository.set_status(execution.execution_id, "running")


def test_json_writers_are_serialized_and_audited(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    dictionary_path = tmp_path / "dictionary.json"
    catalog_path.write_text(
        json.dumps({"AC.01": {
            "codigo_estandar": "AC.01", "nombre_estandar": "Caja",
            "categoria": "activo", "tipo_estado": "balance",
            "naturaleza": "activo",
        }}), encoding="utf-8",
    )
    dictionary_path.write_text("[]", encoding="utf-8")
    repository = JsonKnowledgeRepository(catalog_path, dictionary_path)

    def save(index: int) -> None:
        repository.save_validation(ValidationDecision(
            account_name=f"Cuenta {index}", validated_code="AC.01",
            source="humano", reviewer="test",
        ))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(24)))
    assert len(repository.load_dictionary()) == 24
    history = (tmp_path / "history" / "validations.jsonl").read_text(
        encoding="utf-8",
    ).splitlines()
    assert len(history) == 24


def test_telemetry_payload_has_closed_non_documental_shape() -> None:
    event = TelemetryEvent(
        event_type="processing_completed",
        organization_id="org-pseudonima",
        node_id="node-pseudonimo",
        application_version="1.0.0",
        master_bundle_version="2026.08.1",
        occurred_at=NOW + timedelta(seconds=1),
        metrics={"pages": 3, "ocr_used": False},
    )
    payload = telemetry_as_closed_payload(event)
    assert set(payload) == {
        "schema_version", "event_type", "organization_id", "node_id",
        "application_version", "master_bundle_version", "occurred_at", "metrics",
    }
    assert not {
        "document", "file_name", "rut", "account_name", "amount", "ocr_text",
    } & payload.keys()

    forbidden = TelemetryEvent(
        event_type=event.event_type,
        organization_id=event.organization_id,
        node_id=event.node_id,
        application_version=event.application_version,
        master_bundle_version=event.master_bundle_version,
        occurred_at=event.occurred_at,
        metrics={"amount": 1000},
    )
    with pytest.raises(ValueError, match="no permitidas"):
        telemetry_as_closed_payload(forbidden)
