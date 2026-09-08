from __future__ import annotations

from datetime import datetime, timezone

import pytest

from persistence.contracts import (
    AuthenticatedActor,
    AuthenticationRequest,
    AuthenticationRequired,
    AuthorizationDenied,
    DenyAllIdentityProvider,
    IdentityProvider,
    audit_event_for_actor,
    require_role,
)


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def _actor(*roles: str) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id="local:u-123",
        display_name="Analista Uno",
        organization_id="org-1",
        roles=frozenset(roles),
        provider_subject="subject-123",
    )


def test_default_identity_provider_denies_every_request() -> None:
    provider = DenyAllIdentityProvider()
    assert isinstance(provider, IdentityProvider)
    with pytest.raises(AuthenticationRequired, match="no configurado"):
        provider.authenticate(AuthenticationRequest(credentials={}))
    with pytest.raises(AuthenticationRequired, match="no configurado"):
        provider.authenticate(AuthenticationRequest(
            credentials={"X-User": "admin", "X-Role": "admin"},
        ))


def test_actor_rejects_empty_or_unknown_roles() -> None:
    with pytest.raises(ValueError, match="al menos un rol"):
        _actor()
    with pytest.raises(ValueError, match="Roles de identidad inválidos"):
        _actor("owner")


def test_role_hierarchy_is_explicit_and_fails_closed() -> None:
    require_role(_actor("analyst"), "analyst")
    require_role(_actor("supervisor"), "analyst")
    require_role(_actor("admin"), "supervisor")
    with pytest.raises(AuthorizationDenied, match="supervisor"):
        require_role(_actor("analyst"), "supervisor")
    with pytest.raises(AuthenticationRequired):
        require_role(None, "analyst")


def test_audit_event_requires_and_propagates_authenticated_actor() -> None:
    actor = _actor("supervisor")
    event = audit_event_for_actor(
        actor,
        occurred_at=NOW,
        action="REPORT_APPROVED",
        subject_type="report",
        subject_id="report-1",
        details={"execution_id": "execution-1"},
    )
    assert event.actor_id == actor.actor_id
    assert event.details == {
        "execution_id": "execution-1",
        "organization_id": "org-1",
        "roles": ["supervisor"],
    }
    with pytest.raises(AuthenticationRequired, match="sin actor"):
        audit_event_for_actor(
            None,
            occurred_at=NOW,
            action="REPORT_APPROVED",
            subject_type="report",
            subject_id="report-1",
        )
