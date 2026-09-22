"""Tests for Codex review fixes in Round B1.

Covers:
1. Recertificación de ocho columnas:
   - Todos los métodos reales (excel_8_columns, revision_humana_8_columnas, ocr_coordinates_8_amounts, coordinates_10_columns).
   - Simulación de pulsación del botón y acción directa.
   - Edición válida mantiene o alcanza certificación.
   - Edición con descuadre nuevo pasa a fallida con explicación visible.
   - Falta de fuente completa documental no certifica (falla cerrada).
   - Separación de descuadre auxiliar (Debe/Haber) vs. descuadre de columnas finales.
2. Cuentas legítimas sin código:
   - 3+ cuentas con código + 1 cuenta legítima sin código conservada y homologable.
   - Cuenta sin código con movimientos compensados (débitos == créditos) conservada.
   - Firmas y textos legales al pie excluidos por regex textual, no por conveniencia de balance.
   - Subtotales jerárquicos excluidos como totales, subcuentas preservadas.
3. Confianza y propagación:
   - Preservación exacta de confianza 0.0 (no coerción a 1.0).
   - Confianza ausente o inválida marcada para revisión sin inventar valores.
   - file_metadata poblado con RUT y organización verificada.
   - Aislamiento multi-tenant y RUT: sin propagación inter-organizaciones ni sin RUT.
"""

from copy import deepcopy
import hashlib
import math
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app_validacion as app
import parser_universal as parser
from persistence.contracts import AuthenticatedActor
from parser_universal import (
    CertificacionExtraccion,
    CuentaRaw,
    FormatoCodigo,
    OrigenColumna,
    RAW_MONETARY_COLUMNS,
    certificar_extraccion_columnas,
    es_ruido_ocr_no_contable,
    marcar_subtotales_jerarquicos,
    parsear_linea,
)


@pytest.fixture(autouse=True)
def _cleanup_streamlit_session():
    import streamlit as st
    st.session_state.clear()
    yield
    st.session_state.clear()


def _crear_muestra_ocho_columnas():
    """Genera cuentas de muestra cuadradas para balance de ocho columnas."""
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "110102 Banco 150 50 100 0 100 0 0 0",
        "210101 Proveedores 0 100 0 100 0 100 0 0",
        "410101 Ventas 0 100 0 100 0 0 0 100",
        "Sumas 250 250 200 200 200 100 0 100",
        "Resultado positivo 0 0 0 0 0 100 100 0",
        "Sumas totales 250 250 200 200 200 200 100 100",
    ]
    cuentas = [parsear_linea(line, i, FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lineas)]
    return cuentas


def _crear_dataframe_desde_cuentas(cuentas):
    records = []
    for c in cuentas:
        rec = {
            "linea": c.linea,
            "codigo_original": c.codigo or "",
            "nombre_original": c.nombre,
            "monto": c.monto,
            "origen_columna": c.origen_columna.value if c.origen_columna else "",
            "es_total": c.es_total,
            "codigo_clasificado": "AC.01" if not c.es_total else "",
            "confianza": 1.0,
            "requiere_revision": False,
        }
        rec.update(c.montos_columnas)
        records.append(rec)
    df = pd.DataFrame(records)
    df.attrs["certification_binding"] = {"digest": "initial_digest_123"}
    return df


# ==============================================================================
# BLOQUE 1: RECERTIFICACIÓN DE OCHO COLUMNAS
# ==============================================================================

@pytest.mark.parametrize("metodo", [
    "excel_8_columns",
    "revision_humana_8_columnas",
    "ocr_coordinates_8_amounts",
    "coordinates_10_columns",
])
def test_ocho_columnas_recertificacion_todos_los_metodos(monkeypatch, metodo):
    """Verifica que el flujo de recertificación cubra todos los métodos de ocho columnas."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo=metodo)
    assert app._es_certificacion_ocho_columnas(cert_inicial)

    df = _crear_dataframe_desde_cuentas(cuentas)
    archivo_nombre = "balance_test.xlsx"

    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("excel", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": metodo,
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.columnas_finales_validadas
    assert nueva_cert.metodo == metodo
    assert "certification_binding" in df.attrs


def test_recertificacion_edicion_valida_mantiene_certificacion(monkeypatch):
    """Una edición válida que mantiene la cuadratura documental certifica exitosamente."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")

    df = _crear_dataframe_desde_cuentas(cuentas)
    # Editar un nombre de cuenta sin alterar los importes contables
    df.loc[df["linea"] == 0, "nombre_original"] = "Caja General Moneda Nacional"

    archivo_nombre = "balance.xlsx"
    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("excel", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": "excel_8_columns",
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.estado == "certificada"
    assert nueva_cert.columnas_finales_validadas


def test_recertificacion_descuadre_nuevo_pasa_a_fallida_con_explicacion(monkeypatch):
    """Una edición que altera importes finales rompiendo el subtotal pasa a fallida con explicación visible."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="revision_humana_8_columnas")

    df = _crear_dataframe_desde_cuentas(cuentas)
    # Introducir descuadre: aumentar activo de Caja en 500 sin contrapartida en el subtotal
    df.loc[df["linea"] == 0, "activo"] = 600.0
    df.loc[df["linea"] == 0, "monto"] = 600.0

    archivo_nombre = "balance.pdf"
    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("pdf", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": "revision_humana_8_columnas",
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.estado == "fallida"
    assert not nueva_cert.columnas_finales_validadas
    assert any("no reproducen el subtotal" in r for r in nueva_cert.razones)


def test_recertificacion_falla_sin_fuente_completa(monkeypatch):
    """Si falta la fuente completa documental, no se certifica (falla cerrada)."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    archivo_nombre = "balance_sin_fuente.xlsx"
    # classified_source_snapshots NO contiene el archivo
    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {},
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.estado == "fallida"
    assert not nueva_cert.columnas_finales_validadas
    assert any("Falta el documento completo original" in r for r in nueva_cert.razones)


def test_separacion_descuadre_auxiliar_vs_columnas_finales():
    """Una discrepancia en Débitos/Créditos no bloquea columnas finales, pero un descuadre final sí bloquea."""
    cuentas = _crear_muestra_ocho_columnas()
    # Descuadre auxiliar: alterar debitos de Caja sin alterar saldos ni activos
    cuentas[0].montos_columnas["debitos"] = 999.0
    cert_aux = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")

    # Columnas finales validadas debe ser True (clasificación habilitada con observación no bloqueante)
    assert cert_aux.columnas_finales_validadas
    assert len(cert_aux.observaciones_auxiliares) > 0
    assert app._permite_clasificar_extraccion(cert_aux)

    # Ahora introducir descuadre en columnas finales: alterar pasivo de Proveedores
    cuentas[2].montos_columnas["pasivo"] = 999.0
    cert_final = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    assert not cert_final.columnas_finales_validadas
    assert not app._permite_clasificar_extraccion(cert_final)


# ==============================================================================
# BLOQUE 2: CUENTAS LEGÍTIMAS SIN CÓDIGO
# ==============================================================================

def test_cuentas_sin_codigo_conservadas_con_tres_codificadas():
    """3 o más cuentas con código + 1 cuenta legítima sin código: se conserva y se homologa."""
    lineas = [
        "110101 Caja 50 0 50 0 50 0 0 0",
        "110102 Banco Estado 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 50 0 50 0 50 0 0",
        "Banco Santander 50 0 50 0 50 0 0 0",
        "410101 Ventas 0 150 0 150 0 0 0 150",
        "Sumas 200 200 200 200 200 50 0 150",
        "Resultado positivo 0 0 0 0 0 150 150 0",
        "Sumas totales 200 200 200 200 200 200 150 150",
    ]
    cuentas = [parsear_linea(line, i, FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lineas)]
    cert = certificar_extraccion_columnas(cuentas)

    # La cuenta sin código debe estar evaluada y preservada en el detalle
    cuenta_sin_cod = next((c for c in cuentas if c.nombre == "Banco Santander"), None)
    assert cuenta_sin_cod is not None
    assert cuenta_sin_cod.codigo is None
    assert cuenta_sin_cod.requiere_revision_extraccion
    assert cert.columnas_finales_validadas
    assert cert.filas_evaluadas == 5


def test_cuenta_sin_codigo_movimientos_compensados():
    """Cuenta sin código con movimientos compensados (débitos == créditos) se conserva y no se descarta."""
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 100 0 100 0 100 0 0",
        "Compensacion Transitoria 500 500 0 0 0 0 0 0",
        "Sumas 600 600 100 100 100 100 0 0",
        "Sumas totales 600 600 100 100 100 100 0 0",
    ]
    cuentas = [parsear_linea(line, i, FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lineas)]
    cert = certificar_extraccion_columnas(cuentas)

    cuenta_comp = next((c for c in cuentas if c.nombre == "Compensacion Transitoria"), None)
    assert cuenta_comp is not None
    assert cuenta_comp.codigo is None
    assert cert.columnas_finales_validadas
    assert cert.filas_evaluadas == 3


def test_firmas_y_textos_legales_excluidos_por_regex_no_por_balance():
    """Firmas y textos legales se excluyen por regex textual independientemente de si el balance cuadra."""
    linea_firma = "Firma Representante Legal 0 0 0 0 0 0 0 0"
    cuenta_firma = parsear_linea(linea_firma, 10, FormatoCodigo.COMPACTO, ".")
    assert cuenta_firma is None or es_ruido_ocr_no_contable(cuenta_firma)

    # Test directo con CuentaRaw poblada para verificar que es_ruido_ocr_no_contable la detecte
    cuenta_directa_firma = CuentaRaw(
        linea=20, codigo=None, nombre="Firma Representante Legal",
        monto=0.0, origen_columna=OrigenColumna.ACTIVO, es_total=False,
        confianza_extraccion=1.0, tipo_cuenta=None,
        montos_columnas={c: 0.0 for c in RAW_MONETARY_COLUMNS},
    )
    assert es_ruido_ocr_no_contable(cuenta_directa_firma)

    cuenta_directa_contador = CuentaRaw(
        linea=21, codigo=None, nombre="Contador General",
        monto=0.0, origen_columna=OrigenColumna.ACTIVO, es_total=False,
        confianza_extraccion=1.0, tipo_cuenta=None,
        montos_columnas={c: 0.0 for c in RAW_MONETARY_COLUMNS},
    )
    assert es_ruido_ocr_no_contable(cuenta_directa_contador)

    cuenta_directa_rut = CuentaRaw(
        linea=22, codigo=None, nombre="RUT: 76.543.210-K",
        monto=0.0, origen_columna=OrigenColumna.ACTIVO, es_total=False,
        confianza_extraccion=1.0, tipo_cuenta=None,
        montos_columnas={c: 0.0 for c in RAW_MONETARY_COLUMNS},
    )
    assert es_ruido_ocr_no_contable(cuenta_directa_rut)

    linea_valida = "Caja Chica 50 0 50 0 50 0 0 0"
    cuenta_valida = parsear_linea(linea_valida, 13, FormatoCodigo.COMPACTO, ".")
    assert not es_ruido_ocr_no_contable(cuenta_valida)


def test_subtotales_jerarquicos_excluidos_subcuentas_preservadas():
    """Subtotales jerárquicos se excluyen como totales, pero sus subcuentas se preservan."""
    lineas = [
        "110100 Total Disponible 200 0 200 0 200 0 0 0",
        "110101 Caja Chica 50 0 50 0 50 0 0 0",
        "110102 Banco Estado 150 0 150 0 150 0 0 0",
        "210101 Proveedores 0 200 0 200 0 200 0 0",
        "Sumas 200 200 200 200 200 200 0 0",
        "Sumas totales 200 200 200 200 200 200 0 0",
    ]
    cuentas = [parsear_linea(line, i, FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lineas)]
    marcados = marcar_subtotales_jerarquicos(cuentas)
    assert marcados == 1
    assert cuentas[0].es_total

    cert = certificar_extraccion_columnas(cuentas)
    assert cert.columnas_finales_validadas
    assert cert.filas_evaluadas == 3


# ==============================================================================
# BLOQUE 3: CONFIANZA Y PROPAGACIÓN
# ==============================================================================

def test_propagar_entre_balances_seguro_confianza_cero_preservada():
    """Confianza 0.0 se preserva exactamente y no se convierte en 1.0."""
    df1 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Banco BCI", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo",
        "confianza": 0.0, "monto": 100.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Banco BCI", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo",
        "confianza": 0.0, "monto": 150.0,
    }])
    resultados = {"b1.xlsx": df1, "b2.xlsx": df2}
    metadatos = {
        "b1.xlsx": {"rut": "76123456-7", "organization_id": "org_1", "verified": True},
        "b2.xlsx": {"rut": "76123456-7", "organization_id": "org_1", "verified": True},
    }
    propagados = app.propagar_entre_balances_seguro(resultados, metadatos_archivos=metadatos)
    assert propagados == 1
    assert df2.at[0, "codigo_clasificado"] == "AC.01"
    assert df2.at[0, "confianza"] == 0.0
    assert df2.at[0, "requiere_revision"] is True


def test_propagar_entre_balances_confianza_invalida_sin_inventar():
    """Confianza ausente (None) o inválida se asigna a 0.0 y requiere revisión."""
    assert app._extraer_confianza_segura(0.0) == 0.0
    assert app._extraer_confianza_segura(False) == 0.0
    assert app._extraer_confianza_segura(None) is None
    assert app._extraer_confianza_segura("invalido") is None
    assert app._extraer_confianza_segura(float("nan")) is None

    df1 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Mercaderías", "codigo_clasificado": "AC.03",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo",
        "confianza": None, "monto": 100.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Mercaderías", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo",
        "confianza": None, "monto": 120.0,
    }])
    resultados = {"f1.xlsx": df1, "f2.xlsx": df2}
    metadatos = {
        "f1.xlsx": {"rut": "99555444-1", "organization_id": "org_1", "verified": True},
        "f2.xlsx": {"rut": "99555444-1", "organization_id": "org_1", "verified": True},
    }
    propagados = app.propagar_entre_balances_seguro(resultados, metadatos_archivos=metadatos)
    assert propagados == 1
    assert df2.at[0, "confianza"] == 0.0
    assert df2.at[0, "requiere_revision"] is True


def test_propagar_entre_balances_seguro_aislamiento_rut_org():
    """No se permite propagar entre organizaciones distintas ni con RUT no verificado."""
    df1 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Caja", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO", "origen_columna": "activo",
        "confianza": 0.9, "monto": 50.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 0, "nombre_original": "Caja", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo",
        "confianza": 0.0, "monto": 50.0,
    }])
    resultados = {"empresa_a.xlsx": df1, "empresa_b.xlsx": df2}

    # Caso 1: Distintas organizaciones (multi-tenant)
    metadatos_multi = {
        "empresa_a.xlsx": {"rut": "76111222-3", "organization_id": "org_A", "verified": True},
        "empresa_b.xlsx": {"rut": "76111222-3", "organization_id": "org_B", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(resultados, metadatos_archivos=metadatos_multi) == 0
    assert df2.at[0, "codigo_clasificado"] == ""

    # Caso 2: Mismo org pero distintos RUTs
    metadatos_distinto_rut = {
        "empresa_a.xlsx": {"rut": "76111222-3", "organization_id": "org_A", "verified": True},
        "empresa_b.xlsx": {"rut": "88999000-4", "organization_id": "org_A", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(resultados, metadatos_archivos=metadatos_distinto_rut) == 0
    assert df2.at[0, "codigo_clasificado"] == ""

    # Caso 3: Archivo sin RUT verificado
    metadatos_sin_rut = {
        "empresa_a.xlsx": {"rut": "76111222-3", "organization_id": "org_A", "verified": True},
        "empresa_b.xlsx": {"rut": "", "organization_id": "org_A", "verified": False},
    }
    assert app.propagar_entre_balances_seguro(resultados, metadatos_archivos=metadatos_sin_rut) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


# ==============================================================================
# BLOQUE 1: IDENTIDAD Y ORGANIZACIÓN EN PROPAGACIÓN (PRUEBAS REQUERIDAS A-H)
# ==============================================================================

def test_propagar_a_mismo_rut_verified_false():
    """(a) Mismo RUT con verified=False o string 'false' no debe propagar."""
    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.9, "monto": 100.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 100.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}

    # Subcaso 1: verified booleano False
    meta_false = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": False},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": False},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta_false) == 0
    assert df2.at[0, "codigo_clasificado"] == ""

    # Subcaso 2: verified con string "false" (no debe tratarse como truthy)
    meta_str_false = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": "false"},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": "false"},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta_str_false) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_b_ausencia_verificacion():
    """(b) Ausencia de verificación ('verified' ausente o None) no propaga."""
    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Banco", "codigo_clasificado": "AC.02",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.9, "monto": 200.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Banco", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 200.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    # verified None o ausente
    meta = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": None},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1"},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_c_ausencia_organizacion():
    """(c) Ausencia de organización en uno o ambos archivos omite la propagación."""
    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Clientes", "codigo_clasificado": "AC.03",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.8, "monto": 300.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Clientes", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 300.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}

    # Falta en f1
    meta1 = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "", "verified": True},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_1", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta1) == 0
    assert df2.at[0, "codigo_clasificado"] == ""

    # Falta en ambos
    meta2 = {
        "f1.xlsx": {"rut": "76.111.222-3", "verified": True},
        "f2.xlsx": {"rut": "76.111.222-3", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta2) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_d_organizaciones_distintas():
    """(d) Organizaciones distintas entre archivos no deben propagar."""
    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.9, "monto": 50.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 50.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    meta = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "org_A", "verified": True},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_B", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_e_archivo_sin_rut_propio_y_sesion_company_rut(monkeypatch):
    """(e) Archivo sin RUT propio y sesión con company_rut: no toma prestada la identidad."""
    import streamlit as st
    monkeypatch.setattr(st.session_state, "_state", {"company_rut": "76.999.888-7"}, raising=False)
    st.session_state["company_rut"] = "76.999.888-7"

    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.9, "monto": 100.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 100.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    # f1 tiene RUT propio verificado, pero f2 carece de RUT propio
    meta = {
        "f1.xlsx": {"rut": "76.999.888-7", "organization_id": "org_1", "verified": True},
        "f2.xlsx": {"rut": "", "organization_id": "org_1", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_f_contexto_autenticado_incompatible(monkeypatch):
    """(f) Contexto autenticado incompatible (actor org_A vs archivo org_B)."""
    import streamlit as st
    actor = AuthenticatedActor(
        actor_id="user_1", display_name="Usuario Uno", organization_id="org_A",
        roles=frozenset(["analyst"]), provider_subject="user_1@local",
    )
    monkeypatch.setattr(st.session_state, "_state", {"authenticated_actor": actor}, raising=False)
    st.session_state["authenticated_actor"] = actor

    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "AC.01",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.9, "monto": 100.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Caja", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO", "origen_columna": "activo", "confianza": 0.0, "monto": 100.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    # Archivos pertenecen a org_B (distinta del actor org_A)
    meta = {
        "f1.xlsx": {"rut": "76.111.222-3", "organization_id": "org_B", "verified": True},
        "f2.xlsx": {"rut": "76.111.222-3", "organization_id": "org_B", "verified": True},
    }
    assert app.propagar_entre_balances_seguro(res, metadatos_archivos=meta) == 0
    assert df2.at[0, "codigo_clasificado"] == ""


def test_propagar_g_caso_positivo_identidades_verificadas(monkeypatch):
    """(g) Caso positivo: identidades verificadas, misma org, misma empresa y clasificación compatible."""
    import streamlit as st
    actor = AuthenticatedActor(
        actor_id="user_1", display_name="Usuario Uno", organization_id="org_corp",
        roles=frozenset(["analyst"]), provider_subject="user_1@local",
    )
    st.session_state["authenticated_actor"] = actor

    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Banco Santander", "codigo_clasificado": "AC.02",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo", "confianza": 0.85, "monto": 1000.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Banco Santander", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo", "confianza": 0.0, "monto": 1200.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    # RUT con formatos distintos pero equivalentes tras normalizar_rut
    meta = {
        "f1.xlsx": {"rut": "76.693.319-K", "organization_id": "org_corp", "verified": True},
        "f2.xlsx": {"rut": "76693319-k", "organization_id": "org_corp", "verified": True},
    }
    propagados = app.propagar_entre_balances_seguro(res, metadatos_archivos=meta)
    assert propagados == 1
    assert df2.at[0, "codigo_clasificado"] == "AC.02"
    assert df2.at[0, "metodo"] == "propagado_sugerido"
    assert df2.at[0, "confianza"] == 0.85
    assert df2.at[0, "requiere_revision"] is True


def test_propagar_h_preservacion_confianza_cero_y_revision(monkeypatch):
    """(h) Preservación de confianza cero y revisión pendiente."""
    import streamlit as st
    actor = AuthenticatedActor(
        actor_id="user_1", display_name="Usuario Uno", organization_id="org_corp",
        roles=frozenset(["analyst"]), provider_subject="user_1@local",
    )
    st.session_state["authenticated_actor"] = actor

    df1 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Anticipos", "codigo_clasificado": "AC.05",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo", "confianza": 0.0, "monto": 500.0,
    }])
    df2 = pd.DataFrame([{
        "linea": 1, "nombre_original": "Anticipos", "codigo_clasificado": "",
        "seccion_contable": "ACTIVO CIRCULANTE", "origen_columna": "activo", "confianza": 0.0, "monto": 600.0,
    }])
    res = {"f1.xlsx": df1, "f2.xlsx": df2}
    meta = {
        "f1.xlsx": {"rut": "76.123.456-7", "organization_id": "org_corp", "verified": True},
        "f2.xlsx": {"rut": "76.123.456-7", "organization_id": "org_corp", "verified": True},
    }
    propagados = app.propagar_entre_balances_seguro(res, metadatos_archivos=meta)
    assert propagados == 1
    assert df2.at[0, "codigo_clasificado"] == "AC.05"
    assert df2.at[0, "confianza"] == 0.0
    assert df2.at[0, "requiere_revision"] is True


# ==============================================================================
# BLOQUE 2: CORRESPONDENCIA DOCUMENTAL EN RECERTIFICACIÓN (PRUEBAS A-H)
# ==============================================================================

def test_recertificar_a_lineas_duplicadas_importes_distintos():
    """(a) Líneas duplicadas con importes distintos en la edición deben fallar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    # Duplicar línea 0 con importes distintos
    fila_dup = df.iloc[0].copy()
    fila_dup["monto"] = 9999.0
    fila_dup["activo"] = 9999.0
    df_con_dup = pd.concat([df, pd.DataFrame([fila_dup])], ignore_index=True)

    resultado = app._recertificar_balance_columnas("b.xlsx", df_con_dup, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("duplicadas con importes distintos" in r.lower() for r in resultado.razones)


def test_recertificar_a2_lineas_duplicadas_mismos_importes():
    """Líneas duplicadas con mismos importes también deben detectarse y fallar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    fila_dup = df.iloc[0].copy()
    df_con_dup = pd.concat([df, pd.DataFrame([fila_dup])], ignore_index=True)

    resultado = app._recertificar_balance_columnas("b.xlsx", df_con_dup, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("duplicadas" in r.lower() for r in resultado.razones)


def test_recertificar_b_identificador_ausente():
    """(b) Identificador ausente o nulo en fila editada debe fallar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.at[0, "linea"] = None

    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("ausente o nulo" in r.lower() for r in resultado.razones)


def test_recertificar_c_fila_agregada_sin_respaldo_documental():
    """(c) Fila agregada sin respaldo documental estructurado (incluso con origen='manual' y montos cuadrados) NO debe certificar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Agregar fila con origen='manual' y montos cuadrados pero SIN respaldo_documental
    fila_nueva = {
        "linea": 999, "codigo_original": "110199", "nombre_original": "Caja Chica",
        "monto": 50.0, "debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0,
        "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0,
        "origen": "manual", "origen_columna": "activo",
    }
    df_agregado = pd.concat([df, pd.DataFrame([fila_nueva])], ignore_index=True)

    resultado = app._recertificar_balance_columnas("b.xlsx", df_agregado, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("respaldo documental" in r.lower() for r in resultado.razones)
    assert "certification_binding" not in df_agregado.attrs


def test_recertificar_c2_fila_agregada_columnas_faltantes_sin_inventar():
    _register_test_source("b.xlsx", b"DOCUMENTO_SINTETICO", actor_id="supervisor_1")
    """Fila agregada con respaldo documental pero con columnas monetarias faltantes no inventa ceros y falla."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Falta columna 'ganancia' y 'perdida'
    fila_nueva = {
        "linea": 999, "codigo_original": "110199", "nombre_original": "Caja Chica",
        "monto": 50.0, "debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0,
        "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0,
        "respaldo_documental": {
            "archivo": "b.xlsx", "pagina": 1, "actor": "supervisor_1",
            "file_digest": hashlib.sha256(b"DOCUMENTO_SINTETICO").hexdigest(),
            "importes_confirmados": {"debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0},
        },
    }
    df_agregado = pd.concat([df, pd.DataFrame([fila_nueva])], ignore_index=True)
    resultado = app._recertificar_balance_columnas("b.xlsx", df_agregado, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("no se permite inventar importes" in r.lower() for r in resultado.razones)


def test_recertificar_d_cuenta_omitida_agregada_con_respaldo_valido():
    _register_test_source("banco.xlsx", b"DOCUMENTO_SINTETICO", actor_id="auditor_senior")
    """(d) Cuenta omitida agregada con respaldo válido se incorpora a las 8 columnas y certifica si cuadra."""
    # Base: Caja 50 (deb=50, act=50) + Proveedores 100 (cred=100, pas=100) + Ventas 100 (cred=100, gan=100)
    # Sumas subtotal: deb=250, cred=250, deud=200, acreed=200, act=200, pas=100, gan=100
    # Omitimos Banco 150/50 (deb=150, cred=50, deud=100, act=100) en el snapshot
    caja = CuentaRaw(0, "110101", "Caja", 100.0, montos_columnas={"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0})
    prov = CuentaRaw(1, "210101", "Proveedores", 100.0, montos_columnas={"debitos": 0, "creditos": 100, "saldo_deudor": 0, "saldo_acreedor": 100, "activo": 0, "pasivo": 100, "perdida": 0, "ganancia": 0})
    ventas = CuentaRaw(2, "410101", "Ventas", 100.0, montos_columnas={"debitos": 0, "creditos": 100, "saldo_deudor": 0, "saldo_acreedor": 100, "activo": 0, "pasivo": 0, "perdida": 0, "ganancia": 100})
    subtot = CuentaRaw(3, None, "Sumas", None, es_total=True, montos_columnas={"debitos": 250, "creditos": 250, "saldo_deudor": 200, "saldo_acreedor": 200, "activo": 200, "pasivo": 100, "perdida": 0, "ganancia": 100})
    fin = CuentaRaw(4, None, "Sumas totales", None, es_total=True, montos_columnas={"debitos": 250, "creditos": 250, "saldo_deudor": 200, "saldo_acreedor": 200, "activo": 200, "pasivo": 200, "perdida": 100, "ganancia": 100})

    cuentas_snap = [caja, prov, ventas, subtot, fin]
    cert_prev = CertificacionExtraccion(estado="parcial", metodo="excel_8_columns")

    # En df, agregamos Banco que faltaba, aportando respaldo documental estructurado
    df = pd.DataFrame([
        {"linea": 0, "codigo_original": "110101", "nombre_original": "Caja", "monto": 100.0, "debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        {"linea": 1, "codigo_original": "210101", "nombre_original": "Proveedores", "monto": 100.0, "debitos": 0.0, "creditos": 100.0, "saldo_deudor": 0.0, "saldo_acreedor": 100.0, "activo": 0.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0},
        {"linea": 2, "codigo_original": "410101", "nombre_original": "Ventas", "monto": 100.0, "debitos": 0.0, "creditos": 100.0, "saldo_deudor": 0.0, "saldo_acreedor": 100.0, "activo": 0.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 100.0},
        # Banco agregado con respaldo documental
        {
            "linea": 9, "codigo_original": "110102", "nombre_original": "Banco Santander", "monto": 100.0,
            "debitos": 150.0, "creditos": 50.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0,
            "respaldo_documental": {
                "archivo": "banco.xlsx", "pagina": 1, "actor": "auditor_senior",
                "file_digest": hashlib.sha256(b"DOCUMENTO_SINTETICO").hexdigest(),
                "importes_confirmados": {"debitos": 150.0, "creditos": 50.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
                "justificacion": "Cuenta bancaria omitida en parseo inicial por celda combinada",
            }
        },
    ])

    resultado = app._recertificar_balance_columnas("banco.xlsx", df, cert_prev, snapshot_cuentas=cuentas_snap)
    assert resultado.estado == "certificada"
    assert resultado.filas_evaluadas == 4
    assert len(resultado.decisiones_incorporacion) == 1
    assert resultado.decisiones_incorporacion[0]["actor"] == "auditor_senior"
    assert app._certificacion_coincide_contenido(resultado, df) is True


def test_recertificar_e_eliminacion_cuenta_relevante_falla():
    """(e) Eliminación de cuenta relevante no nula (o con Debe/Haber aunque saldo sea cero) sin respaldo debe fallar."""
    # Cuenta con saldo cero pero Debe=500 y Haber=500 es relevante
    c_saldo_cero = CuentaRaw(
        linea=99, codigo="110199", nombre="Compensación Bancaria", monto=0.0,
        montos_columnas={"debitos": 500, "creditos": 500, "saldo_deudor": 0, "saldo_acreedor": 0, "activo": 0, "pasivo": 0, "perdida": 0, "ganancia": 0},
    )
    cuentas = _crear_muestra_ocho_columnas()
    cuentas.insert(2, c_saldo_cero)
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")

    # En df se elimina c_saldo_cero
    df = _crear_dataframe_desde_cuentas([c for c in cuentas if c.linea != 99])

    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("eliminación no documentada de cuenta relevante" in r.lower() for r in resultado.razones)


def test_recertificar_e2_exclusion_sin_autorizacion_estructurada_falla():
    """Exclusión de cuenta relevante con justificación libre pero sin autorización estructurada debe fallar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Marcar excluida con justificación libre
    df.at[0, "excluida"] = True
    df.at[0, "justificacion"] = "no corresponde al balance general"

    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("exclusión no autorizada" in r.lower() for r in resultado.razones)


def test_recertificar_e3_exclusion_documentada_autorizada_recalcula_controles():
    """Exclusión documentada y autorizada retira efectivamente la cuenta y re-contrasta controles."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Registrar exclusión estructurada en fila 0
    df["decision_exclusion"] = None
    df.at[0, "excluida"] = True
    df.at[0, "decision_exclusion"] = {
        "archivo": "b.xlsx", "actor": "auditor_jefe",
        "motivo": "partida_extracontable_no_computable",
        "cuenta_linea": 0,
    }

    # Al retirar la cuenta de 100 de activo, ya no reproduce el subtotal de 200 de activo -> falla por descuadre de control
    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert len(resultado.decisiones_exclusion) == 1
    assert resultado.decisiones_exclusion[0]["actor"] == "auditor_jefe"
    # Controles contrastados: subtotal impreso 200 vs calculado 100
    assert resultado.estado == "fallida"
    assert any("no reproducen el subtotal" in r.lower() for r in resultado.razones)


def test_recertificar_f_identificadores_ambiguos_entre_paginas_falla():
    """(f) Identificadores de línea repetidos entre páginas sin correspondencia unívoca en el documento deben fallar."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Asignar página 1 a fila 0 y agregar otra fila con misma línea 0 en página 2
    df["pagina"] = 1
    fila_pag2 = df.iloc[0].copy()
    fila_pag2["pagina"] = 2
    fila_pag2["monto"] = 888.0
    df_ambiguo = pd.concat([df, pd.DataFrame([fila_pag2])], ignore_index=True)

    # El snapshot no tiene página 2 para la línea 0
    resultado = app._recertificar_balance_columnas("b.xlsx", df_ambiguo, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "fallida"
    assert any("ambiguos entre páginas" in r.lower() for r in resultado.razones)


def test_recertificar_f2_identificadores_compuestos_pagina_linea_validos():
    _register_test_source("multipage.xlsx", b"DOCUMENTO_SINTETICO", actor_id="source_analyst")
    """(f2) Si (pagina, linea) permite distinguir unívocamente las cuentas, no se rechaza la correspondencia."""
    c_p1_l1 = CuentaRaw(linea=1, codigo="1101", nombre="Caja Central", monto=100.0, montos_columnas={"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0})
    setattr(c_p1_l1, "pagina", 1)
    c_p2_l1 = CuentaRaw(linea=1, codigo="2101", nombre="Proveedores", monto=100.0, montos_columnas={"debitos": 0, "creditos": 100, "saldo_deudor": 0, "saldo_acreedor": 100, "activo": 0, "pasivo": 100, "perdida": 0, "ganancia": 0})
    setattr(c_p2_l1, "pagina", 2)
    subtot = CuentaRaw(linea=2, codigo=None, nombre="Sumas", monto=None, es_total=True, montos_columnas={"debitos": 100, "creditos": 100, "saldo_deudor": 100, "saldo_acreedor": 100, "activo": 100, "pasivo": 100, "perdida": 0, "ganancia": 0})
    fin = CuentaRaw(linea=3, codigo=None, nombre="Sumas totales", monto=None, es_total=True, montos_columnas={"debitos": 100, "creditos": 100, "saldo_deudor": 100, "saldo_acreedor": 100, "activo": 100, "pasivo": 100, "perdida": 0, "ganancia": 0})

    snapshot = [c_p1_l1, c_p2_l1, subtot, fin]
    cert = certificar_extraccion_columnas(snapshot, metodo="excel_8_columns")

    df = pd.DataFrame([
        {"pagina": 1, "linea": 1, "codigo_original": "1101", "nombre_original": "Caja Central", "monto": 100.0, "debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        {"pagina": 2, "linea": 1, "codigo_original": "2101", "nombre_original": "Proveedores", "monto": 100.0, "debitos": 0.0, "creditos": 100.0, "saldo_deudor": 0.0, "saldo_acreedor": 100.0, "activo": 0.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0},
    ])

    resultado = app._recertificar_balance_columnas("multipage.xlsx", df, cert, snapshot_cuentas=snapshot)
    assert resultado.estado == "certificada"
    assert resultado.filas_evaluadas == 2
    assert app._certificacion_coincide_contenido(resultado, df) is True


def test_recertificar_g_edicion_valida_correspondencia_completa():
    _register_test_source("b.xlsx", b"DOCUMENTO_SINTETICO", actor_id="source_analyst")
    """(g) Edición válida con correspondencia documental completa 1:1 recertifica exitosamente."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Corregir nombre contable sin alterar importes
    df.at[0, "nombre_original"] = "Caja Moneda Nacional"
    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert resultado.estado == "certificada"
    assert resultado.filas_evaluadas == 4
    assert app._certificacion_coincide_contenido(resultado, df) is True


def test_recertificar_h_comprobacion_certificado_corresponde_contenido():
    _register_test_source("balance_2024.xlsx", b"DOCUMENTO_SINTETICO", actor_id="source_analyst")
    """(h) Comprobación de que el certificado corresponde exactamente al contenido evaluado."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = "balance_2024.xlsx"
    df.attrs["file_digest"] = hashlib.sha256(b"DOCUMENTO_SINTETICO").hexdigest()

    resultado = app._recertificar_balance_columnas(
        "balance_2024.xlsx", df, cert, snapshot_cuentas=cuentas, file_digest=hashlib.sha256(b"DOCUMENTO_SINTETICO").hexdigest()
    )
    assert resultado.estado == "certificada"

    # Verificar que el vínculo contenga identidad documental, alcance y filas evaluadas
    binding = df.attrs.get("certification_binding", {})
    assert binding["document_identity"]["filename"] == "balance_2024.xlsx"
    assert binding["document_identity"]["file_digest"] == hashlib.sha256(b"DOCUMENTO_SINTETICO").hexdigest()
    assert binding["evaluated_rows_count"] == 4
    assert binding["digest"] == resultado.contenido_certificado_digest
    assert app._certificacion_coincide_contenido(resultado, df) is True


def test_recertificar_h2_alteraciones_posteriores_invalidan_vinculo():
    _register_test_source("b.xlsx", b"DOCUMENTO_SINTETICO", actor_id="source_analyst")
    """(h2) Alteraciones posteriores de página, identidad, respaldo o exclusión invalidan el vínculo."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    resultado = app._recertificar_balance_columnas("b.xlsx", df, cert, snapshot_cuentas=cuentas)
    assert app._certificacion_coincide_contenido(resultado, df) is True

    # 1. Alteración de página
    df_alt_pag = df.copy()
    df_alt_pag.at[0, "pagina"] = 99
    assert app._certificacion_coincide_contenido(resultado, df_alt_pag) is False

    # 2. Alteración de identidad (nombre o línea)
    df_alt_nom = df.copy()
    df_alt_nom.at[0, "nombre_original"] = "Cuenta Alterada Ilegítimamente"
    assert app._certificacion_coincide_contenido(resultado, df_alt_nom) is False

    # 3. Alteración de monto
    df_alt_monto = df.copy()
    df_alt_monto.at[0, "monto"] = 99999.0
    assert app._certificacion_coincide_contenido(resultado, df_alt_monto) is False

    # 4. Alteración de exclusión
    df_alt_exc = df.copy()
    df_alt_exc.at[0, "excluida"] = True
    assert app._certificacion_coincide_contenido(resultado, df_alt_exc) is False


# ==============================================================================
# BLOQUE 3: PRUEBAS DE INTEGRACIÓN DE REVISIÓN CODEX (CONDICIONES 1 A 8)
# ==============================================================================

import pickle


def test_boton_recertificar_contenido_corregido_preserva_vinculo_enriquecido(monkeypatch):
    """El controlador del botón 'Recertificar contenido corregido' preserva el vínculo enriquecido."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    archivo_nombre = "balance_test.xlsx"

    # Simular una cuenta con respaldo documental incorporada
    respaldo = {
        "archivo": archivo_nombre,
        "pagina": 1,
        "ubicacion": "Celda B15",
        "actor": "analyst_1",
        "confirmacion_explicita": True,
        "importes_confirmados": {"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0},
    }
    df["respaldo_documental"] = None
    df.at[0, "respaldo_documental"] = respaldo

    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("excel", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": "excel_8_columns",
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)
    _register_test_source(archivo_nombre, b"DOCUMENTO_SINTETICO", actor_id="analyst_1")

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.estado == "certificada"
    assert nueva_cert.columnas_finales_validadas

    # Verificar que el vínculo enriquecido no fue sobreescrito con valores vacíos
    binding = df.attrs.get("certification_binding")
    assert isinstance(binding, dict)
    assert "document_identity" in binding
    assert binding["document_identity"]["filename"] == archivo_nombre
    assert "scope" in binding
    assert binding["evaluated_rows_count"] == 4
    assert isinstance(binding["incorporaciones"], list)
    assert isinstance(binding["exclusiones"], list)
    assert app._certificacion_coincide_contenido(nueva_cert, df) is True


def test_alteracion_contenido_invalida_vinculo_tras_boton(monkeypatch):
    """Cualquier alteración en el DataFrame posterior a la acción del botón invalida el vínculo."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    archivo_nombre = "balance_editado.xlsx"

    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("excel", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": "excel_8_columns",
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)
    _register_test_source(archivo_nombre, b"DOCUMENTO_SINTETICO", actor_id="analyst_1")

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert app._certificacion_coincide_contenido(nueva_cert, df) is True

    # Alterar un valor en la tabla
    df_alterado = df.copy()
    df_alterado.at[0, "monto"] = 9999.0
    assert app._certificacion_coincide_contenido(nueva_cert, df_alterado) is False


def test_fallo_recertificacion_no_retiene_vinculo_previo(monkeypatch):
    """Una recertificación fallida purga el certification_binding previo sin retener validez anterior."""
    cuentas = _crear_muestra_ocho_columnas()
    cert_inicial = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["certification_binding"] = {"digest": "previo_valido", "version": "1.0"}
    archivo_nombre = "balance_descuadrado.xlsx"

    # Descuadrar el contenido
    df.at[0, "activo"] = 9999.0

    state = {
        "extraction_certifications": {archivo_nombre: cert_inicial},
        "classified_source_snapshots": {
            archivo_nombre: {
                "scope": ("excel", (archivo_nombre,), ()),
                "accounts": deepcopy(cuentas),
                "periods": [],
                "currencies": [],
                "metodo": "excel_8_columns",
            }
        },
        "audit_events": [],
    }
    monkeypatch.setattr(app.st, "session_state", state)

    nueva_cert = app._ejecutar_recertificar_contenido_corregido(
        archivo_nombre, df, cert_inicial,
    )
    assert nueva_cert.estado == "fallida"
    assert not nueva_cert.columnas_finales_validadas
    assert "certification_binding" not in df.attrs


def test_apptest_formulario_ingreso_cuenta_omitida_flujo_completo(tmp_path):
    """Condición 4: Envío real de formulario con Streamlit AppTest: submit, storage, rerun, recovery, recert."""
    # Crear archivo real temporal para verificación de huella
    test_file = tmp_path / "balance_apptest.xlsx"
    file_bytes = b"CONTENIDO_REAL_EXCEL_STREAMLIT_APPTEST_SHA256"
    test_file.write_bytes(file_bytes)
    real_hash = hashlib.sha256(file_bytes).hexdigest()
    fname = str(test_file)

    def run_gui():
        import streamlit as st
        import app_validacion as app
        fname_actual = st.session_state.get("current_test_fname")
        app._mostrar_correccion_extraccion(fname_actual)

    caja = CuentaRaw(0, "1101", "Caja", 100.0, montos_columnas={"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0})
    subtot = CuentaRaw(1, None, "Sumas", None, es_total=True, montos_columnas={"debitos": 200, "creditos": 200, "saldo_deudor": 200, "saldo_acreedor": 200, "activo": 200, "pasivo": 200, "perdida": 0, "ganancia": 0})
    fin = CuentaRaw(2, None, "Sumas totales", None, es_total=True, montos_columnas={"debitos": 200, "creditos": 200, "saldo_deudor": 200, "saldo_acreedor": 200, "activo": 200, "pasivo": 200, "perdida": 0, "ganancia": 0})

    from parser_universal import ResultadoParseo, FormatoCodigo
    res = ResultadoParseo(
        archivo=fname, formato_codigo=FormatoCodigo.COMPACTO,
        separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[caja, subtot, fin],
        certificacion_extraccion=CertificacionExtraccion(estado="fallida", metodo="excel_8_columns", razones=["Falta Banco para cuadrar"]),
    )

    at = AppTest.from_function(run_gui)
    at.session_state["current_test_fname"] = fname
    at.session_state["extraction_pending"] = {fname: res}
    at.session_state["classified_source_snapshots"] = {
        fname: {
            "scope": ("excel", (fname,), ()),
            "accounts": deepcopy([caja, subtot, fin]),
            "periods": [],
            "currencies": [],
            "metodo": "excel_8_columns",
        }
    }
    at.session_state["authenticated_actor"] = AuthenticatedActor(
        actor_id="analyst_test_1", display_name="Analyst Tester",
        roles=frozenset(["analyst"]), organization_id="org_test_apptest",
        provider_subject="sub_apptest",
    )
    at.session_state["file_metadata"] = {fname: {"organization_id": "org_test_apptest", "file_digest": real_hash}}
    at.session_state["raw_file_bytes"] = {(fname, "org_test_apptest", real_hash): file_bytes}

    at.run()

    # Completar el formulario
    at.text_input(key=f"manual_code_{fname}").input("1102")
    at.text_input(key=f"manual_name_{fname}").input("Banco de Chile")
    at.text_input(key=f"manual_loc_{fname}").input("Fila 25, columna C")
    at.number_input(key=f"manual_page_{fname}").set_value(1)
    at.number_input(key=f"man_deb_{fname}").set_value(100.0)
    at.number_input(key=f"man_cred_{fname}").set_value(200.0)
    at.number_input(key=f"man_sdeud_{fname}").set_value(100.0)
    at.number_input(key=f"man_sacred_{fname}").set_value(200.0)
    at.number_input(key=f"man_act_{fname}").set_value(100.0)
    at.number_input(key=f"man_pas_{fname}").set_value(200.0)
    at.number_input(key=f"man_per_{fname}").set_value(0.0)
    at.number_input(key=f"man_gan_{fname}").set_value(0.0)
    at.checkbox(key=f"man_conf_{fname}").check()

    # Enviar formulario
    at.button(key=f"manual_submit_{fname}").click().run()

    # Verificar recuperación de fila, recertificación exitosa y snapshot prístino inmutable
    cuentas_actuales = at.session_state["extraction_pending"][fname].cuentas
    assert len(cuentas_actuales) == 4
    fila_incorporada = cuentas_actuales[-1]
    assert fila_incorporada.nombre == "Banco de Chile"
    assert hasattr(fila_incorporada, "respaldo_documental")
    resp = fila_incorporada.respaldo_documental
    assert resp["actor"] == "analyst_test_1"
    assert resp["actor_org"] == "org_test_apptest"
    assert resp["file_digest"] == real_hash
    assert resp["confirmacion_explicita"] is True

    # Recertificación exitosa
    cert_actual = at.session_state["extraction_certifications"][fname]
    assert cert_actual.estado == "certificada"
    assert len(getattr(cert_actual, "decisiones_incorporacion", [])) == 1

    # Snapshot prístino no contaminado
    snapshot_pristino = at.session_state["classified_source_snapshots"][fname]["accounts"]
    assert len(snapshot_pristino) == 3


def test_ingreso_cuenta_omitida_rechaza_actor_no_acreditado_o_incompatible(monkeypatch, tmp_path):
    """Condición 1: Verifica actor acreditado con rol 'analyst' y coincidencia de organización."""
    test_file = tmp_path / "doc_auth.xlsx"
    test_file.write_bytes(b"DATA_AUTH")
    fname = str(test_file)

    montos = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos["activo"] = 100.0

    # 1. Sin actor autenticado
    state = {"authenticated_actor": None, "file_metadata": {fname: {"organization_id": "org_a"}}}
    monkeypatch.setattr(app.st, "session_state", state)
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="10", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos, confirmacion_explicita=True,
    )
    assert not ok
    assert "no existe un actor autenticado" in msg

    # 2. Objeto arbitrario no acreditado como AuthenticatedActor
    state["authenticated_actor"] = {"actor_id": "hacker", "roles": ["analyst"], "organization_id": "org_a"}
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="10", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos, confirmacion_explicita=True,
    )
    assert not ok
    assert "no existe un actor autenticado" in msg

    # 3. Actor de organización distinta
    actor_otra_org = AuthenticatedActor(
        actor_id="analyst_2", display_name="Analista",
        roles=frozenset(["analyst"]), organization_id="org_b",
        provider_subject="sub_2",
    )
    state["authenticated_actor"] = actor_otra_org
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="10", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos, confirmacion_explicita=True,
    )
    assert not ok
    assert "no coincide con la del archivo" in msg


def test_ingreso_cuenta_omitida_rechaza_archivo_sustituido_distinta_huella(tmp_path):
    """Condición 2: Rechaza respaldo si el archivo fue reemplazado por otro con el mismo nombre."""
    test_file = tmp_path / "archivo_reemplazado.xlsx"
    # Versión 1 original
    test_file.write_bytes(b"VERSION_1_ORIGINAL")
    hash_v1 = hashlib.sha256(b"VERSION_1_ORIGINAL").hexdigest()
    fname = str(test_file)
    _register_test_source(fname, b"VERSION_1_ORIGINAL", path=test_file)

    # El archivo es sobreescrito en disco por versión 2
    test_file.write_bytes(b"VERSION_2_NUEVA")
    hash_v2 = hashlib.sha256(b"VERSION_2_NUEVA").hexdigest()

    # Fila respaldada contra versión 1
    respaldo = {
        "archivo": fname,
        "file_digest": hash_v1,
        "pagina": 1,
        "actor": "analyst_1",
        "confirmacion_explicita": True,
        "importes": {col: 100.0 for col in RAW_MONETARY_COLUMNS},
    }
    row = {"linea": 9, "respaldo_documental": respaldo, **respaldo["importes"]}

    valido, motivo, _ = app._validar_respaldo_incorporacion(row, fname)
    assert not valido
    assert "rechazada o alterada" in motivo


def test_ingreso_cuenta_omitida_rechaza_importes_no_finitos_o_ausentes(tmp_path):
    """Condición 6: Distingue ausencia de valor de cero confirmado y rechaza montos no finitos."""
    test_file = tmp_path / "finitos.xlsx"
    test_file.write_bytes(b"DATA_FINITOS")
    fname = str(test_file)

    act = AuthenticatedActor(
        actor_id="analyst_1", display_name="Analista",
        roles=frozenset(["analyst"]), organization_id="org_fin",
        provider_subject="sub_fin",
    )
    app.st.session_state["authenticated_actor"] = act
    _register_test_source(fname, b"DATA_FINITOS", path=test_file, org="org_fin")

    # 1. Monto NaN
    montos_nan = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos_nan["activo"] = float("nan")
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos_nan, confirmacion_explicita=True,
    )
    assert not ok
    assert "no es un número finito" in msg

    # 2. Monto Infinito
    montos_inf = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos_inf["activo"] = float("inf")
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos_inf, confirmacion_explicita=True,
    )
    assert not ok
    assert "no es un número finito" in msg

    # 3. Columna omitida (None)
    montos_incompletos = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos_incompletos["perdida"] = None
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos_incompletos, confirmacion_explicita=True,
    )
    assert not ok
    assert "no se permite inventar ceros" in msg.lower()

    # 4. Cero confirmado explícitamente (válido)
    montos_ceros_confirmados = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos_ceros_confirmados["activo"] = 100.0
    montos_ceros_confirmados["debitos"] = 100.0
    montos_ceros_confirmados["saldo_deudor"] = 100.0
    ok, msg, nueva = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos_ceros_confirmados, confirmacion_explicita=True,
    )
    assert ok
    assert nueva is not None
    assert nueva.montos_columnas["pasivo"] == 0.0


def test_ingreso_cuenta_omitida_rechaza_sin_ubicacion_o_sin_confirmacion(tmp_path):
    """Rechaza cuando falta ubicación comprobable o falta confirmación explícita."""
    test_file = tmp_path / "reqs.xlsx"
    test_file.write_bytes(b"DATA_REQS")
    fname = str(test_file)

    act = AuthenticatedActor(
        actor_id="analyst_1", display_name="Analista",
        roles=frozenset(["analyst"]), organization_id="org_req",
        provider_subject="sub_req",
    )
    app.st.session_state["authenticated_actor"] = act
    _register_test_source(fname, b"DATA_REQS", path=test_file, org="org_req")

    montos = {col: 0.0 for col in RAW_MONETARY_COLUMNS}
    montos["activo"] = 100.0

    # Sin ubicación (página None y ubicación vacía)
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=None, ubicacion="",
        montos=montos, confirmacion_explicita=True,
    )
    assert not ok
    assert "ubicación comprobable" in msg

    # Sin confirmación explícita
    ok, msg, _ = app._ejecutar_incorporar_cuenta_omitida(
        fname, codigo="1", nombre="Caja", pagina=1, ubicacion="A1",
        montos=montos, confirmacion_explicita=False,
    )
    assert not ok
    assert "confirmar explícitamente" in msg


def test_subtotal_manual_no_suma_al_detalle_ni_autocertifica():
    """Condición 7: Mantén los subtotales manuales separados del detalle: no deben sumarse a las cuentas ni convertirse en controles independientes que se autocertifiquen."""
    # Balance sin subtotales impresos en el snapshot original
    caja = CuentaRaw(0, "1101", "Caja", 100.0, montos_columnas={"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0})
    banco = CuentaRaw(1, "1102", "Banco", 100.0, montos_columnas={"debitos": 100, "creditos": 0, "saldo_deudor": 100, "saldo_acreedor": 0, "activo": 100, "pasivo": 0, "perdida": 0, "ganancia": 0})

    snapshot_sin_controles = [caja, banco]
    cert = CertificacionExtraccion(estado="no_evaluable", metodo="excel_8_columns")

    # Si alguien intenta agregar una fila de subtotal manual en df
    respaldo_subtot = {
        "archivo": "sin_controles.xlsx", "pagina": 1, "actor": "analista_1",
        "confirmacion_explicita": True,
        "importes_confirmados": {"debitos": 200, "creditos": 0, "saldo_deudor": 200, "saldo_acreedor": 0, "activo": 200, "pasivo": 0, "perdida": 0, "ganancia": 0},
    }
    df = pd.DataFrame([
        {"linea": 0, "nombre_original": "Caja", "es_total": False, "total": False, **caja.montos_columnas},
        {"linea": 1, "nombre_original": "Banco", "es_total": False, "total": False, **banco.montos_columnas},
        # Fila agregada que pretende actuar como subtotal
        {"linea": 2, "nombre_original": "Subtotal Inventado", "es_total": True, "total": True, "respaldo_documental": respaldo_subtot, **respaldo_subtot["importes_confirmados"]},
    ])

    resultado = app._recertificar_balance_columnas("sin_controles.xlsx", df, cert, snapshot_cuentas=snapshot_sin_controles)
    # El subtotal manual no debe autocertificar el balance
    assert resultado.estado != "certificada"
    assert not resultado.columnas_finales_validadas


def test_serializacion_restauracion_real_pickle_y_verificacion_archivo(tmp_path):
    """Condición 8: Comprueba serialización y deserialización reales mediante pickle.dumps y pickle.loads.

    Si el archivo no está disponible al restaurar, conserva la evidencia como pendiente de verificación,
    sin habilitar certificación. Si está disponible con huella correcta, habilita certificación.
    """
    test_file = tmp_path / "balance_serializado.xlsx"
    content = b"EXCEL_SERIALIZADO_TEST_SHA256"
    test_file.write_bytes(content)
    real_hash = hashlib.sha256(content).hexdigest()
    fname = str(test_file)
    _register_test_source(fname, content, path=test_file)

    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = fname
    df.attrs["file_digest"] = real_hash

    # Certificar y sellar vínculo
    app._vincular_certificacion_contenido(cert, df, filename=fname, file_digest=real_hash)
    assert app._certificacion_coincide_contenido(cert, df) is True

    # 1. Serialización real con pickle
    df_bytes = pickle.dumps(df)
    cert_bytes = pickle.dumps(cert)

    # 2. Deserialización real con pickle
    df_restored = pickle.loads(df_bytes)
    cert_restored = pickle.loads(cert_bytes)

    # Restaurar cuando el archivo fuente está disponible en disco y coincide
    cert_ok = app._restaurar_vinculo_certificacion(cert_restored, df_restored, al_restaurar=True)
    assert cert_ok.estado == "certificada"
    assert app._certificacion_coincide_contenido(cert_ok, df_restored) is True

    # 3. Ahora el archivo fuente ya no está disponible (ej. eliminado o movido)
    test_file.unlink()

    df_restored_2 = pickle.loads(df_bytes)
    cert_restored_2 = pickle.loads(cert_bytes)

    cert_pendiente = app._restaurar_vinculo_certificacion(cert_restored_2, df_restored_2, al_restaurar=True)

    # Evidencia conservada pero pendiente de verificación, sin habilitar certificación
    binding = df_restored_2.attrs.get("certification_binding")
    assert isinstance(binding, dict)
    assert binding["estado_verificacion"] == "pendiente_archivo_fuente"
    assert cert_pendiente.estado == "parcial"
    assert not cert_pendiente.columnas_finales_validadas
    assert app._certificacion_coincide_contenido(cert_pendiente, df_restored_2) is False


def test_registro_documental_permite_listas_vacias_incorporaciones_exclusiones():
    """Condición 5: Permite listas vacías en incorporaciones y exclusiones sin tratarlas como dato falso o faltante."""
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)

    # Vincular pasando explícitamente listas vacías
    app._vincular_certificacion_contenido(
        cert, df, filename="test.xlsx",
        incorporaciones=[], exclusiones=[],
    )
    binding = df.attrs["certification_binding"]
    assert binding["incorporaciones"] == []
    assert binding["exclusiones"] == []
    # Las listas vacías no deben ser None ni eliminadas
    assert isinstance(binding["incorporaciones"], list)
    assert isinstance(binding["exclusiones"], list)


# ==============================================================================
# BLOQUE 4: IDENTIDAD FUENTE, HOMÓNIMOS, PRESERVACIÓN DE FALLOS Y RECUPERACIÓN DURABLE
# ==============================================================================


def _register_test_source(name, content, *, path=None, org="source_test", actor_id="source_analyst"):
    """Registro explícito sintético: no autoriza rutas por su nombre."""
    actor = AuthenticatedActor(actor_id, "Analista", org,
                               frozenset({"analyst"}), "source_subject")
    app.st.session_state["authenticated_actor"] = actor
    meta = {"organization_id": org, "file_digest": hashlib.sha256(content).hexdigest()}
    if path is not None:
        meta["source_path"] = str(path)
    app.st.session_state.setdefault("file_metadata", {})[name] = meta
    if path is None:
        app.st.session_state.setdefault("raw_file_bytes", {})[(name, org, meta["file_digest"])] = content
    return actor


class _MockUploadedFile:
    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def test_fuente_archivo_cargado_prioritario_sobre_local_homonimo(tmp_path, monkeypatch):
    """Verifica que el archivo cargado en sesión tiene prioridad absoluta sobre cualquier ruta local homónima."""
    contenido_sesion = b"CONTENIDO_SESION_CARGADO_123"
    digest_sesion = hashlib.sha256(contenido_sesion).hexdigest()

    # Crear un archivo homónimo local con distinto contenido
    archivo_local = tmp_path / "balance_homonimo.xlsx"
    archivo_local.write_bytes(b"CONTENIDO_LOCAL_DISTINTO_456")

    upload = _MockUploadedFile("balance_homonimo.xlsx", contenido_sesion)
    app.st.session_state["archivos"] = [upload]
    _register_test_source(upload.name, contenido_sesion)

    # Debe resolver los bytes de la sesión, no del archivo local
    digest_resuelto, estado = app._obtener_huella_archivo_real("balance_homonimo.xlsx")
    assert estado == "disponible"
    assert digest_resuelto == digest_sesion
    assert digest_resuelto != hashlib.sha256(archivo_local.read_bytes()).hexdigest()


def test_fuente_dos_documentos_mismo_nombre_distinto_contenido_misma_organizacion_detecta_colision():
    """Detecta y bloquea colisión de dos archivos homónimos con distinto contenido en la misma organización."""
    fname = "balance_ejercicio.xlsx"
    digest_1 = hashlib.sha256(b"CONTENIDO_DOC_1").hexdigest()
    digest_2 = hashlib.sha256(b"CONTENIDO_DOC_2").hexdigest()

    # Registrar primer documento en metadata
    app.st.session_state["file_metadata"] = {
        fname: {
            "rut": "76111222-3",
            "organization_id": "org_contable_1",
            "file_digest": digest_1,
            "verified": True,
        }
    }

    # Intentar sobrescribir con el segundo documento homónimo en la misma organización debe fallar
    with pytest.raises(ValueError, match="Colisión de archivo homónimo detectada"):
        app._detectar_bloquear_colision_homonimo(fname, digest_2, "org_contable_1")


def test_fuente_dos_documentos_mismo_nombre_distintas_organizaciones_aisladas(tmp_path):
    """Verifica que dos documentos homónimos en distintas organizaciones están estrictamente aislados."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope, AuthorizationDenied

    bundle = build_persistence(PersistenceSettings(
        mode="local",
        local_root=tmp_path / "runtime_multi_org",
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    service = bundle.processes

    actor_org_a = AuthenticatedActor(
        actor_id="actor_a", display_name="Actor A",
        organization_id="org_alpha", roles=frozenset(["analyst"]),
        provider_subject="sub_a",
    )
    actor_org_b = AuthenticatedActor(
        actor_id="actor_b", display_name="Actor B",
        organization_id="org_beta", roles=frozenset(["analyst"]),
        provider_subject="sub_b",
    )

    content_a = b"BALANCE_ORG_A"
    content_b = b"BALANCE_ORG_B"
    scope_a = ProcessScope(page_mode="all", selected_pages=(), periods=("2024",))
    scope_b = ProcessScope(page_mode="all", selected_pages=(), periods=("2024",))

    proc_a = service.start(
        content_a, original_name="balance.pdf", media_type="application/pdf",
        scope=scope_a, actor=actor_org_a, application_version="1.0.0",
    )
    proc_b = service.start(
        content_b, original_name="balance.pdf", media_type="application/pdf",
        scope=scope_b, actor=actor_org_b, application_version="1.0.0",
    )

    # Actor A puede recuperar su proceso pero NO el de la organización B
    rec_a = service.get(proc_a.execution.execution_id, actor=actor_org_a)
    assert rec_a is not None
    assert rec_a.document.sha256 == hashlib.sha256(content_a).hexdigest()

    with pytest.raises(AuthorizationDenied):
        service.get(proc_b.execution.execution_id, actor=actor_org_a)

    with pytest.raises(AuthorizationDenied):
        service.get(proc_a.execution.execution_id, actor=actor_org_b)


def test_fuente_sustitucion_rechaza_evidencia_previa(tmp_path):
    """Sustituir el archivo fuente con otra huella invalida el vínculo y marca certificación fallida."""
    archivo_real = tmp_path / "balance_original.xlsx"
    archivo_real.write_bytes(b"CONTENIDO_ORIGINAL")
    h_orig = hashlib.sha256(b"CONTENIDO_ORIGINAL").hexdigest()
    fname = str(archivo_real)
    _register_test_source(fname, b"CONTENIDO_ORIGINAL", path=archivo_real)

    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = fname
    df.attrs["file_digest"] = h_orig
    df.attrs["source_path"] = fname

    app._vincular_certificacion_contenido(cert, df, filename=fname, file_digest=h_orig)
    assert app._certificacion_coincide_contenido(cert, df) is True

    # El archivo es reemplazado en disco por otra versión con igual nombre
    archivo_real.write_bytes(b"CONTENIDO_SUSTITUIDO_FALSO")

    cert_verif = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert cert_verif.estado == "fallida"
    assert not cert_verif.columnas_finales_validadas
    assert "huella rechazada" in cert_verif.razones[0]
    assert "certification_binding" not in df.attrs


def test_fuente_ausente_no_busca_en_datasets_falla_cerrada():
    """Si el archivo no está en sesión, no debe buscar en datasets/ ni fixtures, fallando cerrado."""
    # Nombre de un archivo que existe en fixtures del repositorio
    fn = "balance_ocho_columnas.xlsx"
    app.st.session_state.clear()

    digest, estado = app._obtener_huella_archivo_real(fn)
    assert estado == "no_autorizada"
    assert digest is None


def test_persistencia_recuperacion_durable_documento_ejecucion_alcance(tmp_path, monkeypatch):
    """Prueba el recorrido real de recuperación durable mediante _restore_streamlit_process_scope."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    bundle = build_persistence(PersistenceSettings(
        mode="local",
        local_root=tmp_path / "runtime_restore",
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_test", display_name="Analista",
        organization_id="org_test", roles=frozenset(["analyst"]),
        provider_subject="sub_test",
    )
    content = b"PDF_DURABLE_TEST_BYTES"
    digest = hashlib.sha256(content).hexdigest()
    upload = _MockUploadedFile("balance_durable.pdf", content)

    # Iniciar proceso con alcance específico
    scope = ProcessScope(page_mode="selected", selected_pages=(1, 2), periods=("2024", "2023"))
    proc = bundle.processes.start(
        content, original_name=upload.name, media_type="application/pdf",
        scope=scope, actor=actor, application_version="1.0.0",
    )

    # Registrar puntero opaco en el registro URL
    app._save_process_registry({digest: proc.execution.execution_id})

    # Restaurar sesión simulando recarga
    app.st.session_state.clear()
    app._restore_streamlit_process_scope([upload], actor)

    assert "persisted_processes" in app.st.session_state
    recovered = app.st.session_state["persisted_processes"][upload.name]
    assert recovered.document.sha256 == digest
    assert app.st.session_state["document_pages"][upload.name] == [1, 2]
    assert app.st.session_state["company_periodos_seleccionados"] == ("2024", "2023")
    assert app.st.session_state["document_scope_confirmed"] == ((upload.name, digest),)


def test_revalidacion_estado_tabular_certificacion_fallida_no_se_promueve(tmp_path):
    """Una certificación fallida conserva su estado y razones, sin promoverse al aportar el archivo."""
    test_file = tmp_path / "balance_fallido.xlsx"
    content = b"CONTENIDO_BALANCE_CON_DESCUADRE"
    test_file.write_bytes(content)
    real_hash = hashlib.sha256(content).hexdigest()
    fname = str(test_file)
    _register_test_source(fname, content, path=test_file)

    cuentas = _crear_muestra_ocho_columnas()
    cert = CertificacionExtraccion(
        estado="fallida",
        metodo="excel_8_columns",
        razones=["Descuadre en columnas Debe y Haber"],
        columnas_finales_validadas=False,
    )
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = fname
    df.attrs["file_digest"] = real_hash
    df.attrs["source_path"] = fname

    app._vincular_certificacion_contenido(cert, df, filename=fname, file_digest=real_hash)

    # Restaurar cuando el archivo coincide: debe permanecer fallida
    cert_restaurada = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert cert_restaurada.estado == "fallida"
    assert "Descuadre en columnas Debe y Haber" in cert_restaurada.razones
    assert not cert_restaurada.columnas_finales_validadas


def test_revalidacion_estado_tabular_certificacion_parcial_no_se_auto_certifica(tmp_path):
    """Una certificación parcial conserva su estado parcial y razones; no se auto-certifica."""
    test_file = tmp_path / "balance_parcial.xlsx"
    content = b"CONTENIDO_BALANCE_PARCIAL"
    test_file.write_bytes(content)
    real_hash = hashlib.sha256(content).hexdigest()
    fname = str(test_file)
    _register_test_source(fname, content, path=test_file)

    cuentas = _crear_muestra_ocho_columnas()
    cert = CertificacionExtraccion(
        estado="parcial",
        metodo="excel_8_columns",
        razones=["Falta columna de pérdidas"],
        columnas_finales_validadas=False,
    )
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = fname
    df.attrs["file_digest"] = real_hash
    df.attrs["source_path"] = fname

    app._vincular_certificacion_contenido(cert, df, filename=fname, file_digest=real_hash)

    cert_restaurada = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert cert_restaurada.estado == "parcial"
    assert "Falta columna de pérdidas" in cert_restaurada.razones
    assert not cert_restaurada.columnas_finales_validadas


def test_revalidacion_estado_tabular_fuente_ausente_bloquea_y_revalidacion_exige_recorrido(tmp_path):
    """Fuente ausente bloquea emisión con estado pendiente; aportar archivo exige recorrido real de validación."""
    test_file = tmp_path / "balance_recert.xlsx"
    content = b"CONTENIDO_RECERT"
    test_file.write_bytes(content)
    real_hash = hashlib.sha256(content).hexdigest()
    fname = str(test_file)
    _register_test_source(fname, content, path=test_file)

    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = fname
    df.attrs["file_digest"] = real_hash
    df.attrs["source_path"] = fname

    app._vincular_certificacion_contenido(cert, df, filename=fname, file_digest=real_hash)

    # 1. Archivo ausente
    test_file.unlink()
    cert_ausente = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert cert_ausente.estado == "parcial"
    assert not cert_ausente.columnas_finales_validadas
    assert any("archivo original no está disponible" in r for r in cert_ausente.razones)

    # 2. Archivo restaurado: huella coincide, pero no habilita emisión por sí sola
    test_file.write_bytes(content)
    cert_reprovista = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert not cert_reprovista.columnas_finales_validadas
    assert not any("archivo original no está disponible" in r for r in cert_reprovista.razones)


def test_declaracion_brecha_recuperacion_sesion_limpia(tmp_path, monkeypatch):
    """Verifica la brecha arquitectónica: en sesión limpia se recupera proceso pero no estado tabular en memoria."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    bundle = build_persistence(PersistenceSettings(
        mode="local",
        local_root=tmp_path / "runtime_gap",
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_gap", display_name="Analista",
        organization_id="org_gap", roles=frozenset(["analyst"]),
        provider_subject="sub_gap",
    )
    content = b"EXCEL_GAP_BYTES"
    digest = hashlib.sha256(content).hexdigest()
    upload = _MockUploadedFile("balance_gap.xlsx", content)

    proc = bundle.processes.start(
        content, original_name=upload.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor, application_version="1.0.0",
    )
    app._save_process_registry({digest: proc.execution.execution_id})

    # Simular inicio de sesión completamente limpia (sin st.session_state)
    app.st.session_state.clear()
    app._restore_streamlit_process_scope([upload], actor)

    # Documento y alcance recuperados duraderamente
    assert app.st.session_state["persisted_processes"][upload.name].execution.execution_id == proc.execution.execution_id

    # Brecha formal verificada: resultados tabulares no existen en memoria y deben ser re-extraídos
    assert "resultados" not in app.st.session_state or upload.name not in app.st.session_state.get("resultados", {})
    assert upload.name not in app.st.session_state.get("extraction_certifications", {})


# ==============================================================================
# BLOQUE: PRUEBAS ESPECÍFICAS DE RESOLUCIÓN DEL ARCHIVO FUENTE (A - I)
# ==============================================================================

def test_fuente_persistencia_archivo_eliminado_no_disponible(tmp_path, monkeypatch):
    """(a) Archivo persistido eliminado físicamente -> no disponible."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    root = tmp_path / "storage_a"
    bundle = build_persistence(PersistenceSettings(
        mode="local", local_root=root,
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_1", display_name="Analista",
        organization_id="org_a", roles=frozenset(["analyst"]),
        provider_subject="sub_a",
    )
    content = b"DOCUMENTO_A_ELIMINAR"
    proc = bundle.processes.start(
        content, original_name="balance_a.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor, application_version="1.0.0",
    )
    app.st.session_state["persisted_processes"] = {"balance_a.xlsx": proc}
    app.st.session_state["authenticated_actor"] = actor

    # Eliminar físicamente el archivo del disco
    doc_path = root / "documents" / proc.document.document_id / "document.bin"
    assert doc_path.is_file()
    doc_path.unlink()

    digest, estado = app._obtener_huella_archivo_real("balance_a.xlsx", actor=actor)
    assert digest is None
    assert estado == "no_disponible"


def test_fuente_persistencia_archivo_alterado_rechazado(tmp_path, monkeypatch):
    """(b) Archivo persistido alterado en disco -> rechazado."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    root = tmp_path / "storage_b"
    bundle = build_persistence(PersistenceSettings(
        mode="local", local_root=root,
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_1", display_name="Analista",
        organization_id="org_b", roles=frozenset(["analyst"]),
        provider_subject="sub_b",
    )
    content = b"DOCUMENTO_B_ORIGINAL"
    proc = bundle.processes.start(
        content, original_name="balance_b.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor, application_version="1.0.0",
    )
    app.st.session_state["persisted_processes"] = {"balance_b.xlsx": proc}
    app.st.session_state["authenticated_actor"] = actor

    # Alterar el archivo en disco
    doc_path = root / "documents" / proc.document.document_id / "document.bin"
    doc_path.write_bytes(b"CONTENIDO_CORRUPTO_O_ALTERADO")

    digest, estado = app._obtener_huella_archivo_real("balance_b.xlsx", actor=actor)
    assert digest is None
    assert estado == "rechazada"


def test_fuente_persistencia_integra_lectura_bytes_autorizado(tmp_path, monkeypatch):
    """(c) Lectura íntegra de bytes del documento persistido cuando el actor está autorizado."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    root = tmp_path / "storage_c"
    bundle = build_persistence(PersistenceSettings(
        mode="local", local_root=root,
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_1", display_name="Analista",
        organization_id="org_c", roles=frozenset(["analyst"]),
        provider_subject="sub_c",
    )
    content = b"DOCUMENTO_INTEGRO_VERIFICADO"
    expected_digest = hashlib.sha256(content).hexdigest()
    proc = bundle.processes.start(
        content, original_name="balance_c.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor, application_version="1.0.0",
    )
    app.st.session_state["persisted_processes"] = {"balance_c.xlsx": proc}
    app.st.session_state["authenticated_actor"] = actor

    original_read = bundle.documents.read
    read_called = []
    def spy_read(doc_id):
        read_called.append(doc_id)
        return original_read(doc_id)
    monkeypatch.setattr(bundle.documents, "read", spy_read)

    digest, estado = app._obtener_huella_archivo_real("balance_c.xlsx", actor=actor)
    assert estado == "disponible"
    assert digest == expected_digest
    assert len(read_called) == 1
    assert read_called[0] == proc.document.document_id


def test_fuente_persistencia_actor_otra_organizacion_rechazado_antes_de_leer(tmp_path, monkeypatch):
    """(d) Actor de otra organización intentando acceder al archivo persistido -> denegado antes de leer bytes."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope
    from persistence.contracts import AuthorizationDenied

    root = tmp_path / "storage_d"
    bundle = build_persistence(PersistenceSettings(
        mode="local", local_root=root,
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor_propietario = AuthenticatedActor(
        actor_id="analista_org1", display_name="Analista Org 1",
        organization_id="org_1", roles=frozenset(["analyst"]),
        provider_subject="sub_1",
    )
    actor_intruso = AuthenticatedActor(
        actor_id="analista_org2", display_name="Analista Org 2",
        organization_id="org_2", roles=frozenset(["analyst"]),
        provider_subject="sub_2",
    )
    content = b"DOCUMENTO_CONFIDENCIAL_ORG1"
    proc = bundle.processes.start(
        content, original_name="balance_privado.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor_propietario, application_version="1.0.0",
    )
    app.st.session_state["persisted_processes"] = {"balance_privado.xlsx": proc}
    app.st.session_state["authenticated_actor"] = actor_intruso

    read_called = []
    def fail_if_read(doc_id):
        read_called.append(doc_id)
        raise AssertionError("No debe llamarse a read para actor no autorizado")
    monkeypatch.setattr(bundle.documents, "read", fail_if_read)

    with pytest.raises(AuthorizationDenied):
        app._obtener_huella_archivo_real("balance_privado.xlsx", actor=actor_intruso)

    assert len(read_called) == 0


def test_fuente_homonimos_distinto_contenido_ambiguo_no_elige_primero():
    """(e) Dos archivos con el mismo nombre y distinto contenido -> ambiguo, no elige el primero."""
    f1 = _MockUploadedFile("balance.xlsx", b"CONTENIDO_VERSION_1")
    f2 = _MockUploadedFile("balance.xlsx", b"CONTENIDO_VERSION_2")
    app.st.session_state["uploaded_files"] = [f1, f2]
    _register_test_source(f1.name, f1.getvalue())

    digest, estado = app._obtener_huella_archivo_real("balance.xlsx", expected_digest=None)
    assert digest is None
    assert estado == "ambiguo"


def test_fuente_homonimos_identificado_correctamente_usa_fuente_vinculada():
    """(f) Homónimos donde se identifica correctamente la versión vinculada -> usa la fuente vinculada."""
    f1 = _MockUploadedFile("balance.xlsx", b"CONTENIDO_VERSION_1")
    f2 = _MockUploadedFile("balance.xlsx", b"CONTENIDO_VERSION_2")
    h1 = hashlib.sha256(b"CONTENIDO_VERSION_1").hexdigest()
    h2 = hashlib.sha256(b"CONTENIDO_VERSION_2").hexdigest()
    app.st.session_state["uploaded_files"] = [f1, f2]
    _register_test_source(f2.name, f2.getvalue())

    digest2, estado2 = app._obtener_huella_archivo_real("balance.xlsx", expected_digest=h2)
    assert digest2 == h2
    assert estado2 == "disponible"

    digest1, estado1 = app._obtener_huella_archivo_real("balance.xlsx", expected_digest=h1)
    assert digest1 is None
    assert estado1 == "rechazada"  # No permite cambiar la versión registrada mediante el argumento.


def test_fuente_ruta_absoluta_existente_no_registrada_rechazada(tmp_path):
    """(g) Ruta absoluta existente no registrada como fuente -> rechazada."""
    arbitrary_file = tmp_path / "arbitrary.xlsx"
    arbitrary_file.write_bytes(b"CONTENIDO_NO_REGISTRADO")
    abs_path = str(arbitrary_file)

    app.st.session_state["file_metadata"] = {}
    app.st.session_state["file_sources"] = {}

    digest, estado = app._obtener_huella_archivo_real(abs_path)
    assert digest is None
    assert estado == "no_autorizada"

    digest2, estado2 = app._obtener_huella_archivo_real("arbitrary.xlsx", source_path=abs_path)
    assert digest2 is None
    assert estado2 == "no_autorizada"


def test_fuente_ruta_registrada_valida_lectura_y_contraste_version(tmp_path):
    """(h) Ruta registrada válida -> lectura exitosa y contraste de versión."""
    test_file = tmp_path / "registrada.xlsx"
    content_v1 = b"VERSION_REGISTRADA_1"
    test_file.write_bytes(content_v1)
    hash_v1 = hashlib.sha256(content_v1).hexdigest()
    abs_path = str(test_file)

    app.st.session_state["file_sources"] = {"registrada.xlsx": abs_path}
    _register_test_source("registrada.xlsx", content_v1, path=abs_path)

    digest, estado = app._obtener_huella_archivo_real("registrada.xlsx", source_path=abs_path)
    assert estado == "disponible"
    assert digest == hash_v1

    content_v2 = b"VERSION_REGISTRADA_2_ALTERADA"
    test_file.write_bytes(content_v2)

    digest_alt, estado_alt = app._obtener_huella_archivo_real("registrada.xlsx", expected_digest=hash_v1, source_path=abs_path)
    assert digest_alt is None
    assert estado_alt == "rechazada"


def test_fuente_recorrido_operativo_carga_recuperacion_recertificacion(tmp_path, monkeypatch):
    """(i) Recorrido operativo completo: carga -> persistencia -> recuperación -> recertificación con validación física."""
    from pathlib import Path
    from persistence import build_persistence, PersistenceSettings
    from persistence.contracts import AuthenticatedActor, ProcessScope

    root = tmp_path / "operativo_i"
    bundle = build_persistence(PersistenceSettings(
        mode="local", local_root=root,
        catalog_seed=Path(app.__file__).parent / "catalogo_maestro.json",
        dictionary_seed=Path(app.__file__).parent / "diccionario.json",
    ))
    monkeypatch.setattr(app, "_streamlit_process_service", lambda actor: bundle.processes)

    actor = AuthenticatedActor(
        actor_id="analista_operativo", display_name="Analista Operativo",
        organization_id="org_i", roles=frozenset(["analyst"]),
        provider_subject="sub_i",
    )
    app.st.session_state["authenticated_actor"] = actor

    # 1. Carga
    raw_content = b"BALANCE_OPERATIVO_BYTES_123"
    raw_digest = hashlib.sha256(raw_content).hexdigest()
    upload = _MockUploadedFile("balance_operativo.xlsx", raw_content)

    # 2. Persistencia
    proc = bundle.processes.start(
        raw_content, original_name=upload.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        scope=ProcessScope(page_mode="all", selected_pages=(), periods=("2024",)),
        actor=actor, application_version="1.0.0",
    )
    app._save_process_registry({raw_digest: proc.execution.execution_id})

    # 3. Recuperación en sesión
    app.st.session_state.clear()
    app.st.session_state["authenticated_actor"] = actor
    app._restore_streamlit_process_scope([upload], actor)

    persisted_proc = app.st.session_state["persisted_processes"][upload.name]
    assert persisted_proc.execution.execution_id == proc.execution.execution_id

    # 4. Certificación y validación física
    cuentas = _crear_muestra_ocho_columnas()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    df = _crear_dataframe_desde_cuentas(cuentas)
    df.attrs["filename"] = upload.name
    df.attrs["file_digest"] = raw_digest
    df.attrs["organization_id"] = "org_i"

    app._vincular_certificacion_contenido(cert, df, filename=upload.name, file_digest=raw_digest)

    # Recertificación con archivo persistido intacto -> validación física pasa
    cert_valida = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert app._certificacion_coincide_contenido(cert_valida, df) is True

    # Si se altera el archivo persistido en disco -> recertificación física falla y se rechaza
    doc_path = root / "documents" / proc.document.document_id / "document.bin"
    doc_path.write_bytes(b"CONTENIDO_ALTERADO_ILEGITIMAMENTE")
    cert_alterada = app._restaurar_vinculo_certificacion(cert, df, al_restaurar=True)
    assert cert_alterada.estado == "fallida"
    assert any("alterado" in r.lower() or "fallida" in r.lower() for r in cert_alterada.razones)
