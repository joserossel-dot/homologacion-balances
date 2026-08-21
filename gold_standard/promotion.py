"""gold_standard/promotion.py — Promoción de feedback humano al gold runtime.

Cierra el loop de aprendizaje (M-3 / F3.1) sin tocar el benchmark:

  - Lee revisiones humanas (gold_records con final_code != '') de la DB fuente.
  - Valida, normaliza y resuelve conflictos.
  - Escribe SOLO en la DB runtime (gold_standard_runtime.db), nunca en la DB
    del benchmark (gold_standard.db).

Restricciones P1.1 respetadas:
  - No modifica learning/engine.py ni el algoritmo de clasificación.
  - El benchmark (2660/2662) queda congelado: esta módulo no lo escribe.

Uso:
    python3 -m gold_standard.promotion --dry-run
    python3 -m gold_standard.promotion --apply
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gold_standard.runtime import BENCHMARK_DB, RUNTIME_DB_DEFAULT, RuntimeGoldStorage
from learning.exact_match import normalize_name

logger = logging.getLogger(__name__)

RESERVED_TOKENS = {"total"}


@dataclass
class PromotionResult:
    """Resultado de un dry-run o de una aplicación de promoción."""

    candidates: int = 0
    promotable: int = 0
    promoted: int = 0
    duplicates: int = 0
    conflicts: int = 0
    reserved: int = 0
    empty_code: int = 0
    errors: int = 0
    dry_run: bool = True
    conflict_details: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": self.candidates,
            "promotable": self.promotable,
            "promoted": self.promoted,
            "duplicates": self.duplicates,
            "conflicts": self.conflicts,
            "reserved": self.reserved,
            "empty_code": self.empty_code,
            "errors": self.errors,
            "dry_run": self.dry_run,
            "conflict_details": self.conflict_details,
        }


def _fetch_candidates(source_conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Registros de gold_records de la DB fuente (feedback humano)."""
    try:
        return source_conn.execute(
            "SELECT id, account_name, final_code, reviewer, review_date "
            "FROM gold_records ORDER BY id"
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def _classify(
    row: sqlite3.Row,
    runtime: RuntimeGoldStorage,
    *,
    reviewer_filter: str | None = None,
) -> dict[str, Any]:
    """Clasifica un candidato: empty_code / reserved / duplicate / conflict / promotable."""
    if reviewer_filter and row["reviewer"] != reviewer_filter:
        return {"status": "skip_reviewer"}

    final_code = (row["final_code"] or "").strip()
    name = (row["account_name"] or "").strip()
    if not final_code or not name:
        return {"status": "empty_code"}

    norm = normalize_name(name)
    if not norm:
        return {"status": "empty_code"}

    if any(token in norm.split() for token in RESERVED_TOKENS):
        return {"status": "reserved", "norm": norm}

    existing = runtime.connection.execute(
        "SELECT codigo_estandar FROM gold_standard WHERE normalized = ?",
        (norm,),
    ).fetchall()
    existing_codes = {r[0] for r in existing}
    if existing_codes:
        if final_code in existing_codes:
            return {"status": "duplicate", "norm": norm, "code": final_code}
        return {
            "status": "conflict",
            "norm": norm,
            "code": final_code,
            "existing_codes": sorted(existing_codes),
            "name": name,
        }
    return {"status": "promotable", "norm": norm}


def promote(
    source_db: str | Path = BENCHMARK_DB,
    runtime_db: str | Path = RUNTIME_DB_DEFAULT,
    *,
    dry_run: bool = True,
    reviewer_filter: str | None = None,
) -> PromotionResult:
    """Promueve revisiones humanas de source_db a la DB runtime.

    ``dry_run=True`` solo clasifica y cuenta; ``dry_run=False`` inserta.
    Nunca modifica source_db (es la DB del benchmark).
    """
    result = PromotionResult(dry_run=dry_run)

    source_path = Path(source_db)
    if not source_path.exists():
        logger.warning("DB fuente no encontrada: %s", source_db)
        return result

    source_conn = sqlite3.connect(str(source_path))
    source_conn.row_factory = sqlite3.Row
    candidates = _fetch_candidates(source_conn)
    result.candidates = len(candidates)

    runtime_exists = Path(runtime_db).exists()
    if runtime_exists:
        runtime = RuntimeGoldStorage(runtime_db)
    elif dry_run:
        # dry-run sobre runtime inexistente: tratar como vacío sin crear el archivo
        runtime = RuntimeGoldStorage(":memory:")
    else:
        runtime = RuntimeGoldStorage(runtime_db)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    promoted_ids: list[tuple[int, str, str, str, str]] = []
    for row in candidates:
        cls = _classify(
            row, runtime, reviewer_filter=reviewer_filter,
        )
        status = cls["status"]
        if status == "skip_reviewer":
            continue
        if status == "empty_code":
            result.empty_code += 1
            continue
        if status == "reserved":
            result.reserved += 1
            continue
        if status == "duplicate":
            result.duplicates += 1
            continue
        if status == "conflict":
            result.conflicts += 1
            result.conflict_details.append({
                "name": cls["name"],
                "candidate_code": cls["code"],
                "existing_codes": ", ".join(cls["existing_codes"]),
            })
            continue
        # promotable
        result.promotable += 1
        promoted_ids.append((
            row["id"], row["account_name"], row["final_code"],
            row["reviewer"] or "", row["review_date"] or "",
        ))

    if not dry_run:
        for source_id, name, code, reviewer, review_date in promoted_ids:
            try:
                runtime.connection.execute(
                    """
                    INSERT OR IGNORE INTO gold_standard
                        (codigo_estandar, nombre_cuenta, normalized,
                         source_record_id, reviewer, review_date, promoted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (code, name, normalize_name(name), source_id,
                     reviewer, review_date, now),
                )
                result.promoted += 1
            except sqlite3.IntegrityError as e:
                logger.warning("Error promoviendo '%s' -> %s: %s", name, code, e)
                result.errors += 1
        runtime.connection.commit()
    else:
        result.promoted = result.promotable

    runtime.close()
    source_conn.close()
    return result


def _print_result(result: PromotionResult, action: str) -> None:
    print("=" * 56)
    print(f"PROMOCIÓN ({action})")
    print("=" * 56)
    print(f"  Candidatos (gold_records con final_code != ''): {result.candidates}")
    print(f"  Promovibles:                                   {result.promotable}")
    print(f"  Promovidos (a runtime):                        {result.promoted}")
    print(f"  Duplicados (ya en runtime):                    {result.duplicates}")
    print(f"  Conflictos (mismo normalized, código distinto): {result.conflicts}")
    print(f"  Palabra reservada (total):                     {result.reserved}")
    print(f"  Sin código corregido:                          {result.empty_code}")
    print(f"  Errores:                                       {result.errors}")
    if result.conflict_details:
        print("\n  CONFLICTOS:")
        for c in result.conflict_details:
            print(f"    - {c['name']}: candidato={c['candidate_code']} "
                  f"gold={c['existing_codes']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promueve feedback humano al gold runtime (sin tocar benchmark)."
    )
    parser.add_argument("--source-db", default=BENCHMARK_DB, help="DB fuente (solo lectura)")
    parser.add_argument("--runtime-db", default=RUNTIME_DB_DEFAULT, help="DB runtime destino")
    parser.add_argument("--reviewer", default=None, help="Filtro por reviewer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Clasifica sin escribir")
    group.add_argument("--apply", action="store_true", help="Escribe en la DB runtime")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = promote(
        args.source_db,
        args.runtime_db,
        dry_run=not args.apply,
        reviewer_filter=args.reviewer,
    )
    _print_result(result, "APPLY" if args.apply else "DRY-RUN")
    if args.apply:
        print("\n  La DB del benchmark NO fue modificada (solo lectura).")


if __name__ == "__main__":
    main()
