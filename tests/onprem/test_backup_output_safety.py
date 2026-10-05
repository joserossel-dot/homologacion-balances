"""Seguridad de publicación para bundles de backup on-premise.

Los casos son sintéticos y verifican que un directorio o nombre preparado por
terceros no permita reemplazar archivos, y que los fallos no dejen parciales.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
ONPREM = ROOT / "deployment" / "onprem"
SCRIPTS = ONPREM / "scripts"
FIXED_TIMESTAMP = "20260927T120000Z"


def _runtime(root: Path) -> Path:
    (root / "knowledge").mkdir(parents=True)
    (root / "operational").mkdir()
    (root / "documents" / "synthetic").mkdir(parents=True)
    (root / "knowledge" / "catalogo_maestro.json").write_text(
        json.dumps({"AC.01": {"nombre_estandar": "Cuenta sintética"}}),
        encoding="utf-8",
    )
    (root / "knowledge" / "diccionario.json").write_text("[]", encoding="utf-8")
    (root / "documents" / "synthetic" / "content.bin").write_bytes(b"contenido")
    with sqlite3.connect(root / "operational" / "operations.db") as connection:
        connection.execute("CREATE TABLE marker(value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES ('sintetico')")
    return root


def _docker_stub(tmp_path: Path) -> Path:
    executable = tmp_path / "docker-stub"
    executable.write_text(
        "#!/bin/sh\n"
        "if [ \"${DOCKER_FAIL:-false}\" = true ]; then exit 42; fi\n"
        "printf 'postgres-custom-sintetico'\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _context(
    tmp_path: Path,
    script_name: str,
) -> tuple[Path, dict[str, str], str, str]:
    backup_dir = tmp_path / "backups"
    python_dir = str(Path(sys.executable).resolve().parent)
    environment = {
        **os.environ,
        "PATH": f"{python_dir}:{os.environ.get('PATH', '')}",
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
        "BACKUP_AUTHENTICATION_REQUIRED": "false",
        "BACKUP_ENCRYPTION_KEY_FILE": "",
        "BACKUP_RETENTION_DAYS": "30",
        "BACKUP_RPO_HOURS": "24",
        "BACKUP_RTO_HOURS": "8",
    }
    if script_name == "backup-runtime.sh":
        environment["RUNTIME_SOURCE_DIR"] = str(_runtime(tmp_path / "runtime"))
        return backup_dir, environment, "homologacion-app-runtime-", ".tar.gz"
    environment["DOCKER_BIN"] = str(_docker_stub(tmp_path))
    return backup_dir, environment, "homologacion-", ".dump"


def _run(script_name: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SCRIPTS / script_name)],
        env=environment,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_backup_rejects_symlink_as_destination_directory(
    tmp_path: Path,
    script_name: str,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, script_name)
    real_directory = tmp_path / "real-backups"
    real_directory.mkdir(mode=0o700)
    backup_dir.symlink_to(real_directory, target_is_directory=True)

    result = _run(script_name, environment)

    assert result.returncode == 78
    assert "enlace simbólico" in result.stderr
    assert list(real_directory.iterdir()) == []


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_backup_rejects_group_or_world_writable_destination(
    tmp_path: Path,
    script_name: str,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, script_name)
    backup_dir.mkdir(mode=0o700)
    backup_dir.chmod(0o777)

    result = _run(script_name, environment)

    assert result.returncode == 78
    assert "escritura a grupo u otros" in result.stderr
    assert list(backup_dir.iterdir()) == []


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_relative_backup_directory_is_resolved_before_compose_changes_directory(
    tmp_path: Path,
    script_name: str,
) -> None:
    _, environment, _, suffix = _context(tmp_path, script_name)
    environment["BACKUP_DIR"] = "relative backups"

    result = subprocess.run(
        ["sh", str(SCRIPTS / script_name)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    backup_dir = tmp_path / "relative backups"
    assert len(list(backup_dir.glob(f"*{suffix}"))) == 1
    assert not (ONPREM / "relative backups").exists()


def test_postgres_backup_captures_relative_key_before_compose_directory_change(
    tmp_path: Path,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, "backup.sh")
    key = tmp_path / "relative-backup.key"
    key.write_text("clave-relativa-segura-2026", encoding="utf-8")
    key.chmod(0o600)
    environment.update(
        {
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": key.name,
        }
    )

    result = subprocess.run(
        ["sh", str(SCRIPTS / "backup.sh")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert len(list(backup_dir.glob("*.dump.enc"))) == 1
    assert len(list(backup_dir.glob("*.dump.enc.auth.json"))) == 1


def test_postgres_backup_never_stages_captured_key_under_backup_directory(
    tmp_path: Path,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, "backup.sh")
    key = tmp_path / "outside-backup.key"
    key.write_text("clave-fuera-del-storage-2026", encoding="utf-8")
    key.chmod(0o600)
    observed = tmp_path / "observed-key-location"
    docker = tmp_path / "docker-inspects-key"
    docker.write_text(
        "#!/bin/sh\n"
        "if find \"$BACKUP_DIR\" -name .backup.key -o -name backup.key | "
        "grep -q .; then printf 'inside-backup' > \"$OBSERVED_KEY\"; fi\n"
        "printf 'postgres-custom-sintetico'\n",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    environment.update(
        {
            "DOCKER_BIN": str(docker),
            "OBSERVED_KEY": str(observed),
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key),
        }
    )

    result = _run("backup.sh", environment)

    assert result.returncode == 0, result.stderr
    assert not observed.exists()
    assert not any(path.name == "backup.key" for path in backup_dir.rglob("*"))


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_backup_with_relative_tmpdir_cleans_absolute_private_workdir(
    tmp_path: Path,
    script_name: str,
) -> None:
    backup_dir, environment, _, suffix = _context(tmp_path, script_name)
    relative_tmp = tmp_path / "relative-tmp"
    relative_tmp.mkdir(mode=0o700)
    key = tmp_path / "relative-tmp.key"
    key.write_text("clave-tmp-relativa-segura-2026", encoding="utf-8")
    key.chmod(0o600)
    environment.update(
        {
            "ONPREM_DEPLOYMENT_MODE": "evaluation",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key),
            "TMPDIR": relative_tmp.name,
        }
    )

    result = subprocess.run(
        ["sh", str(SCRIPTS / script_name)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert len(list(backup_dir.glob(f"*{suffix}.enc"))) == 1
    assert list(relative_tmp.iterdir()) == []


def _blocking_date(tmp_path: Path, environment: dict[str, str]) -> tuple[Path, Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    ready = tmp_path / "date-ready"
    release = tmp_path / "date-release"
    date = fake_bin / "date"
    date.write_text(
        "#!/bin/sh\n"
        ": > \"$DATE_READY\"\n"
        "while [ ! -e \"$DATE_RELEASE\" ]; do /bin/sleep 0.01; done\n"
        f"printf '%s\\n' '{FIXED_TIMESTAMP}'\n",
        encoding="utf-8",
    )
    date.chmod(0o700)
    environment["DATE_READY"] = str(ready)
    environment["DATE_RELEASE"] = str(release)
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    return ready, release


def _wait_for(path: Path, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 5
    while not path.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"El proceso terminó antes del checkpoint: {stdout=} {stderr=}"
            )
        time.sleep(0.01)
    assert path.exists(), "El date sintético no alcanzó el checkpoint"


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
@pytest.mark.parametrize("collision_kind", ("symlink-primary", "regular-sidecar"))
def test_backup_does_not_clobber_preexisting_bundle_members(
    tmp_path: Path,
    script_name: str,
    collision_kind: str,
) -> None:
    backup_dir, environment, prefix, suffix = _context(tmp_path, script_name)
    backup_dir.mkdir(mode=0o700)
    ready, release = _blocking_date(tmp_path, environment)
    process = subprocess.Popen(
        ["sh", str(SCRIPTS / script_name)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for(ready, process)
        primary = backup_dir / f"{prefix}{FIXED_TIMESTAMP}-{process.pid}{suffix}"
        victim = tmp_path / "victim"
        victim.write_text("no reemplazar", encoding="utf-8")
        if collision_kind == "symlink-primary":
            primary.symlink_to(victim)
            collision = primary
        else:
            collision = Path(str(primary) + ".meta.json")
            collision.write_text("sidecar previo", encoding="utf-8")
        release.touch()
        stdout, stderr = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 73, (stdout, stderr)
    assert "Colisión" in stderr
    assert victim.read_text(encoding="utf-8") == "no reemplazar"
    if collision_kind == "symlink-primary":
        assert collision.is_symlink()
    else:
        assert collision.read_text(encoding="utf-8") == "sidecar previo"
    assert not Path(str(primary) + ".sha256").exists()
    assert not Path(str(primary) + ".meta.json.sha256").exists()
    assert not any(path.name.startswith(".homologacion-") for path in backup_dir.iterdir())


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_published_bundle_is_private_regular_and_complete(
    tmp_path: Path,
    script_name: str,
) -> None:
    backup_dir, environment, _, suffix = _context(tmp_path, script_name)
    key = tmp_path / "backup.key"
    key.write_text("clave-sintetica-segura-2026", encoding="utf-8")
    key.chmod(0o600)
    environment.update(
        {
            "ONPREM_DEPLOYMENT_MODE": (
                "evaluation" if script_name == "backup-runtime.sh" else "production"
            ),
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key),
        }
    )

    result = _run(script_name, environment)

    assert result.returncode == 0, result.stderr
    encrypted_suffix = f"{suffix}.enc"
    artifacts = sorted(backup_dir.iterdir())
    primary = next(path for path in artifacts if path.name.endswith(encrypted_suffix))
    expected = {
        primary.name,
        f"{primary.name}.sha256",
        f"{primary.name}.meta.json",
        f"{primary.name}.meta.json.sha256",
        f"{primary.name}.auth.json",
    }
    assert {path.name for path in artifacts} == expected
    assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
    for path in artifacts:
        info = path.lstat()
        assert stat.S_ISREG(info.st_mode)
        assert stat.S_IMODE(info.st_mode) == 0o600
    metadata = json.loads(Path(str(primary) + ".meta.json").read_text(encoding="utf-8"))
    assert isinstance(metadata["rpo_hours"], int)
    assert isinstance(metadata["rto_hours"], int)
    assert ".homologacion-" not in Path(str(primary) + ".sha256").read_text()
    assert ".homologacion-" not in Path(
        str(primary) + ".meta.json.sha256"
    ).read_text()


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
@pytest.mark.parametrize(
    ("variable", "value"),
    (
        ("BACKUP_RPO_HOURS", "1:2"),
        ("BACKUP_RPO_HOURS", "12.5"),
        ("BACKUP_RPO_HOURS", "08"),
        ("BACKUP_RTO_HOURS", "ocho"),
        ("BACKUP_RTO_HOURS", "-1"),
        ("BACKUP_RTO_HOURS", "004"),
        ("BACKUP_RETENTION_DAYS", "030"),
    ),
)
def test_backup_rejects_noncanonical_numeric_metadata_before_output(
    tmp_path: Path,
    script_name: str,
    variable: str,
    value: str,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, script_name)
    environment[variable] = value

    result = _run(script_name, environment)

    assert result.returncode == 78
    assert variable in result.stderr
    assert not backup_dir.exists()


@pytest.mark.parametrize("script_name", ("backup-runtime.sh", "backup.sh"))
def test_failed_backup_removes_private_staging_and_partial_outputs(
    tmp_path: Path,
    script_name: str,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, script_name)
    if script_name == "backup-runtime.sh":
        invalid_runtime = tmp_path / "invalid-runtime"
        invalid_runtime.mkdir()
        environment["RUNTIME_SOURCE_DIR"] = str(invalid_runtime)
    else:
        environment["DOCKER_FAIL"] = "true"

    result = _run(script_name, environment)

    assert result.returncode != 0
    assert backup_dir.is_dir()
    assert list(backup_dir.iterdir()) == []


def test_postgres_retention_only_deletes_old_top_level_postgres_bundle_members(
    tmp_path: Path,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, "backup.sh")
    backup_dir.mkdir(mode=0o700)
    environment["BACKUP_RETENTION_DAYS"] = "1"
    pg_primary = "homologacion-20200101T000000Z-101.dump.enc"
    old_postgres = {
        pg_primary,
        f"{pg_primary}.sha256",
        f"{pg_primary}.meta.json",
        f"{pg_primary}.meta.json.sha256",
        f"{pg_primary}.auth.json",
    }
    runtime_primary = "homologacion-app-runtime-20200101T000000Z-202.tar.gz.enc"
    preserved = {
        runtime_primary,
        f"{runtime_primary}.sha256",
        f"{runtime_primary}.meta.json",
        f"{runtime_primary}.meta.json.sha256",
        f"{runtime_primary}.auth.json",
        "foreign.sha256",
        "homologacion-not-a-timestamp.dump",
        "homologacion-20200101T000000Z-not-a-pid.dump.auth.json",
    }
    old_time = time.time() - 3 * 86400
    for name in old_postgres | preserved:
        path = backup_dir / name
        path.write_text("old", encoding="utf-8")
        os.utime(path, (old_time, old_time))
    nested = backup_dir / "nested"
    nested.mkdir()
    nested_member = nested / "homologacion-20200101T000000Z-303.dump"
    nested_member.write_text("nested-old", encoding="utf-8")
    os.utime(nested_member, (old_time, old_time))

    result = _run("backup.sh", environment)

    assert result.returncode == 0, result.stderr
    assert all(not (backup_dir / name).exists() for name in old_postgres)
    assert all((backup_dir / name).is_file() for name in preserved)
    assert nested_member.read_text(encoding="utf-8") == "nested-old"
    new_primary = [
        path
        for path in backup_dir.glob("homologacion-*.dump")
        if path.name not in old_postgres | preserved
    ]
    assert len(new_primary) == 1


def test_runtime_retention_only_deletes_old_top_level_runtime_bundle_members(
    tmp_path: Path,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, "backup-runtime.sh")
    backup_dir.mkdir(mode=0o700)
    environment["BACKUP_RETENTION_DAYS"] = "1"
    runtime_primary = "homologacion-app-runtime-20200101T000000Z-202.tar.gz.enc"
    old_runtime = {
        runtime_primary,
        f"{runtime_primary}.sha256",
        f"{runtime_primary}.meta.json",
        f"{runtime_primary}.meta.json.sha256",
        f"{runtime_primary}.auth.json",
    }
    postgres_primary = "homologacion-20200101T000000Z-101.dump.enc"
    preserved = {
        postgres_primary,
        f"{postgres_primary}.sha256",
        f"{runtime_primary}.evidence",
        "homologacion-app-runtime-not-a-timestamp.tar.gz",
        "homologacion-app-runtime-20200101T000000Z-not-a-pid.tar.gz.auth.json",
    }
    old_time = time.time() - 3 * 86400
    for name in old_runtime | preserved:
        path = backup_dir / name
        path.write_text("old", encoding="utf-8")
        os.utime(path, (old_time, old_time))
    nested = backup_dir / "nested"
    nested.mkdir()
    nested_member = nested / "homologacion-app-runtime-20200101T000000Z-303.tar.gz"
    nested_member.write_text("nested-old", encoding="utf-8")
    os.utime(nested_member, (old_time, old_time))

    result = _run("backup-runtime.sh", environment)

    assert result.returncode == 0, result.stderr
    assert all(not (backup_dir / name).exists() for name in old_runtime)
    assert all((backup_dir / name).is_file() for name in preserved)
    assert nested_member.read_text(encoding="utf-8") == "nested-old"
    new_primary = [
        path
        for path in backup_dir.glob("homologacion-app-runtime-*.tar.gz")
        if path.name not in old_runtime | preserved
    ]
    assert len(new_primary) == 1


def test_postgres_signal_after_publication_does_not_truncate_published_hardlinks(
    tmp_path: Path,
) -> None:
    backup_dir, environment, _, _ = _context(tmp_path, "backup.sh")
    key = tmp_path / "signal.key"
    key.write_text("clave-para-senal-segura-2026", encoding="utf-8")
    key.chmod(0o600)
    fake_bin = tmp_path / "python-wrapper-bin"
    fake_bin.mkdir()
    call_count = tmp_path / "python-call-count"
    wrapper = fake_bin / "python3"
    wrapper.write_text(
        "#!/bin/sh\n"
        "count=0\n"
        "[ ! -f \"$PYTHON_CALL_COUNT\" ] || count=$(cat \"$PYTHON_CALL_COUNT\")\n"
        "count=$((count + 1))\n"
        "printf '%s' \"$count\" > \"$PYTHON_CALL_COUNT\"\n"
        "if [ \"$count\" -eq 5 ]; then kill -TERM \"$PPID\"; exit 143; fi\n"
        "exec \"$REAL_PYTHON\" \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o700)
    environment.update(
        {
            "ONPREM_DEPLOYMENT_MODE": "production",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            "BACKUP_AUTHENTICATION_REQUIRED": "true",
            "BACKUP_ENCRYPTION_KEY_FILE": str(key),
            "PYTHON_CALL_COUNT": str(call_count),
            "REAL_PYTHON": sys.executable,
            "PATH": f"{fake_bin}:{environment['PATH']}",
        }
    )

    result = _run("backup.sh", environment)

    assert result.returncode != 0
    assert call_count.read_text(encoding="utf-8") == "5"
    primaries = list(backup_dir.glob("*.dump.enc"))
    assert len(primaries) == 1
    primary = primaries[0]
    members = (
        primary,
        Path(str(primary) + ".sha256"),
        Path(str(primary) + ".meta.json"),
        Path(str(primary) + ".meta.json.sha256"),
        Path(str(primary) + ".auth.json"),
    )
    assert all(path.stat().st_size > 0 for path in members)
