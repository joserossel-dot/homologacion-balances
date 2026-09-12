"""Etiquetas canónicas requieren una sección contable compatible."""

import pytest

from pipeline.homologation_pipeline import HomologationPipeline


@pytest.fixture
def pipeline():
    # Estas reglas deterministas deben resolverse sin aprendizaje ni conexión.
    return HomologationPipeline.__new__(HomologationPipeline)


@pytest.mark.parametrize("name,origin,section,code", [
    ("Propiedades, planta y equipo", "ACTIVO", "Activos no corrientes", "ANC.01"),
    ("Activos por impuestos diferidos, no corrientes", "ACTIVO", "ANC", "ANC.09"),
    ("Pasivo por impuestos diferidos", "PASIVO", "PNC", "PNC.06"),
    ("Otros pasivos financieros, no corrientes", "PASIVO", "PNC", "PNC.05"),
    ("Cuentas por pagar a entidades relacionadas, no corrientes", "PASIVO", "PNC", "PNC.04"),
    ("Capital emitido", "PASIVO", "Patrimonio", "PAT.01"),
    ("Otras reservas", "PASIVO", "Patrimonio neto", "PAT.02"),
    ("Ganancias (pérdidas) acumuladas", "PASIVO", "PAT", "PAT.03"),
    ("Capital emitido", "DESCONOCIDO", "PAT", "PAT.01"),
])
def test_explicit_section_resolves_canonical_labels(pipeline, name, origin, section, code):
    result = pipeline._classify_account("", name, origin, account_section=section)
    assert result["standard_code"] == code
    assert result["method"] == "audited_statement_label"


@pytest.mark.parametrize("name,origin,section", [
    ("Propiedades, planta y equipo", "ACTIVO", "AC"),
    ("Activos por impuestos diferidos", "ACTIVO", "AC"),
    ("Otros pasivos financieros, no corrientes", "PASIVO", "PC"),
    ("Capital emitido", "PASIVO", "PC"),
    ("Otras reservas", "PASIVO", None),
    ("Capital emitido", "ACTIVO", "PAT"),
    ("Caja", "PASIVO", "PAT"),
    ("Reserva para cuentas incobrables", "PASIVO", "PAT"),
    ("Capital emitido y otras cuentas por pagar", "PASIVO", "PAT"),
    ("Total capital emitido", "PASIVO", "PAT"),
])
def test_section_does_not_bypass_incompatible_or_ambiguous_labels(pipeline, name, origin, section):
    assert pipeline._classify_audited_statement_label(name, origin, section) is None
