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
