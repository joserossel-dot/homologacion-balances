"""Controles auxiliares posteriores para el pipeline operativo.

Este módulo consume una copia del resultado ya clasificado. Structure,
Coverage y Self-QA sólo observan: nunca reciben callbacks ni referencias que
permitan cambiar códigos o importes. La política puede pasar de shadow a
enforcement mediante una bandera explícita, limitada al permiso de exportar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from coverage_engine import CoverageCalculator
from coverage_engine.monetary_coverage import MonetaryCoverageCalculator
from coverage_engine.models import family_from_code
from document_context import DocumentContext
from document_context.models import (
    DocumentMetadata, KnowledgeData, ParserData, StructureData, ValidationData,
)
from self_qa_engine import SelfQAAdapter
from structure_engine import StructureDetector


@dataclass(frozen=True)
class OperationalQualityResult:
    mode: str
    structure: dict[str, Any]
    coverage: dict[str, Any]
    self_qa: dict[str, Any]
    requires_review: bool
    export_allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _relevant_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows = df.copy()
    if "es_total" in rows:
        rows = rows[~rows["es_total"].fillna(False).astype(bool)]
    amount = pd.to_numeric(rows.get("monto"), errors="coerce")
    return rows[amount.notna() & amount.ne(0)].copy()


def _family_for_row(row: pd.Series) -> str:
    code = str(row.get("codigo_clasificado") or "")
    if code and code != "__EXCLUIR__":
        return family_from_code(code)
    origin = str(
        row.get("origen_columna_efectiva")
        or row.get("origen_columna") or ""
    ).lower()
    if origin == "activo":
        return "Activo"
    if origin == "pasivo":
        return "Pasivo"
    if origin in {"perdida", "ganancia"}:
        return "Resultado"
    return "Unknown"


def analyze_operational_quality(
    df: pd.DataFrame, *, balance_squared: bool,
    enforce_export: bool = False,
) -> OperationalQualityResult:
    """Ejecuta Structure -> Coverage -> Self-QA sin reclasificar cuentas."""
    rows = _relevant_rows(df)
    snapshots = []
    classified = []
    ignored = []
    totals_by_family: dict[str, float] = {}

    for _, row in rows.iterrows():
        amount = abs(float(row.get("monto") or 0.0))
        code = str(row.get("codigo_clasificado") or "")
        item = {
            "account_code": str(row.get("codigo_original") or ""),
            "account_name": str(row.get("nombre_original") or ""),
            "final_code": code if code not in {"", "__EXCLUIR__"} else "",
            "standard_code": code if code not in {"", "__EXCLUIR__"} else "",
            "classification_amount": amount,
            "method": str(row.get("metodo") or ""),
            "confidence": float(row.get("confianza") or 0.0),
            "origen_columna": str(row.get("origen_columna") or ""),
            "es_total": False,
        }
        snapshots.append(dict(item))
        family = _family_for_row(row)
        totals_by_family[family] = totals_by_family.get(family, 0.0) + amount
        if item["final_code"]:
            classified.append(dict(item))
        else:
            ignored.append(dict(item))

    structure = {
        "code_format": StructureDetector.detect_code_format(snapshots),
        "column_layout": StructureDetector.detect_column_layout(snapshots),
        "sections": sorted({
            StructureDetector.detect_section(
                item["account_name"], item["origen_columna"],
            )
            for item in snapshots
            if StructureDetector.detect_section(
                item["account_name"], item["origen_columna"],
            )
        }),
        "detail_rows": sum(
            StructureDetector.detect_type(
                item["account_name"], False, item["classification_amount"],
            ) == "D"
            for item in snapshots
        ),
    }

    structure_data = StructureData(
        family="operational_shadow",
        template=structure["code_format"],
        document_type="balance",
        sections=[{"name": section} for section in structure["sections"]],
        column_layout=structure["column_layout"],
    )
    validation = ValidationData(
        warnings=[] if balance_squared else ["balance_homologado_descuadrado"],
        errors=[] if balance_squared else ["balance_homologado_descuadrado"],
    )
    coverage_result = CoverageCalculator().compute_from_data(
        classified=classified,
        ignored=ignored,
        structure_data=structure_data,
        validation_data=validation,
    )
    # CoverageCalculator infiere sus denominadores desde las clasificadas. Se
    # reemplaza sólo el componente monetario por el mismo motor con el universo
    # completo, evitando que las cuentas sin clasificar produzcan un falso 100%.
    monetary, monetary_issues = MonetaryCoverageCalculator().compute(
        classified, total_by_family=totals_by_family,
    )
    coverage_result.monetary = monetary
    coverage_result.issues = [
        issue for issue in coverage_result.issues
        if issue.issue_type != "unexplained_amount"
    ] + monetary_issues
    weights = coverage_result.weights
    coverage_result.overall = (
        weights.get("monetary", 0.0) * monetary.coverage_pct
        + weights.get("structural", 0.0) * coverage_result.structural.overall
        + weights.get("semantic", 0.0) * coverage_result.semantic.overall
        + weights.get("document", 0.0) * coverage_result.document.coverage_pct
    )
    coverage = coverage_result.to_dict()

    ctx = DocumentContext()
    ctx.set_metadata(DocumentMetadata(layout=structure["column_layout"]), module="operational_shadow")
    ctx.set_structure(structure_data, module="operational_shadow")
    ctx.set_parser(
        ParserData(
            selected_parser="operational_pipeline",
            parser_version="1",
            accounts=classified,
            raw_accounts=snapshots,
            ignored_accounts=ignored,
        ),
        module="operational_shadow",
    )
    ctx.set_knowledge(
        KnowledgeData(dictionary_matches=[
            item for item in classified if "dictionary" in item["method"]
        ]),
        module="operational_shadow",
    )
    ctx.set_validation(validation, module="operational_shadow")
    ctx.set_custom("classified", classified)
    ctx.set_custom("ignored", ignored)
    ctx.set_custom("decisions", [])
    ctx.set_custom("decision_stats", {
        "total": len(snapshots),
        "classified": len(classified),
        "manual_review": len(ignored),
    })
    ctx.set_custom("coverage", coverage)
    SelfQAAdapter().run(ctx)
    self_qa = ctx.get_custom("self_qa", {}) or {}

    reasons = []
    hard_blockers = []
    if ignored:
        reason = f"{len(ignored)} cuenta(s) con saldo sin clasificación"
        reasons.append(reason)
        hard_blockers.append(reason)
    if not balance_squared:
        reason = "el balance homologado no cuadra"
        reasons.append(reason)
        hard_blockers.append(reason)
    critical = sum(
        issue.get("severity") == "CRITICAL"
        for issue in coverage.get("issues", [])
    )
    if critical:
        reason = f"{critical} hallazgo(s) crítico(s) de cobertura"
        reasons.append(reason)
        hard_blockers.append(reason)
    qa_state = str(self_qa.get("approval_state") or "")
    if qa_state in {"MANUAL_REVIEW", "LEARNING", "STRESS"}:
        reasons.append(f"Self-QA recomienda {qa_state.lower().replace('_', ' ')}")
    elif qa_state in {"REJECTED", "FAILED"}:
        reason = f"Self-QA informó {qa_state.lower()}"
        reasons.append(reason)
        hard_blockers.append(reason)
    requires_review = bool(reasons)
    export_allowed = not (enforce_export and hard_blockers)

    return OperationalQualityResult(
        mode="enforced" if enforce_export else "shadow",
        structure=structure,
        coverage=coverage,
        self_qa=self_qa,
        requires_review=requires_review,
        export_allowed=export_allowed,
        reasons=tuple(reasons),
    )
