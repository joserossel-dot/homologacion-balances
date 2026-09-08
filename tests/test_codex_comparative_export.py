"""Synthetic comparative edit through the real report renderer, not private Gold."""
from io import BytesIO

import pandas as pd
import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

import app_validacion as app
from test_report_integrity import afuminsal, report_app


@pytest.mark.parametrize('year', ['2024', '2023'])
def test_edited_period_reaches_download_without_changing_other_period(year):
    df = pd.DataFrame(afuminsal(False))
    df['monto_periodo_2024'] = df['monto']
    df['monto_periodo_2023'] = df['monto'] * .8
    df['monto_periodo_actual'] = df['monto_periodo_2024']
    df['monto_periodo_anterior'] = df['monto_periodo_2023']
    before = df.copy(deep=True)
    df.attrs['certification_binding'] = {'digest': 'obsolete'}
    amount = float(df.loc[0, 'monto_periodo_' + year]) + 12345
    app._aplicar_edicion_monto_periodos(df, 0, amount, year, periodos=('2024', '2023'))
    assert 'certification_binding' not in df.attrs
    # An unresolved certificate must not become valid merely by exporting edits.
    at = AppTest.from_function(report_app, args=(df.to_dict('records'),
        '__resolved_without_adjustment__', 'fallida'))
    at.session_state['company_periodos_seleccionados'] = ('2024', '2023')
    at.session_state['depreciation_reclassifications'] = {
        'caso.pdf': {'2024': {'mode': 'none'}, '2023': {'mode': 'none'}}}
    at.run(timeout=30)
    assert not at.exception
    download = at.session_state['export_kwargs']
    assert download['file_name'].startswith('BORRADOR-')
    wb = load_workbook(BytesIO(download['data']), data_only=True)
    rows = list(wb['Balance Normalizado'].values)
    header_index = next(i for i, row in enumerate(rows) if 'Monto Extraído 2024' in row)
    headers = rows[header_index]
    detail = next(row for row in rows[header_index + 1:] if row[headers.index('Nombre')] == 'Activos')
    for period in ('2024', '2023'):
        expected = amount if period == year else before.loc[0, 'monto_periodo_' + period]
        assert detail[headers.index('Monto Extraído ' + period)] == expected
        assert detail[headers.index('Monto Normalizado ' + period)] == expected
