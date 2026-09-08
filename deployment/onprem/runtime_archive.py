"""Archivo verificable de la raíz durable local JSON+SQLite."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tarfile
import tempfile
from typing import Any


MANIFEST_NAME = "manifest.json"
REQUIRED = (
    "knowledge/catalogo_maestro.json",
    "knowledge/diccionario.json",
    "operational/operations.db",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_snapshot(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f"No se permiten enlaces simbólicos: {relative}")
        if path.is_dir():
            (destination / relative).mkdir(parents=True, exist_ok=True)
            continue
        if path.name in {"operations.db-wal", "operations.db-shm"}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.as_posix() == "operational/operations.db":
            with sqlite3.connect(path) as source_db, sqlite3.connect(target) as target_db:
                source_db.backup(target_db)
        else:
            shutil.copy2(path, target)


def create_archive(
    source: str | Path,
    archive: str | Path,
    *,
    rpo_hours: int,
    rto_hours: int,
) -> dict[str, Any]:
    source_path = Path(source).resolve()
    archive_path = Path(archive).resolve()
    if not source_path.is_dir():
        raise ValueError(f"Raíz runtime no encontrada: {source_path}")
    with tempfile.TemporaryDirectory(prefix="homologacion-runtime-snapshot-") as temp:
        snapshot = Path(temp) / "runtime"
        snapshot.mkdir()
        _copy_snapshot(source_path, snapshot)
        files = {
            path.relative_to(snapshot).as_posix(): {
                "sha256": _sha256(path), "size": path.stat().st_size,
            }
            for path in sorted(snapshot.rglob("*")) if path.is_file()
        }
        missing = [name for name in REQUIRED if name not in files]
        if missing:
            raise ValueError("Snapshot incompleto; faltan: " + ", ".join(missing))
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": "homologacion-app-runtime-v1",
            "rpo_hours": int(rpo_hours),
            "rto_hours": int(rto_hours),
            "files": files,
        }
        (snapshot / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{archive_path.name}.", suffix=".partial", dir=archive_path.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with tarfile.open(temporary, "w:gz") as bundle:
                for path in sorted(snapshot.rglob("*")):
                    if path.is_file():
                        bundle.add(path, arcname=path.relative_to(snapshot).as_posix())
            os.replace(temporary, archive_path)
        finally:
            temporary.unlink(missing_ok=True)
    return manifest


def _safe_extract(bundle: tarfile.TarFile, destination: Path) -> None:
    for member in bundle.getmembers():
        name = PurePosixPath(member.name)
        if name.is_absolute() or ".." in name.parts or not member.isfile():
            raise ValueError(f"Entrada insegura en respaldo: {member.name}")
    bundle.extractall(destination, filter="data")


def verify_archive(archive: str | Path, extract_to: str | Path | None = None) -> dict[str, Any]:
    archive_path = Path(archive).resolve()
    if not archive_path.is_file() or archive_path.stat().st_size == 0:
        raise ValueError("Respaldo runtime vacío o inexistente")
    temporary_context = tempfile.TemporaryDirectory(prefix="homologacion-runtime-verify-")
    try:
        destination = Path(temporary_context.name)
        with tarfile.open(archive_path, "r:gz") as bundle:
            _safe_extract(bundle, destination)
        manifest_path = destination / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "homologacion-app-runtime-v1":
            raise ValueError("Formato de respaldo runtime no reconocido")
        declared = manifest.get("files")
        if not isinstance(declared, dict):
            raise ValueError("Manifiesto runtime inválido")
        actual = {
            path.relative_to(destination).as_posix()
            for path in destination.rglob("*")
            if path.is_file() and path.name != MANIFEST_NAME
        }
        if actual != set(declared):
            raise ValueError("El contenido no coincide con el manifiesto")
        for name, expected in declared.items():
            path = destination / name
            if _sha256(path) != expected.get("sha256") or path.stat().st_size != expected.get("size"):
                raise ValueError(f"Integridad inválida: {name}")
        for name in REQUIRED:
            if name not in declared:
                raise ValueError(f"Falta archivo obligatorio: {name}")
        json.loads((destination / REQUIRED[0]).read_text(encoding="utf-8"))
        json.loads((destination / REQUIRED[1]).read_text(encoding="utf-8"))
        with sqlite3.connect(destination / REQUIRED[2]) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite no supera integrity_check")
        if extract_to is not None:
            target = Path(extract_to).resolve()
            if target.exists() and any(target.iterdir()):
                raise ValueError("El destino de staging debe estar vacío")
            target.mkdir(parents=True, exist_ok=True)
            for path in destination.iterdir():
                if path.name != MANIFEST_NAME:
                    shutil.move(str(path), target / path.name)
        return manifest
    finally:
        temporary_context.cleanup()


def restore_local(archive: str | Path, target: str | Path) -> Path | None:
    """Verifica en staging y reemplaza un directorio local con rollback preservado."""
    target_path = Path(target).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target_path.name}.staging.", dir=target_path.parent))
    previous: Path | None = None
    try:
        verify_archive(archive, staging)
        if target_path.exists():
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            previous = target_path.with_name(f"{target_path.name}.before-{suffix}-{os.getpid()}")
            os.replace(target_path, previous)
        try:
            os.replace(staging, target_path)
        except Exception:
            if previous is not None and not target_path.exists():
                os.replace(previous, target_path)
            raise
        return previous
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("source")
    create.add_argument("archive")
    create.add_argument("--rpo-hours", type=int, required=True)
    create.add_argument("--rto-hours", type=int, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive")
    verify.add_argument("--extract-to")
    restore = subparsers.add_parser("restore-local")
    restore.add_argument("archive")
    restore.add_argument("target")
    args = parser.parse_args()
    if args.command == "create":
        result = create_archive(
            args.source, args.archive, rpo_hours=args.rpo_hours,
            rto_hours=args.rto_hours,
        )
    elif args.command == "verify":
        result = verify_archive(args.archive, args.extract_to)
    else:
        previous = restore_local(args.archive, args.target)
        result = {"previous": str(previous) if previous else None}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
