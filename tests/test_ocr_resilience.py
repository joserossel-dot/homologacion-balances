from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

import parser_universal as parser


def _imagen_temporal(tmp_path: Path, size: tuple[int, int] = (100, 100)) -> Path:
    path = tmp_path / "pagina.png"
    Image.new("RGB", size, "white").save(path)
    return path


def test_tesseract_limita_hilos_en_instancias_pequenas():
    assert parser._tesseract_env()["OMP_THREAD_LIMIT"] == "1"


def test_ocr_timeout_no_aborta_documento(monkeypatch, tmp_path, caplog):
    imagen = _imagen_temporal(tmp_path)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(parser.subprocess, "run", timeout)

    assert parser.ocr_pagina(imagen, 0) == ""
    assert "OCR excedió" in caplog.text


def test_ocr_timeout_reintenta_con_imagen_reducida(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (200, 200))
    monkeypatch.setattr(parser, "OCR_MAX_PIXELS", 100_000)
    monkeypatch.setattr(parser, "OCR_RETRY_MAX_PIXELS", 10_000)
    llamadas = []

    def ejecutar(cmd, **kwargs):
        llamadas.append((Path(cmd[1]), kwargs["timeout"]))
        if len(llamadas) == 1:
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        with Image.open(cmd[1]) as img:
            assert img.width * img.height <= parser.OCR_RETRY_MAX_PIXELS
        return subprocess.CompletedProcess(cmd, 0, stdout="Caja 100\n", stderr="")

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina(imagen, 0) == "Caja 100\n"
    assert [timeout for _, timeout in llamadas] == [
        parser.OCR_PAGE_TIMEOUT_SECONDS,
        parser.OCR_RETRY_TIMEOUT_SECONDS,
    ]


def test_ocr_reduce_imagen_grande_antes_de_tesseract(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (200, 200))
    monkeypatch.setattr(parser, "OCR_MAX_PIXELS", 10_000)
    observado = {}

    def ejecutar(cmd, **kwargs):
        entrada = Path(cmd[1])
        with Image.open(entrada) as img:
            observado["pixeles"] = img.width * img.height
        return subprocess.CompletedProcess(cmd, 0, stdout="Caja 100\n", stderr="")

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina(imagen, 0) == "Caja 100\n"
    assert observado["pixeles"] <= parser.OCR_MAX_PIXELS


def test_ocr_error_de_tesseract_devuelve_vacio(monkeypatch, tmp_path, caplog):
    imagen = _imagen_temporal(tmp_path)

    monkeypatch.setattr(
        parser.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="language data unavailable"
        ),
    )

    assert parser.ocr_pagina(imagen, 0) == ""
    assert "Tesseract falló" in caplog.text


def test_parseo_sin_texto_expone_advertencia_ocr(monkeypatch, tmp_path):
    pdf = tmp_path / "grande.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(parser, "validar_archivo", lambda path: (True, "OK"))
    monkeypatch.setattr(parser.ParserPDF, "_analizar_documento", lambda self, path: None)

    def sin_texto(self, path, context):
        self._ocr_advertencias.append("Página 1: OCR sin texto utilizable")
        return [], True, 0

    monkeypatch.setattr(parser.ParserPDF, "_extraer_lineas", sin_texto)

    resultado = parser.ParserPDF().parsear(pdf)

    assert resultado.requirio_ocr is True
    assert "Página 1: OCR sin texto utilizable" in resultado.advertencias
    assert "No se pudo extraer texto" in resultado.advertencias[-1]
