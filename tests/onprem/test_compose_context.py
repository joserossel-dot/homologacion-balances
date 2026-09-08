"""Maintenance must resolve the same images and volumes as its caller."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ONPREM = Path(__file__).resolve().parents[2] / "deployment" / "onprem"


def test_maintenance_preserves_smoke_context(tmp_path):
    env_file = tmp_path / "smoke with spaces.env"
    env_file.write_text(
        "APP_IMAGE_REFERENCE=homologacion-balances:isolated-test\n"
        "CADDYFILE_PATH=./Caddyfile\n"
        "ONPREM_DEPLOYMENT_MODE=evaluation\n"
    )
    environment = {
        **os.environ,
        "compose_dir": str(ONPREM),
        "ONPREM_COMPOSE_ENV_FILE": str(env_file),
        "ONPREM_COMPOSE_OVERRIDE": str(ONPREM / "docker-compose.evaluation.yml"),
        "COMPOSE_PROJECT_NAME": "maintenance-isolated-test",
    }
    environment.pop("APP_IMAGE_REFERENCE", None)
    environment.pop("CADDYFILE_PATH", None)
    result = subprocess.run(
        ["sh", "-c", '. "$1"; compose config --format json', "sh",
         str(ONPREM / "scripts" / "compose-context.sh")],
        env=environment, capture_output=True, text=True, check=True,
    )
    config = json.loads(result.stdout)
    assert config["name"] == "maintenance-isolated-test"
    assert config["services"]["app"]["image"] == "homologacion-balances:isolated-test"
    assert "build" in config["services"]["app"]
    assert config["volumes"]["app_runtime"]["name"].startswith("maintenance-isolated-test_")


@pytest.mark.parametrize("mode,message", [
    ("production", "digest"), ("invalid", "evaluation o production"),
])
def test_smoke_rejects_invalid_production_configuration_before_docker(mode, message):
    environment = {**os.environ, "ONPREM_SMOKE_MODE": mode}
    for name in ("APP_IMAGE_REFERENCE", "POSTGRES_IMAGE", "CADDY_IMAGE", "CADDY_INIT_IMAGE"):
        environment.pop(name, None)
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "smoke-test.sh")],
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert message in result.stderr


@pytest.mark.parametrize("mode", ["evaluation", "production"])
def test_failed_smoke_cleanup_uses_same_compose_context(tmp_path, mode):
    # Stub only command dispatch to fail config; this is not a Docker smoke.
    binary = tmp_path / "docker"
    log = tmp_path / "commands.jsonl"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "sys.exit(77 if 'config' in sys.argv else 0)\n"
    )
    binary.chmod(0o700)
    digest = "registry.local/image@sha256:" + "a" * 64
    environment = {
        **os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "COMMAND_LOG": str(log), "ONPREM_SMOKE_MODE": mode,
        "KEEP_ONPREM_SMOKE_ARTIFACTS": "false", "TMPDIR": str(tmp_path),
        **{name: digest for name in (
            "APP_IMAGE_REFERENCE", "POSTGRES_IMAGE", "CADDY_IMAGE", "CADDY_INIT_IMAGE",
        )},
    }
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "smoke-test.sh")],
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 77, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    config = next(call for call in calls if "config" in call)
    cleanup = next(call for call in calls if "down" in call)
    assert config[:config.index("config")] == cleanup[:cleanup.index("down")]
    assert (str(ONPREM / "docker-compose.evaluation.yml") in cleanup) == (mode == "evaluation")
    assert not list(tmp_path.glob("homologacion-onprem-smoke.*"))
