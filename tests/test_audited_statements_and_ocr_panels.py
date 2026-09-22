"""Pruebas unitarias para estados financieros auditados, contrato PAT.04 y paneles OCR paralelos."""
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
from PIL import Image

from document_scope import contar_paginas_pdf
from parser_universal import (
    CuentaRaw,
    _es_linea_basura,
    detectar_años_y_monedas,
    normalizar_linea_ocr_tabla,
    _es_fragmento_decorativo_ocr,
    _extraer_paneles_paralelos_ocr,
    certificar_totales_clasificados,
)
from reporting_integrity import catalogo_local, conciliar_resultados
from app_validacion import _preparar_periodo_reporte


def _crear_fila(nombre, monto, origen, codigo="", es_total=False, es_subtotal=False, es_control=False):
    return {
        "codigo_clasificado": codigo,
        "nombre_original": nombre,
        "monto": monto,
        "origen_columna": origen,
        "es_total": es_total,
        "es_subtotal": es_subtotal,
        "es_control": es_control,
        "confianza": 0.95,
        "metodo": "test",
    }


# =============================================================================
# 1. PRUEBAS DEL CONTRATO PAT.04
# =============================================================================

def test_pat04_omitido_cuando_balance_ya_cuadra():
    """Si el balance ya cuadra de forma autónoma, PAT.04 no se inyecta y no duplica utilidad/pérdida."""
    cat = catalogo_local()
    filas = [
        # Activos = 1000
        _crear_fila("Caja y Bancos", 1000.0, "activo", "AC.01"),
        # Pasivos = 400
        _crear_fila("Proveedores", 400.0, "pasivo", "PC.01"),
        # Patrimonio = 600 (ya incluye resultado del ejercicio en resultados acumulados o patrimonio cerrado)
        _crear_fila("Capital Social", 600.0, "pasivo", "PAT.01"),
        # Estado de Resultados: Utilidad de 150
        _crear_fila("Ventas", 500.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 350.0, "perdida", "ER.02"),
    ]
    df = pd.DataFrame(filas)
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is True
    assert diag["pat04_status"] == "omitido_patrimonio_cerrado"
    assert "PAT.04" not in set(reporte["agrupado"]["codigo_clasificado"])
    assert diag["activo"] == 1000.0
    assert diag["pasivo_patrimonio"] == 1000.0


def test_pat04_incorporado_cuando_explica_diferencia():
    """Si el balance está descuadrado y el resultado del ejercicio explica exactamente la diferencia, PAT.04 se incorpora."""
    cat = catalogo_local()
    filas = [
        # Activos = 1000
        _crear_fila("Caja y Bancos", 1000.0, "activo", "AC.01"),
        # Pasivos = 400
        _crear_fila("Proveedores", 400.0, "pasivo", "PC.01"),
        # Patrimonio antes de resultado = 450 (falta utilidad de 150 para llegar a 1000)
        _crear_fila("Capital Social", 450.0, "pasivo", "PAT.01"),
        # Estado de Resultados: Utilidad de 150
        _crear_fila("Ventas", 500.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 350.0, "perdida", "ER.02"),
    ]
    df = pd.DataFrame(filas)
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is True
    assert diag["pat04_status"] == "derivado_incorporado"
    assert "PAT.04" in set(reporte["agrupado"]["codigo_clasificado"])
    pat04_row = reporte["agrupado"][reporte["agrupado"]["codigo_clasificado"] == "PAT.04"].iloc[0]
    assert pat04_row["monto_total"] == 150.0
    assert diag["activo"] == 1000.0
    assert diag["pasivo_patrimonio"] == 1000.0


def test_pat04_rechazado_cuando_no_explica_diferencia():
    """Si la diferencia en el balance no coincide con el resultado del ejercicio, no se inventa PAT.04 y se reporta el descuadre."""
    cat = catalogo_local()
    filas = [
        # Activos = 1000
        _crear_fila("Caja y Bancos", 1000.0, "activo", "AC.01"),
        # Pasivos = 400
        _crear_fila("Proveedores", 400.0, "pasivo", "PC.01"),
        # Patrimonio = 300 (descuadre de 300)
        _crear_fila("Capital Social", 300.0, "pasivo", "PAT.01"),
        # Estado de Resultados: Utilidad de 150 (no explica los 300)
        _crear_fila("Ventas", 500.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 350.0, "perdida", "ER.02"),
    ]
    df = pd.DataFrame(filas)
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is False
    assert diag["pat04_status"] == "rechazado_no_explica"
    assert "PAT.04" not in set(reporte["agrupado"]["codigo_clasificado"])
    assert diag["diferencia"] == 300.0


def test_pat04_ocr_admite_residuo_minimo_sin_ocultar_descuadre_material():
    """Un residuo OCR de pocos pesos no debe impedir incorporar una pérdida que cierra el balance."""
    cat = catalogo_local()
    filas = [
        _crear_fila("Caja y Bancos", 1_374_719_360.0, "activo", "AC.01"),
        _crear_fila("Capital", 1_437_541_691.0, "pasivo", "PAT.01"),
        _crear_fila("Ventas", 557_284_683.0, "ganancia", "ER.01"),
        _crear_fila("Costos", 620_107_008.0, "perdida", "ER.02"),
    ]
    reporte = _preparar_periodo_reporte(
        pd.DataFrame(filas), cat, "2021", 0, tolerancia=10.0,
    )

    assert reporte["diagnostico"]["pat04_status"] == "derivado_incorporado"
    assert reporte["diagnostico"]["cuadra"] is True
    pat04 = reporte["agrupado"].query("codigo_clasificado == 'PAT.04'").iloc[0]
    assert pat04["monto_total"] == -62_822_325.0


def test_pat04_explicito_no_se_duplica():
    """Si el balance ya contiene PAT.04 explícito, se conserva sin inyectar otro derivado."""
    cat = catalogo_local()
    filas = [
        _crear_fila("Caja y Bancos", 1000.0, "activo", "AC.01"),
        _crear_fila("Proveedores", 400.0, "pasivo", "PC.01"),
        _crear_fila("Capital Social", 450.0, "pasivo", "PAT.01"),
        _crear_fila("Resultado del Ejercicio", 150.0, "pasivo", "PAT.04"),
        _crear_fila("Ventas", 500.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 350.0, "perdida", "ER.02"),
    ]
    df = pd.DataFrame(filas)
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is True
    assert diag["pat04_status"] == "explicito"
    pat04_count = len(reporte["agrupado"][reporte["agrupado"]["codigo_clasificado"] == "PAT.04"])
    assert pat04_count == 1


def test_pat04_multiperiodo_evaluacion_independiente():
    """Cada período evalúa su propia condición PAT.04 de forma aislada."""
    cat = catalogo_local()
    filas_p1 = [
        _crear_fila("Caja y Bancos", 1000.0, "activo", "AC.01"),
        _crear_fila("Proveedores", 400.0, "pasivo", "PC.01"),
        _crear_fila("Capital Social", 450.0, "pasivo", "PAT.01"),
        _crear_fila("Ventas", 500.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 350.0, "perdida", "ER.02"),
    ]
    filas_p2 = [
        _crear_fila("Caja y Bancos", 800.0, "activo", "AC.01"),
        _crear_fila("Proveedores", 300.0, "pasivo", "PC.01"),
        _crear_fila("Capital Social", 500.0, "pasivo", "PAT.01"),
        _crear_fila("Ventas", 400.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 400.0, "perdida", "ER.02"),
    ]
    df1 = pd.DataFrame(filas_p1)
    df2 = pd.DataFrame(filas_p2)

    rep1 = _preparar_periodo_reporte(df1, cat, "2020", 0)
    rep2 = _preparar_periodo_reporte(df2, cat, "2019", 1)

    assert rep1["diagnostico"]["pat04_status"] == "derivado_incorporado"
    assert rep2["diagnostico"]["pat04_status"] == "omitido_patrimonio_cerrado"


# =============================================================================
# 2. PRUEBAS DE CONCILIACIÓN DEL ESTADO DE RESULTADOS Y SUBTOTALES
# =============================================================================

def test_conciliacion_resultados_excluye_subtotales_intermedios():
    """Los subtotales impresos en el PDF no se suman como detalle independiente."""
    cat = catalogo_local()
    filas = [
        _crear_fila("Ingresos Ordinarios", 1000.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 600.0, "perdida", "ER.02"),
        # Subtotal impreso que coincide con Ganancia Bruta (400)
        _crear_fila("Ganancia Bruta", 400.0, "ganancia", "", es_subtotal=True),
        _crear_fila("Gastos de Administración", 150.0, "perdida", "ER.04"),
        # Subtotal impreso que coincide con Resultado Operacional (250)
        _crear_fila("Resultado Operacional", 250.0, "ganancia", "", es_total=True),
    ]
    res = conciliar_resultados(filas, cat)
    assert res["cuadra"] is True
    assert res["resultado_origen"] == 250.0
    assert res["resultado_homologado"] == 250.0
    assert res["diferencia"] == 0.0


def test_conciliacion_resultados_detecta_controles_impresos():
    """Filas marcadas como control o encabezado se excluyen del cálculo de resultado homologado."""
    cat = catalogo_local()
    filas = [
        _crear_fila("Ventas Netas", 2000.0, "ganancia", "ER.01"),
        _crear_fila("Costo de Ventas", 1200.0, "perdida", "ER.02"),
        _crear_fila("CONTROL ENCABEZADO", 0.0, "control", "", es_control=True),
    ]
    res = conciliar_resultados(filas, cat)
    assert res["cuadra"] is True
    assert res["resultado_homologado"] == 800.0


def test_diagnostico_cuadratura_no_alerta_subtotales_excluidos_como_error():
    """Filas marcadas como subtotal o control con saldo no distorsionan la cobertura ni las excluidas."""
    filas = [
        _crear_fila("Activo Corriente", 500.0, "activo", "AC.01"),
        _crear_fila("Pasivo Corriente", 500.0, "pasivo", "PC.01"),
        _crear_fila("Subtotal Activos", 500.0, "activo", "__EXCLUIR__", es_subtotal=True),
        _crear_fila("Total Pasivos", 500.0, "pasivo", "__EXCLUIR__", es_total=True),
    ]
    df = pd.DataFrame(filas)
    cat = catalogo_local()
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is True
    assert len(diag["excluidas"]) == 0
    assert diag["total_cuentas"] == 2
    assert diag["cobertura"] == 1.0


def test_diagnostico_cuadratura_excluye_controles_en_cuentas_validas():
    """El total de cuentas en el diagnóstico no infla el denominador con líneas de control."""
    filas = [
        _crear_fila("Banco Estado", 300.0, "activo", "AC.01"),
        _crear_fila("Capital", 300.0, "pasivo", "PAT.01"),
        _crear_fila("Línea Control 1", 0.0, "control", "__EXCLUIR__", es_control=True),
    ]
    df = pd.DataFrame(filas)
    cat = catalogo_local()
    reporte = _preparar_periodo_reporte(df, cat, "2020", 0)
    diag = reporte["diagnostico"]

    assert diag["cuadra"] is True
    assert diag["total_cuentas"] == 2


# =============================================================================
# 3. PRUEBAS DE CONTEO DE PÁGINAS Y METADATOS
# =============================================================================

def test_contar_paginas_pdf_con_respaldo_pdfium():
    """Si pdfplumber retorna 0 páginas, PDFium recupera el conteo real y emite advertencia trazable."""
    with patch("pdfplumber.open") as mock_plumber, patch("pypdfium2.PdfDocument") as mock_pdfium:
        mock_plumber_doc = MagicMock()
        mock_plumber_doc.pages = []
        mock_plumber.return_value.__enter__.return_value = mock_plumber_doc

        mock_pdfium_doc = MagicMock()
        mock_pdfium_doc.__len__.return_value = 2
        mock_pdfium.return_value.__enter__.return_value = mock_pdfium_doc

        count, warnings = contar_paginas_pdf("dummy.pdf")
        assert count == 2
        assert len(warnings) == 1
        assert "PDFium recuperó 2 páginas válidas" in warnings[0]


def test_contar_paginas_pdf_ambos_fallan_retorna_cero():
    """Si ambos extractores fallan, retorna 0 páginas y advierte del fallo."""
    with patch("pdfplumber.open", side_effect=Exception("Error lectura")), \
         patch("pypdfium2.PdfDocument", side_effect=Exception("Error pdfium")):
        count, warnings = contar_paginas_pdf("dummy_roto.pdf")
        assert count == 0
        assert len(warnings) >= 1


def test_detectar_anios_y_monedas_encabezado_comparativo():
    """Detecta correctamente ambos años en cabeceras comparativas y monedas."""
    lineas = [
        "GIDDINGS BERRIES CHILE S.A.",
        "ESTADO DE SITUACION FINANCIERA",
        "ACTIVOS 2020 US$ 2019 US",
        "EFECTIVO Y EFECTIVO EQUIVALENTE 2.470.554 4.222.460",
    ]
    anios, monedas = detectar_años_y_monedas(lineas)
    assert anios == ["2020", "2019"]
    assert monedas == ["USD"]


def test_detectar_anios_y_monedas_multiples_anios_descendentes():
    """Detecta los dos años más relevantes en cabeceras comparativas."""
    lineas = [
        "BALANCE GENERAL AL 31 DE DICIEMBRE DE 2020 Y 2019 (EN PESOS)",
        "ACTIVOS 2020 2019",
        "Caja 100 200",
    ]
    anios, monedas = detectar_años_y_monedas(lineas)
    assert anios == ["2020", "2019"]
    assert monedas == ["CLP"]


# =============================================================================
# 4. PRUEBAS DE RUIDO Y LIMPIEZA OCR
# =============================================================================

def test_garbage_patterns_filtra_encabezados_y_preserva_saldos():
    """Los encabezados con meses, años o títulos de firmas se filtran, pero los saldos válidos se conservan."""
    assert _es_linea_basura("LOS NOGALES Diciembre 2019") is True
    assert _es_linea_basura("PASIVOS 2020 US 2019 US") is True
    assert _es_linea_basura("ESTADO DE RESULTADO | 2020US 2019US") is True
    assert _es_linea_basura("CFO Corporativo Holding Regional") is True
    assert _es_linea_basura("__P=") is True

    # Cuentas reales NO son basura
    assert _es_linea_basura("1.1.01 Caja y Bancos 2.019") is False
    assert _es_linea_basura("Gastos Diciembre 2.019 50.000") is False
    assert _es_linea_basura("PROVISION BENEFICIOS EMPLEADOS 531.474") is False


def test_garbage_patterns_descarta_pie_kame_ocr_con_cifras_adjuntas():
    assert _es_linea_basura(
        "httos://www.kameone.cl/Reporte/EmisionBalanceGeneral?"
        "fechaD=01/01/2023 fechaH=31/12/2023 emision=8 habilitar=S 1/4"
    ) is True
    assert _es_linea_basura("5 1 1 1 49 6 1593 2150 29 17 2/4") is True


def test_pagina_de_firmas_ocr_no_se_trata_como_tabla():
    from parser_universal import _es_pagina_firmas_ocr

    assert _es_pagina_firmas_ocr(
        "RUT: 13.884.014-6\nCONTADOR GENERAL\nVOB Gerencia\nFirma"
    ) is True
    assert _es_pagina_firmas_ocr(
        "KAME ONE Balance General\nwww.kameone.cl/Reporte/EmisionBalanceGeneral 4/4"
    ) is True
    assert _es_pagina_firmas_ocr(
        "CUENTA DEBITOS CREDITOS SALDO ACTIVO\n1.01.01 Caja 100 0 100 100"
    ) is False


def test_garbage_patterns_filtra_firmas_y_auditores():
    """Cargos y rótulos de firma se identifican sin codificar nombres propios."""
    assert _es_linea_basura("Firma Representante Legal") is True
    assert _es_linea_basura("Contador General") is True
    assert _es_linea_basura("Gerente General Holding Regional") is True


def test_normalizar_linea_ocr_limpia_prefijos_y_ruido_conectores():
    """Limpia letras aisladas al inicio, prefijos espurios y normaliza errores tipográficos comunes."""
    l1 = "A A RESULTADO ANTES DE IMPUESTO A LA RENTA ( 1.500.000 ) ( 1.200.000 )"
    assert "RESULTADO ANTES DE IMPUESTO A LA RENTA" in normalizar_linea_ocr_tabla(l1)
    assert not normalizar_linea_ocr_tabla(l1).startswith("A A")

    l2 = "E E EE A o IMPUESTO A LAS GANANCIAS ( 200.000 ) ( 150.000 )"
    assert normalizar_linea_ocr_tabla(l2).startswith("IMPUESTO A LAS GANANCIAS")

    l3 = "SANANCIABELAÑOS 1.300.000 1.050.000"
    assert normalizar_linea_ocr_tabla(l3).startswith("GANANCIA DEL AÑO")

    l4 = "roraL activos 10.680.068 62.671.342"
    norm4 = normalizar_linea_ocr_tabla(l4)
    assert norm4.startswith("TOTAL ACTIVOS")


def test_normalizar_linea_ocr_preserva_ceros_finales_de_ocho_columnas():
    """Las letras ``o`` de Tesseract son ceros, no basura de una glosa."""
    line = (
        "2.4.01.01 Capital Social | o 831.689.848 0 831.689.848 "
        "o 831.689.848 o o"
    )
    normalized = normalizar_linea_ocr_tabla(line)
    assert normalized.endswith("o 831.689.848 o o")


# =============================================================================
# 5. PRUEBAS DE RECONSTRUCCIÓN GEOMÉTRICA TSV Y PANELES PARALELOS
# =============================================================================

@pytest.fixture
def fake_image_path(tmp_path):
    img = Image.new("RGB", (1000, 1000), color="white")
    path = tmp_path / "fake_balance.png"
    img.save(path)
    return path


def test_reconstruccion_paneles_paralelos_tsv_sintetico(fake_image_path):
    """Reconstruye un balance en 2 paneles paralelos ordenando glosas y montos por Y."""
    words = [
        # Encabezados
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVOS", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        # Panel Izquierdo (Activos, Y in [280, 630])
        {"text": "EFECTIVO", "x0": 50, "x1": 150, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "1.000", "x0": 380, "x1": 420, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "800", "x0": 460, "x1": 500, "top": 300, "raw_top": 300, "yc": 300},
        # Panel Derecho (Pasivos, Y in [280, 630])
        {"text": "PROVEEDORES", "x0": 520, "x1": 650, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "1.000", "x0": 820, "x1": 860, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "800", "x0": 900, "x1": 940, "top": 300, "raw_top": 300, "yc": 300},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is not None
    assert "ACTIVOS" in res
    assert "PASIVOS" in res
    assert any("EFECTIVO 1.000 800" in line for line in res)
    assert any("PROVEEDORES 1.000 800" in line for line in res)


def test_reconstruccion_paneles_preserva_cuentas_saldo_cero(fake_image_path):
    """Cuentas con saldos '0 0' no se fusionan con renglones contiguos."""
    words = [
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVOS", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        # Fila 1: Activos Biológicos con ceros
        {"text": "ACTIVOS", "x0": 50, "x1": 120, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "BIOLOGICOS", "x0": 130, "x1": 220, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "0", "x0": 390, "x1": 410, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "0", "x0": 470, "x1": 490, "top": 350, "raw_top": 350, "yc": 350},
        # Fila 2: Deudores con saldo
        {"text": "DEUDORES", "x0": 50, "x1": 150, "top": 400, "raw_top": 400, "yc": 400},
        {"text": "500", "x0": 390, "x1": 410, "top": 400, "raw_top": 400, "yc": 400},
        {"text": "400", "x0": 470, "x1": 490, "top": 400, "raw_top": 400, "yc": 400},
        # Dummy pasivos para satisfacer ambos paneles
        {"text": "CAPITAL", "x0": 520, "x1": 650, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "500", "x0": 820, "x1": 860, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "400", "x0": 900, "x1": 940, "top": 350, "raw_top": 350, "yc": 350},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is not None
    assert any("ACTIVOS BIOLOGICOS 0 0" in line for line in res)
    assert any("DEUDORES 500 400" in line for line in res)


def test_fragmentos_decorativos_no_contaminan_cuenta_siguiente():
    assert _es_fragmento_decorativo_ocr("E E EE A o") is True
    assert _es_fragmento_decorativo_ocr("A A A A aa") is True
    assert _es_fragmento_decorativo_ocr("IMPUESTO A LAS GANANCIAS") is False
    assert _es_fragmento_decorativo_ocr("IVA DF") is False


def test_reconstruccion_paneles_relee_uno_ambiguo_como_cero(
    fake_image_path, monkeypatch,
):
    """Una segunda lectura confirmada evita inventar 1 donde la celda dice 0."""
    words = [
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVOS", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "CAJA", "x0": 50, "x1": 100, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "100", "x0": 390, "x1": 410, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "100", "x0": 470, "x1": 490, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "OTROS", "x0": 520, "x1": 580, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "PASIVOS", "x0": 590, "x1": 670, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "0", "x0": 820, "x1": 830, "top": 300, "raw_top": 300, "yc": 300, "conf": 80},
        {"text": "1", "x0": 900, "x1": 910, "top": 300, "raw_top": 300, "yc": 300, "conf": 39, "height": 18},
    ]
    completed = MagicMock(stdout="0\n")
    monkeypatch.setattr("parser_universal.subprocess.run", lambda *args, **kwargs: completed)

    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)

    assert res is not None
    assert any("OTROS PASIVOS 0 0" in line for line in res)


def test_reconstruccion_paneles_separa_reservas_y_acumulados(fake_image_path):
    """Otras Reservas (0 0) y Resultados Acumulados se emiten en líneas independientes."""
    words = [
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PATRIMONIO", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        # Activo dummy
        {"text": "CAJA", "x0": 50, "x1": 100, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "100", "x0": 390, "x1": 410, "top": 300, "raw_top": 300, "yc": 300},
        {"text": "100", "x0": 470, "x1": 490, "top": 300, "raw_top": 300, "yc": 300},
        # Patrimonio: Otras reservas
        {"text": "OTRAS", "x0": 520, "x1": 600, "top": 450, "raw_top": 450, "yc": 450},
        {"text": "RESERVAS", "x0": 610, "x1": 700, "top": 450, "raw_top": 450, "yc": 450},
        {"text": "0", "x0": 820, "x1": 840, "top": 450, "raw_top": 450, "yc": 450},
        {"text": "0", "x0": 900, "x1": 920, "top": 450, "raw_top": 450, "yc": 450},
        # Patrimonio: Resultados Acumulados
        {"text": "RESULTADOS", "x0": 520, "x1": 640, "top": 500, "raw_top": 500, "yc": 500},
        {"text": "ACUMULADOS", "x0": 650, "x1": 750, "top": 500, "raw_top": 500, "yc": 500},
        {"text": "24.786.136", "x0": 820, "x1": 870, "top": 500, "raw_top": 500, "yc": 500},
        {"text": "20.155.074", "x0": 900, "x1": 950, "top": 500, "raw_top": 500, "yc": 500},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is not None
    assert any("OTRAS RESERVAS 0 0" in line for line in res)
    assert any("RESULTADOS ACUMULADOS 24.786.136 20.155.074" in line for line in res)


def test_reconstruccion_paneles_repara_totales_degradados_ocr(fake_image_path):
    """Repara errores OCR en totales de balance como 'roraL activos 10.680.068' -> 70.880.068."""
    words = [
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVOS", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        # Total Activos degradado
        {"text": "roraL", "x0": 50, "x1": 100, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "activos", "x0": 110, "x1": 200, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "10.680.068", "x0": 380, "x1": 430, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "62.671.32", "x0": 460, "x1": 510, "top": 600, "raw_top": 600, "yc": 600},
        # Total Pasivos y Patrimonio degradado
        {"text": "TOTAL", "x0": 520, "x1": 570, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "PATRIMONIO", "x0": 580, "x1": 670, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "Y", "x0": 675, "x1": 685, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "PASIVOS", "x0": 690, "x1": 750, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "70.830.068", "x0": 820, "x1": 870, "top": 600, "raw_top": 600, "yc": 600},
        {"text": "62.671.32", "x0": 900, "x1": 950, "top": 600, "raw_top": 600, "yc": 600},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is not None
    assert any("TOTAL ACTIVOS 70.880.068 62.671.342" in line for line in res)
    assert any("TOTAL PATRIMONIO Y PASIVOS 70.880.068 62.671.342" in line for line in res)


def test_reconstruccion_paneles_descarta_firmas_pie_de_pagina(fake_image_path):
    """Palabras ubicadas en la zona de firmas (Y > 0.63h) son filtradas."""
    words = [
        {"text": "ACTIVOS", "x0": 50, "x1": 150, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVOS", "x0": 520, "x1": 600, "top": 100, "raw_top": 100, "yc": 100},
        # Cuerpo
        {"text": "CAJA", "x0": 50, "x1": 100, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "100", "x0": 390, "x1": 410, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "100", "x0": 470, "x1": 490, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "PROVEEDORES", "x0": 520, "x1": 650, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "100", "x0": 820, "x1": 860, "top": 350, "raw_top": 350, "yc": 350},
        {"text": "100", "x0": 900, "x1": 940, "top": 350, "raw_top": 350, "yc": 350},
        # Zona de firmas (Y > 630)
        {"text": "Jorge", "x0": 100, "x1": 200, "top": 850, "raw_top": 850, "yc": 850},
        {"text": "Salman", "x0": 210, "x1": 300, "top": 850, "raw_top": 850, "yc": 850},
        {"text": "Ricardo", "x0": 600, "x1": 700, "top": 850, "raw_top": 850, "yc": 850},
        {"text": "Ortiz", "x0": 710, "x1": 800, "top": 850, "raw_top": 850, "yc": 850},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is not None
    assert not any("Jorge" in line for line in res)
    assert not any("Ricardo" in line for line in res)


def test_certificar_totales_clasificados_balance_comparativo_con_montos_periodos():
    """certificar_totales_clasificados evalúa correctamente montos_periodos cuando monto es None."""
    cuentas = [
        CuentaRaw(
            linea=1,
            codigo="",
            nombre="TOTAL ACTIVOS",
            monto=None,
            es_total=True,
            montos_periodos={"actual": 70880068.0, "anterior": 62671342.0},
        ),
        CuentaRaw(
            linea=2,
            codigo="",
            nombre="TOTAL PATRIMONIO Y PASIVOS",
            monto=None,
            es_total=True,
            montos_periodos={"actual": 70880068.0, "anterior": 62671342.0},
        ),
    ]
    cert = certificar_totales_clasificados(cuentas)
    assert cert.estado == "parcial"
    assert cert.totales_finales_validos is True
    assert cert.totales_impresos["activo"] == 70880068.0
    assert cert.totales_impresos["pasivo_patrimonio"] == 70880068.0
    assert cert.diferencias["activo_menos_pasivo_patrimonio"] == 0.0


def test_extraer_paneles_paralelos_ocr_retorna_none_si_no_es_panel_doble(fake_image_path):
    """Si el documento no presenta estructura lado a lado de Activos y Pasivos, retorna None."""
    words = [
        {"text": "BALANCE", "x0": 100, "x1": 200, "top": 50, "raw_top": 50, "yc": 50},
        {"text": "GENERAL", "x0": 210, "x1": 300, "top": 50, "raw_top": 50, "yc": 50},
        {"text": "CAJA", "x0": 50, "x1": 100, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "1.000", "x0": 200, "x1": 250, "top": 100, "raw_top": 100, "yc": 100},
    ]
    res = _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words)
    assert res is None


def test_paneles_paralelos_no_degrada_balance_tributario_de_ocho_columnas(
    fake_image_path,
):
    """La presencia de Activo/Pasivo no convierte ocho columnas en dos paneles."""
    words = [
        {"text": "CUENTA", "x0": 30, "x1": 100, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "DEBITOS", "x0": 180, "x1": 250, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "CREDITOS", "x0": 280, "x1": 350, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "DEUDOR", "x0": 380, "x1": 440, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "ACREEDOR", "x0": 470, "x1": 540, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "ACTIVO", "x0": 570, "x1": 630, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PASIVO", "x0": 660, "x1": 720, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "PERDIDAS", "x0": 750, "x1": 820, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "GANANCIAS", "x0": 850, "x1": 930, "top": 100, "raw_top": 100, "yc": 100},
        {"text": "CAJA", "x0": 30, "x1": 80, "top": 250, "raw_top": 250, "yc": 250},
    ]

    assert _extraer_paneles_paralelos_ocr(fake_image_path, words_tsv=words) is None
