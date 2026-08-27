import json

import pytest

from scripts.certify_local_corpus import (
    evaluate_expectations,
    load_manifest,
    resolve_manifest_cases,
)


def _result(*, valid=True, result=100, unclassified=0):
    return {
        "raw_accounts": 2,
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
