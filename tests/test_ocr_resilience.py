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


def test_linea_ocr_preserva_ceros_finales_y_columna_activo():
    cuenta = parser.parsear_linea(
        "1010101 Caja 3,100,000 1,385,515 1,714,485 0 1714485 o 0 o",
        numero_linea=10,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo == "1010101"
    assert cuenta.nombre == "Caja"
    assert cuenta.monto == 1714485
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_vehiculo_queda_en_activo():
    cuenta = parser.parsear_linea(
        "1.02.03.03 Vehículos 23,871,062 o 23,871,062 O 23,871,062 o 0 o",
        numero_linea=33,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Vehículos"
    assert cuenta.monto == 23871062
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_tolera_ruido_breve_dentro_de_columnas_finales():
    cuenta = parser.parsear_linea(
        "1.01.02.01 Documentos en Garantía 2,550,000 0 2,550,000 O 2,550,000 o ly 0",
        numero_linea=12,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Documentos en Garantía"
    assert cuenta.monto == 2550000
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_recupera_codigo_con_un_separador_en_documento_punto():
    cuenta = parser.parsear_linea(
        "4.021201 Diferencias de cambio Perdida 572 o 572 o o o 572 o",
        numero_linea=80,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo == "4.021201"
    assert cuenta.monto == 572
    assert cuenta.origen_columna == parser.OrigenColumna.PERDIDA


def test_normaliza_slash_perdido_en_codigo_ocr():
    assert parser.normalizar_codigo_ocr("2/03.01.01 Capital 0 1,000,000") == (
        "2.03.01.01 Capital 0 1,000,000"
    )


def test_tabla_nativa_preserva_posicion_de_perdida_y_ganancia():
    class Pagina:
        @staticmethod
        def extract_tables():
            return [[
                ['Nombre', 'Débitos', 'Créditos', 'Saldo Deudor',
                 'Saldo Acreedor', 'Activo', 'Pasivo', 'Perdida', 'Ganancia'],
                ['COSTO MOTOS', '80.149.009', '2.864.000', '77.285.009',
                 '-', '-', '-', '77.285.009', '-'],
                ['VENTA MOTOS', '546.449.983', '4.215.989.922', '-',
                 '3.669.539.939', '-', '-', '-', '3.669.539.939'],
            ]]

    lineas = parser._extraer_tabla_balance_8_columnas(Pagina())
    perdida = parser.parsear_linea(
        lineas[0], 1, parser.FormatoCodigo.SIN_CODIGO, '.', 1.0
    )
    ganancia = parser.parsear_linea(
        lineas[1], 2, parser.FormatoCodigo.SIN_CODIGO, '.', 1.0
    )

    assert perdida.nombre == 'COSTO MOTOS'
    assert perdida.monto == 77285009
    assert perdida.origen_columna == parser.OrigenColumna.PERDIDA
    assert ganancia.nombre == 'VENTA MOTOS'
    assert ganancia.monto == 3669539939
    assert ganancia.origen_columna == parser.OrigenColumna.GANANCIA
