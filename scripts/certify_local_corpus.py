"""Certifica extracción y clasificación sobre un corpus local ignorado por Git."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

# El entorno de desarrollo puede tener otra copia del proyecto instalada en
# modo editable. La certificación debe importar exactamente el árbol donde se
# encuentra este script para que la versión medida sea inequívoca.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from dotenv import load_dotenv

from account_qualification import qualify_cuentas
from adapters.account_adapter import AccountAdapter
from app_validacion import (
    PATRON_NO_CUENTA,
    UMBRAL_REVISION,
    _codigo_compatible_con_origen,
    _es_contra_activo,
    _es_partida_patrimonial,
    _origen_efectivo,
    _resolver_tipo_cuenta,
)
from interpreters.balance_interpreter import BalanceInterpreter
from parser_universal import (
    ParserPDF, certificar_extraccion_columnas, parsear_excel,
)
from pipeline.homologation_pipeline import HomologationPipeline
from document_scope import select_pdf


def _serializable(value):
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _parse(path: Path):
    if path.suffix.lower() in {".xlsx", ".xls"}:
        accounts = parsear_excel(path)
        certification = certificar_extraccion_columnas(
            accounts, metodo="excel_8_columns",
        )
        return accounts, certification, [], False, 0
    result = ParserPDF().parsear(path)
    return (
        result.cuentas,
        result.certificacion_extraccion,
        result.advertencias,
        result.requirio_ocr,
        result.rotacion_aplicada,
    )


def _classify(accounts, pipeline: HomologationPipeline) -> dict:
    rows = []
    for account in accounts:
        if account.monto is None and not account.codigo:
            continue
        if account.monto is not None and float(account.monto) == 0:
            continue
        if not account.codigo and PATRON_NO_CUENTA.match(account.nombre.strip()):
            continue
        adapted = AccountAdapter.from_cuenta_raw(account)
        amount = BalanceInterpreter(adapted).classification_amount
        if amount is None:
            continue
        effective_origin = _origen_efectivo(
            account.origen_columna, amount, account.nombre,
        )
        account_type = _resolver_tipo_cuenta(effective_origin, account.codigo)
        if effective_origin == "pasivo" and _es_contra_activo(account.nombre):
            account_type = "ACTIVO"
        if _es_partida_patrimonial(account.nombre):
            account_type = "PATRIMONIO"
        started = time.perf_counter()
        classification = pipeline._classify_account(
            adapted.account_code, adapted.account_name,
            account_tipo=account_type,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        adjustment = pipeline._rule_processor.aplicar(
            nombre_cuenta=adapted.account_name,
            codigo_clasificado=classification.get("standard_code") or "",
            monto=amount,
            origen_columna=account.origen_columna,
        )
        final_code = (
            adjustment.codigo_final if adjustment.aplica
            else classification.get("standard_code")
        )
        compatible = bool(
            final_code
            and _codigo_compatible_con_origen(
                final_code, account.origen_columna, amount, account.nombre,
            )
        )
        if final_code and not compatible:
            final_code = None
        confidence = float(classification.get("confidence") or 0.0)
        review = (
            not final_code
            or confidence < UMBRAL_REVISION
            or bool(adjustment.aplica and adjustment.requiere_revision)
            or bool(account.columnas_derivadas)
        )
        rows.append({
            "line": account.linea,
            "account_code": adapted.account_code,
            "name": account.nombre,
            "origin": _serializable(account.origen_columna),
            "amount": amount,
            "code": final_code or "",
            "method": classification.get("method", ""),
            "confidence": confidence,
            "review": review,
            "classification_ms": round(elapsed_ms, 3),
        })
    methods = Counter(row["method"] for row in rows)
    return {
        "eligible": len(rows),
        "classified": sum(bool(row["code"]) for row in rows),
        "automatic": sum(bool(row["code"]) and not row["review"] for row in rows),
        "review": sum(row["review"] for row in rows),
        "unclassified": sum(not row["code"] for row in rows),
        "methods": dict(methods.most_common()),
        "classification_seconds": round(
            sum(row["classification_ms"] for row in rows) / 1000, 3
        ),
        "rows": rows,
    }


def evaluate_expectations(result: dict, expectations: dict) -> tuple[list[dict], bool]:
    """Compara el resultado con criterios declarados, sin ocultar fallos conocidos."""
    checks: list[dict] = []

    def add(name: str, actual, expected, passed: bool) -> None:
        checks.append({
            "name": name,
            "actual": actual,
            "expected": expected,
            "passed": bool(passed),
        })

    certification = result.get("certification") or {}
    classification = result.get("classification") or {}
    if "final_totals_valid" in expectations:
        actual = bool(
            certification.get("state") == "certificada"
            or certification.get("final_totals_valid")
        )
        expected = bool(expectations["final_totals_valid"])
        add("final_totals_valid", actual, expected, actual is expected)
    if "certification_state" in expectations:
        actual = certification.get("state")
        expected = expectations["certification_state"]
        add("certification_state", actual, expected, actual == expected)
    if "result" in expectations:
        actual = certification.get("result")
        expected = expectations["result"]
        tolerance = float(expectations.get("result_tolerance", 0))
        passed = (
            actual is not None
            and abs(float(actual) - float(expected)) <= tolerance
        )
        add("result", actual, expected, passed)
    if "min_raw_accounts" in expectations:
        actual = int(result.get("raw_accounts") or 0)
        expected = int(expectations["min_raw_accounts"])
        add("min_raw_accounts", actual, expected, actual >= expected)
    if "max_unclassified" in expectations:
        actual = int(classification.get("unclassified") or 0)
        expected = int(expectations["max_unclassified"])
        add("max_unclassified", actual, expected, actual <= expected)
    if "max_inconsistent_rows" in expectations:
        actual = len(certification.get("inconsistent_rows") or [])
        expected = int(expectations["max_inconsistent_rows"])
        add("max_inconsistent_rows", actual, expected, actual <= expected)
    if "inconsistent_account_names" in expectations:
        actual_rows = certification.get("inconsistent_accounts") or []
        actual_names = [str(row.get("name") or "") for row in actual_rows]
        expected_names = [
            str(name) for name in expectations["inconsistent_account_names"]
        ]
        normalize = lambda value: re.sub(r"[^a-z0-9]+", "", value.casefold())
        normalized_actual = [normalize(name) for name in actual_names]
        passed = len(actual_names) == len(expected_names) and all(
            any(normalize(expected) in actual for actual in normalized_actual)
            for expected in expected_names
        )
        add("inconsistent_account_names", actual_names, expected_names, passed)
    for position, expected_account in enumerate(expectations.get("accounts", []), 1):
        expected_code = str(expected_account.get("account_code") or "")
        expected_name = str(expected_account.get("name_contains") or "").casefold()
        expected_amount = expected_account.get("amount")
        tolerance = float(expected_account.get("tolerance", 0))
        candidates = [
            row for row in classification.get("rows", [])
            if (not expected_code or str(row.get("account_code") or "") == expected_code)
            and (not expected_name or expected_name in str(row.get("name") or "").casefold())
        ]
        passed = bool(candidates)
        if passed and expected_amount is not None:
            passed = any(
                row.get("amount") is not None
                and abs(float(row["amount"]) - float(expected_amount)) <= tolerance
                for row in candidates
            )
        add(
            f"account_{position}",
            [
                {
                    "account_code": row.get("account_code"),
                    "name": row.get("name"),
                    "amount": row.get("amount"),
                }
                for row in candidates
            ],
            expected_account,
            passed,
        )
    return checks, all(check["passed"] for check in checks)


def load_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("El manifiesto debe contener una lista no vacía en 'cases'.")
    filenames = []
    for case in cases:
        if not isinstance(case, dict) or not case.get("file"):
            raise ValueError("Cada caso del manifiesto debe indicar 'file'.")
        filenames.append(case["file"])
        pages = case.get("pages")
        if pages is not None and (
            not isinstance(pages, list)
            or not pages
            or any(not isinstance(page, int) or page < 1 for page in pages)
            or pages != sorted(set(pages))
        ):
            raise ValueError(f"Selección de páginas inválida para {case['file']}.")
    if len(filenames) != len(set(filenames)):
        raise ValueError("El manifiesto contiene nombres de archivo duplicados.")
    return cases


def resolve_manifest_cases(root: Path, cases: list[dict]) -> list[tuple[Path, dict]]:
    available: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.suffix.lower() in {".pdf", ".xlsx", ".xls"}:
            available.setdefault(path.name, []).append(path)
    resolved = []
    for case in cases:
        matches = available.get(case["file"], [])
        if not matches:
            raise FileNotFoundError(f"No se encontró el documento: {case['file']}")
        if len(matches) > 1:
            raise ValueError(f"El documento no es único en el corpus: {case['file']}")
        resolved.append((matches[0], case))
    return resolved


def certify(path: Path, pipeline: HomologationPipeline) -> dict:
    started = time.perf_counter()
    accounts, certification, warnings, ocr, rotation = _parse(path)
    parse_seconds = time.perf_counter() - started
    qualified = qualify_cuentas(accounts)
    origins = Counter(_serializable(account.origen_columna) for account in accounts)
    zero_rows = sum(
        account.monto is not None and float(account.monto) == 0
        for account in accounts
    )
    classification = _classify(qualified, pipeline)
    accounts_by_line = {account.linea: account for account in accounts}
    inconsistent_accounts = []
    if certification is not None:
        for line in certification.filas_inconsistentes:
            account = accounts_by_line.get(line)
            inconsistent_accounts.append({
                "line": line,
                "account_code": account.codigo if account is not None else None,
                "name": account.nombre if account is not None else "",
            })
    return {
        "file": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "status": "ok",
        "raw_accounts": len(accounts),
        "qualified_accounts": len(qualified),
        "filtered_rows": len(accounts) - len(qualified),
        "zero_rows": zero_rows,
        "total_rows": sum(bool(account.es_total) for account in accounts),
        "origins": dict(origins),
        "requires_ocr": ocr,
        "rotation": rotation,
        "parse_seconds": round(parse_seconds, 3),
        "certification": (
            {
                "state": certification.estado,
                "method": certification.metodo,
                "reasons": certification.razones,
                "inconsistent_rows": certification.filas_inconsistentes,
                "inconsistent_accounts": inconsistent_accounts,
                "final_totals_valid": certification.totales_finales_validos,
                "result": certification.resultado_ejercicio,
                "result_type": certification.tipo_resultado,
                "differences": certification.diferencias,
            }
            if certification is not None else None
        ),
        "warnings": warnings,
        "classification": classification,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--manifest", type=Path,
        help="Matriz JSON con archivos, páginas seleccionadas y resultados esperados.",
    )
    parser.add_argument(
        "--match", action="append", default=[],
        help="Procesa sólo archivos cuyo nombre contenga alguno de estos textos.",
    )
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    os.environ.setdefault("SAFE_MODE", "ON")
    if args.manifest:
        jobs = resolve_manifest_cases(args.input, load_manifest(args.manifest))
    else:
        paths = sorted(
            path for path in args.input.rglob("*")
            if path.suffix.lower() in {".pdf", ".xlsx", ".xls"}
            and "04_resultados_previos" not in path.parts
            and (
                not args.match
                or any(token.lower() in path.name.lower() for token in args.match)
            )
        )
        jobs = [(path, {}) for path in paths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pipeline = HomologationPipeline()
    results = []
    with tempfile.TemporaryDirectory(prefix="balance-cert-") as temp_dir:
        for position, (path, case) in enumerate(jobs, 1):
            print(f"[{position}/{len(jobs)}] {path.name}", flush=True)
            try:
                selected_pages = case.get("pages")
                parsed_path = path
                if selected_pages:
                    if path.suffix.lower() != ".pdf":
                        raise ValueError(
                            "La selección de páginas sólo aplica a archivos PDF."
                        )
                    parsed_path = Path(temp_dir) / f"{position:03d}-{path.name}"
                    parsed_path.write_bytes(
                        select_pdf(path.read_bytes(), selected_pages)
                    )
                result = certify(parsed_path, pipeline)
                result["file"] = path.name
                result["path"] = str(path)
                result["selected_pages"] = selected_pages or []
                if case.get("expect"):
                    checks, passed = evaluate_expectations(result, case["expect"])
                    result["expectation_checks"] = checks
                    result["expectations_passed"] = passed
                    result["required_for_release"] = bool(
                        case.get("required_for_release", True)
                    )
                print(
                    "  "
                    f"cuentas={result['raw_accounts']} "
                    f"cert={result['certification']['state'] if result['certification'] else 'n/a'} "
                    f"auto={result['classification']['automatic']} "
                    f"revision={result['classification']['review']} "
                    f"tiempo={result['elapsed_seconds']}s",
                    flush=True,
                )
                if "expectations_passed" in result:
                    print(
                        "  expectativas="
                        f"{'PASA' if result['expectations_passed'] else 'FALLA'}",
                        flush=True,
                    )
            except Exception as exc:  # continúa para localizar todos los patrones
                result = {
                    "file": path.name, "path": str(path), "status": "error",
                    "error_type": type(exc).__name__, "error": str(exc),
                }
                print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)
            results.append(result)
            args.output.write_text(
                json.dumps(results, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
    failed = any(row["status"] == "error" for row in results)
    failed = failed or any(
        row.get("required_for_release", True)
        and row.get("expectations_passed") is False
        for row in results
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
