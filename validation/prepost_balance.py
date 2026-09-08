"""Adaptador seguro entre el cuadre documental temprano y el homologado."""
from __future__ import annotations

from typing import Any, Iterable


def early_balance_state(certification: Any, tolerance: float = 1000.0) -> dict[str, Any]:
    if certification is None:
        return {"available": False, "squared": None, "difference": None}
    validated = getattr(certification, "totales_finales_validos", None)
    differences = getattr(certification, "diferencias", None) or {}
    difference = differences.get("activo_menos_pasivo_patrimonio")
    if validated is None and difference is None:
        return {"available": False, "squared": None, "difference": None}
    squared = bool(validated) if validated is not None else abs(float(difference)) <= tolerance
    return {"available": True, "squared": squared,
            "difference": float(difference or 0.0)}


def _late_coefficient(code: str) -> int:
    if code.startswith(("AC.", "ANC.")): return 1
    if code.startswith(("PC.", "PNC.", "PAT.")): return -1
    return 0


def _early_coefficient(nature: str) -> int:
    value = str(nature or "").lower()
    if "activo" in value: return 1
    if "pasivo" in value or "patrimonio" in value: return -1
    return 0


def compare_pre_post(certification: Any, accounts: Iterable[dict[str, Any]],
                     late_difference: float | None = None,
                     tolerance: float = 1000.0) -> dict[str, Any]:
    early = early_balance_state(certification, tolerance)
    responsible = []
    derived_late = 0.0
    for row in accounts:
        if row.get("es_total") or row.get("is_total"):
            continue
        amount = float(row.get("classification_amount", row.get("monto", 0)) or 0)
        code = str(row.get("final_code") or row.get("standard_code")
                   or row.get("codigo_clasificado") or "")
        nature = row.get("nature") or row.get("origen_columna_efectiva") or row.get("origen_columna")
        early_coef = _early_coefficient(str(nature))
        late_coef = _late_coefficient(code)
        derived_late += late_coef * amount
        impact = (late_coef - early_coef) * amount
        if abs(impact) > 0.01:
            responsible.append({
                "account": row.get("account_name") or row.get("nombre_original", ""),
                "code": code, "method": row.get("method") or row.get("metodo", ""),
                "amount": amount, "impact": impact,
                "reason": "La categoría homologada cambia o elimina el lado contable extraído",
            })
    late_difference = float(derived_late if late_difference is None else late_difference)
    late_squared = abs(late_difference) <= tolerance
    degradation = bool(early["available"] and early["squared"] and not late_squared)
    return {"early": early, "late": {"squared": late_squared, "difference": late_difference},
            "classification_degradation": degradation,
            "responsible_changes": sorted(responsible, key=lambda row: abs(row["impact"]), reverse=True)}
