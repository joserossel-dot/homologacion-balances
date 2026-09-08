from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sqlite3

import pytest

from persistence.contracts.identity import AuthenticatedActor
from persistence.contracts.promotions import PromotionOutcomeRecord
from persistence.local.sqlite_operational import SqliteOperationalRepository
from persistence.neon_store import NeonKnowledgeStore
from persistence.promotion_metadata import build_promotion_policy_record
from validation.promotion_policy import MINIMUM_EVIDENCE


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _policy(*, allowed: bool = True):
    actor = AuthenticatedActor(
        actor_id="supervisor-42",
        display_name="Supervisor 42",
        organization_id="org-1",
        roles=frozenset({"supervisor"}),
        provider_subject="oidc-subject-42",
    )
    evidence = (
        {key: f"evidence:{key}" for key in MINIMUM_EVIDENCE}
        if allowed else {}
    )
    return build_promotion_policy_record(
        subject_id="gold-runtime-batch:abc123",
        actor=actor,
        evidence=evidence,
        conflicts=0,
        approved=True,
        reversal_reference="promotion-history:batch-42",
        evaluated_at=NOW,
        evaluation_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )


def _outcome(**overrides):
    values = {
        "evaluation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "subject_id": "gold-runtime-batch:abc123",
        "organization_id": "org-1",
        "actor_id": "supervisor-42",
        "status": "APPLIED",
        "occurred_at": NOW,
        "promotion_ids": ("runtime-row:1", "runtime-row:2"),
        "error": None,
    }
    values.update(overrides)
    return PromotionOutcomeRecord(**values)


def test_local_outcome_round_trip_is_batch_append_only_and_org_scoped(tmp_path):
    database = tmp_path / "operations.db"
    repository = SqliteOperationalRepository(database)
    policy = _policy()
    outcome = _outcome()
    repository.save_promotion_policy_metadata(policy)

    assert repository.list_unresolved_promotion_evaluations(
        policy.subject_id, organization_id="org-1",
    ) == [policy]
    assert repository.save_promotion_outcome(outcome) == outcome
    assert repository.save_promotion_outcome(outcome) == outcome

    reopened = SqliteOperationalRepository(database)
    assert reopened.get_promotion_outcome(
        policy.evaluation_id, organization_id="org-1",
    ) == outcome
    assert reopened.get_promotion_outcome(
        policy.evaluation_id, organization_id="org-2",
    ) is None
    assert reopened.list_promotion_outcomes_for_subject(
        policy.subject_id, organization_id="org-1",
    ) == [outcome]
    assert reopened.list_unresolved_promotion_evaluations(
        policy.subject_id, organization_id="org-1",
    ) == []
    with reopened._connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM local_promotion_outcomes"
        ).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM local_promotion_outcomes")


def test_outcome_rejects_missing_policy_denied_policy_and_cross_org(tmp_path):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    with pytest.raises(ValueError, match="no existe"):
        repository.save_promotion_outcome(_outcome())

    denied = _policy(allowed=False)
    repository.save_promotion_policy_metadata(denied)
    with pytest.raises(ValueError, match="denegada"):
        repository.save_promotion_outcome(_outcome())

    allowed = replace(denied, allowed=True)
    # Nueva base evita colisionar el evaluation_id append-only del caso denegado.
    other = SqliteOperationalRepository(tmp_path / "allowed.db")
    other.save_promotion_policy_metadata(allowed)
    with pytest.raises(ValueError, match="sujeto u organización"):
        other.save_promotion_outcome(_outcome(organization_id="org-2"))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"promotion_ids": ()}, "promotion_id"),
        ({"promotion_ids": ("runtime-row:1", "runtime-row:1")}, "duplicados"),
        ({"actor_id": "supervisor"}, "individual"),
        ({"status": "FAILED", "promotion_ids": (), "error": None}, "exige error"),
    ],
)
def test_outcome_contract_fails_closed(tmp_path, changes, message):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    repository.save_promotion_policy_metadata(_policy())
    with pytest.raises(ValueError, match=message):
        repository.save_promotion_outcome(_outcome(**changes))


def test_failed_outcome_is_terminal_and_can_capture_partial_ids(tmp_path):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    policy = _policy()
    repository.save_promotion_policy_metadata(policy)
    outcome = _outcome(
        status="FAILED",
        promotion_ids=("runtime-row:1",),
        error="runtime promotion failed after first row",
    )
    repository.save_promotion_outcome(outcome)
    assert repository.list_unresolved_promotion_evaluations(
        policy.subject_id, organization_id="org-1",
    ) == []
    assert repository.get_promotion_outcome(
        policy.evaluation_id, organization_id="org-1",
    ) == outcome


def test_inconsistent_outcome_keeps_evaluation_unresolved(tmp_path):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    policy = _policy()
    repository.save_promotion_policy_metadata(policy)
    repository.save_promotion_outcome(_outcome(
        status="INCONSISTENT",
        promotion_ids=("runtime-row:1",),
        error="promotion applied but durable identifiers are incomplete",
    ))
    assert repository.list_unresolved_promotion_evaluations(
        policy.subject_id, organization_id="org-1",
    ) == [policy]


class _Cursor:
    def __init__(self, one_results=(), all_results=()):
        self.one_results = list(one_results)
        self.all_results = list(all_results)
        self.executions = []

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))
    def fetchone(self):
        return self.one_results.pop(0) if self.one_results else None
    def fetchall(self):
        return self.all_results.pop(0) if self.all_results else []


class _Connection:
    def __init__(self, cursor): self.cursor_value = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_value


def test_neon_outcome_write_is_batch_append_only_and_policy_bound():
    cursor = _Cursor(one_results=[
        ("gold-runtime-batch:abc123", "org-1", True),
        ("fingerprint",),
    ])
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: _Connection(cursor),
    )
    outcome = _outcome()
    assert store.save_promotion_outcome(outcome) == outcome
    insert_sql, params = cursor.executions[1]
    assert insert_sql.startswith("INSERT INTO promotion_outcomes")
    assert "ON CONFLICT (record_fingerprint) DO NOTHING" in insert_sql
    assert "UPDATE" not in insert_sql and "DELETE" not in insert_sql
    assert params[6] == '["runtime-row:1","runtime-row:2"]'


def test_neon_unresolved_query_only_treats_applied_and_failed_as_terminal():
    cursor = _Cursor(all_results=[[]])
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: _Connection(cursor),
    )
    assert store.list_unresolved_promotion_evaluations(
        "gold-runtime-batch:abc123", organization_id="org-1",
    ) == []
    sql, params = cursor.executions[0]
    assert "o.status IN ('APPLIED', 'FAILED')" in sql
    assert params == ("gold-runtime-batch:abc123", "org-1", 100)


def test_neon_outcome_migrations_include_batch_upgrade(tmp_path):
    first = tmp_path / "004.sql"
    first.write_text("SELECT 4;", encoding="utf-8")
    cursor = _Cursor()
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: _Connection(cursor),
    )
    store.initialize_promotion_outcomes(first)
    assert cursor.executions == [("SELECT 4;", None)]
