"""Cuentas locales, solicitudes de acceso y auditoría de administración.

Este módulo administra credenciales derivadas, roles, equipos y eventos de
acceso. La misma base privada puede alojar, en tablas separadas, asignaciones
explícitas del diccionario de equipo gestionadas por ``team_dictionary.py``.
No almacena balances, PDFs ni resultados extraídos del piloto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any

from access_control import Actor, Permission, Role, authorize


class LocalAccountError(ValueError):
    """Error de validación o estado de una cuenta local."""


class LocalAccountAccessError(LocalAccountError, PermissionError):
    """La identidad autenticada no puede administrar cuentas locales."""


class AccountStatus:
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DENIED = "DENIED"
    DISABLED = "DISABLED"

    ALL = frozenset({PENDING, ACTIVE, DENIED, DISABLED})


@dataclass(frozen=True)
class LocalAccount:
    username: str
    display_name: str
    role: Role | None
    team_id: str | None
    requested_team: str
    status: str
    created_at: str
    updated_at: str

    def actor(self) -> Actor:
        if self.status != AccountStatus.ACTIVE or self.role is None:
            raise LocalAccountAccessError("La cuenta no está activa")
        return Actor(self.username, self.role, self.team_id)


@dataclass(frozen=True)
class Team:
    team_id: str
    name: str
    created_at: str


_USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}")
_VALID_ASSIGNABLE_ROLES = frozenset({
    Role.DATA_ENTRY,
    Role.ANALYST,
    Role.MANAGEMENT,
})


def default_local_accounts_path() -> Path:
    """Ruta privada predeterminada para las cuentas locales en macOS."""

    configured = os.environ.get("HOMOLOGACION_LOCAL_ACCOUNTS_DB", "").strip()
    if configured:
        return Path(configured).expanduser()
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "HomologacionBalances"
        / "local_accounts.sqlite3"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_username(value: str) -> str:
    username = str(value or "").strip().lower()
    if not _USERNAME.fullmatch(username):
        raise LocalAccountError(
            "El usuario debe tener entre 3 y 64 caracteres: letras, números, punto, guion o guion bajo."
        )
    return username


def _validate_display_name(value: str) -> str:
    display_name = " ".join(str(value or "").split())
    if not 2 <= len(display_name) <= 120:
        raise LocalAccountError("El nombre visible debe tener entre 2 y 120 caracteres.")
    return display_name


def _validate_password(value: str) -> str:
    password = str(value or "")
    if len(password) < 12:
        raise LocalAccountError("La contraseña debe tener al menos 12 caracteres.")
    if len(password.encode("utf-8")) > 1024:
        raise LocalAccountError("La contraseña es demasiado extensa.")
    return password


def _password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64,
    )


class LocalAccountStore:
    """Repositorio SQLite privado para acceso local.

    La única creación de administrador se realiza por el comando de bootstrap.
    Luego, la administración ordinaria solo puede aprobar los tres roles no
    administrativos definidos para el equipo.
    """

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.path = Path(database_path or default_local_accounts_path()).expanduser()
        self._prepare_storage()
        self._initialize()

    def _prepare_storage(self) -> None:
        if not self.path.name:
            raise LocalAccountError("La ruta de cuentas locales no identifica una base de datos.")
        repository_root = Path(__file__).resolve().parent
        if self.path.resolve().is_relative_to(repository_root):
            raise LocalAccountError(
                "La base de cuentas locales debe estar fuera del repositorio."
            )
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            parent.chmod(0o700)
        except OSError as exc:
            raise LocalAccountError("No se pudo asegurar el directorio de cuentas locales.") from exc
        if parent.stat().st_mode & 0o077:
            raise LocalAccountError("El directorio de cuentas locales debe ser privado.")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        roles = ", ".join(repr(role.value) for role in Role)
        statuses = ", ".join(repr(status) for status in AccountStatus.ALL)
        with self._connect() as conn:
            conn.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_digest BLOB NOT NULL,
                    role TEXT CHECK(role IS NULL OR role IN ({roles})),
                    team_id TEXT REFERENCES teams(team_id),
                    requested_team TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK(status IN ({statuses})),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS access_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor_username TEXT,
                    subject_username TEXT,
                    team_id TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
        try:
            self.path.chmod(0o600)
        except OSError as exc:
            raise LocalAccountError("No se pudo asegurar la base de cuentas locales.") from exc
        if self.path.stat().st_mode & 0o077:
            raise LocalAccountError("La base de cuentas locales debe ser privada.")

    @staticmethod
    def _require_administrator(actor: Actor) -> None:
        decision = authorize(actor, Permission.ROLE_MANAGE)
        if not decision.allowed:
            raise LocalAccountAccessError("Solo el administrador puede gestionar accesos.")

    @staticmethod
    def _audit(
        conn: sqlite3.Connection,
        *,
        event_type: str,
        actor_username: str | None,
        subject_username: str | None,
        team_id: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """INSERT INTO access_audit
               (event_type, actor_username, subject_username, team_id, details_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                event_type,
                actor_username,
                subject_username,
                team_id,
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
                _now(),
            ),
        )

    @staticmethod
    def _account_from_row(row: sqlite3.Row) -> LocalAccount:
        role_value = row["role"]
        return LocalAccount(
            username=row["username"],
            display_name=row["display_name"],
            role=Role(role_value) if role_value else None,
            team_id=row["team_id"],
            requested_team=row["requested_team"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def has_administrator(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM accounts WHERE role = ? AND status = ? LIMIT 1",
                (Role.ADMINISTRATOR.value, AccountStatus.ACTIVE),
            ).fetchone()
        return row is not None

    def bootstrap_administrator(
        self, username: str, display_name: str, password: str,
    ) -> LocalAccount:
        """Crea el único administrador inicial antes de habilitar solicitudes."""

        username = _normalize_username(username)
        display_name = _validate_display_name(display_name)
        password = _validate_password(password)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT username FROM accounts WHERE role = ? LIMIT 1",
                (Role.ADMINISTRATOR.value,),
            ).fetchone()
            if existing:
                raise LocalAccountError("Ya existe un administrador local.")
            salt = secrets.token_bytes(16)
            now = _now()
            conn.execute(
                """INSERT INTO accounts
                   (username, display_name, password_salt, password_digest, role,
                    team_id, requested_team, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, NULL, '', ?, ?, ?)""",
                (
                    username,
                    display_name,
                    salt,
                    _password_digest(password, salt),
                    Role.ADMINISTRATOR.value,
                    AccountStatus.ACTIVE,
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                event_type="ADMIN_BOOTSTRAPPED",
                actor_username=username,
                subject_username=username,
                team_id=None,
            )
        return self.require_active_account(username)

    def request_access(
        self,
        username: str,
        display_name: str,
        password: str,
        requested_team: str = "",
    ) -> LocalAccount:
        """Registra una solicitud pendiente sin conceder un rol."""

        username = _normalize_username(username)
        display_name = _validate_display_name(display_name)
        password = _validate_password(password)
        requested_team = " ".join(str(requested_team or "").split())[:120]
        with self._connect() as conn:
            if conn.execute(
                "SELECT 1 FROM accounts WHERE username = ?", (username,),
            ).fetchone():
                raise LocalAccountError("Ese usuario ya tiene una solicitud o cuenta.")
            salt = secrets.token_bytes(16)
            now = _now()
            conn.execute(
                """INSERT INTO accounts
                   (username, display_name, password_salt, password_digest, role,
                    team_id, requested_team, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)""",
                (
                    username,
                    display_name,
                    salt,
                    _password_digest(password, salt),
                    requested_team,
                    AccountStatus.PENDING,
                    now,
                    now,
                ),
            )
            self._audit(
                conn,
                event_type="ACCESS_REQUESTED",
                actor_username=username,
                subject_username=username,
                team_id=None,
                details={"requested_team": requested_team},
            )
        return self.get_account(username)

    def authenticate(self, username: str, password: str) -> LocalAccount | None:
        """Valida credenciales sin revelar si el usuario existe o está pendiente."""

        try:
            username = _normalize_username(username)
        except LocalAccountError:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE username = ?", (username,),
            ).fetchone()
            if row is None or row["status"] != AccountStatus.ACTIVE:
                return None
            digest = _password_digest(str(password or ""), bytes(row["password_salt"]))
            if not hmac.compare_digest(digest, bytes(row["password_digest"])):
                return None
            self._audit(
                conn,
                event_type="LOGIN_SUCCEEDED",
                actor_username=username,
                subject_username=username,
                team_id=row["team_id"],
            )
        return self.require_active_account(username)

    def get_account(self, username: str) -> LocalAccount:
        username = _normalize_username(username)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE username = ?", (username,),
            ).fetchone()
        if row is None:
            raise LocalAccountError("La cuenta no existe.")
        return self._account_from_row(row)

    def require_active_account(self, username: str) -> LocalAccount:
        account = self.get_account(username)
        if account.status != AccountStatus.ACTIVE or account.role is None:
            raise LocalAccountAccessError("La cuenta no está activa.")
        return account

    def create_team(self, actor: Actor, name: str) -> Team:
        self._require_administrator(actor)
        name = " ".join(str(name or "").split())
        if not 2 <= len(name) <= 120:
            raise LocalAccountError("El equipo debe tener entre 2 y 120 caracteres.")
        team = Team(f"team-{secrets.token_hex(8)}", name, _now())
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO teams (team_id, name, created_at) VALUES (?, ?, ?)",
                    (team.team_id, team.name, team.created_at),
                )
            except sqlite3.IntegrityError as exc:
                raise LocalAccountError("Ya existe un equipo con ese nombre.") from exc
            self._audit(
                conn,
                event_type="TEAM_CREATED",
                actor_username=actor.actor_id,
                subject_username=None,
                team_id=team.team_id,
                details={"name": team.name},
            )
        return team

    def list_teams(self) -> list[Team]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT team_id, name, created_at FROM teams ORDER BY name COLLATE NOCASE",
            ).fetchall()
        return [Team(row["team_id"], row["name"], row["created_at"]) for row in rows]

    def list_pending_requests(self, actor: Actor) -> list[LocalAccount]:
        self._require_administrator(actor)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE status = ? ORDER BY created_at, username",
                (AccountStatus.PENDING,),
            ).fetchall()
        return [self._account_from_row(row) for row in rows]

    def list_active_accounts(self, actor: Actor) -> list[LocalAccount]:
        self._require_administrator(actor)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE status = ? ORDER BY username",
                (AccountStatus.ACTIVE,),
            ).fetchall()
        return [self._account_from_row(row) for row in rows]

    def approve_request(
        self, actor: Actor, username: str, role: Role, team_id: str,
    ) -> LocalAccount:
        """Aprueba una solicitud para uno de los tres roles de equipo."""

        self._require_administrator(actor)
        username = _normalize_username(username)
        if role not in _VALID_ASSIGNABLE_ROLES:
            raise LocalAccountError("La aprobación solo permite roles de equipo.")
        if not team_id:
            raise LocalAccountError("Debe asignar un equipo al aprobar acceso.")
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (team_id,)).fetchone():
                raise LocalAccountError("El equipo seleccionado no existe.")
            row = conn.execute(
                "SELECT status FROM accounts WHERE username = ?", (username,),
            ).fetchone()
            if row is None:
                raise LocalAccountError("La solicitud no existe.")
            if row["status"] != AccountStatus.PENDING:
                raise LocalAccountError("Solo se pueden aprobar solicitudes pendientes.")
            now = _now()
            conn.execute(
                """UPDATE accounts SET role = ?, team_id = ?, status = ?, updated_at = ?
                   WHERE username = ?""",
                (role.value, team_id, AccountStatus.ACTIVE, now, username),
            )
            self._audit(
                conn,
                event_type="ACCESS_APPROVED",
                actor_username=actor.actor_id,
                subject_username=username,
                team_id=team_id,
                details={"role": role.value},
            )
        return self.require_active_account(username)

    def deny_request(self, actor: Actor, username: str) -> LocalAccount:
        self._require_administrator(actor)
        username = _normalize_username(username)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM accounts WHERE username = ?", (username,),
            ).fetchone()
            if row is None or row["status"] != AccountStatus.PENDING:
                raise LocalAccountError("Solo se pueden rechazar solicitudes pendientes.")
            conn.execute(
                "UPDATE accounts SET status = ?, updated_at = ? WHERE username = ?",
                (AccountStatus.DENIED, _now(), username),
            )
            self._audit(
                conn,
                event_type="ACCESS_DENIED",
                actor_username=actor.actor_id,
                subject_username=username,
                team_id=None,
            )
        return self.get_account(username)

    def update_active_account(
        self, actor: Actor, username: str, role: Role, team_id: str,
    ) -> LocalAccount:
        """Reasigna un rol o equipo activo, sin habilitar otros administradores."""

        self._require_administrator(actor)
        username = _normalize_username(username)
        if role not in _VALID_ASSIGNABLE_ROLES:
            raise LocalAccountError("La reasignación solo permite roles de equipo.")
        if not team_id:
            raise LocalAccountError("Debe asignar un equipo.")
        with self._connect() as conn:
            if not conn.execute("SELECT 1 FROM teams WHERE team_id = ?", (team_id,)).fetchone():
                raise LocalAccountError("El equipo seleccionado no existe.")
            row = conn.execute(
                "SELECT role, status FROM accounts WHERE username = ?", (username,),
            ).fetchone()
            if row is None or row["status"] != AccountStatus.ACTIVE:
                raise LocalAccountError("Solo se pueden reasignar cuentas activas.")
            if row["role"] == Role.ADMINISTRATOR.value:
                raise LocalAccountError("El administrador inicial no se reasigna desde esta pantalla.")
            conn.execute(
                """UPDATE accounts SET role = ?, team_id = ?, updated_at = ?
                   WHERE username = ?""",
                (role.value, team_id, _now(), username),
            )
            self._audit(
                conn,
                event_type="ACCOUNT_REASSIGNED",
                actor_username=actor.actor_id,
                subject_username=username,
                team_id=team_id,
                details={"role": role.value},
            )
        return self.require_active_account(username)

    def disable_account(self, actor: Actor, username: str) -> LocalAccount:
        self._require_administrator(actor)
        username = _normalize_username(username)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT role, status, team_id FROM accounts WHERE username = ?", (username,),
            ).fetchone()
            if row is None or row["status"] != AccountStatus.ACTIVE:
                raise LocalAccountError("Solo se pueden deshabilitar cuentas activas.")
            if row["role"] == Role.ADMINISTRATOR.value:
                raise LocalAccountError("El administrador inicial no se deshabilita desde esta pantalla.")
            conn.execute(
                "UPDATE accounts SET status = ?, updated_at = ? WHERE username = ?",
                (AccountStatus.DISABLED, _now(), username),
            )
            self._audit(
                conn,
                event_type="ACCOUNT_DISABLED",
                actor_username=actor.actor_id,
                subject_username=username,
                team_id=row["team_id"],
            )
        return self.get_account(username)

    def list_audit(self, actor: Actor, limit: int = 100) -> list[dict[str, Any]]:
        self._require_administrator(actor)
        safe_limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT event_type, actor_username, subject_username, team_id,
                          details_json, created_at
                   FROM access_audit ORDER BY id DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [
            {
                "event_type": row["event_type"],
                "actor_username": row["actor_username"],
                "subject_username": row["subject_username"],
                "team_id": row["team_id"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


__all__ = [
    "AccountStatus",
    "LocalAccount",
    "LocalAccountAccessError",
    "LocalAccountError",
    "LocalAccountStore",
    "Team",
    "default_local_accounts_path",
]
