from types import SimpleNamespace

from reporting_integrity import (
    certificar_cuadratura_homologada,
    debe_incorporar_resultado_derivado,
    resultado_final_fuente_certificado,
)


def fila(nombre, monto, origen, codigo, **extra):
    return {
        "nombre_original": nombre,
        "monto": monto,
        "origen_columna": origen,
        "codigo_clasificado": codigo,
        "es_total": False,
        **extra,
    }


def filas_cuadradas():
    return [
        fila("Caja", 100, "activo", "AC.01"),
        fila("Proveedor", 40, "pasivo", "PC.01"),
        fila("Capital", 50, "pasivo", "PAT.01"),
        fila("Ventas", 20, "ganancia", "ER.01"),
        fila("Gastos", 10, "perdida", "ER.04"),
    ]


def test_certifica_activo_igual_pasivo_mas_patrimonio_y_resultado():
    resultado = certificar_cuadratura_homologada(filas_cuadradas())

    assert resultado["certificada"] is True
    assert resultado["cuadra"] is True
    assert resultado["activo"] == 100
    assert resultado["pasivo"] == 40
    assert resultado["patrimonio_sin_resultado"] == 50
    assert resultado["resultado_periodo"] == 10
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_no_certifica_si_queda_cuenta_sin_clasificar_aunque_cuadre():
    rows = filas_cuadradas() + [
        fila("Ajuste pendiente", 1, "activo", ""),
        fila("Capital adicional", 1, "pasivo", "PAT.01"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["cuadra"] is True
    assert resultado["certificada"] is False
    assert len(resultado["sin_clasificar"]) == 1


def test_no_certifica_resultado_con_codigo_de_naturaleza_incompatible():
    rows = filas_cuadradas()
    rows[3]["codigo_clasificado"] = "ER.04"

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is False
    assert resultado["resultado"]["problemas"]


def test_pat10_reduce_patrimonio_sin_duplicar_resultado():
    rows = [
        fila("Caja", 100, "activo", "AC.01"),
        fila("Proveedor", 50, "pasivo", "PC.01"),
        fila("Capital", 70, "pasivo", "PAT.01"),
        fila("Cuenta socio", 20, "activo", "PAT.10"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is True
    assert resultado["patrimonio_sin_resultado"] == 50
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_pat07_capital_por_enterar_reduce_patrimonio():
    rows = [
        fila("Caja", 100, "activo", "AC.01"),
        fila("Capital suscrito", 120, "pasivo", "PAT.06"),
        fila("Capital por enterar", 20, "activo", "PAT.07"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is True
    assert resultado["cuadra"] is True
    assert resultado["patrimonio_sin_resultado"] == 100
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_obligacion_bancaria_deudora_se_presenta_como_contra_pasivo():
    rows = [
        fila("Caja", 100, "activo", "AC.01"),
        fila(
            "OBLIG .CON BCO E INST. FINANCIERA C/P",
            20,
            "activo",
            "PC.02",
        ),
        fila("Capital", 120, "pasivo", "PAT.01"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is True
    assert resultado["activo"] == 100
    assert resultado["pasivo"] == -20
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_depreciacion_acreedora_se_presenta_como_contra_activo():
    rows = [
        fila("Activo fijo", 120, "activo", "ANC.01"),
        fila("DEP.CONSTRUCCIONES", 20, "pasivo", "ANC.01.01"),
        fila("Proveedor", 40, "pasivo", "PC.01"),
        fila("Capital", 60, "pasivo", "PAT.01"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is True
    assert resultado["activo"] == 100
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_resultado_acumulado_en_lado_deudor_reduce_patrimonio():
    rows = [
        fila("Caja", 100, "activo", "AC.01"),
        fila("Proveedor", 40, "pasivo", "PC.01"),
        fila("Capital", 70, "pasivo", "PAT.01"),
        fila("Resultado acumulado", 10, "activo", "PAT.03"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["certificada"] is True
    assert resultado["cuadra"] is True
    assert resultado["patrimonio_sin_resultado"] == 60
    assert resultado["pasivo_mas_patrimonio"] == 100


def test_resultado_del_periodo_en_lado_deudor_reduce_patrimonio():
    rows = [
        fila("Caja", 90, "activo", "AC.01"),
        fila("Proveedor", 40, "pasivo", "PC.01"),
        fila("Capital", 60, "pasivo", "PAT.01"),
        fila("Pérdida del ejercicio", 10, "activo", "PAT.04"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["cuadra"] is True
    assert resultado["resultado_periodo"] == -10
    assert resultado["pasivo_mas_patrimonio"] == 90


def test_cierre_fuente_certificado_no_reemplaza_pat04_del_detalle():
    filas = [
        fila("Caja", 150, "activo", "AC.01"),
        fila("Proveedor", 10, "pasivo", "PC.01"),
        fila("Capital", 20, "pasivo", "PAT.01"),
        fila("Saldo patrimonial previo", 20, "pasivo", "PAT.04"),
        fila("Ventas", 100, "ganancia", "ER.01"),
    ]
    certificacion = SimpleNamespace(
        estado="certificada",
        totales_finales_validos=True,
        ecuacion_contable_fuente_valida=True,
        resultado_ejercicio=100,
        tipo_resultado="utilidad",
    )

    resultado = certificar_cuadratura_homologada(
        filas,
        resultado_final_fuente=resultado_final_fuente_certificado(
            certificacion,
        ),
    )

    assert resultado["certificada"] is True
    assert resultado["cuadra"] is True
    assert resultado["patrimonio_sin_resultado"] == 40
    assert resultado["resultado_periodo"] == 100
    assert resultado["resultado_final_fuente_incorporado"] is True
    assert resultado["resultado_final_fuente"] == 100
    assert resultado["resultado"]["problemas"] == []


def test_cierre_fuente_exige_certificacion_completa_y_ecuacion_valida():
    base = dict(
        estado="certificada",
        totales_finales_validos=True,
        ecuacion_contable_fuente_valida=True,
        resultado_ejercicio=-100,
        tipo_resultado="perdida",
    )
    assert resultado_final_fuente_certificado(SimpleNamespace(**base)) == -100
    assert resultado_final_fuente_certificado(SimpleNamespace(
        **{**base, "estado": "parcial"},
    )) is None
    assert resultado_final_fuente_certificado(SimpleNamespace(
        **{**base, "ecuacion_contable_fuente_valida": False},
    )) is None


def test_requiere_revision_bloquea_certificacion_aunque_la_ecuacion_cuadre():
    rows = filas_cuadradas()
    rows[0]["requiere_revision"] = True

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["cuadra"] is True
    assert resultado["certificada"] is False
    assert len(resultado["pendientes"]) == 1


def test_resultado_patrimonial_declarado_debe_coincidir_con_las_cuentas_er():
    rows = [
        fila("Caja", 98, "activo", "AC.01"),
        fila("Proveedor", 40, "pasivo", "PC.01"),
        fila("Capital", 50, "pasivo", "PAT.01"),
        fila("Utilidad declarada", 8, "pasivo", "PAT.04"),
        fila("Ventas", 20, "ganancia", "ER.01"),
        fila("Gastos", 10, "perdida", "ER.04"),
    ]

    resultado = certificar_cuadratura_homologada(rows)

    assert resultado["cuadra"] is True
    assert resultado["certificada"] is False
    assert any("PAT.04 no coincide" in problema for problema in resultado["motivos"])


def test_no_certifica_un_universo_vacio():
    resultado = certificar_cuadratura_homologada([])

    assert resultado["cuadra"] is True
    assert resultado["certificada"] is False
    assert "No se encontraron cuentas" in resultado["motivos"][0]


def test_estado_resultados_separado_no_duplica_patrimonio_en_cuadratura():
    filas = [
        fila("Caja", 100, "activo", "AC.01", estado_financiero="balance"),
        fila("Proveedor", 40, "pasivo", "PC.01", estado_financiero="balance"),
        fila("Capital", 60, "pasivo", "PAT.01", estado_financiero="balance"),
        fila("Ventas", 30, "ganancia", "ER.01", estado_financiero="resultados"),
        fila("Gastos", 10, "perdida", "ER.04", estado_financiero="resultados"),
    ]
    certificacion = SimpleNamespace(
        metodo="ocr_classified_two_columns", totales_finales_validos=True,
    )

    incluir_resultado = debe_incorporar_resultado_derivado(
        filas, certificacion,
    )
    resultado = certificar_cuadratura_homologada(
        filas, incluir_resultado_derivado=incluir_resultado,
    )

    assert incluir_resultado is False
    assert resultado["cuadra"] is True
    assert resultado["resultado_periodo"] == 0
    assert resultado["resultado_derivado_incorporado"] is False
