from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def test_insecure_legacy_src_route_is_retired() -> None:
    retired = (
        ROOT / "src" / "db_repository.py",
        ROOT / "src" / "api" / "main.py",
        ROOT / "src" / "core" / "orquestador.py",
    )
    assert all(not path.exists() for path in retired)


def test_no_tls_verification_bypass_in_runtime_python() -> None:
    forbidden = ("CERT_NONE", "check_hostname = False")
    runtime_files = [
        path for path in ROOT.rglob("*.py")
        if not any(part in {".git", ".venv", "tests"} for part in path.parts)
    ]
    violations = {
        str(path.relative_to(ROOT)): token
        for path in runtime_files
        for token in forbidden
        if token in path.read_text(encoding="utf-8", errors="ignore")
    }
    assert violations == {}


def test_poetry_does_not_publish_a_missing_cli_entrypoint() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = config.get("tool", {}).get("poetry", {}).get("scripts", {})
    assert "src.cli:main" not in scripts.values()
