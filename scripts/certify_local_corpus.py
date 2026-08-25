"""Certifica extracción y clasificación sobre un corpus local ignorado por Git."""

from __future__ import annotations

import argparse
import json
import os
import sys
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
        "--match", action="append", default=[],
        help="Procesa sólo archivos cuyo nombre contenga alguno de estos textos.",
    )
    args = parser.parse_args()
    if args.env_file:
        load_dotenv(args.env_file)
    os.environ.setdefault("SAFE_MODE", "ON")
    paths = sorted(
        path for path in args.input.rglob("*")
        if path.suffix.lower() in {".pdf", ".xlsx", ".xls"}
        and "04_resultados_previos" not in path.parts
        and (
            not args.match
            or any(token.lower() in path.name.lower() for token in args.match)
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pipeline = HomologationPipeline()
    results = []
    for position, path in enumerate(paths, 1):
        print(f"[{position}/{len(paths)}] {path.name}", flush=True)
        try:
            result = certify(path, pipeline)
            print(
                "  "
                f"cuentas={result['raw_accounts']} "
                f"cert={result['certification']['state'] if result['certification'] else 'n/a'} "
                f"auto={result['classification']['automatic']} "
                f"revision={result['classification']['review']} "
                f"tiempo={result['elapsed_seconds']}s",
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
    return 1 if any(row["status"] == "error" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
