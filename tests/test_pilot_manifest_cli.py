from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts" / "validate_pilot_manifest.py"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _manifest(document_id: str, content: bytes) -> dict[str, object]:
    return {
        "pilot": {
            "pilot_id": "pilot-opaque-001",
            "client_id": "client-opaque-001",
        },
        "documents": [
            {
                "document_id": document_id,
                "status": "AUTHORIZED",
                "sha256": sha256(content).hexdigest(),
                "confirmed_closing_year": 2024,
                "closing_year_evidence": "visible-document-heading",
            },
        ],
    }


def _run(manifest: Path, batch: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--manifest",
            str(manifest),
            "--batch",
            str(batch),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_cli_emits_only_safe_structured_result_for_valid_batch(tmp_path):
    content = b"private balance bytes"
    document_path = tmp_path / "real-client-balance-2024.pdf"
    document_path.write_bytes(content)
    manifest_path = tmp_path / "manifest.json"
    batch_path = tmp_path / "batch.json"
    _write_json(manifest_path, _manifest("doc-opaque-001", content))
    _write_json(batch_path, {"doc-opaque-001": str(document_path)})

    completed = _run(manifest_path, batch_path)

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["valid"] is True
    assert payload["documents"] == [
        {"document_id": "doc-opaque-001", "confirmed_closing_year": 2024},
    ]
    assert str(document_path) not in completed.stdout
    assert sha256(content).hexdigest() not in completed.stdout
    assert content.decode() not in completed.stdout
    assert not completed.stderr


def test_cli_returns_one_for_unreadable_document_without_printing_path(tmp_path):
    content = b"private balance bytes"
    missing_path = tmp_path / "real-client-balance-2024.pdf"
    manifest_path = tmp_path / "manifest.json"
    batch_path = tmp_path / "batch.json"
    _write_json(manifest_path, _manifest("doc-opaque-001", content))
    _write_json(batch_path, {"doc-opaque-001": str(missing_path)})

    completed = _run(manifest_path, batch_path)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["valid"] is False
    assert "unreadable_uploaded_document" in {
        error["code"] for error in payload["errors"]
    }
    assert str(missing_path) not in completed.stdout
    assert not completed.stderr


def test_cli_rejects_unsafe_pilot_id_without_echoing_its_value(tmp_path):
    content = b"private balance bytes"
    document_path = tmp_path / "real-client-balance-2024.pdf"
    document_path.write_bytes(content)
    manifest_path = tmp_path / "manifest.json"
    batch_path = tmp_path / "batch.json"
    unsafe_pilot_id = "pilot batch.pdf"
    manifest = _manifest("doc-opaque-001", content)
    manifest["pilot"]["pilot_id"] = unsafe_pilot_id
    _write_json(manifest_path, manifest)
    _write_json(batch_path, {"doc-opaque-001": str(document_path)})

    completed = _run(manifest_path, batch_path)

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["valid"] is False
    assert "invalid_pilot_id" in {error["code"] for error in payload["errors"]}
    assert unsafe_pilot_id not in completed.stdout
    assert str(document_path) not in completed.stdout
    assert not completed.stderr
