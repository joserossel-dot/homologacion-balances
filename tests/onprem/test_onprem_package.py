from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ONPREM = ROOT / "deployment" / "onprem"
COMPOSE = ONPREM / "docker-compose.yml"
COMPOSE_EVALUATION = ONPREM / "docker-compose.evaluation.yml"


def _compose_config(*, legacy_postgres: bool = False) -> dict:
    docker = shutil.which("docker")
    assert docker, "Docker CLI requerido para validar el contrato Compose"
    command = [
            docker,
            "compose",
            "--project-directory",
            str(ONPREM),
            "-f",
            str(COMPOSE),
            "-f",
            str(COMPOSE_EVALUATION),
            "--env-file",
            str(ONPREM / ".env.example"),
    ]
    if legacy_postgres:
        command.extend(["--profile", "legacy-postgres"])
    command.extend([
            "config",
            "--format",
            "json",
    ])
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _production_compose_config() -> dict:
    docker = shutil.which("docker")
    assert docker
    digest = "registry.local/component@sha256:" + "a" * 64
    result = subprocess.run(
        [
            docker, "compose", "--project-directory", str(ONPREM),
            "-f", str(COMPOSE), "config", "--format", "json",
        ],
        check=True, capture_output=True, text=True,
        env={
            **os.environ,
            "APP_IMAGE_REFERENCE": digest,
            "POSTGRES_IMAGE": digest,
            "CADDY_IMAGE": digest,
            "CADDY_INIT_IMAGE": digest,
            "ONPREM_DEPLOYMENT_MODE": "production",
            "AUTH_ENFORCEMENT": "forward_auth",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
        },
    )
    return json.loads(result.stdout)


def test_compose_has_expected_services_and_healthchecks() -> None:
    config = _compose_config()
    services = config["services"]
    assert set(services) == {
        "app", "app-volume-init", "bootstrap", "caddy-volume-init",
        "reverse-proxy",
    }
    assert services["app"].get("healthcheck")
    assert services["app"]["depends_on"]["bootstrap"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["bootstrap"]["depends_on"]["app-volume-init"]["condition"] == (
        "service_completed_successfully"
    )


def test_database_is_internal_and_has_no_published_ports() -> None:
    config = _compose_config(legacy_postgres=True)
    db = config["services"]["db"]
    assert not db.get("ports")
    assert set(db["networks"]) == {"data"}
    assert config["networks"]["data"]["internal"] is True
    assert set(config["services"]["reverse-proxy"]["networks"]) == {
        "edge", "frontend",
    }
    assert config["networks"]["frontend"]["internal"] is True
    services = config["services"]
    assert services["db"]["profiles"] == ["legacy-postgres"]
    assert services["bootstrap"]["network_mode"] == "none"
    assert set(services["app"]["networks"]) == {"frontend"}


def test_security_defaults_are_enabled() -> None:
    config = _compose_config()
    services = config["services"]
    assert services["app"]["environment"]["QUALITY_CONTROL_ENFORCE_EXPORT"] == "true"
    assert services["app"]["environment"]["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] == "true"
    assert services["app"]["environment"]["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] == "50"
    assert services["reverse-proxy"]["user"] == "10001:10001"
    assert services["reverse-proxy"]["read_only"] is True
    assert services["bootstrap"]["read_only"] is True
    assert services["app"]["read_only"] is True
    assert services["app"]["environment"]["ONPREM_JSON_FALLBACK"] == "disabled"
    assert services["app"]["environment"]["PERSISTENCE_MODE"] == "local"
    assert "DATABASE_URL" not in services["app"]["environment"]
    assert "DATABASE_URL" not in services["bootstrap"]["environment"]
    assert not services["app"].get("secrets")
    assert not services["bootstrap"].get("secrets")
    assert services["app"]["environment"]["LOCAL_PERSISTENCE_ROOT"] == (
        "/var/lib/homologacion/runtime"
    )
    assert services["bootstrap"]["environment"]["PERSISTENCE_MODE"] == "local"
    assert services["app-volume-init"]["user"] == "0:0"
    assert services["app-volume-init"]["read_only"] is True
    caddy_init_command = services["caddy-volume-init"]["command"]
    assert "/data/caddy" in caddy_init_command[-1]
    assert "/config/caddy" in caddy_init_command[-1]
    assert "chown -R 10001:10001 /data /config" in caddy_init_command[-1]
    assert services["app"]["user"] == "10001:10001"
    assert all(
        "no-new-privileges:true" in services[name].get("security_opt", [])
        for name in ("app", "bootstrap", "reverse-proxy")
    )


def test_app_image_runs_as_non_root_and_contains_ocr_dependencies() -> None:
    dockerfile = (ONPREM / "Dockerfile").read_text(encoding="utf-8")
    assert "USER homologacion:homologacion" in dockerfile
    assert "tesseract-ocr-spa" in dockerfile
    assert "poppler-utils" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_secret_is_external_and_not_present_in_example_environment() -> None:
    config = _compose_config(legacy_postgres=True)
    secret = config["secrets"]["postgres_password"]
    assert secret["file"].endswith("secrets/postgres_password.txt")
    example = (ONPREM / ".env.example").read_text(encoding="utf-8")
    forbidden = ("DATABASE_URL=", "POSTGRES_PASSWORD=", "API_TOKEN=", "LICENSE_KEY=")
    assert not any(item in example for item in forbidden)


def test_bootstrap_uses_local_durable_bundle(monkeypatch, tmp_path) -> None:
    spec = importlib.util.spec_from_file_location(
        "onprem_bootstrap", ONPREM / "bootstrap.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("PERSISTENCE_MODE", "local")
    monkeypatch.setenv("LOCAL_PERSISTENCE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("LOCAL_CATALOG_SEED", str(ROOT / "catalogo_maestro.json"))
    monkeypatch.setenv("LOCAL_DICTIONARY_SEED", str(ROOT / "diccionario.json"))
    monkeypatch.setenv("LOCAL_MASTER_BUNDLE_VERSION", "test-bundle")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    module.main()
    assert (tmp_path / "runtime" / "knowledge" / "catalogo_maestro.json").is_file()
    assert (tmp_path / "runtime" / "knowledge" / "diccionario.json").is_file()
    assert (tmp_path / "runtime" / "operational" / "operations.db").is_file()


def test_entrypoint_fails_closed_outside_local_persistence() -> None:
    env = os.environ.copy()
    env["PERSISTENCE_MODE"] = "legacy_neon"
    env["LOCAL_PERSISTENCE_ROOT"] = "/var/lib/homologacion/runtime"
    env["ONPREM_DEPLOYMENT_MODE"] = "evaluation"
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(ONPREM / "preflight.py")],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "PERSISTENCE_MODE=local" in result.stderr


def test_restore_requires_explicit_confirmation(tmp_path) -> None:
    fake_backup = tmp_path / "backup.dump"
    fake_backup.write_bytes(b"not-a-real-dump")
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore.sh"), str(fake_backup)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 64
    assert "--confirm" in result.stderr


def test_restore_rejects_missing_or_invalid_checksum_before_docker(tmp_path) -> None:
    fake_backup = tmp_path / "backup.dump"
    fake_backup.write_bytes(b"dump")
    env = {
        **os.environ, "PATH": "/usr/bin:/bin",
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
    }
    missing = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore.sh"), str(fake_backup), "--confirm"],
        env=env, capture_output=True, text=True,
    )
    assert missing.returncode == 66
    fake_backup.with_suffix(".dump.sha256").write_text("0" * 64, encoding="utf-8")
    invalid = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore.sh"), str(fake_backup), "--confirm"],
        env=env, capture_output=True, text=True,
    )
    assert invalid.returncode == 65
    assert "Checksum no coincide" in invalid.stderr


def test_restore_enforces_maintenance_prebackup_and_staged_swap() -> None:
    source = (ONPREM / "scripts" / "restore.sh").read_text(encoding="utf-8")
    assert "compose stop app reverse-proxy" in source
    assert '"$script_dir/backup.sh"' in source
    assert "createdb" in source
    assert "--exit-on-error" in source
    assert "ALTER DATABASE" in source
    assert "Base anterior preservada" in source


def test_docker_context_excludes_sensitive_runtime_material() -> None:
    source = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for pattern in (
        "**/secrets/", "**/backups/", "**/*.dump", "**/*.sqlite",
        "**/*.db", "**/*.pem", "**/*.key", "**/*credentials*",
    ):
        assert pattern in source
    assert "!**/.env.example" in source
    assert "!migrations/**/*.sql" in source
    assert "!persistence/migrations/**/*.sql" in source
    assert "!persistence/local/migrations/**/*.sql" in source
    assert "**/__pycache__/" in source
    assert "**/*.py[cod]" in source


def test_production_authentication_is_default_deny() -> None:
    source = (ONPREM / "Caddyfile.production").read_text(encoding="utf-8")
    evaluation_source = (ONPREM / "Caddyfile").read_text(encoding="utf-8")
    assert source.count("bind 0.0.0.0") == 2
    assert evaluation_source.count("bind 0.0.0.0") == 2
    assert "forward_auth" in source
    assert "AUTH_GATEWAY_URL:http://127.0.0.1:1" in source
    assert "X-Authenticated-User" in source
    assert "request_header -X-Authenticated-User" in source
    config = _compose_config()
    assert config["services"]["reverse-proxy"]["volumes"][0]["source"].endswith(
        "Caddyfile"
    )  # .env.example declara explícitamente evaluación sin autenticación


def test_production_compose_has_no_local_build_and_uses_auth_config() -> None:
    config = _production_compose_config()
    assert "build" not in config["services"]["app"]
    assert "build" not in config["services"]["bootstrap"]
    assert set(config["services"]["reverse-proxy"]["networks"]) == {
        "edge", "frontend",
    }
    assert config["networks"]["frontend"]["internal"] is True
    assert config["networks"]["edge"].get("internal", False) is False
    assert set(config["services"]["app"]["networks"]) == {"frontend"}
    assert config["services"]["reverse-proxy"]["volumes"][0]["source"].endswith(
        "Caddyfile.production"
    )


def test_production_preflight_rejects_mutable_images_and_accepts_digests() -> None:
    spec = importlib.util.spec_from_file_location(
        "onprem_preflight", ONPREM / "preflight.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    local = {
        "PERSISTENCE_MODE": "local",
        "LOCAL_PERSISTENCE_ROOT": "/var/lib/homologacion/runtime",
        "ONPREM_JSON_FALLBACK": "disabled",
    }
    with pytest.raises(ValueError, match="digest"):
        module.validate({
            **local,
            "ONPREM_DEPLOYMENT_MODE": "production",
            "AUTH_ENFORCEMENT": "forward_auth",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            **{name: "vendor/image:latest" for name in module.IMAGE_VARIABLES},
        })
    immutable = "registry.local/image@sha256:" + "a" * 64
    module.validate({
        **local,
        "ONPREM_DEPLOYMENT_MODE": "production",
        "AUTH_ENFORCEMENT": "forward_auth",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        **{name: immutable for name in module.IMAGE_VARIABLES},
    })
    with pytest.raises(ValueError, match="CADDYFILE_PATH"):
        module.validate({
            **local,
            "ONPREM_DEPLOYMENT_MODE": "production",
            "AUTH_ENFORCEMENT": "forward_auth",
            "CADDYFILE_PATH": "./Caddyfile",
            "BACKUP_ENCRYPTION_REQUIRED": "true",
            **{name: immutable for name in module.IMAGE_VARIABLES},
        })


def test_preflight_rejects_neon_and_enables_all_local_ports(tmp_path) -> None:
    spec = importlib.util.spec_from_file_location(
        "onprem_preflight_local", ONPREM / "preflight.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = {
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "PERSISTENCE_MODE": "local",
        "LOCAL_PERSISTENCE_ROOT": str(tmp_path / "runtime"),
        "LOCAL_CATALOG_SEED": str(ROOT / "catalogo_maestro.json"),
        "LOCAL_DICTIONARY_SEED": str(ROOT / "diccionario.json"),
        "ONPREM_JSON_FALLBACK": "disabled",
    }
    module.validate(base)
    module.validate_runtime_persistence(base)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        module.validate({**base, "DATABASE_URL": "postgresql://remote.invalid/db"})
    with pytest.raises(ValueError, match="PERSISTENCE_MODE=local"):
        module.validate({**base, "PERSISTENCE_MODE": "legacy_neon"})


def test_persistence_probe_observes_durable_audit_and_promotions(
    monkeypatch, tmp_path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "onprem_persistence_probe", ONPREM / "persistence_probe.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("PERSISTENCE_MODE", "local")
    monkeypatch.setenv("LOCAL_PERSISTENCE_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("LOCAL_CATALOG_SEED", str(ROOT / "catalogo_maestro.json"))
    monkeypatch.setenv("LOCAL_DICTIONARY_SEED", str(ROOT / "diccionario.json"))
    first = module.inspect(write_marker=True)
    second = module.inspect()
    assert first["mode"] == "local"
    assert first["operational_enabled"] is True
    assert all(first["repositories"].values())
    assert second["audit_markers"] == 1


def test_master_seed_history_has_formal_migration() -> None:
    migration = ROOT / "persistence" / "migrations" / "002_master_seed_history.sql"
    source = migration.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS master_seed_history" in source
    assert "bundle_checksum TEXT PRIMARY KEY" in source


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "docker-fake"
    log = tmp_path / "docker.log"
    executable.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  *"ps --services"*) printf 'app\\nreverse-proxy\\n' ;;
  *"pg_dump"*) printf 'pre-restore-dump' ;;
  *"pg_restore"*) [ "${FAIL_STAGE:-}" != pg_restore ] || exit 42 ;;
esac
""",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable, log


def _write_checksum(path: Path) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(
        f"{digest}  {path}\n", encoding="utf-8",
    )


def test_restore_simulation_runs_maintenance_prebackup_and_atomic_swap(tmp_path) -> None:
    docker, log = _fake_docker(tmp_path)
    backup = tmp_path / "source.dump"
    backup.write_bytes(b"source-dump")
    _write_checksum(backup)
    env = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "BACKUP_DIR": str(tmp_path / "backups"),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
    }
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore.sh"), str(backup), "--confirm"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8")
    assert "stop app reverse-proxy" in calls
    assert "pg_dump" in calls
    assert "createdb" in calls
    assert "pg_restore" in calls
    assert "pg_terminate_backend" in calls
    assert "start app" in calls and "start reverse-proxy" in calls
    assert list((tmp_path / "backups" / "pre-restore").glob("*.dump"))


def test_restore_simulation_rolls_back_and_restarts_after_failure(tmp_path) -> None:
    docker, log = _fake_docker(tmp_path)
    backup = tmp_path / "source.dump"
    backup.write_bytes(b"source-dump")
    _write_checksum(backup)
    env = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "FAIL_STAGE": "pg_restore",
        "BACKUP_DIR": str(tmp_path / "backups"),
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
    }
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore.sh"), str(backup), "--confirm"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 42
    calls = log.read_text(encoding="utf-8")
    assert "pg_restore" in calls
    assert "pg_terminate_backend" not in calls
    assert "dropdb" in calls
    assert "start app" in calls and "start reverse-proxy" in calls


def test_production_backup_requires_external_key_and_writes_encrypted_metadata(
    tmp_path,
) -> None:
    docker, log = _fake_docker(tmp_path)
    backup_dir = tmp_path / "backups"
    base_env = {
        **os.environ,
        "DOCKER_BIN": str(docker),
        "DOCKER_LOG": str(log),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "production",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_RETENTION_DAYS": "30",
        "BACKUP_RPO_HOURS": "24",
        "BACKUP_RTO_HOURS": "8",
    }
    rejected = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup.sh")],
        env=base_env, capture_output=True, text=True,
    )
    assert rejected.returncode == 78
    key = tmp_path / "backup.key"
    key.write_text("clave-externa-de-prueba", encoding="utf-8")
    key.chmod(0o600)
    accepted = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup.sh")],
        env={**base_env, "BACKUP_ENCRYPTION_KEY_FILE": str(key)},
        capture_output=True, text=True,
    )
    assert accepted.returncode == 0, accepted.stderr
    encrypted = list(backup_dir.glob("*.dump.enc"))
    assert len(encrypted) == 1
    assert encrypted[0].with_name(encrypted[0].name + ".sha256").is_file()
    metadata = json.loads(
        encrypted[0].with_name(encrypted[0].name + ".meta.json").read_text()
    )
    assert encrypted[0].with_name(
        encrypted[0].name + ".meta.json.sha256"
    ).is_file()
    assert metadata == {
        "created_at": metadata["created_at"],
        "encrypted": True,
        "rpo_hours": 24,
        "rto_hours": 8,
        "retention_days": 30,
        "format": "postgres-custom",
    }
    restored = subprocess.run(
        [
            "sh", str(ONPREM / "scripts" / "restore.sh"),
            str(encrypted[0]), "--confirm",
        ],
        env={**base_env, "BACKUP_ENCRYPTION_KEY_FILE": str(key)},
        capture_output=True, text=True,
    )
    assert restored.returncode == 0, restored.stderr


def test_backup_supports_linux_and_macos_sha256_tools() -> None:
    source = (ONPREM / "scripts" / "backup.sh").read_text(encoding="utf-8")
    assert "sha256sum" in source
    assert "shasum -a 256" in source
