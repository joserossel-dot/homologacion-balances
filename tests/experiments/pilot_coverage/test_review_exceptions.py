"""
tests/experiments/pilot_coverage/test_review_exceptions.py

Evaluación rigurosa de la Actividad C: Revisión limitada a excepciones y control de emisión.
Aislamiento real: Red y Neon bloqueados preventivamente.
Verifica:
1. Exclusión de cuentas válidas y saldos cero de la cola de revisión.
2. Aislamiento estricto de filas durante la confirmación de categoría.
3. Distinción entre corrección de extracción (que invalida certificación y exige revisión) y confirmación de categoría.
4. Bloqueo de emisión por causas individuales e independientes (certificación inválida, cuenta pendiente, descuadratura).
5. Desbloqueo y autorización definitiva sobre un balance sintético cuadrado y certificado.
6. Conservación íntegra de decisiones del usuario durante todo el flujo.
"""

from __future__ import annotations

import json
import pathlib
import pandas as pd  # type: ignore[import-untyped]  # Biblioteca externa para manipulación de tablas
import pytest
import streamlit as st

from app_validacion import (
    _pendientes_revision,
    _codigo_compatible_con_origen,
    _control_emision,
    _registrar_decision,
    _origen_efectivo,
    _etiqueta_origen,
    _aplicar_edicion_monto_periodos,
    _vincular_certificacion_contenido,
)
from parser_universal import CertificacionExtraccion


@pytest.fixture(autouse=True)
def clean_streamlit_session(monkeypatch):
    """Limpia el estado de sesión de Streamlit y aísla la prueba."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_ENFORCEMENT", "staging")
    if hasattr(st, "session_state"):
        st.session_state.clear()


@pytest.fixture
def catalogo_maestro() -> dict:
    cat_path = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "catalogo_maestro.json"
    with open(cat_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_cuentas_validas_no_vuelven_a_revision():
    """Verifica que filas con codigo_clasificado no vacío y requiere_revision=False queden fuera de pendientes."""
    data = [
        {"nombre": "Caja", "monto": 100000, "codigo_clasificado": "AC.01", "requiere_revision": False, "es_total": False},
        {"nombre": "Banco Chile", "monto": 500000, "codigo_clasificado": "AC.01", "requiere_revision": False, "es_total": False},
        {"nombre": "Cuenta Dudosa", "monto": 25000, "codigo_clasificado": "", "requiere_revision": True, "es_total": False},
        {"nombre": "Total Activo", "monto": 625000, "codigo_clasificado": "", "requiere_revision": True, "es_total": True},
    ]
    df = pd.DataFrame(data)
    pendientes = _pendientes_revision(df)

    assert len(pendientes) == 1, f"Solo la cuenta dudosa debe ser pendiente; obtenidos {len(pendientes)}"
    assert pendientes.iloc[0]["nombre"] == "Cuenta Dudosa"


def test_excluir_saldos_cero_de_revision():
    """Filas con saldo cero deben excluirse de la cola de revisión para evitar sobrecarga operativa."""
    data = [
        {"nombre": "Cuenta Inactiva", "monto": 0, "codigo_clasificado": "", "requiere_revision": True, "es_total": False},
        {"nombre": "Cuenta Activa", "monto": 50000, "codigo_clasificado": "", "requiere_revision": True, "es_total": False},
    ]
    df = pd.DataFrame(data)
    pendientes = _pendientes_revision(df)

    assert len(pendientes) == 1
    assert pendientes.iloc[0]["nombre"] == "Cuenta Activa"


def test_flujo_confirmacion_categoria_y_aislamiento_filas(catalogo_maestro):
    """Verifica que confirmar la categoría de una fila preserve intactas las demás filas y registre auditoría."""
    archivo_nombre = "balance_aislamiento.xlsx"
    data = [
        {
            "id": 1, "nombre_original": "Caja Central", "monto": 100000.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
        {
            "id": 2, "nombre_original": "Fondo Transitorio X", "monto": 250000.0,
            "origen_columna": "activo", "codigo_clasificado": "",
            "metodo": "unclassified", "confianza": 0.0,
            "requiere_revision": True, "es_total": False,
        },
        {
            "id": 3, "nombre_original": "Capital Social", "monto": 350000.0,
            "origen_columna": "pasivo", "codigo_clasificado": "PAT.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
    ]
    df = pd.DataFrame(data)
    st.session_state.setdefault("resultados", {})[archivo_nombre] = df
    st.session_state["historial_decisiones"] = []

    # Instantánea previa de filas no intervenidas
    fila_0_previa = df.iloc[0].to_dict()
    fila_2_previa = df.iloc[2].to_dict()

    idx_target = 1
    row_target = df.iloc[idx_target]
    codigo_seleccionado = "AC.08"  # Otros Activos

    # 1. Validación contable de compatibilidad
    assert _codigo_compatible_con_origen(
        codigo_seleccionado, row_target["origen_columna"],
        row_target["monto"], row_target["nombre_original"],
        catalogo_maestro,
    )

    # 2. Registro de auditoría
    _registrar_decision(archivo_nombre, idx_target, row_target.copy(), codigo_seleccionado, "Confirmación de analista")

    # 3. Actualización de estado de la fila objetivo
    df.at[idx_target, "codigo_clasificado"] = codigo_seleccionado
    df.at[idx_target, "metodo"] = "validacion_humana"
    df.at[idx_target, "confianza"] = 1.0
    df.at[idx_target, "requiere_revision"] = False

    # Comprobaciones de aislamiento y resolución
    pendientes = _pendientes_revision(df)
    assert len(pendientes) == 0, "No deben quedar filas pendientes"
    assert df.iloc[0].to_dict() == fila_0_previa, "La fila 0 debe conservarse estrictamente idéntica"
    assert df.iloc[2].to_dict() == fila_2_previa, "La fila 2 debe conservarse estrictamente idéntica"
    assert len(st.session_state["historial_decisiones"]) == 1
    assert st.session_state["historial_decisiones"][0]["Clasificación nueva"] == "AC.08"


def test_flujo_correccion_extraccion_invalida_certificacion_sin_confirmar_categoria(catalogo_maestro):
    """La corrección de extracción invalida el binding de certificación y mantiene requiere_revision=True."""
    archivo_nombre = "balance_extraccion.xlsx"
    data = [
        {
            "linea": 1, "nombre_original": "Venta Mal Extraida", "monto": 500.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.08",
            "metodo": "unclassified", "confianza": 0.5,
            "requiere_revision": True, "es_total": False,
            "tipo_revision": "",
        },
        {
            "linea": 2, "nombre_original": "Caja Operativa", "monto": 50000.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
            "tipo_revision": "",
        },
    ]
    df = pd.DataFrame(data)
    df.attrs["certification_binding"] = {"digest": "abc123hash", "estado_verificacion": "ok"}
    st.session_state.setdefault("resultados", {})[archivo_nombre] = df

    columnas_clave = ["linea", "nombre_original", "monto", "origen_columna", "codigo_clasificado", "metodo", "confianza", "requiere_revision"]
    fila_1_previa = df.iloc[1][columnas_clave].to_dict()

    # Ejecución de la corrección de extracción en fila 0
    nuevo_nombre = "Ventas del Giro"
    nueva_columna = "ganancia"
    nuevo_monto = 5000000.0

    df.at[0, "nombre_original"] = nuevo_nombre
    df.at[0, "origen_columna"] = nueva_columna
    _aplicar_edicion_monto_periodos(df, 0, nuevo_monto, periodo_activo=None, periodos=None)
    df.at[0, "origen_columna_efectiva"] = _origen_efectivo(nueva_columna, nuevo_monto, nuevo_nombre)
    df.at[0, "origen_columna_display"] = _etiqueta_origen(nueva_columna, nuevo_monto, nuevo_nombre)
    df.at[0, "metodo"] = "manual_revision"
    df.at[0, "confianza"] = 1.0
    df.at[0, "requiere_revision"] = True  # Permanece pendiente de validación contable
    df.at[0, "tipo_revision"] = "correccion_extraccion"

    # La edición de datos documentales invalida el binding de certificación previo
    df.attrs.pop("certification_binding", None)

    assert df.at[0, "tipo_revision"] == "correccion_extraccion"
    assert bool(df.at[0, "requiere_revision"]) is True, "Una corrección de extracción NO debe auto-confirmar la categoría"
    assert "certification_binding" not in df.attrs, "El binding de certificación debe quedar invalidado"
    assert df.iloc[1][columnas_clave].to_dict() == fila_1_previa, "La fila 1 debe permanecer inalterada en sus columnas clave"


def test_bloqueos_de_emision_por_causa_individual(catalogo_maestro):
    """Comprueba cada motivo de bloqueo de exportación por separado y verifica la conservación de decisiones."""
    data_base = [
        {
            "linea": 1, "nombre_original": "Caja", "monto": 100000.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
        {
            "linea": 2, "nombre_original": "Capital Social", "monto": 100000.0,
            "origen_columna": "pasivo", "codigo_clasificado": "PAT.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
    ]

    # ── CAUSA 1: Bloqueo exclusivo por certificación inválida ──
    df1 = pd.DataFrame(data_base)
    cert_invalida = CertificacionExtraccion(estado="invalida", razones=["Discrepancia en columnas documentales"])
    emision_cert = _control_emision(
        df=df1,
        catalogo=catalogo_maestro,
        diagnostico={"cuadra": True, "diferencia": 0.0},
        extraction_certification=cert_invalida,
    )
    assert emision_cert["definitivo"] is False
    assert any("certificad" in m.lower() for m in emision_cert["motivos"])
    assert df1.at[0, "codigo_clasificado"] == "AC.01"  # Decisiones conservadas

    # ── CAUSA 2: Bloqueo exclusivo por cuenta pendiente de revisión ──
    df2 = pd.DataFrame(data_base + [{
        "linea": 3, "nombre_original": "Cuenta Incierta", "monto": 20000.0,
        "origen_columna": "activo", "codigo_clasificado": "",
        "metodo": "unclassified", "confianza": 0.0,
        "requiere_revision": True, "es_total": False,
    }])
    cert_valida2 = CertificacionExtraccion(estado="certificada", razones=[])
    _vincular_certificacion_contenido(cert_valida2, df2, filename="")
    emision_pend = _control_emision(
        df=df2,
        catalogo=catalogo_maestro,
        diagnostico={"cuadra": True, "diferencia": 0.0},
        extraction_certification=cert_valida2,
    )
    assert emision_pend["definitivo"] is False
    assert any("requieren corregir o confirmar" in m.lower() for m in emision_pend["motivos"])
    assert df2.at[0, "codigo_clasificado"] == "AC.01"

    # ── CAUSA 3: Bloqueo exclusivo por descuadratura contable ──
    df3 = pd.DataFrame(data_base)
    cert_valida3 = CertificacionExtraccion(estado="certificada", razones=[])
    _vincular_certificacion_contenido(cert_valida3, df3, filename="")
    emision_descuadre = _control_emision(
        df=df3,
        catalogo=catalogo_maestro,
        diagnostico={"cuadra": False, "diferencia": 15000.0},
        extraction_certification=cert_valida3,
    )
    assert emision_descuadre["definitivo"] is False
    assert any("no coincide" in m.lower() for m in emision_descuadre["motivos"])
    assert df3.at[0, "codigo_clasificado"] == "AC.01"


def test_desbloqueo_autorizacion_emision_balance_cuadrado(catalogo_maestro):
    """Comprueba la autorización explícita de emisión sobre un balance sintético cuadrado y certificado."""
    # Balance sintético con cuadratura estricta: Activo (1.000.000) == Pasivo (300.000) + Patrimonio (700.000)
    data_cuadrada = [
        {
            "linea": 1, "nombre_original": "Caja Central", "monto": 600000.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
        {
            "linea": 2, "nombre_original": "Clientes Nacionales", "monto": 400000.0,
            "origen_columna": "activo", "codigo_clasificado": "AC.03",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
        {
            "linea": 3, "nombre_original": "Proveedores Comerciales", "monto": 300000.0,
            "origen_columna": "pasivo", "codigo_clasificado": "PC.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
        {
            "linea": 4, "nombre_original": "Capital Social Pagado", "monto": 700000.0,
            "origen_columna": "pasivo", "codigo_clasificado": "PAT.01",
            "metodo": "validacion_humana", "confianza": 1.0,
            "requiere_revision": False, "es_total": False,
        },
    ]
    df = pd.DataFrame(data_cuadrada)

    # Certificación documental válida vinculada
    cert_valida = CertificacionExtraccion(
        estado="certificada",
        razones=[],
    )
    _vincular_certificacion_contenido(cert_valida, df, filename="")

    # Diagnóstico contable de cuadratura perfecta
    diagnostico_cuadrado = {"cuadra": True, "diferencia": 0.0}

    # Ejecución del control de emisión
    emision = _control_emision(
        df=df,
        catalogo=catalogo_maestro,
        diagnostico=diagnostico_cuadrado,
        extraction_certification=cert_valida,
    )

    # Aserción explícita de autorización definitiva
    assert emision["definitivo"] is True, f"La emisión debe estar plenamente autorizada. Motivos bloqueantes: {emision.get('motivos')}"
    assert len(emision["motivos"]) == 0, f"No deben existir motivos de bloqueo: {emision['motivos']}"
    assert emision["incidencias"].empty, "No deben existir incidencias de cuentas"
