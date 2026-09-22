from io import BytesIO
import pytest
import pypdfium2 as pdfium
from document_scope import parse_pages, page_count, select_pdf, render_page


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


def test_extractor_receives_only_selected_pdf(monkeypatch):
    import app_validacion as app
    source = BytesIO(pdf_bytes())
    source.name = "balance.pdf"
    monkeypatch.setattr(app.st, "session_state", {"document_pages": {"balance.pdf": [2]}})
    assert page_count(app._contenido_para_extraer(source)) == 1
    assert page_count(source.getvalue()) == 3


def test_pipeline_update_invalidates_only_derived_result_for_same_document(monkeypatch):
    import app_validacion as app

    source = BytesIO(pdf_bytes())
    source.name = "balance.pdf"
    other = "otro.xlsx"
    state = {
        "resultados": {source.name: "resultado antiguo", other: "conservar"},
        "extraction_certifications": {source.name: "certificado antiguo", other: "conservar"},
        "document_intel": {source.name: "intel antiguo"},
        "extraction_revisions": {source.name: 2},
        "extraction_pipeline_versions": {source.name: "ocr_rows_columns.v1"},
    }
    monkeypatch.setattr(app.st, "session_state", state)

    assert app._invalidar_extracciones_de_version_anterior([source]) is True
    assert source.name not in state["resultados"]
    assert state["resultados"][other] == "conservar"
    assert source.name not in state["extraction_certifications"]
    assert state["extraction_revisions"][source.name] == 3
    assert state["extraction_pipeline_versions"][source.name] == app.EXTRACTION_PIPELINE_VERSION


def test_manual_reextraction_clears_only_derived_state(monkeypatch):
    import app_validacion as app

    state = {
        "resultados": {"balance.pdf": "antiguo", "otro.pdf": "conservar"},
        "extraction_pending": {"balance.pdf": "pendiente"},
        "extraction_revisions": {"balance.pdf": 4},
        "file_metadata": {"balance.pdf": {"file_digest": "abc"}},
    }
    monkeypatch.setattr(app.st, "session_state", state)

    assert app._limpiar_estado_derivado_extraccion("balance.pdf") is True
    assert "balance.pdf" not in state["resultados"]
    assert state["resultados"]["otro.pdf"] == "conservar"
    assert "balance.pdf" not in state["extraction_pending"]
    assert state["file_metadata"]["balance.pdf"]["file_digest"] == "abc"
    assert state["extraction_revisions"]["balance.pdf"] == 5
