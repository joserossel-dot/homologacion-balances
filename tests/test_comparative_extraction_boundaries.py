"""Regresiones sintéticas de fronteras entre filas de estados comparativos."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import parser_universal as parser


def test_total_no_absorbe_encabezado_de_la_siguiente_seccion():
    rows = [
        parser.CuentaRaw(1, None, "Total activos corrientes", 150, es_total=True),
        parser.CuentaRaw(2, None, "Activos no corrientes", 0),
        parser.CuentaRaw(3, None, "Propiedades, planta y equipo", 200),
    ]
    actual, merged = parser.fusionar_continuaciones_verticales(rows)
    assert merged == 0
    assert [row.nombre for row in actual] == [
        "Total activos corrientes", "Activos no corrientes",
        "Propiedades, planta y equipo",
    ]


def test_cuenta_cero_con_importe_comparativo_no_es_continuacion():
    rows = [
        parser.CuentaRaw(1, None, "Gasto de administración", -500),
        parser.CuentaRaw(
            2, None, "Otros gastos, por función", 0,
            montos_periodos={"2024": 0, "2023": -25},
        ),
    ]
    actual, merged = parser.fusionar_continuaciones_verticales(rows)
    assert merged == 0
    assert len(actual) == 2
    assert actual[1].montos_periodos == {"2024": 0, "2023": -25}


def test_cuenta_corta_sin_monto_no_se_fusiona_por_longitud():
    rows = [
        parser.CuentaRaw(1, None, "Total pasivos", 150, es_total=True),
        parser.CuentaRaw(2, None, "Patrimonio", 0),
        parser.CuentaRaw(3, None, "Capital emitido", 70),
        parser.CuentaRaw(4, None, "Otras reservas", 0),
    ]
    actual, merged = parser.fusionar_continuaciones_verticales(rows)
    assert merged == 0
    assert len(actual) == 4


def test_fuente_no_upright_sin_giro_recupera_tabla_por_coordenadas(monkeypatch):
    # Una escala vertical negativa puede marcar upright=False sin girar la
    # dirección de lectura. Las palabras siguen avanzando horizontalmente.
    page = MagicMock()
    page.chars = [
        {"upright": False, "matrix": (1, 0, 0, -1, 0, 0)}
        for _ in range(100)
    ]
    page.extract_text.return_value = "I n g r e s o s 1 0 0 8 0"
    words = []
    for line_index, label in enumerate(("Ventas", "Costos", "Margen", "Gastos", "Resultado")):
        words.extend([
            {"text": label, "x0": 10, "x1": 50, "top": line_index * 15},
            {"text": "100", "x0": 100, "x1": 120, "top": line_index * 15},
            {"text": "80", "x0": 150, "x1": 170, "top": line_index * 15},
        ])
    page.extract_words.return_value = words
    pdf = MagicMock()
    pdf.__enter__.return_value.pages = [page]
    monkeypatch.setattr(parser.pdfplumber, "open", lambda _: pdf)
    monkeypatch.setattr(parser, "_pagina_comparativa_con_texto_nativo_corrupto", lambda *_: True)
    engine = parser.ParserPDF()
    engine._ocr_advertencias = []
    engine._extraction_confidence = 1.0
    lines, ocr, rotation = engine._extraer_lineas(Path("synthetic.pdf"))
    assert lines == [f"{label} 100 80" for label in ("Ventas", "Costos", "Margen", "Gastos", "Resultado")]
    assert not ocr
    assert rotation == 0
    assert engine._extraction_confidence == 0.75


@pytest.mark.parametrize("direction", [-1, 1])
def test_rotacion_real_conserva_lectura_vertical(direction):
    page = MagicMock()
    text = "CAJA 100"
    page.chars = [
        {
            "text": character, "x0": 50, "x1": 56,
            "top": 700 - direction * index * 5,
            "bottom": 705 - direction * index * 5,
            "upright": False,
            "matrix": (0, direction, -direction, 0, 0, 0),
        }
        for index, character in enumerate(text)
    ]
    assert parser.ParserPDF._extraer_lineas_pagina_orientada(page) == [text]


def test_sufijo_acumulados_se_conserva_como_cuenta_no_control():
    rows = [
        parser.CuentaRaw(1, None, "RESULTADOS", 100),
        parser.CuentaRaw(2, None, "ACUMULADOS", 0),
    ]
    actual, merged = parser.fusionar_continuaciones_verticales(rows)
    assert merged == 1
    assert actual[0].nombre == "RESULTADOS ACUMULADOS"
    assert not actual[0].es_total


def test_resultado_con_cero_ocr_no_absorbe_sumas_totales():
    lines = [
        "Resultado positivo O O O O O 250 250 O",
        "Sumas totales 1000 1000 750 750 500 500 400 400",
    ]
    assert parser.asociar_lineas_verticales(lines) == lines
    accounts = [
        parser.parsear_linea(line, index, parser.FormatoCodigo.SIN_CODIGO, ".", 0.75)
        for index, line in enumerate(lines)
    ]
    assert all(account is not None and account.es_total for account in accounts)
    assert accounts[0].nombre == "Resultado positivo"
    assert accounts[0].montos_columnas["pasivo"] == 250
    assert accounts[1].nombre == "Sumas totales"
