from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
ONPREM = ROOT / "deployment" / "onprem"


def _module():
    spec = importlib.util.spec_from_file_location(
        "runtime_archive", ONPREM / "runtime_archive.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime(root: Path, *, marker: str = "original") -> Path:
    (root / "knowledge").mkdir(parents=True)
    (root / "operational").mkdir()
    (root / "documents" / "doc-1").mkdir(parents=True)
    (root / "knowledge" / "catalogo_maestro.json").write_text(
        json.dumps({"AC.01": {"nombre_estandar": "Caja"}}), encoding="utf-8",
    )
    (root / "knowledge" / "diccionario.json").write_text("[]", encoding="utf-8")
    (root / "documents" / "doc-1" / "content.bin").write_bytes(marker.encode())
    with sqlite3.connect(root / "operational" / "operations.db") as connection:
        connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES (?)", (marker,))
    return root


def test_runtime_archive_round_trip_and_atomic_local_restore(tmp_path) -> None:
    module = _module()
    source = _runtime(tmp_path / "source", marker="snapshot")
    archive = tmp_path / "runtime.tar.gz"
    manifest = module.create_archive(source, archive, rpo_hours=24, rto_hours=8)
    assert manifest["format"] == "homologacion-app-runtime-v1"
    assert "operational/operations.db" in manifest["files"]
    assert module.verify_archive(archive)["files"] == manifest["files"]

    target = _runtime(tmp_path / "target", marker="before")
    previous = module.restore_local(archive, target)
    assert previous is not None and previous.is_dir()
    assert (previous / "documents" / "doc-1" / "content.bin").read_text() == "before"
    assert (target / "documents" / "doc-1" / "content.bin").read_text() == "snapshot"
    with sqlite3.connect(target / "operational" / "operations.db") as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "snapshot"


def test_runtime_archive_rejects_traversal_and_manifest_tampering(tmp_path) -> None:
    module = _module()
    unsafe = tmp_path / "unsafe.tar.gz"
    with tarfile.open(unsafe, "w:gz") as bundle:
        payload = b"escape"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="insegura"):
        module.verify_archive(unsafe)

    source = _runtime(tmp_path / "source")
    valid = tmp_path / "valid.tar.gz"
    module.create_archive(source, valid, rpo_hours=24, rto_hours=8)
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(valid, "r:gz") as bundle:
        bundle.extractall(extracted, filter="data")
    (extracted / "knowledge" / "diccionario.json").write_text(
        '[{"alterado": true}]', encoding="utf-8",
    )
    tampered = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered, "w:gz") as bundle:
        for path in sorted(extracted.rglob("*")):
            if path.is_file():
                bundle.add(path, arcname=path.relative_to(extracted).as_posix())
    with pytest.raises(ValueError, match="Integridad inválida"):
        module.verify_archive(tampered)


def test_invalid_restore_keeps_current_runtime_unchanged(tmp_path) -> None:
    module = _module()
    target = _runtime(tmp_path / "target", marker="must-remain")
    invalid = tmp_path / "invalid.tar.gz"
    invalid.write_bytes(b"not-a-tar")
    with pytest.raises((tarfile.TarError, OSError)):
        module.restore_local(invalid, target)
    assert (target / "documents" / "doc-1" / "content.bin").read_text() == (
        "must-remain"
    )


def test_local_restore_rolls_back_when_final_replace_fails(monkeypatch, tmp_path) -> None:
    module = _module()
    source = _runtime(tmp_path / "source", marker="new")
    archive = tmp_path / "runtime.tar.gz"
    module.create_archive(source, archive, rpo_hours=24, rto_hours=8)
    target = _runtime(tmp_path / "target", marker="current")
    original_replace = module.os.replace
    failed = False

    def injected_replace(source_path, destination_path):
        nonlocal failed
        if ".staging." in str(source_path) and Path(destination_path) == target and not failed:
            failed = True
            raise OSError("injected final replace failure")
        return original_replace(source_path, destination_path)

    monkeypatch.setattr(module.os, "replace", injected_replace)
    with pytest.raises(OSError, match="injected"):
        module.restore_local(archive, target)
    assert (target / "documents" / "doc-1" / "content.bin").read_text() == "current"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_runtime_scripts_require_encryption_and_restore_direct_directory(tmp_path) -> None:
    source = _runtime(tmp_path / "source", marker="encrypted-snapshot")
    backup_dir = tmp_path / "backups"
    key = tmp_path / "backup.key"
    key.write_text("clave-externa-prueba", encoding="utf-8")
    key.chmod(0o600)
    environment = {
        **os.environ,
        "RUNTIME_SOURCE_DIR": str(source),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "production",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(key),
    }
    backup = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup-runtime.sh")],
        env=environment, capture_output=True, text=True,
    )
    assert backup.returncode == 0, backup.stderr
    archives = list(backup_dir.glob("*.tar.gz.enc"))
    assert len(archives) == 1
    archive = archives[0]
    assert Path(str(archive) + ".sha256").is_file()
    assert json.loads(Path(str(archive) + ".meta.json").read_text())["format"] == (
        "homologacion-app-runtime-v1"
    )

    target = _runtime(tmp_path / "target", marker="before")
    restore = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore-runtime.sh"), str(archive), "--confirm"],
        env={**environment, "RUNTIME_TARGET_DIR": str(target)},
        capture_output=True, text=True,
    )
    assert restore.returncode == 0, restore.stderr
    assert (target / "documents" / "doc-1" / "content.bin").read_text() == (
        "encrypted-snapshot"
    )


def test_runtime_backup_production_rejects_missing_external_key(tmp_path) -> None:
    source = _runtime(tmp_path / "source")
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup-runtime.sh")],
        env={
            **os.environ,
            "RUNTIME_SOURCE_DIR": str(source),
            "BACKUP_DIR": str(tmp_path / "backups"),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(tmp_path / "missing.key"),
        },
        capture_output=True, text=True,
    )
    assert result.returncode == 78
    assert "BACKUP_ENCRYPTION_KEY_FILE" in result.stderr


def test_failed_backup_does_not_delete_unrelated_hidden_files(tmp_path):
    sentinels = [tmp_path / name for name in (".sha256", ".meta.json", ".meta.json.sha256")]
    for path in sentinels:
        path.write_text("preservar")
    source = tmp_path / "invalid-runtime"
    source.mkdir()
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup-runtime.sh")], cwd=tmp_path,
        env={**os.environ, "RUNTIME_SOURCE_DIR": str(source),
             "BACKUP_DIR": str(tmp_path / "backups"),
             "ONPREM_DEPLOYMENT_MODE": "evaluation", "BACKUP_ENCRYPTION_REQUIRED": "false",
             "BACKUP_ENCRYPTION_KEY_FILE": ""},
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert all(path.read_text() == "preservar" for path in sentinels)


@pytest.mark.parametrize("failure,expected_code", [("copy", 73), ("restart", 70)])
def test_restore_failure_attempts_rollback_and_remains_failed(tmp_path, failure, expected_code):
    # Docker dispatch stub: host copies supply the valid pre-restore snapshot.
    # This exercises shell failure handling, not container recovery certification.
    source = _runtime(tmp_path / "source")
    archive = tmp_path / "input.tar.gz"
    _module().create_archive(source, archive, rpo_hours=24, rto_hours=8)
    import hashlib
    Path(str(archive) + ".sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest())
    log = tmp_path / "calls.jsonl"
    docker = tmp_path / "docker-stub"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json,os,shutil,sys\n"
        "args=sys.argv[1:]\n"
        "with open(os.environ['CALL_LOG'],'a') as output: output.write(json.dumps(args)+'\\n')\n"
        "if 'ps' in args: print('app\\nreverse-proxy')\n"
        "mount=args[args.index('-v')+1] if '-v' in args else ''\n"
        "if mount.endswith(':/snapshot'):\n"
        "    shutil.copytree(os.environ['SNAPSHOT_SOURCE'], mount[:-10], dirs_exist_ok=True)\n"
        "if '/staging:/replacement:ro' in mount and os.environ['FAILURE']=='copy': sys.exit(73)\n"
        "if 'start' in args and os.environ['FAILURE']=='restart': sys.exit(74)\n"
    )
    docker.chmod(0o700)
    environment = {
        **os.environ, "DOCKER_BIN": str(docker), "CALL_LOG": str(log),
        "SNAPSHOT_SOURCE": str(source), "FAILURE": failure,
        "ONPREM_DEPLOYMENT_MODE": "evaluation", "BACKUP_ENCRYPTION_REQUIRED": "false",
        "BACKUP_ENCRYPTION_KEY_FILE": "", "BACKUP_DIR": str(tmp_path / "backups"),
        "RUNTIME_SOURCE_DIR": "", "RUNTIME_TARGET_DIR": "", "TMPDIR": str(tmp_path),
    }
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore-runtime.sh"), str(archive), "--confirm"],
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode == expected_code, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert any(any('/rollback:/replacement:ro' in arg for arg in call) for call in calls)
    assert "Restore app_runtime verificado" not in result.stdout
    if failure == "restart":
        assert "no se pudieron reiniciar" in result.stderr
