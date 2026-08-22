import os
from pathlib import Path
import pytest
from parser_universal import ParserPDF, parsear_excel

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "balances_reales"

@pytest.fixture
def parser():
    return ParserPDF()

def test_fixtures_exist():
    assert FIXTURES_DIR.exists(), f"Fixtures directory not found: {FIXTURES_DIR}"
    files = list(FIXTURES_DIR.glob("*"))
    assert len(files) >= 4, f"Expected at least 4 test files, found: {len(files)}"

def test_mar_vivo_pdf(parser):
    pdf_path = FIXTURES_DIR / "Balance 2017 - Mar Vivo.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"
    
    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 10
    
    # Check that Disponible y Bancos and Deudas Bancarias Corto Plazo were split
    nombres = [c.nombre for c in res.cuentas]
    
    disponible_acct = [c for c in res.cuentas if "Disponible y Bancos" in c.nombre]
    deudas_acct = [c for c in res.cuentas if "Deudas Bancarias Corto Plazo" in c.nombre]
    
    assert len(disponible_acct) >= 1, "Should split and extract 'Disponible y Bancos'"
    assert len(deudas_acct) >= 1, "Should split and extract 'Deudas Bancarias Corto Plazo'"
    
    # Check CLP and USD values are separated correctly in montos_periodos
    disp = disponible_acct[0]
    assert "CLP" in disp.montos_periodos
    assert "USD" in disp.montos_periodos
    assert disp.montos_periodos["CLP"] == 137564463.0
    assert disp.montos_periodos["USD"] == 223773.0

    deuda = deudas_acct[0]
    assert "CLP" in deuda.montos_periodos
    assert "USD" in deuda.montos_periodos
    assert deuda.montos_periodos["CLP"] == 930950530.0
    assert deuda.montos_periodos["USD"] == 1514356.0

def test_naviera_orca_pdf(parser):
    pdf_path = FIXTURES_DIR / "Balance 2017 - Naviera Orca.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"
    
    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 5
    
    # Verify currencies are detected and populated
    clp_usd_populated = any("CLP" in c.montos_periodos or "USD" in c.montos_periodos for c in res.cuentas)
    assert clp_usd_populated, "Should populate currency keys in montos_periodos"

def test_inagal_excel():
    excel_path = FIXTURES_DIR / "Pre-Balance al 31-12-2020_Inagal 76 273 859-7.xlsx"
    assert excel_path.exists(), f"Missing: {excel_path}"
    
    cuentas = parsear_excel(excel_path)
    assert len(cuentas) > 10
    
    # Verify years are detected from the columns and structured
    for c in cuentas:
        if "Caja" in c.nombre:
            assert len(c.montos_periodos) > 0
            break

def test_agricola_general_excel():
    excel_path = FIXTURES_DIR / "BALANCE GENERAL AGRICOLA 2013.xlsx"
    assert excel_path.exists(), f"Missing: {excel_path}"
    
    cuentas = parsear_excel(excel_path)
    assert len(cuentas) > 5
    
    # Verify we successfully extracted non-zero amounts
    assert any(c.monto and c.monto > 0 for c in cuentas)

def test_los_maitenes_pdf(parser):
    pdf_path = FIXTURES_DIR / "EEFF- 2017 Los Maitenes.pdf"
    assert pdf_path.exists(), f"Missing: {pdf_path}"
    
    res = parser.parsear(pdf_path)
    assert len(res.cuentas) > 10
    
    # Check total assets is parsed correctly (should be 441477.0)
    total_activos = [c for c in res.cuentas if "Total de Activos" == c.nombre]
    assert len(total_activos) >= 1
    assert total_activos[0].monto == 441477.0
    
    # Check negative cost of sales (Costo de Ventas should be -160646.0)
    costo_ventas = [c for c in res.cuentas if "Costo de Ventas" == c.nombre]
    assert len(costo_ventas) >= 1
    assert costo_ventas[0].monto == -160646.0
    
    # Check negative retained earnings (Ganancias acumuladas should be -116171.0)
    ganancias_acum = [c for c in res.cuentas if "Ganancias acumuladas" == c.nombre]
    assert len(ganancias_acum) >= 1
    assert ganancias_acum[0].monto == -116171.0
