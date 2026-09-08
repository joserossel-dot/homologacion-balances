"""Persistencia operacional local mínima sobre SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import UUID, uuid4
import re

from persistence.contracts.audit import AuditEvent
from persistence.contracts.executions import ExecutionRecord, ExecutionStatus
from persistence.contracts.promotions import PromotionOutcomeRecord, PromotionPolicyRecord
from persistence.contracts.users import UserRecord
from persistence.promotion_metadata import (
    promotion_outcome_fingerprint,
    promotion_outcome_payload,
    validate_promotion_outcome,
    promotion_record_fingerprint,
    promotion_record_payload,
    validate_promotion_policy_record,
)


_SAFE_ID = re.compile(r"^[a-f0-9]{32}$")
_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    "pending": {"running", "failed", "cancelled"},
    "running": {"review", "completed", "failed", "cancelled"},
    "review": {"running", "completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _validated_id(value: str, field: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} inválido")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SqliteOperationalRepository:
    """Adaptador inicial para ejecuciones, auditoría y usuarios.

    Es durable y apropiado para pruebas o una instalación individual. Una
    instalación multiusuario debe usar un adaptador PostgreSQL equivalente.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS local_users (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('analyst', 'supervisor', 'admin')
                    ),
                    active INTEGER NOT NULL CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS local_executions (
                    execution_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'pending', 'running', 'review', 'completed',
                            'failed', 'cancelled'
                        )
                    ),
                    application_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_code TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_local_executions_document
                    ON local_executions(document_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS local_audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    actor_id TEXT,
                    action TEXT NOT NULL,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_local_audit_subject
                    ON local_audit_events(
                        subject_type, subject_id, event_id DESC
                    );

                CREATE TABLE IF NOT EXISTS local_schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            self._migrate_local_users_admin_role(connection)
            promotion_migration = (
                Path(__file__).resolve().parent
                / "migrations"
                / "003_promotion_policy_metadata.sql"
            ).read_text(encoding="utf-8")
            connection.executescript(promotion_migration)
            outcome_migration = (
                Path(__file__).resolve().parent
                / "migrations"
                / "004_promotion_outcomes.sql"
            ).read_text(encoding="utf-8")
            connection.executescript(outcome_migration)
            self._migrate_promotion_outcomes_batch_ids(connection)
            now = _utc_now().isoformat()
            connection.execute(
                """INSERT OR IGNORE INTO local_schema_migrations(version, applied_at)
                   VALUES ('001_identity_role_admin', ?)""",
                (now,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO local_schema_migrations(version, applied_at)
                   VALUES ('004_promotion_outcomes', ?)""",
                (now,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO local_schema_migrations(version, applied_at)
                   VALUES ('005_promotion_outcome_batches', ?)""",
                (now,),
            )
            connection.execute(
                """INSERT OR IGNORE INTO local_schema_migrations(version, applied_at)
                   VALUES ('003_promotion_policy_metadata', ?)""",
                (now,),
            )

    @staticmethod
    def _migrate_promotion_outcomes_batch_ids(
        connection: sqlite3.Connection,
    ) -> None:
        """Amplía instalaciones tempranas con IDs batch sin perder outcomes."""
        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(local_promotion_outcomes)"
            ).fetchall()
        }
        if "promotion_ids_json" in columns:
            return
        connection.execute("DROP TRIGGER IF EXISTS trg_local_promotion_outcomes_no_update")
        connection.execute(
            """ALTER TABLE local_promotion_outcomes
               ADD COLUMN promotion_ids_json TEXT NOT NULL DEFAULT '[]'"""
        )
        if "promotion_id" in columns:
            rows = connection.execute(
                """SELECT record_fingerprint, promotion_id
                   FROM local_promotion_outcomes WHERE promotion_id IS NOT NULL"""
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE local_promotion_outcomes
                       SET promotion_ids_json=? WHERE record_fingerprint=?""",
                    (json.dumps([row[1]], separators=(",", ":")), row[0]),
                )
        connection.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS trg_local_promotion_outcomes_no_update
            BEFORE UPDATE ON local_promotion_outcomes
            BEGIN
                SELECT RAISE(ABORT, 'promotion outcome is append-only');
            END;
            """
        )

    @staticmethod
    def _migrate_local_users_admin_role(connection: sqlite3.Connection) -> None:
        """Reconstruye el CHECK heredado y traduce administrator a admin."""
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='local_users'"
        ).fetchone()
        definition = str(row[0] if row else "")
        if "administrator" not in definition:
            return
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            ALTER TABLE local_users RENAME TO local_users_legacy_role;
            CREATE TABLE local_users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('analyst', 'supervisor', 'admin')),
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL
            );
            INSERT INTO local_users(user_id, display_name, role, active, created_at)
            SELECT user_id, display_name,
                   CASE WHEN role='administrator' THEN 'admin' ELSE role END,
                   active, created_at
            FROM local_users_legacy_role;
            DROP TABLE local_users_legacy_role;
            COMMIT;
            """
        )

    def create(
        self,
        *,
        document_id: str,
        application_version: str,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        _validated_id(document_id, "document_id")
        now = _utc_now()
        record = ExecutionRecord(
            execution_id=uuid4().hex,
            document_id=document_id,
            status="pending",
            application_version=application_version,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO local_executions
                   (execution_id, document_id, status, application_version,
                    created_at, updated_at, error_code, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.execution_id,
                    record.document_id,
                    record.status,
                    record.application_version,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.error_code,
                    _as_json(record.metadata),
                ),
            )
        return record

    def get_execution(self, execution_id: str) -> ExecutionRecord | None:
        _validated_id(execution_id, "execution_id")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_executions WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
        return self._execution_from_row(row) if row else None

    def list_executions(self) -> list[ExecutionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM local_executions ORDER BY created_at, execution_id"
            ).fetchall()
        return [self._execution_from_row(row) for row in rows]

    def set_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        *,
        error_code: str | None = None,
        expected_status: ExecutionStatus | None = None,
    ) -> ExecutionRecord:
        _validated_id(execution_id, "execution_id")
        if status not in _TRANSITIONS:
            raise ValueError("status inválido")
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status FROM local_executions WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if row is None:
                raise KeyError(execution_id)
            current_status: ExecutionStatus = row["status"]
            if expected_status is not None and current_status != expected_status:
                raise RuntimeError(
                    f"Conflicto de estado: esperado {expected_status}, actual {current_status}"
                )
            if status not in _TRANSITIONS[current_status]:
                raise ValueError(f"Transición inválida: {current_status} -> {status}")
            cursor = connection.execute(
                """UPDATE local_executions
                   SET status=?, updated_at=?, error_code=?
                   WHERE execution_id=? AND status=?""",
                (status, now.isoformat(), error_code, execution_id, current_status),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("La ejecución cambió concurrentemente")
        record = self.get_execution(execution_id)
        if record is None:  # pragma: no cover - defensa tras transacción
            raise KeyError(execution_id)
        return record

    def append(self, event: AuditEvent) -> AuditEvent:
        occurred_at = event.occurred_at.astimezone(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO local_audit_events
                   (occurred_at, actor_id, action, subject_type, subject_id,
                    details_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    occurred_at.isoformat(),
                    event.actor_id,
                    event.action,
                    event.subject_type,
                    event.subject_id,
                    _as_json(event.details),
                ),
            )
            event_id = int(cursor.lastrowid)
        return AuditEvent(
            event_id=event_id,
            occurred_at=occurred_at,
            actor_id=event.actor_id,
            action=event.action,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            details=dict(event.details),
        )

    def list_for_subject(
        self,
        subject_type: str,
        subject_id: str,
        *,
        limit: int = 100,
    ) -> list[AuditEvent]:
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM local_audit_events
                   WHERE subject_type=? AND subject_id=?
                   ORDER BY event_id DESC LIMIT ?""",
                (subject_type, subject_id, safe_limit),
            ).fetchall()
        return [self._audit_from_row(row) for row in rows]

    def upsert(self, user: UserRecord) -> UserRecord:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO local_users
                   (user_id, display_name, role, active, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     display_name=excluded.display_name,
                     role=excluded.role,
                     active=excluded.active""",
                (
                    user.user_id,
                    user.display_name,
                    user.role,
                    int(user.active),
                    user.created_at.astimezone(timezone.utc).isoformat(),
                ),
            )
        stored = self.get_user(user.user_id)
        if stored is None:  # pragma: no cover - defensa tras transacción
            raise KeyError(user.user_id)
        return stored

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_users WHERE user_id=?", (user_id,),
            ).fetchone()
        return self._user_from_row(row) if row else None

    def list_active(self) -> list[UserRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM local_users WHERE active=1
                   ORDER BY display_name, user_id"""
            ).fetchall()
        return [self._user_from_row(row) for row in rows]

    def save_promotion_policy_metadata(
        self, record: PromotionPolicyRecord,
    ) -> PromotionPolicyRecord:
        """Añade metadata de política sin aprobar ni rechazar la promoción."""
        validate_promotion_policy_record(record)
        payload = promotion_record_payload(record)
        fingerprint = promotion_record_fingerprint(record)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """INSERT OR IGNORE INTO local_promotion_policy_metadata
                   (evaluation_id, subject_id, policy_mode, decision_allowed,
                    decision_reasons_json, evidence_json, supervisor_actor_id,
                    supervisor_role, organization_id, conflict_count,
                    evaluated_at, expires_at, reversal_reference,
                    record_fingerprint, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload["evaluation_id"], payload["subject_id"],
                    payload["policy_mode"], int(bool(payload["allowed"])),
                    json.dumps(
                        payload["decision_reasons"], ensure_ascii=False,
                        sort_keys=True, separators=(",", ":"),
                    ),
                    json.dumps(
                        payload["evidence"], ensure_ascii=False,
                        sort_keys=True, separators=(",", ":"),
                    ),
                    payload["supervisor_actor_id"], payload["supervisor_role"],
                    payload["organization_id"], payload["conflict_count"],
                    payload["evaluated_at"], payload["expires_at"],
                    payload["reversal_reference"], fingerprint,
                    _utc_now().isoformat(),
                ),
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    """SELECT record_fingerprint
                       FROM local_promotion_policy_metadata
                       WHERE evaluation_id=?""",
                    (record.evaluation_id,),
                ).fetchone()
                if not existing or existing[0] != fingerprint:
                    raise ValueError(
                        "evaluation_id ya existe con metadata diferente"
                    )
        return record

    def get_promotion_policy_metadata(
        self,
        evaluation_id: str,
        *,
        organization_id: str,
    ) -> PromotionPolicyRecord | None:
        """Lee por organización; una organización distinta obtiene ausencia."""
        try:
            canonical_id = str(UUID(evaluation_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("evaluation_id inválido") from exc
        if evaluation_id != canonical_id:
            raise ValueError("evaluation_id debe usar formato UUID canónico")
        if not str(organization_id).strip():
            raise ValueError("organization_id es obligatorio")
        with self._connect() as connection:
            row = connection.execute(
                """SELECT evaluation_id, subject_id, policy_mode,
                          decision_allowed, decision_reasons_json, evidence_json,
                          supervisor_actor_id, supervisor_role, organization_id,
                          conflict_count, evaluated_at, expires_at,
                          reversal_reference
                   FROM local_promotion_policy_metadata
                   WHERE evaluation_id=? AND organization_id=?""",
                (evaluation_id, organization_id),
            ).fetchone()
        return self._promotion_from_row(row) if row else None

    def save_promotion_outcome(
        self, record: PromotionOutcomeRecord,
    ) -> PromotionOutcomeRecord:
        """Añade el evento terminal de una evaluación sin reescribir historia."""
        validate_promotion_outcome(record)
        payload = promotion_outcome_payload(record)
        fingerprint = promotion_outcome_fingerprint(record)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            policy = connection.execute(
                """SELECT subject_id, organization_id, decision_allowed
                   FROM local_promotion_policy_metadata
                   WHERE evaluation_id=?""",
                (record.evaluation_id,),
            ).fetchone()
            if policy is None:
                raise ValueError("La evaluación de promoción no existe")
            if (
                policy["subject_id"] != record.subject_id
                or policy["organization_id"] != record.organization_id
            ):
                raise ValueError("El outcome no coincide con sujeto u organización")
            if not bool(policy["decision_allowed"]):
                raise ValueError("No se puede aplicar outcome a una evaluación denegada")
            cursor = connection.execute(
                """INSERT OR IGNORE INTO local_promotion_outcomes
                   (record_fingerprint, evaluation_id, subject_id,
                    organization_id, actor_id, status, promotion_ids_json,
                    occurred_at, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fingerprint, payload["evaluation_id"], payload["subject_id"],
                    payload["organization_id"], payload["actor_id"],
                    payload["status"],
                    json.dumps(payload["promotion_ids"], separators=(",", ":")),
                    payload["occurred_at"], payload["error"],
                    _utc_now().isoformat(),
                ),
            )
            if cursor.rowcount == 0:
                existing = connection.execute(
                    """SELECT record_fingerprint FROM local_promotion_outcomes
                       WHERE record_fingerprint=?""",
                    (fingerprint,),
                ).fetchone()
                if existing is None:
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
        try:
            canonical_id = str(UUID(evaluation_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("evaluation_id inválido") from exc
        if canonical_id != evaluation_id or not str(organization_id).strip():
            raise ValueError("evaluation_id u organization_id inválido")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM local_promotion_outcomes
                   WHERE evaluation_id=? AND organization_id=?
                   ORDER BY occurred_at DESC, record_fingerprint DESC""",
                (evaluation_id, organization_id),
            ).fetchall()
        return [self._promotion_outcome_from_row(row) for row in rows]

    def list_promotion_outcomes_for_subject(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionOutcomeRecord]:
        if not str(subject_id).strip() or not str(organization_id).strip():
            raise ValueError("subject_id y organization_id son obligatorios")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit debe estar entre 1 y 1000")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM local_promotion_outcomes
                   WHERE subject_id=? AND organization_id=?
                   ORDER BY occurred_at DESC, record_fingerprint DESC LIMIT ?""",
                (subject_id, organization_id, int(limit)),
            ).fetchall()
        return [self._promotion_outcome_from_row(row) for row in rows]

    def list_unresolved_promotion_evaluations(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionPolicyRecord]:
        """Lista evaluaciones permitidas sin outcome durable terminal."""
        if not str(subject_id).strip() or not str(organization_id).strip():
            raise ValueError("subject_id y organization_id son obligatorios")
        if not 1 <= int(limit) <= 1000:
            raise ValueError("limit debe estar entre 1 y 1000")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT p.* FROM local_promotion_policy_metadata AS p
                   WHERE p.subject_id=? AND p.organization_id=?
                     AND p.decision_allowed=1
                     AND NOT EXISTS (
                         SELECT 1 FROM local_promotion_outcomes AS o
                         WHERE o.evaluation_id=p.evaluation_id
                           AND o.organization_id=p.organization_id
                           AND o.status IN ('APPLIED', 'FAILED')
                     )
                   ORDER BY p.evaluated_at DESC, p.evaluation_id DESC LIMIT ?""",
                (subject_id, organization_id, int(limit)),
            ).fetchall()
        return [self._promotion_from_row(row) for row in rows]

    @staticmethod
    def _execution_from_row(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=row["execution_id"],
            document_id=row["document_id"],
            status=row["status"],
            application_version=row["application_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_code=row["error_code"],
            metadata=json.loads(row["metadata_json"]),
        )

    @staticmethod
    def _audit_from_row(row: sqlite3.Row) -> AuditEvent:
        return AuditEvent(
            event_id=int(row["event_id"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            actor_id=row["actor_id"],
            action=row["action"],
            subject_type=row["subject_type"],
            subject_id=row["subject_id"],
            details=json.loads(row["details_json"]),
        )

    @staticmethod
    def _user_from_row(row: sqlite3.Row) -> UserRecord:
        return UserRecord(
            user_id=row["user_id"],
            display_name=row["display_name"],
            role=row["role"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _promotion_from_row(row: sqlite3.Row) -> PromotionPolicyRecord:
        return PromotionPolicyRecord(
            evaluation_id=row["evaluation_id"],
            subject_id=row["subject_id"],
            policy_mode=row["policy_mode"],
            allowed=bool(row["decision_allowed"]),
            decision_reasons=tuple(json.loads(row["decision_reasons_json"])),
            evidence=dict(json.loads(row["evidence_json"])),
            supervisor_actor_id=row["supervisor_actor_id"],
            supervisor_role=row["supervisor_role"],
            organization_id=row["organization_id"],
            conflict_count=int(row["conflict_count"]),
            evaluated_at=datetime.fromisoformat(row["evaluated_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            reversal_reference=row["reversal_reference"],
        )

    @staticmethod
    def _promotion_outcome_from_row(row: sqlite3.Row) -> PromotionOutcomeRecord:
        return PromotionOutcomeRecord(
            evaluation_id=row["evaluation_id"],
            subject_id=row["subject_id"],
            organization_id=row["organization_id"],
            actor_id=row["actor_id"],
            status=row["status"],
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            promotion_ids=tuple(json.loads(row["promotion_ids_json"])),
            error=row["error"],
        )
