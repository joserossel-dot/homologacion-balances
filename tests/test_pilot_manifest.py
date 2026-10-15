from __future__ import annotations

from hashlib import sha256
import json

import pytest

from pilot_manifest import (
    UploadedPilotDocument,
    match_pilot_manifest_uploads,
    match_pilot_manifest_uploads_json,
    validate_pilot_manifest,
    validate_pilot_manifest_json,
)


def _hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def _document(
    document_id: str,
    content: bytes,
    *,
    confirmed_closing_year: int | None = 2024,
    closing_year_evidence: str = "visible-document-heading",
) -> dict[str, object]:
    return {
        "document_id": document_id,
        "status": "AUTHORIZED",
        "sha256": _hash(content),
        "confirmed_closing_year": confirmed_closing_year,
        "closing_year_evidence": closing_year_evidence,
    }


def _manifest(documents: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "pilot": {
            "pilot_id": "pilot-opaque-001",
            "client_id": "client-opaque-001",
            "max_authorized_documents": 10,
        },
        "documents": documents,
    }


def _codes(result) -> set[str]:
    return {error.code for error in result.errors}


def test_valid_manifest_matches_authorized_bytes_and_returns_safe_result():
    content = b"authorized balance contents"
    result = validate_pilot_manifest_json(
        json.dumps(_manifest([_document("doc-opaque-001", content)])),
        {"doc-opaque-001": content},
    )

    assert result.valid
    assert result.client_id == "client-opaque-001"
    assert result.documents[0].document_id == "doc-opaque-001"
    assert result.documents[0].confirmed_closing_year == 2024
    assert result.as_dict() == {
        "valid": True,
        "client_id": "client-opaque-001",
        "documents": [
            {
                "document_id": "doc-opaque-001",
                "confirmed_closing_year": 2024,
            },
        ],
        "errors": [],
    }


@pytest.mark.parametrize(
    ("field", "unsafe_id", "error_code"),
    [
        ("pilot_id", "pilot-batch.pdf", "invalid_pilot_id"),
        ("client_id", "client opaque 001", "invalid_client_id"),
        ("document_id", "../balance-2024", "invalid_document_id"),
    ],
)
def test_manifest_identity_ids_reject_unsafe_syntax_without_echoing_value(
    field: str,
    unsafe_id: str,
    error_code: str,
):
    content = b"authorized balance contents"
    manifest = _manifest([_document("doc-opaque-001", content)])
    if field == "document_id":
        manifest["documents"][0][field] = unsafe_id
    else:
        manifest["pilot"][field] = unsafe_id

    result = validate_pilot_manifest(manifest, {"doc-opaque-001": content})

    assert not result.valid
    assert error_code in _codes(result)
    assert unsafe_id not in json.dumps(result.as_dict())
    assert all(error.document_id != unsafe_id for error in result.errors)


@pytest.mark.parametrize(
    ("pilot_id", "client_id", "document_id"),
    [
        ("pilot-opaque-001", "client-opaque-001", "doc-opaque-001"),
        (
            "550e8400-e29b-41d4-a716-446655440000",
            "123e4567-e89b-12d3-a456-426614174000",
            "018f0b7f-6f06-7b73-a70b-6f66f4f64a8e",
        ),
    ],
)
def test_manifest_identity_ids_accept_safe_prefixes_and_reasonable_uuids(
    pilot_id: str,
    client_id: str,
    document_id: str,
):
    content = b"authorized balance contents"
    manifest = _manifest([_document(document_id, content)])
    manifest["pilot"]["pilot_id"] = pilot_id
    manifest["pilot"]["client_id"] = client_id

    result = validate_pilot_manifest(manifest, {document_id: content})

    assert result.valid
    assert result.client_id == client_id
    assert result.documents[0].document_id == document_id


def test_unsafe_uploaded_document_id_is_rejected_without_echoing_value():
    content = b"authorized balance contents"
    unsafe_id = "cliente real/balance.pdf"

    result = validate_pilot_manifest(
        _manifest([_document("doc-opaque-001", content)]),
        {unsafe_id: content},
    )

    assert not result.valid
    assert "invalid_uploaded_document_id" in _codes(result)
    assert unsafe_id not in json.dumps(result.as_dict())
    assert all(error.document_id != unsafe_id for error in result.errors)


def test_hash_mismatch_blocks_batch_without_exposing_hashes():
    expected = b"expected balance"
    result = validate_pilot_manifest(
        _manifest([_document("doc-opaque-001", expected)]),
        {"doc-opaque-001": b"different uploaded balance"},
    )

    assert not result.valid
    assert "content_sha256_mismatch" in _codes(result)
    assert all("expected" not in error.as_dict().values() for error in result.errors)
    assert all("different" not in error.as_dict().values() for error in result.errors)


def test_more_than_ten_documents_is_rejected():
    contents = [f"document-{index}".encode() for index in range(11)]
    documents = [
        _document(f"doc-opaque-{index:02d}", content)
        for index, content in enumerate(contents)
    ]
    batch = {
        f"doc-opaque-{index:02d}": content
        for index, content in enumerate(contents)
    }

    result = validate_pilot_manifest(_manifest(documents), batch)

    assert not result.valid
    assert "document_count_out_of_range" in _codes(result)
    assert "uploaded_document_count_out_of_range" in _codes(result)


def test_missing_year_evidence_is_rejected_even_when_year_is_unknown():
    content = b"document without confirmed period"
    result = validate_pilot_manifest(
        _manifest([
            _document(
                "doc-opaque-001",
                content,
                confirmed_closing_year=None,
                closing_year_evidence="   ",
            ),
        ]),
        {"doc-opaque-001": content},
    )

    assert not result.valid
    assert "missing_closing_year_evidence" in _codes(result)


def test_document_must_be_explicitly_authorized():
    content = b"not yet authorized"
    missing_status = _document("doc-opaque-missing", content)
    missing_status.pop("status")
    declined = _document("doc-opaque-declined", b"declined")
    declined["status"] = "PENDING"

    result = validate_pilot_manifest(
        _manifest([missing_status, declined]),
        {
            "doc-opaque-missing": content,
            "doc-opaque-declined": b"declined",
        },
    )

    assert not result.valid
    assert {"missing_document_status", "unauthorized_document_status"} <= _codes(result)


def test_duplicate_manifest_ids_and_hashes_are_rejected():
    first = b"first contents"
    second = b"second contents"
    documents = [
        _document("doc-opaque-001", first),
        _document("doc-opaque-001", second),
        _document("doc-opaque-003", first),
    ]
    batch = [
        UploadedPilotDocument("doc-opaque-001", first),
        UploadedPilotDocument("doc-opaque-003", first),
    ]

    result = validate_pilot_manifest(_manifest(documents), batch)

    assert not result.valid
    assert {"duplicate_document_id", "duplicate_document_sha256"} <= _codes(result)


def test_conflicting_document_client_id_is_rejected():
    content = b"one client only"
    document = _document("doc-opaque-001", content)
    document["client_id"] = "another-client-opaque"

    result = validate_pilot_manifest(
        _manifest([document]),
        {"doc-opaque-001": content},
    )

    assert not result.valid
    assert "multiple_client_identifiers" in _codes(result)


def test_filename_is_not_an_input_to_closing_year_inference():
    content = b"balance-2024.pdf"
    document = _document(
        "doc-opaque-001",
        content,
        confirmed_closing_year=None,
        closing_year_evidence="period cannot be confirmed from the visible source",
    )
    document["original_filename"] = "balance-2024.pdf"

    result = validate_pilot_manifest(
        _manifest([document]),
        {"doc-opaque-001": content},
    )

    assert result.valid
    assert result.documents[0].confirmed_closing_year is None


def test_json_parser_returns_structured_error_for_invalid_json():
    result = validate_pilot_manifest_json(
        "{not valid json",
        {"doc-opaque-001": b"ignored"},
    )

    assert not result.valid
    assert _codes(result) == {"invalid_json"}


def test_unexpected_and_missing_uploaded_documents_are_rejected():
    expected = b"expected"
    result = validate_pilot_manifest(
        _manifest([_document("doc-opaque-expected", expected)]),
        {"doc-opaque-unexpected": b"other"},
    )

    assert not result.valid
    assert {"missing_uploaded_document", "unexpected_uploaded_document"} <= _codes(result)


def test_upload_byte_matcher_maps_opaque_upload_tokens_to_authorized_documents():
    first = b"first authorized balance"
    second = b"second authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", first, confirmed_closing_year=2023),
            _document("doc-opaque-002", second, confirmed_closing_year=2024),
        ]),
        {
            "upload-token-01": first,
            "upload-token-02": second,
        },
    )

    assert result.valid
    assert result.token_to_document["upload-token-01"].as_dict() == {
        "document_id": "doc-opaque-001",
        "confirmed_closing_year": 2023,
    }
    assert result.token_to_document["upload-token-02"].as_dict() == {
        "document_id": "doc-opaque-002",
        "confirmed_closing_year": 2024,
    }
    assert result.as_dict()["token_to_document"] == {
        "upload-token-01": {
            "document_id": "doc-opaque-001",
            "confirmed_closing_year": 2023,
        },
        "upload-token-02": {
            "document_id": "doc-opaque-002",
            "confirmed_closing_year": 2024,
        },
    }


def test_upload_byte_matcher_matches_swapped_upload_order_by_content_not_token():
    first = b"first authorized balance"
    second = b"second authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", first),
            _document("doc-opaque-002", second),
        ]),
        {
            "local-upload-a": second,
            "local-upload-b": first,
        },
    )

    assert result.valid
    assert result.token_to_document["local-upload-a"].document_id == "doc-opaque-002"
    assert result.token_to_document["local-upload-b"].document_id == "doc-opaque-001"


def test_upload_byte_matcher_rejects_unknown_bytes_without_exposing_content_or_hash():
    authorized = b"authorized balance"
    unknown = b"private unknown balance"
    result = match_pilot_manifest_uploads(
        _manifest([_document("doc-opaque-001", authorized)]),
        {"local-upload-01": unknown},
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert {"unexpected_uploaded_content", "missing_uploaded_document"} <= _codes(result)
    serialized = json.dumps(result.as_dict())
    assert unknown.decode() not in serialized
    assert _hash(unknown) not in serialized


def test_upload_byte_matcher_rejects_duplicate_uploaded_bytes():
    first = b"first authorized balance"
    second = b"second authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", first),
            _document("doc-opaque-002", second),
        ]),
        {
            "local-upload-01": first,
            "local-upload-02": first,
        },
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert "duplicate_uploaded_content" in _codes(result)


def test_upload_byte_matcher_rejects_duplicate_normalized_tokens():
    first = b"first authorized balance"
    second = b"second authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", first),
            _document("doc-opaque-002", second),
        ]),
        {
            "local-upload": first,
            " local-upload ": second,
        },
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert "duplicate_uploaded_token" in _codes(result)


def test_upload_byte_matcher_rejects_missing_authorized_document():
    first = b"first authorized balance"
    second = b"second authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", first),
            _document("doc-opaque-002", second),
        ]),
        {"local-upload-01": first},
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert "missing_uploaded_document" in _codes(result)


def test_upload_byte_matcher_accepts_explicit_unknown_closing_year():
    content = b"balance with explicitly unknown period"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document(
                "doc-opaque-001",
                content,
                confirmed_closing_year=None,
                closing_year_evidence="source has no verifiable closing period",
            ),
        ]),
        {"local-upload-01": content},
    )

    assert result.valid
    assert result.token_to_document["local-upload-01"].confirmed_closing_year is None


def test_upload_byte_matcher_rejects_ambiguous_manifest_hash():
    content = b"one ambiguous authorized balance"
    result = match_pilot_manifest_uploads(
        _manifest([
            _document("doc-opaque-001", content),
            _document("doc-opaque-002", content),
        ]),
        {"local-upload-01": content},
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert {"duplicate_document_sha256", "ambiguous_manifest_content"} <= _codes(result)


def test_upload_byte_matcher_json_parser_returns_safe_error():
    result = match_pilot_manifest_uploads_json(
        "{not valid json",
        {"local-upload-01": b"ignored"},
    )

    assert not result.valid
    assert result.token_to_document == {}
    assert _codes(result) == {"invalid_json"}
