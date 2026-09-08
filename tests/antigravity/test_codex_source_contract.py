import hashlib
from types import SimpleNamespace

import pytest
import pandas as pd
from parser_universal import CertificacionExtraccion
import app_validacion as app
from persistence.contracts import AuthenticatedActor


@pytest.fixture
def source(monkeypatch):
    actor = AuthenticatedActor('a', 'Analista', 'org', frozenset({'analyst'}), 'subject')
    data = b'actual source'
    digest = hashlib.sha256(data).hexdigest()
    state = {'file_metadata': {'x.pdf': {'organization_id': 'org', 'file_digest': digest}},
             'uploaded_files': [SimpleNamespace(name='x.pdf', getvalue=lambda: data)]}
    monkeypatch.setattr(app, '_safe_session_get', lambda key: state.get(key))
    monkeypatch.setattr(app, '_authenticated_actor', lambda: actor)
    return state, actor, digest


def test_valid_registered_upload(source):
    _, _, digest = source
    assert app._obtener_huella_archivo_real('x.pdf') == (digest, 'disponible')


def test_single_upload_wrong_expected_version(source):
    assert app._obtener_huella_archivo_real('x.pdf', expected_digest='0' * 64)[1] != 'disponible'


def test_upload_requires_actor(source, monkeypatch):
    monkeypatch.setattr(app, '_authenticated_actor', lambda: None)
    assert app._obtener_huella_archivo_real('x.pdf')[1] != 'disponible'


@pytest.mark.parametrize('org', [None, '', 'foreign'])
def test_upload_requires_matching_document_organization(source, org):
    state, _, _ = source
    state['file_metadata']['x.pdf']['organization_id'] = org
    assert app._obtener_huella_archivo_real('x.pdf')[1] != 'disponible'


def test_raw_bytes_do_not_fallback_to_foreign_organization(source):
    state, _, digest = source
    state['uploaded_files'] = []
    state['raw_file_bytes'] = {('x.pdf', 'foreign', digest): b'actual source'}
    assert app._obtener_huella_archivo_real('x.pdf', organization_id='org', expected_digest=digest)[1] != 'disponible'


def test_absolute_metadata_key_is_not_source_registration(source, tmp_path):
    state, _, digest = source
    p = tmp_path / 'x.pdf'
    p.write_bytes(b'actual source')
    state['uploaded_files'] = []
    state['file_metadata'][str(p)] = {'organization_id': 'org', 'file_digest': digest}
    assert app._obtener_huella_archivo_real(str(p))[1] != 'disponible'


def test_explicit_source_registration(source, tmp_path):
    state, _, digest = source
    p = tmp_path / 'x.pdf'
    p.write_bytes(b'actual source')
    state['uploaded_files'] = []
    state['file_metadata']['x.pdf']['source_path'] = str(p)
    assert app._obtener_huella_archivo_real('x.pdf') == (digest, 'disponible')


def test_missing_source_cannot_validate_manual_evidence(source, monkeypatch):
    state, actor, digest = source
    state['uploaded_files'] = []
    monkeypatch.setattr(app.st, 'session_state', state)
    amounts = {col: 0.0 for col in app.RAW_MONETARY_COLUMNS}
    row = dict(amounts, respaldo_documental={
        'archivo': 'x.pdf', 'file_digest': digest, 'pagina': 1,
        'actor': actor.actor_id, 'confirmacion_explicita': True,
        'importes': amounts,
    })
    assert app._validar_respaldo_incorporacion(row, 'x.pdf', digest)[0] is False


def test_source_removed_before_content_check_blocks_certificate(source, monkeypatch):
    state, actor, digest = source
    monkeypatch.setattr(app.st, 'session_state', state)
    df = pd.DataFrame([{'nombre_original': 'Caja', 'monto': 100}])
    cert = CertificacionExtraccion(estado='certificada', metodo='excel_8_columns',
                                  columnas_finales_validadas=True)
    app._vincular_certificacion_contenido(cert, df, filename='x.pdf', file_digest=digest)
    assert app._certificacion_coincide_contenido(cert, df)
    state['uploaded_files'] = []
    assert not app._certificacion_coincide_contenido(cert, df)


def test_manual_evidence_without_recorded_version_is_not_accepted(source, monkeypatch):
    state, actor, digest = source
    monkeypatch.setattr(app.st, 'session_state', state)
    amounts = {col: 0.0 for col in app.RAW_MONETARY_COLUMNS}
    row = dict(amounts, respaldo_documental={
        'archivo': 'x.pdf', 'pagina': 1, 'actor': actor.actor_id,
        'confirmacion_explicita': True, 'importes': amounts,
    })
    assert not app._validar_respaldo_incorporacion(row, 'x.pdf', digest)[0]
