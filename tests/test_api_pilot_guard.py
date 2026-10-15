"""Regression tests for the no-write pilot API boundary.

They use the ASGI callable directly because this repository does not install
the optional TestClient transport dependency.  The request helper records
whether the application ever asks for the request body.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from src.api import main as api


async def _request(
    *,
    method: str,
    path: str,
    body: bytes = b"customer-pdf-bytes-must-not-be-read",
) -> tuple[list[dict], int]:
    """Invoke the ASGI app and return response messages and body-read count."""
    messages: list[dict] = []
    receive_calls = 0

    async def receive() -> dict:
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    await api.app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"multipart/form-data; boundary=pilot"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        },
        receive,
        send,
    )
    return messages, receive_calls


def _response(messages: list[dict]) -> tuple[int, dict]:
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return start["status"], json.loads(body)


def test_lifespan_pilot_no_instancia_ni_inicializa_repositorio(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://must-not-connect.invalid/pilot")
    construction_calls: list[str] = []

    class RepositoryThatMustNotBeConstructed:
        def __init__(self) -> None:
            construction_calls.append("constructed")
            raise AssertionError("El piloto no debe construir el repositorio")

    monkeypatch.setattr(api, "RepositorioDiccionario", RepositoryThatMustNotBeConstructed)
    monkeypatch.setattr(api, "repositorio", object())

    async def exercise_lifespan() -> None:
        async with api.lifespan(api.app):
            assert api.repositorio is None

    asyncio.run(exercise_lifespan())

    assert construction_calls == []
    assert api.repositorio is None


def test_procesamiento_piloto_responde_503_sin_leer_cuerpo_multipart(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    messages, receive_calls = asyncio.run(
        _request(method="POST", path="/api/v1/analisis/procesar"),
    )

    status, payload = _response(messages)
    assert status == 503
    assert payload == {"detail": "API no disponible durante el piloto"}
    assert receive_calls == 0


def test_endpoint_directo_tambien_se_bloquea_antes_de_tocar_archivos(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")

    class UnreadableUpload:
        @property
        def filename(self):
            raise AssertionError("El guard no debe inspeccionar el archivo")

        @property
        def file(self):
            raise AssertionError("El guard no debe leer el archivo")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            api.procesar_analisis(
                UnreadableUpload(),
                UnreadableUpload(),
                giro_empresa="comercio",
            ),
        )

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail == "API no disponible durante el piloto"


def test_health_no_piloto_conserva_respuesta_existente(monkeypatch):
    monkeypatch.delenv("PILOT_MODE", raising=False)
    monkeypatch.setattr(api, "repositorio", object())

    messages, _ = asyncio.run(_request(method="GET", path="/health", body=b""))

    status, payload = _response(messages)
    assert status == 200
    assert payload == {"status": "ok", "repositorio": True}


def test_health_piloto_expone_solo_estado_seguro(monkeypatch):
    monkeypatch.setenv("PILOT_MODE", "1")
    monkeypatch.setattr(api, "repositorio", object())

    messages, _ = asyncio.run(_request(method="GET", path="/health", body=b""))

    status, payload = _response(messages)
    assert status == 200
    assert payload == {
        "status": "pilot_disabled",
        "repositorio": False,
        "pilot_mode": True,
    }
