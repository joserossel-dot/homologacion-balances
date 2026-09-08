"""Repositorio transaccional de catalogo, diccionario y validaciones en Neon."""

from __future__ import annotations

import os
import re
import unicodedata
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from catalog_aliases import (
    canonical_catalog_code, canonicalize_catalog, canonicalize_dictionary,
)
from persistence.contracts.promotions import PromotionOutcomeRecord, PromotionPolicyRecord
from persistence.promotion_metadata import (
    promotion_outcome_fingerprint,
    promotion_outcome_payload,
    promotion_record_fingerprint,
    promotion_record_payload,
    validate_promotion_policy_record,
    validate_promotion_outcome,
)


def normalize_account_name(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def _reject_policy_promotion_through_validation(source: str) -> None:
    """Evita usar el camino heredado, con reviewer implícito, como promoción."""
    tokens = set(normalize_account_name(source).split())
    if tokens.intersection({"promotion", "promocion", "manual", "supervisor"}) and (
        "promotion" in tokens
        or "promocion" in tokens
        or {"manual", "supervisor"}.issubset(tokens)
    ):
        raise ValueError(
            "Una promoción debe usar save_promotion_policy_metadata con actor "
            "supervisor y organización explícitos"
        )


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

    def initialize_promotion_policy_metadata(
        self, migration: str | Path | None = None,
    ) -> None:
        """Aplica explícitamente la migración de metadata de promociones."""
        path = Path(migration) if migration else (
            Path(__file__).resolve().parent
            / "migrations"
            / "003_promotion_policy_metadata.sql"
        )
        sql = path.read_text(encoding="utf-8")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)

    def initialize_promotion_outcomes(
        self, migration: str | Path | None = None,
    ) -> None:
        """Aplica explícitamente la migración append-only de outcomes."""
        if migration:
            paths = [Path(migration)]
        else:
            root = Path(__file__).resolve().parent / "migrations"
            paths = [
                root / "004_promotion_outcomes.sql",
                root / "005_promotion_outcome_batches.sql",
            ]
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for path in paths:
                    cursor.execute(path.read_text(encoding="utf-8"))

    def save_promotion_policy_metadata(
        self, record: PromotionPolicyRecord,
    ) -> PromotionPolicyRecord:
        """Persiste sólo evidencia de política, nunca cambia el estado de cola.

        No acepta un reviewer por defecto. El registro debe contener actor
        supervisor explícito, rol y organización, construidos por el contrato
        de identidad.
        """
        validate_promotion_policy_record(record)
        fingerprint = promotion_record_fingerprint(record)
        payload = promotion_record_payload(record)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO promotion_policy_metadata
                       (evaluation_id, subject_id, policy_mode, decision_allowed,
                        decision_reasons, evidence, supervisor_actor_id,
                        supervisor_role, organization_id, conflict_count,
                        evaluated_at, expires_at, reversal_reference,
                        record_fingerprint)
                       VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb,
                               %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (evaluation_id) DO NOTHING
                       RETURNING evaluation_id""",
                    (
                        payload["evaluation_id"], payload["subject_id"],
                        payload["policy_mode"], payload["allowed"],
                        json.dumps(payload["decision_reasons"], ensure_ascii=False),
                        json.dumps(payload["evidence"], ensure_ascii=False, sort_keys=True),
                        payload["supervisor_actor_id"], payload["supervisor_role"],
                        payload["organization_id"], payload["conflict_count"],
                        record.evaluated_at, record.expires_at,
                        payload["reversal_reference"], fingerprint,
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """SELECT record_fingerprint
                           FROM promotion_policy_metadata
                           WHERE evaluation_id=%s::uuid""",
                        (record.evaluation_id,),
                    )
                    existing = cursor.fetchone()
                    if not existing or existing[0] != fingerprint:
                        raise ValueError(
                            "evaluation_id ya existe con metadata diferente"
                        )
        return record

    def get_promotion_policy_metadata(
        self, evaluation_id: str, *, organization_id: str,
    ) -> PromotionPolicyRecord | None:
        """Recupera una evaluación por ID sin tocar la cola de promoción."""
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT evaluation_id::text, subject_id, policy_mode,
                              decision_allowed, decision_reasons, evidence,
                              supervisor_actor_id, supervisor_role, organization_id,
                              conflict_count, evaluated_at, expires_at,
                              reversal_reference
                       FROM promotion_policy_metadata
                       WHERE evaluation_id=%s::uuid AND organization_id=%s""",
                    (evaluation_id, organization_id),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return PromotionPolicyRecord(
            evaluation_id=row[0], subject_id=row[1], policy_mode=row[2],
            allowed=bool(row[3]), decision_reasons=tuple(row[4]),
            evidence=dict(row[5]), supervisor_actor_id=row[6],
            supervisor_role=row[7], organization_id=row[8],
            conflict_count=int(row[9]), evaluated_at=row[10], expires_at=row[11],
            reversal_reference=row[12],
        )

    def save_promotion_outcome(
        self, record: PromotionOutcomeRecord,
    ) -> PromotionOutcomeRecord:
        validate_promotion_outcome(record)
        payload = promotion_outcome_payload(record)
        fingerprint = promotion_outcome_fingerprint(record)
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT subject_id, organization_id, decision_allowed
                       FROM promotion_policy_metadata
                       WHERE evaluation_id=%s::uuid""",
                    (record.evaluation_id,),
                )
                policy = cursor.fetchone()
                if policy is None:
                    raise ValueError("La evaluación de promoción no existe")
                if policy[0] != record.subject_id or policy[1] != record.organization_id:
                    raise ValueError(
                        "El outcome no coincide con sujeto u organización"
                    )
                if not bool(policy[2]):
                    raise ValueError(
                        "No se puede aplicar outcome a una evaluación denegada"
                    )
                cursor.execute(
                    """INSERT INTO promotion_outcomes
                       (record_fingerprint, evaluation_id, subject_id,
                        organization_id, actor_id, status, promotion_ids,
                        occurred_at, error)
                       VALUES (%s, %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s)
                       ON CONFLICT (record_fingerprint) DO NOTHING
                       RETURNING record_fingerprint""",
                    (
                        fingerprint, payload["evaluation_id"],
                        payload["subject_id"], payload["organization_id"],
                        payload["actor_id"], payload["status"],
                        json.dumps(payload["promotion_ids"], separators=(",", ":")),
                        record.occurred_at, payload["error"],
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """SELECT record_fingerprint FROM promotion_outcomes
                           WHERE record_fingerprint=%s""",
                        (fingerprint,),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError("No se pudo persistir outcome de promoción")
        return record

    def get_promotion_outcome(
        self, evaluation_id: str, *, organization_id: str,
    ) -> PromotionOutcomeRecord | None:
        rows = self.list_promotion_outcomes_for_evaluation(
            evaluation_id, organization_id=organization_id,
        )
        return rows[0] if rows else None

    def list_promotion_outcomes_for_evaluation(
        self, evaluation_id: str, *, organization_id: str,
    ) -> list[PromotionOutcomeRecord]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT evaluation_id::text, subject_id, organization_id,
                              actor_id, status, promotion_ids, occurred_at, error
                       FROM promotion_outcomes
                       WHERE evaluation_id=%s::uuid AND organization_id=%s
                       ORDER BY occurred_at DESC, record_fingerprint DESC""",
                    (evaluation_id, organization_id),
                )
                rows = cursor.fetchall()
        return [self._promotion_outcome_from_row(row) for row in rows]

    def list_promotion_outcomes_for_subject(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionOutcomeRecord]:
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit debe estar entre 1 y 1000")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT evaluation_id::text, subject_id, organization_id,
                              actor_id, status, promotion_ids, occurred_at, error
                       FROM promotion_outcomes
                       WHERE subject_id=%s AND organization_id=%s
                       ORDER BY occurred_at DESC, record_fingerprint DESC LIMIT %s""",
                    (subject_id, organization_id, int(limit)),
                )
                rows = cursor.fetchall()
        return [self._promotion_outcome_from_row(row) for row in rows]

    def list_unresolved_promotion_evaluations(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionPolicyRecord]:
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit debe estar entre 1 y 1000")
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT p.evaluation_id::text, p.subject_id,
                              p.policy_mode, p.decision_allowed,
                              p.decision_reasons, p.evidence,
                              p.supervisor_actor_id, p.supervisor_role,
                              p.organization_id, p.conflict_count,
                              p.evaluated_at, p.expires_at,
                              p.reversal_reference
                       FROM promotion_policy_metadata AS p
                       WHERE p.subject_id=%s AND p.organization_id=%s
                         AND p.decision_allowed=TRUE
                         AND NOT EXISTS (
                             SELECT 1 FROM promotion_outcomes AS o
                             WHERE o.evaluation_id=p.evaluation_id
                               AND o.organization_id=p.organization_id
                               AND o.status IN ('APPLIED', 'FAILED')
                         )
                       ORDER BY p.evaluated_at DESC, p.evaluation_id DESC
                       LIMIT %s""",
                    (subject_id, organization_id, int(limit)),
                )
                rows = cursor.fetchall()
        return [self._promotion_policy_from_row(row) for row in rows]

    @staticmethod
    def _promotion_policy_from_row(row: tuple[Any, ...]) -> PromotionPolicyRecord:
        return PromotionPolicyRecord(
            evaluation_id=row[0], subject_id=row[1], policy_mode=row[2],
            allowed=bool(row[3]), decision_reasons=tuple(row[4]),
            evidence=dict(row[5]), supervisor_actor_id=row[6],
            supervisor_role=row[7], organization_id=row[8],
            conflict_count=int(row[9]), evaluated_at=row[10], expires_at=row[11],
            reversal_reference=row[12],
        )

    @staticmethod
    def _promotion_outcome_from_row(row: tuple[Any, ...]) -> PromotionOutcomeRecord:
        promotion_ids = row[5]
        if isinstance(promotion_ids, str):
            promotion_ids = json.loads(promotion_ids)
        return PromotionOutcomeRecord(
            evaluation_id=row[0], subject_id=row[1], organization_id=row[2],
            actor_id=row[3], status=row[4], promotion_ids=tuple(promotion_ids),
            occurred_at=row[6], error=row[7],
        )

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
        return canonicalize_catalog({row["codigo_estandar"]: row for row in rows})

    def load_dictionary(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT cuenta_original, codigo_estandar, fuente "
                    "FROM diccionario_homologacion WHERE activo ORDER BY cuenta_original"
                )
                return canonicalize_dictionary([
                    {"cuenta_original": row[0], "codigo_estandar": row[1], "fuente": row[2]}
                    for row in cursor.fetchall()
                ])

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
                canonical_catalog_code(row["codigo_estandar"]), row.get("fuente", "seed_json"),
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

    def seed_baseline(
        self,
        catalog: dict[str, dict[str, Any]],
        dictionary: list[dict[str, Any]],
        *,
        bundle_version: str,
        bundle_checksum: str,
    ) -> tuple[int, int]:
        """Instala sólo filas ausentes y registra el paquete aplicado.

        Los conflictos se preservan deliberadamente: una actualización de
        maestros debe ejecutarse como migración explícita y no como bootstrap.
        """
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", bundle_version):
            raise ValueError("bundle_version inválida")
        if not re.fullmatch(r"[a-f0-9]{64}", bundle_checksum):
            raise ValueError("bundle_checksum inválido")
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
                canonical_catalog_code(row["codigo_estandar"]), row.get("fuente", "seed_json"),
            )
            for row in dictionary
            if canonical_catalog_code(row.get("codigo_estandar", "")) in valid_codes
        ]
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._execute_many(cursor,
                    """INSERT INTO catalogo_maestro
                       (codigo_estandar, nombre_estandar, categoria, tipo_estado,
                        naturaleza, signo_normal, es_deuda_financiera,
                        es_activo_liquido, afecta_ebitda)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (codigo_estandar) DO NOTHING""",
                    catalog_rows,
                )
                self._execute_many(cursor,
                    """INSERT INTO diccionario_homologacion
                       (cuenta_original, cuenta_normalizada, codigo_estandar, fuente)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (cuenta_normalizada) DO NOTHING""",
                    dictionary_rows,
                )
                cursor.execute(
                    """INSERT INTO master_seed_history
                       (bundle_checksum, bundle_version, applied_at,
                        catalog_rows, dictionary_rows)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (bundle_checksum) DO NOTHING""",
                    (
                        bundle_checksum, bundle_version,
                        datetime.now(timezone.utc), len(catalog_rows), len(dictionary_rows),
                    ),
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
        _reject_policy_promotion_through_validation(source)
        validated_code = canonical_catalog_code(validated_code)
        suggested_code = (
            canonical_catalog_code(suggested_code) if suggested_code else suggested_code
        )
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
        for validation in validations:
            _reject_policy_promotion_through_validation(validation["source"])
        with self._connect() as conn:
            with conn.cursor() as cursor:
                for validation in validations:
                    self._save_validation_cursor(cursor, validation)

    @staticmethod
    def _save_validation_cursor(cursor, validation: dict[str, Any]) -> None:
        account_name = validation["account_name"]
        validated_code = canonical_catalog_code(validation["validated_code"])
        source = validation["source"]
        _reject_policy_promotion_through_validation(source)
        suggested_code = validation.get("suggested_code")
        suggested_code = (
            canonical_catalog_code(suggested_code) if suggested_code else suggested_code
        )
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
