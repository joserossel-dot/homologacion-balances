"""Repositorio transaccional de catalogo, diccionario y validaciones en Neon."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable


def normalize_account_name(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


class NeonKnowledgeStore:
    """Acceso sincrono usado por Streamlit; no abre conexiones al importar."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", "")
        self._connect_override = connect

    @property
    def enabled(self) -> bool:
        return bool(self.database_url)

    def _connect(self):
        if not self.enabled:
            raise RuntimeError("DATABASE_URL no configurada")
        if self._connect_override is not None:
            return self._connect_override(self.database_url)
        try:
            import psycopg2
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise RuntimeError("psycopg2-binary no esta instalado") from exc
        return psycopg2.connect(self.database_url, connect_timeout=5)

    def _execute_many(self, cursor, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if self._connect_override is not None:
            cursor.executemany(sql, rows)
            return
        from psycopg2.extras import execute_batch
        execute_batch(cursor, sql, rows, page_size=250)

    def initialize(self, migration: str | Path | None = None) -> None:
        path = Path(migration) if migration else (
            Path(__file__).resolve().parent.parent / "migrations" / "001_neon_knowledge.sql"
        )
        sql = path.read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)

    def healthcheck(self) -> bool:
        if not self.enabled:
            return False
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return cursor.fetchone()[0] == 1
        except Exception:
            return False

    def load_catalog(self) -> dict[str, dict[str, Any]]:
        query = """SELECT codigo_estandar, nombre_estandar, categoria, tipo_estado,
                   naturaleza, signo_normal, es_deuda_financiera,
                   es_activo_liquido, afecta_ebitda
                   FROM catalogo_maestro WHERE activo ORDER BY codigo_estandar"""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                columns = [item[0] for item in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {row["codigo_estandar"]: row for row in rows}

    def load_dictionary(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT cuenta_original, codigo_estandar, fuente "
                    "FROM diccionario_homologacion WHERE activo ORDER BY cuenta_original"
                )
                return [
                    {"cuenta_original": row[0], "codigo_estandar": row[1], "fuente": row[2]}
                    for row in cursor.fetchall()
                ]

    def seed(
        self,
        catalog: dict[str, dict[str, Any]],
        dictionary: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Carga inicial repetible; actualiza entradas existentes sin duplicarlas."""
        catalog_rows = []
        for code, raw in catalog.items():
            row = {**raw, "codigo_estandar": raw.get("codigo_estandar", code)}
            catalog_rows.append((
                row["codigo_estandar"], row["nombre_estandar"], row["categoria"],
                row["tipo_estado"], row["naturaleza"], row.get("signo_normal", 1),
                row.get("es_deuda_financiera", False),
                row.get("es_activo_liquido", False), row.get("afecta_ebitda", False),
            ))
        valid_codes = {row[0] for row in catalog_rows}
        dictionary_rows = [
            (
                row["cuenta_original"], normalize_account_name(row["cuenta_original"]),
                row["codigo_estandar"], row.get("fuente", "seed_json"),
            )
            for row in dictionary
            if row.get("codigo_estandar") in valid_codes
        ]
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._execute_many(cursor,
                    """INSERT INTO catalogo_maestro
                       (codigo_estandar, nombre_estandar, categoria, tipo_estado,
                        naturaleza, signo_normal, es_deuda_financiera,
                        es_activo_liquido, afecta_ebitda)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (codigo_estandar) DO UPDATE SET
                         nombre_estandar=EXCLUDED.nombre_estandar,
                         categoria=EXCLUDED.categoria, tipo_estado=EXCLUDED.tipo_estado,
                         naturaleza=EXCLUDED.naturaleza, signo_normal=EXCLUDED.signo_normal,
                         es_deuda_financiera=EXCLUDED.es_deuda_financiera,
                         es_activo_liquido=EXCLUDED.es_activo_liquido,
                         afecta_ebitda=EXCLUDED.afecta_ebitda, activo=TRUE""",
                    catalog_rows,
                )
                self._execute_many(cursor,
                    """INSERT INTO diccionario_homologacion
                       (cuenta_original, cuenta_normalizada, codigo_estandar, fuente)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (cuenta_normalizada) DO UPDATE SET
                         cuenta_original=EXCLUDED.cuenta_original,
                         codigo_estandar=EXCLUDED.codigo_estandar,
                         fuente=EXCLUDED.fuente, activo=TRUE, actualizado_en=NOW()""",
                    dictionary_rows,
                )
        return len(catalog_rows), len(dictionary_rows)

    def save_validation(
        self,
        *,
        account_name: str,
        validated_code: str,
        source: str,
        suggested_code: str | None = None,
        suggested_method: str | None = None,
        suggested_confidence: float | None = None,
        reviewer: str = "analista",
        source_file: str = "",
        add_to_dictionary: bool = True,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._save_validation_cursor(cursor, {
                    "account_name": account_name, "validated_code": validated_code,
                    "source": source, "suggested_code": suggested_code,
                    "suggested_method": suggested_method,
                    "suggested_confidence": suggested_confidence,
                    "reviewer": reviewer, "source_file": source_file,
                    "add_to_dictionary": add_to_dictionary,
                })

    def save_validations(self, validations: list[dict[str, Any]]) -> None:
        """Guarda un lote completo usando una sola conexión y transacción."""
        if not validations:
            return
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for validation in validations:
                    self._save_validation_cursor(cursor, validation)

    @staticmethod
    def _save_validation_cursor(cursor, validation: dict[str, Any]) -> None:
        account_name = validation["account_name"]
        validated_code = validation["validated_code"]
        source = validation["source"]
        suggested_code = validation.get("suggested_code")
        suggested_method = validation.get("suggested_method")
        suggested_confidence = validation.get("suggested_confidence")
        reviewer = validation.get("reviewer", "analista")
        source_file = validation.get("source_file", "")
        normalized = normalize_account_name(account_name)
        if validation.get("add_to_dictionary", True):
            cursor.execute(
                "SELECT codigo_estandar FROM diccionario_homologacion "
                "WHERE cuenta_normalizada = %s FOR UPDATE",
                (normalized,),
            )
            previous_row = cursor.fetchone()
            previous_code = previous_row[0] if previous_row else None
            cursor.execute(
                """INSERT INTO diccionario_homologacion
                   (cuenta_original, cuenta_normalizada, codigo_estandar,
                    fuente, validado_humano, validado_por, validado_en)
                   VALUES (%s, %s, %s, %s, TRUE, %s, NOW())
                   ON CONFLICT (cuenta_normalizada) DO UPDATE SET
                     cuenta_original = EXCLUDED.cuenta_original,
                     codigo_estandar = EXCLUDED.codigo_estandar,
                     fuente = EXCLUDED.fuente,
                     validado_humano = TRUE,
                     validado_por = EXCLUDED.validado_por,
                     validado_en = NOW(),
                     frecuencia_uso = diccionario_homologacion.frecuencia_uso + 1,
                     activo = TRUE,
                     actualizado_en = NOW()""",
                (account_name, normalized, validated_code, source, reviewer),
            )
            if previous_code != validated_code:
                cursor.execute(
                    """INSERT INTO historial_diccionario
                       (cuenta_original, cuenta_normalizada, codigo_anterior,
                        codigo_nuevo, accion, validado_por, archivo_origen)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        account_name, normalized, previous_code, validated_code,
                        "INSERT" if previous_code is None else "UPDATE",
                        reviewer, source_file,
                    ),
                )
        cursor.execute(
            """INSERT INTO log_validaciones
               (cuenta_original, cuenta_normalizada, codigo_sugerido, codigo_validado,
                metodo_sugerido, confianza_sugerida, fue_correccion,
                validado_por, archivo_origen)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                account_name, normalized, suggested_code, validated_code,
                suggested_method, suggested_confidence,
                bool(suggested_code and suggested_code != validated_code),
                reviewer, source_file,
            ),
        )

    def save_catalog_entry(self, entry: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO catalogo_maestro
                       (codigo_estandar, nombre_estandar, categoria, tipo_estado,
                        naturaleza, signo_normal, es_deuda_financiera,
                        es_activo_liquido, afecta_ebitda)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (codigo_estandar) DO UPDATE SET
                         nombre_estandar=EXCLUDED.nombre_estandar,
                         categoria=EXCLUDED.categoria, tipo_estado=EXCLUDED.tipo_estado,
                         naturaleza=EXCLUDED.naturaleza, signo_normal=EXCLUDED.signo_normal,
                         es_deuda_financiera=EXCLUDED.es_deuda_financiera,
                         es_activo_liquido=EXCLUDED.es_activo_liquido,
                         afecta_ebitda=EXCLUDED.afecta_ebitda, activo=TRUE""",
                    (
                        entry["codigo_estandar"], entry["nombre_estandar"],
                        entry["categoria"], entry["tipo_estado"], entry["naturaleza"],
                        entry.get("signo_normal", 1),
                        entry.get("es_deuda_financiera", False),
                        entry.get("es_activo_liquido", False),
                        entry.get("afecta_ebitda", False),
                    ),
                )

    def learning_statistics(self) -> dict[str, int]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT
                       (SELECT COUNT(*) FROM catalogo_maestro WHERE activo),
                       (SELECT COUNT(*) FROM diccionario_homologacion WHERE activo),
                       (SELECT COUNT(*) FROM diccionario_homologacion
                        WHERE activo AND validado_humano),
                       (SELECT COUNT(*) FROM log_validaciones),
                       (SELECT COUNT(*) FROM log_validaciones WHERE fue_correccion)"""
                )
                row = cursor.fetchone()
        return {
            "catalog_entries": int(row[0]),
            "dictionary_entries": int(row[1]),
            "human_learned": int(row[2]),
            "validations": int(row[3]),
            "corrections": int(row[4]),
        }

    def recent_validations(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT cuenta_original, codigo_sugerido, codigo_validado,
                       metodo_sugerido, confianza_sugerida, fue_correccion,
                       validado_por, archivo_origen, creado_en
                       FROM log_validaciones ORDER BY creado_en DESC LIMIT %s""",
                    (safe_limit,),
                )
                rows = cursor.fetchall()
        keys = (
            "cuenta_original", "codigo_sugerido", "codigo_validado",
            "metodo_sugerido", "confianza_sugerida", "fue_correccion",
            "validado_por", "archivo_origen", "creado_en",
        )
        return [dict(zip(keys, row)) for row in rows]

    def conflicts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT cuenta_normalizada,
                       MIN(cuenta_original) AS cuenta_original,
                       ARRAY_AGG(DISTINCT codigo_validado ORDER BY codigo_validado) AS codigos,
                       COUNT(*) AS validaciones
                       FROM log_validaciones
                       WHERE cuenta_normalizada IS NOT NULL
                       GROUP BY cuenta_normalizada
                       HAVING COUNT(DISTINCT codigo_validado) > 1
                       ORDER BY COUNT(*) DESC, cuenta_normalizada"""
                )
                rows = cursor.fetchall()
        return [
            {"cuenta_normalizada": row[0], "cuenta_original": row[1],
             "codigos": list(row[2]), "validaciones": int(row[3])}
            for row in rows
        ]

    def dictionary_history(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT id, cuenta_original, cuenta_normalizada, codigo_anterior,
                       codigo_nuevo, accion, validado_por, archivo_origen, creado_en
                       FROM historial_diccionario ORDER BY id DESC LIMIT %s""",
                    (safe_limit,),
                )
                rows = cursor.fetchall()
        keys = ("id", "cuenta_original", "cuenta_normalizada", "codigo_anterior",
                "codigo_nuevo", "accion", "validado_por", "archivo_origen", "creado_en")
        return [dict(zip(keys, row)) for row in rows]

    def rollback_dictionary_change(self, history_id: int, reviewer: str = "analista") -> bool:
        """Revierte solo si el cambio seleccionado sigue siendo el estado vigente."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT cuenta_original, cuenta_normalizada, codigo_anterior, codigo_nuevo
                       FROM historial_diccionario WHERE id = %s FOR UPDATE""",
                    (int(history_id),),
                )
                change = cursor.fetchone()
                if not change:
                    return False
                account_name, normalized, previous_code, new_code = change
                cursor.execute(
                    "SELECT codigo_estandar FROM diccionario_homologacion "
                    "WHERE cuenta_normalizada = %s FOR UPDATE",
                    (normalized,),
                )
                current = cursor.fetchone()
                if not current or current[0] != new_code:
                    return False
                if previous_code is None:
                    cursor.execute(
                        "UPDATE diccionario_homologacion SET activo=FALSE, actualizado_en=NOW() "
                        "WHERE cuenta_normalizada=%s",
                        (normalized,),
                    )
                else:
                    cursor.execute(
                        """UPDATE diccionario_homologacion SET codigo_estandar=%s,
                           activo=TRUE, actualizado_en=NOW()
                           WHERE cuenta_normalizada=%s""",
                        (previous_code, normalized),
                    )
                cursor.execute(
                    """INSERT INTO historial_diccionario
                       (cuenta_original, cuenta_normalizada, codigo_anterior,
                        codigo_nuevo, accion, validado_por)
                       VALUES (%s, %s, %s, %s, 'ROLLBACK', %s)""",
                    (account_name, normalized, new_code, previous_code, reviewer),
                )
        return True
