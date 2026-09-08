from types import SimpleNamespace
from functools import partial
import hashlib
from persistence.contracts import AuthenticatedActor

import pandas as pd

import app_validacion as app
from parser_universal import CuentaRaw, CertificacionExtraccion


def setup(monkeypatch):
    monkeypatch.setattr(app, "_recertificar_balance_clasificado", partial(
        app._recertificar_balance_clasificado,
        catalogo={"AC.01": {}, "AC.02": {}, "PC.01": {}, "PAT.01": {}},
    ))
    content = b"DOCUMENTO_SINTETICO_CLASIFICADO"
    digest = hashlib.sha256(content).hexdigest()
    state = {"document_scope_confirmed": (("sample.pdf", digest),),
             "authenticated_actor": AuthenticatedActor("a", "Analista", "org", frozenset({"analyst"}), "subject"),
             "file_metadata": {"sample.pdf": {"organization_id": "org", "file_digest": digest}},
             "raw_file_bytes": {("sample.pdf", "org", digest): content},
             "document_pages": {"sample.pdf": [1]},
             "company_periodos_seleccionados": ("2024", "2023")}
    monkeypatch.setattr(app.st, "session_state", state)
    accounts = [
        CuentaRaw(0, None, "Caja", 100, seccion_contable="Activo corriente"),
        CuentaRaw(1, None, "Total activos corrientes", 100, es_total=True),
        CuentaRaw(2, None, "Total activos", 100, es_total=True),
        CuentaRaw(3, None, "Capital", 100, seccion_contable="Patrimonio"),
        CuentaRaw(4, None, "Total patrimonio", 100, es_total=True),
        CuentaRaw(5, None, "Total patrimonio y pasivos", 100, es_total=True),
    ]
    for account in accounts:
        account.montos_periodos = {"2024": 100, "2023": 100}
    initial = CertificacionExtraccion(estado="parcial", metodo="classified_totals")
    result = SimpleNamespace(cuentas=accounts, certificacion_extraccion=initial,
                             periodos_detectados=["2024", "2023"], monedas_detectadas=["CLP"])
    app._guardar_snapshot_clasificado("sample.pdf", result)
    df = pd.DataFrame([
        {"linea": a.linea, "nombre_original": a.nombre, "monto": 100,
         "origen_columna": "desconocido", "es_total": False,
         "monto_periodo_2024": 100, "monto_periodo_2023": 100,
         "codigo_clasificado": code, "requiere_revision": False}
        for a, code in [(accounts[0], "AC.01"), (accounts[3], "PAT.01")]
    ])
    return state, df, initial


def test_complete_source_controls_can_certify_ui(monkeypatch):
    _, df, initial = setup(monkeypatch)
    final = app._recertificar_balance_clasificado("sample.pdf", df, initial)
    assert final.estado == "certificada"
    assert app._certificacion_coincide_contenido(final, df)


def test_code_change_invalidates_final_binding_and_rechecks(monkeypatch):
    _, df, initial = setup(monkeypatch)
    final = app._recertificar_balance_clasificado("sample.pdf", df, initial)
    df.loc[0, "codigo_clasificado"] = "PC.01"
    assert not app._certificacion_coincide_contenido(final, df)
    assert app._recertificar_balance_clasificado("sample.pdf", df, final) is final
    retry = app._recertificar_balance_clasificado("sample.pdf", df, final, force=True)
    assert retry.estado == "parcial"


def test_pages_or_document_change_rejects_snapshot(monkeypatch):
    state, df, initial = setup(monkeypatch)
    state["document_pages"]["sample.pdf"] = [2]
    assert app._recertificar_balance_clasificado("sample.pdf", df, initial).estado == "parcial"


def test_filtered_detail_cannot_certify(monkeypatch):
    _, df, initial = setup(monkeypatch)
    assert app._recertificar_balance_clasificado("sample.pdf", df.iloc[:1], initial).estado == "parcial"


def test_excluded_detail_and_changed_period_cannot_certify(monkeypatch):
    _, df, initial = setup(monkeypatch)
    df.loc[0, "codigo_clasificado"] = "__EXCLUIR__"
    assert app._recertificar_balance_clasificado("sample.pdf", df, initial).estado == "parcial"
    df.loc[0, "codigo_clasificado"] = "AC.01"
    df.loc[0, "monto_periodo_2023"] = 99
    assert app._recertificar_balance_clasificado("sample.pdf", df, initial).estado == "fallida"


def test_no_snapshot_and_duplicate_identity_fail_closed(monkeypatch):
    state, df, initial = setup(monkeypatch)
    assert app._recertificar_balance_clasificado("sample.pdf", pd.concat([df, df]), initial).estado == "parcial"
    state["classified_source_snapshots"] = {}
    assert app._recertificar_balance_clasificado("sample.pdf", df, initial).estado == "parcial"


def test_eight_column_certificate_is_untouched(monkeypatch):
    _, df, _ = setup(monkeypatch)
    initial = CertificacionExtraccion(estado="certificada", metodo="excel_8_columns")
    app._vincular_certificacion_contenido(initial, df)
    df.loc[0, "codigo_clasificado"] = "AC.02"
    assert app._certificacion_coincide_contenido(initial, df)
    assert app._recertificar_balance_clasificado("sample.pdf", df, initial) is initial
