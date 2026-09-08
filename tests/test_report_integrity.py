from io import BytesIO
import json
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest
import streamlit as st
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from app_validacion import (_codigo_compatible_con_origen, _control_emision,
                            _aplicar_promocion_durable,
                            _km_usuario, _normalize_required_role,
                            PromotionStateInconsistent,
                            _registrar_decision,
                            _registrar_evento_auditoria,
                            _require_app_role,
                            _resumen_bloqueadores_emision,
                            _vincular_certificacion_contenido)
from persistence.contracts.identity import (
    AuthenticatedActor, AuthenticationRequired, AuthorizationDenied,
)
from pipeline.homologation_pipeline import HomologationPipeline
from gold_standard.runtime_manager import RuntimeManager
from reporting_integrity import catalogo_local, conciliar_resultados


def cuenta(nombre, monto, origen, codigo):
    return dict(nombre_original=nombre, codigo_original=nombre, monto=monto,
                origen_columna=origen, origen_columna_efectiva=origen,
                codigo_clasificado=codigo, es_total=False,
                requiere_revision=False, metodo='validacion_humana', confianza=1.0,
                nombre_revision_usuario='')


def certificacion(estado='certificada', razones=None, finales=True):
    return SimpleNamespace(
        estado=estado,
        razones=list(razones or []),
        columnas_finales_validadas=finales,
        totales_calculados={}, totales_impresos={}, diferencias={},
        observaciones_auxiliares=[],
    )


def _actor(*roles):
    return AuthenticatedActor(
        actor_id='actor-1', display_name='Analista Uno', organization_id='org-1',
        roles=frozenset(roles), provider_subject='subject-1',
    )


class _PromotionRepository:
    def __init__(self, events, *, durable=True, outcome_durable=True):
        self.events = events
        self.record = None
        self.outcome = None
        self.durable = durable
        self.outcome_durable = outcome_durable

    def save_promotion_policy_metadata(self, record):
        self.events.append("persist")
        self.record = record
        return record

    def get_promotion_policy_metadata(self, evaluation_id, *, organization_id):
        self.events.append("verify")
        if not self.durable:
            return None
        assert self.record.evaluation_id == evaluation_id
        assert self.record.organization_id == organization_id
        return self.record

    def save_promotion_outcome(self, record):
        self.events.append(f"persist-outcome:{record.status}")
        if not self.outcome_durable:
            raise RuntimeError("outcome store unavailable")
        self.outcome = record
        return record

    def get_promotion_outcome(self, evaluation_id, *, organization_id):
        self.events.append("verify-outcome")
        if not self.outcome_durable:
            return None
        return self.outcome

    def list_promotion_outcomes_for_evaluation(
            self, evaluation_id, *, organization_id):
        return [self.outcome] if self.outcome else []

    def list_promotion_outcomes_for_subject(
            self, subject_id, *, organization_id, limit=100):
        return [self.outcome] if self.outcome and self.outcome.subject_id == subject_id else []

    def list_unresolved_promotion_evaluations(
            self, subject_id, *, organization_id, limit=100):
        self.events.append("unresolved")
        if (self.record is not None and self.record.allowed
                and self.record.subject_id == subject_id
                and (self.outcome is None or self.outcome.status == "INCONSISTENT")):
            return [self.record]
        return []


def _promotion_preview(conflicts=0):
    return SimpleNamespace(
        conflicts=conflicts,
        to_dict=lambda: {
            "candidates": 2, "promotable": 2 - conflicts,
            "conflicts": conflicts, "conflict_details": [],
        },
    )


def _promotion_source(tmp_path):
    source = tmp_path / "gold.db"
    source.write_bytes(b"gold-source")
    return source


def test_promocion_persiste_y_verifica_metadata_antes_de_aplicar(tmp_path):
    events = []
    repository = _PromotionRepository(events)
    record, result = _aplicar_promocion_durable(
        preview=_promotion_preview(), actor=_actor('supervisor'),
        evidence_confirmed=True, approved=True, expiration_days=90,
        repository=repository,
        apply_callback=lambda record: events.append("apply") or "aplicada",
        promotion_ids_resolver=lambda _result, _record: ("promotion-1",),
        source_path=_promotion_source(tmp_path),
    )
    assert result == "aplicada"
    assert events == [
        "unresolved", "persist", "verify", "apply",
        "persist-outcome:APPLIED", "verify-outcome",
    ]
    assert repository.outcome.evaluation_id == record.evaluation_id
    assert repository.outcome.status == "APPLIED"
    assert repository.outcome.promotion_ids == ("promotion-1",)
    assert record.allowed is True
    assert record.subject_id.startswith("gold-runtime-batch:")
    assert set(record.evidence) == {
        "source_document", "human_decision", "classification_reason",
    }
    assert record.supervisor_actor_id == "actor-1"
    assert record.organization_id == "org-1"
    assert record.reversal_reference == f"promotion-policy:{record.evaluation_id}"


def test_promocion_denegada_se_persiste_y_no_se_aplica(tmp_path):
    events = []
    record, result = _aplicar_promocion_durable(
        preview=_promotion_preview(), actor=_actor('supervisor'),
        evidence_confirmed=False, approved=True, expiration_days=90,
        repository=_PromotionRepository(events),
        apply_callback=lambda record: events.append("apply"),
        source_path=_promotion_source(tmp_path),
    )
    assert record.allowed is False
    assert result is None
    assert events == ["unresolved", "persist", "verify"]
    assert any("evidencia" in reason.lower() for reason in record.decision_reasons)


def test_fallo_de_metadata_durable_bloquea_promocion(tmp_path):
    events = []
    with pytest.raises(RuntimeError, match="persistencia durable"):
        _aplicar_promocion_durable(
            preview=_promotion_preview(), actor=_actor('supervisor'),
            evidence_confirmed=True, approved=True, expiration_days=90,
            repository=_PromotionRepository(events, durable=False),
            apply_callback=lambda record: events.append("apply"),
            source_path=_promotion_source(tmp_path),
        )
    assert events == ["unresolved", "persist", "verify"]


def test_staging_sin_actor_no_puede_aplicar_promocion_con_texto_libre(tmp_path):
    events = []
    with pytest.raises(AuthenticationRequired):
        _aplicar_promocion_durable(
            preview=_promotion_preview(), actor=None,
            evidence_confirmed=True, approved=True, expiration_days=90,
            repository=_PromotionRepository(events),
            apply_callback=lambda record: events.append("apply"),
            source_path=_promotion_source(tmp_path),
        )
    assert events == []


def test_referencia_de_politica_identifica_promocion_y_rollback(tmp_path):
    source = tmp_path / "gold.db"
    with sqlite3.connect(source) as connection:
        connection.execute(
            "CREATE TABLE gold_records (id INTEGER PRIMARY KEY, account_name TEXT, "
            "final_code TEXT, reviewer TEXT, review_date TEXT)"
        )
        connection.execute(
            "INSERT INTO gold_records VALUES (1, 'Cuenta revisada', 'AC.01', "
            "'actor-1', '2026-08-30')"
        )
    manager = RuntimeManager(tmp_path / "runtime.db")
    preview = manager.promote(source, dry_run=True)
    record, result = _aplicar_promocion_durable(
        preview=preview, actor=_actor('supervisor'),
        evidence_confirmed=True, approved=True, expiration_days=90,
        repository=_PromotionRepository([]),
        apply_callback=lambda durable_record: manager.promote(
            source, dry_run=False, usuario='actor-1',
            origen=durable_record.reversal_reference,
        ),
        promotion_ids_resolver=lambda _result, durable_record: tuple(
            event["promotion_id"] for event in manager.get_history()
            if event["accion"] == "PROMOTE"
            and event["origen"] == durable_record.reversal_reference
        ),
        source_path=source,
    )
    assert result.promoted == 1
    promoted_event = manager.get_history()[0]
    assert promoted_event["origen"] == record.reversal_reference
    assert promoted_event["promotion_id"]
    entry = manager.load_runtime()[0]
    assert manager.rollback(entry["id"], usuario='actor-1') is True
    rollback_event = manager.get_history()[0]
    assert rollback_event["accion"] == "ROLLBACK"
    assert rollback_event["promotion_id"] == promoted_event["promotion_id"]


def test_fallo_de_apply_persiste_failed_y_relanzar_error(tmp_path):
    events = []
    repository = _PromotionRepository(events)

    def fail_apply(_record):
        events.append("apply")
        raise ValueError("falló runtime")

    with pytest.raises(ValueError, match="falló runtime"):
        _aplicar_promocion_durable(
            preview=_promotion_preview(), actor=_actor('supervisor'),
            evidence_confirmed=True, approved=True, expiration_days=90,
            repository=repository, apply_callback=fail_apply,
            source_path=_promotion_source(tmp_path),
        )
    assert repository.outcome.status == "FAILED"
    assert repository.outcome.promotion_ids == ()
    assert "ValueError: falló runtime" in repository.outcome.error
    assert events[-2:] == ["persist-outcome:FAILED", "verify-outcome"]


def test_fallo_de_outcome_deja_subject_bloqueado_hasta_reconciliacion(tmp_path):
    events = []
    repository = _PromotionRepository(events, outcome_durable=False)
    source = _promotion_source(tmp_path)
    with pytest.raises(PromotionStateInconsistent, match="outcome APPLIED"):
        _aplicar_promocion_durable(
            preview=_promotion_preview(), actor=_actor('supervisor'),
            evidence_confirmed=True, approved=True, expiration_days=90,
            repository=repository,
            apply_callback=lambda _record: "aplicada",
            promotion_ids_resolver=lambda _result, _record: ("promotion-1",),
            source_path=source,
        )

    with pytest.raises(PromotionStateInconsistent, match="sin outcome terminal"):
        _aplicar_promocion_durable(
            preview=_promotion_preview(), actor=_actor('supervisor'),
            evidence_confirmed=True, approved=True, expiration_days=90,
            repository=repository,
            apply_callback=lambda _record: pytest.fail("no debe reaplicar"),
            source_path=source,
        )


def test_modo_local_usa_repositorio_y_no_escribe_json_empaquetados(
        tmp_path, monkeypatch):
    import app_validacion as app

    root = tmp_path / "onprem"
    packaged_catalog = app.BASE_DIR / "catalogo_maestro.json"
    packaged_dictionary = app.BASE_DIR / "diccionario.json"
    before_catalog = packaged_catalog.read_bytes()
    before_dictionary = packaged_dictionary.read_bytes()
    monkeypatch.setenv("PERSISTENCE_MODE", "local")
    monkeypatch.setenv("LOCAL_PERSISTENCE_ROOT", str(root))
    monkeypatch.setenv("LOCAL_CATALOG_SEED", str(packaged_catalog))
    monkeypatch.setenv("LOCAL_DICTIONARY_SEED", str(packaged_dictionary))
    monkeypatch.delenv("AUTH_ENFORCEMENT", raising=False)
    monkeypatch.setattr(
        app, "NeonKnowledgeStore",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Neon no debe instanciarse en modo local")
        ),
    )
    app.cargar_catalogo.clear()
    app.cargar_diccionario_base.clear()
    app._neon_disponible.clear()

    assert app._legacy_json_fallback_allowed() is False
    packaged_runtime = app.BASE_DIR / "gold_standard_runtime.db"
    packaged_runtime_before = (
        packaged_runtime.read_bytes() if packaged_runtime.exists() else None
    )
    runtime_path = app._gold_runtime_path()
    assert runtime_path == root.resolve() / "gold" / "gold_standard_runtime.db"
    assert app.BASE_DIR.resolve() not in runtime_path.parents
    RuntimeManager(runtime_path).initialize()
    assert runtime_path.is_file()
    assert (
        packaged_runtime.read_bytes() if packaged_runtime.exists() else None
    ) == packaged_runtime_before
    assert app._neon_disponible() is False
    with pytest.raises(RuntimeError, match="Neon está deshabilitado"):
        app._legacy_neon_store()
    with pytest.raises(RuntimeError, match="JSON empaquetado"):
        app._write_legacy_packaged_dictionary([])
    with pytest.raises(RuntimeError, match="JSON empaquetado"):
        app._write_legacy_packaged_catalog({})
    assert app.cargar_catalogo()
    assert app.cargar_diccionario_base()
    assert app._persistir_validacion(
        nombre="Cuenta local trazable", codigo="AC.01",
        fuente="validacion_humana", agregar_diccionario=True,
        archivo="balance-local.pdf",
    ) is True
    assert app._persistir_validacion(
        nombre="Decisión sólo del caso", codigo="ER.01",
        fuente="validacion_humana", agregar_diccionario=False,
        archivo="balance-local.pdf",
    ) is True
    new_category = {
        "codigo_estandar": "ER.99.99",
        "nombre_estandar": "Categoría local de prueba",
        "categoria": "resultado",
        "tipo_estado": "resultados",
        "naturaleza": "deudora",
    }
    assert app._persistir_catalogo(new_category) is True

    assert packaged_catalog.read_bytes() == before_catalog
    assert packaged_dictionary.read_bytes() == before_dictionary
    local_dictionary = json.loads(
        (root / "knowledge" / "diccionario.json").read_text(encoding="utf-8")
    )
    assert any(
        row["cuenta_original"] == "Cuenta local trazable"
        for row in local_dictionary
    )
    assert not any(
        row["cuenta_original"] == "Decisión sólo del caso"
        for row in local_dictionary
    )
    history = (root / "knowledge" / "history" / "validations.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"reviewer": "anonymous_staging"' in history
    assert '"account_name": "Decisión sólo del caso"' in history
    assert '"add_to_dictionary": false' in history
    local_catalog = json.loads(
        (root / "knowledge" / "catalogo_maestro.json").read_text(encoding="utf-8")
    )
    assert "ER.99.99" in local_catalog
    app.cargar_catalogo.clear()
    app.cargar_diccionario_base.clear()
    app._neon_disponible.clear()


def test_modo_autenticado_exige_actor_al_persistir_validacion(monkeypatch):
    import app_validacion as app

    monkeypatch.setenv("AUTH_ENFORCEMENT", "forward_auth")
    st.session_state.pop("authenticated_actor", None)
    with pytest.raises(AuthenticationRequired):
        app._persistir_validacion(
            nombre="Cuenta", codigo="AC.01", fuente="validacion_humana",
            agregar_diccionario=True,
        )


def test_validacion_persistida_usa_actor_autenticado_como_reviewer(monkeypatch):
    import app_validacion as app

    captured = []
    repository = SimpleNamespace(
        save_validation=lambda decision: captured.append(decision),
    )
    monkeypatch.setenv("AUTH_ENFORCEMENT", "forward_auth")
    st.session_state["authenticated_actor"] = _actor('analyst')
    monkeypatch.setattr(app, "_knowledge_repository", lambda: repository)
    assert app._persistir_validacion(
        nombre="Cuenta", codigo="AC.01", fuente="validacion_humana",
        agregar_diccionario=True, archivo="balance.pdf",
    ) is True
    assert captured[0].reviewer == "actor-1"
    assert captured[0].source_file == "balance.pdf"
    st.session_state.pop("authenticated_actor", None)


def test_staging_audita_sin_inventar_identidad(monkeypatch):
    monkeypatch.delenv('AUTH_ENFORCEMENT', raising=False)
    st.session_state.pop('authenticated_actor', None)
    evento = _registrar_evento_auditoria('Prueba', 'x.pdf', 'staging')
    assert evento['Actor'] == ''
    assert evento['Organización'] == ''
    assert evento['Roles'] == []
    assert _km_usuario() == ''
    assert _require_app_role('supervisor') is None


def test_modo_autenticado_deniega_sin_actor(monkeypatch):
    monkeypatch.setenv('AUTH_ENFORCEMENT', 'forward_auth')
    st.session_state.pop('authenticated_actor', None)
    with pytest.raises(AuthenticationRequired):
        _require_app_role('analyst')
    with pytest.raises(AuthenticationRequired):
        _registrar_evento_auditoria('Prueba', 'x.pdf', 'sin actor')


def test_actor_autenticado_propaga_auditoria_y_roles(monkeypatch):
    monkeypatch.setenv('AUTH_ENFORCEMENT', 'forward_auth')
    actor = _actor('supervisor')
    st.session_state['authenticated_actor'] = actor
    assert _require_app_role('analyst') is actor
    assert _require_app_role('supervisor') is actor
    with pytest.raises(AuthorizationDenied):
        _require_app_role('admin')
    evento = _registrar_evento_auditoria('Prueba', 'x.pdf', 'autenticada')
    assert evento['Actor'] == 'actor-1'
    assert evento['Organización'] == 'org-1'
    assert evento['Roles'] == ['supervisor']
    assert _km_usuario() == 'actor-1'
    st.session_state['historial_decisiones'] = []
    _registrar_decision(
        'x.pdf', 1, {"codigo_clasificado": "AC.08", "metodo": "origin_fallback"},
        'AC.01', 'corrección',
    )
    decision = st.session_state['historial_decisiones'][-1]
    assert decision['Actor'] == 'actor-1'
    assert decision['Organización'] == 'org-1'
    st.session_state.pop('authenticated_actor', None)


def test_administrator_es_alias_transitorio_de_admin(monkeypatch):
    monkeypatch.setenv('AUTH_ENFORCEMENT', 'forward_auth')
    actor = _actor('admin')
    st.session_state['authenticated_actor'] = actor
    assert _normalize_required_role('administrator') == 'admin'
    assert _require_app_role('administrator') is actor
    st.session_state.pop('authenticated_actor', None)


def control_emision(df, diagnostico=None, quality_control=None,
                    extraction_certification=None):
    certificate = extraction_certification if extraction_certification is not None else certificacion()
    if extraction_certification is None:
        _vincular_certificacion_contenido(certificate, df)
    return _control_emision(
        df, catalogo_local(), diagnostico or {'cuadra': True},
        quality_control=quality_control,
        extraction_certification=certificate,
    )


def afuminsal(mal=True):
    # Importes del reporte AFUMINSAL: la cuota social se había incluido en ER.04.
    return [
        cuenta('Activos', 29943255, 'activo', 'AC.01'),
        cuenta('Facturas por pagar', 3177262, 'pasivo', 'PC.01'),
        cuenta('Capital social', 15201792, 'pasivo', 'PAT.01'),
        cuenta('Resultados acumulados', 1653256, 'pasivo', 'PAT.03'),
        cuenta('Gastos administración', 16376428, 'perdida', 'ER.04'),
        cuenta('Gastos financieros', 19306, 'perdida', 'ER.09'),
        cuenta('Ingreso Cuotas Sociales', 21623055, 'ganancia', 'ER.04' if mal else 'ER.17'),
        cuenta('Ingresos financieros', 4089280, 'ganancia', 'ER.12'),
        cuenta('Otros ingresos', 594344, 'ganancia', 'ER.17'),
    ]


@pytest.mark.parametrize('codigo,columna,monto,permitido', [
    ('ER.04', 'ganancia', 100, False), ('ER.04', 'perdida', 100, True),
    ('ER.01', 'perdida', 100, False), ('ER.01', 'ganancia', 100, True),
    ('ER.04', 'ganancia', -100, True), ('ER.01', 'perdida', -100, True),
    ('ER.18', 'ganancia', 100, False), ('ER.18', 'perdida', 100, True),
    ('ER.14', 'perdida', 100, True), ('ER.14', 'ganancia', 100, True),
])
def test_naturaleza_individual_y_compartida(codigo, columna, monto, permitido):
    assert _codigo_compatible_con_origen(codigo, columna, monto) is permitido
    if monto > 0:
        assert HomologationPipeline._is_code_allowed_for_tipo(codigo, columna.upper()) is permitido


def test_afuminsal_no_confunde_cuadratura_con_resultado_correcto():
    rows = afuminsal()
    original = pd.DataFrame(rows)
    control = control_emision(original)
    assert not control['definitivo']
    assert control['resultado']['resultado_origen'] == 9910945
    assert control['resultado']['resultado_homologado'] == -33335165
    assert control['resultado']['diferencia'] == -43246110
    assert control['incidencias']['Cuenta'].tolist() == ['Ingreso Cuotas Sociales']
    pd.testing.assert_frame_equal(original, pd.DataFrame(rows))
    corrected = control_emision(pd.DataFrame(afuminsal(False)))
    assert corrected['definitivo']
    assert corrected['resultado']['diferencia'] == 0


def test_errores_compensados_siguen_bloqueados():
    df = pd.DataFrame([cuenta('Ingreso', 100, 'ganancia', 'ER.04'),
                       cuenta('Gasto', 100, 'perdida', 'ER.01')])
    control = control_emision(df)
    assert control['resultado']['diferencia'] == 0
    assert len(control['incidencias']) == 2
    assert not control['definitivo']


@pytest.mark.parametrize('cambio', [dict(requiere_revision=True),
    dict(codigo_clasificado=''), dict(codigo_clasificado='__EXCLUIR__'),
    dict(codigo_clasificado='ER.999'), dict(monto=float('nan'))])
def test_pendiente_o_excluida_no_se_certifica(cambio):
    rows = afuminsal(False)
    rows[-1].update(cambio)
    assert not control_emision(pd.DataFrame(rows))['definitivo']


def test_revision_pendiente_sin_saldo_tambien_bloquea_emision():
    rows = afuminsal(False)
    rows.append({
        **cuenta('Cuenta pendiente sin saldo', 0, 'activo', 'AC.08'),
        'requiere_revision': True,
    })

    control = control_emision(pd.DataFrame(rows))

    assert not control['definitivo']
    assert control['incidencias'].iloc[0]['Cuenta'] == 'Cuenta pendiente sin saldo'
    assert 'Decisión pendiente' in control['incidencias'].iloc[0]['Qué corregir']


def test_controles_impresos_no_suman_y_resultado_declarado_se_contrasta():
    rows = afuminsal(False)
    rows += [{**cuenta('SUMAS', 999999, 'ganancia', ''), 'es_total': True}]
    assert conciliar_resultados(rows, catalogo_local())['cuadra']
    rows += [cuenta('Utilidad del ejercicio', 123, 'pasivo', 'PAT.04')]
    result = conciliar_resultados(rows, catalogo_local())
    assert not result['cuadra']
    assert any('PAT.04' in msg for msg in result['problemas'])


def test_enforced_no_certifica_y_shadow_no_bloquea_por_si_solo():
    df = pd.DataFrame(afuminsal(False))
    assert not control_emision(df,
        quality_control=SimpleNamespace(export_allowed=False, reasons=['Cobertura insuficiente']))['definitivo']
    assert control_emision(df,
        quality_control=SimpleNamespace(export_allowed=True, reasons=['Shadow']))['definitivo']
    assert not control_emision(df,
        quality_control=SimpleNamespace(export_allowed=False, reasons=[]))['definitivo']
    assert not control_emision(df, quality_control=SimpleNamespace(
        export_allowed=True, reasons=['1 hallazgo crítico de cobertura']))['definitivo']


def test_edicion_compensada_invalida_certificacion_hasta_recertificar():
    original = pd.DataFrame(afuminsal(False))
    certificate = _vincular_certificacion_contenido(certificacion(), original)
    assert control_emision(original, extraction_certification=certificate)['definitivo']
    edited = original.copy()
    edited.loc[edited['nombre_original'] == 'Activos', 'monto'] += 1_000
    edited.loc[edited['nombre_original'] == 'Capital social', 'monto'] += 1_000
    assert not control_emision(edited, extraction_certification=certificate)['definitivo']
    _vincular_certificacion_contenido(certificate, edited)
    assert control_emision(edited, extraction_certification=certificate)['definitivo']


def test_vinculo_certificacion_sobrevive_serializacion_del_dataframe():
    import pickle
    original = pd.DataFrame(afuminsal(False))
    _vincular_certificacion_contenido(certificacion(), original)
    _registrar_evento_auditoria(
        'Invalidación de certificación', 'caso.pdf',
        'Edición manual de monto u origen', df=original,
    )
    restored = pickle.loads(pickle.dumps(original))
    assert restored.attrs['audit_events'][0]['Actor'] == ''
    restored_certificate = certificacion()
    assert control_emision(
        restored, extraction_certification=restored_certificate,
    )['definitivo']
    legacy = restored.copy()
    legacy.attrs.clear()
    assert not control_emision(
        legacy, extraction_certification=certificacion(),
    )['definitivo']


def test_resumen_previo_diferencia_recertificacion_y_clasificacion():
    resumen = _resumen_bloqueadores_emision([
        'La certificación documental no corresponde al contenido actual',
        '1 cuenta requiere corregir su clasificación',
    ])
    assert resumen['Tipo'].tolist() == [
        'Recertificar extracción', 'Corregir clasificación o control',
    ]


@pytest.mark.parametrize('estado', ['fallida', 'parcial', 'no_evaluable'])
def test_certificacion_no_aprobada_bloquea_entregable_definitivo(estado):
    control = control_emision(
        pd.DataFrame(afuminsal(False)),
        extraction_certification=certificacion(
            estado, ['Hallazgo documental pendiente'], finales=(estado == 'fallida'),
        ),
    )

    assert not control['definitivo']
    assert any('no está certificada' in reason for reason in control['motivos'])
    assert 'Hallazgo documental pendiente' in control['motivos']


def test_certificacion_ausente_bloquea_entregable_definitivo():
    control = _control_emision(
        pd.DataFrame(afuminsal(False)), catalogo_local(), {'cuadra': True},
        extraction_certification=None,
    )

    assert not control['definitivo']
    assert 'No existe una certificación documental válida para emitir' in control['motivos']


@pytest.mark.parametrize('origen,monto', [('ganancia', 50), ('perdida', 50),
                                         ('ganancia', -50), ('perdida', -50)])
def test_resultado_mixto_conserva_signo_contable(origen, monto):
    result = conciliar_resultados([cuenta('Diferencia de cambio', monto, origen, 'ER.13')], catalogo_local())
    assert result['cuadra']
    assert result['resultado_homologado'] == (monto if origen == 'ganancia' else -monto)


def test_resultado_calculado_no_oculta_error_aunque_ambos_controles_coincidan():
    rows = afuminsal()
    rows += [cuenta('Utilidad calculada', 9910945, 'pasivo', 'PAT.04'),
             cuenta('Utilidad neta', 9910945, 'desconocido', 'ER.11')]
    result = conciliar_resultados(rows, catalogo_local())
    assert not result['cuadra']
    assert result['resultado_homologado'] == -33335165
    assert any('PAT.04' in p for p in result['problemas'])
    assert any('ER.11' in p for p in result['problemas'])


def test_atribuciones_controladora_y_no_controladores_no_duplican_resultado():
    rows = [
        cuenta('Ingresos', 110193, 'ganancia', 'ER.01'),
        cuenta('Costos y gastos', 113655, 'perdida', 'ER.02'),
        cuenta('Atribuible a propietarios de la controladora', 3488,
               'perdida', 'ER.20'),
        cuenta('Atribuible a participaciones no controladoras', 26,
               'ganancia', 'ER.21'),
    ]

    result = conciliar_resultados(rows, catalogo_local())

    assert result['cuadra']
    assert result['resultado_origen'] == -3462
    assert result['resultado_homologado'] == -3462


def review_app(rows):
    import streamlit as st
    import pandas as pd
    import app_validacion as app
    from reporting_integrity import catalogo_local
    st.session_state.setdefault('resultados', {'caso.pdf': pd.DataFrame(rows)})
    st.session_state.setdefault('diccionario', [])
    st.session_state.setdefault('correcciones', [])
    st.session_state.setdefault('persistidas', [])
    def persistir(**kwargs):
        st.session_state.persistidas.append(kwargs)
        return True
    def persistir_lote(items):
        st.session_state.persistidas.extend(items)
        return True
    prev, prev_lote = app._persistir_validacion, app._persistir_validaciones_lote
    app._persistir_validacion, app._persistir_validaciones_lote = persistir, persistir_lote
    try:
        app._tab_revision(st.session_state.resultados['caso.pdf'], catalogo_local(),
                          app.MotorHibridoLocal([]), 'caso.pdf')
    finally:
        app._persistir_validacion, app._persistir_validaciones_lote = prev, prev_lote


def all_view(rows):
    at = AppTest.from_function(review_app, args=(rows,)).run()
    assert not at.exception
    at.radio[0].set_value('Todas (incluye confirmadas y excluidas)').run()
    assert not at.exception
    return at


def test_ui_recupera_decision_manual_sin_pendientes():
    rows = [cuenta('Cuotas', 100, 'ganancia', 'ER.04'), cuenta('Cuotas', 100, 'ganancia', 'ER.12')]
    at = all_view(rows)
    selector = next(s for s in at.selectbox if s.label == 'Clasificación correcta')
    assert not any('ER.04' in option for option in selector.options)
    selector.set_value('ER.17').run()
    next(r for r in at.radio if r.label == '¿Aplicar esta clasificación?').set_value('Solo para este caso').run()
    next(b for b in at.button if b.label == '✅ Confirmar').click().run()
    assert not at.exception
    df = at.session_state.resultados['caso.pdf']
    assert df.at[0, 'codigo_clasificado'] == 'ER.17'
    assert df.at[1, 'codigo_clasificado'] == 'ER.12'
    assert at.session_state.historial_decisiones[0]['Clasificación anterior'] == 'ER.04'
    assert at.session_state.persistidas[0]['agregar_diccionario'] is False
    assert not at.session_state.diccionario


def test_ui_buscar_mas_no_permite_aprender_ingreso_como_gasto():
    at = all_view([cuenta('Cuotas', 100, 'ganancia', 'ER.17')])
    next(c for c in at.checkbox if 'Buscar más' in c.label).check().run()
    next(s for s in at.selectbox if s.label == 'Clasificación correcta').set_value('ER.04').run()
    next(b for b in at.button if b.label == '✅ Confirmar').click().run()
    assert not at.exception
    assert at.error
    assert at.session_state.resultados['caso.pdf'].at[0, 'codigo_clasificado'] == 'ER.17'
    assert not at.session_state.persistidas
    assert not at.session_state.diccionario


def test_ui_lote_incompatible_no_modifica_ninguna_cuenta():
    rows = [cuenta('Cuotas', 100, 'ganancia', 'ER.17'), cuenta('Gastos', 100, 'perdida', 'ER.04')]
    at = all_view(rows)
    next(b for b in at.button if 'Seleccionar todas' in b.label).click().run()
    next(s for s in at.selectbox if s.label.startswith('Clasificar todas')).set_value('ER.04').run()
    next(b for b in at.button if 'Confirmar lote' in b.label).click().run()
    assert not at.exception
    assert at.error
    pd.testing.assert_frame_equal(at.session_state.resultados['caso.pdf'], pd.DataFrame(rows))
    assert not at.session_state.persistidas


def test_ui_recupera_excluida():
    at = all_view([cuenta('Cuotas', 100, 'ganancia', '__EXCLUIR__')])
    next(s for s in at.selectbox if s.label == 'Clasificación correcta').set_value('ER.17').run()
    next(b for b in at.button if b.label == '✅ Confirmar').click().run()
    assert not at.exception
    assert at.session_state.resultados['caso.pdf'].at[0, 'codigo_clasificado'] == 'ER.17'


def test_ui_no_redefine_categoria_existente_para_evadir_control():
    at = all_view([cuenta('Cuotas', 100, 'ganancia', 'ER.17')])
    next(s for s in at.selectbox if s.label == 'Clasificación correcta').set_value('➕ NUEVA CATEGORÍA').run()
    next(t for t in at.text_input if t.label.startswith('Código (ej')).set_value('ER.04')
    next(t for t in at.text_input if t.label == 'Nombre de la categoría').set_value('Ingreso falso')
    next(s for s in at.selectbox if s.label == 'Categoría').set_value('resultado').run()
    next(b for b in at.button if b.label == '✅ Confirmar').click().run()
    assert not at.exception
    assert any('No se puede redefinir' in e.value for e in at.error)
    assert not at.session_state.persistidas


def test_ui_busqueda_vacia_no_oculta_acceso_a_confirmadas():
    at = AppTest.from_function(review_app, args=([cuenta('Cuotas', 100, 'ganancia', 'ER.17')],)).run()
    next(t for t in at.text_input if t.label == 'Buscar cuenta o código').set_value('Cuotas').run()
    assert not at.exception
    at.radio[0].set_value('Todas (incluye confirmadas y excluidas)').run()
    assert not at.exception
    assert any(s.label == 'Clasificación correcta' for s in at.selectbox)


def report_app(rows, depreciation="__resolved_without_adjustment__",
               certification_state="certificada", early_squared=None,
               actor=None):
    import streamlit as st
    import pandas as pd
    import app_validacion as app
    from types import SimpleNamespace
    from extractor_metadata import MetadataEmpresa
    from reporting_integrity import catalogo_local
    if actor is not None:
        st.session_state['authenticated_actor'] = actor
    st.session_state.setdefault('metadata_files', {'caso.pdf': MetadataEmpresa(moneda='$')})
    st.session_state.setdefault('company_periodos_seleccionados', ('2024',))
    data = pd.DataFrame(rows)
    certificate = SimpleNamespace(
        estado=certification_state,
        razones=(['Diferencia crítica de extracción']
                 if certification_state != 'certificada' else []),
        columnas_finales_validadas=certification_state == 'fallida',
        totales_calculados={}, totales_impresos={}, diferencias={},
        observaciones_auxiliares=[],
        totales_finales_validos=early_squared,
    )
    if certification_state == 'certificada':
        app._vincular_certificacion_contenido(certificate, data)
    st.session_state.setdefault('extraction_certifications', {
        'caso.pdf': certificate,
    })
    # Estas pruebas históricas certifican el informe una vez resuelto el nuevo
    # control de depreciación desde notas.
    if depreciation == "__resolved_without_adjustment__":
        depreciation = {'mode': 'none'}
    depreciation_state = (
        {'caso.pdf': {'2024': depreciation}} if depreciation is not None else {}
    )
    st.session_state.setdefault('depreciation_reclassifications', depreciation_state)
    previous = app.st.download_button
    def capture(label, **kwargs):
        st.session_state['export_label'] = label
        st.session_state['export_kwargs'] = kwargs
    app.st.download_button = capture
    try:
        app._tab_balance(data, catalogo_local(), 'caso.pdf')
    finally:
        app.st.download_button = previous


def test_reporte_integra_depreciacion_de_notas_y_deja_trazabilidad():
    at = AppTest.from_function(
        report_app,
        args=(afuminsal(False), {
            'mode': 'notes', 'total': 500,
            'cost_of_sales': 0, 'administration': 500,
            'source': 'manual_notes',
        }),
    ).run(timeout=20)
    assert not at.exception
    assert 'BORRADOR' not in at.session_state.export_kwargs['file_name']
    wb = load_workbook(BytesIO(at.session_state.export_kwargs['data']), data_only=True)
    balance_rows = list(wb['Balance Normalizado'].iter_rows(values_only=True))
    administracion = next(row for row in balance_rows if row[0] == 'ER.04')
    depreciacion = next(row for row in balance_rows if row[0] == 'ER.07')
    assert administracion[2] == -16_375_928
    assert depreciacion[2] == -500
    summary_rows = list(wb['Resumen'].iter_rows(min_row=27, values_only=True))
    adjustment = next(
        row for row in summary_rows
        if row[3] == 'Depreciación del ejercicio informada desde notas'
    )
    assert adjustment[0] == 'ER.07'
    assert adjustment[4] is None
    assert adjustment[5] == -500
    controls = {row[0]: row[1] for row in wb['Control de emisión'].iter_rows(
        min_row=2, values_only=True,
    ) if row[0]}
    assert controls['Depreciación informada desde notas (2024)'] == 500
    assert controls['Rebaja de Gastos de Administración (2024)'] == 500


def test_depreciacion_acumulada_no_sustituye_gasto_del_ejercicio():
    rows = afuminsal(False)
    rows[0]['monto'] += 500
    rows.append(cuenta(
        'Depreciación Acumulada', 500, 'pasivo', 'ANC.01.01',
    ))

    at = AppTest.from_function(
        report_app, args=(rows, None),
    ).run(timeout=20)

    assert not at.exception
    assert any(select.label == 'Tratamiento' for select in at.selectbox)
    assert any(
        'ANC.01.01' in caption.value and 'ER.07' in caption.value
        for caption in at.caption
    )
    assert at.session_state.export_kwargs['file_name'].startswith('BORRADOR-')


def test_depreciacion_acumulada_resta_activo_y_no_altera_resultado():
    rows = afuminsal(False)
    rows[0]['monto'] += 500
    rows.append(cuenta(
        'Depreciación Acumulada', 500, 'pasivo', 'ANC.01.01',
    ))

    at = AppTest.from_function(report_app, args=(rows,)).run(timeout=20)

    assert not at.exception
    workbook = load_workbook(
        BytesIO(at.session_state.export_kwargs['data']), data_only=True,
    )
    balance_rows = list(workbook['Balance Normalizado'].iter_rows(values_only=True))
    accumulated = next(row for row in balance_rows if row[0] == 'ANC.01.01')
    assert accumulated[2] == -500
    controls = {row[0]: row[1] for row in workbook['Control de emisión'].iter_rows(
        min_row=2, values_only=True,
    ) if row[0]}
    assert controls['Resultado según columnas originales'] == 9_910_945
    assert controls['Resultado según categorías homologadas'] == 9_910_945


def test_decision_sin_depreciacion_queda_trazada_en_reporte():
    at = AppTest.from_function(report_app, args=(afuminsal(False),)).run(timeout=20)
    assert not at.exception
    workbook = load_workbook(BytesIO(at.session_state.export_kwargs['data']), data_only=True)
    assert 'Decisiones depreciación' in workbook.sheetnames
    headers = [cell.value for cell in workbook['Decisiones depreciación'][1]]
    values = [cell.value for cell in workbook['Decisiones depreciación'][2]]
    row = dict(zip(headers, values))
    assert row['Decisión'] == 'No existe o no aplica depreciación por separar'
    assert row['Evidencia']
    assert row['Fecha/hora']
    assert row['Analista'] is None
    controls = {row[0]: row[1] for row in workbook['Control de emisión'].iter_rows(
        min_row=2, values_only=True) if row[0]}
    assert controls['Versión de contenido certificado'] == 'certifiable_rows.v1'
    assert len(controls['Digest de contenido certificado']) == 64
    assert 'Auditoría de emisión' in workbook.sheetnames


def test_render_produccion_exige_control_de_exportacion():
    from pathlib import Path
    render = Path(__file__).parents[1].joinpath('render.yaml').read_text(encoding='utf-8')
    assert 'QUALITY_CONTROL_ENFORCE_EXPORT' in render
    assert 'value: "true"' in render


def test_cuadre_temprano_aprobado_y_tardio_degradado_bloquea_reporte():
    rows = afuminsal(False)
    rows[0]['origen_columna'] = 'desconocido'
    rows[0]['origen_columna_efectiva'] = 'desconocido'
    rows[0]['codigo_clasificado'] = 'PC.08'
    at = AppTest.from_function(
        report_app, args=(rows, "__resolved_without_adjustment__", "certificada", True),
    ).run(timeout=20)
    assert not at.exception
    assert at.session_state.export_kwargs['file_name'].startswith('BORRADOR-')
    workbook = load_workbook(BytesIO(at.session_state.export_kwargs['data']), data_only=True)
    assert 'Cambios de cuadratura' in workbook.sheetnames
    controls = {row[0]: row[1] for row in workbook['Control de emisión'].iter_rows(
        min_row=2, values_only=True) if row[0]}
    assert controls['Degradación introducida por clasificación'] is True


def test_depreciacion_del_ejercicio_extraida_evita_solicitud_desde_notas():
    rows = afuminsal(False)
    admin = next(row for row in rows if row['nombre_original'] == 'Gastos administración')
    admin['monto'] -= 500
    rows.append(cuenta(
        'Depreciación del ejercicio', 500, 'perdida', 'ER.07',
    ))

    at = AppTest.from_function(
        report_app, args=(rows, None),
    ).run(timeout=20)

    assert not at.exception
    assert not any(select.label == 'Tratamiento' for select in at.selectbox)
    assert not at.session_state.export_kwargs['file_name'].startswith('BORRADOR-')
    workbook = load_workbook(
        BytesIO(at.session_state.export_kwargs['data']), data_only=True,
    )
    balance_rows = list(workbook['Balance Normalizado'].iter_rows(values_only=True))
    depreciation = next(row for row in balance_rows if row[0] == 'ER.07')
    assert depreciation[2] == -500


def test_reporte_distribuye_depreciacion_entre_costo_y_administracion_sin_cambiar_utilidad():
    rows = afuminsal(False)
    rows.append(cuenta('Costo de ventas', 1_000, 'perdida', 'ER.02'))
    otros_ingresos = next(
        row for row in rows if row['nombre_original'] == 'Otros ingresos'
    )
    otros_ingresos['monto'] += 1_000
    ajuste = {
        'mode': 'notes', 'total': 500,
        'cost_of_sales': 350, 'administration': 150,
        'source': 'manual_notes',
    }

    at = AppTest.from_function(report_app, args=(rows, ajuste)).run(timeout=20)

    assert not at.exception
    workbook = load_workbook(
        BytesIO(at.session_state.export_kwargs['data']), data_only=True,
    )
    balance_rows = list(workbook['Balance Normalizado'].iter_rows(values_only=True))
    values = {
        code: next(row[2] for row in balance_rows if row[0] == code)
        for code in ('ER.02', 'ER.04', 'ER.07')
    }
    assert values == {
        'ER.02': -650,
        'ER.04': -16_376_278,
        'ER.07': -500,
    }
    controls = {row[0]: row[1] for row in workbook['Control de emisión'].iter_rows(
        min_row=2, values_only=True,
    ) if row[0]}
    assert controls['Resultado según columnas originales'] == 9_910_945
    assert controls['Resultado según categorías homologadas'] == 9_910_945
    assert controls['Diferencia de resultado'] == 0
    assert controls['Depreciación informada desde notas (2024)'] == 500
    assert controls['Rebaja de Costo de Ventas (2024)'] == 350
    assert controls['Rebaja de Gastos de Administración (2024)'] == 150
    trace_names = {
        row[3] for row in workbook['Resumen'].iter_rows(
            min_row=27, values_only=True,
        ) if row[3]
    }
    assert {
        'Ajuste: depreciación separada desde Costo de Ventas',
        'Ajuste: depreciación separada desde Gastos de Administración',
        'Depreciación del ejercicio informada desde notas',
    }.issubset(trace_names)


def test_reporte_pide_depreciacion_y_muestra_montos_sin_envio_intermedio():
    at = AppTest.from_function(
        report_app, args=(afuminsal(False), None),
    ).run(timeout=20)
    assert not at.exception
    tratamiento = next(s for s in at.selectbox if s.label == 'Tratamiento')
    tratamiento.select('notes').run(timeout=20)
    assert not at.exception
    assert {n.label for n in at.number_input} >= {
        'Depreciación total del período',
        'Incluida en Costo de Ventas',
        'Incluida en Gastos de Administración',
    }
    assert 'BORRADOR' in at.session_state.export_kwargs['file_name']


def test_reporte_rechaza_distribucion_depreciacion_que_no_suma_el_total():
    at = AppTest.from_function(
        report_app, args=(afuminsal(False), None),
    ).run(timeout=20)
    next(select for select in at.selectbox if select.label == 'Tratamiento').select(
        'notes'
    ).run(timeout=20)
    inputs = {item.label: item for item in at.number_input}
    inputs['Depreciación total del período'].set_value(500)
    inputs['Incluida en Costo de Ventas'].set_value(350)
    inputs['Incluida en Gastos de Administración'].set_value(100)
    next(
        button for button in at.button if button.label == 'Guardar tratamiento'
    ).click().run(timeout=20)

    assert not at.exception
    assert any('igual a la suma' in error.value for error in at.error)
    assert '2024' not in at.session_state.depreciation_reclassifications['caso.pdf']
    assert at.session_state.export_kwargs['file_name'].startswith('BORRADOR-')


def test_reporte_con_certificacion_fallida_solo_descarga_borrador_no_certificado():
    at = AppTest.from_function(
        report_app,
        args=(afuminsal(False), "__resolved_without_adjustment__", "fallida"),
    ).run(timeout=20)

    assert not at.exception
    download = at.session_state.export_kwargs
    assert at.session_state.export_label == 'Descargar BORRADOR con diagnóstico (Excel)'
    assert download['file_name'].startswith('BORRADOR-')
    workbook = load_workbook(BytesIO(download['data']), data_only=True)
    assert workbook['Balance Normalizado']['F1'].value == 'BORRADOR: REQUIERE REVISIÓN'
    assert 'Control de extracción' in workbook.sheetnames
    controls = list(workbook['Control de emisión'].iter_rows(
        min_row=2, values_only=True,
    ))
    assert any(
        row[0] == 'Pendiente de resolver'
        and 'no está certificada' in str(row[1])
        for row in controls
    )
    assert any(
        row[0] == 'Pendiente de resolver'
        and row[1] == 'Diferencia crítica de extracción'
        for row in controls
    )


@pytest.mark.parametrize('hallazgo', ['sin_clasificar', 'revision_pendiente'])
def test_descarga_real_es_borrador_ante_cuenta_critica(hallazgo):
    rows = afuminsal(False)
    if hallazgo == 'sin_clasificar':
        rows[-1]['codigo_clasificado'] = ''
    else:
        rows[-1]['requiere_revision'] = True

    at = AppTest.from_function(report_app, args=(rows,)).run(timeout=20)

    assert not at.exception
    assert at.session_state.export_label == 'Descargar BORRADOR con diagnóstico (Excel)'
    assert at.session_state.export_kwargs['file_name'].startswith('BORRADOR-')
    workbook = load_workbook(
        BytesIO(at.session_state.export_kwargs['data']), data_only=True,
    )
    assert workbook['Balance Normalizado']['F1'].value == 'BORRADOR: REQUIERE REVISIÓN'
    assert 'Cuentas a corregir' in workbook.sheetnames


@pytest.mark.parametrize('mal', [True, False])
def test_reporte_real_ui_y_excel(mal, monkeypatch):
    monkeypatch.setenv('QUALITY_CONTROL_ENFORCE_EXPORT', 'false')
    at = AppTest.from_function(report_app, args=(afuminsal(mal),)).run(timeout=20)
    assert not at.exception
    download = at.session_state.export_kwargs
    assert ('BORRADOR' in download['file_name']) is mal
    wb = load_workbook(BytesIO(download['data']), data_only=True)
    assert ('BORRADOR' in wb['Balance Normalizado']['F1'].value) is mal
    assert wb['Balance Normalizado']['C7'].value == 'Monto Total ($)'
    assert 'Control de emisión' in wb.sheetnames
    rows = list(wb['Balance Normalizado'].iter_rows(min_row=8, max_row=7+len(catalogo_local()), values_only=True))
    gastos = next(row for row in rows if row[0] == 'ER.04')
    assert gastos[2] == (-37999483 if mal else -16376428)
    assert not any(m.label == 'Subtotal' and m.value == '52,613,358' for m in at.metric)
    next(b for b in at.button if b.label == 'Revisar o cambiar clasificaciones').click().run()
    assert not at.exception
    assert 'Cola de Revisión' in at.session_state.vista_trabajo_solicitada
