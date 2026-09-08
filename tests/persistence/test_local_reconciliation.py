from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

import pytest

from persistence import PersistenceSettings, build_persistence
from persistence.contracts import AuthenticatedActor, AuthorizationDenied, ProcessScope
from persistence.local import LocalRuntimeReconciler
from scripts.reconcile_local_runtime import main as reconciliation_main


def _actor(
    organization_id: str = "org-1", *, role: str = "admin",
) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id=f"{role}-1",
        display_name="Administrador Uno",
        organization_id=organization_id,
        roles=frozenset({role}),
        provider_subject=f"subject-{role}-1",
    )


def _settings(tmp_path: Path) -> PersistenceSettings:
    catalog = tmp_path / "catalog.json"
    dictionary = tmp_path / "dictionary.json"
    catalog.write_text(json.dumps({
        "AC.01": {
            "codigo_estandar": "AC.01",
            "nombre_estandar": "Caja y Bancos",
            "categoria": "activo_corriente",
            "tipo_estado": "situacion",
            "naturaleza": "activo",
        },
    }), encoding="utf-8")
    dictionary.write_text("[]", encoding="utf-8")
    return PersistenceSettings(
        mode="local",
        local_root=tmp_path / "runtime",
        catalog_seed=catalog,
        dictionary_seed=dictionary,
    )


def _reconciler(bundle, root: Path) -> LocalRuntimeReconciler:
    assert bundle.executions is not None and bundle.audit is not None
    return LocalRuntimeReconciler(
        root, executions=bundle.executions, audit=bundle.audit,
    )


def _tree_fingerprint(root: Path, *, include_operational: bool = True) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if not include_operational and relative.split("/", 1)[0] == "operational":
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if path.is_file():
            digest.update(path.read_bytes())
            digest.update(str(path.stat().st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def test_scan_is_read_only_and_returns_only_aggregate_non_accounting_data(tmp_path):
    settings = _settings(tmp_path)
    bundle = build_persistence(settings)
    assert bundle.processes is not None and bundle.documents is not None
    process = bundle.processes.start(
        b"documento-original",
        original_name="balance-secreto.pdf",
        media_type="application/pdf",
        scope=ProcessScope("all", (), ("2024",)),
        actor=_actor(role="analyst"),
        application_version="test-1",
    )
    content_path = (
        settings.local_root / "documents" / process.document.storage_key
    )
    content_path.write_bytes(b"monto-contable-alterado-987654321")
    stale = content_path.parent / ".metadata.json.interrumpido.tmp"
    stale.write_text("CUENTA RESERVADA 123456", encoding="utf-8")
    old = datetime.now(timezone.utc) - timedelta(hours=48)
    os.utime(stale, (old.timestamp(), old.timestamp()))

    before = _tree_fingerprint(settings.local_root, include_operational=False)
    scan = _reconciler(bundle, settings.local_root).scan()
    after = _tree_fingerprint(settings.local_root, include_operational=False)
    payload = scan.aggregate()

    assert before == after
    assert payload["mode"] == "read_only"
    assert payload["counts"] == {
        "invalid_document_hash": 1,
        "stale_temporary": 1,
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "balance-secreto", "CUENTA RESERVADA", "987654321", str(content_path),
    ):
        assert forbidden not in serialized


def test_quarantine_is_explicit_audited_recoverable_and_never_deletes(tmp_path):
    settings = _settings(tmp_path)
    bundle = build_persistence(settings)
    assert bundle.documents is not None and bundle.audit is not None
    orphan = bundle.documents.save(
        b"documento-huerfano",
        original_name="huerfano.pdf",
        media_type="application/pdf",
        metadata={"organization_id": "org-1"},
    )
    original_directory = settings.local_root / "documents" / orphan.document_id
    original_fingerprint = LocalRuntimeReconciler._digest_path(original_directory)
    reconciler = _reconciler(bundle, settings.local_root)

    with pytest.raises(AuthorizationDenied):
        reconciler.quarantine(actor=_actor(role="analyst"))

    result = reconciler.quarantine(
        actor=_actor(), quarantine_retention_days=30,
    )
    assert result["mode"] == "repair"
    assert result["quarantined"] == 1
    assert not original_directory.exists()
    case_id = result["case_id"]
    case_root = settings.local_root / "quarantine" / "cases" / case_id
    manifest = json.loads((case_root / "manifest.json").read_text("utf-8"))
    assert manifest["status"] == "quarantined"
    assert manifest["actor_id"] == "admin-1"
    assert manifest["organization_id"] == "org-1"
    assert manifest["retention_days"] == 30
    quarantined = settings.local_root / manifest["entries"][0]["quarantine_path"]
    assert quarantined.exists()
    assert LocalRuntimeReconciler._digest_path(quarantined) == original_fingerprint

    events = bundle.audit.list_for_subject("runtime", "org-1")
    assert {event.action for event in events} >= {
        "RUNTIME_RECONCILIATION_STARTED",
        "RUNTIME_RECONCILIATION_COMPLETED",
    }
    assert all(event.actor_id == "admin-1" for event in events)
    assert all(event.details["organization_id"] == "org-1" for event in events)

    restored = reconciler.restore(case_id, actor=_actor())
    assert restored == {"mode": "restore", "case_id": case_id, "restored": 1}
    assert original_directory.exists()
    assert LocalRuntimeReconciler._digest_path(original_directory) == original_fingerprint
    assert case_root.exists()
    assert json.loads((case_root / "manifest.json").read_text("utf-8"))[
        "status"
    ] == "restored"


def test_quarantine_is_tenant_scoped_and_expired_cases_are_only_reported(tmp_path):
    settings = _settings(tmp_path)
    bundle = build_persistence(settings)
    assert bundle.documents is not None
    own = bundle.documents.save(
        b"own", original_name="own.pdf", media_type="application/pdf",
        metadata={"organization_id": "org-1"},
    )
    foreign = bundle.documents.save(
        b"foreign", original_name="foreign.pdf", media_type="application/pdf",
        metadata={"organization_id": "org-2"},
    )
    reconciler = _reconciler(bundle, settings.local_root)
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    result = reconciler.quarantine(
        actor=_actor("org-1"), quarantine_retention_days=1, now=start,
    )
    assert result["quarantined"] == 1
    assert result["unresolved"] == 1
    assert not (settings.local_root / "documents" / own.document_id).exists()
    assert (settings.local_root / "documents" / foreign.document_id).exists()

    later = reconciler.scan(
        quarantine_retention_days=3650,
        now=start + timedelta(days=2),
    )
    assert later.retention_due == 1
    case_root = (
        settings.local_root / "quarantine" / "cases" / result["case_id"]
    )
    assert case_root.exists(), "la retención vencida no borra la cuarentena"

    with pytest.raises(PermissionError):
        reconciler.restore(result["case_id"], actor=_actor("org-2"))


@pytest.mark.parametrize(
    ("temporary_hours", "retention_days"),
    [(0, 90), (8761, 90), (24, 0), (24, 3651)],
)
def test_retention_policy_rejects_unsafe_bounds(
    tmp_path, temporary_hours, retention_days,
):
    settings = _settings(tmp_path)
    bundle = build_persistence(settings)
    with pytest.raises(ValueError):
        _reconciler(bundle, settings.local_root).scan(
            temporary_min_age_hours=temporary_hours,
            quarantine_retention_days=retention_days,
        )


def test_cli_defaults_to_read_only_without_changing_runtime(tmp_path, capsys):
    settings = _settings(tmp_path)
    build_persistence(settings)
    before = _tree_fingerprint(settings.local_root)

    assert reconciliation_main(["--root", str(settings.local_root)]) == 0

    after = _tree_fingerprint(settings.local_root)
    payload = json.loads(capsys.readouterr().out)
    assert before == after
    assert payload["mode"] == "read_only"
    assert payload["finding_count"] == 0


def test_cli_requires_literal_confirmation_for_mutations(tmp_path):
    settings = _settings(tmp_path)
    build_persistence(settings)
    with pytest.raises(SystemExit):
        reconciliation_main([
            "--root", str(settings.local_root), "quarantine",
            "--actor-id", "admin-1", "--actor-name", "Admin",
            "--organization-id", "org-1",
            "--provider-subject", "subject-admin-1",
        ])


def test_cli_never_creates_missing_operational_database(tmp_path, capsys):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    result = reconciliation_main(["--root", str(runtime)])
    error = json.loads(capsys.readouterr().err)
    assert result == 2
    assert error["error_type"] == "FileNotFoundError"
    assert not (runtime / "operational").exists()
