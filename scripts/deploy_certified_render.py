from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RENDER_API_BASE_URL = "https://api.render.com/v1"
SUCCESS_STATUSES = {"live"}
FAILURE_STATUSES = {
    "build_failed",
    "canceled",
    "deactivated",
    "pre_deploy_failed",
    "update_failed",
}


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta el secreto requerido: {name}")
    return value


def _request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Render API respondió HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"No fue posible contactar Render API: {exc.reason}") from exc

    parsed = json.loads(body or "{}")
    if not isinstance(parsed, dict):
        raise RuntimeError("Render API devolvió una respuesta JSON inesperada")
    return parsed


def _deploy_payload(response: dict[str, Any]) -> dict[str, Any]:
    deploy = response.get("deploy", response)
    if not isinstance(deploy, dict):
        raise RuntimeError("Render API no devolvió un objeto de despliegue")
    return deploy


def _commit_id(deploy: dict[str, Any]) -> str:
    commit = deploy.get("commit")
    if isinstance(commit, dict):
        return str(commit.get("id") or "").strip()
    return str(deploy.get("commitId") or "").strip()


def _verify_commit(deploy: dict[str, Any], expected_commit: str) -> None:
    actual_commit = _commit_id(deploy)
    if not actual_commit:
        raise RuntimeError(
            "Render no informó el commit asociado al despliegue; "
            "no es posible certificar la versión activa"
        )
    if actual_commit != expected_commit:
        raise RuntimeError(
            "Render informó un commit distinto del certificado: "
            f"esperado={expected_commit}, recibido={actual_commit}"
        )


def trigger_deploy(
    api_key: str,
    service_id: str,
    expected_commit: str,
) -> str:
    response = _request_json(
        "POST",
        f"{RENDER_API_BASE_URL}/services/{service_id}/deploys",
        api_key,
        {"commitId": expected_commit},
    )
    deploy = _deploy_payload(response)
    _verify_commit(deploy, expected_commit)
    deploy_id = str(deploy.get("id") or "").strip()
    if not deploy_id:
        raise RuntimeError("Render API no devolvió el identificador del despliegue")
    return deploy_id


def wait_for_deploy(
    api_key: str,
    service_id: str,
    deploy_id: str,
    expected_commit: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = _request_json(
            "GET",
            f"{RENDER_API_BASE_URL}/services/{service_id}/deploys/{deploy_id}",
            api_key,
        )
        deploy = _deploy_payload(response)
        _verify_commit(deploy, expected_commit)
        status = str(deploy.get("status") or "").strip().lower()
        if status in SUCCESS_STATUSES:
            return status
        if status in FAILURE_STATUSES:
            raise RuntimeError(
                f"El despliegue certificado terminó con estado {status}"
            )
        time.sleep(poll_seconds)

    raise RuntimeError(
        f"Render no terminó el despliegue dentro de {timeout_seconds} segundos"
    )


def main() -> int:
    api_key = _required_env("RENDER_API_KEY")
    service_id = _required_env("RENDER_SERVICE_ID")
    expected_commit = _required_env("GITHUB_SHA")
    timeout_seconds = int(os.environ.get("RENDER_DEPLOY_TIMEOUT_SECONDS", "1200"))
    poll_seconds = int(os.environ.get("RENDER_DEPLOY_POLL_SECONDS", "10"))

    deploy_id = trigger_deploy(api_key, service_id, expected_commit)
    print(f"Despliegue solicitado: id={deploy_id}, commit={expected_commit}")
    status = wait_for_deploy(
        api_key,
        service_id,
        deploy_id,
        expected_commit,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    print(
        "Despliegue certificado verificado: "
        f"id={deploy_id}, commit={expected_commit}, estado={status}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
