from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import app_validacion as app
import parser_universal as parser


def cuentas_con_controles():
    lines = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 40 0 40 0 40 0 0",
        "410101 Ventas 0 60 0 60 0 0 0 60",
        "Sumas 100 100 100 100 100 40 0 60",
        "Resultado positivo 0 0 0 0 0 60 60 0",
        "Sumas totales 100 100 100 100 100 100 60 60",
    ]
    return [
        parser.parsear_linea(line, i, parser.FormatoCodigo.COMPACTO, ".")
        for i, line in enumerate(lines)
    ]


def test_controles_reconocidos_no_se_suman_como_cuentas():
    cuentas = cuentas_con_controles()
    cert = parser.certificar_extraccion_columnas(cuentas)
    assert all(c.es_total for c in cuentas[3:])
    assert cert.estado == "certificada"
    assert cert.filas_evaluadas == 3
    assert cert.resultado_ejercicio == 60
    assert cert.totales_finales_validos is True
    assert not any(cert.diferencias.values())


def test_extraccion_no_certificada_fuerza_revision_y_control_no_se_clasifica():
    certificada = SimpleNamespace(estado="certificada")
    parcial = SimpleNamespace(estado="parcial")

    assert not app._requiere_revision_por_extraccion(certificada)
    assert app._requiere_revision_por_extraccion(parcial)
    assert app._requiere_revision_por_extraccion(None)
    assert "parcial" in app._nota_revision_por_extraccion(parcial)

    control = cuentas_con_controles()[3]
    fila = app._fila_control_extraccion(control)

    assert fila["es_total"] is True
    assert fila["codigo_clasificado"] == ""
    assert fila["metodo"] == "extraction_control"
    assert fila["requiere_revision"] is False


def test_bloqueo_de_subtotal_no_verificable_no_induce_reconstruccion():
    mensaje = app._mensaje_bloqueo_extraccion(SimpleNamespace(
        diagnostico="SUBTOTAL_IMPRESO_NO_VERIFICABLE",
    ))

    assert "formato fue reconocido" in mensaje
    assert "no complete el subtotal por suma" in mensaje
    assert "copia legible" in mensaje


def test_bloqueo_generico_conserva_instruccion_de_correccion():
    mensaje = app._mensaje_bloqueo_extraccion(SimpleNamespace(
        diagnostico="CONTROLES_NO_CONCILIAN",
    ))

    assert "no reproduce los totales impresos" in mensaje


@pytest.mark.parametrize("nombre", ["Resultado positivo", "Resultado 'positivo", "Resultado negativo"])
def test_resultado_de_cierre_se_reconoce_sin_confundir_cuenta_codificada(nombre):
    control = parser.parsear_linea(f"{nombre} 0 0 0 0 0 60 60 0", 1, parser.FormatoCodigo.COMPACTO, ".")
    cuenta = parser.parsear_linea(f"2301001 {nombre} 0 60 0 60 0 60 0 0", 2, parser.FormatoCodigo.COMPACTO, ".")
    assert control.es_total
    assert not cuenta.es_total


def test_excluir_no_borra_controles_reconocidos():
    cuentas = cuentas_con_controles()
    edited = pd.DataFrame([
        {"linea": c.linea, "total": c.es_total, "excluir": c.es_total, **c.montos_columnas}
        for c in cuentas
    ])
    corrected, cert = app._aplicar_correcciones_extraccion(cuentas, edited)
    assert len(corrected) == len(cuentas)
    assert cert.estado == "certificada"
    assert [c.montos_columnas for c in corrected] == [c.montos_columnas for c in cuentas]


def test_diagnostico_no_pide_excluir_ni_cambiar_cifras_de_control():
    controls = cuentas_con_controles()[3:]
    diagnosis = app._diagnosticar_filas_extraccion(controls)
    for c in controls:
        assert "No necesita excluirlo" in diagnosis[c.linea]["accion_sugerida"]
        assert diagnosis[c.linea]["valores_sugeridos"] == ""


def test_diferencias_reales_siguen_bloqueadas_aunque_se_excluyan_totales():
    cuentas = cuentas_con_controles()
    cuentas[3] = replace(cuentas[3], montos_columnas={**cuentas[3].montos_columnas, "debitos": 200, "creditos": 200})
    edited = pd.DataFrame([
        {"linea": c.linea, "total": c.es_total, "excluir": c.es_total, **c.montos_columnas}
        for c in cuentas
    ])
    _, cert = app._aplicar_correcciones_extraccion(cuentas, edited)
    assert cert.estado == "fallida"
    assert cert.diferencias["debitos"] == -100
    assert "no se corrige reclasificando" in app._explicar_diferencia_controles(cert)


def test_no_atribuye_a_subtotal_una_fila_inconsistente():
    cert = SimpleNamespace(
        diferencias={c: (-100 if c in ("debitos", "creditos") else 0) for c in parser.RAW_MONETARY_COLUMNS},
        filas_inconsistentes=[1],
    )
    assert app._explicar_diferencia_controles(cert) == ""


@pytest.mark.parametrize("separator", ["·", "•"])
def test_recupera_codigo_separado_por_punto_tipografico(separator):
    line = parser.normalizar_codigo_ocr(f"3101003{separator} Beneficio de Estudios 550000 25000 525000 0 0 0 525000 0")
    c = parser.parsear_linea(line, 1, parser.FormatoCodigo.COMPACTO, ".")
    assert c.codigo == "3101003"
    assert c.nombre == "Beneficio de Estudios"
    assert c.montos_columnas["perdida"] == 525000


def test_reconoce_encabezados_s_deudor_s_acreedor():
    headers = ["Cuenta", "Debe", "Haber", "S.deudor", "S.Acreedor", "Activo", "Pasivo", "Pérdidas", "Ganancias"]
    words = [{"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 10} for i, text in enumerate(headers)]
    words += [{"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 30} for i, text in enumerate(["Caja", "100", "0", "100", "0", "100", "0", "0", "0"])]
    page = SimpleNamespace(extract_words=lambda **kwargs: words)
    lines, centers = parser._extraer_tabla_balance_por_coordenadas(page)
    assert centers is not None
    assert lines == ["Caja 100 0 100 0 100 0 0 0"]


def test_reconoce_variantes_ocr_de_acreedor_y_pasivo_en_encabezado():
    headers = ["Cuenta", "Debe", "Haber", "Deudor", "Vercedor", "Activo", "Pasiva", "Pérdidas", "Ganancias"]
    words = [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 10}
        for i, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 30}
        for i, text in enumerate(["Proveedores", "0", "100", "0", "100", "0", "100", "0", "0"])
    ]

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kwargs: words),
    )

    assert centers is not None
    assert lines == ["Proveedores 0 100 0 100 0 100 0 0"]


def test_reconoce_haber_con_rastro_de_saldo_deudor_en_encabezado():
    headers = [
        "Cuenta", "Debe", "Haber___S", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 30}
        for index, text in enumerate(
            ["Caja", "100", "0", "100", "0", "100", "0", "0", "0"],
        )
    ]

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kwargs: words),
    )

    assert centers is not None
    assert lines == ["Caja 100 0 100 0 100 0 0 0"]


def test_celda_geometrica_repara_separador_de_miles_omitido_sin_desplazarla():
    headers = [
        "Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 30}
        for index, text in enumerate([
            "Caja", "3.732989.407", "0", "3.732989.407", "0",
            "3.732989.407", "0", "0", "0",
        ])
    ]

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kwargs: words),
    )
    cuenta = parser.parsear_linea(
        parser.normalizar_linea_ocr_tabla(lines[0]),
        1,
        parser.FormatoCodigo.COMPACTO,
        ".",
        0.75,
    )

    assert lines == [
        "Caja 3.732.989.407 0 3.732.989.407 0 3.732.989.407 0 0 0",
    ]
    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 3_732_989_407
    assert cuenta.montos_columnas["creditos"] == 0
    assert cuenta.montos_columnas["activo"] == 3_732_989_407


def test_reconoce_variantes_ocr_de_encabezado_con_mayor_resolucion():
    headers = ["Cuenta", "Dche", "Haber", "Deudor", "Vervedor", "Aclivo", "Pasivo", "Perdida", "Ganancia"]
    words = [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 10}
        for i, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 30}
        for i, text in enumerate(["Caja", "100", "0", "100", "0", "100", "0", "0", "0"])
    ]

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kwargs: words),
    )

    assert centers is not None
    assert lines == ["Caja 100 0 100 0 100 0 0 0"]


def test_borde_ocr_pegado_a_importe_no_desplaza_las_ocho_columnas():
    headers = ["Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo", "Pasivo", "Pérdidas", "Ganancias"]
    words = [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 10}
        for i, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": i * 70, "x1": i * 70 + 40, "top": 30}
        for i, text in enumerate(["Caja", "100|", "0", "100", "0", "100", "0", "0", "|0"])
    ]

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kwargs: words),
    )

    assert parser.normalizar_token_ocr("3.108.206.983|") == "3.108.206.983"
    assert parser.normalizar_token_ocr("|478.724") == "478.724"
    assert parser.normalizar_token_ocr("N*15807") == "N*15807"
    assert parser.PATRON_MONTOS.fullmatch("0")
    assert not parser.PATRON_MONTOS.fullmatch(",")
    assert not parser.PATRON_MONTOS.fullmatch(".")
    assert lines == ["Caja 100 0 100 0 100 0 0 0"]


def test_control_ocr_de_ocho_columnas_se_canoniza_y_detiene_el_pie():
    headers = [
        "Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]

    def fila(top, etiqueta, importes):
        fila_etiqueta = [
            {"text": text, "x0": index * 20, "x1": index * 20 + 16, "top": top}
            for index, text in enumerate(etiqueta)
        ]
        fila_importes = [
            {"text": text, "x0": (index + 1) * 70, "x1": (index + 1) * 70 + 40, "top": top}
            for index, text in enumerate(importes)
        ]
        return fila_etiqueta + fila_importes

    words += fila(30, ["Caja"], ["100", "0", "100", "0", "100", "0", "0", "0"])
    words += fila(50, ["Sub", "Total", "o"], ["100", "100", "100", "100", "100", "40", "0", "60"])
    words += fila(70, ["tilidad", "o", "y"], ["0", "0", "0", "0", "0", "60", "60", "0"])
    words += fila(90, ["OTALES"], ["100", "100", "100", "100", "100", "100", "60", "60"])
    words += fila(110, ["RESPONSABLE", "DEL", "INFORME"], ["0"] * 8)
    page = SimpleNamespace(extract_words=lambda **kwargs: words)

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(page)

    assert lines == [
        "Caja 100 0 100 0 100 0 0 0",
        "SUBTOTAL 100 100 100 100 100 40 0 60",
        "UTILIDAD DEL EJERCICIO 0 0 0 0 0 60 60 0",
        "TOTALES 100 100 100 100 100 100 60 60",
    ]
    assert parser.parsear_linea(
        "Sub Total 100 100 100 100 100 40 0 60",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
    ).es_total
    assert parser._normalizar_etiqueta_control_ocr(
        "tilidad [o] y",
        [None, None, None, {"token": "0"}, None, {"token": "60"}, {"token": "60"}, None],
    ) == "UTILIDAD DEL EJERCICIO"
    assert parser._normalizar_etiqueta_control_ocr(
        "Utilidad j",
        [None, None, None, None, None, {"token": "60"}, {"token": "60"}, None],
    ) == "UTILIDAD DEL EJERCICIO"
    assert parser._normalizar_etiqueta_control_ocr(
        "PERDIDA DEL EJERCICIO l :",
        [None, None, None, None, {"token": "60"}, None, None, {"token": "60"}],
    ) == "PERDIDA DEL EJERCICIO"


def test_conserva_subtotal_anonimo_anclado_por_utilidad_del_ejercicio():
    headers = [
        "Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]
    words += [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 30}
        for index, text in enumerate(
            ["Caja", "100", "0", "100", "0", "100", "0", "0", "0"]
        )
    ]
    words += [
        {"text": text, "x0": (index + 1) * 70, "x1": (index + 1) * 70 + 40, "top": 50}
        for index, text in enumerate(
            ["100", "100", "100", "100", "100", "40", "0", "60"]
        )
    ]
    words += [
        {"text": "UTILIDAD DEL EJERCICIO", "x0": 0, "x1": 150, "top": 70},
        *[
            {"text": text, "x0": (index + 1) * 70, "x1": (index + 1) * 70 + 40, "top": 70}
            for index, text in enumerate(["0", "0", "0", "0", "0", "60", "60", "0"])
        ],
    ]
    page = SimpleNamespace(extract_words=lambda **kwargs: words)

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(page)

    assert "SUBTOTAL SIN ETIQUETA 100 100 100 100 100 40 0 60" in lines


def test_arrastre_y_subtotal_anonimo_se_certifican_sin_contar_nota_al_pie():
    lines = parser.etiquetar_subtotales_anonimos([
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 40 0 40 0 40 0 0",
        "410101 Ventas 0 60 0 60 0 0 0 60",
        "De la Página Anterior 100 100 100 100 100 40 0 60",
        "100 100 100 100 100 40 0 60",
        "UTILIDAD DEL EJERCICIO 0 0 0 0 0 60 60 0",
        "SUMAS IGUALES 100 100 100 100 100 100 60 60",
        "De acuerdo al ARTICULO del CODIGO TRIBUTARIO dejo 0 0 0 0 0 100 0 0",
    ])
    cuentas = [
        cuenta
        for index, line in enumerate(lines)
        if (
            cuenta := parser.parsear_linea(
                line, index, parser.FormatoCodigo.COMPACTO, ".",
            )
        ) is not None
    ]

    arrastre = next(cuenta for cuenta in cuentas if "Página Anterior" in cuenta.nombre)
    subtotal = next(cuenta for cuenta in cuentas if cuenta.nombre == "SUBTOTAL SIN ETIQUETA")
    cert = parser.certificar_extraccion_columnas(cuentas)

    assert arrastre.es_total
    assert subtotal.es_total
    assert cert.estado == "certificada"
    assert not any(cert.diferencias.values())
    assert not any("ARTICULO" in cuenta.nombre for cuenta in cuentas)


@pytest.mark.parametrize("lectura_ocr", ["Amerior", "Anterlor"])
def test_arrastre_ocr_mal_leido_se_normaliza_como_control(lectura_ocr):
    original = f"De la Página {lectura_ocr} 100 100 100 100 100 40 0 60"

    normalizada = parser.normalizar_linea_ocr_tabla(original)
    cuenta = parser.parsear_linea(
        normalizada, 0, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert normalizada == "De la Página Anterior 100 100 100 100 100 40 0 60"
    assert cuenta is not None
    assert cuenta.es_total
    assert cuenta.nombre == "De la Página Anterior"
    assert cuenta.montos_columnas == {
        "debitos": 100.0,
        "creditos": 100.0,
        "saldo_deudor": 100.0,
        "saldo_acreedor": 100.0,
        "activo": 100.0,
        "pasivo": 40.0,
        "perdida": 0.0,
        "ganancia": 60.0,
    }


def test_fusiona_control_partido_en_columnas_complementarias():
    headers = [
        "Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 70, "x1": index * 70 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]
    words += [
        {"text": "Total", "x0": 0, "x1": 40, "top": 30},
        *[
            {"text": text, "x0": column * 70, "x1": column * 70 + 40, "top": 30}
            for column, text in ((1, "100"), (3, "100"), (5, "100"), (7, "60"))
        ],
        *[
            {"text": text, "x0": column * 70, "x1": column * 70 + 40, "top": 50}
            for column, text in ((2, "100"), (4, "100"), (6, "40"), (8, "60"))
        ],
    ]
    page = SimpleNamespace(extract_words=lambda **kwargs: words)

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(page)

    assert lines == ["Total 100 100 100 100 100 40 60 60"]


def test_total_y_total_perdida_partidos_certifican_cierre():
    lines = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Pasivo 0 160 0 160 0 160 0 0",
        "510101 Gasto 60 0 60 0 0 0 60 0",
        "Total 160 160 160 160 100 160 60 0",
        "TOTAL PERDIDA 0 0 0 0 60 0 0 60",
        "TOTAL GENERAL 160 160 160 160 160 160 60 60",
    ]
    cuentas = [
        parser.parsear_linea(line, index, parser.FormatoCodigo.COMPACTO, ".")
        for index, line in enumerate(lines)
    ]

    cert = parser.certificar_extraccion_columnas(cuentas)

    assert cert.estado == "certificada"
    assert cert.resultado_ejercicio == -60
    assert not any(cert.diferencias.values())


def test_total_despues_de_resultado_se_reconoce_como_cierre_final():
    lines = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Pasivo 0 160 0 160 0 160 0 0",
        "510101 Gasto 60 0 60 0 0 0 60 0",
        "Sumas 160 160 160 160 100 160 60 0",
        "Resultado 0 0 0 0 60 0 0 60",
        "Total 160 160 160 160 160 160 60 60",
    ]
    cuentas = [
        parser.parsear_linea(line, index, parser.FormatoCodigo.COMPACTO, ".")
        for index, line in enumerate(lines)
    ]

    cert = parser.certificar_extraccion_columnas(cuentas)

    assert cert.estado == "certificada"
    assert cert.totales_finales_validos is True
    assert cert.columnas_finales_validadas is True
    assert not any(cert.diferencias.values())


def test_total_despues_de_resultado_sin_sumas_no_se_promueve_a_cierre():
    lines = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Pasivo 0 160 0 160 0 160 0 0",
        "510101 Gasto 60 0 60 0 0 0 60 0",
        "Resultado 0 0 0 0 60 0 0 60",
        "Total 160 160 160 160 160 160 60 60",
    ]
    cuentas = [
        parser.parsear_linea(line, index, parser.FormatoCodigo.COMPACTO, ".")
        for index, line in enumerate(lines)
    ]

    cert = parser.certificar_extraccion_columnas(cuentas)

    assert cert.estado == "fallida"
    assert cert.diagnostico == "CONTROLES_NO_CONCILIAN"
    assert cert.totales_finales_validos is None


def test_visor_aparece_debajo_de_correccion_a_ancho_completo(monkeypatch):
    calls = []
    monkeypatch.setattr(app, "_mostrar_correccion_extraccion", lambda name: calls.append(("correccion", name)))
    monkeypatch.setattr(app.st, "divider", lambda: calls.append(("divider",)))
    monkeypatch.setattr(app.st, "subheader", lambda title: calls.append(("titulo", title)))
    monkeypatch.setattr(app, "_visor_documento", lambda archivo, **kwargs: calls.append(("visor", archivo, kwargs)))
    app._mostrar_etapa_correccion_extraccion("archivo", "balance.pdf")
    assert calls[0] == ("correccion", "balance.pdf")
    assert calls[-1] == ("visor", "archivo", {"altura": "58vh", "mostrar_titulo": False})


def test_ui_no_habilita_clasificacion_sin_control_independiente():
    at = AppTest.from_string('''
import streamlit as st
import app_validacion as app
import parser_universal as parser
if "extraction_pending" not in st.session_state:
    c = parser.parsear_linea("110101 Caja 100 0 100 0 100 0 0 0", 0, parser.FormatoCodigo.COMPACTO, ".")
    st.session_state.extraction_pending = {"balance.pdf": parser.ResultadoParseo(
        archivo="balance.pdf", formato_codigo=parser.FormatoCodigo.COMPACTO,
        separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[c], certificacion_extraccion=parser.certificar_extraccion_columnas([c]),
    )}
    st.session_state.extraction_resolved = {}
    st.session_state.resultados = {}
app._mostrar_correccion_extraccion("balance.pdf")
''').run()
    assert not at.exception
    next(b for b in at.button if "Verificar correcciones" in b.label).click().run()
    assert not at.exception
    assert "balance.pdf" in at.session_state.extraction_pending
    assert not at.session_state.extraction_resolved
    assert at.session_state.extraction_revisions["balance.pdf"] == 1
    assert any("Falta un subtotal" in w.value for w in at.warning)


def test_ui_separa_controles_sin_opcion_de_excluir_y_conserva_el_bloqueo():
    at = AppTest.from_string('''
import streamlit as st
import app_validacion as app
import parser_universal as parser
if "extraction_pending" not in st.session_state:
    lines = ["110101 Caja 100 0 100 0 100 0 0 0", "Sumas 200 0 100 0 100 0 0 0"]
    cuentas = [parser.parsear_linea(line, i, parser.FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lines)]
    st.session_state.extraction_pending = {"balance.pdf": parser.ResultadoParseo(
        archivo="balance.pdf", formato_codigo=parser.FormatoCodigo.COMPACTO,
        separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
        cuentas=cuentas, certificacion_extraccion=parser.certificar_extraccion_columnas(cuentas),
    )}
    st.session_state.extraction_resolved = {}
    st.session_state.resultados = {}
app._mostrar_correccion_extraccion("balance.pdf")
''').run()
    assert not at.exception
    tables = [el.value for el in at.dataframe if "total" in el.value.columns]
    assert len(tables) == 2
    detail, controls = tables
    assert not detail["total"].any()
    assert controls["total"].all()
    assert "excluir" not in controls.columns
    next(b for b in at.button if "Verificar correcciones" in b.label).click().run()
    assert not at.exception
    assert not at.session_state.extraction_resolved
    assert len(at.session_state.extraction_pending["balance.pdf"].cuentas) == 2
    assert at.session_state.extraction_pending["balance.pdf"].certificacion_extraccion.estado == "fallida"


def test_editores_agrupados_con_separadores_y_columnas_finales_primero():
    import json
    at = AppTest.from_string("""
import streamlit as st
import app_validacion as app
import parser_universal as parser
lines = ["110101 Caja 100 0 100 0 100 0 0 0", "Sumas 200 0 100 0 100 0 0 0"]
cuentas = [parser.parsear_linea(line, i, parser.FormatoCodigo.COMPACTO, ".") for i, line in enumerate(lines)]
st.session_state.extraction_pending = {"balance.pdf": parser.ResultadoParseo(
    archivo="balance.pdf", formato_codigo=parser.FormatoCodigo.COMPACTO,
    separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
    cuentas=cuentas, certificacion_extraccion=parser.certificar_extraccion_columnas(cuentas),
)}
app._mostrar_correccion_extraccion("balance.pdf")
""").run()
    assert not at.exception
    editors = [el for el in at.dataframe if "total" in el.value.columns]
    assert len(editors) == 2
    assert editors[0].proto.form_id == editors[1].proto.form_id
    assert editors[0].proto.form_id.startswith("extraction_batch_")
    assert list(editors[0].proto.column_order)[3:7] == ["activo", "pasivo", "perdida", "ganancia"]
    for editor in editors:
        config = json.loads(editor.proto.columns)
        for column in parser.RAW_MONETARY_COLUMNS:
            assert config[column]["type_config"]["format"] == "localized"
