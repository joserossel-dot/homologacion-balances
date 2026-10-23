from types import SimpleNamespace
from unittest.mock import MagicMock

from parser_universal import (
    CertificacionExtraccion, CuentaRaw, FormatoCodigo, OrigenColumna,
    ResultadoParseo,
)
from app_validacion import _codigo_compatible_con_origen, _origen_efectivo
from parsers.account_type_resolver import (
    is_capital_pending_name,
    is_contra_asset_name,
    is_credit_balance_depreciation_name,
    is_debit_balance_financial_liability,
    is_historical_accumulated_result_name,
    is_current_result_name,
    result_year_from_name,
)
from pipeline.homologation_pipeline import (
    HomologationPipeline,
    _lineas_revision_extraccion,
)
from pipeline.features import CMCCFeatureFlags
from config.regex_rules import CODIGOS_REGEX_FALLBACK_AUDITADOS


def test_regex_fallback_usa_reglas_auditadas_por_codigo_y_no_por_indice():
    """Agregar una regla no debe desplazar los fallbacks habilitados."""
    codigos = tuple(
        code for _pattern, code, _confidence
        in HomologationPipeline._REGEX_FALLBACK
    )

    assert codigos == CODIGOS_REGEX_FALLBACK_AUDITADOS


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


def test_regex_contextual_sugiere_interes_como_ingreso_solo_en_ganancia(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    gain = pipeline._classify_by_regex_contextual(
        'Intereses Devengados Proyectos', 'GANANCIA',
    )
    loss = pipeline._classify_by_regex_contextual(
        'Intereses Devengados Proyectos', 'PERDIDA',
    )

    assert gain is not None
    assert gain['standard_code'] == 'ER.12'
    assert gain['confidence'] < 0.85
    assert loss is None


def test_regex_contextual_descarta_categoria_incompatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    assert pipeline._classify_by_regex_contextual('VENTA MOTOS', 'ACTIVO') is None


def test_sugerencia_contextual_bancaria_respeta_columna_fisica(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    activo = pipeline._classify_by_regex_contextual('BCO CHILE', 'ACTIVO')
    pasivo = pipeline._classify_by_regex_contextual('BCO BICE', 'PASIVO')

    assert activo is not None
    assert activo['standard_code'] == 'AC.01'
    assert activo['method'] == 'contextual_accounting_suggestion'
    assert activo['confidence'] < 0.85
    assert activo['requires_review'] is True
    assert pasivo is not None
    assert pasivo['standard_code'] == 'PC.02'
    assert pasivo['requires_review'] is True


def test_sugerencia_contextual_relacionadas_exige_tipo_compatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    cobrar = pipeline._classify_by_regex_contextual(
        'DOCTOS. Y CTAS. POR COBRAR EMP. REL. MU', 'ACTIVO',
    )
    pagar = pipeline._classify_by_regex_contextual(
        'DOCTOS. Y CTAS. POR PAGAR EMP. REL. MULT', 'PASIVO',
    )
    pagar_en_activo = pipeline._classify_by_regex_contextual(
        'DOCTOS. Y CTAS. POR PAGAR EMP. REL. MULT', 'ACTIVO',
    )

    assert cobrar is not None
    assert cobrar['standard_code'] == 'AC.06'
    assert cobrar['requires_review'] is True
    assert pagar is not None
    assert pagar['standard_code'] == 'PC.07'
    assert pagar['requires_review'] is True
    assert pagar_en_activo is None


def test_sugerencias_de_plan_con_saldo_fisico_siempre_quedan_en_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    relacionada = pipeline._classify_by_regex_contextual(
        'Empresas Relacionadas en UF', 'ACTIVO', '2.1.07.02',
    )
    prestamo = pipeline._classify_by_regex_contextual(
        'Prestamo Proyecto Inmob. en UF', 'ACTIVO', '1.3.02.03',
    )

    assert relacionada is not None
    assert relacionada['standard_code'] == 'AC.06'
    assert relacionada['requires_review'] is True
    assert prestamo is not None
    assert prestamo['standard_code'] == 'ANC.06'
    assert prestamo['requires_review'] is True


def test_sugerencia_contextual_obligacion_financiera_es_pasivo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'OBLIGACION INSTITUCIONES FINANCIERAS C/P', 'PASIVO',
    )

    assert result is not None
    assert result['standard_code'] == 'PC.02'
    assert result['requires_review'] is True


def test_sugerencias_contextuales_exactas_siempre_requieren_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    cases = (
        ('Plantaciones en Producción', 'ACTIVO', 'ANC.07'),
        ('Instituciones previsionales', 'PASIVO', 'PC.06'),
        ('Diferencia tipo de cambio', 'PERDIDA', 'ER.15'),
        ('Comisiones y gastos bancarios', 'PERDIDA', 'ER.09'),
    )
    for name, account_type, expected_code in cases:
        result = pipeline._classify_by_regex_contextual(name, account_type)
        assert result is not None
        assert result['standard_code'] == expected_code
        assert result['method'] == 'contextual_accounting_suggestion'
        assert result['confidence'] < 0.85
        assert result['requires_review'] is True


def test_reglas_contables_exactas_automaticas_exigen_texto_y_columna(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    cases = (
        ('Cotizaciones Previsionales', 'PASIVO', 'PC.06'),
        ('Retenciones Honorarios y Dietas', 'PASIVO', 'PC.05'),
        ('Retenciones Impto. Unico 2* Categ', 'PASIVO', 'PC.05'),
        ('Ingresos Anticipados Escuela', 'PASIVO', 'PC.08'),
        ('Interés Prestamos Bancarios', 'PERDIDA', 'ER.09'),
        ('Reajuste Fiscal', 'GANANCIA', 'ER.14'),
    )
    for name, account_type, expected_code in cases:
        result = pipeline._classify_by_exact_accounting_rule(name, account_type)
        assert result is not None
        assert result['standard_code'] == expected_code
        assert result['method'] == 'accounting_exact_rule'
        assert result['confidence'] >= 0.99
        assert 'requires_review' not in result

    assert pipeline._classify_by_exact_accounting_rule(
        'Cotizaciones Previsionales', 'ACTIVO',
    ) is None


def test_motor_de_decision_conserva_regla_contable_exacta_automatica(tmp_path):
    pipeline = HomologationPipeline(
        db_path=tmp_path / 'gold.db',
        features=CMCCFeatureFlags(ENABLE_DECISION_ENGINE=True),
    )
    pipeline._dictionary = []

    result = pipeline._classify_account(
        '21080504', 'Cotizaciones Previsionales', 'PASIVO',
    )

    assert result['standard_code'] == 'PC.06'
    assert result['method'] == 'accounting_exact_rule'
    assert result['decision_engine']['codigo_final'] is None


def test_motor_de_decision_conserva_sugerencia_contextual_revisable(tmp_path):
    pipeline = HomologationPipeline(
        db_path=tmp_path / 'gold.db',
        features=CMCCFeatureFlags(ENABLE_DECISION_ENGINE=True),
    )
    pipeline._dictionary = []

    result = pipeline._classify_account('', 'BCO CHILE', 'ACTIVO')

    assert result['standard_code'] == 'AC.01'
    assert result['method'] == 'contextual_accounting_suggestion'
    assert result['requires_review'] is True
    assert result['decision_engine']['codigo_final'] is None


def test_fallback_de_origen_clasifica_y_exige_revision():
    result = HomologationPipeline._classify_by_origin_fallback('', 'PERDIDA')

    assert result['standard_code'] == 'ER.18'
    assert result['method'] == 'origin_fallback'
    assert result['confidence'] < 0.85


def test_fallback_de_origen_no_sustituye_codigo_existente():
    assert HomologationPipeline._classify_by_origin_fallback(
        '4.01.01', 'PERDIDA'
    ) is None


def test_fallback_de_origen_sugiere_si_el_codigo_no_tuvo_homologacion(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_account(
        '3.2.02.02', 'Concepto sin equivalencia local', 'GANANCIA',
    )

    assert result['standard_code'] == 'ER.17'
    assert result['method'] == 'origin_fallback'
    assert result['confidence'] < 0.85
    assert 'código de origen no tuvo homologación compatible' in result['reason']


def test_reconstruccion_final_acotada_delimita_la_revision_de_extraccion():
    certificacion = CertificacionExtraccion(
        estado='parcial',
        reconstruccion_final_revisable=True,
        reconstrucciones_finales=[{
            'linea': 7, 'cuenta': 'Terreno', 'columnas': ['activo'],
            'importe': 100,
        }],
    )

    assert _lineas_revision_extraccion(certificacion) == {7}
    assert _lineas_revision_extraccion(
        CertificacionExtraccion(estado='parcial'),
    ) is None


def test_reconstruccion_movimiento_acotada_delimita_la_revision_de_extraccion():
    certificacion = CertificacionExtraccion(
        estado='parcial',
        reconstruccion_movimientos_revisable=True,
        reconstrucciones_movimientos=[{
            'linea': 7, 'cuenta': 'Terreno', 'columnas': ['debitos'],
            'importe': 100,
        }],
    )

    assert _lineas_revision_extraccion(certificacion) == {7}


def test_pipeline_solo_fuerza_revision_en_fila_final_reconstruida(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuentas = [
        CuentaRaw(
            linea=1, codigo='110101', nombre='Caja revisable', monto=100,
            origen_columna=OrigenColumna.ACTIVO,
        ),
        CuentaRaw(
            linea=2, codigo='110102', nombre='Banco observado', monto=100,
            origen_columna=OrigenColumna.ACTIVO,
        ),
    ]
    certificacion = CertificacionExtraccion(
        estado='parcial', metodo='ocr_coordinates_8_amounts',
        orientacion_certificada=True,
        reconstruccion_final_revisable=True,
        reconstrucciones_finales=[{
            'linea': 1, 'cuenta': 'Caja revisable', 'columnas': ['activo'],
            'importe': 100,
        }],
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=cuentas, certificacion_extraccion=certificacion,
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
    filas = {fila['account_name']: fila for fila in result['classified']}

    assert result['automatic_decisions_allowed'] is True
    assert filas['Caja revisable']['extraction_review_required'] is True
    assert filas['Caja revisable']['review_required'] is True
    assert filas['Banco observado']['extraction_review_required'] is False
    assert filas['Banco observado']['review_required'] is False


def test_pipeline_solo_fuerza_revision_en_movimiento_reconstruido(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuentas = [
        CuentaRaw(
            linea=1, codigo='110101', nombre='Caja revisable', monto=100,
            origen_columna=OrigenColumna.ACTIVO,
        ),
        CuentaRaw(
            linea=2, codigo='110102', nombre='Banco observado', monto=100,
            origen_columna=OrigenColumna.ACTIVO,
        ),
    ]
    certificacion = CertificacionExtraccion(
        estado='parcial', metodo='ocr_coordinates_8_amounts',
        orientacion_certificada=True,
        reconstruccion_movimientos_revisable=True,
        reconstrucciones_movimientos=[{
            'linea': 1, 'cuenta': 'Caja revisable', 'columnas': ['debitos'],
            'importe': 100,
        }],
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=cuentas, certificacion_extraccion=certificacion,
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
    filas = {fila['account_name']: fila for fila in result['classified']}

    assert result['automatic_decisions_allowed'] is True
    assert filas['Caja revisable']['extraction_review_required'] is True
    assert filas['Banco observado']['extraction_review_required'] is False
    assert filas['Banco observado']['review_required'] is False


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


def test_abreviatura_dep_acumulada_es_contra_activo():
    assert is_contra_asset_name('DEP. ACUMULADA BIENES RAICES')


def test_depreciacion_acreedora_es_regla_contextual_acotada():
    assert is_credit_balance_depreciation_name(
        'DEP.CONSTRUCCIONES', 'pasivo', 472611756,
    )
    assert is_credit_balance_depreciation_name(
        'DE. DEL EJERC EQ. COMPUTA', 'acreedor', 17683719,
    )
    assert not is_credit_balance_depreciation_name(
        'Depreciación del Ejercicio', 'perdida', 100,
    )
    assert not is_credit_balance_depreciation_name(
        'Depósito a plazo', 'pasivo', 100,
    )


def test_depreciacion_acreedora_sugiere_contra_activo_y_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_credit_balance_depreciation(
        'DEP.CONSTRUCCIONES', 'pasivo', 472611756,
    )

    assert result is not None
    assert result['standard_code'] == 'ANC.01.01'
    assert result['requires_review'] is True
    assert result['method'] == 'contextual_credit_balance_depreciation'


def test_obligacion_bancaria_deudora_es_regla_acotada():
    assert is_debit_balance_financial_liability(
        'OBLIG .CON BCO E INST. FINANCIERA C/P', 'activo', 242655,
    )
    assert not is_debit_balance_financial_liability(
        'Proveedores nacionales', 'activo', 242655,
    )
    assert not is_debit_balance_financial_liability(
        'OBLIG .CON BCO E INST. FINANCIERA C/P', 'pasivo', 242655,
    )


def test_diccionario_exacto_para_contra_pasivo_exige_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'OBLIG .CON BCO E INST. FINANCIERA C/P',
        'codigo_estandar': 'PC.02',
    }]

    result = pipeline._classify_debit_balance_financial_liability(
        'OBLIG .CON BCO E INST. FINANCIERA C/P',
    )

    assert result is not None
    assert result['standard_code'] == 'PC.02'
    assert result['requires_review'] is True
    assert result['method'] == 'dictionary_exact_contra_pasivo'


def test_capital_por_enterar_se_trata_como_contra_patrimonio(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'CAPITAL POR ENTERAR', 'codigo_estandar': 'PAT.07',
    }]

    result = pipeline._classify_account(
        '', 'Capital Por Enterar', 'PATRIMONIO',
    )

    assert is_capital_pending_name('Capital pendiente de enterar')
    assert _origen_efectivo('activo', 100, 'Capital por enterar') == 'patrimonio'
    assert _codigo_compatible_con_origen(
        'PAT.07', 'activo', 100, 'Capital por enterar',
    )
    assert result['standard_code'] == 'PAT.07'
    assert result['method'] == 'dictionary_exact'


def test_resultado_del_ejercicio_es_patrimonial_y_no_resultado_acumulado():
    assert is_current_result_name('UTILIDAD (PERDIDA) DEL EJERCICIO')
    assert is_current_result_name('Pérdida del Ejercicio')
    assert not is_current_result_name('Utilidades acumuladas')


def test_resultado_del_ejercicio_activo_acepta_pat04_del_diccionario(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'UTILIDAD (PERDIDA) DEL EJERCICIO',
        'codigo_estandar': 'PAT.04',
    }]

    result = pipeline._classify_account(
        '', 'UTILIDAD (PERDIDA) DEL EJERCICIO', 'PATRIMONIO',
    )

    assert result['standard_code'] == 'PAT.04'
    assert result['method'] == 'dictionary_exact'


def _process_explicit_result_year(
    tmp_path, *, account_name, account_code='2402-01',
    origen=OrigenColumna.ACTIVO, closing_year=2024, seccion_contable=None,
):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo=account_code, nombre=account_name, monto=100,
        origen_columna=origen, seccion_contable=seccion_contable,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
    ))
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='', nota='', requiere_revision=False,
    ))

    result = pipeline.process(
        tmp_path / 'balance.pdf', closing_year=closing_year,
    )
    return result['classified'][0]


def test_resultado_anual_historico_2402_en_activo_es_pat03(tmp_path):
    row = _process_explicit_result_year(
        tmp_path, account_name='RESULTADO AÑO 2022', closing_year=2024,
    )

    assert result_year_from_name('RESULTADO AÑO 2022') == 2022
    assert is_historical_accumulated_result_name(
        'RESULTADO AÑO 2022', account_code='2402-01', closing_year=2024,
    )
    assert row['origen_columna'] == 'activo'
    assert row['origen_columna_efectiva'] == 'patrimonio'
    assert row['standard_code'] == 'PAT.03'
    assert row['final_code'] == 'PAT.03'
    assert row['method'] == 'historical_result_year'
    assert row['review_required'] is False


def test_resultado_historico_2402_prevalece_sobre_seccion_activo(tmp_path):
    row = _process_explicit_result_year(
        tmp_path,
        account_name='RESULTADO AÑO 2022',
        closing_year=2024,
        seccion_contable='activo',
    )

    assert row['origen_columna'] == 'activo'
    assert row['seccion_contable'] == 'activo'
    assert row['origen_columna_efectiva'] == 'patrimonio'
    assert row['standard_code'] == 'PAT.03'
    assert row['final_code'] == 'PAT.03'


def test_resultado_anual_historico_exige_codigo_2402_y_cierre_confirmado():
    assert not is_historical_accumulated_result_name(
        'RESULTADO AÑO 2022', account_code='', closing_year=2024,
    )
    assert not is_historical_accumulated_result_name(
        'RESULTADO AÑO 2022', account_code='2402-01', closing_year=None,
    )
    assert not is_historical_accumulated_result_name(
        'RESULTADO AÑO 2022', account_code='2402-01', closing_year=2022,
    )


def test_resultado_del_cierre_nunca_pasa_silenciosamente_a_pat03(tmp_path):
    row = _process_explicit_result_year(
        tmp_path,
        account_name='RESULTADO AÑO 2024',
        origen=OrigenColumna.PASIVO,
        closing_year=2024,
    )

    assert row['origen_columna'] == 'pasivo'
    assert row['origen_columna_efectiva'] == 'patrimonio'
    assert row['standard_code'] == 'PAT.04'
    assert row['final_code'] == 'PAT.04'
    assert row['standard_code'] != 'PAT.03'
    assert row['review_required'] is True


def test_resultado_del_cierre_sin_2402_no_pasa_a_pat04(tmp_path):
    row = _process_explicit_result_year(
        tmp_path,
        account_name='RESULTADO AÑO 2024',
        account_code='1101-01',
        origen=OrigenColumna.PASIVO,
        closing_year=2024,
    )

    assert row['standard_code'] is None
    assert row['final_code'] is None
    assert row['method'] == 'unclassified_current_result_year'
    assert row['review_required'] is True


def test_resultado_anual_futuro_nunca_pasa_silenciosamente_a_pat03(tmp_path):
    row = _process_explicit_result_year(
        tmp_path,
        account_name='RESULTADO ANO 2025',
        origen=OrigenColumna.PASIVO,
        closing_year=2024,
    )

    assert row['standard_code'] is None
    assert row['final_code'] is None
    assert row['method'] == 'unclassified_future_result_year'
    assert row['review_required'] is True


def test_codigo_incompatible_no_oculta_un_nombre_exacto_del_diccionario(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = [{
        'cuenta_original': 'GASTOS DE ADMINISTRACIÓN',
        'codigo_estandar': 'ER.04',
    }]

    result = pipeline._classify_account(
        '3-01-06-01', 'GASTOS DE ADMINISTRACIÓN', 'PERDIDA',
    )

    # El clasificador de código propone PAT.03 para este plan ajeno. La
    # columna PÉRDIDA lo invalida y debe permitir la coincidencia exacta.
    assert result['standard_code'] == 'ER.04'
    assert result['method'] == 'dictionary_exact'


def test_codigo_incompatible_habilita_regla_contextual_para_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._dictionary = []

    result = pipeline._classify_account(
        '3-01-06-01', 'COSTO DE VENTA ACCION', 'PERDIDA',
    )

    assert result['standard_code'] == 'ER.02'
    assert result['method'] == 'regex_contextual'
    assert result['confidence'] < 0.85


def test_aprendizaje_incompatible_no_oculta_diccionario_compatible(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._learning_engine.best_match = MagicMock(return_value={
        'source': 'exact', 'code': 'PC.06', 'confidence': 0.98,
        'matched_name': 'HONORARIOS',
    })
    pipeline._dictionary = [{
        'cuenta_original': 'HONORARIOS', 'codigo_estandar': 'ER.04',
    }]

    result = pipeline._classify_account('', 'HONORARIOS', 'PERDIDA')

    assert result['standard_code'] == 'ER.04'
    assert result['method'] == 'dictionary_exact'
    assert result['learning_rejected']['standard_code'] == 'PC.06'


def test_aprendizaje_compatible_conserva_prioridad(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    pipeline._learning_engine.best_match = MagicMock(return_value={
        'source': 'exact', 'code': 'PC.06', 'confidence': 0.98,
        'matched_name': 'HONORARIOS',
    })
    pipeline._dictionary = [{
        'cuenta_original': 'HONORARIOS', 'codigo_estandar': 'ER.04',
    }]

    result = pipeline._classify_account('', 'HONORARIOS', 'PASIVO')

    assert result['standard_code'] == 'PC.06'
    assert result['method'] == 'learning_exact'


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


def test_resultados_retenidos_clasifican_pat03(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'Resultado Retenidos', 'PATRIMONIO'
    )

    assert result['standard_code'] == 'PAT.03'


def test_utilidad_o_perdida_de_balance_clasificado_es_resultado_periodo(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')

    result = pipeline._classify_by_regex_contextual(
        'Utilidad o (Pérdida)', 'PATRIMONIO'
    )

    assert result['standard_code'] == 'PAT.04'


def test_process_aplica_reglas_a_la_cuenta_actual(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    control = CuentaRaw(
        linea=2, codigo=None, nombre='SUMAS', monto=100,
        origen_columna=OrigenColumna.ACTIVO, es_total=True,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta, control],
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

    assert result['accounts_total'] == 2
    assert result['accounts_classified'] == 1
    assert result['accounts_ignored'] == 1
    assert result['ignored'] == [{
        'account_code': '', 'account_name': 'SUMAS',
        'ignored_reason': 'extraction_control',
    }]
    assert pipeline._classify_account.call_count == 1
    assert result['extraction_certification_state'] == 'no_evaluable'
    assert result['automatic_decisions_allowed'] is False
    assert result['classified'][0]['review_required'] is True
    assert result['classified'][0]['extraction_review_required'] is True
    assert result['delivery_readiness']['estado'] == 'EXTRACCION_NO_VALIDADA'
    assert pipeline._rule_processor.aplicar.call_args.kwargs['origen_columna'] \
        == OrigenColumna.ACTIVO


def test_process_permite_decision_automatica_solo_con_extraccion_certificada(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
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

    assert result['extraction_certification_state'] == 'certificada'
    assert result['automatic_decisions_allowed'] is True
    assert result['classified'][0]['review_required'] is False
    assert result['classified'][0]['extraction_review_required'] is False
    assert result['delivery_readiness']['estado'] == 'LISTO_PARA_REVISION_ANALISTA'


def test_process_reenvia_a_revision_la_confianza_bajo_el_umbral(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'AC.01', 'confidence': 0.84,
        'method': 'regex_contextual', 'reason': 'prueba', '_cmcc_score': -1,
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

    assert result['classified'][0]['review_required'] is True
    assert result['delivery_readiness']['cobertura']['cuentas']['sugeridas'] == 1


def test_process_respeta_revision_pedida_por_motor_decision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'AC.01', 'confidence': 0.90,
        'method': 'decision_sm_high', 'reason': 'prueba', '_cmcc_score': -1,
        'decision_engine': {'review_required': True},
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

    assert result['classified'][0]['review_required'] is True
    assert result['delivery_readiness']['cobertura']['cuentas']['sugeridas'] == 1


def test_process_depreciacion_acreedora_siempre_exige_revision(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='120403', nombre='DEP.CONSTRUCCIONES', monto=100,
        origen_columna=OrigenColumna.PASIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
    ))
    # Simula una coincidencia ANC genérica previa. La regla contextual debe
    # conservarla como propuesta revisable, no convertirla en automática.
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'ANC.01', 'confidence': 0.98,
        'method': 'dictionary_exact', 'reason': 'prueba', '_cmcc_score': -1,
    })
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='ANC.01', nota='', requiere_revision=False,
    ))

    result = pipeline.process(tmp_path / 'balance.pdf')

    classified = result['classified'][0]
    assert classified['final_code'] == 'ANC.01.01'
    assert classified['method'] == 'contextual_credit_balance_depreciation'
    assert classified['review_required'] is True
    assert classified['extraction_review_required'] is False


def test_process_depreciacion_acumulada_explicita_conserva_regla_previa(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='120403', nombre='DEPRECIACION ACUMULADA', monto=100,
        origen_columna=OrigenColumna.PASIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(
            estado='certificada', metodo='coordinates_8_amounts',
        ),
    ))
    pipeline._classify_account = MagicMock(return_value={
        'standard_code': 'ANC.01.01', 'confidence': 0.98,
        'method': 'dictionary_exact', 'reason': 'prueba', '_cmcc_score': -1,
    })
    pipeline._semantic_engine.interpret = MagicMock(
        return_value=SimpleNamespace(to_dict=lambda: {
            'semantic_type': 'unknown', 'confidence': 0.0,
        })
    )
    pipeline._rule_processor.aplicar = MagicMock(return_value=SimpleNamespace(
        aplica=False, codigo_final='ANC.01.01', nota='', requiere_revision=False,
    ))

    result = pipeline.process(tmp_path / 'balance.pdf')

    classified = result['classified'][0]
    assert classified['final_code'] == 'ANC.01.01'
    assert classified['method'] == 'dictionary_exact'
    assert classified['review_required'] is False


def test_process_no_certifica_ajuste_incompatible_con_columna_de_origen(tmp_path):
    pipeline = HomologationPipeline(db_path=tmp_path / 'gold.db')
    cuenta = CuentaRaw(
        linea=1, codigo='101001', nombre='Caja', monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )
    pipeline._parser.parsear = MagicMock(return_value=ResultadoParseo(
        archivo='balance.pdf', formato_codigo=FormatoCodigo.SIN_CODIGO,
        separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
        cuentas=[cuenta],
        certificacion_extraccion=CertificacionExtraccion(estado='certificada'),
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
        aplica=True, codigo_final='PC.01', nota='', requiere_revision=False,
    ))

    result = pipeline.process(tmp_path / 'balance.pdf')

    fila = result['classified'][0]
    assert fila['final_code'] == 'PC.01'
    assert fila['compatible'] is False
    assert fila['review_required'] is True
    assert result['homologated_balance_certified'] is False
