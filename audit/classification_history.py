from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha             TEXT    NOT NULL,
    archivo           TEXT    NOT NULL DEFAULT '',
    cuenta            TEXT    NOT NULL DEFAULT '',
    codigo_original   TEXT    NOT NULL DEFAULT '',
    codigo_homologado TEXT    NOT NULL DEFAULT '',
    metodo            TEXT    NOT NULL DEFAULT '',
    confianza         REAL    NOT NULL DEFAULT 0.0,
    tiempo            REAL    NOT NULL DEFAULT 0.0,
    usuario           TEXT    NOT NULL DEFAULT '',
    corregida         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_history_fecha
    ON classification_history(fecha);

CREATE INDEX IF NOT EXISTS idx_history_archivo
    ON classification_history(archivo);

CREATE INDEX IF NOT EXISTS idx_history_codigo
    ON classification_history(codigo_homologado);
"""


class ClassificationHistoryRecorder:
    def __init__(self, db_path: str | Path = "classification_history.db") -> None:
        self._path = Path(db_path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def record(
        self,
        archivo: str = "",
        cuenta: str = "",
        codigo_original: str = "",
        codigo_homologado: str | None = None,
        metodo: str = "",
        confianza: float = 0.0,
        tiempo: float = 0.0,
        usuario: str = "",
        corregida: bool = False,
        fecha: str | None = None,
    ) -> int:
        if fecha is None:
            fecha = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO classification_history
                (fecha, archivo, cuenta, codigo_original, codigo_homologado,
                 metodo, confianza, tiempo, usuario, corregida)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fecha, archivo, cuenta, codigo_original,
             codigo_homologado or "", metodo, confianza, tiempo, usuario,
             1 if corregida else 0),
        )
        self._conn.commit()
        return self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def mark_corregida(self, record_id: int, corregida: bool = True) -> None:
        self._conn.execute(
            "UPDATE classification_history SET corregida = ? WHERE id = ?",
            (1 if corregida else 0, record_id),
        )
        self._conn.commit()

    def query(
        self,
        limit: int = 100,
        offset: int = 0,
        archivo: str | None = None,
        codigo_homologado: str | None = None,
        corregida: bool | None = None,
        metodo: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if archivo is not None:
            clauses.append("archivo = ?")
            params.append(archivo)
        if codigo_homologado is not None:
            clauses.append("codigo_homologado = ?")
            params.append(codigo_homologado)
        if corregida is not None:
            clauses.append("corregida = ?")
            params.append(1 if corregida else 0)
        if metodo is not None:
            clauses.append("metodo = ?")
            params.append(metodo)
        where = ""
        if clauses:
            where = " WHERE " + " AND ".join(clauses)
        rows = self._conn.execute(
            f"SELECT * FROM classification_history{where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self, archivo: str | None = None) -> int:
        if archivo is not None:
            return self._conn.execute(
                "SELECT COUNT(*) FROM classification_history WHERE archivo = ?",
                (archivo,),
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM classification_history").fetchone()[0]

    def statistics(self) -> dict[str, Any]:
        total = self.count()
        corregidas = self._conn.execute(
            "SELECT COUNT(*) FROM classification_history WHERE corregida = 1"
        ).fetchone()[0]
        avg_confianza = self._conn.execute(
            "SELECT AVG(confianza) FROM classification_history"
        ).fetchone()[0] or 0.0
        metodos = {}
        for row in self._conn.execute(
            "SELECT metodo, COUNT(*) as cnt FROM classification_history GROUP BY metodo ORDER BY cnt DESC"
        ).fetchall():
            metodos[row["metodo"]] = row["cnt"]
        return {
            "total": total,
            "corregidas": corregidas,
            "tasa_correccion": round(corregidas / total, 4) if total else 0.0,
            "confianza_promedio": round(avg_confianza, 4),
            "metodos": metodos,
        }
