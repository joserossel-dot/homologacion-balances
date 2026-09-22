"""Pruebas sintéticas y anonimizadas para prevención de regresiones en:
1. Atribución de columnas (Activo, Pasivo, Pérdida, Ganancia).
2. Segmentación de columnas paralelas (Side-by-Side).
3. Resiliencia OCR (ceros 'o'/'O' vs conjunciones, caracteres de tabla).
4. Manejo de rotación documental.
5. Detección y bloqueo de filas fusionadas o ambiguas con revisión obligatoria.

Todos los casos utilizan datos sintéticos y nombres genéricos sin información confidencial.
"""
from pathlib import Path
import pytest

import parser_universal as parser
from parser_universal import CuentaRaw, FormatoCodigo, OrigenColumna
from pipeline.homologation_pipeline import HomologationPipeline
from scripts.certify_local_corpus import _account_snapshot, _classify


# ─────────────────────────────────────────────────────────────────────────────
# 1. ATRIBUCIÓN DE COLUMNAS (ACTIVO, PASIVO, PÉRDIDA, GANANCIA)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("linea,nombre_exp,monto_exp,origen_exp", [
    ("1.1.01 CUENTA ACTIVO SYN 100.000 0 0 0", "CUENTA ACTIVO SYN", 100000.0, OrigenColumna.ACTIVO),
    ("2.1.01 CUENTA PASIVO SYN 0 250.000 0 0", "CUENTA PASIVO SYN", 250000.0, OrigenColumna.PASIVO),
    ("5.1.01 CUENTA PERDIDA SYN 0 0 320.000 0", "CUENTA PERDIDA SYN", 320000.0, OrigenColumna.PERDIDA),
    ("4.1.01 CUENTA GANANCIA SYN 0 0 0 480.000", "CUENTA GANANCIA SYN", 480000.0, OrigenColumna.GANANCIA),
])
def test_atribucion_4_columnas_finales_sinteticas(linea, nombre_exp, monto_exp, origen_exp):
    """Verifica que una línea con 4 columnas posicionales asigne monto y origen esperado."""
    cuenta = parser.parsear_linea(linea, 1, FormatoCodigo.PUNTO, ".")
    assert cuenta is not None
    assert cuenta.nombre == nombre_exp
    assert cuenta.monto == monto_exp
    assert cuenta.origen_columna == origen_exp
    assert cuenta.requiere_revision_extraccion is False


@pytest.mark.parametrize("linea,nombre_exp,monto_exp,origen_exp,columna_clave", [
    ("110101 CAJA_SYN 100 0 100 0 100 0 0 0", "CAJA_SYN", 100.0, OrigenColumna.ACTIVO, "activo"),
    ("210101 PROVEEDOR_SYN 0 200 0 200 0 200 0 0", "PROVEEDOR_SYN", 200.0, OrigenColumna.PASIVO, "pasivo"),
    ("510101 GASTO_SYN 300 0 300 0 0 0 300 0", "GASTO_SYN", 300.0, OrigenColumna.PERDIDA, "perdida"),
    ("410101 INGRESO_SYN 0 400 0 400 0 0 0 400", "INGRESO_SYN", 400.0, OrigenColumna.GANANCIA, "ganancia"),
])
def test_atribucion_8_columnas_tributarias_sinteticas(linea, nombre_exp, monto_exp, origen_exp, columna_clave):
    """Verifica la asignación de columnas canónicas en formato tributario de 8 columnas."""
    cuenta = parser.parsear_linea(linea, 1, FormatoCodigo.COMPACTO, ".")
    assert cuenta is not None
    assert cuenta.nombre == nombre_exp
    assert cuenta.monto == monto_exp
    assert cuenta.origen_columna == origen_exp
    assert cuenta.montos_columnas.get(columna_clave) == monto_exp
    assert cuenta.requiere_revision_extraccion is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEGMENTACIÓN DE COLUMNAS LADO A LADO (SIDE-BY-SIDE)
# ─────────────────────────────────────────────────────────────────────────────

def test_side_by_side_dos_cuentas_independientes_sinteticas():
    """Líneas con 2 cuentas paralelas con código y monto se dividen limpiamente."""
    linea = "1.1.01 CAJA_CENTRAL_SYN 1.500.000 2.1.01 PROVEEDOR_LOCAL_SYN 2.500.000"
    partes = parser.split_side_by_side(linea)
    assert len(partes) == 2
    assert partes[0] == "1.1.01 CAJA_CENTRAL_SYN 1.500.000"
    assert partes[1] == "2.1.01 PROVEEDOR_LOCAL_SYN 2.500.000"

    c1 = parser.parsear_linea(partes[0], 1, FormatoCodigo.PUNTO, ".")
    c2 = parser.parsear_linea(partes[1], 2, FormatoCodigo.PUNTO, ".")

    assert c1 is not None and c2 is not None
    assert c1.codigo == "1.1.01" and c1.nombre == "CAJA_CENTRAL_SYN" and c1.monto == 1500000.0
    assert c2.codigo == "2.1.01" and c2.nombre == "PROVEEDOR_LOCAL_SYN" and c2.monto == 2500000.0
    assert c1.requiere_revision_extraccion is False
    assert c2.requiere_revision_extraccion is False


def test_side_by_side_tres_cuentas_recursivo_sintetico():
    """Línea compuesta por 3 cuentas con separadores y ceros OCR se separa sin pérdida."""
    linea = "CTA_ALPHA_SYN 100.000 0 o o CTA_BETA_SYN 200.000 o CTA_GAMMA_SYN"
    partes = parser.split_side_by_side(linea)
    assert len(partes) == 3
    assert partes[0] == "CTA_ALPHA_SYN 100.000 0 o o"
    assert partes[1] == "CTA_BETA_SYN 200.000 o"
    assert partes[2] == "CTA_GAMMA_SYN"

    c1 = parser.parsear_linea(partes[0], 1, FormatoCodigo.SIN_CODIGO, ".")
    c2 = parser.parsear_linea(partes[1], 2, FormatoCodigo.SIN_CODIGO, ".")
    c3 = parser.parsear_linea(partes[2], 3, FormatoCodigo.SIN_CODIGO, ".")

    assert c1 is not None and c1.nombre == "CTA_ALPHA_SYN" and c1.monto == 100000.0
    assert c2 is not None and c2.nombre == "CTA_BETA_SYN" and c2.monto == 200000.0
    assert c3 is not None and c3.nombre == "CTA_GAMMA_SYN" and c3.monto is None
    assert not c2.nombre.startswith("o ")


# ─────────────────────────────────────────────────────────────────────────────
# 3. RESILIENCIA OCR (CEROS 'o'/'O' VS CONJUNCIONES Y CARACTERES DE TABLA)
# ─────────────────────────────────────────────────────────────────────────────

def test_ocr_ceros_confundibles_en_celdas_ocho_columnas():
    """Ceros OCR representados como 'o', 'O', '—', '-' se normalizan a 0.0 en columnas."""
    linea = "110101 BANCO_SYN 100.000 o 100.000 — 100.000 o o o"
    cuenta = parser.parsear_linea(linea, 1, FormatoCodigo.COMPACTO, ".")
    assert cuenta is not None
    assert cuenta.nombre == "BANCO_SYN"
    assert cuenta.monto == 100000.0
    assert cuenta.origen_columna == OrigenColumna.ACTIVO
    assert cuenta.montos_columnas["debitos"] == 100000.0
    assert cuenta.montos_columnas["creditos"] == 0.0
    assert cuenta.montos_columnas["saldo_deudor"] == 100000.0
    assert cuenta.montos_columnas["saldo_acreedor"] == 0.0
    assert cuenta.montos_columnas["activo"] == 100000.0
    assert cuenta.montos_columnas["pasivo"] == 0.0
    assert cuenta.montos_columnas["perdida"] == 0.0
    assert cuenta.montos_columnas["ganancia"] == 0.0
    assert cuenta.requiere_revision_extraccion is False


def test_ocr_distingue_conjuncion_o_dentro_de_glosa():
    """La letra 'o' entre palabras de la glosa contable no debe partir la fila ni ser cero."""
    linea = "GASTOS DE TRASLADO O VIAJE 50.000"
    partes = parser.split_side_by_side(linea)
    assert len(partes) == 1
    assert partes[0] == linea

    cuenta = parser.parsear_linea(linea, 1, FormatoCodigo.SIN_CODIGO, ".")
    assert cuenta is not None
    assert cuenta.nombre == "GASTOS DE TRASLADO O VIAJE"
    assert cuenta.monto == 50000.0
    assert cuenta.requiere_revision_extraccion is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. MANEJO DE ROTACIÓN DOCUMENTAL
# ─────────────────────────────────────────────────────────────────────────────

def test_propaga_rotacion_simulada_en_parser_pdf(monkeypatch, tmp_path):
    """Verifica propagación de metadatos simulados, sin ejecutar detección ni OCR."""
    dummy_pdf = tmp_path / "rotacion_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    lineas_extraidas = [
        "110101 CAJA_SYN 100.000 0 100.000 0 100.000 0 0 0",
    ]

    monkeypatch.setattr(parser, "validar_archivo", lambda p: (True, ""))
    monkeypatch.setattr(
        parser.ParserPDF,
        "_extraer_lineas",
        lambda self, p, ctx: (list(lineas_extraidas), False, 180),
    )
    monkeypatch.setattr(parser, "extraer_encabezados_documento_pdf", lambda p: [])

    pdf_parser = parser.ParserPDF()
    resultado = pdf_parser.parsear(dummy_pdf)

    assert resultado is not None
    assert resultado.rotacion_aplicada == 180
    assert len(resultado.cuentas) == 1
    c = resultado.cuentas[0]
    assert c.nombre == "CAJA_SYN"
    assert c.monto == 100000.0
    assert c.origen_columna == OrigenColumna.ACTIVO
    assert c.requiere_revision_extraccion is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. FILAS FUSIONADAS Y REVISIÓN OBLIGATORIA
# ─────────────────────────────────────────────────────────────────────────────

def test_fila_fusionada_inseparable_obliga_revision_humana():
    """Fila con glosas múltiples y monto intermedio inseparable exige revisión y baja confianza."""
    linea_inseparable = "CUENTA ALPHA SYN 15.000.000 CUENTA BETA SYN"
    reasons = parser.detectar_linea_sospechosa(linea_inseparable, mediana_longitud=20.0)
    assert "multiples_glosas_separadas_por_monto" in reasons

    cuenta = parser.parsear_linea(linea_inseparable, 1, FormatoCodigo.SIN_CODIGO, ".")
    assert cuenta is not None
    parser.marcar_cuenta_sospechosa(cuenta, linea_inseparable, reasons)

    assert cuenta.requiere_revision_extraccion is True
    assert cuenta.confianza_extraccion <= 0.35

    # Verificación en contrato de snapshot y clasificación
    snapshot = _account_snapshot([cuenta], {
        "rows": [{"line": 1, "code": "AC.01", "review": False}],
    })
    assert len(snapshot) == 1
    assert snapshot[0]["requires_review"] is True
    assert "multiples_glosas_separadas_por_monto" in snapshot[0]["extraction_review_reasons"]


def test_cuenta_con_origen_desconocido_en_pipeline_requiere_revision(tmp_path):
    """Una cuenta con origen desconocido y sin código compatible queda sujeta a revisión."""
    cuenta = CuentaRaw(
        linea=10,
        codigo=None,
        nombre="GLOSA_AMBIGUA_SYN",
        monto=500000.0,
        montos_periodos={"2024": 500000.0},
        origen_columna=OrigenColumna.DESCONOCIDO,
        requiere_revision_extraccion=False,
    )
    pipeline = HomologationPipeline(db_path=tmp_path / "learning.db", dictionary=[])
    classification = _classify([cuenta], pipeline)
    assert classification["eligible"] == 1
    assert classification["automatic"] == 0
    assert classification["rows"][0]["review"] is True

    snapshot = _account_snapshot([cuenta], classification)
    assert len(snapshot) == 1
    assert snapshot[0]["line"] == 10
    assert snapshot[0]["origin"] == "desconocido"
    assert snapshot[0]["amount"] == 500000.0
    assert snapshot[0]["requires_review"] is True
