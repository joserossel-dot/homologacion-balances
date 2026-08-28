import json

import pandas as pd
import pytest

from scripts.certify_local_corpus import (
    evaluate_gold_rows,
    evaluate_expectations,
    load_gold_rows,
    load_manifest,
    resolve_manifest_cases,
    write_gold_candidate,
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
        json.dumps({"cases": [{"file": "a.pdf"}, {"file": "a.pdf"}]}),
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
        json.dumps({"cases": [{"file": "a.pdf", "pages": [1, 3]}]}),
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


def test_manifest_rejects_gold_path_outside_matrix(tmp_path):
    manifest = tmp_path / "matrix.json"
    manifest.write_text(
        json.dumps({"cases": [{"file": "a.pdf", "gold_file": "../gold.xlsx"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Ruta Gold inválida"):
        load_manifest(manifest)
