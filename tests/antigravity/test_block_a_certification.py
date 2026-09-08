"""Pruebas exhaustivas para el Bloque A (Encargo B1)."""
from __future__ import annotations

import copy
import math
import pandas as pd
import pytest

from parser_universal import (
    CuentaRaw,
    CertificacionExtraccion,
    OrigenColumna,
    RAW_MONETARY_COLUMNS,
    certificar_extraccion_columnas,
    certificar_clasificado_final,
    marcar_subtotales_jerarquicos,
    parsear_monto,
)
import app_validacion as app


def _crear_cuentas_8_columnas_base() -> list[CuentaRaw]:
    c1 = CuentaRaw(
        linea=1, codigo="1101", nombre="Caja", monto=100.0,
        montos_columnas={
            "debitos": 100.0, "creditos": 0.0,
            "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
            "activo": 100.0, "pasivo": 0.0,
            "perdida": 0.0, "ganancia": 0.0,
        },
        origen_columna=OrigenColumna.ACTIVO, es_total=False,
    )
    c2 = CuentaRaw(
        linea=2, codigo="2101", nombre="Proveedores", monto=100.0,
        montos_columnas={
            "debitos": 0.0, "creditos": 100.0,
            "saldo_deudor": 0.0, "saldo_acreedor": 100.0,
            "activo": 0.0, "pasivo": 100.0,
            "perdida": 0.0, "ganancia": 0.0,
        },
        origen_columna=OrigenColumna.PASIVO, es_total=False,
    )
    subtotal = CuentaRaw(
        linea=3, codigo=None, nombre="SUBTOTAL", monto=100.0,
        montos_columnas={
            "debitos": 100.0, "creditos": 100.0,
            "saldo_deudor": 100.0, "saldo_acreedor": 100.0,
            "activo": 100.0, "pasivo": 100.0,
            "perdida": 0.0, "ganancia": 0.0,
        },
        es_total=True,
    )
    final = CuentaRaw(
        linea=4, codigo=None, nombre="TOTALES IGUALES", monto=100.0,
        montos_columnas={
            "debitos": 100.0, "creditos": 100.0,
            "saldo_deudor": 100.0, "saldo_acreedor": 100.0,
            "activo": 100.0, "pasivo": 100.0,
            "perdida": 0.0, "ganancia": 0.0,
        },
        es_total=True,
    )
    return [c1, c2, subtotal, final]


def test_a0_1_digest_detecta_cambio_en_columnas_8_col():
    """Comprueba que _digest_filas_certificables detecta cambios en columnas monetarias de 8 cols."""
    df = pd.DataFrame([
        {"linea": 1, "codigo_original": "1101", "nombre_original": "Caja",
         "monto": 100.0, "origen_columna": "activo", "es_total": False,
         "debitos": 100.0, "creditos": 0.0, "activo": 100.0},
    ])
    d1 = app._digest_filas_certificables(df)
    df_mod = df.copy()
    df_mod.at[0, "debitos"] = 999999.0
    d2 = app._digest_filas_certificables(df_mod)
    assert d1 != d2, "El digest debe invalidarse al modificar Débitos"


def test_a0_1_recertificacion_8_cols_detecta_descuadre_final():
    """Comprueba que la recertificación de 8 cols degrada a fallida si se descuadran columnas finales."""
    cuentas = _crear_cuentas_8_columnas_base()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    assert cert.estado == "certificada"

    # Editar DataFrame alterando el activo de Caja a 500, descuadrando contra el subtotal
    df_editado = pd.DataFrame([
        {"linea": 1, "codigo_original": "1101", "nombre_original": "Caja",
         "monto": 500.0, "origen_columna": "activo", "es_total": False,
         "debitos": 500.0, "creditos": 0.0, "saldo_deudor": 500.0, "saldo_acreedor": 0.0,
         "activo": 500.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        {"linea": 2, "codigo_original": "2101", "nombre_original": "Proveedores",
         "monto": 100.0, "origen_columna": "pasivo", "es_total": False,
         "debitos": 0.0, "creditos": 100.0, "saldo_deudor": 0.0, "saldo_acreedor": 100.0,
         "activo": 0.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0},
    ])
    recert = app._recertificar_balance_columnas("test.xlsx", df_editado, cert, snapshot_cuentas=cuentas)
    assert recert.estado == "fallida"
    assert "no reproducen el subtotal impreso" in " ".join(recert.razones)


def test_a0_1_recertificacion_8_cols_conserva_advertencia_auxiliar_sin_bloquear():
    """Condición 2: Discrepancia en Débitos/Créditos con columnas finales correctas no es fallida."""
    cuentas = _crear_cuentas_8_columnas_base()
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    assert cert.estado == "certificada"

    # Fila de detalle con movimiento auxiliar abierto pero columnas finales (Activo/Pasivo) correctas
    c_aux = CuentaRaw(
        linea=1, codigo="1101", nombre="Caja", monto=100.0,
        montos_columnas={
            "debitos": 50.0, "creditos": 0.0,  # Débitos no exhaustivos (subtotal es 100)
            "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
            "activo": 100.0, "pasivo": 0.0,
            "perdida": 0.0, "ganancia": 0.0,
        },
        origen_columna=OrigenColumna.ACTIVO, es_total=False,
    )
    cuentas_aux = [c_aux, cuentas[1], cuentas[2], cuentas[3]]
    # certificar columnas directas
    res = certificar_extraccion_columnas(cuentas_aux, metodo="excel_8_columns")
    # No debe ser fallida (movimientos_no_exhaustivos la mantiene válida para homologación)
    assert res.estado != "fallida", "Una discrepancia meramente auxiliar de Débito/Crédito no debe bloquear emisión si finales cuadran"


def test_a0_1_recertificacion_8_cols_sin_snapshot_no_certifica():
    """Condición 1: Si no hay snapshot del documento fuente completo vinculado, no certifica."""
    df = pd.DataFrame([{"linea": 1, "monto": 100.0}])
    cert = CertificacionExtraccion(estado="certificada", metodo="excel_8_columns")
    # Sin snapshot en session_state ni argumento
    recert = app._recertificar_balance_columnas("archivo_inexistente.xlsx", df, cert, snapshot_cuentas=None)
    assert recert.estado in ("parcial", "fallida")
    assert not recert.columnas_finales_validadas
    assert "Falta el documento completo original" in " ".join(recert.razones)


def test_a0_2_sincronizacion_monto_periodo_activo_y_alias():
    """Condición 5: Sincroniza monto, período activo y alias sin tocar otros períodos."""
    df = pd.DataFrame([
        {"linea": 1, "codigo_original": "1101", "nombre_original": "Caja",
         "monto": 100.0, "monto_periodo_2024": 100.0, "monto_periodo_2023": 80.0,
         "monto_periodo_actual": 100.0, "origen_columna": "activo", "es_total": False},
    ])
    app._aplicar_edicion_monto_periodos(df, idx=0, nuevo_monto=160.0, periodo_activo="2024")
    assert df.at[0, "monto"] == 160.0
    assert df.at[0, "monto_periodo_2024"] == 160.0
    assert df.at[0, "monto_periodo_actual"] == 160.0
    assert df.at[0, "monto_periodo_2023"] == 80.0, "El período comparativo no debe ser modificado"


def test_a0_3_propagacion_aislamiento_empresa_seccion_y_revision():
    """Condición 3: No propaga entre empresas distintas, no cruza CP/LP y mantiene requiere_revision=True."""
    # Caso 1: Empresas distintas (distinto RUT)
    df_alfa = pd.DataFrame([
        {"nombre_original": "Otros pasivos financieros", "codigo_clasificado": "PC.02",
         "origen_columna": "pasivo", "seccion_contable": "PC", "monto": 100.0, "confianza": 0.95, "requiere_revision": False},
    ])
    df_beta = pd.DataFrame([
        {"nombre_original": "Otros pasivos financieros", "codigo_clasificado": "",
         "origen_columna": "pasivo", "seccion_contable": "PC", "monto": 100.0, "requiere_revision": True},
    ])
    res_distintos = {"alfa.pdf": df_alfa, "beta.pdf": df_beta}
    meta_distintos = {
        "alfa.pdf": {"rut": "76.111.111-1", "organization_id": "org_test", "verified": True},
        "beta.pdf": {"rut": "77.222.222-2", "organization_id": "org_test", "verified": True},
    }
    prop = app.propagar_entre_balances_seguro(res_distintos, meta_distintos)
    assert prop == 0
    assert df_beta.at[0, "codigo_clasificado"] == "", "No debe propagar entre empresas con RUT distinto"

    # Caso 2: Misma empresa con RUT comprobado, pero cruce CP vs LP
    df_gamma = pd.DataFrame([
        {"nombre_original": "Otros pasivos financieros", "codigo_clasificado": "PC.02",
         "origen_columna": "pasivo", "seccion_contable": "PC", "monto": 100.0, "confianza": 0.95, "requiere_revision": False},
    ])
    df_delta = pd.DataFrame([
        {"nombre_original": "Otros pasivos financieros", "codigo_clasificado": "",
         "origen_columna": "pasivo", "seccion_contable": "PNC", "monto": 100.0, "requiere_revision": True},
    ])
    res_mismo_rut = {"gamma.pdf": df_gamma, "delta.pdf": df_delta}
    meta_mismo_rut = {
        "gamma.pdf": {"rut": "76.111.111-1", "organization_id": "org_test", "verified": True},
        "delta.pdf": {"rut": "76.111.111-1", "organization_id": "org_test", "verified": True},
    }
    prop_cp_lp = app.propagar_entre_balances_seguro(res_mismo_rut, meta_mismo_rut)
    assert prop_cp_lp == 0
    assert df_delta.at[0, "codigo_clasificado"] == "", "No debe cruzar sección corriente a no corriente"

    # Caso 3: Misma empresa, sección compatible -> debe propagar conservando procedencia y revisión pendiente
    df_eps = pd.DataFrame([
        {"nombre_original": "Caja Principal", "codigo_clasificado": "AC.01",
         "origen_columna": "activo", "seccion_contable": "AC", "monto": 50.0, "confianza": 0.95, "requiere_revision": False},
    ])
    df_zeta = pd.DataFrame([
        {"nombre_original": "Caja Principal", "codigo_clasificado": "",
         "origen_columna": "activo", "seccion_contable": "AC", "monto": 70.0, "requiere_revision": True},
    ])
    res_valido = {"eps.pdf": df_eps, "zeta.pdf": df_zeta}
    meta_valido = {
        "eps.pdf": {"rut": "76.111.111-1", "organization_id": "org_test", "verified": True},
        "zeta.pdf": {"rut": "76.111.111-1", "organization_id": "org_test", "verified": True},
    }
    prop_ok = app.propagar_entre_balances_seguro(res_valido, meta_valido)
    assert prop_ok == 1
    assert df_zeta.at[0, "codigo_clasificado"] == "AC.01"
    assert df_zeta.at[0, "metodo"] == "propagado_sugerido"
    assert bool(df_zeta.at[0, "requiere_revision"]) is True, "Debe mantener revisión humana pendiente"
    assert df_zeta.at[0, "confianza"] == 0.95, "Debe conservar confianza original de la procedencia"


def test_a0_6_subtotales_jerarquicos_estructura_vs_coincidencia_aritmetica():
    """Condición 4: Subtotales se detectan por estructura y código, no por coincidencia numérica casual."""
    # Caso estructural válido: código padre 1100 posterior a hijos 1101 y 1102 con nombre TOTAL
    h1 = CuentaRaw(
        linea=1, codigo="1101", nombre="Caja", monto=50.0,
        montos_columnas={"debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0,
                         "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    h2 = CuentaRaw(
        linea=2, codigo="1102", nombre="Banco", monto=50.0,
        montos_columnas={"debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0,
                         "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    padre_posterior = CuentaRaw(
        linea=3, codigo="1100", nombre="TOTAL DISPONIBLE", monto=100.0,
        montos_columnas={"debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
                         "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    cuentas = [h1, h2, padre_posterior]
    marcados = marcar_subtotales_jerarquicos(cuentas)
    assert marcados == 1
    assert padre_posterior.es_total is True
    assert "subtotal_jerarquico" in padre_posterior.columnas_derivadas

    # Caso coincidencia numérica SIN evidencia estructural: cuenta operativa 3500 "Gastos Varios" que casualmente suma 100
    acc1 = CuentaRaw(
        linea=1, codigo="1101", nombre="Caja", monto=40.0,
        montos_columnas={"debitos": 40.0, "creditos": 0.0, "saldo_deudor": 40.0, "saldo_acreedor": 0.0,
                         "activo": 40.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    acc2 = CuentaRaw(
        linea=2, codigo="2105", nombre="Proveedores", monto=60.0,
        montos_columnas={"debitos": 60.0, "creditos": 0.0, "saldo_deudor": 60.0, "saldo_acreedor": 0.0,
                         "activo": 60.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    acc3 = CuentaRaw(
        linea=3, codigo="3500", nombre="Gastos Administrativos", monto=100.0,
        montos_columnas={"debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
                         "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0},
        es_total=False,
    )
    cuentas_casuales = [acc1, acc2, acc3]
    marcados_casuales = marcar_subtotales_jerarquicos(cuentas_casuales)
    assert marcados_casuales == 0
    assert acc3.es_total is False, "No debe marcar subtotal por mera coincidencia aritmética sin relación de código"


def test_a0_7_cuentas_legitimas_sin_codigo_y_ruido_ocr():
    """Condición 4: Conserva cuentas legítimas sin código y descarta ruido OCR de firmas/notas."""
    c1 = CuentaRaw(linea=1, codigo="101", nombre="Caja", monto=10.0,
                   montos_columnas={"debitos": 10, "creditos": 0, "saldo_deudor": 10, "saldo_acreedor": 0,
                                    "activo": 10, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=False)
    c2 = CuentaRaw(linea=2, codigo="102", nombre="Banco", monto=10.0,
                   montos_columnas={"debitos": 10, "creditos": 0, "saldo_deudor": 10, "saldo_acreedor": 0,
                                    "activo": 10, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=False)
    c3 = CuentaRaw(linea=3, codigo="103", nombre="Clientes", monto=10.0,
                   montos_columnas={"debitos": 10, "creditos": 0, "saldo_deudor": 10, "saldo_acreedor": 0,
                                    "activo": 10, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=False)
    # Cuenta legítima sin código con saldo contable real
    c4 = CuentaRaw(linea=4, codigo=None, nombre="Otras cuentas menores", monto=10.0,
                   montos_columnas={"debitos": 10, "creditos": 0, "saldo_deudor": 10, "saldo_acreedor": 0,
                                    "activo": 10, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=False)
    # Línea de ruido OCR (firma con montos 0)
    c5 = CuentaRaw(linea=5, codigo=None, nombre="Firma Representante Legal", monto=0.0,
                   montos_columnas={"debitos": 0, "creditos": 0, "saldo_deudor": 0, "saldo_acreedor": 0,
                                    "activo": 0, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=False)
    subtotal = CuentaRaw(linea=6, codigo=None, nombre="SUBTOTAL", monto=40.0,
                         montos_columnas={"debitos": 40, "creditos": 0, "saldo_deudor": 40, "saldo_acreedor": 0,
                                          "activo": 40, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=True)
    final = CuentaRaw(linea=7, codigo=None, nombre="TOTALES IGUALES", monto=40.0,
                      montos_columnas={"debitos": 40, "creditos": 0, "saldo_deudor": 40, "saldo_acreedor": 0,
                                       "activo": 40, "pasivo": 0, "perdida": 0, "ganancia": 0}, es_total=True)
    cuentas = [c1, c2, c3, c4, c5, subtotal, final]
    cert = certificar_extraccion_columnas(cuentas, metodo="excel_8_columns")
    assert cert.diferencias.get("debitos") == 0.0, "La cuenta legítima sin código debe sumarse al total"
    assert cert.filas_evaluadas == 4, "Debe evaluar exactamente 4 filas de cuentas y excluir la firma OCR"


def test_a0_4_6_distincion_atribuciones_neto_vs_integral_y_ori():
    """Condición 6: Distingue atribuciones del resultado neto de las del resultado integral."""
    # Cuentas de balance para cuadrar activos y pasivos
    act = CuentaRaw(linea=1, codigo="1101", nombre="Efectivo", monto=100.0,
                    montos_periodos={"2024": 100.0}, seccion_contable="AC", es_total=False)
    pas = CuentaRaw(linea=2, codigo="2101", nombre="Proveedores", monto=50.0,
                    montos_periodos={"2024": 50.0}, seccion_contable="PC", es_total=False)
    pat = CuentaRaw(linea=3, codigo="3101", nombre="Capital", monto=50.0,
                    montos_periodos={"2024": 50.0}, seccion_contable="PAT", es_total=False)
    ctrl_ac = CuentaRaw(linea=4, codigo=None, nombre="TOTAL ACTIVOS CORRIENTES", monto=100.0,
                        montos_periodos={"2024": 100.0}, es_total=True)
    ctrl_pc = CuentaRaw(linea=5, codigo=None, nombre="TOTAL PASIVOS CORRIENTES", monto=50.0,
                        montos_periodos={"2024": 50.0}, es_total=True)
    ctrl_a = CuentaRaw(linea=6, codigo=None, nombre="TOTAL ACTIVOS", monto=100.0,
                       montos_periodos={"2024": 100.0}, es_total=True)
    ctrl_pp = CuentaRaw(linea=7, codigo=None, nombre="TOTAL PASIVO Y PATRIMONIO", monto=100.0,
                        montos_periodos={"2024": 100.0}, es_total=True)
    ctrl_pat = CuentaRaw(linea=8, codigo=None, nombre="TOTAL PATRIMONIO", monto=50.0,
                         montos_periodos={"2024": 50.0}, es_total=True)

    # Cuentas de resultados
    ingresos = CuentaRaw(linea=10, codigo="4101", nombre="Ingresos de actividades ordinarias", monto=200.0,
                         montos_periodos={"2024": 200.0}, seccion_contable="ER", es_total=False)
    costos = CuentaRaw(linea=11, codigo="5101", nombre="Costos de ventas", monto=-100.0,
                       montos_periodos={"2024": -100.0}, seccion_contable="ER", es_total=False)
    ctrl_gross = CuentaRaw(linea=12, codigo=None, nombre="Ganancia bruta", monto=100.0,
                           montos_periodos={"2024": 100.0}, es_total=True)
    gastos = CuentaRaw(linea=13, codigo="5201", nombre="Gastos de administracion", monto=-40.0,
                       montos_periodos={"2024": -40.0}, seccion_contable="ER", es_total=False)
    ctrl_pretax = CuentaRaw(linea=14, codigo=None, nombre="Ganancia antes de impuestos", monto=60.0,
                            montos_periodos={"2024": 60.0}, es_total=True)
    impuesto = CuentaRaw(linea=15, codigo="5301", nombre="Gasto por impuestos", monto=-10.0,
                         montos_periodos={"2024": -10.0}, seccion_contable="ER", es_total=False)
    ctrl_net = CuentaRaw(linea=16, codigo=None, nombre="Ganancia del ejercicio", monto=50.0,
                         montos_periodos={"2024": 50.0}, es_total=True)

    # Atribuciones del resultado neto: 45 + 5 = 50 (cuadra con ER_NET)
    attrib_parent = CuentaRaw(linea=17, codigo=None, nombre="Ganancia atribuible a los propietarios de la controladora", monto=45.0,
                              montos_periodos={"2024": 45.0}, es_total=True)
    attrib_nci = CuentaRaw(linea=18, codigo=None, nombre="Ganancia atribuible a participaciones no controladoras", monto=5.0,
                           montos_periodos={"2024": 5.0}, es_total=True)

    # ORI y Resultado Integral Total: ORI = 10, TCI = 50 + 10 = 60
    ctrl_oci = CuentaRaw(linea=19, codigo=None, nombre="Otro resultado integral", monto=10.0,
                         montos_periodos={"2024": 10.0}, es_total=True)
    ctrl_tci = CuentaRaw(linea=20, codigo=None, nombre="Resultado integral total", monto=60.0,
                         montos_periodos={"2024": 60.0}, es_total=True)

    # Atribuciones del resultado integral: 55 + 5 = 60 (cuadra con TCI)
    comp_attrib_parent = CuentaRaw(linea=21, codigo=None, nombre="Resultado integral atribuible a los propietarios de la controladora", monto=55.0,
                                   montos_periodos={"2024": 55.0}, es_total=True)
    comp_attrib_nci = CuentaRaw(linea=22, codigo=None, nombre="Resultado integral atribuible a participaciones no controladoras", monto=5.0,
                                montos_periodos={"2024": 5.0}, es_total=True)

    cuentas = [act, pas, pat, ctrl_ac, ctrl_pc, ctrl_a, ctrl_pp, ctrl_pat,
               ingresos, costos, ctrl_gross, gastos, ctrl_pretax, impuesto, ctrl_net,
               attrib_parent, attrib_nci, ctrl_oci, ctrl_tci, comp_attrib_parent, comp_attrib_nci]

    clasificaciones = [
        {"line": 1, "code": "AC.01", "name": "Efectivo", "amount": 100.0, "review": False},
        {"line": 2, "code": "PC.01", "name": "Proveedores", "amount": 50.0, "review": False},
        {"line": 3, "code": "PAT.01", "name": "Capital", "amount": 50.0, "review": False},
        {"line": 10, "code": "ER.01", "name": "Ingresos de actividades ordinarias", "amount": 200.0, "review": False},
        {"line": 11, "code": "ER.02", "name": "Costos de ventas", "amount": -100.0, "review": False},
        {"line": 13, "code": "ER.04", "name": "Gastos de administracion", "amount": -40.0, "review": False},
        {"line": 15, "code": "ER.10", "name": "Gasto por impuestos", "amount": -10.0, "review": False},
    ]

    cert = certificar_clasificado_final(
        cuentas, clasificaciones, ["2024"], ["CLP"],
        codigos_validos={"AC.01", "PC.01", "PAT.01", "ER.01", "ER.02", "ER.04", "ER.10", "ER.20", "ER.21"},
        periodo_actual="2024",
    )
    assert cert.estado == "certificada", f"Fallo en certificación IFRS: {cert.razones}"
    assert cert.diferencias.get("2024:ER_ATTRIB_NET") == 0.0
    assert cert.diferencias.get("2024:ER_ATTRIB_COMP") == 0.0
    assert cert.diferencias.get("2024:ER_TCI_EQUATION") == 0.0


def test_a0_8_distincion_guion_vs_ausencia_en_periodo():
    """Condición de término: parsear_monto distingue guion de ausencia."""
    # Guion explícito es 0.0
    assert parsear_monto("-", ".") == 0.0
    assert parsear_monto("—", ".") == 0.0
    assert parsear_monto("0", ".") == 0.0
    # None es ausencia
    assert parsear_monto(None, ".") is None
