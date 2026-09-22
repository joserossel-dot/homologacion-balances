import json

import pandas as pd
import pytest

from scripts.certify_local_corpus import (
    _account_snapshot,
    _classify,
    _detected_dimensions,
    _has_execution_failure,
    build_corpus_measurement,
    certify,
    certify_isolated,
    evaluate_gold_rows,
    evaluate_expectations,
    load_gold_rows,
    load_manifest,
    resolve_manifest_cases,
    write_gold_candidate,
)
from parser_universal import CuentaRaw, OrigenColumna
from pipeline.homologation_pipeline import HomologationPipeline
from scripts.migrate_gold_workbook import (
    build_gold_review_package,
    migrate_gold_workbook,
)


def _result(*, valid=True, result=100, unclassified=0):
    return {
        "file": "ejemplo.pdf",
        "sha256": "a" * 64,
        "raw_accounts": 2,
        "qualified_accounts": 1,
        "detected_periods": ["2024", "2023"],
        "detected_currencies": ["CLP"],
        "certification": {
            "state": "certificada" if valid else "fallida",
            "final_totals_valid": valid,
            "result": result,
            "inconsistent_rows": [] if valid else [19],
            "inconsistent_accounts": [] if valid else [
                {"line": 19, "name": "IMPTOS POR PAGAR"}
            ],
        },
        "classification": {
            "unclassified": unclassified,
            "rows": [
                {
                    "account_code": "2301001",
                    "name": "Capital Social",
                    "amount": 1500,
                }
            ],
        },
        "accounts": [
            {
                "line": 1,
                "account_code": "2301001",
                "name": "Capital Social",
                "accounting_hierarchy": "Patrimonio",
                "origin": "pasivo",
                "amount": 1500,
                "period_amounts": {"2024": 1500, "2023": 1400},
                "column_amounts": {"pasivo": 1500},
                "standard_code": "PAT.01",
                "classification_method": "dictionary_exact",
                "requires_review": False,
                "is_total": False,
                "confidence": 1.0,
                "derived_columns": [],
            }
        ],
    }


def test_certify_keeps_account_snapshot_under_accounts_schema_key(monkeypatch, tmp_path):
    """El contrato público usa ``accounts``; no admite una clave alternativa.

    Evita que un consumidor de la certificación confunda el nombre del campo
    con una implementación interna y concluya que cuentas presentes faltan.
    """
    account = CuentaRaw(
        linea=1,
        codigo="110101",
        nombre="Caja",
        monto=100.0,
        origen_columna=OrigenColumna.ACTIVO,
        montos_columnas={"activo": 100.0},
    )
    monkeypatch.setattr(
        "scripts.certify_local_corpus._parse",
        lambda _path: ([account], None, [], False, 0, ["2024"], ["CLP"], []),
    )
    document = tmp_path / "esquema.pdf"
    document.write_bytes(b"fixture de contrato")

    result = certify(document, HomologationPipeline(db_path=tmp_path / "schema.db"))

    # 1. Clave estable obligatoria
    assert "accounts" in result, "El contrato público de certify() debe incluir la clave 'accounts'"
    assert "accounts_snapshot" not in result, "No debe aparecer la clave alternativa incompatible 'accounts_snapshot'"

    # 2. Tipo de dato estricto
    assert isinstance(result["accounts"], list), "El tipo de 'accounts' debe ser estrictamente list"
    assert len(result["accounts"]) == 1

    # 3. Campos mínimos por cuenta y tipos de datos
    acc = result["accounts"][0]
    assert isinstance(acc, dict), "Cada elemento de 'accounts' debe ser un dict"

    campos_minimos = {"line", "name", "requires_review"}
    assert campos_minimos <= set(acc), f"Faltan campos mínimos en la cuenta: {campos_minimos - set(acc)}"

    # 4. Verificación de tipos de campos obligatorios
    assert isinstance(acc["line"], int)
    assert isinstance(acc["name"], str)
    assert isinstance(acc["requires_review"], bool)
    assert isinstance(acc["account_code"], str)
    assert isinstance(acc["accounting_hierarchy"], str)
    assert isinstance(acc["origin"], str)
    assert isinstance(acc["amount"], (int, float))
    assert isinstance(acc["is_total"], bool)
    assert isinstance(acc["confidence"], (int, float))
    assert isinstance(acc["column_amounts"], dict)
    assert isinstance(acc["period_amounts"], dict)
    assert isinstance(acc["derived_columns"], list)
    assert isinstance(acc["extraction_review_reasons"], list)
    assert isinstance(acc["standard_code"], str)
    assert isinstance(acc["classification_method"], str)


def test_certify_contract_fails_when_accounts_key_missing_or_renamed():
    """Valida que los consumidores y verificadores fallen si 'accounts' falta o se renombra."""
    def validar_contrato_certify(payload: dict) -> None:
        if "accounts" not in payload:
            raise KeyError("Falta la clave obligatoria 'accounts'")
        if "accounts_snapshot" in payload:
            raise KeyError("Clave prohibida 'accounts_snapshot' detectada")
        if not isinstance(payload["accounts"], list):
            raise TypeError("La clave 'accounts' debe ser una lista")
        for acc in payload["accounts"]:
            if not isinstance(acc, dict):
                raise TypeError("Cada cuenta debe ser un diccionario")
            for campo in ("line", "name", "requires_review"):
                if campo not in acc:
                    raise KeyError(f"Falta el campo mínimo '{campo}' en la cuenta")

    # Caso 1: Falta 'accounts'
    with pytest.raises(KeyError, match="Falta la clave obligatoria 'accounts'"):
        validar_contrato_certify({"status": "ok", "raw_accounts": 1})

    # Caso 2: Clave incompatible 'accounts_snapshot'
    with pytest.raises(KeyError, match="Clave prohibida 'accounts_snapshot' detectada"):
        validar_contrato_certify({"accounts": [], "accounts_snapshot": []})

    # Caso 3: Tipo de datos incorrecto para 'accounts'
    with pytest.raises(TypeError, match="La clave 'accounts' debe ser una lista"):
        validar_contrato_certify({"accounts": {"1": "Caja"}})

    # Caso 4: Faltan campos mínimos en un elemento de 'accounts'
    with pytest.raises(KeyError, match="Falta el campo mínimo 'requires_review'"):
        validar_contrato_certify({"accounts": [{"line": 1, "name": "Caja"}]})

    with pytest.raises(KeyError, match="Falta el campo mínimo 'name'"):
        validar_contrato_certify({"accounts": [{"line": 1, "requires_review": False}]})

    with pytest.raises(KeyError, match="Falta el campo mínimo 'line'"):
        validar_contrato_certify({"accounts": [{"name": "Caja", "requires_review": False}]})


def test_certify_accounts_contract_multiple_account_types(monkeypatch, tmp_path):
    """Verifica el contrato con cuentas de detalle, totales, saldos cero y sospechosas."""
    c_detalle = CuentaRaw(linea=1, codigo="1101", nombre="Caja", monto=5000.0, origen_columna=OrigenColumna.ACTIVO)
    c_cero = CuentaRaw(linea=2, codigo="1102", nombre="Fondo Fijo", monto=0.0, origen_columna=OrigenColumna.ACTIVO)
    c_total = CuentaRaw(linea=3, codigo=None, nombre="TOTAL ACTIVO", monto=5000.0, es_total=True)
    c_sospechosa = CuentaRaw(
        linea=4, codigo=None, nombre="Caja 1000 Proveedores", monto=1000.0,
        requiere_revision_extraccion=True, razones_revision_extraccion=["multiples_glosas_separadas_por_monto"],
    )

    accounts = [c_detalle, c_cero, c_total, c_sospechosa]
    monkeypatch.setattr(
        "scripts.certify_local_corpus._parse",
        lambda _path: (accounts, None, [], False, 0, ["2024"], ["CLP"], []),
    )
    document = tmp_path / "multi_accounts.pdf"
    document.write_bytes(b"fixture multi accounts")

    result = certify(document, HomologationPipeline(db_path=tmp_path / "schema.db"))

    assert "accounts" in result
    assert len(result["accounts"]) == 4

    for acc in result["accounts"]:
        assert {"line", "name", "requires_review"} <= set(acc)
        assert isinstance(acc["line"], int)
        assert isinstance(acc["name"], str)
        assert isinstance(acc["requires_review"], bool)

    # Detalle clasificado o pendiente
    assert result["accounts"][0]["line"] == 1
    assert result["accounts"][0]["is_total"] is False

    # Saldo cero
    assert result["accounts"][1]["line"] == 2
    assert result["accounts"][1]["amount"] == 0.0

    # Total de control
    assert result["accounts"][2]["line"] == 3
    assert result["accounts"][2]["is_total"] is True
    assert result["accounts"][2]["requires_review"] is False

    # Sospechosa exige revisión
    assert result["accounts"][3]["line"] == 4
    assert result["accounts"][3]["requires_review"] is True
    assert "multiples_glosas_separadas_por_monto" in result["accounts"][3]["extraction_review_reasons"]


def test_expectations_validate_totals_result_and_account():
    checks, passed = evaluate_expectations(
        _result(),
        {
            "final_totals_valid": True,
            "result": 100,
            "min_raw_accounts": 2,
            "max_unclassified": 0,
            "max_inconsistent_rows": 0,
            "inconsistent_account_names": [],
            "sha256": "a" * 64,
            "exact_raw_accounts": 2,
            "exact_qualified_accounts": 1,
            "periods": ["2023", "2024"],
            "currencies": ["CLP"],
            "accounts": [
                {
                    "account_code": "2301001",
                    "name_contains": "capital",
                    "amount": 1500,
                }
            ],
        },
    )
    assert passed
    assert checks
    assert all(check["passed"] for check in checks)


def test_document_dimensions_survive_when_accounts_have_no_period_map():
    account = CuentaRaw(
        linea=1,
        codigo="110101",
        nombre="Caja",
        monto=100,
        origen_columna=OrigenColumna.ACTIVO,
        montos_columnas={"activo": 100},
    )

    periods, currencies = _detected_dimensions(
        [account], ["2024"], ["CLP"],
    )

    assert periods == ["2024"]
    assert currencies == ["CLP"]


def test_document_dimensions_trust_header_hints_and_limit_to_two_periods():
    account = CuentaRaw(
        linea=1, codigo="110101", nombre="Caja", monto=100,
        origen_columna=OrigenColumna.ACTIVO,
        montos_periodos={"2010": 5, "2022": 80, "2023": 100},
    )

    periods, _ = _detected_dimensions(
        [account], ["2024", "2023", "2010"], [],
    )

    assert periods == ["2024", "2023"]


def test_expectations_expose_release_failure():
    checks, passed = evaluate_expectations(
        _result(valid=False, result=99, unclassified=1),
        {
            "final_totals_valid": True,
            "result": 100,
            "max_unclassified": 0,
            "max_inconsistent_rows": 0,
            "inconsistent_account_names": [],
        },
    )
    assert not passed
    assert {check["name"] for check in checks if not check["passed"]} == {
        "final_totals_valid",
        "result",
        "max_unclassified",
        "max_inconsistent_rows",
        "inconsistent_account_names",
    }


def test_expectations_never_hide_failed_certification():
    checks, passed = evaluate_expectations(
        _result(valid=False),
        {"certification_must_not_fail": True},
    )

    assert not passed
    check = next(
        row for row in checks
        if row["name"] == "certification_must_not_fail"
    )
    assert check == {
        "name": "certification_must_not_fail",
        "actual": "fallida",
        "expected": True,
        "passed": False,
    }


def test_timeout_y_falla_contable_quedan_separados_en_medicion():
    measurement = build_corpus_measurement([
        {
            "file": "timeout.pdf", "status": "timeout",
            "certification": {"state": "timeout"},
            "family_metrics": {"family": "not_processed"},
        },
        {
            "file": "fallida.pdf", "status": "ok",
            "certification": {"state": "fallida"},
            "family_metrics": {"family": "escaneado_ocr"},
        },
        {
            "file": "pendiente.pdf", "status": "not_processed",
            "certification": None,
        },
    ])

    assert measurement["timeout_documents"] == 1
    assert measurement["not_processed_documents"] == 1
    assert measurement["failed_certification_documents"] == 1
    assert measurement["status_counts"] == {
        "not_processed": 1, "ok": 1, "timeout": 1,
    }
    assert _has_execution_failure([
        {"status": "ok"}, {"status": "timeout"},
    ])


def test_certificacion_aislada_termina_worker_al_exceder_presupuesto(
    monkeypatch, tmp_path,
):
    class FakeProcess:
        exitcode = None

        def __init__(self):
            self.alive = True
            self.terminated = False

        def start(self):
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True
            self.alive = False

    process = FakeProcess()

    class FakeContext:
        @staticmethod
        def Process(**kwargs):
            return process

    monkeypatch.setattr(
        "scripts.certify_local_corpus.multiprocessing.get_context",
        lambda method: FakeContext(),
    )

    result = certify_isolated(
        tmp_path / "lento.pdf", timeout_seconds=1, exchange_dir=tmp_path,
    )

    assert process.terminated is True
    assert result["status"] == "timeout"
    assert result["processing_state"] == "timed_out"
    assert result["certification"]["state"] == "timeout"
    assert result["certification"]["final_totals_valid"] is None
    assert result["accounts"] == []


@pytest.mark.parametrize("state", ["parcial", "no_evaluable", "timeout", None])
def test_required_certification_rejects_non_certified_states(state):
    result = _result()
    result["certification"]["state"] = state

    checks, passed = evaluate_expectations(
        result, {"certification_must_not_fail": True},
    )

    assert not passed
    assert checks[0]["passed"] is False


def test_final_totals_none_does_not_prove_true_even_when_state_is_certified():
    result = _result()
    result["certification"]["final_totals_valid"] = None

    checks, passed = evaluate_expectations(
        result, {"final_totals_valid": True},
    )

    assert not passed
    assert checks[0]["actual"] is None


def test_expectations_accept_declared_human_review_row():
    checks, passed = evaluate_expectations(
        _result(valid=False),
        {
            "final_totals_valid": True,
            "max_inconsistent_rows": 1,
            "inconsistent_account_names": ["imptos por pagar"],
        },
    )

    assert not passed  # el total final del ejemplo sigue siendo inválido
    by_name = {check["name"]: check for check in checks}
    assert by_name["max_inconsistent_rows"]["passed"]
    assert by_name["inconsistent_account_names"]["passed"]


def test_manifest_rejects_duplicate_files(tmp_path):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [
            {
                "file": "a.pdf",
                "expect": {"certification_must_not_fail": True},
            },
            {
                "file": "a.pdf",
                "expect": {"certification_must_not_fail": True},
            },
        ]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicados"):
        load_manifest(manifest)


def test_manifest_resolves_unique_document_and_pages(tmp_path):
    source = tmp_path / "sub" / "a.pdf"
    source.parent.mkdir()
    source.write_bytes(b"not parsed in this unit test")
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{
            "file": "a.pdf",
            "pages": [1, 3],
            "expect": {"certification_must_not_fail": True},
        }]}),
        encoding="utf-8",
    )
    cases = load_manifest(manifest)
    assert resolve_manifest_cases(tmp_path, cases) == [(source, cases[0])]


def test_gold_rows_compare_every_account_field():
    result = _result()
    expected = [dict(result["accounts"][0])]
    checks = evaluate_gold_rows(result["accounts"], expected)
    assert all(check["passed"] for check in checks)

    expected[0]["period_amounts"] = {"2024": 1501, "2023": 1400}
    checks = evaluate_gold_rows(result["accounts"], expected)
    mismatch = next(
        check for check in checks if check["name"] == "gold_mismatched_rows"
    )
    assert not mismatch["passed"]
    assert "period_amounts" in mismatch["actual"][0]["differences"]


def test_classifier_reproduces_hierarchy_context_used_by_ui(tmp_path):
    accounts = [
        CuentaRaw(
            linea=1,
            codigo="1101201",
            nombre="BANCOESTADO 1",
            monto=60,
            origen_columna=OrigenColumna.ACTIVO,
            montos_columnas={
                "debe": 60, "saldo_deudor": 60, "activo": 60,
            },
            jerarquia_contable="BANCOS",
        ),
        CuentaRaw(
            linea=2,
            codigo="1201201",
            nombre="DEPRECIACIONES",
            monto=25,
            origen_columna=OrigenColumna.PASIVO,
            montos_columnas={
                "haber": 25, "saldo_acreedor": 25, "pasivo": 25,
            },
            jerarquia_contable="DEPRECIACIÓN ACUMULADA",
        ),
    ]
    classified = _classify(
        accounts, HomologationPipeline(db_path=tmp_path / "gold.db"),
    )
    by_name = {row["name"]: row for row in classified["rows"]}

    assert by_name["BANCOESTADO 1"]["code"] == "AC.01"
    assert by_name["BANCOESTADO 1"]["method"] == "hierarchy_inheritance"
    assert by_name["DEPRECIACIONES"]["code"] == "ANC.01.01"
    assert by_name["DEPRECIACIONES"]["method"] == "hierarchy_inheritance"


def test_gold_snapshot_marks_filtered_unclassified_row_for_review():
    account = CuentaRaw(
        linea=104,
        codigo="3204006",
        nombre="CORREO",
        monto=109371,
        origen_columna=OrigenColumna.PERDIDA,
        montos_columnas={"perdida": 109371},
        jerarquia_contable="3204 - SERVICIOS BASICOS",
    )

    snapshot = _account_snapshot([account], {"rows": []})

    assert snapshot[0]["standard_code"] == ""
    assert snapshot[0]["requires_review"] is True


def test_gold_snapshot_does_not_require_classification_for_control_without_code():
    control = CuentaRaw(
        linea=171,
        codigo="",
        nombre="Sumas",
        monto=1231044771,
        origen_columna=OrigenColumna.ACTIVO,
        montos_columnas={"activo": 1231044771},
        es_total=True,
    )

    snapshot = _account_snapshot([control], {"rows": []})

    assert snapshot[0]["is_total"] is True
    assert snapshot[0]["standard_code"] == ""
    assert snapshot[0]["requires_review"] is False


def test_gold_rows_detect_duplicate_occurrence():
    result = _result()
    duplicate = dict(result["accounts"][0])
    checks = evaluate_gold_rows(
        [result["accounts"][0], duplicate],
        [result["accounts"][0]],
    )
    extra = next(check for check in checks if check["name"] == "gold_extra_rows")
    assert not extra["passed"]
    assert extra["actual"][0][-1] == 2


def test_gold_rows_treat_line_number_as_traceability_not_identity():
    result = _result()
    expected = [dict(result["accounts"][0], line=999)]

    checks = evaluate_gold_rows(result["accounts"], expected)

    assert all(check["passed"] for check in checks)


def test_gold_candidate_requires_explicit_approval(tmp_path):
    result = _result()
    result.update({
        "selected_pages": [1, 2],
        "warnings": [],
        "expectation_checks": [],
    })
    candidate = write_gold_candidate(result, tmp_path)
    with pytest.raises(
        ValueError,
        match="sin Estado_revision=APROBADO o EXCLUIR",
    ):
        load_gold_rows(candidate)

    frame = pd.read_excel(candidate, sheet_name="Cuentas")
    frame["Estado_revision"] = "APROBADO"
    with pd.ExcelWriter(candidate, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        frame.to_excel(writer, sheet_name="Cuentas", index=False)
    loaded = load_gold_rows(candidate)
    assert loaded[0]["name"] == "Capital Social"
    assert loaded[0]["accounting_hierarchy"] == "Patrimonio"
    assert loaded[0]["classification_method"] == "dictionary_exact"
    assert loaded[0]["confidence"] == 1.0
    assert loaded[0]["derived_columns"] == []
    assert loaded[0]["period_amounts"] == {"2023": 1400, "2024": 1500}


def test_gold_candidate_exclusion_makes_parser_noise_visible(tmp_path):
    result = _result()
    result.update({
        "selected_pages": [1, 2],
        "warnings": [],
        "expectation_checks": [],
    })
    candidate = write_gold_candidate(result, tmp_path)
    frame = pd.read_excel(candidate, sheet_name="Cuentas")
    frame["Estado_revision"] = "EXCLUIR"
    with pd.ExcelWriter(
        candidate, engine="openpyxl", mode="a", if_sheet_exists="replace",
    ) as writer:
        frame.to_excel(writer, sheet_name="Cuentas", index=False)

    expected = load_gold_rows(candidate)
    assert expected == []
    checks = evaluate_gold_rows(result["accounts"], expected)
    extra = next(check for check in checks if check["name"] == "gold_extra_rows")
    assert not extra["passed"]
    assert extra["actual"]


def test_gold_migration_requires_review_for_new_protected_metadata(tmp_path):
    result = _result()
    result.update({"selected_pages": [1], "warnings": [], "expectation_checks": []})
    candidate = write_gold_candidate(result, tmp_path / "candidate")
    legacy = tmp_path / "legacy.xlsx"
    frame = pd.read_excel(candidate, sheet_name="Cuentas")
    frame["Estado_revision"] = "APROBADO"
    frame = frame.drop(columns=["Jerarquia_contable"])
    summary = pd.read_excel(candidate, sheet_name="Resumen").drop(
        columns=["Gold_schema_version"],
    )
    with pd.ExcelWriter(legacy, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        frame.to_excel(writer, sheet_name="Cuentas", index=False)

    migrated = migrate_gold_workbook(
        legacy, candidate, tmp_path / "migrated.xlsx",
    )
    migrated_frame = pd.read_excel(migrated, sheet_name="Cuentas")
    migrated_summary = pd.read_excel(migrated, sheet_name="Resumen")

    assert migrated_summary.iloc[0]["Gold_schema_version"] == 2
    assert migrated_frame.iloc[0]["Estado_revision"] == "CORREGIR"
    assert "Jerarquia_contable" in migrated_frame.iloc[0]["Observacion_analista"]


def test_review_package_groups_differences_without_approving(tmp_path):
    report = tmp_path / "gold-report.json"
    report.write_text(json.dumps([{
        "file": "auditado.pdf",
        "selected_pages": [5, 6],
        "certification": {"state": "parcial"},
        "expectations_passed": False,
        "gold_candidate": "/private/auditado.gold-candidate.xlsx",
        "expectation_checks": [
            {
                "name": "allowed_certification_states", "passed": False,
                "actual": "parcial", "expected": ["certificada"],
            },
            {
                "name": "gold_mismatched_rows", "passed": False,
                "actual": [{
                    "key": ["", "caja", 1],
                    "actual_line": 12,
                    "expected_line": 10,
                    "differences": {
                        "accounting_hierarchy": ["Activo > Caja", ""],
                        "amount": [101, 100],
                    },
                }],
                "expected": [],
            },
        ],
    }]), encoding="utf-8")

    package = build_gold_review_package(report, tmp_path / "review")

    assert package["summary"]["release_blocked"] is True
    assert package["summary"]["differences"] == 2
    assert package["summary"]["autofillable_without_ambiguity"] == 1
    assert {row["review_state"] for row in package["differences"]} == {"CORREGIR"}
    hierarchy = next(
        row for row in package["differences"]
        if row["field"] == "accounting_hierarchy"
    )
    assert hierarchy["proposed_value"] == "Activo > Caja"
    assert hierarchy["actual_line"] == 12
    assert hierarchy["expected_line"] == 10
    assert (tmp_path / "review" / "CHECKLIST.md").exists()
    assert (tmp_path / "review" / "revision_gold_schema2.xlsx").exists()


def test_manifest_rejects_gold_path_outside_matrix(tmp_path):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{
            "file": "a.pdf",
            "gold_file": "../gold.xlsx",
            "gold_schema_version": 2,
            "expect": {"certification_must_not_fail": True},
        }]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Ruta Gold inválida"):
        load_manifest(manifest)


def test_manifest_requires_explicit_certification_expectation(tmp_path):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{
            "file": "a.pdf",
            "required_for_release": True,
            "expect": {"max_unclassified": 0},
        }]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="certification_state"):
        load_manifest(manifest)


@pytest.mark.parametrize("state", ["parcial", "no_evaluable", "fallida"])
def test_manifest_forbids_non_certified_required_state(tmp_path, state):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{
            "file": "a.pdf",
            "required_for_release": True,
            "expect": {"certification_state": state},
        }]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sólo puede aceptar"):
        load_manifest(manifest)


def test_gold_schema_two_compares_hierarchy_method_confidence_and_derived():
    actual = _result()["accounts"]
    expected = [dict(actual[0], _gold_schema_version=2)]
    expected[0]["accounting_hierarchy"] = "Otra jerarquía"
    expected[0]["classification_method"] = "manual"
    expected[0]["confidence"] = 0.5
    expected[0]["derived_columns"] = ["activo"]

    checks = evaluate_gold_rows(actual, expected)
    mismatches = next(row for row in checks if row["name"] == "gold_mismatched_rows")

    assert not mismatches["passed"]
    fields = mismatches["actual"][0]["differences"]
    assert set(fields) >= {
        "accounting_hierarchy", "classification_method", "confidence",
        "derived_columns",
    }


def test_classify_omits_recognized_total(tmp_path):
    total = CuentaRaw(
        linea=99, codigo=None, nombre="Total activos", monto=100,
        origen_columna=OrigenColumna.ACTIVO, es_total=True,
        montos_columnas={"activo": 100},
    )

    result = _classify(
        [total], HomologationPipeline(db_path=tmp_path / "totals.db"),
    )

    assert result["eligible"] == 0
    assert result["rows"] == []


@pytest.mark.parametrize(
    "expectation",
    [
        {"certification_state": "fallida"},
        {"certification_must_not_fail": False},
    ],
)
def test_manifest_forbids_accepting_failed_certification(
    tmp_path, expectation,
):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{
            "file": "a.pdf",
            "required_for_release": True,
            "expect": expectation,
        }]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="sólo puede aceptar|debe exigir"):
        load_manifest(manifest)
