#!/usr/bin/env python3
"""Escanea o concilia la persistencia local sin exponer datos contables.

Sin subcomando, y con el subcomando ``scan``, abre SQLite en modo de sólo
lectura y emite únicamente contadores agregados. Cualquier movimiento exige el
subcomando explícito ``quarantine`` o ``restore``, rol administrador e identidad
de actor y organización. No existe una operación de borrado definitivo.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.contracts import AuthenticatedActor, ExecutionRecord  # noqa: E402
from persistence.local import LocalRuntimeReconciler, SqliteOperationalRepository  # noqa: E402


class ReadOnlyExecutionRepository:
    """Vista mínima de ejecuciones que nunca crea ni migra la base SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve(strict=True)

    def list_executions(self) -> list[ExecutionRecord]:
        # SQLite puede consolidar un WAL incluso al abrir una conexión mode=ro.
        # Consultamos una copia estable para que ni esa operación interna toque
        # el runtime inspeccionado.
        with tempfile.TemporaryDirectory(prefix="runtime-reconciliation-") as temp:
            snapshot = Path(temp) / "operations.db"
            self._copy_stable_snapshot(snapshot)
            uri = f"file:{quote(str(snapshot), safe='/')}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, timeout=5)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA query_only=ON")
                rows = connection.execute(
                    "SELECT * FROM local_executions ORDER BY created_at, execution_id"
                ).fetchall()
            finally:
                connection.close()
        return [self._record(row) for row in rows]

    def _copy_stable_snapshot(self, target: Path) -> None:
        sources = [
            self.database_path,
            Path(f"{self.database_path}-wal"),
            Path(f"{self.database_path}-shm"),
        ]
        for _attempt in range(3):
            before = self._source_state(sources)
            for source in sources:
                destination = target if source == self.database_path else Path(
                    f"{target}{source.name.removeprefix(self.database_path.name)}"
                )
                if source.exists():
                    shutil.copy2(source, destination)
                elif destination.exists():
                    destination.unlink()
            if before == self._source_state(sources):
                return
        raise RuntimeError(
            "La base operacional cambió durante el escaneo; reintente"
        )

    @staticmethod
    def _source_state(paths: list[Path]) -> tuple[tuple[str, int, int] | None, ...]:
        state: list[tuple[str, int, int] | None] = []
        for path in paths:
            try:
                stat = path.stat()
            except FileNotFoundError:
                state.append(None)
            else:
                state.append((path.name, stat.st_size, stat.st_mtime_ns))
        return tuple(state)

    @staticmethod
    def _record(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=row["execution_id"],
            document_id=row["document_id"],
            status=row["status"],
            application_version=row["application_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_code=row["error_code"],
            metadata=json.loads(row["metadata_json"]),
        )


class NoWriteAuditRepository:
    def append(self, _event):  # pragma: no cover - defensa de contrato
        raise PermissionError("El escaneo de sólo lectura no admite auditoría")

    def list_for_subject(self, *_args, **_kwargs):
        return []


def _positive_bounded(value: str, *, label: str, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} debe ser entero") from exc
    if not 1 <= parsed <= maximum:
        raise argparse.ArgumentTypeError(
            f"{label} debe estar entre 1 y {maximum}"
        )
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Escaneo agregado y conciliación recuperable del runtime local. "
            "El modo predeterminado es scan y no escribe."
        ),
    )
    parser.add_argument(
        "--root", type=Path,
        default=Path(os.environ.get("LOCAL_PERSISTENCE_ROOT", "")),
        help="Raíz durable local (o LOCAL_PERSISTENCE_ROOT).",
    )
    parser.add_argument(
        "--temporary-min-age-hours", default=24,
        type=lambda value: _positive_bounded(
            value, label="temporary-min-age-hours", maximum=8760,
        ),
    )
    parser.add_argument(
        "--quarantine-retention-days", default=90,
        type=lambda value: _positive_bounded(
            value, label="quarantine-retention-days", maximum=3650,
        ),
        help=(
            "Plazo de conservación/alerta. Los casos vencidos se informan, "
            "no se eliminan."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("scan", help="Escaneo agregado de sólo lectura.")

    quarantine = subparsers.add_parser(
        "quarantine", help="Mueve hallazgos reparables a cuarentena recuperable.",
    )
    _identity_arguments(quarantine)
    quarantine.add_argument(
        "--confirm", required=True, choices=["QUARANTINE"],
        help="Confirmación literal obligatoria.",
    )

    restore = subparsers.add_parser(
        "restore", help="Restaura un caso de cuarentena sin sobrescribir datos.",
    )
    restore.add_argument("case_id")
    _identity_arguments(restore)
    restore.add_argument(
        "--confirm", required=True, choices=["RESTORE"],
        help="Confirmación literal obligatoria.",
    )
    return parser


def _identity_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--actor-name", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--provider-subject", required=True)


def _actor(arguments: argparse.Namespace) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id=arguments.actor_id,
        display_name=arguments.actor_name,
        organization_id=arguments.organization_id,
        roles=frozenset({"admin"}),
        provider_subject=arguments.provider_subject,
    )


def _validated_root(value: Path) -> Path:
    if not str(value):
        raise ValueError(
            "Debe indicar --root o configurar LOCAL_PERSISTENCE_ROOT"
        )
    root = value.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("La raíz local no es un directorio")
    return root


def _reconciler(root: Path, *, writable: bool) -> LocalRuntimeReconciler:
    database_path = root / "operational" / "operations.db"
    if not database_path.is_file():
        raise FileNotFoundError(
            "No existe operational/operations.db; conciliación cancelada"
        )
    if writable:
        operational: Any = SqliteOperationalRepository(database_path)
    else:
        operational = ReadOnlyExecutionRepository(database_path)
    return LocalRuntimeReconciler(
        root, executions=operational,
        audit=operational if writable else NoWriteAuditRepository(),
    )


def run(arguments: argparse.Namespace) -> dict[str, object]:
    root = _validated_root(arguments.root)
    command = arguments.command or "scan"
    writable = command in {"quarantine", "restore"}
    reconciler = _reconciler(root, writable=writable)
    if command == "scan":
        return reconciler.scan(
            temporary_min_age_hours=arguments.temporary_min_age_hours,
            quarantine_retention_days=arguments.quarantine_retention_days,
        ).aggregate()
    if command == "quarantine":
        return reconciler.quarantine(
            actor=_actor(arguments),
            temporary_min_age_hours=arguments.temporary_min_age_hours,
            quarantine_retention_days=arguments.quarantine_retention_days,
        )
    if command == "restore":
        return reconciler.restore(arguments.case_id, actor=_actor(arguments))
    raise ValueError("Operación no soportada")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        result = run(parser.parse_args(argv))
    except (OSError, ValueError, PermissionError, sqlite3.Error) as exc:
        print(json.dumps({
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
