import json
import pathlib
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


def test_subcuenta_bancaria_hereda_caja_y_bancos_del_control(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_account(
        '', 'BANCOESTADO 1', 'ACTIVO', account_hierarchy='BANCOS',
    )

    assert result['standard_code'] == 'AC.01'
    assert result['method'] == 'hierarchy_inheritance'
    assert result['confidence'] == 0.99


def test_depreciacion_generica_bajo_acumulada_hereda_contra_activo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_account(
        '', 'DEPRECIACIONES', 'ACTIVO',
        account_hierarchy='DEPRECIACIÓN ACUMULADA',
    )

    assert result['standard_code'] == 'ANC.01.01'
    assert result['method'] == 'hierarchy_inheritance'


def test_depreciacion_del_ejercicio_sin_contexto_no_hereda_contra_activo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_account(
        '', 'DEPRECIACIÓN EQUIPOS', 'PERDIDA', account_hierarchy=None,
    )

    assert result['standard_code'] != 'ANC.01.01'


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
    ('Otros pasivos financieros, no corrientes', 'PASIVO', 'PNC.05'),
    ('Activos por impuestos diferidos', 'ACTIVO', 'ANC.09'),
    ('Activos por impuestos diferidos, no corrientes', 'ACTIVO', 'ANC.09'),
    ('Otras provisiones', 'PASIVO', 'PC.09'),
    ('Pasivo por impuestos diferidos', 'PASIVO', 'PNC.06'),
    ('Pasivos por impuestos diferidos', 'PASIVO', 'PNC.06'),
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


# ---------------------------------------------------------------------------
# Regresión: impuestos diferidos y controles aritméticos — Encargo B3.2
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parents[1]


def _catalog() -> dict:
    return json.loads((_REPO_ROOT / 'catalogo_maestro.json').read_text())


# 1. ANC.09 — nombre recuperado desde catálogo
def test_anc09_nombre_desde_catalogo():
    cat = _catalog()
    entry = cat.get('ANC.09')
    assert entry is not None, 'ANC.09 no está en catalogo_maestro.json'
    assert entry['nombre_estandar'] == 'Activos por Impuestos Diferidos'
    assert entry['categoria'] == 'activo_no_corriente'
    assert entry['clasificable'] is True


# 2. PNC.06 — nombre recuperado desde catálogo
def test_pnc06_nombre_desde_catalogo():
    cat = _catalog()
    entry = cat.get('PNC.06')
    assert entry is not None, 'PNC.06 no está en catalogo_maestro.json'
    assert entry['nombre_estandar'] == 'Pasivos por Impuestos Diferidos'
    assert entry['categoria'] == 'pasivo_no_corriente'
    assert entry['clasificable'] is True


# 3. ANC.09 — clasificación automática exacta desde diccionario (pipeline)
@pytest.mark.parametrize('nombre', [
    'Activos por impuestos diferidos',
    'Activos por impuestos diferidos, no corrientes',
])
def test_anc09_clasificacion_automatica_exacta(tmp_path, nombre):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_by_dictionary_exact(nombre)
    assert result is not None, f'Sin coincidencia en diccionario para: {nombre!r}'
    assert result['standard_code'] == 'ANC.09'
    assert result['method'] == 'dictionary_exact'


# 4. PNC.06 — clasificación automática exacta desde diccionario (pipeline)
@pytest.mark.parametrize('nombre', [
    'Pasivo por impuestos diferidos',
    'Pasivos por impuestos diferidos',
])
def test_pnc06_clasificacion_automatica_exacta(tmp_path, nombre):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_by_dictionary_exact(nombre)
    assert result is not None, f'Sin coincidencia en diccionario para: {nombre!r}'
    assert result['standard_code'] == 'PNC.06'
    assert result['method'] == 'dictionary_exact'


# 5. ANC.09 — etiqueta auditada automática por tipo ACTIVO
def test_anc09_etiqueta_auditada_automatica(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_audited_statement_label(
        'Activos por impuestos diferidos', 'ACTIVO'
    )
    assert result is not None
    assert result['standard_code'] == 'ANC.09'
    assert result['confidence'] >= 0.85


# 6. PNC.06 — etiqueta auditada automática por tipo PASIVO
def test_pnc06_etiqueta_auditada_automatica(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_audited_statement_label(
        'Pasivos por impuestos diferidos', 'PASIVO'
    )
    assert result is not None
    assert result['standard_code'] == 'PNC.06'
    assert result['confidence'] >= 0.85


# 7. ANC.09 no se confunde con ANC.06 (Otros Activos No Corrientes)
def test_anc09_no_reutiliza_anc06(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_by_dictionary_exact('Activos por impuestos diferidos')
    assert result is not None
    assert result['standard_code'] != 'ANC.06', (
        'Activos por impuestos diferidos no debe caer en ANC.06'
    )


# 8. PNC.06 no se confunde con PNC.05 (Otros Pasivos LP)
def test_pnc06_no_reutiliza_pnc05(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    result = pipeline._classify_by_dictionary_exact('Pasivos por impuestos diferidos')
    assert result is not None
    assert result['standard_code'] != 'PNC.05', (
        'Pasivos por impuestos diferidos no debe caer en PNC.05'
    )


# 9. ER.11 tiene clasificable=False en el catálogo
def test_er11_no_clasificable():
    cat = _catalog()
    entry = cat.get('ER.11')
    assert entry is not None, 'ER.11 no está en catalogo_maestro.json'
    assert entry['clasificable'] is False, 'ER.11 debe tener clasificable=False'
    assert entry['nombre_estandar'] == 'Utilidad Neta'


# 10. PAT.04 tiene clasificable=False y es distinto de ER.11
def test_pat04_no_clasificable_y_separado_de_er11():
    cat = _catalog()
    er11 = cat.get('ER.11')
    pat04 = cat.get('PAT.04')
    assert pat04 is not None, 'PAT.04 no está en catalogo_maestro.json'
    assert pat04['clasificable'] is False, 'PAT.04 debe tener clasificable=False'
    assert pat04['nombre_estandar'] == 'Resultado del Ejercicio'
    # Deben ser entradas distintas
    assert pat04['nombre_estandar'] != er11['nombre_estandar']
    assert pat04['categoria'] != er11['categoria']


# 11. es_total=True impide que el monto se agregue al classification_amount
def test_es_total_excluye_monto_de_clasificacion(tmp_path):
    """
    El pipeline no debe asignar classification_amount a una fila con es_total=True
    ni incorporarla a la suma de cuentas clasificadas.
    """
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta_total = CuentaRaw(
        linea=99, codigo=None,
        nombre='Total activos',
        monto=1_000_000,
        es_total=True,
        montos_periodos={'2024': 1_000_000, '2023': 900_000},
    )
    cuenta_detalle = CuentaRaw(
        linea=10, codigo=None,
        nombre='Activos por impuestos diferidos',
        monto=50_000,
        es_total=False,
        montos_periodos={'2024': 50_000, '2023': 45_000},
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta_detalle, cuenta_total],
    ))
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='ANC.09', nota='', requiere_revision=False,
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'ANC.09', 'confidence': 0.98,
        'method': 'dictionary_exact', 'reason': 'prueba', '_cmcc_score': -1,
    })

    result = pipeline.process(tmp_path / 'balance.pdf')

    # Solo la cuenta de detalle debe contar; el total no agrega cuentas
    assert result['accounts_classified'] == 1, (
        f'Solo la cuenta de detalle debe clasificarse; '
        f'se clasificaron {result["accounts_classified"]}'
    )


# 12. El pipeline usa el monto del período actual correctamente (no trunca períodos)
def test_periodos_comparativos_se_preservan(tmp_path):
    """
    El pipeline debe usar el monto del período actual como classification_amount.
    Los montos_periodos del CuentaRaw son manejados internamente; el pipeline
    no los re-expone en 'classified' pero debe seleccionar el monto correcto.
    """
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=5, codigo=None,
        nombre='Activos por impuestos diferidos',
        monto=100,
        es_total=False,
        montos_periodos={'2024': 100, '2023': 80, '2022': 60},
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
    ))
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='ANC.09', nota='', requiere_revision=False,
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'ANC.09', 'confidence': 0.98,
        'method': 'dictionary_exact', 'reason': 'prueba', '_cmcc_score': -1,
    })

    result = pipeline.process(tmp_path / 'balance.pdf')

    classified = result.get('classified', [])
    assert classified, 'El proceso no devolvió cuentas clasificadas'
    anc09_rows = [r for r in classified if r.get('standard_code') == 'ANC.09']
    assert anc09_rows, 'No se encontró ANC.09 en las cuentas clasificadas'
    row = anc09_rows[0]
    # El monto clasificado debe ser el del período actual (100), no el de 2023 (80)
    assert row['classification_amount'] == 100.0, (
        f'El pipeline no usó el monto del período actual: {row["classification_amount"]}'
    )
