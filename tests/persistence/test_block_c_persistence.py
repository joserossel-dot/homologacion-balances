"""Pruebas rigurosas para el Bloque C: persistencia, aislamiento multi-org y auditoría."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import pytest

from persistence.contracts.identity import AuthenticatedActor
from persistence.contracts.promotions import PromotionOutcomeRecord, PromotionPolicyRecord
from persistence.local.sqlite_operational import SqliteOperationalRepository
from persistence.promotion_metadata import (
    build_promotion_policy_record,
    validate_promotion_outcome,
)
from scripts.audit_local_promotion_backlog import audit_local_backlog
from validation.promotion_policy import MINIMUM_EVIDENCE


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _make_actor(actor_id: str, org_id: str, role: str = "supervisor") -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id=actor_id,
        display_name=f"User {actor_id}",
        organization_id=org_id,
        roles=frozenset({role}),
        provider_subject=f"oidc-{actor_id}",
    )


def _make_policy(
    actor: AuthenticatedActor,
    subject_id: str = "batch:org-test-1",
    evaluation_id: str = "11111111-1111-4111-8111-111111111111",
    approved: bool = True,
) -> PromotionPolicyRecord:
    evidence = {k: f"evidence:{k}" for k in MINIMUM_EVIDENCE} if approved else {}
    return build_promotion_policy_record(
        subject_id=subject_id,
        actor=actor,
        evidence=evidence,
        conflicts=0,
        approved=approved,
        reversal_reference="rev:test-1",
        evaluated_at=NOW,
        evaluation_id=evaluation_id,
    )


def test_multi_organization_isolation_two_orgs(tmp_path):
    """Verifica que dos organizaciones en la misma base operen con estricto aislamiento."""
    db_path = tmp_path / "multi_org.sqlite"
    repo = SqliteOperationalRepository(db_path)

    actor_a = _make_actor("sup-org-a", "org-alpha")
    actor_b = _make_actor("sup-org-b", "org-beta")

    policy_a = _make_policy(actor_a, subject_id="batch:alpha-01", evaluation_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    policy_b = _make_policy(actor_b, subject_id="batch:beta-01", evaluation_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    repo.save_promotion_policy_metadata(policy_a)
    repo.save_promotion_policy_metadata(policy_b)

    # Org Alpha sólo ve sus propias políticas
    assert repo.get_promotion_policy_metadata(policy_a.evaluation_id, organization_id="org-alpha") == policy_a
    assert repo.get_promotion_policy_metadata(policy_a.evaluation_id, organization_id="org-beta") is None

    # Org Beta sólo ve sus propias políticas
    assert repo.get_promotion_policy_metadata(policy_b.evaluation_id, organization_id="org-beta") == policy_b
    assert repo.get_promotion_policy_metadata(policy_b.evaluation_id, organization_id="org-alpha") is None

    # Intentar aplicar outcome de Org Beta a la política de Org Alpha debe fallar
    outcome_cross = PromotionOutcomeRecord(
        evaluation_id=policy_a.evaluation_id,
        subject_id=policy_a.subject_id,
        organization_id="org-beta",
        actor_id=actor_b.actor_id,
        status="APPLIED",
        occurred_at=NOW,
        promotion_ids=("row-1",),
        error=None,
    )
    with pytest.raises(ValueError, match="no coincide"):
        repo.save_promotion_outcome(outcome_cross)

    # Outcome legítimo para Alpha
    outcome_a = PromotionOutcomeRecord(
        evaluation_id=policy_a.evaluation_id,
        subject_id=policy_a.subject_id,
        organization_id="org-alpha",
        actor_id=actor_a.actor_id,
        status="APPLIED",
        occurred_at=NOW,
        promotion_ids=("row-alpha-1",),
        error=None,
    )
    repo.save_promotion_outcome(outcome_a)

    # Org Beta no puede ver outcomes de Org Alpha
    assert repo.get_promotion_outcome(policy_a.evaluation_id, organization_id="org-beta") is None
    assert repo.list_promotion_outcomes_for_subject("batch:alpha-01", organization_id="org-beta") == []
    assert len(repo.list_promotion_outcomes_for_subject("batch:alpha-01", organization_id="org-alpha")) == 1


def test_durable_restart_and_idempotence(tmp_path):
    """Verifica persistencia durable tras reconectar e idempotencia de outcomes."""
    db_path = tmp_path / "durable.sqlite"
    repo1 = SqliteOperationalRepository(db_path)
    actor = _make_actor("sup-durable", "org-durable")
    policy = _make_policy(actor, subject_id="batch:dur-1", evaluation_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    repo1.save_promotion_policy_metadata(policy)

    outcome = PromotionOutcomeRecord(
        evaluation_id=policy.evaluation_id,
        subject_id=policy.subject_id,
        organization_id="org-durable",
        actor_id=actor.actor_id,
        status="APPLIED",
        occurred_at=NOW,
        promotion_ids=("row-dur-1", "row-dur-2"),
        error=None,
    )
    saved1 = repo1.save_promotion_outcome(outcome)
    saved2 = repo1.save_promotion_outcome(outcome)  # idempotente
    assert saved1 == saved2

    # Reinicio completo (nueva instancia de repositorio sobre el mismo archivo)
    repo2 = SqliteOperationalRepository(db_path)
    loaded = repo2.get_promotion_outcome(policy.evaluation_id, organization_id="org-durable")
    assert loaded == outcome

    # Triggers impiden modificación y eliminación
    with repo2._connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE local_promotion_outcomes SET status='FAILED'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM local_promotion_outcomes")


def test_applied_outcome_cannot_have_error():
    """Un fallo nunca debe aparecer como APPLIED."""
    outcome_with_error = PromotionOutcomeRecord(
        evaluation_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        subject_id="batch:err-1",
        organization_id="org-1",
        actor_id="sup-1",
        status="APPLIED",
        occurred_at=NOW,
        promotion_ids=("row-1",),
        error="some error message",
    )
    with pytest.raises(ValueError, match="APPLIED no permite error"):
        validate_promotion_outcome(outcome_with_error)


def test_failed_outcome_requires_normalized_error(tmp_path):
    """FAILED e INCONSISTENT exigen error explicativo no vacío."""
    db_path = tmp_path / "failed_outcome.sqlite"
    repo = SqliteOperationalRepository(db_path)
    actor = _make_actor("sup-failed", "org-failed")
    policy = _make_policy(actor, subject_id="batch:fail-1", evaluation_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    repo.save_promotion_policy_metadata(policy)

    # FAILED sin error es rechazado
    outcome_no_err = PromotionOutcomeRecord(
        evaluation_id=policy.evaluation_id,
        subject_id=policy.subject_id,
        organization_id="org-failed",
        actor_id=actor.actor_id,
        status="FAILED",
        occurred_at=NOW,
        promotion_ids=(),
        error=None,
    )
    with pytest.raises(ValueError, match="exige error normalizado"):
        repo.save_promotion_outcome(outcome_no_err)

    # FAILED con error es aceptado y marca la evaluación como resuelta
    outcome_ok = PromotionOutcomeRecord(
        evaluation_id=policy.evaluation_id,
        subject_id=policy.subject_id,
        organization_id="org-failed",
        actor_id=actor.actor_id,
        status="FAILED",
        occurred_at=NOW,
        promotion_ids=(),
        error="Fallo de conexión en base de datos secundaria",
    )
    repo.save_promotion_outcome(outcome_ok)
    assert repo.list_unresolved_promotion_evaluations("batch:fail-1", organization_id="org-failed") == []


def test_authorization_requires_explicit_non_generic_supervisor():
    """No se permite actor None, rol analista ni actores genéricos por defecto."""
    with pytest.raises(PermissionError):
        build_promotion_policy_record(
            subject_id="batch:auth-1",
            actor=None,
            evidence={},
            conflicts=0,
            approved=True,
            reversal_reference="rev:1",
        )

    # Rol analista no está autorizado
    analyst = _make_actor("analyst-1", "org-1", role="analyst")
    with pytest.raises(PermissionError):
        build_promotion_policy_record(
            subject_id="batch:auth-1",
            actor=analyst,
            evidence={k: f"evidence:{k}" for k in MINIMUM_EVIDENCE},
            conflicts=0,
            approved=True,
            reversal_reference="rev:1",
        )

    # Actor genérico rechazado
    generic_sup = _make_actor("supervisor", "org-1", role="supervisor")
    with pytest.raises(ValueError, match="individual, no genérico"):
        build_promotion_policy_record(
            subject_id="batch:auth-1",
            actor=generic_sup,
            evidence={k: f"evidence:{k}" for k in MINIMUM_EVIDENCE},
            conflicts=0,
            approved=True,
            reversal_reference="rev:1",
        )


def test_approval_without_minimum_evidence_is_denied():
    """Aprobación sin evidencia mínima genera allowed=False."""
    actor = _make_actor("sup-valid", "org-1")
    policy = build_promotion_policy_record(
        subject_id="batch:no-ev",
        actor=actor,
        evidence={},  # Sin evidencia requerida
        conflicts=0,
        approved=True,
        reversal_reference="rev:1",
        evaluated_at=NOW,
    )
    assert policy.allowed is False
    assert len(policy.decision_reasons) > 0
