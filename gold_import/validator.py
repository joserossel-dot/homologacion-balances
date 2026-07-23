from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


CMCC_CODE_PATTERN = re.compile(r"^(AC|ANC|PC|PNC|PAS|PAT|ER)\.\d{2}$")

REQUIRED_COLUMNS = [
    "source_file",
    "account_name",
    "gold_standard_code",
    "gold_standard_name",
    "notes",
]


@dataclass
class ValidationError:
    row: int
    field: str
    message: str
    value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "message": self.message, "value": self.value}


@dataclass
class ValidationResult:
    valid: bool = True
    total_rows: int = 0
    reviewed_rows: int = 0
    unreviewed_rows: int = 0
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cmcc_codes_seen: set[str] = field(default_factory=set)
    filename: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "total_rows": self.total_rows,
            "reviewed_rows": self.reviewed_rows,
            "unreviewed_rows": self.unreviewed_rows,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "cmcc_codes_seen": sorted(self.cmcc_codes_seen),
            "filename": self.filename,
        }


def _v(val: object, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, float) and (math.isnan(val) or val != val):
        return default
    return str(val).strip()


def validate_template(path: str | Path) -> ValidationResult:
    result = ValidationResult(filename=str(path))

    if not Path(path).exists():
        result.valid = False
        result.errors.append(ValidationError(0, "file", f"Archivo no encontrado: {path}"))
        return result

    try:
        df = pd.read_excel(path)
    except Exception as e:
        result.valid = False
        result.errors.append(ValidationError(0, "file", f"Error al leer archivo: {e}"))
        return result

    df.columns = [str(c).strip() for c in df.columns]
    result.total_rows = len(df)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            result.valid = False
            result.errors.append(ValidationError(0, "columns", f"Columna requerida faltante: {col}"))

    if not result.valid:
        return result

    unreviewed = df[df["gold_standard_code"].isna() | (df["gold_standard_code"].astype(str).str.strip() == "")]
    reviewed = df[df["gold_standard_code"].notna() & (df["gold_standard_code"].astype(str).str.strip() != "")]
    result.unreviewed_rows = len(unreviewed)
    result.reviewed_rows = len(reviewed)

    seen_accounts: dict[str, list[int]] = {}
    for idx, row in reviewed.iterrows():
        row_num = idx + 2
        code = _v(row.get("gold_standard_code"))
        name = _v(row.get("account_name"))
        gs_name = _v(row.get("gold_standard_name"))
        notes = _v(row.get("notes"))
        source_file = _v(row.get("source_file"))

        if not CMCC_CODE_PATTERN.match(code):
            result.valid = False
            result.errors.append(ValidationError(
                row_num, "gold_standard_code",
                f"Código inválido: '{code}' — debe ser formato AC.01, PC.02, etc.",
                code,
            ))

        if not gs_name:
            result.warnings.append(
                f"Fila {row_num}: gold_standard_code '{code}' sin gold_standard_name"
            )

        if name and code:
            key = f"{name}::{code}"
            if key in seen_accounts:
                result.warnings.append(
                    f"Fila {row_num}: cuenta duplicada '{name}' con código '{code}' "
                    f"(también en fila {seen_accounts[key][0]})"
                )
            seen_accounts.setdefault(key, []).append(row_num)

        result.cmcc_codes_seen.add(code)

    if len(reviewed) == 0:
        result.warnings.append("No se encontraron filas revisadas (gold_standard_code vacío en todas)")

    return result
