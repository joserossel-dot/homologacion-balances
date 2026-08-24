from types import SimpleNamespace
from unittest.mock import MagicMock

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

    assert result['standard_code'] == 'ANC.01'
    assert result['confidence'] < 0.85


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
