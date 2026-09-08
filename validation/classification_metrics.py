"""Contrato canónico de métricas de clasificación y familias documentales."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

SPECIFIC_CLASSIFICATION_METHODS = frozenset({
    "code", "audited_statement_label", "hierarchy_inheritance",
    "dictionary_exact", "dictionary_fuzzy", "learning_exact", "learning_fuzzy",
    "regex_fallback", "semantic_exact", "semantic_high", "cmcc",
    "validacion_humana", "validacion_humana_lote", "manual_revision",
    "propagado_automático", "validacion_humana_propagada",
    # Motor local histórico. La equivalencia es explícita y no depende de confianza.
    "codigo", "diccionario_exacto", "diccionario_fuzzy", "regla_regex",
    "columna_ambiguo",
})
RESIDUAL_CLASSIFICATION_METHODS = frozenset({
    "origin_fallback", "regex_contextual", "decision_conflict",
    "decision_unknown", "semantic_unknown", "unknown", "",
})
CONTROL_METHODS = frozenset({"control", "subtotal", "total"})


def method_provenance(method: str | None) -> str:
    value = str(method or "unclassified").strip().lower()
    base = value.split("+", 1)[0]
    if (value == "unclassified" or value.startswith(("unclassified_", "sin_clasificar"))
            or value == "movement_only"):
        return "unclassified"
    if value in RESIDUAL_CLASSIFICATION_METHODS or base in RESIDUAL_CLASSIFICATION_METHODS:
        return "residual"
    if value in CONTROL_METHODS or base in CONTROL_METHODS:
        return "control"
    if value.startswith(("decision_", "semantic_", "learning_")):
        return "specific"
    if value in SPECIFIC_CLASSIFICATION_METHODS or base in SPECIFIC_CLASSIFICATION_METHODS:
        return "specific"
    return "residual"


def account_metrics(accounts: Iterable[dict[str, Any]], controls: int = 0) -> dict[str, int]:
    rows = list(accounts)
    specific = residual = unclassified = pending = 0
    for row in rows:
        is_control = bool(row.get("es_total") or row.get("is_total"))
        if is_control:
            controls += 1
            continue
        code = row.get("final_code") or row.get("standard_code") or row.get("codigo_clasificado")
        provenance = method_provenance(row.get("method") or row.get("metodo"))
        if code == "__EXCLUIR__":
            continue
        requires_review = bool(row.get("review_required") or row.get("requiere_revision"))
        if requires_review or not code or provenance in {"residual", "unclassified"}:
            pending += 1
        if not code:
            unclassified += 1
        elif provenance in {"residual", "unclassified"}:
            residual += 1
        else:
            specific += 1
    detail = specific + residual + unclassified
    return {
        "accounts_classified_specific": specific,
        "accounts_classified_residual": residual,
        "accounts_unclassified": unclassified,
        "accounts_pending_review": pending,
        "accounts_controls": controls,
        "accounts_total_detail": detail,
        # Compatibilidad explícita: clasificada significa código asignado,
        # incluyendo categorías residuales, pero excluyendo controles.
        "accounts_classified": specific + residual,
    }


def document_family(file_entry: dict[str, Any], accounts: Iterable[dict[str, Any]]) -> str:
    rows = [
        row for row in accounts
        if not (row.get("es_total") or row.get("is_total"))
        and (row.get("final_code") or row.get("standard_code")
             or row.get("codigo_clasificado")) != "__EXCLUIR__"
    ]
    if bool(file_entry.get("ocr") or file_entry.get("requirio_ocr")):
        return "ocr_scanned"
    if any(str(row.get("account_code") or row.get("codigo_original") or "").strip()
           for row in rows):
        return "coded_balance"
    return "ifrs_no_code"


def family_metrics(files: Iterable[dict[str, Any]], accounts: Iterable[dict[str, Any]]) -> dict[str, dict]:
    file_rows = list(files)
    account_rows = list(accounts)
    output: dict[str, dict] = {}
    for file_entry in file_rows:
        source = file_entry.get("source_file", "")
        rows = [row for row in account_rows if row.get("source_file", "") == source]
        family = file_entry.get("document_family") or document_family(file_entry, rows)
        target = output.setdefault(family, {"documents": 0, "methods": Counter()})
        target["documents"] += 1
        target["methods"].update(
            str(row.get("method") or row.get("metodo") or "unknown")
            for row in rows
            if not (row.get("es_total") or row.get("is_total"))
            and (row.get("final_code") or row.get("standard_code")
                 or row.get("codigo_clasificado")) != "__EXCLUIR__"
        )
        controls_in_rows = sum(
            1 for row in rows if row.get("es_total") or row.get("is_total")
        )
        reported_controls = int(file_entry.get("accounts_controls", 0))
        counts = account_metrics(rows, max(reported_controls - controls_in_rows, 0))
        for key, value in counts.items():
            target[key] = target.get(key, 0) + value
    for target in output.values():
        target["methods"] = dict(target["methods"])
        total = target.get("accounts_total_detail", 0)
        target["specific_coverage"] = round(
            target.get("accounts_classified_specific", 0) / total, 4
        ) if total else 1.0
        target["assigned_coverage"] = round(
            target.get("accounts_classified", 0) / total, 4
        ) if total else 1.0
    return output
