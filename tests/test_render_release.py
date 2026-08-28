from __future__ import annotations

from pathlib import Path

import pytest

from scripts import deploy_certified_render as release


ROOT = Path(__file__).parents[1]
COMMIT = "a" * 40


def test_trigger_deploy_envia_el_commit_certificado(monkeypatch):
    calls = []

    def fake_request(method, url, api_key, payload=None):
        calls.append((method, url, api_key, payload))
        return {
            "id": "dep-123",
            "status": "created",
            "commit": {"id": COMMIT},
        }

    monkeypatch.setattr(release, "_request_json", fake_request)

    deploy_id = release.trigger_deploy("secret", "srv-123", COMMIT)

    assert deploy_id == "dep-123"
    assert calls == [
        (
            "POST",
            "https://api.render.com/v1/services/srv-123/deploys",
            "secret",
            {"commitId": COMMIT},
        )
    ]


def test_trigger_deploy_rechaza_un_commit_distinto(monkeypatch):
    monkeypatch.setattr(
        release,
        "_request_json",
        lambda *args, **kwargs: {
            "id": "dep-123",
            "status": "created",
            "commit": {"id": "b" * 40},
        },
    )

    with pytest.raises(RuntimeError, match="distinto del certificado"):
        release.trigger_deploy("secret", "srv-123", COMMIT)


def test_trigger_deploy_rechaza_una_respuesta_sin_commit(monkeypatch):
    monkeypatch.setattr(
        release,
        "_request_json",
        lambda *args, **kwargs: {"id": "dep-123", "status": "created"},
    )

    with pytest.raises(RuntimeError, match="no informó el commit"):
        release.trigger_deploy("secret", "srv-123", COMMIT)


def test_wait_for_deploy_confirma_estado_live_y_commit(monkeypatch):
    responses = iter(
        [
            {"id": "dep-123", "status": "build_in_progress", "commitId": COMMIT},
            {"id": "dep-123", "status": "live", "commitId": COMMIT},
        ]
    )
    monkeypatch.setattr(
        release,
        "_request_json",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(release.time, "sleep", lambda seconds: None)

    status = release.wait_for_deploy(
        "secret",
        "srv-123",
        "dep-123",
        COMMIT,
        timeout_seconds=60,
        poll_seconds=1,
    )

    assert status == "live"


def test_wait_for_deploy_propaga_un_estado_fallido(monkeypatch):
    monkeypatch.setattr(
        release,
        "_request_json",
        lambda *args, **kwargs: {
            "id": "dep-123",
            "status": "build_failed",
            "commitId": COMMIT,
        },
    )

    with pytest.raises(RuntimeError, match="build_failed"):
        release.wait_for_deploy(
            "secret",
            "srv-123",
            "dep-123",
            COMMIT,
            timeout_seconds=60,
            poll_seconds=1,
        )


def test_workflow_despliega_el_hash_certificado_y_evitar_ejecuciones_obsoletas():
    source = (ROOT / ".github" / "workflows" / "release-gate.yml").read_text()

    assert "cancel-in-progress: true" in source
    assert (
        'git fetch origin "$GITHUB_REF_NAME:refs/remotes/origin/$GITHUB_REF_NAME"'
        in source
    )
    assert 'git rev-parse "origin/$GITHUB_REF_NAME"' in source
    assert "secrets.RENDER_API_KEY" in source
    assert "secrets.RENDER_SERVICE_ID" in source
    assert "python scripts/deploy_certified_render.py" in source
    assert "DEPLOYED_COMMIT=$GITHUB_SHA" in source
