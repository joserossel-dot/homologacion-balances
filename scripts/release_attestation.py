"""Crea y verifica evidencia firmada de la recertificación privada.

La clave privada permanece fuera del repositorio y del CI. El analista ejecuta
``create`` junto al corpus privado; CI sólo recibe la atestación y la clave
pública, y verifica que ambas correspondan exactamente al commit y a los
manifiestos versionados que intenta publicar.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ATTESTATION_SCHEMA = 1
MAX_CLOCK_SKEW = timedelta(minutes=5)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: dict) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _openssl(*args: str) -> None:
    completed = subprocess.run(
        ["openssl", *args], capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"OpenSSL rechazó la operación: {detail}")


def _validate_commit(commit_sha: str) -> str:
    commit_sha = str(commit_sha).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("El commit de la atestación debe ser un SHA Git de 40 caracteres.")
    return commit_sha


def _required_manifest_cases(manifest: Path) -> dict[str, str | None]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Manifiesto inválido: {manifest}")
    return {
        str(case["file"]): (
            str((case.get("expect") or {}).get("sha256") or "").lower()
            or None
        )
        for case in cases
        if bool(case.get("required_for_release", True))
    }


def validate_private_report(report: Path, manifests: list[Path]) -> list[dict]:
    rows = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("El informe privado debe ser una lista JSON.")
    by_file: dict[str, list[dict]] = {}
    for row in rows:
        if isinstance(row, dict):
            by_file.setdefault(str(row.get("file") or ""), []).append(row)
    evidence = []
    for manifest in manifests:
        for filename, expected_sha in sorted(
            _required_manifest_cases(manifest).items()
        ):
            matches = by_file.get(filename, [])
            if len(matches) != 1:
                raise ValueError(
                    f"El informe debe contener exactamente un resultado para {filename}."
                )
            row = matches[0]
            if row.get("status") != "ok" or row.get("expectations_passed") is not True:
                raise ValueError(f"La recertificación privada no aprobó {filename}.")
            certification_state = (row.get("certification") or {}).get("state")
            if certification_state != "certificada":
                raise ValueError(
                    f"La recertificación privada de {filename} no está certificada."
                )
            document_sha = str(row.get("sha256") or "").lower()
            if expected_sha and document_sha != expected_sha:
                raise ValueError(
                    f"El SHA del documento {filename} no coincide con el manifiesto."
                )
            evidence.append({
                "file": filename,
                "sha256": document_sha,
                "status": "approved",
            })
    return evidence


def create_attestation(
    *, report: Path, manifests: list[Path], commit_sha: str,
    private_key: Path, output: Path, valid_for_hours: int = 24,
    now: datetime | None = None,
) -> dict:
    commit_sha = _validate_commit(commit_sha)
    if not 1 <= int(valid_for_hours) <= 168:
        raise ValueError("La vigencia debe estar entre 1 y 168 horas.")
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise ValueError("La fecha de atestación debe incluir zona horaria.")
    issued_at = issued_at.astimezone(timezone.utc)
    evidence = validate_private_report(report, manifests)
    payload = {
        "schema": ATTESTATION_SCHEMA,
        "commit_sha": commit_sha,
        "created_at": issued_at.isoformat(),
        "expires_at": (
            issued_at + timedelta(hours=int(valid_for_hours))
        ).isoformat(),
        "report_sha256": _sha256(report),
        "manifests": [
            {"name": path.name, "sha256": _sha256(path)}
            for path in manifests
        ],
        "required_cases": evidence,
    }
    with tempfile.TemporaryDirectory(prefix="release-attestation-") as temp:
        payload_path = Path(temp) / "payload.json"
        signature_path = Path(temp) / "signature.bin"
        payload_path.write_bytes(_canonical_json(payload))
        _openssl(
            "pkeyutl", "-sign", "-rawin", "-inkey", str(private_key),
            "-in", str(payload_path), "-out", str(signature_path),
        )
        envelope = {
            "payload": payload,
            "signature": base64.b64encode(signature_path.read_bytes()).decode("ascii"),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return envelope


def verify_attestation(
    *, attestation: Path, manifests: list[Path], commit_sha: str,
    public_key: Path, now: datetime | None = None,
) -> dict:
    commit_sha = _validate_commit(commit_sha)
    envelope = json.loads(attestation.read_text(encoding="utf-8"))
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    signature = envelope.get("signature") if isinstance(envelope, dict) else None
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise ValueError("Formato de atestación inválido.")
    try:
        signature_bytes = base64.b64decode(signature, validate=True)
    except ValueError as exc:
        raise ValueError("Firma base64 inválida.") from exc
    with tempfile.TemporaryDirectory(prefix="release-attestation-") as temp:
        payload_path = Path(temp) / "payload.json"
        signature_path = Path(temp) / "signature.bin"
        payload_path.write_bytes(_canonical_json(payload))
        signature_path.write_bytes(signature_bytes)
        _openssl(
            "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey",
            str(public_key), "-in", str(payload_path), "-sigfile",
            str(signature_path),
        )
    if payload.get("schema") != ATTESTATION_SCHEMA:
        raise ValueError("Versión de atestación no soportada.")
    if payload.get("commit_sha") != commit_sha:
        raise ValueError("La atestación pertenece a otro commit.")
    try:
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("La atestación no declara fechas válidas.") from exc
    verification_time = now or datetime.now(timezone.utc)
    if verification_time.tzinfo is None:
        raise ValueError("La fecha de verificación debe incluir zona horaria.")
    if created_at.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("Las fechas de la atestación deben incluir zona horaria.")
    verification_time = verification_time.astimezone(timezone.utc)
    created_at = created_at.astimezone(timezone.utc)
    expires_at = expires_at.astimezone(timezone.utc)
    if created_at > verification_time + MAX_CLOCK_SKEW:
        raise ValueError("La atestación declara una fecha de emisión futura.")
    if expires_at <= created_at:
        raise ValueError("La atestación declara una vigencia inválida.")
    if expires_at - created_at > timedelta(hours=168):
        raise ValueError("La atestación excede la vigencia máxima permitida.")
    if verification_time >= expires_at:
        raise ValueError("La atestación expiró y no puede reutilizarse.")
    current_manifests = [
        {"name": path.name, "sha256": _sha256(path)} for path in manifests
    ]
    if payload.get("manifests") != current_manifests:
        raise ValueError("Los manifiestos cambiaron después de la recertificación.")
    required = set().union(*(
        set(_required_manifest_cases(path)) for path in manifests
    ))
    attested = {
        row.get("file") for row in payload.get("required_cases", [])
        if isinstance(row, dict) and row.get("status") == "approved"
    }
    if attested != required:
        raise ValueError("La atestación no cubre exactamente todos los casos obligatorios.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--report", type=Path, required=True)
    create.add_argument("--manifest", type=Path, action="append", required=True)
    create.add_argument("--commit", required=True)
    create.add_argument("--private-key", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--valid-for-hours", type=int, default=24)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--attestation", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, action="append", required=True)
    verify.add_argument("--commit", required=True)
    verify.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        create_attestation(
            report=args.report, manifests=args.manifest, commit_sha=args.commit,
            private_key=args.private_key, output=args.output,
            valid_for_hours=args.valid_for_hours,
        )
    else:
        verify_attestation(
            attestation=args.attestation, manifests=args.manifest,
            commit_sha=args.commit, public_key=args.public_key,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
