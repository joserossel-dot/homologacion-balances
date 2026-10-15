#!/usr/bin/env python3
"""Valida un manifiesto externo de piloto sin revelar datos locales.

Uso::

    python scripts/validate_pilot_manifest.py \
        --manifest /ruta/externa/manifiesto.json \
        --batch /ruta/externa/lote.json

``lote.json`` es un objeto JSON ``document_id_opaco -> ruta_local``. Las
rutas se usan exclusivamente para leer bytes; no se incluyen en la salida ni
se usan como evidencia contable.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pilot_manifest import (
    PilotManifestError,
    PilotManifestValidation,
    UploadedPilotDocument,
    validate_pilot_manifest_json,
)


def _failure(code: str) -> PilotManifestValidation:
    return PilotManifestValidation(
        client_id=None,
        documents=(),
        errors=(PilotManifestError(code, "$"),),
    )


def _read_json(path: Path, *, file_error: str, json_error: str) -> object | PilotManifestValidation:
    try:
        raw = path.read_bytes()
    except (OSError, ValueError):
        return _failure(file_error)
    try:
        return json.loads(raw)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return _failure(json_error)


def _load_uploaded_documents(
    raw_batch: object,
) -> tuple[tuple[UploadedPilotDocument, ...], tuple[PilotManifestError, ...]]:
    if not isinstance(raw_batch, Mapping):
        return (), (PilotManifestError("invalid_batch_mapping", "$batch"),)

    documents: list[UploadedPilotDocument] = []
    errors: list[PilotManifestError] = []
    for raw_document_id, raw_path in raw_batch.items():
        document_id = raw_document_id.strip() if isinstance(raw_document_id, str) else None
        if document_id is None or not document_id:
            errors.append(PilotManifestError("invalid_batch_document_id", "$batch"))
            continue
        if not isinstance(raw_path, str) or not raw_path.strip():
            errors.append(PilotManifestError("invalid_batch_document_path", "$batch", document_id))
            continue
        try:
            content = Path(raw_path).read_bytes()
        except (OSError, ValueError):
            errors.append(PilotManifestError("unreadable_uploaded_document", "$batch", document_id))
            continue
        documents.append(UploadedPilotDocument(document_id=document_id, content=content))
    return tuple(documents), tuple(errors)


def _append_errors(
    validation: PilotManifestValidation,
    errors: Sequence[PilotManifestError],
) -> PilotManifestValidation:
    if not errors:
        return validation
    return PilotManifestValidation(
        client_id=validation.client_id,
        documents=validation.documents,
        errors=tuple(errors) + validation.errors,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida un manifiesto de piloto y un lote de documentos externos.",
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw_manifest = _read_json(
        args.manifest,
        file_error="unreadable_manifest",
        json_error="invalid_manifest_json",
    )
    if isinstance(raw_manifest, PilotManifestValidation):
        _emit(raw_manifest)
        return 1

    raw_batch = _read_json(
        args.batch,
        file_error="unreadable_batch_mapping",
        json_error="invalid_batch_mapping_json",
    )
    if isinstance(raw_batch, PilotManifestValidation):
        _emit(raw_batch)
        return 1

    uploaded_documents, batch_errors = _load_uploaded_documents(raw_batch)
    validation = validate_pilot_manifest_json(
        json.dumps(raw_manifest),
        uploaded_documents,
    )
    validation = _append_errors(validation, batch_errors)
    _emit(validation)
    return 0 if validation.valid else 1


def _emit(validation: PilotManifestValidation) -> None:
    print(json.dumps(validation.as_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
