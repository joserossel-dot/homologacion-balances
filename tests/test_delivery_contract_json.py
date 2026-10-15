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
