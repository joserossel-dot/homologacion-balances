"""Modelo de autorización por rol y equipo.

Este módulo no autentica usuarios. Recibe una identidad ya confiable desde la
capa que corresponda al despliegue y aplica una política que falla cerrada.
No debe usarse ``st.session_state`` ni un selector de interfaz como fuente de
identidad: ambos son contexto de presentación, no autenticación.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Mapping


class Role(str, Enum):
    """Roles operativos definidos para el servicio."""

    DATA_ENTRY = "data_entry"
    ANALYST = "analyst"
    MANAGEMENT = "management"
    ADMINISTRATOR = "administrator"


class Permission(str, Enum):
    """Acciones protegidas, independientes de la interfaz."""

    ENTRY_UPLOAD = "entry.upload"
    ENTRY_VIEW_OWN = "entry.view_own"
    ENTRY_EDIT_OWN = "entry.edit_own"
    ENTRY_SUBMIT = "entry.submit"
    ENTRY_VIEW_TEAM = "entry.view_team"
    ENTRY_EDIT_TEAM = "entry.edit_team"
    ACCOUNT_CLASSIFY = "account.classify"
    ACCOUNT_REVIEW = "account.review"
    EXPORT_REVIEW_PACKAGE = "export.review_package"
    DELIVERY_APPROVE = "delivery.approve"
    DICTIONARY_PROPOSE = "dictionary.propose"
    TEAM_DICTIONARY_ACTIVATE = "dictionary.team_activate"
    TEAM_DICTIONARY_UNASSIGN = "dictionary.team_unassign"
    TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW = "dictionary.team_submit_global_review"
    GLOBAL_DICTIONARY_PROMOTION_REVIEW = "dictionary.global_promotion_review"
    GLOBAL_DICTIONARY_EDIT = "dictionary.global_edit"
    TEAM_AUDIT_VIEW = "audit.team_view"
    ROLE_MANAGE = "role.manage"
    SYSTEM_CONFIGURE = "system.configure"
    AUDIT_ERASE = "audit.erase"


@dataclass(frozen=True)
class Actor:
    """Identidad autenticada que llega desde la capa de acceso."""

    actor_id: str
    role: Role
    team_id: str | None = None

    def __post_init__(self) -> None:
        if not self.actor_id or not self.actor_id.strip():
            raise ValueError("actor_id es obligatorio")
        if self.role is not Role.ADMINISTRATOR and not self.team_id:
            raise ValueError("team_id es obligatorio fuera del rol administrador")


@dataclass(frozen=True)
class ResourceScope:
    """Alcance del recurso sobre el que se solicita una acción."""

    team_id: str | None = None
    owner_id: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    requires_audit: bool


_ROLE_PERMISSIONS: Mapping[Role, FrozenSet[Permission]] = {
    Role.DATA_ENTRY: frozenset({
        Permission.ENTRY_UPLOAD,
        Permission.ENTRY_VIEW_OWN,
        Permission.ENTRY_EDIT_OWN,
        Permission.ENTRY_SUBMIT,
    }),
    Role.ANALYST: frozenset({
        Permission.ENTRY_VIEW_TEAM,
        Permission.ACCOUNT_CLASSIFY,
        Permission.ACCOUNT_REVIEW,
        Permission.EXPORT_REVIEW_PACKAGE,
        Permission.DICTIONARY_PROPOSE,
        Permission.TEAM_AUDIT_VIEW,
    }),
    Role.MANAGEMENT: frozenset({
        Permission.ENTRY_VIEW_TEAM,
        Permission.ENTRY_EDIT_TEAM,
        Permission.ACCOUNT_CLASSIFY,
        Permission.ACCOUNT_REVIEW,
        Permission.EXPORT_REVIEW_PACKAGE,
        Permission.DELIVERY_APPROVE,
        Permission.DICTIONARY_PROPOSE,
        Permission.TEAM_DICTIONARY_ACTIVATE,
        Permission.TEAM_DICTIONARY_UNASSIGN,
        Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW,
        Permission.TEAM_AUDIT_VIEW,
    }),
    Role.ADMINISTRATOR: frozenset(
        permission
        for permission in Permission
        if permission is not Permission.AUDIT_ERASE
    ),
}

_OWNER_SCOPED = frozenset({
    Permission.ENTRY_UPLOAD,
    Permission.ENTRY_VIEW_OWN,
    Permission.ENTRY_EDIT_OWN,
    Permission.ENTRY_SUBMIT,
})

_TEAM_SCOPED = frozenset({
    Permission.ENTRY_VIEW_TEAM,
    Permission.ENTRY_EDIT_TEAM,
    Permission.ACCOUNT_CLASSIFY,
    Permission.ACCOUNT_REVIEW,
    Permission.EXPORT_REVIEW_PACKAGE,
    Permission.DELIVERY_APPROVE,
    Permission.DICTIONARY_PROPOSE,
    Permission.TEAM_DICTIONARY_ACTIVATE,
    Permission.TEAM_DICTIONARY_UNASSIGN,
    Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW,
    Permission.TEAM_AUDIT_VIEW,
})

_AUDITED_MUTATIONS = frozenset({
    Permission.ENTRY_UPLOAD,
    Permission.ENTRY_EDIT_OWN,
    Permission.ENTRY_SUBMIT,
    Permission.ENTRY_EDIT_TEAM,
    Permission.ACCOUNT_CLASSIFY,
    Permission.ACCOUNT_REVIEW,
    Permission.DELIVERY_APPROVE,
    Permission.DICTIONARY_PROPOSE,
    Permission.TEAM_DICTIONARY_ACTIVATE,
    Permission.TEAM_DICTIONARY_UNASSIGN,
    Permission.TEAM_DICTIONARY_SUBMIT_GLOBAL_REVIEW,
    Permission.GLOBAL_DICTIONARY_PROMOTION_REVIEW,
    Permission.GLOBAL_DICTIONARY_EDIT,
    Permission.ROLE_MANAGE,
    Permission.SYSTEM_CONFIGURE,
})


def permissions_for(role: Role) -> FrozenSet[Permission]:
    """Devuelve los permisos declarados para un rol sin concederlos."""

    return _ROLE_PERMISSIONS[role]


def authorize(
    actor: Actor | None,
    permission: Permission,
    resource: ResourceScope | None = None,
) -> AuthorizationDecision:
    """Evalúa una acción con denegación por defecto.

    Las operaciones de equipo necesitan un recurso con ``team_id``. Eso impide
    que una jefatura modifique por error un registro global del diccionario.
    ``AUDIT_ERASE`` se deniega incluso al administrador: el historial es
    evidencia operativa y debe conservarse de manera append-only.
    """

    audit_required = permission in _AUDITED_MUTATIONS
    if actor is None:
        return AuthorizationDecision(False, "identity_required", audit_required)
    if permission is Permission.AUDIT_ERASE:
        return AuthorizationDecision(False, "audit_history_is_append_only", True)
    if permission not in _ROLE_PERMISSIONS[actor.role]:
        return AuthorizationDecision(False, "role_not_permitted", audit_required)
    if actor.role is Role.ADMINISTRATOR:
        return AuthorizationDecision(True, "administrator", audit_required)
    if permission in _OWNER_SCOPED:
        if resource is None or not resource.team_id or not resource.owner_id:
            return AuthorizationDecision(False, "owner_scope_required", audit_required)
        if resource.team_id != actor.team_id:
            return AuthorizationDecision(False, "outside_team", audit_required)
        if resource.owner_id != actor.actor_id:
            return AuthorizationDecision(False, "not_resource_owner", audit_required)
    if permission in _TEAM_SCOPED:
        if resource is None or not resource.team_id:
            return AuthorizationDecision(False, "team_scope_required", audit_required)
        if resource.team_id != actor.team_id:
            return AuthorizationDecision(False, "outside_team", audit_required)
    return AuthorizationDecision(True, "role_and_scope_permitted", audit_required)


__all__ = [
    "Actor",
    "AuthorizationDecision",
    "Permission",
    "ResourceScope",
    "Role",
    "authorize",
    "permissions_for",
]
