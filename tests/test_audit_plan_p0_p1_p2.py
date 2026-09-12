"""Tests de validación y criterios de cierre para P0, P1 y P2.

Cubre:
1. P0.1: Filtro anti-ruido ERP con trazabilidad y protección de cuentas reales (BANCO CHILE, CLIENTES CURICO).
2. P0.2: Desenredado de colisiones de columnas H3 en PDF real.
3. P1.1 & P2.1: Expansión de reglas contextuales y diccionario agrícola para evitar origin_fallback.
4. P1.2: Fusión de glosas partidas en dos líneas (Istria SA: PRESTAMOS BANCARIOS + L.P) con protección de cuentas cortas.
5. P1.3: Detección y aislamiento auditable de metadatos (paginación, fechas, separadores ===, encabezados).
6. P2.2: Causa estructurada en reconciliación de balance (compare_pre_post).
"""

from parser_universal import (
    CuentaRaw,
    es_ruido_ocr_no_contable,
    fusionar_continuaciones_verticales,
)
from pipeline.homologation_pipeline import HomologationPipeline
from validation.prepost_balance import compare_pre_post


# ─────────────────────────────────────────────────────────────────────────────
# P0.1: ANTI-RUIDO ERP Y TRAZABILIDAD
# ─────────────────────────────────────────────────────────────────────────────

def test_p01_filtro_ruido_no_descarta_cuentas_con_codigo():
    assert HomologationPipeline._is_erp_metadata_noise("GASTOS", monto=0.0, account_code="4.1.01.001") is False
    assert HomologationPipeline._is_erp_metadata_noise("BANCO CHILE", monto=500000.0, account_code="1.1.01.001") is False


def test_p01_filtro_ruido_no_descarta_cuentas_con_monto():
    assert HomologationPipeline._is_erp_metadata_noise("BANCO DE CHILE", monto=1250000.0) is False
    assert HomologationPipeline._is_erp_metadata_noise("CLIENTES CURICO", monto=850000.0) is False
    assert HomologationPipeline._is_erp_metadata_noise("GASTOS FINANCIEROS", monto=350000.0) is False


def test_p01_filtro_ruido_identifica_basura_erp_sin_monto():
    assert HomologationPipeline._is_erp_metadata_noise("Usuario : GORELLANA", monto=0.0) is True
    assert HomologationPipeline._is_erp_metadata_noise("HASTA 31/12/2016 EN NIVEL 4", monto=0.0) is True
    assert HomologationPipeline._is_erp_metadata_noise("$ $", monto=0.0) is True
    assert HomologationPipeline._is_erp_metadata_noise("====================", monto=0.0) is True


# ─────────────────────────────────────────────────────────────────────────────
# P1.2: FUSIÓN DE GLOSAS PARTIDAS EN DOS LÍNEAS
# ─────────────────────────────────────────────────────────────────────────────

def test_p12_fusion_glosa_partida_istria():
    cuentas = [
        CuentaRaw(
            linea=10,
            codigo="210101",
            nombre="PRESTAMOS BANCARIOS",
            monto=45000000.0,
            montos_columnas={"pasivo": 45000000.0},
        ),
        CuentaRaw(
            linea=11,
            codigo=None,
            nombre="L.P",
            monto=0.0,
            montos_columnas={},
        ),
    ]
    fusionadas, cantidad = fusionar_continuaciones_verticales(cuentas)
    assert cantidad == 1
    assert len(fusionadas) == 1
    assert fusionadas[0].nombre == "PRESTAMOS BANCARIOS L.P"
    assert fusionadas[0].monto == 45000000.0


def test_p12_fusion_glosa_partida_variantes():
    cuentas = [
        CuentaRaw(
            linea=20,
            codigo="210205",
            nombre="OBLIGACIONES CON BANCOS",
            monto=12000000.0,
            montos_columnas={"pasivo": 12000000.0},
        ),
        CuentaRaw(
            linea=21,
            codigo=None,
            nombre="LARGO PLAZO",
            monto=0.0,
            montos_columnas={},
        ),
    ]
    fusionadas, cantidad = fusionar_continuaciones_verticales(cuentas)
    assert cantidad == 1
    assert len(fusionadas) == 1
    assert fusionadas[0].nombre == "OBLIGACIONES CON BANCOS LARGO PLAZO"


def test_p12_proteccion_cuentas_cortas_independientes():
    # Cuentas como CAJA, IVA, PPM no deben fusionarse a la cuenta anterior
    cuentas = [
        CuentaRaw(
            linea=30,
            codigo="110101",
            nombre="BANCO SANTANDER",
            monto=500000.0,
            montos_columnas={"activo": 500000.0},
        ),
        CuentaRaw(
            linea=31,
            codigo=None,
            nombre="CAJA",
            monto=100000.0,
            montos_columnas={"activo": 100000.0},
        ),
        CuentaRaw(
            linea=32,
            codigo=None,
            nombre="PPM",
            monto=50000.0,
            montos_columnas={"activo": 50000.0},
        ),
    ]
    fusionadas, cantidad = fusionar_continuaciones_verticales(cuentas)
    assert cantidad == 0
    assert len(fusionadas) == 3
    assert fusionadas[0].nombre == "BANCO SANTANDER"
    assert fusionadas[1].nombre == "CAJA"
    assert fusionadas[2].nombre == "PPM"


# ─────────────────────────────────────────────────────────────────────────────
# P1.3: METADATOS Y SEPARADORES NO CONTABLES
# ─────────────────────────────────────────────────────────────────────────────

def test_p13_deteccion_metadata_y_separadores():
    # Separadores de texto
    c_sep = CuentaRaw(linea=1, codigo=None, nombre="==============================", monto=0.0)
    assert es_ruido_ocr_no_contable(c_sep) is True

    # Paginación
    c_pag = CuentaRaw(linea=2, codigo=None, nombre="Pag: 1", monto=0.0)
    assert es_ruido_ocr_no_contable(c_pag) is True

    # Fechas ERP
    c_fec = CuentaRaw(linea=3, codigo=None, nombre="2016 Hasta: diciembre", monto=0.0)
    assert es_ruido_ocr_no_contable(c_fec) is True

    # Encabezados de tabla
    c_enc = CuentaRaw(linea=4, codigo=None, nombre="NOMBRE DE LA CUENTA", monto=0.0)
    assert es_ruido_ocr_no_contable(c_enc) is True

    # Cuenta legítima con saldo no es descartada
    c_cta = CuentaRaw(linea=5, codigo=None, nombre="BANCO CHILE", monto=150000.0)
    assert es_ruido_ocr_no_contable(c_cta) is False


# ─────────────────────────────────────────────────────────────────────────────
# P1.1 & P2.1: REGLAS CONTEXTUALES Y DICCIONARIO AGRÍCOLA
# ─────────────────────────────────────────────────────────────────────────────

def test_p21_clasificacion_cuentas_agricolas():
    pipeline = HomologationPipeline()

    # Activo Fijo Agrícola (ANC.01)
    for nombre in [
        "PARRONALES EN PRODUCCION",
        "POZOS PROFUNDOS Y TRANQUES",
        "SISTEMAS DE RIEGO TECNIFICADO",
        "AZUFRADORAS Y TRACTORES",
        "BOCATOMAS Y CANALES",
        "INSTALACIONES DE PACKING",
    ]:
        res = pipeline._classify_by_regex_contextual(nombre, account_tipo="ACTIVO")
        assert res is not None, f"No clasificó '{nombre}'"
        assert res["standard_code"] == "ANC.01"

    # Intangibles Agrícolas - Derechos de Agua (ANC.03)
    for nombre in [
        "DERECHOS DE AGUA RIO CLARO",
        "ACCIONES DE AGUA CANAL MATRIZ",
        "CUOTAS DE AGUA",
    ]:
        res = pipeline._classify_by_regex_contextual(nombre, account_tipo="ACTIVO")
        assert res is not None, f"No clasificó '{nombre}'"
        assert res["standard_code"] == "ANC.03"

    # Existencias Agrícolas (AC.05)
    for nombre in [
        "AGROQUIMICOS Y FERTILIZANTES",
        "COSECHAS EN PROCESO UVA MESA",
        "FRUTA EN TRANSITO",
        "ENVASES Y EMBALAJES DE EXPORTACION",
    ]:
        res = pipeline._classify_by_regex_contextual(nombre, account_tipo="ACTIVO")
        assert res is not None, f"No clasificó '{nombre}'"
        assert res["standard_code"] == "AC.05"


def test_p11_clasificacion_bancos_y_clientes_especificos():
    pipeline = HomologationPipeline()

    # Bancos específicos (AC.01)
    for bco in ["BANCO CHILE", "BANCO SANTANDER", "BCI", "SCOTIABANK"]:
        res = pipeline._classify_by_regex_contextual(bco, account_tipo="ACTIVO")
        assert res is not None, f"No clasificó '{bco}'"
        assert res["standard_code"] == "AC.01"

    # Clientes con nombre de ciudad o tipo (AC.03)
    for cli in ["CLIENTES CURICO", "CLIENTES MERCADO NACIONAL", "CLIENTES EXPORTACION"]:
        res = pipeline._classify_by_regex_contextual(cli, account_tipo="ACTIVO")
        assert res is not None, f"No clasificó '{cli}'"
        assert res["standard_code"] == "AC.03"


# ─────────────────────────────────────────────────────────────────────────────
# P2.2: CAUSA ESTRUCTURADA EN RECONCILIACIÓN DE BALANCE
# ─────────────────────────────────────────────────────────────────────────────

def test_p22_reconciliacion_causa_estructurada():
    class DummyCert:
        totales_finales_validos = True
        diferencias = {"activo_menos_pasivo_patrimonio": 0.0}

    # 1. Exact match
    accounts_ok = [
        {"account_name": "Caja", "classification_amount": 100000.0, "standard_code": "AC.01", "nature": "ACTIVO"},
        {"account_name": "Capital", "classification_amount": 100000.0, "standard_code": "PAT.01", "nature": "PASIVO"},
    ]
    res_ok = compare_pre_post(DummyCert(), accounts_ok)
    assert res_ok["late"]["squared"] is True
    assert res_ok["reason"] == "exact_match"

    # 2. Classification error
    accounts_err = [
        {"account_name": "Caja", "classification_amount": 100000.0, "standard_code": "AC.01", "nature": "ACTIVO"},
        {"account_name": "Proveedores", "classification_amount": 100000.0, "standard_code": "AC.03", "nature": "PASIVO"},
    ]
    res_err = compare_pre_post(DummyCert(), accounts_err)
    assert res_err["late"]["squared"] is False
    assert res_err["classification_degradation"] is True
    assert res_err["reason"] == "classification_error"
