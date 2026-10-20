import json
from types import SimpleNamespace

import pandas as pd

import app_validacion as app


def test_documento_sin_cuentas_entrega_diagnostico_json_serializable():
    certificacion = SimpleNamespace(
        estado="fallida",
        metodo="ocr_coordinates_8_amounts",
        orientacion_certificada=False,
        razones=["Sin evidencia de orientación"],
    )
    estado = app._evaluar_estado_entrega_documento(
        pd.DataFrame(), certificacion, {},
    )
    payload = app._payload_entrega_json(
        archivo_nombre="sin-cuentas.pdf",
        meta=None,
        estado_entrega=estado,
        emision={"definitivo": False, "motivos": estado["razones"]},
        presentacion=pd.DataFrame(),
        detalle=pd.DataFrame(),
    )

    assert estado["estado"] == "NO_LEGIBLE"
    assert payload["emision"]["definitiva"] is False
    assert payload["balance_homologado"] == []
    assert payload["cuentas_origen"] == []
    json.dumps(payload, ensure_ascii=False)


def test_json_entrega_expone_cuadratura_fuente_sin_confundirla_con_homologada():
    certificacion = SimpleNamespace(
        estado="certificada",
        metodo="native_layout_8_columns",
        orientacion_certificada=None,
        razones=[],
        ecuacion_contable_fuente_valida=True,
        diferencia_ecuacion_contable_fuente=0.0,
    )
    filas = pd.DataFrame([{
        "nombre_original": "Caja",
        "monto": 100,
        "origen_columna": "activo",
        "codigo_clasificado": "AC.01",
    }])
    estado = app._evaluar_estado_entrega_documento(filas, certificacion, {})
    payload = app._payload_entrega_json(
        archivo_nombre="balance.pdf",
        meta=None,
        estado_entrega=estado,
        emision={"definitivo": False, "motivos": estado["razones"]},
        presentacion=pd.DataFrame(),
        detalle=filas,
    )

    assert payload["estado_entrega"]["certificacion_extraccion"][
        "cuadratura_fuente"
    ] == {"validada": True, "diferencia": 0.0}
    assert payload["estado_entrega"]["cuadratura_homologada"]["certificada"] is False
    json.dumps(payload, ensure_ascii=False)


def test_diagnostico_bloqueado_no_expone_filas_reutilizables():
    estado = {
        "estado": "EXTRACCION_NO_VALIDADA",
        "etiqueta": "Extracción no validada",
        "exportacion_final_permitida": False,
        "exportacion_revision_permitida": False,
        "razones": ["Los controles fuente no concilian."],
    }
    presentacion = pd.DataFrame([{
        "codigo_clasificado": "AC.01", "monto_total": 100,
    }])
    detalle = pd.DataFrame([{
        "nombre_original": "Caja", "monto": 100,
        "codigo_clasificado": "AC.01",
    }])

    payload = app._payload_entrega_json(
        archivo_nombre="bloqueado.pdf",
        meta=None,
        estado_entrega=estado,
        emision={"definitivo": False, "motivos": estado["razones"]},
        presentacion=presentacion,
        detalle=detalle,
    )

    assert payload["emision"]["definitiva"] is False
    assert payload["balance_homologado"] == []
    assert payload["cuentas_origen"] == []
    json.dumps(payload, ensure_ascii=False)


def test_ui_bloqueada_ofrece_solo_diagnostico_json(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.delenv("PILOT_MODE", raising=False)
    monkeypatch.setenv("QUALITY_CONTROL_ENFORCE_EXPORT", "false")
    filas = [
        {
            "nombre_original": "Caja", "codigo_original": "1101-01",
            "monto": 100, "origen_columna": "activo",
            "origen_columna_efectiva": "activo", "codigo_clasificado": "AC.01",
            "es_total": False, "requiere_revision": False,
            "metodo": "validacion_humana", "confianza": 1.0,
            "nombre_revision_usuario": "",
        },
        {
            "nombre_original": "Capital", "codigo_original": "2401-01",
            "monto": 100, "origen_columna": "pasivo",
            "origen_columna_efectiva": "patrimonio", "codigo_clasificado": "PAT.01",
            "es_total": False, "requiere_revision": False,
            "metodo": "validacion_humana", "confianza": 1.0,
            "nombre_revision_usuario": "",
        },
    ]

    def render(rows):
        import json as json_local
        from types import SimpleNamespace

        import pandas as pandas_local
        import streamlit as st

        import app_validacion as app_local
        from extractor_metadata import MetadataEmpresa
        from reporting_integrity import catalogo_local

        nombre = "bloqueado.pdf"
        st.session_state.metadata_files = {
            nombre: MetadataEmpresa(moneda="$"),
        }
        st.session_state.extraction_certifications = {
            nombre: SimpleNamespace(
                estado="fallida", metodo="ocr_coordinates_8_amounts",
                orientacion_certificada=False,
                razones=["Los controles fuente no concilian."],
            ),
        }
        previo = app_local.st.download_button

        def capturar(label, **kwargs):
            exportaciones = list(st.session_state.get("exportaciones", []))
            exportaciones.append({"label": label, **kwargs})
            st.session_state.exportaciones = exportaciones

        app_local.st.download_button = capturar
        try:
            app_local._tab_balance(
                pandas_local.DataFrame(rows), catalogo_local(), nombre,
            )
        finally:
            app_local.st.download_button = previo

        descarga = st.session_state.exportaciones[0]
        st.session_state.payload_diagnostico = json_local.loads(
            descarga["data"].decode("utf-8"),
        )

    at = AppTest.from_function(render, args=(filas,)).run(timeout=20)

    assert not at.exception
    exportaciones = at.session_state.exportaciones
    assert len(exportaciones) == 1
    assert exportaciones[0]["label"] == "Descargar diagnóstico (JSON)"
    assert exportaciones[0]["mime"] == "application/json"
    assert at.session_state.payload_diagnostico["balance_homologado"] == []
    assert at.session_state.payload_diagnostico["cuentas_origen"] == []
