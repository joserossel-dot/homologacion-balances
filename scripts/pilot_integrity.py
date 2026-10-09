#!/usr/bin/env python3
"""Read-only integrity snapshots for the internal no-write pilot.

The command never writes inside the repository. Save the JSON emitted by
``snapshot`` in the restricted evidence location, then use ``verify`` after a
pilot session to detect changes to protected persistent artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent.parent
PROTECTED_ARTIFACTS = (
    "diccionario.json",
    "catalogo_maestro.json",
    "gold_standard.db",
    "gold_standard.db-journal",
    "gold_standard.db-shm",
    "gold_standard.db-wal",
    "gold_standard_runtime.db",
    "gold_standard_runtime.db-journal",
    "gold_standard_runtime.db-shm",
    "gold_standard_runtime.db-wal",
    "learning_queue.json",
    "datasets/dataset_registry.db",
    "datasets/dataset_registry.db-journal",
    "datasets/dataset_registry.db-shm",
    "datasets/dataset_registry.db-wal",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def capture_snapshot(
    root: Path = ROOT,
    protected_artifacts: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return stable metadata for every protected artifact below ``root``."""
    root = root.resolve()
    if protected_artifacts is None:
        protected_artifacts = PROTECTED_ARTIFACTS
    artifacts: dict[str, dict[str, Any]] = {}
    for relative_path in protected_artifacts:
        path = root / relative_path
        if path.is_symlink():
            artifacts[relative_path] = {"state": "symlink"}
            continue
        if not path.exists():
            artifacts[relative_path] = {"state": "missing"}
            continue
        if not path.is_file():
            artifacts[relative_path] = {"state": "not_file"}
            continue
        try:
            artifacts[relative_path] = {
                "state": "file",
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        except OSError as exc:
            artifacts[relative_path] = {
                "state": "unreadable",
                "error": type(exc).__name__,
            }
    return {"schema_version": 1, "artifacts": artifacts}


def compare_snapshots(
    baseline: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return only artifacts whose protected state differs from the baseline."""
    baseline_artifacts = baseline.get("artifacts", {})
    observed_artifacts = observed.get("artifacts", {})
    if not isinstance(baseline_artifacts, dict):
        raise ValueError("El manifiesto base no contiene artifacts válidos")
    if not isinstance(observed_artifacts, dict):
        raise ValueError("El snapshot observado no contiene artifacts válidos")

    changes: dict[str, dict[str, Any]] = {}
    for relative_path in sorted(set(baseline_artifacts) | set(observed_artifacts)):
        expected = baseline_artifacts.get(relative_path)
        actual = observed_artifacts.get(relative_path)
        if expected != actual:
            changes[relative_path] = {"expected": expected, "observed": actual}
    return changes


def _load_baseline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"No fue posible leer el manifiesto base: {type(exc).__name__}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("El manifiesto base no tiene el esquema esperado")
    return data


def _emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot de integridad para el piloto no mutativo",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Raíz del repositorio a inspeccionar. Por defecto, el repositorio actual.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot", help="Emite un snapshot JSON por stdout")
    verify = commands.add_parser(
        "verify",
        help="Compara el estado actual contra un snapshot externo",
    )
    verify.add_argument("baseline", type=Path, help="Archivo JSON creado antes del piloto")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        _emit({"status": "ERROR", "reason": "repository_root_not_found"})
        return 2

    observed = capture_snapshot(root)
    if args.command == "snapshot":
        _emit(observed)
        return 0

    try:
        baseline = _load_baseline(args.baseline)
        changes = compare_snapshots(baseline, observed)
    except ValueError as exc:
        _emit({"status": "ERROR", "reason": str(exc)})
        return 2

    _emit({
        "status": "PASS" if not changes else "FAIL",
        "checked_artifacts": len(observed["artifacts"]),
        "changes": changes,
    })
    return 0 if not changes else 1


if __name__ == "__main__":
    raise SystemExit(main())
