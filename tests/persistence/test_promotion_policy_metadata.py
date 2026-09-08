from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import inspect
from pathlib import Path
import sqlite3

import pytest

from persistence.contracts.identity import (
    AuthenticatedActor,
    AuthenticationRequired,
    AuthorizationDenied,
)
from persistence.contracts.promotions import PromotionPolicyRecord
from persistence.contracts.promotions import PromotionPolicyRepository
from persistence.neon_store import NeonKnowledgeStore
from persistence.local.sqlite_operational import SqliteOperationalRepository
from persistence.promotion_metadata import build_promotion_policy_record
from validation.promotion_policy import MINIMUM_EVIDENCE


NOW = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)


def _actor(role: str = "supervisor") -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_id="actor-supervisor-1",
        display_name="Supervisor Uno",
        organization_id="org-1",
        roles=frozenset({role}),
        provider_subject="provider-subject-1",
    )


def _evidence() -> dict[str, str]:
    return {key: f"evidence:{key}" for key in MINIMUM_EVIDENCE}


def _record(**overrides) -> PromotionPolicyRecord:
    values = {
        "subject_id": "gold-record:42",
        "actor": _actor(),
        "evidence": _evidence(),
        "conflicts": 0,
        "approved": True,
        "reversal_reference": "promotion-history:42",
        "evaluated_at": NOW,
        "evaluation_id": "12345678123456781234567812345678",
    }
    values.update(overrides)
    return build_promotion_policy_record(**values)


def test_build_requires_explicit_authenticated_supervisor_and_org():
    with pytest.raises(AuthenticationRequired):
        _record(actor=None)
    with pytest.raises(AuthorizationDenied):
        _record(actor=_actor("analyst"))
    record = _record()
    assert record.supervisor_actor_id == "actor-supervisor-1"
    assert record.evaluation_id == "12345678-1234-5678-1234-567812345678"
    assert record.organization_id == "org-1"
    assert record.supervisor_role == "supervisor"
    assert record.allowed is True
    assert record.expires_at.isoformat() == "2027-08-30T18:00:00+00:00"
    assert record.reversal_reference == "promotion-history:42"


def test_missing_evidence_is_persistible_as_denied_not_approved():
    record = _record(evidence={})
    assert record.allowed is False
    assert any("evidencia" in reason.lower() for reason in record.decision_reasons)


def test_no_generic_reviewer_default_exists_on_promotion_method():
    signature = inspect.signature(NeonKnowledgeStore.save_promotion_policy_metadata)
    assert list(signature.parameters) == ["self", "record"]
    assert "reviewer" not in signature.parameters
    store = NeonKnowledgeStore(database_url="unused")
    assert isinstance(store, PromotionPolicyRepository)
    with pytest.raises(ValueError, match="individual"):
        store.save_promotion_policy_metadata(
            PromotionPolicyRecord(
                evaluation_id="12345678-1234-5678-1234-567812345678",
                subject_id="gold-record:42", policy_mode="manual_supervisor",
                allowed=True, decision_reasons=(), evidence=_evidence(),
                supervisor_actor_id="analista", supervisor_role="supervisor",
                organization_id="org-1", conflict_count=0,
                evaluated_at=NOW,
                expires_at=datetime(2027, 8, 30, 18, 0, tzinfo=timezone.utc),
                reversal_reference="promotion-history:42",
            )
        )


def test_legacy_validation_path_rejects_promotion_even_with_generic_default():
    store = NeonKnowledgeStore(database_url="unused")
    with pytest.raises(ValueError, match="actor supervisor"):
        store.save_validation(
            account_name="Cuenta", validated_code="AC.01",
            source="runtime_promotion",
        )
    with pytest.raises(ValueError, match="actor supervisor"):
        store.save_validations([{
            "account_name": "Cuenta", "validated_code": "AC.01",
            "source": "promocion_manual_supervisor",
        }])


def test_builder_rejects_generic_supervisor_actor_even_with_role():
    actor = AuthenticatedActor(
        actor_id="supervisor", display_name="Supervisor genérico",
        organization_id="org-1", roles=frozenset({"supervisor"}),
        provider_subject="provider-subject-generic",
    )
    with pytest.raises(ValueError, match="individual"):
        _record(actor=actor)


class Cursor:
    def __init__(self):
        self.executions = []
        self.next_one = [("12345678-1234-5678-1234-567812345678",)]

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params=None):
        self.executions.append((" ".join(sql.split()), params))
    def fetchone(self):
        return self.next_one.pop(0) if self.next_one else None


class Connection:
    def __init__(self): self.cursor_value = Cursor()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self.cursor_value


def test_neon_save_is_append_only_idempotent_and_contains_required_metadata():
    connection = Connection()
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: connection,
    )
    record = _record()
    assert store.save_promotion_policy_metadata(record) == record
    sql, params = connection.cursor_value.executions[0]
    assert sql.startswith("INSERT INTO promotion_policy_metadata")
    assert "ON CONFLICT (evaluation_id) DO NOTHING" in sql
    assert "UPDATE" not in sql and "DELETE" not in sql
    assert params[6] == "actor-supervisor-1"
    assert params[8] == "org-1"
    assert params[12] == "promotion-history:42"


def test_promotion_metadata_migration_is_explicit(tmp_path):
    connection = Connection()
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: connection,
    )
    migration = tmp_path / "migration.sql"
    migration.write_text("SELECT 1;", encoding="utf-8")
    store.initialize_promotion_policy_metadata(migration)
    assert connection.cursor_value.executions == [("SELECT 1;", None)]


def test_same_evaluation_id_with_different_fingerprint_is_rejected():
    connection = Connection()
    connection.cursor_value.next_one = [None, ("0" * 64,)]
    store = NeonKnowledgeStore(
        "postgresql://placeholder", connect=lambda _url: connection,
    )
    with pytest.raises(ValueError, match="metadata diferente"):
        store.save_promotion_policy_metadata(_record())


def test_migration_is_idempotent_and_constrained():
    migration = (
        Path(__file__).resolve().parents[2]
        / "persistence/migrations/003_promotion_policy_metadata.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS promotion_policy_metadata" in migration
    assert migration.count("CREATE INDEX IF NOT EXISTS") == 2
    assert "manual_supervisor" in migration
    assert "supervisor_actor_id" in migration
    assert "organization_id" in migration
    assert "expires_at > evaluated_at" in migration
    assert "reversal_reference" in migration


def test_sqlite_round_trip_is_durable_idempotent_and_org_scoped(tmp_path):
    database = tmp_path / "operations.db"
    repository = SqliteOperationalRepository(database)
    assert isinstance(repository, PromotionPolicyRepository)
    record = _record()
    assert repository.save_promotion_policy_metadata(record) == record
    assert repository.save_promotion_policy_metadata(record) == record

    reopened = SqliteOperationalRepository(database)
    assert reopened.get_promotion_policy_metadata(
        record.evaluation_id, organization_id="org-1",
    ) == record
    assert reopened.get_promotion_policy_metadata(
        record.evaluation_id, organization_id="org-2",
    ) is None
    with reopened._connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM local_promotion_policy_metadata"
        ).fetchone()[0]
    assert count == 1


def test_sqlite_rejects_evaluation_id_collision(tmp_path):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    original = _record()
    repository.save_promotion_policy_metadata(original)
    changed = replace(original, evidence={**original.evidence, "extra": "evidence:extra"})
    with pytest.raises(ValueError, match="metadata diferente"):
        repository.save_promotion_policy_metadata(changed)


def test_sqlite_table_is_append_only_even_via_direct_sql(tmp_path):
    repository = SqliteOperationalRepository(tmp_path / "operations.db")
    record = _record()
    repository.save_promotion_policy_metadata(record)
    with repository._connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE local_promotion_policy_metadata SET conflict_count=1"
            )
    with repository._connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM local_promotion_policy_metadata")


def test_sqlite_migrates_legacy_administrator_role_to_admin(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE local_users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN ('analyst', 'supervisor', 'administrator')
                ),
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL
            );
            INSERT INTO local_users VALUES (
                'legacy-admin', 'Administrador', 'administrator', 1,
                '2026-08-01T00:00:00+00:00'
            );
            """
        )

    repository = SqliteOperationalRepository(database)
    user = repository.get_user("legacy-admin")
    assert user is not None and user.role == "admin"
    with repository._connect() as connection:
        versions = {
            row[0] for row in connection.execute(
                "SELECT version FROM local_schema_migrations"
            ).fetchall()
        }
        assert versions == {
            "001_identity_role_admin", "003_promotion_policy_metadata",
            "004_promotion_outcomes", "005_promotion_outcome_batches",
        }
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO local_users
                   (user_id, display_name, role, active, created_at)
                   VALUES ('old-role', 'Old', 'administrator', 1, ?)""",
                (NOW.isoformat(),),
            )
