"""Certifica extracción y clasificación sobre un corpus local ignorado por Git."""

from __future__ import annotations

import argparse
import hashlib
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
from parser_universal import ParserPDF, certificar_extraccion_columnas, parsear_excel
from pipeline.homologation_pipeline import HomologationPipeline
from document_scope import select_pdf


def _serializable(value):
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _account_snapshot(accounts, classification: dict) -> list[dict]:
    """Conserva todas las filas extraídas, incluidas cuentas y controles."""
    classified_by_line = {
        int(row["line"]): row for row in classification.get("rows", [])
    }
    snapshots = []
    for account in accounts:
        classified = classified_by_line.get(int(account.linea), {})
        snapshots.append({
            "line": int(account.linea),
            "account_code": str(account.codigo or ""),
            "name": str(account.nombre or ""),
            "origin": _serializable(account.origen_columna),
            "amount": account.monto,
            "is_total": bool(account.es_total),
            "confidence": float(account.confianza_extraccion or 0.0),
            "column_amounts": dict(account.montos_columnas or {}),
            "period_amounts": dict(account.montos_periodos or {}),
            "derived_columns": list(account.columnas_derivadas or []),
            "standard_code": str(classified.get("code") or ""),
            "classification_method": str(classified.get("method") or ""),
            "requires_review": bool(classified.get("review", False)),
        })
    return snapshots


def _detected_dimensions(accounts) -> tuple[list[str], list[str]]:
    periods: set[str] = set()
    currencies: set[str] = set()
    known_currencies = {"CLP", "USD", "EUR", "UF", "UTM", "M$", "MM$"}
    for account in accounts:
        for raw_key in (account.montos_periodos or {}):
            key = str(raw_key)
            periods.update(re.findall(r"(?:19|20)\d{2}", key))
            for token in re.split(r"[_\s/-]+", key.upper()):
                if token in known_currencies:
                    currencies.add(token)
    return sorted(periods, reverse=True), sorted(currencies)


def _json_value(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, (dict, list)):
        return value
    if not str(value).strip():
        return {}
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def _cell_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _cell_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "si", "sí", "yes"}
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(value)


def load_gold_rows(path: Path) -> list[dict]:
    """Lee un candidato revisado y omite sólo exclusiones explícitas.

    ``APROBADO`` describe una fila que debe existir exactamente en la salida.
    ``EXCLUIR`` describe ruido o una fila espuria que el parser ya no debería
    emitir. Cualquier otro estado mantiene el libro en revisión y evita que se
    use accidentalmente como referencia Gold.
    """
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("accounts") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("El Gold JSON debe contener una lista de cuentas.")
        return rows
    frame = pd.read_excel(path, sheet_name="Cuentas")
    if "Estado_revision" not in frame.columns:
        raise ValueError("El Gold XLSX no contiene la columna Estado_revision.")
    states = frame["Estado_revision"].fillna("").astype(str).str.upper().str.strip()
    allowed = {"APROBADO", "EXCLUIR"}
    pending = int((~states.isin(allowed)).sum())
    if pending:
        raise ValueError(
            "El Gold aún tiene "
            f"{pending} fila(s) sin Estado_revision=APROBADO o EXCLUIR."
        )
    rows = []
    for index, source in frame.iterrows():
        if states.iloc[index] == "EXCLUIR":
            continue
        rows.append({
            "line": int(source["Fila"]),
            "account_code": _cell_text(source.get("Codigo_original")),
            "name": _cell_text(source.get("Cuenta_original")),
            "origin": _cell_text(source.get("Origen")),
            "amount": source.get("Monto"),
            "period_amounts": _json_value(source.get("Montos_periodos_JSON")),
            "column_amounts": _json_value(source.get("Montos_columnas_JSON")),
            "standard_code": _cell_text(source.get("Codigo_homologado")),
            "requires_review": _cell_bool(source.get("Requiere_revision")),
            "is_total": _cell_bool(source.get("Es_control_total")),
        })
    return rows


def evaluate_gold_rows(
    actual_rows: list[dict], expected_rows: list[dict], tolerance: float = 0,
) -> list[dict]:
    """Compara el universo de filas sin ocultar faltantes, extras ni cambios."""
    def base_key(row: dict) -> tuple[str, str]:
        # La línea es trazabilidad del extractor, no identidad contable. Una
        # reconstrucción OCR válida puede mover la posición sin cambiar la
        # cuenta; código, nombre y ocurrencia sí deben seguir coincidiendo.
        return (
            str(row.get("account_code") or ""),
            _normalized_text(row.get("name")),
        )

    def indexed(rows: list[dict]) -> dict[tuple[str, str, int], dict]:
        occurrences: Counter = Counter()
        result = {}
        for row in rows:
            identity = base_key(row)
            occurrences[identity] += 1
            result[(*identity, occurrences[identity])] = row
        return result

    actual = indexed(actual_rows)
    expected = indexed(expected_rows)
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    mismatches = []
    fields = (
        "origin", "period_amounts", "column_amounts", "standard_code",
        "requires_review", "is_total",
    )
    for row_key in sorted(expected.keys() & actual.keys()):
        differences = {}
        expected_row = expected[row_key]
        actual_row = actual[row_key]
        expected_amount = expected_row.get("amount")
        actual_amount = actual_row.get("amount")
        amount_ok = (
            expected_amount is None and actual_amount is None
            or expected_amount is not None and actual_amount is not None
            and abs(float(actual_amount) - float(expected_amount)) <= tolerance
        )
        if not amount_ok:
            differences["amount"] = [actual_amount, expected_amount]
        for field in fields:
            if actual_row.get(field) != expected_row.get(field):
                differences[field] = [actual_row.get(field), expected_row.get(field)]
        if differences:
            mismatches.append({"key": row_key, "differences": differences})
    return [
        {"name": "gold_missing_rows", "actual": missing, "expected": [],
         "passed": not missing},
        {"name": "gold_extra_rows", "actual": extra, "expected": [],
         "passed": not extra},
        {"name": "gold_mismatched_rows", "actual": mismatches, "expected": [],
         "passed": not mismatches},
    ]


def _candidate_frame(result: dict) -> pd.DataFrame:
    rows = []
    for row in result.get("accounts", []):
        periods = row.get("period_amounts") or {}
        rows.append({
            "Estado_revision": "PENDIENTE",
            "Tipo_fila_esperado": "",
            "Observacion_analista": "",
            "Fila": row.get("line"),
            "Codigo_original": row.get("account_code"),
            "Cuenta_original": row.get("name"),
            "Origen": row.get("origin"),
            "Monto": row.get("amount"),
            "Monto_actual": periods.get("actual"),
            "Monto_anterior": periods.get("anterior"),
            "Montos_periodos_JSON": json.dumps(
                periods, ensure_ascii=False, sort_keys=True,
            ),
            "Montos_columnas_JSON": json.dumps(
                row.get("column_amounts") or {},
                ensure_ascii=False, sort_keys=True,
            ),
            "Codigo_homologado": row.get("standard_code"),
            "Metodo_clasificacion": row.get("classification_method"),
            "Requiere_revision": row.get("requires_review"),
            "Es_control_total": row.get("is_total"),
            "Confianza_extraccion": row.get("confidence"),
            "Columnas_derivadas_JSON": json.dumps(
                row.get("derived_columns") or [], ensure_ascii=False,
            ),
        })
    return pd.DataFrame(rows)


def write_gold_candidate(result: dict, output_dir: Path) -> Path:
    """Genera un libro revisable; no lo declara Gold automáticamente."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(result["file"]).stem)
    output = output_dir / f"{safe_name}.gold-candidate.xlsx"
    summary = pd.DataFrame([{
        "Documento": result.get("file"),
        "SHA256": result.get("sha256"),
        "Paginas_seleccionadas": ",".join(
            str(page) for page in result.get("selected_pages", [])
        ),
        "Periodos_detectados": ",".join(result.get("detected_periods", [])),
        "Monedas_detectadas": ",".join(result.get("detected_currencies", [])),
        "Filas_extraidas": result.get("raw_accounts"),
        "Cuentas_calificadas": result.get("qualified_accounts"),
        "Estado_certificacion": (result.get("certification") or {}).get("state"),
        "Resultado_ejercicio": (result.get("certification") or {}).get("result"),
        "Instruccion": (
            "Revise todas las filas contra el original. Use APROBADO para "
            "filas que deben existir, EXCLUIR para ruido que el parser debe "
            "dejar de emitir y CORREGIR mientras un valor siga pendiente."
        ),
    }])
    controls = pd.DataFrame([
        {
            "Control": check.get("name"),
            "Actual": json.dumps(check.get("actual"), ensure_ascii=False, default=str),
            "Esperado": json.dumps(check.get("expected"), ensure_ascii=False, default=str),
            "Cumple": check.get("passed"),
        }
        for check in result.get("expectation_checks", [])
    ])
    warnings = pd.DataFrame({"Advertencia": result.get("warnings", [])})
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        _candidate_frame(result).to_excel(writer, sheet_name="Cuentas", index=False)
        controls.to_excel(writer, sheet_name="Controles", index=False)
        warnings.to_excel(writer, sheet_name="Advertencias", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
    return output


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
        if not account.codigo and PATRON_NO_CUENTA.match(account.nombre.strip()):
            continue
        adapted = AccountAdapter.from_cuenta_raw(account)
        amount = BalanceInterpreter(adapted).classification_amount
        if (
            amount is None
            and account.monto is not None
            and account.montos_periodos
            and not account.es_total
        ):
            amount = float(account.monto)
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
        if (
            account.monto is not None
            and float(account.monto) == 0
            and pipeline._classify_audited_statement_label(
                account.nombre, account_type, account.seccion_contable,
            ) is None
        ):
            continue
        started = time.perf_counter()
        classification = pipeline._classify_account(
            adapted.account_code, adapted.account_name,
            account_tipo=account_type,
            account_section=account.seccion_contable,
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
    if "sha256" in expectations:
        actual = result.get("sha256")
        expected = str(expectations["sha256"]).lower()
        add("sha256", actual, expected, actual == expected)
    if "exact_raw_accounts" in expectations:
        actual = int(result.get("raw_accounts") or 0)
        expected = int(expectations["exact_raw_accounts"])
        add("exact_raw_accounts", actual, expected, actual == expected)
    if "exact_qualified_accounts" in expectations:
        actual = int(result.get("qualified_accounts") or 0)
        expected = int(expectations["exact_qualified_accounts"])
        add("exact_qualified_accounts", actual, expected, actual == expected)
    for field, result_field in (
        ("periods", "detected_periods"),
        ("currencies", "detected_currencies"),
    ):
        if field in expectations:
            actual = sorted(result.get(result_field) or [])
            expected = sorted(str(value) for value in expectations[field])
            add(field, actual, expected, actual == expected)
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
    if "_gold_rows" in expectations:
        checks.extend(evaluate_gold_rows(
            result.get("accounts") or [], expectations["_gold_rows"],
            float(expectations.get("gold_tolerance", 0)),
        ))
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
        gold_file = case.get("gold_file")
        if gold_file and (
            Path(gold_file).is_absolute() or ".." in Path(gold_file).parts
        ):
            raise ValueError(f"Ruta Gold inválida para {case['file']}.")
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
    periods, currencies = _detected_dimensions(accounts)
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
    result = {
        "file": path.name,
        "path": str(path),
        "sha256": _sha256(path),
        "extension": path.suffix.lower(),
        "status": "ok",
        "raw_accounts": len(accounts),
        "qualified_accounts": len(qualified),
        "filtered_rows": len(accounts) - len(qualified),
        "zero_rows": zero_rows,
        "total_rows": sum(bool(account.es_total) for account in accounts),
        "origins": dict(origins),
        "detected_periods": periods,
        "detected_currencies": currencies,
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
    result["accounts"] = _account_snapshot(accounts, classification)
    return result


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
    parser.add_argument(
        "--write-gold-candidates", type=Path,
        help="Genera libros revisables; no los considera Gold hasta aprobar filas.",
    )
    parser.add_argument(
        "--gold-root", type=Path,
        help="Directorio privado desde el cual resolver gold_file del manifiesto.",
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
                result["sha256"] = _sha256(path)
                result["selected_pages"] = selected_pages or []
                if case.get("expect"):
                    expectations = dict(case["expect"])
                    if case.get("gold_file"):
                        gold_root = args.gold_root or args.manifest.parent
                        gold_path = gold_root / case["gold_file"]
                        expectations["_gold_rows"] = load_gold_rows(gold_path)
                    checks, passed = evaluate_expectations(result, expectations)
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
                if args.write_gold_candidates:
                    candidate = write_gold_candidate(
                        result, args.write_gold_candidates,
                    )
                    result["gold_candidate"] = str(candidate)
                    print(f"  candidato_gold={candidate}", flush=True)
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
