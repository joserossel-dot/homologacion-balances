from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.audit_module_usage import build_inventory


ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_inventory_classifies_reachability_and_reports_missing_entrypoint(tmp_path) -> None:
    _write(tmp_path / "pyproject.toml", """
[tool.poetry.scripts]
missing = "missing.cli:main"
""")
    _write(tmp_path / "render.yaml", "dockerfilePath: ./Dockerfile\n")
    _write(
        tmp_path / "Dockerfile",
        'CMD ["sh", "-c", "streamlit run app.py --server.port=10000"]\n',
    )
    _write(tmp_path / "app.py", "from pkg.used import VALUE\n")
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "used.py", "VALUE = 1\n")
    _write(tmp_path / "pkg" / "only_test.py", "VALUE = 2\n")
    _write(tmp_path / "pkg" / "orphan.py", "VALUE = 3\n")
    _write(tmp_path / "shadow" / "logger.py", "VALUE = 4\n")
    _write(tmp_path / "scripts" / "task.py", "if __name__ == '__main__':\n    pass\n")
    _write(tmp_path / "tests" / "test_only.py", "from pkg.only_test import VALUE\n")

    report = build_inventory(tmp_path)
    records = {record["module"]: record for record in report["modules"]}

    assert records["app"]["status"] == "productive"
    assert records["pkg.used"]["status"] == "productive"
    assert records["pkg.only_test"]["status"] == "tests_only"
    assert records["pkg.orphan"]["status"] == "orphan"
    assert records["shadow.logger"]["status"] == "shadow"
    assert records["scripts.task"]["status"] == "offline"
    assert report["findings"]["nonexistent_entrypoints"] == [{
        "kind": "poetry_script",
        "name": "missing",
        "target": "missing.cli:main",
        "module": "missing.cli",
        "exists": False,
    }]


def test_inventory_detects_runtime_tls_bypass_but_ignores_test_fixture(tmp_path) -> None:
    _write(tmp_path / "bad.py", "import ssl\nMODE = ssl.CERT_NONE\n")
    _write(tmp_path / "tests" / "test_fixture.py", "TOKEN = 'CERT_NONE'\n")

    report = build_inventory(tmp_path)

    assert report["findings"]["tls_bypasses"] == [{
        "path": "bad.py", "line": 2, "rule": "CERT_NONE",
    }]


def test_json_output_is_deterministic_and_security_exit_is_explicit(tmp_path) -> None:
    _write(tmp_path / "app.py", "VALUE = 1\n")
    output_a = tmp_path / "a.json"
    output_b = tmp_path / "b.json"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "audit_module_usage.py"),
        "--root", str(tmp_path), "--output",
    ]
    first = subprocess.run(command + [str(output_a)], check=False)
    second = subprocess.run(command + [str(output_b)], check=False)
    assert first.returncode == second.returncode == 0
    assert output_a.read_bytes() == output_b.read_bytes()
    assert json.loads(output_a.read_text())["analysis"]["root"] == "."

    _write(tmp_path / "bad.py", "check_hostname = False\n")
    secured = subprocess.run(
        command + [str(output_a), "--fail-on-security"], check=False,
    )
    assert secured.returncode == 2


def test_real_repository_has_no_tls_bypass_and_finds_runtime_entrypoint() -> None:
    report = build_inventory(ROOT)
    assert report["findings"]["tls_bypasses"] == []
    assert any(
        entry["module"] == "app_validacion" and entry["exists"]
        for entry in report["entrypoints"]
    )
    assert all(
        not entry["exists"]
        for entry in report["findings"]["nonexistent_entrypoints"]
    )
