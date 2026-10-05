"""Contrato de autenticidad para respaldos on-premise.

Las pruebas usan exclusivamente datos sintéticos. La autenticación debe validarse
antes de descifrar, restaurar o invocar Docker.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ONPREM = ROOT / "deployment" / "onprem"
AUTH_TOOL = ONPREM / "backup_auth.py"
SCRIPTS = ONPREM / "scripts"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_checksum(path: Path) -> None:
    Path(str(path) + ".sha256").write_text(
        f"{_sha256(path)}  {path.name}\n", encoding="utf-8",
    )


def _write_metadata(
    path: Path, *, payload_kind: str, encrypted: bool = True
) -> Path:
    metadata = Path(str(path) + ".meta.json")
    backup_format = (
        "homologacion-app-runtime-v1"
        if payload_kind == "app-runtime"
        else "postgres-custom"
    )
    metadata.write_text(
        json.dumps(
            {
                "created_at": "20260927T120000Z",
                "encrypted": encrypted,
                "format": backup_format,
                "retention_days": 30,
                "rpo_hours": 24,
                "rto_hours": 8,
                "envelope_version": 2,
                "authentication": "hmac-sha256",
            },
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    _write_checksum(metadata)
    return metadata


def _key(path: Path, value: str = "clave-sintetica-principal-2026") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _auth_cli(
    action: str,
    *,
    artifact: Path,
    metadata: Path,
    key_file: Path,
    auth_file: Path,
    payload_kind: str = "app-runtime",
    key_id: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(AUTH_TOOL),
        action,
        "--artifact",
        str(artifact),
        "--metadata",
        str(metadata),
        "--key-file",
        str(key_file),
        "--payload-kind",
        payload_kind,
    ]
    command.extend(["--output" if action == "sign" else "--auth", str(auth_file)])
    if key_id is not None:
        command.extend(["--key-id", key_id])
    return subprocess.run(command, capture_output=True, text=True)


def _load_auth_tool():
    spec = importlib.util.spec_from_file_location(
        "backup_auth_for_known_vector", AUTH_TOOL,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime(root: Path, marker: str) -> Path:
    (root / "knowledge").mkdir(parents=True)
    (root / "operational").mkdir()
    (root / "documents" / "synthetic-document").mkdir(parents=True)
    (root / "knowledge" / "catalogo_maestro.json").write_text(
        json.dumps({"AC.01": {"nombre_estandar": "Cuenta sintética"}}),
        encoding="utf-8",
    )
    (root / "knowledge" / "diccionario.json").write_text("[]", encoding="utf-8")
    (root / "documents" / "synthetic-document" / "content.bin").write_text(
        marker, encoding="utf-8",
    )
    with sqlite3.connect(root / "operational" / "operations.db") as connection:
        connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES (?)", (marker,))
    return root


def _runtime_archive(source: Path, archive: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "runtime_archive_for_auth_tests", ONPREM / "runtime_archive.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.create_archive(source, archive, rpo_hours=24, rto_hours=8)
    _write_checksum(archive)


def _runtime_backup(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    source = _runtime(tmp_path / "origen sintético con espacios", "respaldo-nuevo")
    backup_dir = tmp_path / "respaldos autenticados con espacios"
    key_file = _key(tmp_path / "llaves con espacios" / "clave principal.key")
    environment = {
        **os.environ,
        "RUNTIME_SOURCE_DIR": str(source),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
    }
    result = subprocess.run(
        ["sh", str(SCRIPTS / "backup-runtime.sh")],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    archives = list(backup_dir.glob("*.tar.gz.enc"))
    assert len(archives) == 1
    return archives[0], key_file, environment


def _authenticated_plain_runtime(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, str]]:
    source = _runtime(tmp_path / "plain-runtime-source", "snapshot-autenticado")
    archive = tmp_path / "plain-runtime.tar.gz"
    _runtime_archive(source, archive)
    metadata = _write_metadata(
        archive, payload_kind="app-runtime", encrypted=False
    )
    key_file = _key(tmp_path / "plain-runtime.key")
    auth_file = Path(str(archive) + ".auth.json")
    signed = _auth_cli(
        "sign",
        artifact=archive,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert signed.returncode == 0, signed.stderr
    environment = {
        **os.environ,
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
        "BACKUP_AUTHENTICATION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
    }
    return archive, metadata, auth_file, environment


def _docker_stub(tmp_path: Path) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    executable = tmp_path / "docker sintético"
    log = tmp_path / "docker-calls.log"
    executable.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "case \"$*\" in\n"
        "  *\"start app\"*) "
        "[ \"${DOCKER_FAIL_START_APP:-false}\" != true ] || exit 74 ;;\n"
        "esac\n"
        "case \"$*\" in\n"
        "  *\"ps --services\"*) printf 'app\\nreverse-proxy\\n' ;;\n"
        "  *\"pg_dump\"*) printf 'contenido-postgres-sintetico' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable, log


def _postgres_backup(tmp_path: Path) -> tuple[Path, Path, dict[str, str], Path]:
    docker, log = _docker_stub(tmp_path)
    backup_dir = tmp_path / "respaldos postgres con espacios"
    key_file = _key(tmp_path / "llaves" / "clave postgres.key")
    environment = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "production",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
        "BACKUP_RETENTION_DAYS": "30",
        "BACKUP_RPO_HOURS": "24",
        "BACKUP_RTO_HOURS": "8",
    }
    result = subprocess.run(
        ["sh", str(SCRIPTS / "backup.sh")],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    archives = list(backup_dir.glob("*.dump.enc"))
    assert len(archives) == 1
    return archives[0], key_file, environment, log


def test_backup_auth_cli_round_trip_and_strict_sidecar_schema(tmp_path: Path) -> None:
    artifact = tmp_path / "directorio con espacios" / "respaldo cifrado.enc"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"ciphertext-sintetico\x00\x01")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "llave con espacios.key")
    auth_file = Path(str(artifact) + ".auth.json")

    signed = _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
        key_id="clave-principal",
    )
    assert signed.returncode == 0, signed.stderr
    envelope = json.loads(auth_file.read_text(encoding="utf-8"))
    assert set(envelope) == {
        "schema",
        "algorithm",
        "kdf",
        "iterations",
        "salt_hex",
        "payload_kind",
        "tag",
        "key_id",
    }
    assert envelope["schema"] == "homologacion-backup-auth-v1"
    assert envelope["algorithm"] == "hmac-sha256"
    assert envelope["kdf"] == "pbkdf2-hmac-sha256"
    assert envelope["iterations"] == 200_000
    assert envelope["payload_kind"] == "app-runtime"
    assert envelope["key_id"] == "clave-principal"
    assert len(envelope["salt_hex"]) == 64
    assert len(envelope["tag"]) == 64
    int(envelope["salt_hex"], 16)
    int(envelope["tag"], 16)

    verified = _auth_cli(
        "verify",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert verified.returncode == 0, verified.stderr


def test_backup_auth_matches_independent_frozen_cryptographic_vector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = b"correct horse battery staple 2026"
    salt = bytes(range(32))
    metadata_bytes = b'{"format":"synthetic"}\n'
    payload_bytes = b"\x00known-payload\xff"
    expected_derived_key = (
        "95b8372f8fa98c2d75b9297e04657c504d5be2d4900d19f0b3098a7d9c8a62e8"
    )
    expected_tag = (
        "5637b024da61420a73fc76ca35a3d015b09461a132bf52a6a2494af23058ffe3"
    )
    domain = b"homologacion-backup-auth-v1\0"
    header = {
        "algorithm": "hmac-sha256",
        "iterations": 200_000,
        "kdf": "pbkdf2-hmac-sha256",
        "payload_kind": "app-runtime",
        "salt_hex": salt.hex(),
        "schema": "homologacion-backup-auth-v1",
    }
    canonical_header = json.dumps(
        header,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    derived_key = hashlib.pbkdf2_hmac(
        "sha256", secret, domain + salt, 200_000, dklen=32,
    )
    independent_mac = hmac.new(derived_key, digestmod=hashlib.sha256)
    for component in (
        domain,
        struct.pack(">Q", len(canonical_header)),
        canonical_header,
        struct.pack(">Q", len(metadata_bytes)),
        metadata_bytes,
        struct.pack(">Q", len(payload_bytes)),
        payload_bytes,
    ):
        independent_mac.update(component)
    assert derived_key.hex() == expected_derived_key
    assert independent_mac.hexdigest() == expected_tag

    artifact = tmp_path / "known-vector.bin"
    metadata = tmp_path / "known-vector.meta.json"
    key_file = tmp_path / "known-vector.key"
    auth_file = tmp_path / "known-vector.auth.json"
    artifact.write_bytes(payload_bytes)
    metadata.write_bytes(metadata_bytes)
    key_file.write_bytes(secret)
    key_file.chmod(0o600)
    module = _load_auth_tool()
    monkeypatch.setattr(module.secrets, "token_bytes", lambda size: salt)
    module.sign(
        artifact_path=artifact,
        metadata_path=metadata,
        key_file=key_file,
        output_path=auth_file,
        payload_kind="app-runtime",
        key_id=None,
    )
    assert json.loads(auth_file.read_text(encoding="utf-8"))["tag"] == expected_tag


def test_backup_auth_verify_stages_exact_private_copies(tmp_path: Path) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-autenticado")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "stage.key")
    auth_file = Path(str(artifact) + ".auth.json")
    signed = _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert signed.returncode == 0, signed.stderr

    private_dir = tmp_path / "private-stage"
    private_dir.mkdir(mode=0o700)
    staged_artifact = private_dir / "payload"
    staged_metadata = private_dir / "metadata.json"
    staged_key = private_dir / "key"
    verified = subprocess.run(
        [
            sys.executable,
            str(AUTH_TOOL),
            "verify",
            "--artifact",
            str(artifact),
            "--metadata",
            str(metadata),
            "--key-file",
            str(key_file),
            "--auth",
            str(auth_file),
            "--payload-kind",
            "app-runtime",
            "--staged-artifact",
            str(staged_artifact),
            "--staged-metadata",
            str(staged_metadata),
            "--staged-key",
            str(staged_key),
        ],
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert staged_artifact.read_bytes() == b"payload-autenticado"
    assert staged_metadata.read_bytes() == metadata.read_bytes()
    assert staged_key.read_bytes() == key_file.read_bytes() + b"\n"
    assert staged_artifact.stat().st_mode & 0o777 == 0o600
    assert staged_metadata.stat().st_mode & 0o777 == 0o600
    assert staged_key.stat().st_mode & 0o777 == 0o600

    artifact.write_bytes(b"payload-cambiado-despues")
    metadata.write_text("{}", encoding="utf-8")
    key_file.write_text("clave-cambiada-despues", encoding="utf-8")
    assert staged_artifact.read_bytes() == b"payload-autenticado"
    assert json.loads(staged_metadata.read_text(encoding="utf-8"))["format"] == (
        "homologacion-app-runtime-v1"
    )
    assert staged_key.read_bytes() == b"clave-sintetica-principal-2026\n"


def test_backup_auth_failed_stage_publishes_no_outputs(tmp_path: Path) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "stage.key")
    auth_file = Path(str(artifact) + ".auth.json")
    assert _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    ).returncode == 0
    artifact.write_bytes(b"payload-adulterado")
    private_dir = tmp_path / "private-stage"
    private_dir.mkdir(mode=0o700)
    staged_artifact = private_dir / "payload"
    staged_metadata = private_dir / "metadata.json"
    staged_key = private_dir / "key"
    rejected = subprocess.run(
        [
            sys.executable,
            str(AUTH_TOOL),
            "verify",
            "--artifact",
            str(artifact),
            "--metadata",
            str(metadata),
            "--key-file",
            str(key_file),
            "--auth",
            str(auth_file),
            "--payload-kind",
            "app-runtime",
            "--staged-artifact",
            str(staged_artifact),
            "--staged-metadata",
            str(staged_metadata),
            "--staged-key",
            str(staged_key),
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 65
    assert not staged_artifact.exists()
    assert not staged_metadata.exists()
    assert not staged_key.exists()
    assert list(private_dir.iterdir()) == []


def test_backup_auth_rejects_aliased_staged_outputs(tmp_path: Path) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "alias.key")
    auth_file = Path(str(artifact) + ".auth.json")
    assert _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    ).returncode == 0
    private_dir = tmp_path / "private-stage"
    private_dir.mkdir(mode=0o700)
    (private_dir / "alias").mkdir(mode=0o700)
    shared_output = private_dir / "payload"
    aliased_output = private_dir / "alias" / ".." / "payload"
    rejected = subprocess.run(
        [
            sys.executable,
            str(AUTH_TOOL),
            "verify",
            "--artifact",
            str(artifact),
            "--metadata",
            str(metadata),
            "--key-file",
            str(key_file),
            "--auth",
            str(auth_file),
            "--payload-kind",
            "app-runtime",
            "--staged-artifact",
            str(shared_output),
            "--staged-metadata",
            str(aliased_output),
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 65
    assert not shared_output.exists()


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW no disponible")
@pytest.mark.parametrize("key_defect", ("symlink", "world-readable"))
def test_backup_auth_rejects_insecure_key_after_signing(
    tmp_path: Path, key_defect: str
) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "private.key")
    auth_file = Path(str(artifact) + ".auth.json")
    assert _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    ).returncode == 0
    if key_defect == "symlink":
        regular = key_file.with_name("private.key.regular")
        key_file.replace(regular)
        key_file.symlink_to(regular)
    else:
        key_file.chmod(0o644)
    rejected = _auth_cli(
        "verify",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert rejected.returncode == 65


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW no disponible")
@pytest.mark.parametrize("linked_input", ("artifact", "metadata", "auth"))
def test_backup_auth_rejects_symlink_inputs(
    tmp_path: Path, linked_input: str
) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "symlink.key")
    auth_file = Path(str(artifact) + ".auth.json")
    assert _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    ).returncode == 0
    selected = {"artifact": artifact, "metadata": metadata, "auth": auth_file}[
        linked_input
    ]
    regular = selected.with_name(selected.name + ".regular")
    selected.replace(regular)
    selected.symlink_to(regular)

    rejected = _auth_cli(
        "verify",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert rejected.returncode == 65


@pytest.mark.parametrize("malformation", ("duplicate-key", "oversize"))
def test_backup_auth_rejects_duplicate_or_oversize_envelope(
    tmp_path: Path, malformation: str
) -> None:
    artifact = tmp_path / "payload.enc"
    artifact.write_bytes(b"payload-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "strict-envelope.key")
    auth_file = Path(str(artifact) + ".auth.json")
    assert _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    ).returncode == 0
    if malformation == "duplicate-key":
        original = auth_file.read_text(encoding="utf-8").strip()
        auth_file.write_text(
            '{"schema":"homologacion-backup-auth-v1",' + original[1:],
            encoding="utf-8",
        )
    else:
        auth_file.write_bytes(b" " * (16 * 1024 + 1))
    rejected = _auth_cli(
        "verify",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert rejected.returncode == 65


@pytest.mark.parametrize(
    "mutation",
    ("artifact", "metadata", "wrong-key", "tag", "malformed", "unknown-field"),
)
def test_backup_auth_cli_rejects_tampering_and_malformed_envelopes(
    tmp_path: Path,
    mutation: str,
) -> None:
    artifact = tmp_path / "authenticated.enc"
    artifact.write_bytes(b"ciphertext-original")
    metadata = _write_metadata(artifact, payload_kind="app-runtime")
    key_file = _key(tmp_path / "primary.key")
    auth_file = Path(str(artifact) + ".auth.json")
    signed = _auth_cli(
        "sign",
        artifact=artifact,
        metadata=metadata,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert signed.returncode == 0, signed.stderr

    verification_key = key_file
    if mutation == "artifact":
        artifact.write_bytes(artifact.read_bytes() + b"-alterado")
    elif mutation == "metadata":
        content = json.loads(metadata.read_text(encoding="utf-8"))
        content["rpo_hours"] = 12
        metadata.write_text(json.dumps(content), encoding="utf-8")
    elif mutation == "wrong-key":
        verification_key = _key(tmp_path / "wrong.key", "clave-distinta-2026")
    elif mutation == "tag":
        content = json.loads(auth_file.read_text(encoding="utf-8"))
        content["tag"] = "0" * 64
        auth_file.write_text(json.dumps(content), encoding="utf-8")
    elif mutation == "malformed":
        auth_file.write_text("{json incompleto", encoding="utf-8")
    elif mutation == "unknown-field":
        content = json.loads(auth_file.read_text(encoding="utf-8"))
        content["campo_no_permitido"] = True
        auth_file.write_text(json.dumps(content), encoding="utf-8")

    rejected = _auth_cli(
        "verify",
        artifact=artifact,
        metadata=metadata,
        key_file=verification_key,
        auth_file=auth_file,
    )
    assert rejected.returncode == 65


def test_production_runtime_backup_rejects_source_override_before_docker(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path / "production-source-override", "no-usar")
    key_file = _key(tmp_path / "production-source.key")
    backup_dir = tmp_path / "production-source-backups"
    docker, log = _docker_stub(tmp_path / "production-source-docker")

    result = subprocess.run(
        ["sh", str(SCRIPTS / "backup-runtime.sh")],
        env={
            **os.environ,
            "RUNTIME_SOURCE_DIR": str(source),
            "BACKUP_DIR": str(backup_dir),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
            "DOCKER_BIN": str(docker),
            "DOCKER_LOG": str(log),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 78
    assert "RUNTIME_SOURCE_DIR" in result.stderr
    assert not log.exists()
    assert not backup_dir.exists()


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_production_runtime_backup_accepts_explicit_quiesced_internal_source(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path / "quiesced-source", "snapshot-quiesced")
    key_file = _key(tmp_path / "quiesced-source.key")
    backup_dir = tmp_path / "quiesced-source-backups"

    result = subprocess.run(
        [
            "sh",
            str(SCRIPTS / "backup-runtime.sh"),
            "--source-dir",
            str(source),
            "--confirm-quiesced",
        ],
        env={
            **os.environ,
            "RUNTIME_SOURCE_DIR": "",
            "BACKUP_DIR": str(backup_dir),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    archives = list(backup_dir.glob("*.tar.gz.enc"))
    assert len(archives) == 1
    assert Path(str(archives[0]) + ".auth.json").is_file()


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_production_runtime_restore_reaches_authenticated_internal_prebackup(
    tmp_path: Path,
) -> None:
    archive, key_file, environment = _runtime_backup(tmp_path)
    current_runtime = _runtime(tmp_path / "container-current-runtime", "antes")
    docker_log = tmp_path / "container-restore-calls.jsonl"
    docker = tmp_path / "container-restore-docker"
    docker.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, shutil, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_LOG'], 'a', encoding='utf-8') as stream:\n"
        "    stream.write(json.dumps(args) + '\\n')\n"
        "if 'ps' in args:\n"
        "    print('app\\nreverse-proxy')\n"
        "for index, value in enumerate(args[:-1]):\n"
        "    if value == '-v' and args[index + 1].endswith(':/snapshot'):\n"
        "        destination = pathlib.Path(args[index + 1][:-10])\n"
        "        shutil.copytree(\n"
        "            os.environ['CURRENT_RUNTIME'], destination, dirs_exist_ok=True\n"
        "        )\n",
        encoding="utf-8",
    )
    docker.chmod(0o700)

    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "RUNTIME_SOURCE_DIR": "",
            "RUNTIME_TARGET_DIR": "",
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
            "DOCKER_BIN": str(docker),
            "DOCKER_LOG": str(docker_log),
            "CURRENT_RUNTIME": str(current_runtime),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Restore app_runtime verificado" in result.stdout
    assert len(list((Path(environment["BACKUP_DIR"]) / "pre-restore").glob(
        "*.tar.gz.enc"
    ))) == 1
    calls = [json.loads(line) for line in docker_log.read_text().splitlines()]
    assert any("stop" in call for call in calls)
    assert any(any(value.endswith(":/snapshot") for value in call) for call in calls)


def test_production_runtime_restore_rejects_target_override_before_docker(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "production-target.tar.gz.enc"
    archive.write_bytes(b"contenido-no-debe-procesarse")
    _write_checksum(archive)
    key_file = _key(tmp_path / "production-target.key")
    target = _runtime(tmp_path / "production-target", "intacto")
    docker, log = _docker_stub(tmp_path / "production-target-docker")

    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **os.environ,
            "RUNTIME_TARGET_DIR": str(target),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
            "DOCKER_BIN": str(docker),
            "DOCKER_LOG": str(log),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 78
    assert "RUNTIME_TARGET_DIR" in result.stderr
    assert not log.exists()
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "intacto"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_runtime_backup_writes_authenticated_envelope_and_exact_metadata(
    tmp_path: Path,
) -> None:
    archive, key_file, _ = _runtime_backup(tmp_path)
    metadata_file = Path(str(archive) + ".meta.json")
    auth_file = Path(str(archive) + ".auth.json")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata == {
        "created_at": metadata["created_at"],
        "encrypted": True,
        "format": "homologacion-app-runtime-v1",
        "retention_days": 30,
        "rpo_hours": 24,
        "rto_hours": 8,
        "envelope_version": 2,
        "authentication": "hmac-sha256",
    }
    assert Path(str(archive) + ".sha256").is_file()
    assert Path(str(metadata_file) + ".sha256").is_file()
    assert auth_file.is_file()
    result = _auth_cli(
        "verify",
        artifact=archive,
        metadata=metadata_file,
        key_file=key_file,
        auth_file=auth_file,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_runtime_backup_uses_one_captured_key_for_encryption_and_authentication(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path / "runtime-key-race-source", "captura-unica")
    backup_dir = tmp_path / "runtime-key-race-backups"
    mutable_key = _key(
        tmp_path / "runtime-key-race.key", "clave-original-capturada-2026",
    )
    verification_key = _key(
        tmp_path / "runtime-key-verification.key", "clave-original-capturada-2026",
    )
    fake_bin = tmp_path / "runtime-key-race-bin"
    fake_bin.mkdir()
    fake_sha = fake_bin / "sha256sum"
    fake_sha.write_text(
        f"#!{sys.executable}\n"
        "import hashlib, os, pathlib, sys\n"
        "pathlib.Path(os.environ['MUTATE_KEY']).write_text(\n"
        "    'clave-rotada-despues-del-cifrado-2026', encoding='utf-8'\n"
        ")\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "print(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')\n",
        encoding="utf-8",
    )
    fake_sha.chmod(0o700)
    backup_environment = {
        **os.environ,
        "RUNTIME_SOURCE_DIR": str(source),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_AUTHENTICATION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(mutable_key),
        "MUTATE_KEY": str(mutable_key),
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    created = subprocess.run(
        ["sh", str(SCRIPTS / "backup-runtime.sh")],
        env=backup_environment,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    assert mutable_key.read_text(encoding="utf-8") == (
        "clave-rotada-despues-del-cifrado-2026"
    )
    archives = list(backup_dir.glob("*.tar.gz.enc"))
    assert len(archives) == 1

    target = _runtime(tmp_path / "runtime-key-race-target", "estado-anterior")
    restored = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archives[0]), "--confirm"],
        env={
            **os.environ,
            "ONPREM_DEPLOYMENT_MODE": "evaluation",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(verification_key),
            "RUNTIME_TARGET_DIR": str(target),
        },
        capture_output=True,
        text=True,
    )
    assert restored.returncode == 0, restored.stderr
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "captura-unica"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
@pytest.mark.parametrize(
    "mutation",
    ("artifact", "metadata", "wrong-key", "tag", "malformed", "missing-auth"),
)
def test_runtime_restore_rejects_auth_failures_before_docker_and_preserves_target(
    tmp_path: Path,
    mutation: str,
) -> None:
    archive, key_file, environment = _runtime_backup(tmp_path)
    metadata = Path(str(archive) + ".meta.json")
    auth_file = Path(str(archive) + ".auth.json")
    verification_key = key_file
    if mutation == "artifact":
        artifact_bytes = bytearray(archive.read_bytes())
        artifact_bytes[len(artifact_bytes) // 2] ^= 0x01
        archive.write_bytes(artifact_bytes)
        _write_checksum(archive)
    elif mutation == "metadata":
        content = json.loads(metadata.read_text(encoding="utf-8"))
        content["retention_days"] = 31
        metadata.write_text(json.dumps(content), encoding="utf-8")
        _write_checksum(metadata)
    elif mutation == "wrong-key":
        verification_key = _key(tmp_path / "wrong.key", "clave-equivocada")
    elif mutation == "tag":
        content = json.loads(auth_file.read_text(encoding="utf-8"))
        content["tag"] = "f" * 64
        auth_file.write_text(json.dumps(content), encoding="utf-8")
    elif mutation == "malformed":
        auth_file.write_text("[]", encoding="utf-8")
    elif mutation == "missing-auth":
        auth_file.unlink()

    target = _runtime(tmp_path / "destino que debe permanecer", "estado-anterior")
    docker_log = tmp_path / "docker-no-debe-ejecutarse.log"
    docker_stub, _ = _docker_stub(tmp_path / "docker-stub-dir")
    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "BACKUP_ENCRYPTION_KEY_FILE": str(verification_key),
            "RUNTIME_TARGET_DIR": str(target),
            "DOCKER_BIN": str(docker_stub),
            "DOCKER_LOG": str(docker_log),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode in {65, 66}
    assert not docker_log.exists()
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "estado-anterior"


def test_authenticated_plain_runtime_restore_uses_only_staged_copy_after_verify(
    tmp_path: Path,
) -> None:
    archive, _, _, environment = _authenticated_plain_runtime(tmp_path)
    original_size = archive.stat().st_size
    target = _runtime(tmp_path / "stable-target", "estado-anterior")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_sha = fake_bin / "sha256sum"
    fake_sha.write_text(
        f"#!{sys.executable}\n"
        "import hashlib, os, pathlib, sys\n"
        "with open(os.environ['MUTATE_SOURCE'], 'ab') as stream:\n"
        "    stream.write(b'-cambio-posterior-a-auth')\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "print(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')\n",
        encoding="utf-8",
    )
    fake_sha.chmod(0o700)
    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "RUNTIME_TARGET_DIR": str(target),
            "MUTATE_SOURCE": str(archive),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert archive.stat().st_size > original_size
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "snapshot-autenticado"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_encrypted_runtime_restore_uses_staged_key_after_authentication(
    tmp_path: Path,
) -> None:
    archive, key_file, environment = _runtime_backup(tmp_path)
    target = _runtime(tmp_path / "stable-key-target", "estado-anterior")
    fake_bin = tmp_path / "fake-key-bin"
    fake_bin.mkdir()
    fake_sha = fake_bin / "sha256sum"
    fake_sha.write_text(
        f"#!{sys.executable}\n"
        "import hashlib, os, pathlib, sys\n"
        "pathlib.Path(os.environ['MUTATE_KEY']).write_text(\n"
        "    'clave-reemplazada-despues-de-auth', encoding='utf-8'\n"
        ")\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "print(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')\n",
        encoding="utf-8",
    )
    fake_sha.chmod(0o700)
    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "RUNTIME_TARGET_DIR": str(target),
            "MUTATE_KEY": str(key_file),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert key_file.read_text(encoding="utf-8") == (
        "clave-reemplazada-despues-de-auth"
    )
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "respaldo-nuevo"


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="O_NOFOLLOW no disponible")
@pytest.mark.parametrize("linked_input", ("artifact", "metadata", "auth"))
def test_runtime_restore_rejects_symlink_before_docker(
    tmp_path: Path, linked_input: str
) -> None:
    archive, metadata, auth_file, environment = _authenticated_plain_runtime(tmp_path)
    selected = {"artifact": archive, "metadata": metadata, "auth": auth_file}[
        linked_input
    ]
    regular = selected.with_name(selected.name + ".regular")
    selected.replace(regular)
    selected.symlink_to(regular)
    target = _runtime(tmp_path / "symlink-target", "intacto")
    docker_stub, docker_log = _docker_stub(tmp_path / "symlink-docker")
    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "RUNTIME_TARGET_DIR": str(target),
            "DOCKER_BIN": str(docker_stub),
            "DOCKER_LOG": str(docker_log),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 65, result.stderr
    assert not docker_log.exists()
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "intacto"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_production_runtime_restore_rejects_legacy_bypass_even_with_both_opt_ins(
    tmp_path: Path,
) -> None:
    archive, _, environment = _runtime_backup(tmp_path)
    Path(str(archive) + ".auth.json").unlink()
    docker, log = _docker_stub(tmp_path / "production-legacy-docker")
    result = subprocess.run(
        [
            "sh",
            str(SCRIPTS / "restore-runtime.sh"),
            str(archive),
            "--confirm",
            "--allow-legacy-unauthenticated",
        ],
        env={
            **environment,
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE": "true",
            "RUNTIME_TARGET_DIR": "",
            "DOCKER_BIN": str(docker),
            "DOCKER_LOG": str(log),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode in {65, 66}
    assert not log.exists()


@pytest.mark.parametrize(
    ("environment_opt_in", "cli_opt_in", "expected_success"),
    ((False, False, False), (True, False, False), (False, True, False), (True, True, True)),
)
def test_evaluation_legacy_runtime_restore_requires_double_opt_in(
    tmp_path: Path,
    environment_opt_in: bool,
    cli_opt_in: bool,
    expected_success: bool,
) -> None:
    source = _runtime(tmp_path / "legacy-source", "legacy-snapshot")
    archive = tmp_path / "legacy runtime with spaces.tar.gz"
    _runtime_archive(source, archive)
    target = _runtime(tmp_path / "legacy-target", "antes")
    environment = {
        **os.environ,
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
        "BACKUP_ENCRYPTION_KEY_FILE": "",
        "RUNTIME_TARGET_DIR": str(target),
    }
    if environment_opt_in:
        environment["BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE"] = "true"
    command = [
        "sh", str(SCRIPTS / "restore-runtime.sh"), str(archive), "--confirm",
    ]
    if cli_opt_in:
        command.append("--allow-legacy-unauthenticated")
    result = subprocess.run(command, env=environment, capture_output=True, text=True)
    assert (result.returncode == 0) is expected_success, result.stderr
    marker = (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8")
    assert marker == ("legacy-snapshot" if expected_success else "antes")


def test_evaluation_legacy_runtime_uses_staged_copy_after_checksum(
    tmp_path: Path,
) -> None:
    source = _runtime(tmp_path / "legacy-race-source", "legacy-estable")
    archive = tmp_path / "legacy-race.tar.gz"
    _runtime_archive(source, archive)
    original_size = archive.stat().st_size
    target = _runtime(tmp_path / "legacy-race-target", "antes")
    fake_bin = tmp_path / "legacy-fake-bin"
    fake_bin.mkdir()
    fake_sha = fake_bin / "sha256sum"
    fake_sha.write_text(
        f"#!{sys.executable}\n"
        "import hashlib, os, pathlib, sys\n"
        "with open(os.environ['MUTATE_SOURCE'], 'ab') as stream:\n"
        "    stream.write(b'-swap-legacy-posterior')\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "print(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')\n",
        encoding="utf-8",
    )
    fake_sha.chmod(0o700)
    result = subprocess.run(
        [
            "sh",
            str(SCRIPTS / "restore-runtime.sh"),
            str(archive),
            "--confirm",
            "--allow-legacy-unauthenticated",
        ],
        env={
            **os.environ,
            "ONPREM_DEPLOYMENT_MODE": "evaluation",
            "BACKUP_ENCRYPTION_REQUIRED": "false",
            "BACKUP_AUTHENTICATION_REQUIRED": "false",
            "BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": "",
            "RUNTIME_TARGET_DIR": str(target),
            "MUTATE_SOURCE": str(archive),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert archive.stat().st_size > original_size
    assert (
        target / "documents" / "synthetic-document" / "content.bin"
    ).read_text(encoding="utf-8") == "legacy-estable"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_postgres_backup_writes_authenticated_envelope_and_exact_metadata(
    tmp_path: Path,
) -> None:
    archive, key_file, _, _ = _postgres_backup(tmp_path)
    metadata_file = Path(str(archive) + ".meta.json")
    auth_file = Path(str(archive) + ".auth.json")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata == {
        "created_at": metadata["created_at"],
        "encrypted": True,
        "rpo_hours": 24,
        "rto_hours": 8,
        "retention_days": 30,
        "format": "postgres-custom",
        "envelope_version": 2,
        "authentication": "hmac-sha256",
    }
    assert auth_file.is_file()
    result = _auth_cli(
        "verify",
        artifact=archive,
        metadata=metadata_file,
        key_file=key_file,
        auth_file=auth_file,
        payload_kind="postgres-custom",
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_postgres_backup_uses_one_captured_key_for_encrypt_sign_and_restore(
    tmp_path: Path,
) -> None:
    docker, log = _docker_stub(tmp_path / "postgres-key-race-docker")
    backup_dir = tmp_path / "postgres-key-race-backups"
    mutable_key = _key(
        tmp_path / "postgres-key-race.key", "clave-postgres-capturada-2026",
    )
    verification_key = _key(
        tmp_path / "postgres-key-verification.key", "clave-postgres-capturada-2026",
    )
    fake_bin = tmp_path / "postgres-key-race-bin"
    fake_bin.mkdir()
    fake_sha = fake_bin / "sha256sum"
    fake_sha.write_text(
        f"#!{sys.executable}\n"
        "import hashlib, os, pathlib, sys\n"
        "pathlib.Path(os.environ['MUTATE_KEY']).write_text(\n"
        "    'clave-postgres-rotada-2026', encoding='utf-8'\n"
        ")\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "print(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')\n",
        encoding="utf-8",
    )
    fake_sha.chmod(0o700)
    backup_environment = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "production",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_AUTHENTICATION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(mutable_key),
        "MUTATE_KEY": str(mutable_key),
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
    }
    created = subprocess.run(
        ["sh", str(SCRIPTS / "backup.sh")],
        env=backup_environment,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    assert mutable_key.read_text(encoding="utf-8") == "clave-postgres-rotada-2026"
    archives = list(backup_dir.glob("*.dump.enc"))
    assert len(archives) == 1

    log.unlink(missing_ok=True)
    restored = subprocess.run(
        ["sh", str(SCRIPTS / "restore.sh"), str(archives[0]), "--confirm"],
        env={
            **os.environ,
            "DOCKER_BIN": str(docker),
            "DOCKER_LOG": str(log),
            "BACKUP_DIR": str(backup_dir),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(verification_key),
        },
        capture_output=True,
        text=True,
    )
    assert restored.returncode == 0, restored.stderr
    assert "Restauración verificada" in restored.stdout


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
@pytest.mark.parametrize(
    "mutation", ("artifact", "metadata", "auth", "wrong-key", "missing-auth")
)
def test_postgres_restore_rejects_auth_failure_before_docker(
    tmp_path: Path,
    mutation: str,
) -> None:
    archive, key_file, environment, log = _postgres_backup(tmp_path)
    metadata = Path(str(archive) + ".meta.json")
    auth_file = Path(str(archive) + ".auth.json")
    verification_key = key_file
    if mutation == "artifact":
        archive.write_bytes(archive.read_bytes() + b"alterado")
        _write_checksum(archive)
    elif mutation == "metadata":
        content = json.loads(metadata.read_text(encoding="utf-8"))
        content["rto_hours"] = 7
        metadata.write_text(json.dumps(content), encoding="utf-8")
        _write_checksum(metadata)
    elif mutation == "auth":
        content = json.loads(auth_file.read_text(encoding="utf-8"))
        content["tag"] = "a" * 64
        auth_file.write_text(json.dumps(content), encoding="utf-8")
    elif mutation == "wrong-key":
        verification_key = _key(tmp_path / "wrong-pg.key", "clave-postgres-incorrecta")
    elif mutation == "missing-auth":
        auth_file.unlink()

    log.unlink(missing_ok=True)
    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore.sh"), str(archive), "--confirm"],
        env={**environment, "BACKUP_ENCRYPTION_KEY_FILE": str(verification_key)},
        capture_output=True,
        text=True,
    )
    assert result.returncode in {65, 66}
    assert not log.exists(), "La autenticación debe fallar antes de cualquier llamada Docker"


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_postgres_restore_reports_restart_failure_instead_of_success(
    tmp_path: Path,
) -> None:
    archive, key_file, environment, log = _postgres_backup(tmp_path)
    log.unlink(missing_ok=True)

    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore.sh"), str(archive), "--confirm"],
        env={
            **environment,
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
            "DOCKER_FAIL_START_APP": "true",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Restauración verificada" not in result.stdout
    assert "no se pudieron reiniciar" in result.stderr
    assert "start app" in log.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_postgres_restore_resolves_relative_tmpdir_and_pre_restore_directory(
    tmp_path: Path,
) -> None:
    archive, key_file, environment, log = _postgres_backup(tmp_path)
    log.unlink(missing_ok=True)
    relative_tmp = tmp_path / "relative-tmp"
    relative_tmp.mkdir(mode=0o700)
    relative_backups_name = f"relative-pre-backups-{tmp_path.name}"

    result = subprocess.run(
        ["sh", str(SCRIPTS / "restore.sh"), str(archive), "--confirm"],
        cwd=tmp_path,
        env={
            **environment,
            "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
            "BACKUP_DIR": relative_backups_name,
            "TMPDIR": relative_tmp.name,
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    pre_restore = tmp_path / relative_backups_name / "pre-restore"
    assert len(list(pre_restore.glob("*.dump.enc"))) == 1
    assert list(relative_tmp.iterdir()) == []
    assert not (ONPREM / relative_backups_name).exists()


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible")
def test_production_postgres_restore_rejects_legacy_bypass_with_both_opt_ins(
    tmp_path: Path,
) -> None:
    archive, _, environment, log = _postgres_backup(tmp_path)
    Path(str(archive) + ".auth.json").unlink()
    log.unlink(missing_ok=True)
    result = subprocess.run(
        [
            "sh",
            str(SCRIPTS / "restore.sh"),
            str(archive),
            "--confirm",
            "--allow-legacy-unauthenticated",
        ],
        env={
            **environment,
            "BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE": "true",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode in {65, 66, 78}
    assert not log.exists()


@pytest.mark.parametrize(
    ("environment_opt_in", "cli_opt_in", "expected_success"),
    ((False, False, False), (True, False, False), (False, True, False), (True, True, True)),
)
def test_evaluation_legacy_postgres_restore_requires_double_opt_in(
    tmp_path: Path,
    environment_opt_in: bool,
    cli_opt_in: bool,
    expected_success: bool,
) -> None:
    docker, log = _docker_stub(tmp_path)
    archive = tmp_path / "legacy postgres con espacios.dump"
    archive.write_bytes(b"dump-postgres-sintetico")
    _write_checksum(archive)
    environment = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "BACKUP_DIR": str(tmp_path / "pre-restore"),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
        "BACKUP_AUTHENTICATION_REQUIRED": "false",
        "BACKUP_ENCRYPTION_KEY_FILE": "",
    }
    if environment_opt_in:
        environment["BACKUP_ALLOW_LEGACY_UNAUTHENTICATED_RESTORE"] = "true"
    command = ["sh", str(SCRIPTS / "restore.sh"), str(archive), "--confirm"]
    if cli_opt_in:
        command.append("--allow-legacy-unauthenticated")
    result = subprocess.run(command, env=environment, capture_output=True, text=True)
    assert (result.returncode == 0) is expected_success, result.stderr
    assert log.exists() is expected_success
