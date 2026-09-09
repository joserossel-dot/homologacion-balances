"""Final certification cannot be obtained from global printed totals alone."""
import copy

from parser_universal import CuentaRaw, certificar_clasificado_final


def case():
    accounts = []
    for i, (name, amount, section, total) in enumerate([
        ("Caja", 100, "Activo corriente", False),
        ("Total activos corrientes", 100, None, True),
        ("Total activos", 100, None, True),
        ("Capital", 100, "Patrimonio", False),
        ("Total patrimonio", 100, None, True),
        ("Total patrimonio y pasivos", 100, None, True),
    ]):
        accounts.append(CuentaRaw(i, None, name, amount, es_total=total,
            seccion_contable=section, montos_periodos={"2024": amount, "2023": amount}))
    classifications = [
        {"line": 0, "name": "Caja", "amount": 100, "code": "AC.01", "review": False},
        {"line": 3, "name": "Capital", "amount": 100, "code": "PAT.01", "review": False},
    ]
    return accounts, classifications


def certify(accounts, rows):
    return certificar_clasificado_final(accounts, rows, ["2024", "2023"], ["CLP"],
        codigos_validos={"AC.01", "AC.02", "PC.01", "PAT.01"}, periodo_actual="2024")


def test_complete_two_period_detail_certifies():
    accounts, rows = case()
    result = certify(accounts, rows)
    assert result.estado == "certificada"
    assert result.diferencias["2023:ecuacion"] == 0


def test_balanced_printed_totals_do_not_hide_wrong_prior_detail():
    accounts, rows = case()
    accounts[0].montos_periodos["2023"] = 99
    assert certify(accounts, rows).estado == "fallida"


def test_missing_year_is_not_zero():
    accounts, rows = case()
    del accounts[0].montos_periodos["2023"]
    assert certify(accounts, rows).estado == "parcial"


def test_no_pending_classification_does_not_prove_sections():
    accounts, rows = case()
    accounts[0].seccion_contable = None
    assert certify(accounts, rows).estado != "certificada"


def test_missing_subtotal_remains_partial():
    accounts, rows = case()
    del accounts[1]
    assert certify(accounts, rows).estado == "parcial"


def test_wrong_classification_or_review_blocks():
    for field, value in [("code", "PC.01"), ("review", True), ("amount", 99)]:
        accounts, rows = case()
        rows[0][field] = value
        assert certify(accounts, rows).estado == "parcial"


def test_duplicate_and_extra_decisions_block():
    accounts, rows = case()
    rows.append(copy.deepcopy(rows[0]))
    assert certify(accounts, rows).estado == "parcial"
    rows[-1]["line"] = 88
    assert certify(accounts, rows).estado == "parcial"


def test_unverified_extraction_and_unknown_controls_block():
    accounts, rows = case()
    accounts[0].confianza_extraccion = 0.75
    assert certify(accounts, rows).estado == "parcial"
    accounts[0].confianza_extraccion = 1
    accounts.append(CuentaRaw(9, None, "Ganancia bruta", 0, es_total=True))
    assert certify(accounts, rows).estado == "parcial"


def test_native_fragment_reconstruction_certifies_only_after_all_controls_match():
    accounts, rows = case()
    for account in accounts:
        account.confianza_extraccion = 0.75

    result = certificar_clasificado_final(
        accounts, rows, ["2024", "2023"], ["CLP"],
        codigos_validos={"AC.01", "AC.02", "PC.01", "PAT.01"},
        periodo_actual="2024",
        metodo_extraccion_fuente="native_fragment_reconstruction",
    )

    assert result.estado == "certificada"
    assert result.totales_finales_validos is True
    assert "Texto nativo fragmentado acreditado" in result.razones[0]


def test_native_fragment_attestation_never_hides_monetary_difference():
    accounts, rows = case()
    for account in accounts:
        account.confianza_extraccion = 0.75
    accounts[0].montos_periodos["2023"] = 99

    result = certificar_clasificado_final(
        accounts, rows, ["2024", "2023"], ["CLP"],
        codigos_validos={"AC.01", "AC.02", "PC.01", "PAT.01"},
        periodo_actual="2024",
        metodo_extraccion_fuente="native_fragment_reconstruction",
    )

    assert result.estado == "fallida"
    assert result.diferencias["2023:ecuacion"] == -1


def test_ocr_low_confidence_cannot_use_native_fragment_attestation():
    accounts, rows = case()
    for account in accounts:
        account.confianza_extraccion = 0.75

    result = certificar_clasificado_final(
        accounts, rows, ["2024", "2023"], ["CLP"],
        codigos_validos={"AC.01", "AC.02", "PC.01", "PAT.01"},
        periodo_actual="2024",
        metodo_extraccion_fuente="ocr_coordinates_8_amounts",
    )

    assert result.estado == "parcial"


def test_nonfinite_values_and_unknown_currency_block():
    accounts, rows = case()
    accounts[0].montos_periodos["2023"] = float("nan")
    assert certify(accounts, rows).estado == "parcial"
    assert certificar_clasificado_final(accounts, rows, ["2024"], []).estado == "parcial"


def test_unknown_catalog_code_and_divergent_principal_block():
    accounts, rows = case()
    rows[0]["code"] = "AC.NO_EXISTE"
    assert certify(accounts, rows).estado == "parcial"
    rows[0]["code"] = "AC.01"
    accounts[0].monto = rows[0]["amount"] = 999
    assert certify(accounts, rows).estado == "parcial"


def test_empty_currency_blocks_even_with_complete_other_evidence():
    accounts, rows = case()
    assert certificar_clasificado_final(accounts, rows, ["2024"], [""],
        codigos_validos={"AC.01", "PAT.01"}, periodo_actual="2024").estado == "parcial"
