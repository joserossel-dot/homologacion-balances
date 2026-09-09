import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from scripts.release_attestation import create_attestation, verify_attestation


pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="OpenSSL no está disponible",
)


def _keys(tmp_path):
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key)],
        check=True,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
    )
    return private_key, public_key


def _inputs(tmp_path):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(json.dumps({"cases": [{
        "file": "a.pdf", "required_for_release": True,
        "expect": {"certification_state": "certificada"},
    }]}), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(json.dumps([{
        "file": "a.pdf", "status": "ok", "expectations_passed": True,
        "sha256": "a" * 64,
        "certification": {"state": "certificada"},
    }]), encoding="utf-8")
    return manifest, report


def test_signed_attestation_binds_commit_manifests_and_required_results(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    commit = "a" * 40

    create_attestation(
        report=report, manifests=[manifest], commit_sha=commit,
        private_key=private_key, output=attestation,
    )
    payload = verify_attestation(
        attestation=attestation, manifests=[manifest], commit_sha=commit,
        public_key=public_key,
    )

    assert payload["commit_sha"] == commit
    assert payload["required_cases"] == [{
        "file": "a.pdf", "sha256": "a" * 64, "status": "approved",
    }]


def test_attestation_rejects_tampered_payload(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    create_attestation(
        report=report, manifests=[manifest], commit_sha="a" * 40,
        private_key=private_key, output=attestation,
    )
    envelope = json.loads(attestation.read_text(encoding="utf-8"))
    envelope["payload"]["commit_sha"] = "b" * 40
    attestation.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(ValueError, match="OpenSSL rechazó"):
        verify_attestation(
            attestation=attestation, manifests=[manifest], commit_sha="b" * 40,
            public_key=public_key,
        )


def test_attestation_rejects_different_commit_even_with_valid_signature(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    create_attestation(
        report=report, manifests=[manifest], commit_sha="a" * 40,
        private_key=private_key, output=attestation,
    )

    with pytest.raises(ValueError, match="otro commit"):
        verify_attestation(
            attestation=attestation, manifests=[manifest], commit_sha="b" * 40,
            public_key=public_key,
        )


def test_attestation_rejects_incomplete_private_report(tmp_path):
    private_key, _ = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    report.write_text(json.dumps([{
        "file": "a.pdf", "status": "ok", "expectations_passed": False,
    }]), encoding="utf-8")

    with pytest.raises(ValueError, match="no aprobó"):
        create_attestation(
            report=report, manifests=[manifest], commit_sha="a" * 40,
            private_key=private_key, output=tmp_path / "attestation.json",
        )


def test_attestation_rejects_partial_result_even_if_flag_is_true(tmp_path):
    private_key, _ = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    rows = json.loads(report.read_text(encoding="utf-8"))
    rows[0]["certification"] = {"state": "parcial"}
    report.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="no está certificada"):
        create_attestation(
            report=report, manifests=[manifest], commit_sha="a" * 40,
            private_key=private_key, output=tmp_path / "attestation.json",
        )


def test_attestation_rejects_document_hash_different_from_manifest(tmp_path):
    private_key, _ = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    manifest.write_text(json.dumps({"cases": [{
        "file": "a.pdf", "required_for_release": True,
        "expect": {
            "certification_state": "certificada", "sha256": "b" * 64,
        },
    }]}), encoding="utf-8")

    with pytest.raises(ValueError, match="no coincide con el manifiesto"):
        create_attestation(
            report=report, manifests=[manifest], commit_sha="a" * 40,
            private_key=private_key, output=tmp_path / "attestation.json",
        )


def test_attestation_rejects_manifest_changed_after_signature(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    create_attestation(
        report=report, manifests=[manifest], commit_sha="a" * 40,
        private_key=private_key, output=attestation,
    )
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8",
    )

    with pytest.raises(ValueError, match="manifiestos cambiaron"):
        verify_attestation(
            attestation=attestation, manifests=[manifest], commit_sha="a" * 40,
            public_key=public_key,
        )


def test_attestation_rejects_expired_replay(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    issued_at = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
    create_attestation(
        report=report, manifests=[manifest], commit_sha="a" * 40,
        private_key=private_key, output=attestation, valid_for_hours=1,
        now=issued_at,
    )

    with pytest.raises(ValueError, match="expiró"):
        verify_attestation(
            attestation=attestation, manifests=[manifest], commit_sha="a" * 40,
            public_key=public_key, now=issued_at + timedelta(hours=2),
        )


def test_attestation_rejects_future_issued_at(tmp_path):
    private_key, public_key = _keys(tmp_path)
    manifest, report = _inputs(tmp_path)
    attestation = tmp_path / "attestation.json"
    verification_time = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
    create_attestation(
        report=report, manifests=[manifest], commit_sha="a" * 40,
        private_key=private_key, output=attestation,
        now=verification_time + timedelta(days=30),
    )

    with pytest.raises(ValueError, match="emisión futura"):
        verify_attestation(
            attestation=attestation, manifests=[manifest], commit_sha="a" * 40,
            public_key=public_key, now=verification_time,
        )
