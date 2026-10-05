#!/usr/bin/env python3
"""Authenticate on-premise backup artifacts with Encrypt-then-MAC.

The authentication envelope is intentionally independent from the diagnostic
SHA-256 sidecars.  It authenticates the exact metadata and payload bytes before
any restore operation is allowed to parse or decrypt them.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import struct
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO, NoReturn


DOMAIN = b"homologacion-backup-auth-v1\0"
SCHEMA = "homologacion-backup-auth-v1"
ALGORITHM = "hmac-sha256"
KDF = "pbkdf2-hmac-sha256"
ITERATIONS = 200_000
SALT_BYTES = 32
TAG_BYTES = 32
CHUNK_SIZE = 1024 * 1024
MAX_ENVELOPE_BYTES = 16 * 1024
MAX_KEY_BYTES = 64 * 1024
PAYLOAD_KINDS = ("app-runtime", "postgres-custom")
KEY_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
HEX_32_RE = re.compile(r"[0-9a-f]{64}\Z")
VERIFY_ERROR = "Autenticación del respaldo inválida."


class BackupAuthError(Exception):
    """Base error for controlled CLI failures."""


class VerificationError(BackupAuthError):
    """An authentication verification failed."""


class ConfigurationError(BackupAuthError):
    """Signing configuration is invalid."""


class DuplicateKeyError(ValueError):
    """A JSON object contains a duplicate key."""


def _u64be(value: int) -> bytes:
    if value < 0 or value >= 2**64:
        raise BackupAuthError("Tamaño de archivo fuera de rango.")
    return struct.pack(">Q", value)


def _read_key(path: Path) -> bytes:
    try:
        stream, size = _open_regular(path)
        info = os.fstat(stream.fileno())
        if size <= 0 or size > MAX_KEY_BYTES:
            stream.close()
            raise ConfigurationError("El archivo de clave tiene un tamaño inválido.")
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            stream.close()
            raise ConfigurationError(
                "El archivo de clave debe pertenecer al operador y usar permisos privados."
            )
        with stream:
            key = stream.readline(MAX_KEY_BYTES + 1).rstrip(b"\r\n")
    except (BackupAuthError, OSError) as exc:
        raise ConfigurationError("No se puede leer el archivo de clave.") from exc
    if len(key) < 16:
        raise ConfigurationError("La clave debe contener al menos 16 bytes.")
    return key


def _validate_key_id(key_id: str | None) -> None:
    if key_id is not None and KEY_ID_RE.fullmatch(key_id) is None:
        raise ConfigurationError("BACKUP_KEY_ID inválido.")


def _header(
    *, salt_hex: str, payload_kind: str, key_id: str | None
) -> dict[str, object]:
    result: dict[str, object] = {
        "algorithm": ALGORITHM,
        "iterations": ITERATIONS,
        "kdf": KDF,
        "payload_kind": payload_kind,
        "salt_hex": salt_hex,
        "schema": SCHEMA,
    }
    if key_id is not None:
        result["key_id"] = key_id
    return result


def _canonical_json(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _derive_auth_key(secret: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", secret, DOMAIN + salt, ITERATIONS, dklen=TAG_BYTES
    )


def _open_regular(path: Path) -> tuple[BinaryIO, int]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(path, flags)
        info = os.fstat(fd)
    except OSError as exc:
        if fd >= 0:
            os.close(fd)
        raise BackupAuthError("No se puede leer un archivo del respaldo.") from exc
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise BackupAuthError("El respaldo debe usar archivos regulares.")
    return os.fdopen(fd, "rb"), info.st_size


def _update_stream(
    mac: hmac.HMAC,
    stream: BinaryIO,
    size: int,
    destination: BinaryIO | None = None,
) -> None:
    remaining = size
    while remaining:
        chunk = stream.read(min(CHUNK_SIZE, remaining))
        if not chunk:
            raise VerificationError
        mac.update(chunk)
        if destination is not None:
            destination.write(chunk)
        remaining -= len(chunk)


def _compute_tag(
    secret: bytes,
    salt: bytes,
    header: dict[str, object],
    metadata_path: Path,
    artifact_path: Path,
) -> bytes:
    metadata, metadata_size = _open_regular(metadata_path)
    try:
        artifact, artifact_size = _open_regular(artifact_path)
    except Exception:
        metadata.close()
        raise
    try:
        canonical_header = _canonical_json(header)
        mac = hmac.new(_derive_auth_key(secret, salt), digestmod=hashlib.sha256)
        mac.update(DOMAIN)
        mac.update(_u64be(len(canonical_header)))
        mac.update(canonical_header)
        mac.update(_u64be(metadata_size))
        _update_stream(mac, metadata, metadata_size)
        mac.update(_u64be(artifact_size))
        _update_stream(mac, artifact, artifact_size)
        return mac.digest()
    finally:
        metadata.close()
        artifact.close()


def _atomic_write(path: Path, content: bytes) -> None:
    directory = path.parent
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=directory
        )
    except OSError as exc:
        raise BackupAuthError("No se puede preparar el sidecar de autenticación.") from exc
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        try:
            directory_fd = os.open(directory, os.O_RDONLY)
        except OSError:
            directory_fd = -1
        if directory_fd >= 0:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def sign(
    *,
    artifact_path: Path,
    metadata_path: Path,
    key_file: Path,
    output_path: Path,
    payload_kind: str,
    key_id: str | None,
) -> None:
    _validate_key_id(key_id)
    secret = _read_key(key_file)
    salt = secrets.token_bytes(SALT_BYTES)
    header = _header(
        salt_hex=salt.hex(), payload_kind=payload_kind, key_id=key_id
    )
    tag = _compute_tag(secret, salt, header, metadata_path, artifact_path)
    envelope = dict(header)
    envelope["tag"] = tag.hex()
    _atomic_write(output_path, _canonical_json(envelope) + b"\n")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _load_envelope(path: Path) -> dict[str, object]:
    try:
        stream, size = _open_regular(path)
        if size <= 0 or size > MAX_ENVELOPE_BYTES:
            stream.close()
            raise VerificationError
        with stream:
            raw = stream.read(size + 1)
        if len(raw) != size:
            raise VerificationError
        envelope = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise VerificationError from exc
    if not isinstance(envelope, dict):
        raise VerificationError
    required = {
        "schema",
        "algorithm",
        "kdf",
        "iterations",
        "salt_hex",
        "payload_kind",
        "tag",
    }
    optional = {"key_id"}
    keys = set(envelope)
    if not required.issubset(keys) or not keys.issubset(required | optional):
        raise VerificationError
    if envelope.get("schema") != SCHEMA:
        raise VerificationError
    if envelope.get("algorithm") != ALGORITHM:
        raise VerificationError
    if envelope.get("kdf") != KDF:
        raise VerificationError
    iterations = envelope.get("iterations")
    if (
        not isinstance(iterations, int)
        or isinstance(iterations, bool)
        or iterations != ITERATIONS
    ):
        raise VerificationError
    if envelope.get("payload_kind") not in PAYLOAD_KINDS:
        raise VerificationError
    salt_hex = envelope.get("salt_hex")
    tag = envelope.get("tag")
    if not isinstance(salt_hex, str) or HEX_32_RE.fullmatch(salt_hex) is None:
        raise VerificationError
    if not isinstance(tag, str) or HEX_32_RE.fullmatch(tag) is None:
        raise VerificationError
    key_id = envelope.get("key_id")
    if key_id is not None and (
        not isinstance(key_id, str) or KEY_ID_RE.fullmatch(key_id) is None
    ):
        raise VerificationError
    return envelope


def _private_output_parent(outputs: list[Path]) -> tuple[Path, tuple[str, ...]]:
    if not outputs:
        raise VerificationError
    try:
        parents = [output.parent.resolve(strict=True) for output in outputs]
        info = os.stat(parents[0], follow_symlinks=False)
    except OSError as exc:
        raise VerificationError from exc
    if any(parent != parents[0] for parent in parents[1:]):
        raise VerificationError
    if not stat.S_ISDIR(info.st_mode):
        raise VerificationError
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise VerificationError
    names = tuple(output.name for output in outputs)
    if len(set(names)) != len(names):
        raise VerificationError
    if any(output.exists() or output.is_symlink() for output in outputs):
        raise VerificationError
    return parents[0], names


def _stage_parent(
    artifact_output: Path,
    metadata_output: Path,
    key_output: Path | None,
) -> tuple[Path, tuple[str, ...]]:
    outputs = [artifact_output, metadata_output]
    if key_output is not None:
        outputs.append(key_output)
    return _private_output_parent(outputs)


def capture_key(*, key_file: Path, output_path: Path) -> None:
    secret = _read_key(key_file)
    try:
        parent, names = _private_output_parent([output_path])
    except VerificationError as exc:
        raise ConfigurationError("El destino de la clave capturada no es privado.") from exc
    _atomic_write(parent / names[0], secret + b"\n")


def _verified_staged_copies(
    *,
    secret: bytes,
    salt: bytes,
    header: dict[str, object],
    supplied_tag: bytes,
    metadata_path: Path,
    artifact_path: Path,
    staged_artifact_path: Path,
    staged_metadata_path: Path,
    staged_key_path: Path | None,
) -> None:
    parent, names = _stage_parent(
        staged_artifact_path, staged_metadata_path, staged_key_path
    )
    artifact_name, metadata_name = names[:2]
    key_name = names[2] if staged_key_path is not None else None
    metadata, metadata_size = _open_regular(metadata_path)
    try:
        artifact, artifact_size = _open_regular(artifact_path)
    except Exception:
        metadata.close()
        raise

    artifact_fd = -1
    metadata_fd = -1
    key_fd = -1
    artifact_temporary: Path | None = None
    metadata_temporary: Path | None = None
    key_temporary: Path | None = None
    published: list[Path] = []
    try:
        artifact_fd, artifact_temporary_name = tempfile.mkstemp(
            prefix=f".{artifact_name}.", suffix=".tmp", dir=parent
        )
        artifact_temporary = Path(artifact_temporary_name)
        metadata_fd, metadata_temporary_name = tempfile.mkstemp(
            prefix=f".{metadata_name}.", suffix=".tmp", dir=parent
        )
        metadata_temporary = Path(metadata_temporary_name)
        os.fchmod(artifact_fd, 0o600)
        os.fchmod(metadata_fd, 0o600)
        if key_name is not None:
            key_fd, key_temporary_name = tempfile.mkstemp(
                prefix=f".{key_name}.", suffix=".tmp", dir=parent
            )
            key_temporary = Path(key_temporary_name)
            os.fchmod(key_fd, 0o600)
            with os.fdopen(key_fd, "wb") as key_destination:
                key_fd = -1
                key_destination.write(secret + b"\n")
                key_destination.flush()
                os.fsync(key_destination.fileno())

        canonical_header = _canonical_json(header)
        mac = hmac.new(_derive_auth_key(secret, salt), digestmod=hashlib.sha256)
        mac.update(DOMAIN)
        mac.update(_u64be(len(canonical_header)))
        mac.update(canonical_header)
        with os.fdopen(metadata_fd, "wb") as metadata_destination:
            metadata_fd = -1
            mac.update(_u64be(metadata_size))
            _update_stream(
                mac, metadata, metadata_size, destination=metadata_destination
            )
            metadata_destination.flush()
            os.fsync(metadata_destination.fileno())
        with os.fdopen(artifact_fd, "wb") as artifact_destination:
            artifact_fd = -1
            mac.update(_u64be(artifact_size))
            _update_stream(
                mac, artifact, artifact_size, destination=artifact_destination
            )
            artifact_destination.flush()
            os.fsync(artifact_destination.fileno())

        if not hmac.compare_digest(supplied_tag, mac.digest()):
            raise VerificationError

        os.replace(metadata_temporary, parent / metadata_name)
        published.append(parent / metadata_name)
        metadata_temporary = None
        os.replace(artifact_temporary, parent / artifact_name)
        published.append(parent / artifact_name)
        artifact_temporary = None
        if key_name is not None and key_temporary is not None:
            os.replace(key_temporary, parent / key_name)
            published.append(parent / key_name)
            key_temporary = None
        for output in published:
            os.chmod(output, 0o600)
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        for output in published:
            try:
                output.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        metadata.close()
        artifact.close()
        if metadata_fd >= 0:
            os.close(metadata_fd)
        if artifact_fd >= 0:
            os.close(artifact_fd)
        if key_fd >= 0:
            os.close(key_fd)
        for temporary in (
            metadata_temporary,
            artifact_temporary,
            key_temporary,
        ):
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass


def verify(
    *,
    artifact_path: Path,
    metadata_path: Path,
    key_file: Path,
    auth_path: Path,
    payload_kind: str,
    staged_artifact_path: Path | None = None,
    staged_metadata_path: Path | None = None,
    staged_key_path: Path | None = None,
) -> None:
    try:
        if (staged_artifact_path is None) != (staged_metadata_path is None):
            raise VerificationError
        if staged_key_path is not None and staged_artifact_path is None:
            raise VerificationError
        envelope = _load_envelope(auth_path)
        if envelope["payload_kind"] != payload_kind:
            raise VerificationError
        secret = _read_key(key_file)
        salt = bytes.fromhex(str(envelope["salt_hex"]))
        supplied_tag = bytes.fromhex(str(envelope["tag"]))
        header = {key: value for key, value in envelope.items() if key != "tag"}
        if staged_artifact_path is not None and staged_metadata_path is not None:
            _verified_staged_copies(
                secret=secret,
                salt=salt,
                header=header,
                supplied_tag=supplied_tag,
                metadata_path=metadata_path,
                artifact_path=artifact_path,
                staged_artifact_path=staged_artifact_path,
                staged_metadata_path=staged_metadata_path,
                staged_key_path=staged_key_path,
            )
        else:
            calculated_tag = _compute_tag(
                secret, salt, header, metadata_path, artifact_path
            )
            if not hmac.compare_digest(supplied_tag, calculated_tag):
                raise VerificationError
    except (BackupAuthError, OSError, ValueError, TypeError) as exc:
        raise VerificationError from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign_parser = subparsers.add_parser("sign", help="Crear sidecar autenticado")
    sign_parser.add_argument("--artifact", "--payload", dest="artifact", required=True)
    sign_parser.add_argument("--metadata", required=True)
    sign_parser.add_argument("--key-file", required=True)
    sign_parser.add_argument("--output", required=True)
    sign_parser.add_argument("--payload-kind", choices=PAYLOAD_KINDS, required=True)
    sign_parser.add_argument("--key-id")

    verify_parser = subparsers.add_parser("verify", help="Verificar sidecar")
    verify_parser.add_argument(
        "--artifact", "--payload", dest="artifact", required=True
    )
    verify_parser.add_argument("--metadata", required=True)
    verify_parser.add_argument("--key-file", required=True)
    verify_parser.add_argument(
        "--auth", "--input", "--sidecar", dest="auth", required=True
    )
    verify_parser.add_argument("--payload-kind", choices=PAYLOAD_KINDS, required=True)
    verify_parser.add_argument("--staged-artifact")
    verify_parser.add_argument("--staged-metadata")
    verify_parser.add_argument("--staged-key")

    capture_parser = subparsers.add_parser(
        "capture-key", help="Capturar una clave privada para una operación"
    )
    capture_parser.add_argument("--key-file", required=True)
    capture_parser.add_argument("--output", required=True)
    return parser


def _verification_failure() -> NoReturn:
    print(VERIFY_ERROR, file=sys.stderr)
    raise SystemExit(65)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "capture-key":
        try:
            capture_key(
                key_file=Path(args.key_file), output_path=Path(args.output)
            )
        except ConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 78
        except (BackupAuthError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 74
        return 0
    if args.command == "sign":
        try:
            sign(
                artifact_path=Path(args.artifact),
                metadata_path=Path(args.metadata),
                key_file=Path(args.key_file),
                output_path=Path(args.output),
                payload_kind=args.payload_kind,
                key_id=args.key_id,
            )
        except ConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            return 78
        except (BackupAuthError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 74
        return 0

    try:
        verify(
            artifact_path=Path(args.artifact),
            metadata_path=Path(args.metadata),
            key_file=Path(args.key_file),
            auth_path=Path(args.auth),
            payload_kind=args.payload_kind,
            staged_artifact_path=(
                Path(args.staged_artifact) if args.staged_artifact else None
            ),
            staged_metadata_path=(
                Path(args.staged_metadata) if args.staged_metadata else None
            ),
            staged_key_path=(Path(args.staged_key) if args.staged_key else None),
        )
    except VerificationError:
        _verification_failure()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
