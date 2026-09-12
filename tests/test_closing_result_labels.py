"""Closing controls must not swallow accumulated equity balances."""

import pytest

from parser_universal import (
    FormatoCodigo,
    certificar_extraccion_columnas,
    parsear_linea,
)


@pytest.mark.parametrize("name", [
    "Utilidad/Perdida", "Utilidad/Pérdida", "Utilidad/Pérdida del ejercicio",
    "Pérdida del ejercicio", "Utilidades o pérdidas del año",
])
def test_closing_labels_are_controls(name):
    row = parsear_linea(
        f"{name} 0 0 0 100 0 100 0 0",
        1, FormatoCodigo.SIN_CODIGO, ".",
    )
    assert row is not None
    assert row.es_total


@pytest.mark.parametrize("name", [
    "Utilidades o pérdidas acumuladas", "Utilidad/Pérdida acumulada",
    "Resultados acumulados", "Pérdida por deterioro",
])
def test_accumulated_equity_and_expenses_remain_accounts(name):
    row = parsear_linea(
        f"{name} 0 0 100 0 100 0 0 0",
        1, FormatoCodigo.SIN_CODIGO, ".",
    )
    assert row is not None
    assert not row.es_total
    # A name must not excuse the deliberately wrong Debits/Credits identity.
    row.montos_columnas["debitos"] = 50.0
    certification = certificar_extraccion_columnas([row])
    assert certification.estado == "fallida"
    assert any("identidades" in reason for reason in certification.razones)
