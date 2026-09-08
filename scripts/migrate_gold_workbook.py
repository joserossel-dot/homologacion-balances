"""Migra un Gold schema 1 a schema 2 sin aprobar metadatos nuevos.

La migración usa un candidato recién generado por el certificador. Conserva
la decisión humana sólo cuando la fila y sus metadatos protegidos coinciden;
cualquier jerarquía, método, confianza o columna derivada nueva queda en
``CORREGIR`` para revisión explícita.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pandas as pd

PROTECTED_COLUMNS = (
    "Jerarquia_contable", "Metodo_clasificacion", "Confianza_extraccion",
    "Columnas_derivadas_JSON",
)

FIELD_LABELS = {
    "accounting_hierarchy": "Jerarquia_contable",
    "classification_method": "Metodo_clasificacion",
    "confidence": "Confianza_extraccion",
    "derived_columns": "Columnas_derivadas_JSON",
    "origin": "Origen",
    "amount": "Monto",
    "period_amounts": "Montos_periodos_JSON",
    "column_amounts": "Montos_columnas_JSON",
    "standard_code": "Codigo_homologado",
    "requires_review": "Requiere_revision",
    "is_total": "Es_control_total",
}
INTERNAL_BY_COLUMN = {value: key for key, value in FIELD_LABELS.items()}


def _normalized(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _indexed(frame: pd.DataFrame) -> dict[tuple[str, str, int], pd.Series]:
    occurrences: Counter = Counter()
    indexed = {}
    for _, row in frame.iterrows():
        base = (
            _text(row.get("Codigo_original")),
            _normalized(row.get("Cuenta_original")),
        )
        occurrences[base] += 1
        indexed[(*base, occurrences[base])] = row
    return indexed


def migrate_gold_workbook(legacy: Path, candidate: Path, output: Path) -> Path:
    legacy_rows = pd.read_excel(legacy, sheet_name="Cuentas")
    candidate_rows = pd.read_excel(candidate, sheet_name="Cuentas")
    candidate_rows["Estado_revision"] = candidate_rows[
        "Estado_revision"
    ].astype(object)
    candidate_rows["Observacion_analista"] = candidate_rows[
        "Observacion_analista"
    ].astype(object)
    legacy_index = _indexed(legacy_rows)
    candidate_index = _indexed(candidate_rows)
    for key, row in candidate_index.items():
        legacy_row = legacy_index.get(key)
        row_index = row.name
        if legacy_row is None:
            candidate_rows.at[row_index, "Estado_revision"] = "CORREGIR"
            candidate_rows.at[row_index, "Observacion_analista"] = (
                "Fila nueva en schema 2; requiere revisión humana."
            )
            continue
        previous_state = str(legacy_row.get("Estado_revision") or "").upper()
        changed = []
        for column in PROTECTED_COLUMNS:
            previous = legacy_row.get(column) if column in legacy_rows.columns else None
            current = row.get(column)
            if pd.isna(previous):
                previous = None
            if pd.isna(current):
                current = None
            if previous != current:
                changed.append(column)
        if changed:
            candidate_rows.at[row_index, "Estado_revision"] = "CORREGIR"
            candidate_rows.at[row_index, "Observacion_analista"] = (
                "Revisar metadatos schema 2: " + ", ".join(changed)
            )
        else:
            candidate_rows.at[row_index, "Estado_revision"] = previous_state
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, output)
    summary = pd.read_excel(output, sheet_name="Resumen")
    summary["Gold_schema_version"] = 2
    with pd.ExcelWriter(
        output, engine="openpyxl", mode="a", if_sheet_exists="replace",
    ) as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        candidate_rows.to_excel(writer, sheet_name="Cuentas", index=False)
    return output


def _review_severity(field: str, kind: str = "mismatch") -> str:
    if kind in {"missing", "extra"} or field in {
        "amount", "period_amounts", "column_amounts", "origin",
        "standard_code", "is_total", "requires_review",
    }:
        return "CRITICA"
    if field in {"accounting_hierarchy", "derived_columns"}:
        return "ALTA"
    return "MEDIA"


def _is_blank(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def build_gold_review_package(
    report: Path, output_dir: Path, *, manifest: Path | None = None,
    legacy_gold_root: Path | None = None,
) -> dict:
    """Genera evidencia privada determinista sin aprobar ninguna diferencia."""
    results = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise ValueError("El informe Gold debe contener una lista JSON.")
    differences: list[dict] = []
    documents: list[dict] = []
    for result in sorted(results, key=lambda row: str(row.get("file") or "")):
        filename = str(result.get("file") or "")
        selected_pages = list(result.get("selected_pages") or [])
        failed_checks = [
            check for check in result.get("expectation_checks", [])
            if check.get("passed") is not True
        ]
        mismatch_check = next(
            (check for check in failed_checks if check.get("name") == "gold_mismatched_rows"),
            {"actual": []},
        )
        for mismatch in mismatch_check.get("actual") or []:
            key = mismatch.get("key") or ["", "", 0]
            for field, values in sorted((mismatch.get("differences") or {}).items()):
                actual, expected = values
                migration_only = bool(
                    field in {
                        "accounting_hierarchy", "classification_method",
                        "confidence", "derived_columns",
                    }
                    and _is_blank(expected)
                    and not _is_blank(actual)
                )
                differences.append({
                    "document": filename,
                    "account_code": key[0],
                    "account_identity": key[1],
                    "occurrence": key[2],
                    "field": field,
                    "field_label": FIELD_LABELS.get(field, field),
                    "severity": _review_severity(field),
                    "original_gold_value": expected,
                    "actual_extracted_value": actual,
                    "expected_value": expected,
                    "proposed_value": actual if migration_only else None,
                    "autofillable_without_ambiguity": migration_only,
                    "review_state": "CORREGIR",
                    "selected_pages": selected_pages,
                    "actual_line": mismatch.get("actual_line"),
                    "expected_line": mismatch.get("expected_line"),
                })
        for check_name, kind in (
            ("gold_missing_rows", "missing"),
            ("gold_extra_rows", "extra"),
        ):
            check = next(
                (item for item in failed_checks if item.get("name") == check_name),
                {"actual": []},
            )
            for key in check.get("actual") or []:
                differences.append({
                    "document": filename,
                    "account_code": key[0],
                    "account_identity": key[1],
                    "occurrence": key[2],
                    "field": kind,
                    "field_label": kind,
                    "severity": "CRITICA",
                    "original_gold_value": key if kind == "missing" else None,
                    "actual_extracted_value": key if kind == "extra" else None,
                    "expected_value": key if kind == "missing" else None,
                    "proposed_value": None,
                    "autofillable_without_ambiguity": False,
                    "review_state": "CORREGIR",
                    "selected_pages": selected_pages,
                    "actual_line": None,
                    "expected_line": None,
                })
        documents.append({
            "document": filename,
            "certification_state": (result.get("certification") or {}).get("state"),
            "expectations_passed": result.get("expectations_passed") is True,
            "selected_pages": selected_pages,
            "gold_candidate": result.get("gold_candidate"),
            "failed_controls": sorted(
                check.get("name") for check in failed_checks
            ),
        })
    # Schema 1 no fijaba jerarquía. Se contrasta directamente el candidato
    # schema 2 con el libro legado para incluir esos campos migratorios, sin
    # modificar ni aprobar el Gold original.
    if manifest and legacy_gold_root:
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        gold_by_document = {
            str(case["file"]): str(case.get("gold_file") or "")
            for case in manifest_data.get("cases", [])
        }
        existing = {
            (
                row["document"], row["account_code"], row["account_identity"],
                int(row["occurrence"]), row["field"],
            )
            for row in differences
        }
        for result in results:
            filename = str(result.get("file") or "")
            legacy_name = gold_by_document.get(filename)
            candidate_path = result.get("gold_candidate")
            if not legacy_name or not candidate_path:
                continue
            legacy_rows = pd.read_excel(
                legacy_gold_root / legacy_name, sheet_name="Cuentas",
            )
            candidate_rows = pd.read_excel(candidate_path, sheet_name="Cuentas")
            legacy_index = _indexed(legacy_rows)
            candidate_index = _indexed(candidate_rows)
            for key in sorted(legacy_index.keys() & candidate_index.keys()):
                legacy_row = legacy_index[key]
                candidate_row = candidate_index[key]
                for column in PROTECTED_COLUMNS:
                    previous = (
                        legacy_row.get(column)
                        if column in legacy_rows.columns else None
                    )
                    current = candidate_row.get(column)
                    if pd.isna(previous):
                        previous = None
                    if pd.isna(current):
                        current = None
                    if previous == current:
                        continue
                    field = INTERNAL_BY_COLUMN[column]
                    identity = (filename, key[0], key[1], int(key[2]), field)
                    if identity in existing:
                        continue
                    migration_only = _is_blank(previous) and not _is_blank(current)
                    differences.append({
                        "document": filename,
                        "account_code": key[0],
                        "account_identity": key[1],
                        "occurrence": key[2],
                        "field": field,
                        "field_label": column,
                        "severity": _review_severity(field),
                        "original_gold_value": previous,
                        "actual_extracted_value": current,
                        "expected_value": previous,
                        "proposed_value": current if migration_only else None,
                        "autofillable_without_ambiguity": migration_only,
                        "review_state": "CORREGIR",
                        "selected_pages": list(result.get("selected_pages") or []),
                        "actual_line": candidate_row.get("Fila"),
                        "expected_line": legacy_row.get("Fila"),
                    })
                    existing.add(identity)
    differences.sort(key=lambda row: (
        row["document"], row["severity"], row["account_identity"],
        int(row["occurrence"]), row["field"],
    ))
    severity_counts = Counter(row["severity"] for row in differences)
    field_counts = Counter(row["field"] for row in differences)
    summary = {
        "schema": 1,
        "source_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        "documents": len(documents),
        "documents_approved": sum(row["expectations_passed"] for row in documents),
        "differences": len(differences),
        "autofillable_without_ambiguity": sum(
            row["autofillable_without_ambiguity"] for row in differences
        ),
        "by_severity": dict(sorted(severity_counts.items())),
        "by_field": dict(sorted(field_counts.items())),
        "release_blocked": any(not row["expectations_passed"] for row in documents),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "differences.json").write_text(
        json.dumps(differences, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    checklist = [
        "# Revisión humana Gold schema 2",
        "",
        "Este paquete no aprueba cuentas automáticamente.",
        "",
        f"- Documentos: {summary['documents']}",
        f"- Diferencias: {summary['differences']}",
        "- Estado de publicación: BLOQUEADO" if summary["release_blocked"] else "- Estado de publicación: APTO",
        "",
        "## Checklist",
        "",
        "- [ ] Confirmar cada monto y período contra la página seleccionada.",
        "- [ ] Confirmar código homologado, origen y naturaleza contable.",
        "- [ ] Revisar jerarquía, método, confianza y columnas derivadas.",
        "- [ ] Aceptar o corregir cada propuesta autocompletable.",
        "- [ ] Mantener CORREGIR mientras exista una diferencia no resuelta.",
        "- [ ] Regenerar Gold schema 2 y ejecutar la matriz completa.",
        "- [ ] Emitir la atestación sólo después de 3/3 certificada.",
        "",
        "## Documentos",
        "",
    ]
    for document in documents:
        checklist.extend([
            f"### {document['document']}",
            "",
            f"- Certificación: {document['certification_state']}",
            f"- Páginas seleccionadas: {document['selected_pages']}",
            f"- Controles fallidos: {document['failed_controls']}",
            "",
        ])
    (output_dir / "CHECKLIST.md").write_text(
        "\n".join(checklist), encoding="utf-8",
    )
    flat_rows = []
    for row in differences:
        flat = dict(row)
        for field in (
            "original_gold_value", "actual_extracted_value", "expected_value",
            "proposed_value", "selected_pages",
        ):
            flat[field] = json.dumps(
                flat[field], ensure_ascii=False, sort_keys=True,
            )
        flat_rows.append(flat)
    grouped_rows = [
        {
            "Documento": document,
            "Campo": field,
            "Severidad": severity,
            "Cantidad": count,
            "Autocompletable_sin_ambiguedad": sum(
                row["autofillable_without_ambiguity"]
                for row in differences
                if row["document"] == document
                and row["field"] == field
                and row["severity"] == severity
            ),
        }
        for (document, field, severity), count in sorted(Counter(
            (row["document"], row["field"], row["severity"])
            for row in differences
        ).items())
    ]
    with pd.ExcelWriter(output_dir / "revision_gold_schema2.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Resumen", index=False)
        pd.DataFrame(documents).to_excel(writer, sheet_name="Documentos", index=False)
        pd.DataFrame(grouped_rows).to_excel(writer, sheet_name="Agrupacion", index=False)
        pd.DataFrame(flat_rows).to_excel(writer, sheet_name="Diferencias", index=False)
    return {"summary": summary, "documents": documents, "differences": differences}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--review-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--legacy-gold-root", type=Path)
    args = parser.parse_args()
    if args.report or args.review_output:
        if not args.report or not args.review_output:
            parser.error("--report y --review-output deben usarse juntos.")
        if bool(args.manifest) != bool(args.legacy_gold_root):
            parser.error(
                "--manifest y --legacy-gold-root deben usarse juntos."
            )
        build_gold_review_package(
            args.report, args.review_output, manifest=args.manifest,
            legacy_gold_root=args.legacy_gold_root,
        )
    else:
        if not args.legacy or not args.candidate or not args.output:
            parser.error("--legacy, --candidate y --output son obligatorios.")
        migrate_gold_workbook(args.legacy, args.candidate, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
