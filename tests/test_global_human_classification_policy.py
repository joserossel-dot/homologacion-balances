import json
from pathlib import Path

import pytest

from pipeline.homologation_pipeline import HomologationPipeline


@pytest.fixture
def pipeline():
    # Canonical rules must execute before historical learning or dictionary reads.
    return HomologationPipeline.__new__(HomologationPipeline)


@pytest.mark.parametrize("name,tipo,section,expected", [
    ("Otros activos financieros", "ACTIVO", None, "AC.08"),
    (" OTROS ACTIVOS FINANCIEROS, CORRIENTES ", "ACTIVO", "Activo corriente", "AC.08"),
    ("Otros pasivos financieros no corrientes", "PASIVO", None, "PNC.05"),
    ("Otros pasivos financieros", "PASIVO", "Pasivos no corrientes", "PNC.05"),
    ("Costos de distribución", "PERDIDA", None, "ER.04"),
    ("COSTO DE DISTRIBUCION", None, "Estado de resultados", "ER.04"),
])
def test_approved_global_labels_take_precedence(pipeline, name, tipo, section, expected):
    result = pipeline._classify_account("", name, tipo, account_section=section)
    assert result["standard_code"] == expected
    assert result["method"] == "audited_statement_label"


@pytest.mark.parametrize("name,tipo,section,expected", [
    ("Otros pasivos financieros corrientes", "PASIVO", None, "PC.02"),
    ("Pasivos financieros no corrientes", "PASIVO", None, "PNC.01"),
    ("Pasivos financieros", "PASIVO", "Pasivos no corrientes", "PNC.01"),
    ("Otros activos financieros no corrientes", "ACTIVO", None, None),
    ("Otros activos financieros", "ACTIVO", "Activo no corriente", None),
    ("Otros activos financieros", "PASIVO", None, None),
    ("Costos de distribución", "PASIVO", None, None),
    ("Total costos de distribución", "PERDIDA", None, None),
    ("Provisión costos de distribución", "PASIVO", None, None),
])
def test_global_policy_does_not_match_neighbors(pipeline, name, tipo, section, expected):
    result = pipeline._classify_audited_statement_label(name, tipo, section)
    assert (result["standard_code"] if result else None) == expected


def test_local_dictionary_contains_only_one_approved_mapping_per_exact_label():
    entries = json.loads((Path(__file__).resolve().parents[1] / "diccionario.json").read_text())
    for name, code in [("Otros activos financieros", "AC.08"),
                       ("Otros pasivos financieros no corrientes", "PNC.05"),
                       ("Costos de distribución", "ER.04")]:
        matches = [row for row in entries if row["cuenta_original"].casefold() == name.casefold()]
        assert len(matches) == 1
        assert matches[0]["codigo_estandar"] == code
