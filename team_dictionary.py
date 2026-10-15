"""Asignaciones de diccionario privadas por equipo.

Esta capa mantiene una superposición local sobre el diccionario operativo. No
escribe Neon, ``diccionario.json`` ni modifica el diccionario original. La
revisión administrativa de una propuesta deja una decisión auditada para una
incorporación posterior, que debe ser un proceso separado y explícito.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Mapping
import unicodedata

from access_control import Actor, Permission, ResourceScope, authorize
from local_accounts import LocalAccountError, LocalAccountStore


class TeamDictionaryError(ValueError):
    """Error de validación o de estado del diccionario de equipo."""


class TeamDictionaryAccessError(TeamDictionaryError, PermissionError):
    """La identidad autenticada no puede ejecutar la acción solicitada."""


class TeamAssignmentStatus:
    """Estados de disponibilidad de una asignación dentro del equipo."""

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"

    ALL = frozenset({PROPOSED, ACTIVE, REVOKED})


class GlobalReviewStatus:
    """Estados de la revisión administrativa para una promoción posterior."""

    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    ALL = frozenset({NOT_SUBMITTED, PENDING, APPROVED, REJECTED})


@dataclass(frozen=True)
class TeamDictionaryAssignment:
    """Una propuesta o asignación efectiva que pertenece a un solo equipo."""

    assignment_id: int
    team_id: str
    account_name: str
    normalized_account_name: str
    standard_code: str
    note: str
    team_status: str
    global_review_status: str
    created_by: str
    created_at: str
    updated_by: str
    updated_at: str
    reviewed_by: str | None
    reviewed_at: str | None
    review_note: str

    def dictionary_entry(self) -> dict[str, Any]:
        """Convierte la asignación activa al formato consumido por el motor."""

        return {
            "cuenta_original": self.account_name,
            "codigo_estandar": self.standard_code,
            "fuente": f"diccionario_equipo:{self.team_id}",
            "nombre_normalizado": self.normalized_account_name,
            "team_assignment_id": self.assignment_id,
            "team_id": self.team_id,
        }


def normalize_account_name(value: object) -> str:
    """Normaliza nombres con la misma semántica del motor local actual."""

    name = unicodedata.normalize("NFC", str(value or "")).lower().strip()
    name = re.sub(r"[^\w\sñáéíóú]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def overlay_team_dictionary(
    global_entries: Iterable[Mapping[str, Any]],
    team_entries: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aplica el diccionario de un equipo sin mutar la lista global recibida.

    Una entrada activa del equipo reemplaza sólo la cuenta normalizada
    equivalente y queda antes que el diccionario base para resolver empates de
    búsqueda. El llamador debe suministrar exclusivamente entradas activas de
    su propio equipo.
    """

    team_by_normalized: dict[str, dict[str, Any]] = {}
    for raw_entry in team_entries:
        entry = dict(raw_entry)
        normalized = normalize_account_name(
            entry.get("nombre_normalizado") or entry.get("cuenta_original"),
        )
        if not normalized:
            continue
        entry["nombre_normalizado"] = normalized
        team_by_normalized[normalized] = entry

    # Las entradas del equipo quedan primero. Además de reemplazar una cuenta
    # idéntica del diccionario base, esa prioridad evita que un empate fuzzy
    # devuelva una entrada global cuando el equipo ya declaró su propia regla.
    merged = list(team_by_normalized.values())
    for raw_entry in global_entries:
        entry = dict(raw_entry)
        normalized = normalize_account_name(
            entry.get("nombre_normalizado") or entry.get("cuenta_original"),
        )
        if normalized not in team_by_normalized:
            merged.append(entry)
    return merged


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_account_name(value: str) -> tuple[str, str]:
    account_name = " ".join(str(value or "").split())
    if not 2 <= len(account_name) <= 240:
        raise TeamDictionaryError("La cuenta debe tener entre 2 y 240 caracteres.")
    normalized = normalize_account_name(account_name)
    if not normalized:
        raise TeamDictionaryError("La cuenta no contiene caracteres clasificables.")
    return account_name, normalized


def _clean_standard_code(value: str) -> str:
    standard_code = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,63}", standard_code):
        raise TeamDictionaryError("El código estándar tiene un formato inválido.")
    return standard_code


def _clean_note(value: str, *, field: str = "La nota") -> str:
    note = " ".join(str(value or "").split())
    if len(note) > 1000:
        raise TeamDictionaryError(f"{field} no puede exceder 1.000 caracteres.")
    return note


class TeamDictionaryStore:
    """Repositorio local y auditado para las asignaciones de cada equipo."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        try:
            accounts = LocalAccountStore(database_path)
        except LocalAccountError as exc:
            raise TeamDictionaryError(str(exc)) from exc
        self.path = accounts.path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        statuses = ", ".join(repr(status) for status in TeamAssignmentStatus.ALL)
        review_statuses = ", ".join(
            repr(status) for status in GlobalReviewStatus.ALL
        )
        with self._connect() as conn:
            conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS team_dictionary_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL REFERENCES teams(team_id),
                    account_name TEXT NOT NULL,
                    normalized_account_name TEXT NOT NULL,
                    standard_code TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    team_status TEXT NOT NULL CHECK(team_status IN ({statuses})),
                    global_review_status TEXT NOT NULL
                        CHECK(global_review_status IN ({review_statuses})),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    review_note TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_team_dictionary_open_account
                    ON team_dictionary_assignments(team_id, normalized_account_name)
                    WHERE team_status IN ('PROPOSED', 'ACTIVE');
                CREATE INDEX IF NOT EXISTS ix_team_dictionary_team_status
                    ON team_dictionary_assignments(team_id, team_status, assignment_id);
                CREATE INDEX IF NOT EXISTS ix_team_dictionary_global_review
                    ON team_dictionary_assignments(global_review_status, assignment_id);
                CREATE TABLE IF NOT EXISTS team_dictionary_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL
                        REFERENCES team_dictionary_assignments(assignment_id),
                    event_type TEXT NOT NULL,
                    actor_username TEXT NOT NULL,
                    team_id TEXT NOT NULL REFERENCES teams(team_id),
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _assignment_from_row(row: sqlite3.Row) -> TeamDictionaryAssignment:
        return TeamDictionaryAssignment(
            assignment_id=int(row["assignment_id"]),
            team_id=row["team_id"],
            account_name=row["account_name"],
            normalized_account_name=row["normalized_account_name"],
            standard_code=row["standard_code"],
            note=row["note"],
            team_status=row["team_status"],
            global_review_status=row["global_review_status"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
            reviewed_by=row["reviewed_by"],
            reviewed_at=row["reviewed_at"],
            review_note=row["review_note"],
        )

    @staticmethod
    def _require_permission(
        actor: Actor,
        permission: Permission,
        team_id: str,
    ) -> None:
        if not team_id:
            raise TeamDictionaryError("Debe indicar el equipo de la asignación.")
        decision = authorize(actor, permission, ResourceScope(team_id=team_id))
        if not decision.allowed:
            raise TeamDictionaryAccessError(
                "La cuenta no tiene permiso para esta acción sobre el diccionario del equipo."
            )

    @staticmethod
    def _require_global_review_permission(actor: Actor, team_id: str) -> None:
        decision = authorize(
            actor,
            Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW,
            ResourceScope(team_id=team_id),
        )
        if not decision.allowed:
            raise TeamDictionaryAccessError(
                "Solo el administrador puede revisar una incorporación al diccionario original."
            )

    @staticmethod
    def _require_existing_team(conn: sqlite3.Connection, team_id: str) -> None:
        if not conn.execute(
            "SELECT 1 FROM teams WHERE team_id = ?", (team_id,),
        ).fetchone():
            raise TeamDictionaryError("El equipo seleccionado no existe.")

    @staticmethod
    def _get_row(conn: sqlite3.Connection, assignment_id: int) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM team_dictionary_assignments WHERE assignment_id = ?",
            (int(assignment_id),),
        ).fetchone()
        if row is None:
            raise TeamDictionaryError("La asignación de diccionario no existe.")
        return row

    @staticmethod
    def _audit(
        conn: sqlite3.Connection,
        *,
        assignment_id: int,
        event_type: str,
        actor: Actor,
        team_id: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO team_dictionary_audit
               (assignment_id, event_type, actor_username, team_id, details_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                assignment_id,
                event_type,
                actor.actor_id,
                team_id,
                json.dumps(dict(details or {}), ensure_ascii=False, sort_keys=True),
                _now(),
            ),
        )

    def propose(
        self,
        actor: Actor,
        *,
        team_id: str,
        account_name: str,
        standard_code: str,
        note: str = "",
    ) -> TeamDictionaryAssignment:
        """Registra una propuesta sin hacerla efectiva para el equipo."""

        self._require_permission(actor, Permission.DICTIONARY_PROPOSE, team_id)
        account_name, normalized_account_name = _clean_account_name(account_name)
        standard_code = _clean_standard_code(standard_code)
        note = _clean_note(note)
        now = _now()
        with self._connect() as conn:
            self._require_existing_team(conn, team_id)
            try:
                cursor = conn.execute(
                    """INSERT INTO team_dictionary_assignments
                       (team_id, account_name, normalized_account_name, standard_code,
                        note, team_status, global_review_status, created_by, created_at,
                        updated_by, updated_at, review_note)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')""",
                    (
                        team_id,
                        account_name,
                        normalized_account_name,
                        standard_code,
                        note,
                        TeamAssignmentStatus.PROPOSED,
                        GlobalReviewStatus.NOT_SUBMITTED,
                        actor.actor_id,
                        now,
                        actor.actor_id,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise TeamDictionaryError(
                    "Ya existe una propuesta o asignación activa para esa cuenta en el equipo."
                ) from exc
            assignment_id = int(cursor.lastrowid)
            self._audit(
                conn,
                assignment_id=assignment_id,
                event_type="TEAM_DICTIONARY_PROPOSED",
                actor=actor,
                team_id=team_id,
                details={"standard_code": standard_code},
            )
            return self._assignment_from_row(self._get_row(conn, assignment_id))

    def activate(self, actor: Actor, assignment_id: int) -> TeamDictionaryAssignment:
        """Hace efectiva una propuesta dentro del equipo, con auditoría."""

        with self._connect() as conn:
            row = self._get_row(conn, assignment_id)
            self._require_permission(
                actor, Permission.TEAM_DICTIONARY_ACTIVATE, row["team_id"],
            )
            if row["team_status"] != TeamAssignmentStatus.PROPOSED:
                raise TeamDictionaryError("Solo una propuesta pendiente puede activarse.")
            now = _now()
            conn.execute(
                """UPDATE team_dictionary_assignments
                   SET team_status = ?, updated_by = ?, updated_at = ?
                   WHERE assignment_id = ?""",
                (TeamAssignmentStatus.ACTIVE, actor.actor_id, now, int(assignment_id)),
            )
            self._audit(
                conn,
                assignment_id=int(assignment_id),
                event_type="TEAM_DICTIONARY_ACTIVATED",
                actor=actor,
                team_id=row["team_id"],
                details={"previous_team_status": row["team_status"]},
            )
            return self._assignment_from_row(self._get_row(conn, assignment_id))

    def revoke(
        self,
        actor: Actor,
        assignment_id: int,
        *,
        note: str = "",
    ) -> TeamDictionaryAssignment:
        """Revoca una asignación sin borrar la evidencia histórica."""

        note = _clean_note(note, field="El motivo")
        with self._connect() as conn:
            row = self._get_row(conn, assignment_id)
            self._require_permission(
                actor, Permission.TEAM_DICTIONARY_UNASSIGN, row["team_id"],
            )
            if row["team_status"] == TeamAssignmentStatus.REVOKED:
                raise TeamDictionaryError("La asignación ya fue revocada.")
            now = _now()
            conn.execute(
                """UPDATE team_dictionary_assignments
                   SET team_status = ?, updated_by = ?, updated_at = ?
                   WHERE assignment_id = ?""",
                (TeamAssignmentStatus.REVOKED, actor.actor_id, now, int(assignment_id)),
            )
            self._audit(
                conn,
                assignment_id=int(assignment_id),
                event_type="TEAM_DICTIONARY_REVOKED",
                actor=actor,
                team_id=row["team_id"],
                details={
                    "previous_team_status": row["team_status"],
                    "reason": note,
                },
            )
            return self._assignment_from_row(self._get_row(conn, assignment_id))

    def submit_for_global_review(
        self,
        actor: Actor,
        assignment_id: int,
        *,
        note: str = "",
    ) -> TeamDictionaryAssignment:
        """Envía una asignación activa a revisión, sin tocar el diccionario base."""

        note = _clean_note(note, field="La nota de revisión")
        with self._connect() as conn:
            row = self._get_row(conn, assignment_id)
            self._require_permission(
                actor,
                Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW,
                row["team_id"],
            )
            if row["team_status"] != TeamAssignmentStatus.ACTIVE:
                raise TeamDictionaryError(
                    "Solo una asignación activa puede enviarse a revisión global."
                )
            if row["global_review_status"] == GlobalReviewStatus.PENDING:
                raise TeamDictionaryError("La asignación ya está pendiente de revisión global.")
            now = _now()
            conn.execute(
                """UPDATE team_dictionary_assignments
                   SET global_review_status = ?, updated_by = ?, updated_at = ?
                   WHERE assignment_id = ?""",
                (GlobalReviewStatus.PENDING, actor.actor_id, now, int(assignment_id)),
            )
            self._audit(
                conn,
                assignment_id=int(assignment_id),
                event_type="TEAM_DICTIONARY_SUBMITTED_FOR_GLOBAL_REVIEW",
                actor=actor,
                team_id=row["team_id"],
                details={"note": note},
            )
            return self._assignment_from_row(self._get_row(conn, assignment_id))

    def review_for_global_promotion(
        self,
        actor: Actor,
        assignment_id: int,
        *,
        approved: bool,
        note: str = "",
    ) -> TeamDictionaryAssignment:
        """Registra la decisión administrativa sin promover la cuenta aún."""

        note = _clean_note(note, field="La nota de decisión")
        with self._connect() as conn:
            row = self._get_row(conn, assignment_id)
            self._require_global_review_permission(actor, row["team_id"])
            if row["global_review_status"] != GlobalReviewStatus.PENDING:
                raise TeamDictionaryError(
                    "Solo una solicitud pendiente puede recibir decisión administrativa."
                )
            if row["team_status"] != TeamAssignmentStatus.ACTIVE:
                raise TeamDictionaryError(
                    "No se puede decidir una incorporación de una asignación revocada."
                )
            review_status = (
                GlobalReviewStatus.APPROVED if approved else GlobalReviewStatus.REJECTED
            )
            now = _now()
            conn.execute(
                """UPDATE team_dictionary_assignments
                   SET global_review_status = ?, updated_by = ?, updated_at = ?,
                       reviewed_by = ?, reviewed_at = ?, review_note = ?
                   WHERE assignment_id = ?""",
                (
                    review_status,
                    actor.actor_id,
                    now,
                    actor.actor_id,
                    now,
                    note,
                    int(assignment_id),
                ),
            )
            self._audit(
                conn,
                assignment_id=int(assignment_id),
                event_type=(
                    "TEAM_DICTIONARY_GLOBAL_PROMOTION_APPROVED"
                    if approved else "TEAM_DICTIONARY_GLOBAL_PROMOTION_REJECTED"
                ),
                actor=actor,
                team_id=row["team_id"],
                details={"note": note},
            )
            return self._assignment_from_row(self._get_row(conn, assignment_id))

    def list_for_team(
        self, actor: Actor, team_id: str,
    ) -> list[TeamDictionaryAssignment]:
        """Lista la evidencia de un equipo para roles autorizados."""

        self._require_permission(actor, Permission.TEAM_AUDIT_VIEW, team_id)
        with self._connect() as conn:
            self._require_existing_team(conn, team_id)
            rows = conn.execute(
                """SELECT * FROM team_dictionary_assignments
                   WHERE team_id = ?
                   ORDER BY normalized_account_name, assignment_id""",
                (team_id,),
            ).fetchall()
        return [self._assignment_from_row(row) for row in rows]

    def list_pending_global_reviews(
        self, actor: Actor,
    ) -> list[TeamDictionaryAssignment]:
        """Lista propuestas pendientes únicamente para la cuenta administradora."""

        self._require_global_review_permission(actor, "global-review")
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM team_dictionary_assignments
                   WHERE global_review_status = ?
                   ORDER BY updated_at, assignment_id""",
                (GlobalReviewStatus.PENDING,),
            ).fetchall()
        return [self._assignment_from_row(row) for row in rows]

    def active_entries_for_team(self, team_id: str) -> list[dict[str, Any]]:
        """Devuelve únicamente las asignaciones activas para la superposición."""

        if not team_id:
            return []
        with self._connect() as conn:
            self._require_existing_team(conn, team_id)
            rows = conn.execute(
                """SELECT * FROM team_dictionary_assignments
                   WHERE team_id = ? AND team_status = ?
                   ORDER BY assignment_id""",
                (team_id, TeamAssignmentStatus.ACTIVE),
            ).fetchall()
        return [self._assignment_from_row(row).dictionary_entry() for row in rows]

    def revision_token_for_team(self, team_id: str) -> str:
        """Identifica la versión actual del diccionario efectivo de un equipo."""

        if not team_id:
            return "empty"
        with self._connect() as conn:
            self._require_existing_team(conn, team_id)
            row = conn.execute(
                """SELECT COALESCE(MAX(assignment_id), 0) AS assignment_id,
                          COALESCE((
                              SELECT MAX(id) FROM team_dictionary_audit
                              WHERE team_id = ?
                          ), 0) AS audit_id
                   FROM team_dictionary_assignments
                   WHERE team_id = ?""",
                (team_id, team_id),
            ).fetchone()
        return f"{row['assignment_id']}:{row['audit_id']}"

    def list_audit(
        self, actor: Actor, team_id: str, *, limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Entrega el historial append-only del equipo dentro de su alcance."""

        self._require_permission(actor, Permission.TEAM_AUDIT_VIEW, team_id)
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            self._require_existing_team(conn, team_id)
            rows = conn.execute(
                """SELECT assignment_id, event_type, actor_username, team_id,
                          details_json, created_at
                   FROM team_dictionary_audit
                   WHERE team_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (team_id, safe_limit),
            ).fetchall()
        return [
            {
                "assignment_id": row["assignment_id"],
                "event_type": row["event_type"],
                "actor_username": row["actor_username"],
                "team_id": row["team_id"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


__all__ = [
    "GlobalReviewStatus",
    "TeamAssignmentStatus",
    "TeamDictionaryAccessError",
    "TeamDictionaryAssignment",
    "TeamDictionaryError",
    "TeamDictionaryStore",
    "normalize_account_name",
    "overlay_team_dictionary",
]
