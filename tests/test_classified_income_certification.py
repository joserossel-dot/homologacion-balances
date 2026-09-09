import pytest

from parser_universal import CuentaRaw, certificar_clasificado_final


def statement(tax=-10):
    data = [
        ("Caja", 100, "Activo corriente", "AC.01"),
        ("Total activos corrientes", 100, None, None),
        ("Total activos", 100, None, None),
        ("Capital", 100, "Patrimonio", "PAT.01"),
        ("Patrimonio total", 100, None, None),
        ("Total patrimonio y pasivos", 100, None, None),
        ("Ingresos de actividades ordinarias", 200, None, "ER.01"),
        ("Costo de ventas", -100, None, "ER.02"),
        ("Ganancia bruta", 100, None, None),
        ("Gastos de administración", -30, None, "ER.04"),
        ("Ganancia (pérdida), antes de impuestos", 70, None, None),
        ("Gasto por impuestos a las ganancias", tax, None, "ER.10"),
        ("Ganancia (pérdida) procedente de operaciones continuadas", 70 + tax, None, None),
        ("Ganancia (pérdida) procedente de operaciones discontinuadas", 0, None, None),
        ("Ganancia (pérdida)", 70 + tax, None, None),
    ]
    accounts, rows = [], []
    for line, (name, amount, section, code) in enumerate(data):
        accounts.append(CuentaRaw(line, None, name, amount, es_total=code is None,
            seccion_contable=section, montos_periodos={"2024": amount, "2023": amount}))
        if code:
            rows.append(dict(line=line, name=name, amount=amount, code=code, review=False))
    return accounts, rows


def certify(accounts, rows):
    return certificar_clasificado_final(accounts, rows, ["2024", "2023"], ["CLP"],
        codigos_validos={"AC.01", "PAT.01", "ER.01", "ER.02", "ER.04", "ER.10"},
        periodo_actual="2024")


@pytest.mark.parametrize("tax", [-10, 10])
def test_signed_tax_and_subtotals_verified_without_double_counting(tax):
    accounts, rows = statement(tax)
    result = certify(accounts, rows)
    assert result.estado == "certificada"
    assert result.totales_calculados["2024:ER_NET"] == 70 + tax


def test_prior_income_error_cannot_hide_behind_balanced_balance_sheet():
    accounts, rows = statement()
    accounts[9].montos_periodos["2023"] = -31
    result = certify(accounts, rows)
    assert result.estado == "fallida"
    assert result.diferencias["2023:ecuacion"] == 0
    assert result.diferencias["2023:ER_NET"] == -1


def test_compensating_error_does_not_hide_wrong_gross_margin():
    accounts, rows = statement()
    accounts[7].montos_periodos["2023"] = -90
    accounts[9].montos_periodos["2023"] = -40
    result = certify(accounts, rows)
    assert result.estado == "fallida"
    assert result.diferencias["2023:ER_NET"] == 0
    assert result.diferencias["2023:ER_GROSS"] == 10


def test_missing_or_duplicate_income_controls_block():
    accounts, rows = statement()
    del accounts[8]
    assert certify(accounts, rows).estado == "parcial"
    accounts, rows = statement()
    accounts.append(CuentaRaw(99, None, "Ganancia (pérdida)", 60, es_total=True,
        montos_periodos={"2024": 60, "2023": 60}))
    assert certify(accounts, rows).estado == "parcial"


def test_comprehensive_income_accepts_equal_net_carry_forward_and_zero_oci():
    accounts, rows = statement()
    net = accounts[-1]
    accounts.extend([
        CuentaRaw(16, None, "Ganancia (pérdida)", net.monto, es_total=True,
            montos_periodos=dict(net.montos_periodos)),
        CuentaRaw(17, None, "Otro resultado integral", 0, es_total=False,
            montos_periodos={"2024": 0, "2023": 0}),
        CuentaRaw(18, None, "Total resultado integral", net.monto, es_total=True,
            montos_periodos=dict(net.montos_periodos)),
    ])

    result = certify(accounts, rows)

    assert result.estado == "certificada"
    assert result.diferencias["2024:ER_TCI_EQUATION"] == 0


def test_comprehensive_income_rejects_different_net_carry_forward():
    accounts, rows = statement()
    accounts.append(CuentaRaw(
        16, None, "Ganancia (pérdida)", 999, es_total=True,
        montos_periodos={"2024": 999, "2023": 999},
    ))

    assert certify(accounts, rows).estado == "parcial"


def test_nonzero_discontinued_result_needs_independent_detail():
    accounts, rows = statement()
    accounts[13].montos_periodos["2023"] = 5
    assert certify(accounts, rows).estado == "parcial"


def test_tax_before_pretax_control_not_certified():
    accounts, rows = statement()
    accounts[11].linea = 9.5
    rows[-1]["line"] = 9.5
    assert certify(accounts, rows).estado == "parcial"


def test_swapped_revenue_and_cost_codes_do_not_certify():
    accounts, rows = statement()
    rows[2]["code"], rows[3]["code"] = rows[3]["code"], rows[2]["code"]
    assert certify(accounts, rows).estado == "parcial"


@pytest.mark.parametrize("index", [12, 13])
def test_optional_controls_out_of_order_do_not_certify(index):
    accounts, rows = statement()
    accounts[index].linea = 0.5
    assert certify(accounts, rows).estado == "parcial"


def test_aggregate_overflow_does_not_certify():
    accounts, rows = statement()
    accounts[6].montos_periodos["2023"] = 1e308
    accounts[7].montos_periodos["2023"] = 1e308
    assert certify(accounts, rows).estado != "certificada"


def legacy_income_tree(printed=None):
    from validation.models import AccountNode, HierarchyTree
    nodes = [AccountNode(account_name="Ingresos", amount=200, naturaleza="INGRESOS"),
             AccountNode(account_name="Costo de ventas", amount=100, naturaleza="COSTOS"),
             AccountNode(account_name="Administración", amount=30, naturaleza="GASTOS")]
    if printed is not None:
        nodes.append(AccountNode(account_name="Ganancia (pérdida) del ejercicio",
                                 amount=printed, es_total=True))
    return HierarchyTree(all_nodes=nodes)


def test_legacy_income_without_printed_control_does_not_validate_itself():
    from validation.equation_validator import validate_balance_equation
    result = validate_balance_equation(legacy_income_tree())[0]
    assert result.passed is False
    assert result.left_components == {}
    assert "no verificable" in result.equation


@pytest.mark.parametrize("printed,passed,difference", [(70, True, 0), (90, False, 20)])
def test_legacy_income_compares_against_independent_printed_control(printed, passed, difference):
    from validation.equation_validator import validate_balance_equation
    result = validate_balance_equation(legacy_income_tree(printed))[0]
    assert result.passed is passed
    assert result.left_side == printed
    assert result.right_side == 70
    assert result.difference == difference


def test_legacy_duplicate_result_controls_do_not_choose_first():
    from validation.equation_validator import validate_balance_equation
    from validation.models import AccountNode
    tree = legacy_income_tree(70)
    tree.all_nodes.append(AccountNode(account_name="Resultado del ejercicio", amount=99, es_total=True))
    assert validate_balance_equation(tree)[0].passed is False


def test_legacy_subtotals_are_excluded_from_income_sum():
    from validation.equation_validator import validate_balance_equation
    from validation.models import AccountNode
    tree = legacy_income_tree(70)
    tree.all_nodes.append(AccountNode(account_name="Subtotal ingresos", amount=200,
                                     naturaleza="INGRESOS", es_subtotal=True))
    assert validate_balance_equation(tree)[0].passed is True


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -100])
def test_legacy_nonfinite_or_unaccredited_signed_details_do_not_pass(invalid):
    from validation.equation_validator import validate_balance_equation
    tree = legacy_income_tree(70)
    tree.all_nodes[1].amount = invalid
    assert validate_balance_equation(tree)[0].passed is False


@pytest.mark.parametrize("nature", ["RESULTADO", "GANANCIA", "PERDIDA", ""])
def test_unmapped_income_component_is_not_silently_omitted(nature):
    from validation.equation_validator import validate_balance_equation
    from validation.models import AccountNode
    tree = legacy_income_tree(70)
    tree.all_nodes.append(AccountNode(account_name="Impuesto a la renta", amount=40, naturaleza=nature))
    assert validate_balance_equation(tree)[0].passed is False


def test_real_hierarchy_tax_columns_do_not_receive_perfect_equation_score():
    from validation.hierarchy import build_hierarchy
    from validation.equation_validator import validate_balance_equation
    from validation.integrity_score import compute_equation_score
    tree = build_hierarchy([
        dict(nombre="Ventas", monto=100, origen_columna="GANANCIA"),
        dict(nombre="Arriendos", monto=30, origen_columna="PERDIDA"),
        dict(nombre="Utilidad del ejercicio", monto=99, es_total=True),
    ])
    results = validate_balance_equation(tree)
    assert results and all(not result.passed for result in results)
    assert compute_equation_score(results) == 0
    assert compute_equation_score([]) == 0


def test_loss_net_control_is_recognized_without_assuming_positive_loss_sign():
    from validation.equation_validator import validate_balance_equation
    tree = legacy_income_tree(-30)
    tree.all_nodes[0].amount = 100
    tree.all_nodes[-1].account_name = "Pérdida del ejercicio"
    result = validate_balance_equation(tree)[0]
    assert result.passed is True
    assert result.left_side == result.right_side == -30


def test_intermediate_loss_control_does_not_replace_net_result():
    from validation.equation_validator import validate_balance_equation
    tree = legacy_income_tree(70)
    tree.all_nodes[-1].account_name = "Pérdida antes de impuestos"
    assert validate_balance_equation(tree)[0].passed is False


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_all_equation_results_are_strict_json_serializable(bad):
    import json
    from dataclasses import asdict
    from validation.equation_validator import validate_balance_equation
    from validation.models import AccountNode
    tree = legacy_income_tree(70)
    tree.all_nodes[1].amount = bad
    tree.all_nodes.extend([
        AccountNode(account_name="Activo", amount=float("inf"), naturaleza="ACTIVO"),
        AccountNode(account_name="Pasivo", amount=10, naturaleza="PASIVO"),
    ])
    results = validate_balance_equation(tree)
    assert all(not result.passed for result in results)
    json.dumps([asdict(result) for result in results], allow_nan=False)
