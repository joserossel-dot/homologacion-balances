"""Validación determinista de manifiestos externos para el piloto.

El módulo no abre documentos, no persiste estado y no interpreta nombres de
archivo. Su única entrada documental son bytes asociados a identificadores o
tokens opacos. La autorización se resuelve contra el manifiesto por SHA-256,
sin convertir un nombre de archivo en evidencia contable.

Los identificadores ``pilot_id``, ``client_id`` y ``document_id`` se limitan
a ASCII alfanumérico, ``-`` y ``_`` (uno a 64 caracteres, empezando y
terminando en alfanumérico). Esta regla rechaza espacios, rutas y extensiones
con punto. Es una comprobación de formato seguro, no una afirmación de que un
identificador sea semánticamente opaco.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any


_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_OPAQUE_ID = re.compile(
    r"^(?:[A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9_-]{0,62}[A-Za-z0-9])$",
)
_MIN_CLOSING_YEAR = 1900
_MAX_CLOSING_YEAR = 2200
_MAX_DOCUMENTS = 10


@dataclass(frozen=True)
class UploadedPilotDocument:
    """Un documento recibido, identificado sólo por su id opaco."""

    document_id: str
    content: bytes


@dataclass(frozen=True)
class PilotManifestError:
    """Error estructurado que no expone contenido, rutas ni hashes."""

    code: str
    path: str
    document_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "path": self.path,
            "document_id": self.document_id,
        }


@dataclass(frozen=True)
class AuthorizedPilotDocument:
    """Metadatos seguros del documento que superó la validación estructural."""

    document_id: str
    confirmed_closing_year: int | None

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "document_id": self.document_id,
            "confirmed_closing_year": self.confirmed_closing_year,
        }


@dataclass(frozen=True)
class PilotManifestValidation:
    """Resultado serializable de validar un manifiesto y una tanda de bytes."""

    client_id: str | None
    documents: tuple[AuthorizedPilotDocument, ...]
    errors: tuple[PilotManifestError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "client_id": self.client_id,
            "documents": [document.as_dict() for document in self.documents],
            "errors": [error.as_dict() for error in self.errors],
        }


@dataclass(frozen=True)
class PilotManifestUploadMatch:
    """Resultado seguro de autorizar archivos cargados por sus bytes.

    La clave de :attr:`token_to_document` es un token local y opaco de la
    interfaz. No es una identidad documental ni se compara con nombres de
    archivo. El mapeo sólo se entrega cuando la tanda completa es válida, para
    que una interfaz no pueda procesar una coincidencia parcial por error.
    """

    client_id: str | None
    documents: tuple[AuthorizedPilotDocument, ...]
    token_to_document: Mapping[str, AuthorizedPilotDocument]
    errors: tuple[PilotManifestError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        """Devuelve sólo ids opacos, años confirmados y errores seguros."""
        return {
            "valid": self.valid,
            "client_id": self.client_id,
            "documents": [document.as_dict() for document in self.documents],
            "token_to_document": {
                token: document.as_dict()
                for token, document in self.token_to_document.items()
            },
            "errors": [error.as_dict() for error in self.errors],
        }


@dataclass(frozen=True)
class _ManifestDocument:
    document_id: str
    sha256_hex: str | None
    confirmed_closing_year: int | None


@dataclass(frozen=True)
class _UploadedPilotContent:
    """Bytes de una carga identificada por un token local no documental."""

    token: str
    content: object


def validate_pilot_manifest_json(
    manifest_json: str | bytes | bytearray,
    uploaded_documents: Mapping[str, bytes] | Iterable[UploadedPilotDocument],
) -> PilotManifestValidation:
    """Parsea JSON y valida una tanda sin leer nombres de archivo.

    Los errores de JSON se devuelven como un resultado estructurado y no como
    excepciones. Ningún error contiene fragmentos del manifiesto, bytes,
    rutas, nombres de archivo ni hashes.
    """
    try:
        manifest = json.loads(manifest_json)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return PilotManifestValidation(
            client_id=None,
            documents=(),
            errors=(PilotManifestError("invalid_json", "$"),),
        )
    return validate_pilot_manifest(manifest, uploaded_documents)


def validate_pilot_manifest(
    manifest: object,
    uploaded_documents: Mapping[str, bytes] | Iterable[UploadedPilotDocument],
) -> PilotManifestValidation:
    """Valida la autorización de una tanda contra un manifiesto ya parseado.

    ``uploaded_documents`` puede ser un mapeo ``document_id -> bytes`` o una
    secuencia de :class:`UploadedPilotDocument`. La comparación se realiza por
    id opaco y SHA-256 del contenido. Los campos de nombres de archivo, si
    existen en un manifiesto de mayor nivel, se ignoran deliberadamente.
    """
    errors: list[PilotManifestError] = []
    client_id, manifest_documents = _validate_manifest(manifest, errors)

    batch = _normalise_uploaded_documents(uploaded_documents, errors)
    _validate_uploaded_documents(batch, errors)
    _compare_batch_with_manifest(manifest_documents, batch, errors)

    public_documents = tuple(
        AuthorizedPilotDocument(
            document_id=document.document_id,
            confirmed_closing_year=document.confirmed_closing_year,
        )
        for document in manifest_documents
    )
    return PilotManifestValidation(
        client_id=client_id,
        documents=public_documents,
        errors=tuple(errors),
    )


def match_pilot_manifest_uploads_json(
    manifest_json: str | bytes | bytearray,
    uploaded_contents: Mapping[str, bytes],
) -> PilotManifestUploadMatch:
    """Parsea JSON y autoriza una carga por SHA-256 de sus bytes.

    ``uploaded_contents`` relaciona exclusivamente un token local opaco de la
    interfaz con bytes. Ni el token ni el manifiesto se interpretan como un
    nombre de archivo y nunca se infiere el año desde ellos.
    """
    try:
        manifest = json.loads(manifest_json)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return PilotManifestUploadMatch(
            client_id=None,
            documents=(),
            token_to_document=MappingProxyType({}),
            errors=(PilotManifestError("invalid_json", "$"),),
        )
    return match_pilot_manifest_uploads(manifest, uploaded_contents)


def match_pilot_manifest_uploads(
    manifest: object,
    uploaded_contents: Mapping[str, bytes],
) -> PilotManifestUploadMatch:
    """Autoriza todas las cargas de una tanda usando sólo contenido y SHA-256.

    Cada contenido cargado debe corresponder a exactamente un documento
    autorizado del manifiesto. La operación es todo o nada: ante un documento
    faltante, inesperado, duplicado o ambiguo, el resultado no contiene ningún
    mapeo utilizable. Los errores no exponen hashes, contenido, rutas ni
    nombres de archivo.
    """
    errors: list[PilotManifestError] = []
    client_id, manifest_documents = _validate_manifest(manifest, errors)
    uploaded = _normalise_uploaded_contents(uploaded_contents, errors)
    _validate_uploaded_contents(uploaded, errors)
    token_to_document = _match_uploaded_contents(
        manifest_documents,
        uploaded,
        errors,
    )

    public_documents = tuple(
        AuthorizedPilotDocument(
            document_id=document.document_id,
            confirmed_closing_year=document.confirmed_closing_year,
        )
        for document in manifest_documents
    )
    if errors:
        token_to_document = {}
    return PilotManifestUploadMatch(
        client_id=client_id,
        documents=public_documents,
        token_to_document=MappingProxyType(dict(token_to_document)),
        errors=tuple(errors),
    )


def _validate_manifest(
    manifest: object,
    errors: list[PilotManifestError],
) -> tuple[str | None, list[_ManifestDocument]]:
    if not isinstance(manifest, Mapping):
        errors.append(PilotManifestError("invalid_manifest", "$"))
        return None, []
    client_id = _validate_client(manifest, errors)
    return client_id, _validate_documents(manifest, client_id, errors)


def _validate_client(
    manifest: Mapping[str, Any],
    errors: list[PilotManifestError],
) -> str | None:
    pilot = manifest.get("pilot")
    if not isinstance(pilot, Mapping):
        errors.append(PilotManifestError("missing_pilot", "$.pilot"))
        return None

    _validate_opaque_id(
        pilot.get("pilot_id"),
        error_code="invalid_pilot_id",
        path="$.pilot.pilot_id",
        errors=errors,
    )
    return _validate_opaque_id(
        pilot.get("client_id"),
        error_code="invalid_client_id",
        path="$.pilot.client_id",
        errors=errors,
    )


def _validate_documents(
    manifest: Mapping[str, Any],
    client_id: str | None,
    errors: list[PilotManifestError],
) -> list[_ManifestDocument]:
    raw_documents = manifest.get("documents")
    if not isinstance(raw_documents, list):
        errors.append(PilotManifestError("invalid_documents", "$.documents"))
        return []
    if not 1 <= len(raw_documents) <= _MAX_DOCUMENTS:
        errors.append(PilotManifestError("document_count_out_of_range", "$.documents"))

    _validate_declared_document_limit(manifest, len(raw_documents), errors)

    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    documents: list[_ManifestDocument] = []
    for index, raw_document in enumerate(raw_documents):
        path = f"$.documents[{index}]"
        if not isinstance(raw_document, Mapping):
            errors.append(PilotManifestError("invalid_document", path))
            continue

        document = _validate_document(raw_document, path, client_id, errors)
        if document is None:
            continue
        if document.document_id in seen_ids:
            errors.append(
                PilotManifestError(
                    "duplicate_document_id", f"{path}.document_id", document.document_id,
                ),
            )
        else:
            seen_ids.add(document.document_id)
        if document.sha256_hex is not None:
            if document.sha256_hex in seen_hashes:
                errors.append(
                    PilotManifestError(
                        "duplicate_document_sha256", f"{path}.sha256", document.document_id,
                    ),
                )
            else:
                seen_hashes.add(document.sha256_hex)
        documents.append(document)
    return documents


def _validate_declared_document_limit(
    manifest: Mapping[str, Any],
    document_count: int,
    errors: list[PilotManifestError],
) -> None:
    pilot = manifest.get("pilot")
    if not isinstance(pilot, Mapping) or "max_authorized_documents" not in pilot:
        return
    declared_limit = pilot["max_authorized_documents"]
    if (
        isinstance(declared_limit, bool)
        or not isinstance(declared_limit, int)
        or not 1 <= declared_limit <= _MAX_DOCUMENTS
    ):
        errors.append(
            PilotManifestError(
                "invalid_max_authorized_documents",
                "$.pilot.max_authorized_documents",
            ),
        )
    elif document_count > declared_limit:
        errors.append(
            PilotManifestError(
                "authorized_document_limit_exceeded",
                "$.documents",
            ),
        )


def _validate_document(
    raw_document: Mapping[str, Any],
    path: str,
    client_id: str | None,
    errors: list[PilotManifestError],
) -> _ManifestDocument | None:
    document_id = _validate_opaque_id(
        raw_document.get("document_id"),
        error_code="invalid_document_id",
        path=f"{path}.document_id",
        errors=errors,
    )
    if document_id is None:
        return None

    _validate_document_client(raw_document, path, document_id, client_id, errors)
    _validate_document_status(raw_document, path, document_id, errors)
    sha256_hex = _validate_document_hash(raw_document, path, document_id, errors)
    year = _validate_closing_year(raw_document, path, document_id, errors)
    _validate_year_evidence(raw_document, path, document_id, errors)
    return _ManifestDocument(
        document_id=document_id,
        sha256_hex=sha256_hex,
        confirmed_closing_year=year,
    )


def _validate_document_status(
    raw_document: Mapping[str, Any],
    path: str,
    document_id: str,
    errors: list[PilotManifestError],
) -> None:
    if "status" not in raw_document:
        errors.append(
            PilotManifestError("missing_document_status", f"{path}.status", document_id),
        )
    elif raw_document["status"] != "AUTHORIZED":
        errors.append(
            PilotManifestError("unauthorized_document_status", f"{path}.status", document_id),
        )


def _validate_document_client(
    raw_document: Mapping[str, Any],
    path: str,
    document_id: str,
    client_id: str | None,
    errors: list[PilotManifestError],
) -> None:
    if "client_id" not in raw_document:
        return
    document_client_id = _validate_opaque_id(
        raw_document["client_id"],
        error_code="invalid_document_client_id",
        path=f"{path}.client_id",
        errors=errors,
        document_id=document_id,
    )
    if document_client_id is not None and client_id is not None and document_client_id != client_id:
        errors.append(
            PilotManifestError("multiple_client_identifiers", f"{path}.client_id", document_id),
        )


def _validate_opaque_id(
    value: object,
    *,
    error_code: str,
    path: str,
    errors: list[PilotManifestError],
    document_id: str | None = None,
) -> str | None:
    """Acepta sólo el formato público de identificador opaco.

    El valor original no se incorpora al error si no cumple la gramática. El
    método no intenta deducir si un valor que sí cumple la gramática contiene
    información de cliente: esa comprobación semántica está fuera de alcance.
    """
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        errors.append(PilotManifestError(error_code, path, document_id))
        return None
    return value


def _safe_opaque_id(value: object) -> str | None:
    """Devuelve un identificador sintácticamente seguro sin normalizarlo."""
    if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
        return None
    return value


def _validate_document_hash(
    raw_document: Mapping[str, Any],
    path: str,
    document_id: str,
    errors: list[PilotManifestError],
) -> str | None:
    value = raw_document.get("sha256")
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        errors.append(PilotManifestError("invalid_document_sha256", f"{path}.sha256", document_id))
        return None
    return value.lower()


def _validate_closing_year(
    raw_document: Mapping[str, Any],
    path: str,
    document_id: str,
    errors: list[PilotManifestError],
) -> int | None:
    if "confirmed_closing_year" not in raw_document:
        errors.append(
            PilotManifestError(
                "missing_confirmed_closing_year",
                f"{path}.confirmed_closing_year",
                document_id,
            ),
        )
        return None
    year = raw_document["confirmed_closing_year"]
    if year is None:
        return None
    if isinstance(year, bool) or not isinstance(year, int):
        errors.append(
            PilotManifestError(
                "invalid_confirmed_closing_year",
                f"{path}.confirmed_closing_year",
                document_id,
            ),
        )
        return None
    if not _MIN_CLOSING_YEAR <= year <= _MAX_CLOSING_YEAR:
        errors.append(
            PilotManifestError(
                "invalid_confirmed_closing_year",
                f"{path}.confirmed_closing_year",
                document_id,
            ),
        )
        return None
    return year


def _validate_year_evidence(
    raw_document: Mapping[str, Any],
    path: str,
    document_id: str,
    errors: list[PilotManifestError],
) -> None:
    evidence = raw_document.get("closing_year_evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        errors.append(
            PilotManifestError(
                "missing_closing_year_evidence",
                f"{path}.closing_year_evidence",
                document_id,
            ),
        )


def _normalise_uploaded_contents(
    uploaded_contents: Mapping[str, bytes],
    errors: list[PilotManifestError],
) -> tuple[_UploadedPilotContent, ...]:
    """Normaliza tokens de carga sin convertirlos en ids documentales."""
    if not isinstance(uploaded_contents, Mapping):
        errors.append(PilotManifestError("invalid_uploaded_token_mapping", "$uploads"))
        return ()

    try:
        entries = tuple(uploaded_contents.items())
    except (TypeError, ValueError):
        errors.append(PilotManifestError("invalid_uploaded_token_mapping", "$uploads"))
        return ()

    uploaded: list[_UploadedPilotContent] = []
    seen_tokens: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$uploads[{index}]"
        try:
            raw_token, content = entry
        except (TypeError, ValueError):
            errors.append(PilotManifestError("invalid_uploaded_token_mapping", path))
            continue
        if not isinstance(raw_token, str) or not raw_token.strip():
            errors.append(PilotManifestError("invalid_uploaded_token", f"{path}.token"))
            continue
        token = raw_token.strip()
        if token in seen_tokens:
            errors.append(PilotManifestError("duplicate_uploaded_token", f"{path}.token"))
        else:
            seen_tokens.add(token)
        uploaded.append(_UploadedPilotContent(token=token, content=content))
    return tuple(uploaded)


def _validate_uploaded_contents(
    uploaded_contents: tuple[_UploadedPilotContent, ...],
    errors: list[PilotManifestError],
) -> None:
    if not 1 <= len(uploaded_contents) <= _MAX_DOCUMENTS:
        errors.append(PilotManifestError("uploaded_document_count_out_of_range", "$uploads"))

    seen_hashes: set[str] = set()
    for index, uploaded in enumerate(uploaded_contents):
        path = f"$uploads[{index}]"
        if not isinstance(uploaded.content, (bytes, bytearray, memoryview)):
            errors.append(PilotManifestError("invalid_uploaded_content", f"{path}.content"))
            continue
        content_hash = sha256(bytes(uploaded.content)).hexdigest()
        if content_hash in seen_hashes:
            errors.append(PilotManifestError("duplicate_uploaded_content", f"{path}.content"))
        else:
            seen_hashes.add(content_hash)


def _match_uploaded_contents(
    manifest_documents: list[_ManifestDocument],
    uploaded_contents: tuple[_UploadedPilotContent, ...],
    errors: list[PilotManifestError],
) -> dict[str, AuthorizedPilotDocument]:
    """Relaciona token local y documento autorizado sólo por hash de bytes."""
    documents_by_hash: dict[str, list[_ManifestDocument]] = {}
    for document in manifest_documents:
        if document.sha256_hex is not None:
            documents_by_hash.setdefault(document.sha256_hex, []).append(document)

    token_to_document: dict[str, AuthorizedPilotDocument] = {}
    matched_document_ids: set[str] = set()
    for uploaded in uploaded_contents:
        if not isinstance(uploaded.content, (bytes, bytearray, memoryview)):
            continue
        candidates = documents_by_hash.get(sha256(bytes(uploaded.content)).hexdigest(), [])
        if len(candidates) == 0:
            errors.append(PilotManifestError("unexpected_uploaded_content", "$uploads"))
            continue
        if len(candidates) > 1:
            errors.append(PilotManifestError("ambiguous_manifest_content", "$uploads"))
            continue

        document = candidates[0]
        if document.document_id in matched_document_ids:
            # Este caso normalmente también fue informado como contenido
            # duplicado. La señal específica evita que una tanda incompleta
            # parezca completa si el llamador ignora la primera señal.
            errors.append(PilotManifestError("duplicate_uploaded_content", "$uploads"))
            continue
        matched_document_ids.add(document.document_id)
        token_to_document[uploaded.token] = AuthorizedPilotDocument(
            document_id=document.document_id,
            confirmed_closing_year=document.confirmed_closing_year,
        )

    for candidates in documents_by_hash.values():
        if len(candidates) != 1:
            continue
        document = candidates[0]
        if document.document_id not in matched_document_ids:
            errors.append(
                PilotManifestError("missing_uploaded_document", "$uploads", document.document_id),
            )
    return token_to_document


def _normalise_uploaded_documents(
    uploaded_documents: Mapping[str, bytes] | Iterable[UploadedPilotDocument],
    errors: list[PilotManifestError],
) -> tuple[UploadedPilotDocument, ...]:
    if isinstance(uploaded_documents, Mapping):
        return tuple(
            UploadedPilotDocument(document_id=document_id, content=content)
            for document_id, content in uploaded_documents.items()
        )
    if isinstance(uploaded_documents, (str, bytes, bytearray)):
        errors.append(PilotManifestError("invalid_uploaded_documents", "$uploaded"))
        return ()
    try:
        entries = tuple(uploaded_documents)
    except TypeError:
        errors.append(PilotManifestError("invalid_uploaded_documents", "$uploaded"))
        return ()
    invalid_entries = [
        index for index, entry in enumerate(entries)
        if not isinstance(entry, UploadedPilotDocument)
    ]
    if invalid_entries:
        for index in invalid_entries:
            errors.append(PilotManifestError("invalid_uploaded_document", f"$uploaded[{index}]"))
        return ()
    return entries


def _validate_uploaded_documents(
    uploaded_documents: tuple[UploadedPilotDocument, ...],
    errors: list[PilotManifestError],
) -> None:
    if not 1 <= len(uploaded_documents) <= _MAX_DOCUMENTS:
        errors.append(PilotManifestError("uploaded_document_count_out_of_range", "$uploaded"))

    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for index, uploaded in enumerate(uploaded_documents):
        path = f"$uploaded[{index}]"
        document_id = _safe_opaque_id(uploaded.document_id)
        if document_id is None:
            errors.append(PilotManifestError("invalid_uploaded_document_id", f"{path}.document_id"))
            continue
        if document_id in seen_ids:
            errors.append(
                PilotManifestError("duplicate_uploaded_document_id", f"{path}.document_id", document_id),
            )
        else:
            seen_ids.add(document_id)

        content = uploaded.content
        if not isinstance(content, (bytes, bytearray, memoryview)):
            errors.append(PilotManifestError("invalid_uploaded_content", f"{path}.content", document_id))
            continue
        content_hash = sha256(bytes(content)).hexdigest()
        if content_hash in seen_hashes:
            errors.append(
                PilotManifestError("duplicate_uploaded_content", f"{path}.content", document_id),
            )
        else:
            seen_hashes.add(content_hash)


def _compare_batch_with_manifest(
    manifest_documents: list[_ManifestDocument],
    uploaded_documents: tuple[UploadedPilotDocument, ...],
    errors: list[PilotManifestError],
) -> None:
    expected_by_id: dict[str, _ManifestDocument] = {}
    for document in manifest_documents:
        expected_by_id.setdefault(document.document_id, document)

    uploaded_by_id: dict[str, UploadedPilotDocument] = {}
    for uploaded in uploaded_documents:
        document_id = _safe_opaque_id(uploaded.document_id)
        if document_id is not None:
            uploaded_by_id.setdefault(document_id, uploaded)

    for document_id in sorted(set(expected_by_id) - set(uploaded_by_id)):
        errors.append(
            PilotManifestError("missing_uploaded_document", "$uploaded", document_id),
        )
    for document_id in sorted(set(uploaded_by_id) - set(expected_by_id)):
        errors.append(
            PilotManifestError("unexpected_uploaded_document", "$uploaded", document_id),
        )

    for document_id in sorted(set(expected_by_id) & set(uploaded_by_id)):
        expected = expected_by_id[document_id]
        content = uploaded_by_id[document_id].content
        if expected.sha256_hex is None or not isinstance(content, (bytes, bytearray, memoryview)):
            continue
        if sha256(bytes(content)).hexdigest() != expected.sha256_hex:
            errors.append(
                PilotManifestError("content_sha256_mismatch", "$uploaded", document_id),
            )


__all__ = [
    "AuthorizedPilotDocument",
    "PilotManifestError",
    "PilotManifestUploadMatch",
    "PilotManifestValidation",
    "UploadedPilotDocument",
    "match_pilot_manifest_uploads",
    "match_pilot_manifest_uploads_json",
    "validate_pilot_manifest",
    "validate_pilot_manifest_json",
]
