from io import BytesIO
import pytest
import pypdfium2 as pdfium
from document_scope import (
    parse_pages, page_count, render_page, select_pdf, sugerir_periodos_balance,
)


def pdf_bytes():
    with pdfium.PdfDocument.new() as doc:
        for width in [100, 200, 300]:
            doc.new_page(width, 400).close()
        data = BytesIO()
        doc.save(data)
        return data.getvalue()


@pytest.mark.parametrize("text", ["", "0", "4", "3-1", "-1", "1,,2", "dos", "1.5"])
def test_reject_invalid_selection(text):
    with pytest.raises(ValueError):
        parse_pages(text, 3)


def test_selection_preserves_original_order():
    assert parse_pages("3, 1-2, 2", 3) == [1, 2, 3]
    original = pdf_bytes()
    selected = select_pdf(original, [1, 3])
    assert page_count(original) == 3
    assert page_count(selected) == 2
    with pdfium.PdfDocument(selected) as doc:
        assert doc[0].get_width() == 100
        assert doc[1].get_width() == 300
    assert select_pdf(original, [1, 2, 3]) == original
    assert render_page(original, 2).startswith(b"\x89PNG")


def test_sugiere_periodos_distintos_sin_incluir_pies_aislados(monkeypatch):
    import document_scope

    monkeypatch.setattr(document_scope, "_extraer_textos_paginas", lambda _content: [
        "BALANCE TRIBUTARIO Desde:01-10-2017 Hasta:01-10-2018\n1101001 Caja",
        "2101001 Proveedores",
        "Página 4 de 4",
        "BALANCE TRIBUTARIO Desde 01-10-2018 hasta 01-10-2019\n1101001 Caja",
        "2101001 Proveedores",
        "6101001 Gastos",
        "Página 4 de 4",
    ])

    assert sugerir_periodos_balance(b"pdf") == [
        {"periodo": "01-10-2017 a 01-10-2018", "paginas": [1, 2]},
        {"periodo": "01-10-2018 a 01-10-2019", "paginas": [4, 5, 6]},
    ]


def test_no_sugiere_un_unico_periodo(monkeypatch):
    import document_scope

    monkeypatch.setattr(document_scope, "_extraer_textos_paginas", lambda _content: [
        "BALANCE TRIBUTARIO Desde 01-10-2017 hasta 01-10-2018",
        "1101001 Caja",
    ])

    assert sugerir_periodos_balance(b"pdf") == []


def test_scope_ui_does_not_extract_before_confirmation():
    from streamlit.testing.v1 import AppTest
    def run(content):
        import streamlit as st
        from io import BytesIO
        import app_validacion as app
        source = BytesIO(content)
        source.name = "balance.pdf"
        previous = app._visor_documento
        app._visor_documento = lambda *args, **kwargs: None
        try:
            if app._confirmar_alcance_documentos([source]):
                st.success("Listo para extraer")
        finally:
            app._visor_documento = previous
    at = AppTest.from_function(run, args=(pdf_bytes(),)).run()
    assert not at.exception and not at.success
    at.radio[0].set_value("Sólo las seleccionadas")
    at.text_input[0].set_value("2-3")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state.document_pages["balance.pdf"] == [2, 3]
    assert at.success
    # Revisar el alcance sin cambiarlo no borra decisiones anteriores.
    at.session_state.resultados = {"balance.pdf": "decisiones confirmadas"}
    at.session_state.document_scope_editing = True
    at.run()
    at.button[0].click().run()
    assert at.session_state.resultados == {"balance.pdf": "decisiones confirmadas"}
    # Una selección diferente sí invalida sólo el documento modificado.
    at.session_state.resultados["otro.xlsx"] = "conservar"
    at.session_state.document_scope_editing = True
    at.run()
    at.text_input[0].set_value("1")
    at.button[0].click().run()
    assert at.session_state.resultados == {"otro.xlsx": "conservar"}
    assert at.session_state.document_pages["balance.pdf"] == [1]


def test_scope_ui_aplica_sugerencia_de_periodo_solo_al_confirmarla():
    from streamlit.testing.v1 import AppTest

    def run(content):
        import streamlit as st
        from io import BytesIO
        import app_validacion as app

        source = BytesIO(content)
        source.name = "balance.pdf"
        previous_visor = app._visor_documento
        previous_sugerencia = app.sugerir_periodos_balance
        app._visor_documento = lambda *args, **kwargs: None
        app.sugerir_periodos_balance = lambda _content: [{
            "periodo": "01-01-2020 a 31-12-2020", "paginas": [1, 2],
        }]
        try:
            if app._confirmar_alcance_documentos([source]):
                st.success("Listo para extraer")
        finally:
            app._visor_documento = previous_visor
            app.sugerir_periodos_balance = previous_sugerencia

    at = AppTest.from_function(run, args=(pdf_bytes(),)).run()
    assert not at.exception and not at.success
    at.selectbox[1].set_value(
        "01-01-2020 a 31-12-2020 (págs. 1, 2)",
    )
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state.document_pages["balance.pdf"] == [1, 2]
    assert at.success


def test_extractor_receives_only_selected_pdf(monkeypatch):
    import app_validacion as app
    source = BytesIO(pdf_bytes())
    source.name = "balance.pdf"
    monkeypatch.setattr(app.st, "session_state", {"document_pages": {"balance.pdf": [2]}})
    assert page_count(app._contenido_para_extraer(source)) == 1
    assert page_count(source.getvalue()) == 3
