"""gold_standard/runtime.py — Base de conocimiento runtime (Learning Loop).

Separación de responsabilidades (ver reports/product/P1_learning_loop_design.md):

  - gold_standard_benchmark  -> dataset congelado del benchmark (NO se modifica).
  - gold_standard_runtime    -> conocimiento en evolución (la escribe la promoción).

El schema de la tabla ``gold_standard`` replica la tabla del benchmark y agrega
columnas de proveniencia (source_record_id, reviewer, review_date, promoted_at)
para trazabilidad del feedback humano.

Este módulo NO toca la DB del benchmark. Solo crea/abre la DB runtime.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

RUNTIME_DB_DEFAULT = "gold_standard_runtime.db"
BENCHMARK_DB = "gold_standard.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gold_standard (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estandar TEXT NOT NULL,
    nombre_cuenta   TEXT NOT NULL,
    normalized      TEXT NOT NULL,
    source_record_id INTEGER NOT NULL DEFAULT 0,
    reviewer        TEXT NOT NULL DEFAULT '',
    review_date     TEXT NOT NULL DEFAULT '',
    promoted_at     TEXT NOT NULL DEFAULT ''
);
"""

_INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_gold_norm_code
    ON gold_standard(normalized, codigo_estandar);
CREATE INDEX IF NOT EXISTS idx_runtime_gold_source
    ON gold_standard(source_record_id);
"""


class RuntimeGoldStorage:
    """Abre y valida la DB runtime del gold standard.

    Puede operar sobre una DB nueva o existente (crea schema si falta).
    """

    def __init__(self, db_path: str | Path = RUNTIME_DB_DEFAULT) -> None:
        self._path = Path(db_path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.executescript(_INDEXES)
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM gold_standard").fetchone()[0]

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM gold_standard ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> RuntimeGoldStorage:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
