"""Certifica extracción y clasificación sobre un corpus local ignorado por Git."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
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
from parsers.account_type_resolver import (
    account_type_from_explicit_section,
    is_contra_asset_name,
    is_credit_balance_depreciation_name,
    is_debit_balance_financial_liability,
)
from pipeline.homologation_pipeline import (
    HomologationPipeline,
    _lineas_revision_extraccion,
)
from reporting_integrity import (
    certificar_cuadratura_homologada,
    debe_incorporar_resultado_derivado,
    resultado_final_fuente_certificado,
)
from delivery_readiness import evaluar_entregabilidad
from format_support import evaluar_formato


@dataclass(frozen=True)
class ConfirmedClosingYear:
    """Año de cierre respaldado por un manifiesto externo al corpus.

    El lote nunca deduce el año desde el nombre del archivo. ``source`` queda
    en el reporte para que una reclasificación basada en período sea auditable.
    """

    year: int
    source: str


def _manifest_basename(value, *, context: str) -> str:
    """Acepta sólo un basename literal, no una ruta ni una coincidencia parcial."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} debe ser un basename no vacío")
    basename = value.strip()
    if Path(basename).name != basename or basename in {".", ".."}:
        raise ValueError(f"{context} debe contener sólo el basename del documento")
    return basename


def _manifest_closing_year(value, *, context: str) -> int:
    """Valida un año explícito sin convertir valores ambiguos silenciosamente."""
    if isinstance(value, bool):
        raise ValueError(f"{context} debe ser un año entero entre 1900 y 2200")
    if isinstance(value, int):
        year = value
    elif isinstance(value, str) and value.strip().isdigit():
        year = int(value.strip())
    else:
        raise ValueError(f"{context} debe ser un año entero entre 1900 y 2200")
    if not 1900 <= year <= 2200:
        raise ValueError(f"{context} debe estar entre 1900 y 2200")
    return year


def _load_closing_year_manifest(
        path: Path | None,
) -> dict[str, ConfirmedClosingYear]:
    """Carga el manifiesto explícito de años de cierre confirmados.

    Esquema admitido::

        {
          "by_basename": {"archivo.pdf": 2024},
          "by_id": {
            "documento-opaco-001": {
              "basename": "otro-archivo.pdf",
              "closing_year": 2023
            }
          }
        }

    Cada basename puede figurar una sola vez. La entrada ``by_id`` mantiene
    un identificador externo sin pedir que el nombre del archivo contenga el
    año ni usarlo como evidencia contable.
    """
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"no se pudo leer {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("el manifiesto debe ser un objeto JSON")

    allowed_sections = {"by_basename", "by_id"}
    unexpected_sections = set(payload) - allowed_sections
    if unexpected_sections:
        raise ValueError(
            "secciones no admitidas en el manifiesto: "
            + ", ".join(sorted(map(str, unexpected_sections)))
        )

    manifest: dict[str, ConfirmedClosingYear] = {}

    def register(basename: str, entry: ConfirmedClosingYear) -> None:
        if basename in manifest:
            raise ValueError(
                f"el documento {basename!r} tiene más de un año de cierre confirmado"
            )
        manifest[basename] = entry

    by_basename = payload.get("by_basename", {})
    if not isinstance(by_basename, dict):
        raise ValueError("by_basename debe ser un objeto JSON")
    for raw_basename, raw_year in by_basename.items():
        basename = _manifest_basename(
            raw_basename, context="cada clave de by_basename",
        )
        year = _manifest_closing_year(
            raw_year, context=f"by_basename[{basename!r}]",
        )
        register(
            basename,
            ConfirmedClosingYear(year=year, source="manifest:basename"),
        )

    by_id = payload.get("by_id", {})
    if not isinstance(by_id, dict):
        raise ValueError("by_id debe ser un objeto JSON")
    for document_id, raw_entry in by_id.items():
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("cada clave de by_id debe ser un identificador no vacío")
        if not isinstance(raw_entry, dict):
            raise ValueError(
                f"by_id[{document_id!r}] debe contener basename y closing_year"
            )
        required_keys = {"basename", "closing_year"}
        if set(raw_entry) != required_keys:
            raise ValueError(
                f"by_id[{document_id!r}] debe contener exactamente "
                "basename y closing_year"
            )
        basename = _manifest_basename(
            raw_entry["basename"], context=f"by_id[{document_id!r}].basename",
        )
        year = _manifest_closing_year(
            raw_entry["closing_year"],
            context=f"by_id[{document_id!r}].closing_year",
        )
        register(
            basename,
            ConfirmedClosingYear(
                year=year,
                source=f"manifest:id:{document_id.strip()}",
            ),
        )

    return manifest


@contextmanager
def _project_runtime_context():
    """Hace disponibles los assets relativos del proyecto durante el lote.

    ``CMCCClassifier`` aún lee ``knowledge/cmcc.json`` relativo al directorio
    actual. El script puede invocarse desde cualquier carpeta, por lo que el
    contexto se limita a la construcción y uso del pipeline. El directorio
    temporal evita crear una base local de aprendizaje dentro del repositorio.
    """
    caller_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(
            prefix="homologacion-balances-corpus-",
    ) as temporary_directory:
        try:
            os.chdir(PROJECT_ROOT)
            yield Path(temporary_directory)
        finally:
            os.chdir(caller_cwd)


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
        return accounts, certification, [], False, 0, None, [], None
    result = ParserPDF().parsear(path)
    return (
        result.cuentas,
        result.certificacion_extraccion,
        result.advertencias,
        result.requirio_ocr,
        result.rotacion_aplicada,
        result.orientacion_certificada,
        result.orientaciones_paginas,
        result.document_context,
    )


def _classify(
        accounts,
        pipeline: HomologationPipeline,
        certification,
        closing_year: int | None = None,
        closing_year_source: str | None = None,
) -> dict:
    rows = []
    certification_state = getattr(certification, "estado", "no_evaluable")
    extraction_certified = certification_state == "certificada"
    extraction_review_lines = _lineas_revision_extraccion(certification)
    for account in accounts:
        # Los controles de cuadratura son evidencia de extracción, no cuentas
        # elegibles para clasificación ni para una decisión automática.
        if account.es_total:
            continue
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
        seccion_contable = getattr(account, "seccion_contable", None)
        source_account_code = account.codigo or adapted.account_code
        classification_by_result_year = (
            pipeline._classification_for_explicit_result_year(
                adapted.account_name,
                source_account_code,
                closing_year,
            )
            if closing_year is not None else None
        )
        result_year_method = (
            classification_by_result_year.get("method")
            if classification_by_result_year is not None else ""
        )
        effective_origin = _origen_efectivo(
            account.origen_columna, amount, account.nombre, seccion_contable,
            codigo_original=source_account_code,
            anio_cierre=closing_year,
        )
        tipo_seccion = account_type_from_explicit_section(seccion_contable)
        account_type = (
            tipo_seccion.value if tipo_seccion is not None
            else _resolver_tipo_cuenta(effective_origin, account.codigo)
        )
        contra_activo_depreciacion = is_credit_balance_depreciation_name(
            account.nombre, account.origen_columna, amount,
        )
        contra_activo_depreciacion_contextual = (
            contra_activo_depreciacion
            and not is_contra_asset_name(account.nombre)
        )
        if (tipo_seccion is None and effective_origin == "pasivo"
                and (
                    _es_contra_activo(
                        account.nombre, account.origen_columna, amount,
                    )
                    or contra_activo_depreciacion
                )):
            account_type = "ACTIVO"
        if tipo_seccion is None and _es_partida_patrimonial(
                account.nombre,
                codigo_original=source_account_code,
                anio_cierre=closing_year,
        ):
            account_type = "PATRIMONIO"
        if result_year_method in {
                "historical_result_year", "current_result_year",
        }:
            account_type = "PATRIMONIO"
        contra_pasivo_deudor = is_debit_balance_financial_liability(
            account.nombre, account.origen_columna, amount,
        )
        started = time.perf_counter()
        classification = classification_by_result_year or (
            pipeline._classify_debit_balance_financial_liability(
                adapted.account_name,
            )
            if contra_pasivo_deudor else None
        ) or pipeline._classify_account(
            adapted.account_code, adapted.account_name,
            account_tipo=account_type,
        )
        # Mantener el lote alineado con el pipeline: aun cuando una regla
        # genérica ya devuelva ANC, una depreciación acreedora es una propuesta
        # contextual que requiere revisión humana.
        if contra_activo_depreciacion_contextual:
            special = pipeline._classify_credit_balance_depreciation(
                adapted.account_name, account.origen_columna, amount,
            )
            if special is not None:
                classification = special
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
                seccion_contable=seccion_contable,
                codigo_original=source_account_code,
                anio_cierre=closing_year,
            )
        )
        if final_code and not compatible:
            final_code = None
        confidence = float(classification.get("confidence") or 0.0)
        candidate_review = (
            not final_code
            or confidence < UMBRAL_REVISION
            or bool(adjustment.aplica and adjustment.requiere_revision)
            or bool(classification.get("requires_review", False))
            or bool(account.columnas_derivadas)
        )
        extraction_review_required = bool(
            not extraction_certified
            and (
                extraction_review_lines is None
                or account.linea in extraction_review_lines
            )
        )
        review = candidate_review or extraction_review_required
        rows.append({
            "line": account.linea,
            "name": account.nombre,
            "source_account_code": source_account_code,
            "origin": _serializable(account.origen_columna),
            "origen_columna": _serializable(account.origen_columna),
            "origen_columna_efectiva": effective_origin,
            "confirmed_closing_year": closing_year,
            "confirmed_closing_year_source": closing_year_source or "",
            "seccion_contable": seccion_contable or "",
            "estado_financiero": getattr(account, "estado_financiero", None) or "",
            "amount": amount,
            "code": final_code or "",
            "method": classification.get("method", ""),
            "confidence": confidence,
            "compatible": compatible,
            "candidate_review": candidate_review,
            "review": review,
            "automatic_blocked_by_extraction": bool(
                final_code and not candidate_review
                and extraction_review_required
            ),
            "extraction_review_required": extraction_review_required,
            "classification_ms": round(elapsed_ms, 3),
        })
    methods = Counter(row["method"] for row in rows)
    return {
        "eligible": len(rows),
        "classified": sum(bool(row["code"]) for row in rows),
        "candidate_automatic": sum(
            bool(row["code"]) and not row["candidate_review"] for row in rows
        ),
        "automatic": sum(bool(row["code"]) and not row["review"] for row in rows),
        "automatic_blocked_by_extraction": sum(
            bool(row["automatic_blocked_by_extraction"]) for row in rows
        ),
        "review": sum(row["review"] for row in rows),
        "unclassified": sum(not row["code"] for row in rows),
        "methods": dict(methods.most_common()),
        "classification_seconds": round(
            sum(row["classification_ms"] for row in rows) / 1000, 3
        ),
        "rows": rows,
    }


def certify(
        path: Path,
        pipeline: HomologationPipeline,
        closing_year: int | None = None,
        closing_year_source: str | None = None,
) -> dict:
    started = time.perf_counter()
    (
        accounts, certification, warnings, ocr, rotation,
        orientation_certified, orientation_pages, document_context,
    ) = _parse(path)
    parse_seconds = time.perf_counter() - started
    qualified = qualify_cuentas(accounts)
    origins = Counter(_serializable(account.origen_columna) for account in accounts)
    zero_rows = sum(
        account.monto is not None and float(account.monto) == 0
        for account in accounts
    )
    certification_state = (
        certification.estado if certification is not None else "no_evaluable"
    )
    classification = _classify(
        qualified,
        pipeline,
        certification,
        closing_year=closing_year,
        closing_year_source=closing_year_source,
    )
    accounting_quadrature = certificar_cuadratura_homologada(
        classification["rows"],
        incluir_resultado_derivado=debe_incorporar_resultado_derivado(
            classification["rows"], certification,
        ),
        resultado_final_fuente=resultado_final_fuente_certificado(
            certification,
        ),
    )
    delivery_readiness = evaluar_entregabilidad(
        classification["rows"],
        certification,
        accounting_quadrature,
        formato=evaluar_formato(certification, document_context),
    )
    return {
        "file": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "status": "ok",
        "confirmed_closing_year": closing_year,
        "confirmed_closing_year_source": closing_year_source or "",
        "raw_accounts": len(accounts),
        "qualified_accounts": len(qualified),
        "filtered_rows": len(accounts) - len(qualified),
        "zero_rows": zero_rows,
        "total_rows": sum(bool(account.es_total) for account in accounts),
        "origins": dict(origins),
        "requires_ocr": ocr,
        "rotation": rotation,
        "orientation_certified": orientation_certified,
        "orientation_pages": orientation_pages,
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
                "source_control_quadrature": {
                    "valid": certification.ecuacion_contable_fuente_valida,
                    "difference": (
                        certification.diferencia_ecuacion_contable_fuente
                    ),
                },
                "orientation_certified": certification.orientacion_certificada,
                "orientation_pages": certification.orientaciones_paginas,
                "final_columns_validated": certification.columnas_finales_validadas,
                "final_reconstructions": certification.reconstrucciones_finales,
                "final_reconstruction_ratio": (
                    certification.proporcion_finales_reconstruidos
                ),
                "final_reconstruction_reviewable": (
                    certification.reconstruccion_final_revisable
                ),
                "inconsistent_rows": certification.filas_inconsistentes,
                "diagnosis": certification.diagnostico,
                "diagnostic_signals": certification.senales_diagnostico,
            }
            if certification is not None else None
        ),
        "warnings": warnings,
        "classification": classification,
        "accounting_quadrature": accounting_quadrature,
        "delivery_readiness": delivery_readiness,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--closing-year-manifest",
        type=Path,
        help=(
            "JSON explícito con by_basename o by_id para años de cierre "
            "confirmados; nunca se infieren desde el nombre del archivo."
        ),
    )
    parser.add_argument(
        "--match", action="append", default=[],
        help="Procesa sólo archivos cuyo nombre contenga alguno de estos textos.",
    )
    args = parser.parse_args()
    # Resolver los argumentos de usuario antes de cambiar al árbol del
    # proyecto. Así un input, output, env-file o manifiesto relativo conserva
    # el significado que tenía al invocar el script desde otra carpeta.
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve() if args.env_file else None
    closing_year_manifest = (
        args.closing_year_manifest.expanduser().resolve()
        if args.closing_year_manifest else None
    )
    if env_file:
        load_dotenv(env_file)
    os.environ.setdefault("SAFE_MODE", "ON")
    try:
        closing_years = _load_closing_year_manifest(
            closing_year_manifest,
        )
    except ValueError as exc:
        parser.error(f"--closing-year-manifest inválido: {exc}")
    paths = sorted(
        path for path in input_path.rglob("*")
        if path.suffix.lower() in {".pdf", ".xlsx", ".xls"}
        and "04_resultados_previos" not in path.parts
        and (
            not args.match
            or any(token.lower() in path.name.lower() for token in args.match)
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with _project_runtime_context() as runtime_directory:
        pipeline = HomologationPipeline(
            db_path=runtime_directory / "gold_standard.db",
        )
        for position, path in enumerate(paths, 1):
            print(f"[{position}/{len(paths)}] {path.name}", flush=True)
            confirmed_closing_year = closing_years.get(path.name)
            try:
                result = certify(
                    path,
                    pipeline,
                    closing_year=(
                        confirmed_closing_year.year
                        if confirmed_closing_year is not None else None
                    ),
                    closing_year_source=(
                        confirmed_closing_year.source
                        if confirmed_closing_year is not None else None
                    ),
                )
                print(
                    "  "
                    f"cuentas={result['raw_accounts']} "
                    f"cert={result['certification']['state'] if result['certification'] else 'n/a'} "
                    f"auto={result['classification']['automatic']} "
                    f"revision={result['classification']['review']} "
                    f"entrega={result['delivery_readiness']['estado']} "
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
            output_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
    return 1 if any(row["status"] == "error" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
