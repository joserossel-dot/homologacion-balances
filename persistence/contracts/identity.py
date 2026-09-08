"""Contratos neutrales de identidad y autorización.

Este módulo no autentica credenciales ni selecciona un proveedor. El proveedor
corporativo debe entregar un ``AuthenticatedActor`` ya verificado. Mientras no
exista esa integración, ``DenyAllIdentityProvider`` impide crear una identidad
implícita o confiar en cabeceras aportadas por el cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, FrozenSet, Literal, Mapping, Protocol, runtime_checkable

from .audit import AuditEvent


IdentityRole = Literal["analyst", "supervisor", "admin"]


class AuthenticationRequired(PermissionError):
    """No existe una identidad autenticada por un proveedor confiable."""


class AuthorizationDenied(PermissionError):
    """La identidad autenticada no tiene el rol exigido."""


@dataclass(frozen=True, slots=True)
class AuthenticationRequest:
    """Datos opacos entregados a una futura integración corporativa.

    ``credentials`` no debe persistirse ni copiarse a eventos de auditoría.
    """

    credentials: Mapping[str, str]
    client_address: str | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    actor_id: str
    display_name: str
    organization_id: str
    roles: FrozenSet[IdentityRole]
    provider_subject: str

    def __post_init__(self) -> None:
        for field_name in (
            "actor_id", "display_name", "organization_id", "provider_subject",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} es obligatorio")
        if not self.roles:
            raise ValueError("La identidad debe contener al menos un rol")
        invalid = set(self.roles) - {"analyst", "supervisor", "admin"}
        if invalid:
            raise ValueError("Roles de identidad inválidos: " + ", ".join(sorted(invalid)))


@runtime_checkable
class IdentityProvider(Protocol):
    def authenticate(self, request: AuthenticationRequest) -> AuthenticatedActor: ...


class DenyAllIdentityProvider:
    """Proveedor seguro por defecto hasta configurar OIDC, AD u otro adaptador."""

    def authenticate(self, request: AuthenticationRequest) -> AuthenticatedActor:
        del request
        raise AuthenticationRequired("Proveedor de identidad no configurado")


_ROLE_RANK: dict[IdentityRole, int] = {
    "analyst": 10,
    "supervisor": 20,
    "admin": 30,
}


def require_role(actor: AuthenticatedActor | None, minimum: IdentityRole) -> None:
    """Autoriza por jerarquía y deniega ante ausencia o rol desconocido."""

    if actor is None:
        raise AuthenticationRequired("Identidad autenticada obligatoria")
    required_rank = _ROLE_RANK[minimum]
    if not any(_ROLE_RANK[role] >= required_rank for role in actor.roles):
        raise AuthorizationDenied(f"Se requiere rol {minimum}")


def audit_event_for_actor(
    actor: AuthenticatedActor | None,
    *,
    occurred_at: datetime,
    action: str,
    subject_type: str,
    subject_id: str,
    details: Mapping[str, Any] | None = None,
) -> AuditEvent:
    """Crea un evento con actor obligatorio y sin propagar credenciales."""

    if actor is None:
        raise AuthenticationRequired("No se puede auditar una acción sin actor")
    safe_details = dict(details or {})
    safe_details.setdefault("organization_id", actor.organization_id)
    safe_details.setdefault("roles", sorted(actor.roles))
    return AuditEvent(
        event_id=None,
        occurred_at=occurred_at,
        actor_id=actor.actor_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        details=safe_details,
    )
