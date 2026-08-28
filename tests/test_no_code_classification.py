from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from parser_universal import (
    CuentaRaw, FormatoCodigo, OrigenColumna, ResultadoParseo,
)
from pipeline.homologation_pipeline import HomologationPipeline


def test_regex_contextual_clasifica_venta_sin_codigo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual('VENTA MOTOS', 'GANANCIA')

    assert result['standard_code'] == 'ER.01'
    assert result['method'] == 'regex_contextual'
    assert result['confidence'] < 0.85


def test_regex_contextual_clasifica_costo_sin_codigo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'COSTO REPUESTOS Y ACCESORIOS', 'PERDIDA'
    )

    assert result['standard_code'] == 'ER.02'


def test_regex_contextual_descarta_categoria_incompatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    assert pipeline._classify_by_regex_contextual('VENTA MOTOS', 'ACTIVO') is None


def test_fallback_de_origen_clasifica_y_exige_revision():
    result = HomologationPipeline._classify_by_origin_fallback('', 'PERDIDA')

    assert result['standard_code'] == 'ER.18'
    assert result['method'] == 'origin_fallback'
    assert result['confidence'] < 0.85


def test_fallback_de_origen_no_sustituye_codigo_existente():
    assert HomologationPipeline._classify_by_origin_fallback(
        '4.01.01', 'PERDIDA'
    ) is None


def test_pasivo_admite_categoria_patrimonio():
    assert HomologationPipeline._is_code_allowed_for_tipo('PAT.01', 'PASIVO')


def test_contra_activo_sin_codigo_se_clasifica_como_activo_fijo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'DEPRECIACION ACUMULADA ACTIVOS', 'ACTIVO'
    )

    assert result['standard_code'] == 'ANC.01.01'
    assert result['confidence'] < 0.85


def test_diccionario_migra_depreciacion_acumulada_al_subcodigo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'Depreciación Acumulada Activo Fijo',
        'codigo_estandar': 'ANC.01',
    }]

    result = pipeline._classify_by_dictionary_exact(
        'Depreciación Acumulada Activo Fijo'
    )

    assert result['standard_code'] == 'ANC.01.01'


def test_diccionario_migra_pat09_a_resultados_acumulados_pat03(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'Utilidades de ejercicios anteriores',
        'codigo_estandar': 'PAT.09',
    }]

    result = pipeline._classify_account(
        '', 'Utilidades de ejercicios anteriores', 'PATRIMONIO',
    )

    assert result['standard_code'] == 'PAT.03'
    assert 'PAT.09' in result['reason']


def test_reserva_patrimonial_clasifica_pat02_con_signo_indistinto(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual('Reservas legales', 'PATRIMONIO')

    assert result['standard_code'] == 'PAT.02'


def test_perdidas_acumuladas_en_activo_clasifican_pat03(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'Pérdidas acumuladas', 'PATRIMONIO'
    )

    assert result['standard_code'] == 'PAT.03'


def test_ganancias_acumuladas_negativas_clasifican_pat03(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'Ganancias acumuladas', 'PATRIMONIO'
    )

    assert result['standard_code'] == 'PAT.03'


@pytest.mark.parametrize('nombre,codigo,tipo', [
    ('Capital emitido', 'PAT.01', 'PATRIMONIO'),
    ('Ganancias (pérdidas) acumuladas', 'PAT.03', 'PATRIMONIO'),
    ('Ingresos de actividades ordinarias', 'ER.01', 'DESCONOCIDO'),
])
def test_etiqueta_auditada_precede_aprendizaje_incompatible(
    tmp_path, nombre, codigo, tipo,
):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._learning_engine.best_match = MagicMock(return_value={
        'source': 'runtime',
        'code': 'AC.08',
        'confidence': 0.99,
        'matched_name': nombre,
    })

    result = pipeline._classify_account('', nombre, tipo)

    assert result['standard_code'] == codigo
    assert result['method'] == 'audited_statement_label'


def test_pasivo_financiero_generico_usa_seccion_no_corriente(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_account(
        '', 'Pasivos financieros', 'PASIVO',
        account_section='Pasivos no corrientes',
    )

    assert result['standard_code'] == 'PNC.01'
    assert result['method'] == 'audited_statement_label'


@pytest.mark.parametrize('nombre,codigo', [
    ('Ganancia atribuible a los propietarios de la controladora', 'ER.20'),
    ('Ganancia atribuible a participaciones no controladoras', 'ER.21'),
])
@pytest.mark.parametrize('origen', ['GANANCIA', 'PERDIDA'])
def test_resultado_atribuible_clasifica_sin_depender_del_signo(
    tmp_path, nombre, codigo, origen,
):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex(nombre, origen)

    assert result['standard_code'] == codigo
    assert result['method'] == 'regex_fallback'
    assert result['confidence'] == 0.97


@pytest.mark.parametrize('nombre,tipo,codigo', [
    ('Efectivo y equivalentes al efectivo', 'ACTIVO', 'AC.01'),
    ('Cuentas por cobrar a entidades relacionadas, no corrientes', 'ACTIVO', 'ANC.05'),
    ('Otros pasivos financieros, no corrientes', 'PASIVO', 'PNC.01'),
    ('Ganancias (pérdidas) acumuladas', 'PATRIMONIO', 'PAT.03'),
    ('Ingresos de actividades ordinarias', 'DESCONOCIDO', 'ER.01'),
    ('Costo de ventas', 'DESCONOCIDO', 'ER.02'),
    ('Resultados por unidades de reajuste', 'DESCONOCIDO', 'ER.14'),
])
def test_etiquetas_exactas_de_estado_auditado_son_automaticas(
    tmp_path, nombre, tipo, codigo,
):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_audited_statement_label(nombre, tipo)

    assert result['standard_code'] == codigo
    assert result['method'] == 'audited_statement_label'
    assert result['confidence'] >= 0.85


def test_etiqueta_auditada_de_balance_exige_tipo_compatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    assert pipeline._classify_audited_statement_label(
        'Otros pasivos financieros, no corrientes', 'ACTIVO',
    ) is None


def test_process_clasifica_monto_comparativo_sin_ocho_columnas(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo=None,
        nombre='Ganancia atribuible a participaciones no controladoras',
        monto=26, origen_columna=OrigenColumna.DESCONOCIDO,
        montos_periodos={'2018': 26, '2017': 269},
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='auditado.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
    ))
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='ER.21', nota='', requiere_revision=False,
    ))

    result = pipeline.process(tmp_path / 'auditado.pdf')

    assert result['accounts_classified'] == 1
    assert not result['ignored']
    assert result['classified'][0]['standard_code'] == 'ER.21'
    assert result['classified'][0]['classification_amount'] == 26


def test_process_aplica_reglas_a_la_cuenta_actual(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'AC.01', 'confidence': 0.98,
        'method': 'dictionary_exact', 'reason': 'prueba', '_cmcc_score': -1,
    })
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='AC.01', nota='', requiere_revision=False,
    ))

    result = pipeline.process(tmp_path / 'balance.pdf')

    assert result['accounts_classified'] == 1
    assert pipeline._rule_processor.aplicar.call_args.kwargs['origen_columna'] \
        == OrigenColumna.ACTIVO
