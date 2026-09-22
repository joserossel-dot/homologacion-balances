"""Pruebas de regresión y certificación para P0.1: Fusión de filas/cuentas durante OCR.

Verifica:
1. Reproducción y resolución de fusión de filas paralelas/side-by-side.
2. Preservación de cuentas independientes con sus montos respectivos.
3. Tratamiento de filas ambiguas/contaminadas: no se clasifican automáticamente y exigen revisión humana.
4. Ausencia de falsos positivos en glosas contables legítimas de varias palabras (IFRS y tributarias).
"""
import pytest
import parser_universal as parser
from pipeline.homologation_pipeline import HomologationPipeline
from scripts.certify_local_corpus import _account_snapshot


# ─────────────────────────────────────────────────────────────────────────────
# 1. REPRODUCCIÓN Y PRESERVACIÓN DE CUENTAS INDEPENDIENTES
# ─────────────────────────────────────────────────────────────────────────────

def test_split_side_by_side_reproduce_y_resuelve_fila_ocr_real():
    """Reproduce y resuelve la fusión de fila OCR real:
    'MB 82.810 0 o o BANCO CHILE 1.190.267.012 o BANCO SANTANDER'

    Antes del fix: se producía una partición inválida ('MB 82.810 0 o') y otra
    contaminada ('o BANCO CHILE 1.190.267.012 o BANCO SANTANDER').
    Con el fix: se divide limpiamente en 3 cuentas sin contaminación ni pérdida.
    """
    linea_real = "MB 82.810 0 o o BANCO CHILE 1.190.267.012 o BANCO SANTANDER"
    partes = parser.split_side_by_side(linea_real)
    assert len(partes) == 3
    assert partes[0] == "MB 82.810 0 o o"
    assert partes[1] == "BANCO CHILE 1.190.267.012 o"
    assert partes[2] == "BANCO SANTANDER"

    c1 = parser.parsear_linea(partes[0], 1, parser.FormatoCodigo.SIN_CODIGO, ".")
    c2 = parser.parsear_linea(partes[1], 2, parser.FormatoCodigo.SIN_CODIGO, ".")
    c3 = parser.parsear_linea(partes[2], 3, parser.FormatoCodigo.SIN_CODIGO, ".")

    assert c1 is not None
    assert c1.nombre == "MB"
    assert c1.monto == 82810.0

    assert c2 is not None
    assert c2.nombre == "BANCO CHILE"
    assert c2.monto == 1190267012.0
    assert not c2.nombre.startswith("o ")

    assert c3 is not None
    assert c3.nombre == "BANCO SANTANDER"
    assert c3.monto is None

    # Clasificación contextual en pipeline para BANCO CHILE limpio
    pipeline = HomologationPipeline()
    res = pipeline._classify_by_regex_contextual(c2.nombre, account_tipo="ACTIVO")
    assert res is not None
    assert res["standard_code"] == "AC.01"


def test_ruta_real_extraccion_parser_pdf_ocr_fila_real(monkeypatch, tmp_path):
    """Valida la resolución a través de la ruta real de extracción de ParserPDF.parsear."""
    dummy_pdf = tmp_path / "balance_ocr_test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    lineas_real = [
        "MB 82.810 0 o o BANCO CHILE 1.190.267.012 o BANCO SANTANDER",
        "500.000",
    ]

    # Mock de bajo nivel para simular extracción OCR de la página
    monkeypatch.setattr(parser, "validar_archivo", lambda p: (True, ""))
    monkeypatch.setattr(
        parser.ParserPDF,
        "_extraer_lineas",
        lambda self, p, ctx: (list(lineas_real), True, 0),
    )
    monkeypatch.setattr(
        parser,
        "extraer_encabezados_documento_pdf",
        lambda p: [],
    )

    pdf_parser = parser.ParserPDF()
    resultado = pdf_parser.parsear(dummy_pdf)

    assert resultado is not None
    assert len(resultado.cuentas) == 3

    nombres = [c.nombre for c in resultado.cuentas]
    assert nombres == ["MB", "BANCO CHILE", "BANCO SANTANDER"]

    # Validar montos extraídos
    c_mb = resultado.cuentas[0]
    assert c_mb.nombre == "MB"
    assert c_mb.monto == 82810.0

    c_bch = resultado.cuentas[1]
    assert c_bch.nombre == "BANCO CHILE"
    assert c_bch.monto == 1190267012.0
    assert not c_bch.nombre.startswith("o ")

    c_bsan = resultado.cuentas[2]
    assert c_bsan.nombre == "BANCO SANTANDER"
    assert c_bsan.monto == 500000.0


def test_split_side_by_side_preserva_dos_cuentas_cortas():
    """Líneas con dos cuentas y montos paralelos de menos de 6 tokens no deben fusionarse."""
    linea = "CAJA 5.519.080 PROVEEDORES 3.200.000"
    partes = parser.split_side_by_side(linea)
    assert len(partes) == 2
    assert partes[0] == "CAJA 5.519.080"
    assert partes[1] == "PROVEEDORES 3.200.000"

    c1 = parser.parsear_linea(partes[0], 1, parser.FormatoCodigo.SIN_CODIGO, ".")
    c2 = parser.parsear_linea(partes[1], 2, parser.FormatoCodigo.SIN_CODIGO, ".")

    assert c1 is not None and c2 is not None
    assert c1.nombre == "CAJA"
    assert c1.monto == 5519080.0
    assert c2.nombre == "PROVEEDORES"
    assert c2.monto == 3200000.0


def test_split_side_by_side_con_nombres_compuestos_y_codigos():
    """Líneas lado a lado con códigos contables o nombres de varias palabras se dividen limpiamente."""
    linea = "1.1.01 BANCO DE CHILE 1.250.000 2.1.01 CLIENTES NACIONALES 850.000"
    partes = parser.split_side_by_side(linea)
    assert len(partes) == 2
    assert partes[0] == "1.1.01 BANCO DE CHILE 1.250.000"
    assert partes[1] == "2.1.01 CLIENTES NACIONALES 850.000"

    c1 = parser.parsear_linea(partes[0], 1, parser.FormatoCodigo.PUNTO, ".")
    c2 = parser.parsear_linea(partes[1], 2, parser.FormatoCodigo.PUNTO, ".")

    assert c1 is not None and c2 is not None
    assert c1.codigo == "1.1.01"
    assert c1.nombre == "BANCO DE CHILE"
    assert c1.monto == 1250000.0
    assert c2.codigo == "2.1.01"
    assert c2.nombre == "CLIENTES NACIONALES"
    assert c2.monto == 850000.0


def test_asociar_lineas_verticales_no_fusiona_fila_con_saldo_cero():
    """Una cuenta con saldo guión (-) u OCR cero no debe absorber la fila siguiente que inicia con conector."""
    lineas = [
        "CAJA -",
        "POR COBRAR A TERCEROS 5.000.000",
        "BANCO ESTADO 0",
        "DEUDORES VARIOS 1.500.000",
    ]
    asociadas = parser.asociar_lineas_verticales(lineas)
    assert len(asociadas) == 4
    assert asociadas[0] == "CAJA -"
    assert asociadas[1] == "POR COBRAR A TERCEROS 5.000.000"
    assert asociadas[2] == "BANCO ESTADO 0"
    assert asociadas[3] == "DEUDORES VARIOS 1.500.000"


# ─────────────────────────────────────────────────────────────────────────────
# 2. DETECCIÓN Y BLOQUEO DE FILAS AMBIGUAS / FUSIONADAS
# ─────────────────────────────────────────────────────────────────────────────

def test_fila_ambigua_fusionada_bloquea_clasificacion_automatica():
    """Una glosa contaminada con monto intermedio irreducible no debe clasificarse automáticamente."""
    linea_fusa = "CAJA 5.519.080 PROVEEDORES"
    reasons = parser.detectar_linea_sospechosa(linea_fusa, mediana_longitud=20.0)
    assert "multiples_glosas_separadas_por_monto" in reasons

    cuenta = parser.parsear_linea(linea_fusa, 10, parser.FormatoCodigo.SIN_CODIGO, ".")
    assert cuenta is not None
    parser.marcar_cuenta_sospechosa(cuenta, linea_fusa, reasons)

    assert cuenta.requiere_revision_extraccion is True
    assert cuenta.confianza_extraccion <= 0.35

    # En el pipeline y la certificación, la cuenta sospechosa exige revisión humana
    snapshot = _account_snapshot([cuenta], {
        "rows": [{"line": 10, "code": "AC.01", "review": False}],
    })
    assert len(snapshot) == 1
    assert snapshot[0]["requires_review"] is True
    assert "multiples_glosas_separadas_por_monto" in snapshot[0]["extraction_review_reasons"]


def test_snapshot_certificacion_refleja_revision_obligatoria_para_fused_account():
    """El verificador de corpus/certificación marca requires_review=True para cuentas sospechosas."""
    cuenta = parser.CuentaRaw(
        linea=1,
        codigo=None,
        nombre="Caja 1.000.000 Proveedores",
        monto=1000000.0,
        requiere_revision_extraccion=True,
        razones_revision_extraccion=["multiples_glosas_separadas_por_monto"],
        confianza_extraccion=0.35,
    )
    snapshot = _account_snapshot([cuenta], {
        "rows": [{"line": 1, "code": "AC.01", "review": False}],
    })
    assert len(snapshot) == 1
    assert snapshot[0]["requires_review"] is True
    assert "multiples_glosas_separadas_por_monto" in snapshot[0]["extraction_review_reasons"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. AUSENCIA DE REGRESIÓN PARA GLOSAS CONTABLES LEGÍTIMAS DE VARIAS PALABRAS
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("glosa,monto_esperado", [
    ("OBLIGACIONES CON BANCOS LARGO PLAZO 45.000.000", 45000000.0),
    ("PROPIEDADES, PLANTA Y EQUIPO NETO 150.000.000", 150000000.0),
    ("GASTOS DE ADMINISTRACION Y VENTAS 12.350.000", 12350000.0),
    ("CUENTAS POR COBRAR COMERCIALES (1.200.000)", -1200000.0),
    ("IMPUESTOS POR RECUPERAR LEY 19880 2.500.000", 2500000.0),
    ("DEUDORES POR VENTAS Y SERVICIOS 8.900.000", 8900000.0),
    ("CONTRATOS DE ARRENDAMIENTO FINANCIERO 3.400.000", 3400000.0),
    ("PROVISIONES POR BENEFICIOS A LOS EMPLEADOS 6.700.000", 6700000.0),
])
def test_glosas_contables_legitimas_no_sufren_falsa_particion(glosa, monto_esperado):
    """Glosas legítimas complejas no deben partirse ni marcarse falsamente como sospechosas."""
    partes = parser.split_side_by_side(glosa)
    assert len(partes) == 1
    assert partes[0] == glosa

    reasons = parser.detectar_linea_sospechosa(glosa, mediana_longitud=30.0)
    assert reasons == []

    cuenta = parser.parsear_linea(glosa, 1, parser.FormatoCodigo.SIN_CODIGO, ".")
    assert cuenta is not None
    parser.marcar_cuenta_sospechosa(cuenta, glosa, reasons)

    assert cuenta.requiere_revision_extraccion is False
    assert cuenta.monto == monto_esperado
