import os
from pathlib import Path

import pytest

from account_qualification import qualify_cuentas, safe_mode_enabled
from parser_universal import (
    OrigenColumna,
    ParserPDF,
    _agrupar_palabras_por_linea,
    certificar_extraccion_columnas,
    parsear_excel,
    parsear_monto,
)


DEFAULT_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "balances_reales"
FIXTURES_DIR_ENV = os.environ.get("BALANCE_REAL_TEST_DIR")
FIXTURES_DIR = Path(FIXTURES_DIR_ENV) if FIXTURES_DIR_ENV else DEFAULT_FIXTURES_DIR


def _directorio_fixtures_reales() -> Path:
    """Devuelve la matriz privada o deja explícito que no está disponible.

    Los balances reales se excluyen del repositorio por contener información
    sensible. Si se configuró ``BALANCE_REAL_TEST_DIR``, una ruta inválida es
    un error de configuración y debe fallar. Sin esa variable, esta cobertura
    de integración se omite de manera visible, sin fingir que se ejecutó.
    """
    if FIXTURES_DIR.is_dir():
        return FIXTURES_DIR
    if FIXTURES_DIR_ENV:
        pytest.fail(
            "BALANCE_REAL_TEST_DIR no apunta a un directorio válido: "
            f"{FIXTURES_DIR}"
        )
    pytest.skip(
        "Fixtures reales privados no disponibles; configure "
        "BALANCE_REAL_TEST_DIR para ejecutar esta cobertura de integración."
    )


@pytest.fixture
def parser():
    return ParserPDF()


@pytest.mark.real_fixtures
def test_fixtures_exist():
    fixtures_dir = _directorio_fixtures_reales()
    files = list(fixtures_dir.glob("*"))
    assert len(files) >= 4, f"Expected at least 4 test files, found: {len(files)}"


@pytest.mark.parametrize(
    ("raw", "separator", "expected"),
    [
        ("(116.171)", ".", -116171.0),
        ("116.171-", ".", -116171.0),
        ("-116.171", ".", -116171.0),
        ("-", ".", 0.0),
        ("—", ".", 0.0),
        ("−", ".", 0.0),
        ("CLP $1.234", ".", 1234.0),
    ],
)
def test_parsear_monto_contable(raw, separator, expected):
    assert parsear_monto(raw, separator) == expected


def test_tolerancia_vertical_une_offset_tipografico():
    words = [
        {"text": "RETENCION", "top": 100.0, "x0": 10.0},
        {"text": "2DA.", "top": 102.0, "x0": 80.0},
        {"text": "CATEGORIA", "top": 102.4, "x0": 120.0},
    ]

    groups = _agrupar_palabras_por_linea(words)

    assert len(groups) == 1


def test_tolerancia_vertical_no_fusiona_filas_contables_distintas():
    words = [
        {"text": "CAJA", "top": 100.0, "x0": 10.0},
        {"text": "100", "top": 100.5, "x0": 150.0},
        {"text": "BANCO", "top": 103.0, "x0": 10.0},
        {"text": "200", "top": 103.4, "x0": 150.0},
    ]

    groups = _agrupar_palabras_por_linea(words)

    assert len(groups) == 2
    assert [[word["text"] for word in group] for group in groups] == [
        ["CAJA", "100"],
        ["BANCO", "200"],
    ]


def test_safe_mode_reconoce_activacion(monkeypatch):
    monkeypatch.setenv("SAFE_MODE", "true")
    assert safe_mode_enabled() is True


@pytest.mark.parametrize(
    "label",
    [
        "FIRMAS",
        "TOTALES IGUALES",
        "TOTAL GENERAL",
        "TOTALES GENERALES",
        "SUMAS IGUALES",
        "SUMAS GENERALES",
    ],
)
def test_safe_footer_descarta_control_aunque_tenga_monto(label):
    rows = [
        {"name": label, "columns": {"activo": 100.0}},
        {"name": "Caja", "columns": {"activo": 100.0}},
    ]

    qualified = qualify_cuentas(rows)

    assert qualified == [{"name": "Caja", "columns": {"activo": 100.0}}]


@pytest.mark.real_fixtures
def test_mar_vivo_pdf(parser):
    pdf_path = _directorio_fixtures_reales() / "Balance 2017 - Mar Vivo.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"

    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 10

    disponible_acct = [
        c for c in res.cuentas if "Disponible y Bancos" in c.nombre
    ]
    deudas_acct = [
        c for c in res.cuentas if "Deudas Bancarias Corto Plazo" in c.nombre
    ]

    assert disponible_acct, "Should split and extract 'Disponible y Bancos'"
    assert deudas_acct, "Should split and extract 'Deudas Bancarias Corto Plazo'"

    disp = disponible_acct[0]
    assert disp.montos_periodos["CLP"] == 137564463.0
    assert disp.montos_periodos["USD"] == 223773.0

    deuda = deudas_acct[0]
    assert deuda.montos_periodos["CLP"] == 930950530.0
    assert deuda.montos_periodos["USD"] == 1514356.0


@pytest.mark.real_fixtures
def test_naviera_orca_pdf(parser):
    pdf_path = _directorio_fixtures_reales() / "Balance 2017 - Naviera Orca.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"

    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 5
    assert any(
        "CLP" in c.montos_periodos or "USD" in c.montos_periodos
        for c in res.cuentas
    ), "Should populate currency keys in montos_periodos"


@pytest.mark.real_fixtures
def test_inagal_excel():
    excel_path = (
        _directorio_fixtures_reales()
        / "Pre-Balance al 31-12-2020_Inagal 76 273 859-7.xlsx"
    )
    assert excel_path.exists(), f"Missing: {excel_path}"

    cuentas = parsear_excel(excel_path)
    assert len(cuentas) > 10
    assert any(c.montos_periodos for c in cuentas if "caja" in c.nombre.lower())
    caja = next(c for c in cuentas if "caja moneda nacional" in c.nombre.lower())
    assert caja.codigo == "110100101"
    assert caja.origen_columna is OrigenColumna.ACTIVO
    assert certificar_extraccion_columnas(
        cuentas, metodo="excel_8_columns",
    ).estado == "no_evaluable"


@pytest.mark.real_fixtures
def test_agricola_general_excel():
    excel_path = (
        _directorio_fixtures_reales() / "BALANCE GENERAL AGRICOLA 2013.xlsx"
    )
    assert excel_path.exists(), f"Missing: {excel_path}"

    cuentas = parsear_excel(excel_path)
    assert len(cuentas) > 5
    assert any(c.monto and c.monto > 0 for c in cuentas)
    banco = next(c for c in cuentas if "banco santander" in c.nombre.lower())
    assert banco.monto == 452093
    assert banco.origen_columna is OrigenColumna.ACTIVO
    assert set(banco.montos_columnas) == {
        "debitos", "creditos", "saldo_deudor", "saldo_acreedor",
        "activo", "pasivo", "perdida", "ganancia",
    }
    certification = certificar_extraccion_columnas(
        cuentas, metodo="excel_8_columns",
    )
    assert certification.estado == "certificada"
    assert all(value == 0 for value in certification.diferencias.values())


@pytest.mark.real_fixtures
def test_los_maitenes_pdf(parser):
    pdf_path = _directorio_fixtures_reales() / "EEFF- 2017 Los Maitenes.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"

    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 10

    total_activos = [c for c in res.cuentas if c.nombre == "Total de Activos"]
    assert total_activos
    assert total_activos[0].monto == 441477.0

    costo_ventas = [c for c in res.cuentas if c.nombre == "Costo de Ventas"]
    assert costo_ventas
    assert costo_ventas[0].monto == -160646.0

    ganancias_acum = [c for c in res.cuentas if c.nombre == "Ganancias acumuladas"]
    assert ganancias_acum
    assert ganancias_acum[0].monto == -116171.0
