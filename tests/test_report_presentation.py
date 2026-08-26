from io import BytesIO
import pandas as pd
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from reporting_integrity import catalogo_local
from report_presentation import complete_catalog, ER_ORDER
from test_report_integrity import report_app, afuminsal


def test_complete_catalog_includes_empty_categories_and_calculates_once():
    grouped = pd.DataFrame([
        dict(codigo_clasificado="ER.01", monto_total=100, num_cuentas=1),
        dict(codigo_clasificado="ER.02", monto_total=-20, num_cuentas=1),
        dict(codigo_clasificado="ER.04", monto_total=-10, num_cuentas=1),
        dict(codigo_clasificado="ER.10", monto_total=-7, num_cuentas=1),
        dict(codigo_clasificado="ER.17", monto_total=2, num_cuentas=1),
    ])
    original = grouped.copy(deep=True)
    table, formulas = complete_catalog(grouped, catalogo_local(), True)
    assert set(table.codigo_clasificado) == set(catalogo_local())
    values = table.set_index("codigo_clasificado").monto_total
    assert values["ER.03"] == 80
    assert values["ER.06"] == 70
    assert values["ER.19"] == 72
    assert values["ER.11"] == 65
    assert values["ANC.01.01"] == 0
    assert not set(formulas["ER.11"]).intersection({"ER.03", "ER.06", "ER.08", "ER.19", "ER.11"})
    assert table[table.categoria == "resultado"].codigo_clasificado.tolist() == list(ER_ORDER)
    pd.testing.assert_frame_equal(original, grouped)


def test_missing_income_is_not_reported_as_zero_profit():
    table, _ = complete_catalog(pd.DataFrame([
        dict(codigo_clasificado="AC.01", monto_total=100, num_cuentas=1),
    ]), catalogo_local(), False)
    net = table.set_index("codigo_clasificado").loc["ER.11"]
    assert pd.isna(net.monto_total)
    assert net.estado_presentacion == "No disponible"


def test_export_has_summary_metadata_units_formulas_and_full_income():
    at = AppTest.from_function(report_app, args=(afuminsal(False),)).run(timeout=20)
    assert not at.exception
    data = at.session_state.export_kwargs["data"]
    workbook = load_workbook(BytesIO(data), data_only=False)
    assert workbook.sheetnames[0] == "Resumen"
    summary = workbook["Resumen"]
    assert summary["B5"].value == "$"
    assert summary["B6"].value
    assert summary["B7"].value is None
    summary_rows = {r[0].value: r[1].value for r in summary}
    for label in ("TOTAL ACTIVOS", "TOTAL PASIVOS", "TOTAL PATRIMONIO", "Diferencia de cuadratura", "Cuadratura aritmética"):
        assert summary_rows[label].startswith("=")
    income = workbook["Estado de Resultados"]
    assert [r[0].value for r in income.iter_rows(min_row=3) if r[0].value] == list(ER_ORDER)
    assert income["C2"].value == "Importe ($)"
    assert income["C3"].number_format.startswith("#,##0")
    assert income["C3"].value.startswith("='Balance Normalizado'!")
    assert "Control de emisión" in workbook.sheetnames
    first_stamp = summary["B6"].value
    at.run(timeout=20)
    second = load_workbook(BytesIO(at.session_state.export_kwargs["data"]))
    assert second["Resumen"]["B6"].value == first_stamp
