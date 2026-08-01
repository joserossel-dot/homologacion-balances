"""Validador de perfiles aprendidos (Sprint 35).

Compara el `TableProfile` aprendido contra TODOS los documentos de la
familia y calcula:

  - cobertura (coverage):  fracción de filas contables dentro de la región
    de tabla predicha por el perfil
  - precisión (precision): fracción de la región de tabla que son filas
    contables reales
  - columnas detectadas:   cuántas columnas del perfil se encuentran en
    cada documento (código, nombre, activo, pasivo, pérdidas, ganancias,
    débitos, créditos, ...)
  - filas perdidas:        filas contables que el perfil no cubre

El resultado se agrega por familia y se almacena en `profile.validation`.
"""

from __future__ import annotations

from typing import Any, Optional

from .profile import TableProfile
from .trainer import TableProfileTrainer, _count_amounts


class ProfileValidator:
    """Valida un TableProfile contra los documentos de la familia."""

    def __init__(self, trainer: Optional[TableProfileTrainer] = None):
        self._trainer = trainer or TableProfileTrainer()

    # ------------------------------------------------------------------
    # Por documento
    # ------------------------------------------------------------------

    def validate_document(self, profile: TableProfile, document) -> dict[str, Any]:
        """Métricas de un documento contra el perfil."""
        s = self._trainer.analyze_document(document)
        if not s.get("valid"):
            return {
                "valid": False, "account_rows": 0, "rows_in_table": 0,
                "rows_lost": 0, "coverage": 0.0, "precision": 0.0,
                "columns_expected": len(profile.columns),
                "columns_detected": 0, "columns_rate": 0.0,
                "header_match": False, "header_rows": 0, "amount_mode": 0,
            }

        rows = s["rows"]
        total = len(rows)
        start = profile.table_start_row
        end = profile.table_end_row
        region = [r["i"] for r in rows if start <= r["i"] <= end]
        region_count = len(region)
        region_size = max(end - start + 1, 0)

        coverage = region_count / total if total else 0.0
        precision = region_count / region_size if region_size else 0.0
        rows_lost = total - region_count

        detected = 0
        for col in profile.columns:
            if col.key == "CODIGO":
                found = bool(s.get("has_codes"))
            elif col.key == "NOMBRE":
                found = total > 0
            else:
                p = col.position or 1
                found = any(_count_amounts(r["tokens"]) >= p for r in rows)
            if found:
                detected += 1
        expected = len(profile.columns)
        column_rate = detected / expected if expected else 1.0

        header_match = s.get("header_rows", 0) == profile.header_rows

        return {
            "valid": True,
            "account_rows": total,
            "rows_in_table": region_count,
            "rows_lost": rows_lost,
            "coverage": round(coverage, 4),
            "precision": round(precision, 4),
            "columns_expected": expected,
            "columns_detected": detected,
            "columns_rate": round(column_rate, 4),
            "header_match": header_match,
            "header_rows": s.get("header_rows", 0),
            "amount_mode": s.get("amount_mode", 0),
        }

    # ------------------------------------------------------------------
    # Por familia
    # ------------------------------------------------------------------

    def validate(self, profile: TableProfile, documents: list) -> dict[str, Any]:
        """Agrega las métricas de todos los documentos de la familia."""
        results = [self.validate_document(profile, d) for d in documents]
        valid = [r for r in results if r.get("valid")]
        n = len(valid)

        if n == 0:
            return {
                "docs_validated": 0, "docs_with_rows": 0,
                "coverage": 0.0, "precision": 0.0,
                "columns_rate": 0.0, "columns_detected": 0,
                "columns_expected": len(profile.columns),
                "total_account_rows": 0, "total_rows_in_table": 0,
                "total_rows_lost": 0, "header_match_rate": 0.0,
            }

        total_rows = sum(r["account_rows"] for r in valid)
        total_in_table = sum(r["rows_in_table"] for r in valid)
        docs_with_rows = sum(1 for r in valid if r["account_rows"] > 0)

        return {
            "docs_validated": n,
            "docs_with_rows": docs_with_rows,
            "coverage": round(
                sum(r["coverage"] for r in valid) / n, 4,
            ),
            "precision": round(
                sum(r["precision"] for r in valid) / n, 4,
            ),
            "columns_rate": round(
                sum(r["columns_rate"] for r in valid) / n, 4,
            ),
            "columns_detected": round(
                sum(r["columns_detected"] for r in valid) / n, 2,
            ),
            "columns_expected": len(profile.columns),
            "total_account_rows": total_rows,
            "total_rows_in_table": total_in_table,
            "total_rows_lost": total_rows - total_in_table,
            "header_match_rate": round(
                sum(1 for r in valid if r["header_match"]) / n, 4,
            ),
        }
