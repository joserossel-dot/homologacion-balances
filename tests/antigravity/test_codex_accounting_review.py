import pandas as pd
import pytest
import app_validacion as app
from parser_universal import CuentaRaw, OrigenColumna, RAW_MONETARY_COLUMNS, es_ruido_ocr_no_contable, _validar_columnas_finales, certificar_extraccion_columnas
from pipeline.homologation_pipeline import HomologationPipeline


@pytest.mark.parametrize('name', ['Honorarios auditores externos', 'Impuesto de timbre y estampillas', 'Documentos por cobrar nota 12'])
def test_account_words_are_not_document_noise(name):
    row = CuentaRaw(1, None, name, 100)
    assert not es_ruido_ocr_no_contable(row)


@pytest.mark.parametrize('tolerance,difference,expected', [(1, .5, True), (0, .01, False), (1, 2, False)])
def test_final_columns_respect_explicit_tolerance(tolerance, difference, expected):
    amounts = dict.fromkeys(RAW_MONETARY_COLUMNS, 0.0)
    amounts.update(debitos=100, saldo_deudor=100, activo=100)
    row = CuentaRaw(1, '1', 'Caja', 100, origen_columna=OrigenColumna.ACTIVO, montos_columnas=amounts)
    calculated = dict(amounts)
    printed = dict(amounts, activo=100 + difference, ganancia=100 + difference)
    calculated['ganancia'] = 100
    assert _validar_columnas_finales([row], [row], printed, calculated, [], [], tolerance) is expected


@pytest.mark.parametrize('name', ['Amortización acumulada software', 'Deterioro acumulado licencias'])
def test_incompatible_special_code_does_not_invent_replacement(name):
    result = HomologationPipeline._canonicalize_special_code(
        {'standard_code': 'ANC.01.01', 'confidence': 1, 'method': 'learning_gold'}, name)
    assert result['standard_code'] is None
    assert result['confidence'] == 0


def frame():
    df = pd.DataFrame([{'monto': 100., 'monto_periodo_2024': 100., 'monto_periodo_2023': 80.,
                        'monto_periodo_actual': 100., 'monto_periodo_anterior': 80.}])
    df.attrs['certification_binding'] = {'digest': 'old'}
    return df


def test_edit_previous_year_preserves_current_and_updates_alias():
    df = frame()
    app._aplicar_edicion_monto_periodos(df, 0, 75, '2023')
    assert df.at[0, 'monto_periodo_2023'] == 75
    assert df.at[0, 'monto_periodo_anterior'] == 75
    assert df.at[0, 'monto_periodo_actual'] == 100
    assert df.at[0, 'monto'] == 100
    assert 'certification_binding' not in df.attrs
    assert app._valor_fila_periodo(df.iloc[0], '2023', 1) == 75


@pytest.mark.parametrize('amount,year', [(float('nan'), '2024'), (float('inf'), '2024'), (10, '2022')])
def test_invalid_edit_is_atomic(amount, year):
    df = frame()
    before = df.copy(deep=True)
    with pytest.raises(ValueError):
        app._aplicar_edicion_monto_periodos(df, 0, amount, year)
    pd.testing.assert_frame_equal(df, before)
    assert df.attrs == before.attrs


@pytest.mark.parametrize('name', ['Honorarios auditores externos', 'Impuesto de timbre y estampillas', 'Documentos por cobrar nota 12'])
def test_uncoded_accounts_survive_full_column_certification(name):
    rows = []
    for i, (label, col, amount) in enumerate([('Caja', 'activo', 100), ('Capital', 'pasivo', 100), (name, 'perdida', 10), ('Ingresos', 'ganancia', 10)]):
        values = dict.fromkeys(RAW_MONETARY_COLUMNS, 0.)
        values[col] = amount
        debit = col in {'activo', 'perdida'}
        values['debitos' if debit else 'creditos'] = amount
        values['saldo_deudor' if debit else 'saldo_acreedor'] = amount
        rows.append(CuentaRaw(i, None if i == 2 else str(i + 1), label, amount,
                              origen_columna=OrigenColumna(col), montos_columnas=values))
    totals = {col: sum(r.montos_columnas[col] for r in rows) for col in RAW_MONETARY_COLUMNS}
    rows.append(CuentaRaw(4, None, 'Sumas', None, es_total=True, montos_columnas=dict(totals)))
    rows.append(CuentaRaw(5, None, 'Sumas totales', None, es_total=True, montos_columnas=dict(totals)))
    cert = certificar_extraccion_columnas(rows, metodo='excel_8_columns')
    assert cert.filas_evaluadas == 4
    assert cert.columnas_finales_validadas


@pytest.mark.parametrize('name', ['Firma Representante Legal', 'Contador General', 'RUT: 76.543.210-K', 'Página 1 de 2'])
def test_explicit_zero_metadata_remains_noise(name):
    assert es_ruido_ocr_no_contable(CuentaRaw(1, None, name, 0))


def test_decision_engine_incompatible_code_abstains(tmp_path, monkeypatch):
    pipeline = HomologationPipeline(db_path=tmp_path / 'synthetic.db')
    pipeline._features.ENABLE_DECISION_ENGINE = True
    monkeypatch.setattr(pipeline._learning_engine, 'best_match', lambda _: {'source': 'none'})
    monkeypatch.setattr(pipeline, '_classify_with_decision_engine', lambda *a, **k: {
        'standard_code': 'ANC.01.01', 'confidence': 1., 'method': 'decision_engine'})
    result = pipeline._classify_account('', 'Amortización acumulada software', 'ACTIVO', account_section='ANC')
    assert result['standard_code'] is None
    assert result['confidence'] == 0


def test_current_year_edit_preserves_previous_and_export_values():
    df = frame()
    app._aplicar_edicion_monto_periodos(df, 0, 120, '2024', periodos=('2024', '2023'))
    assert app._valor_fila_periodo(df.iloc[0], '2024', 0) == 120
    assert app._valor_fila_periodo(df.iloc[0], '2023', 1) == 80
    assert df.at[0, 'monto_periodo_anterior'] == 80
    assert df.at[0, 'monto'] == 120
    assert 'certification_binding' not in df.attrs
