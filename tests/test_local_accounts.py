import os
from pathlib import Path
import sqlite3

import pytest

from access_control import Role
from local_accounts import (
    AccountStatus,
    LocalAccountAccessError,
    LocalAccountError,
    LocalAccountStore,
)


def _store(tmp_path) -> LocalAccountStore:
    return LocalAccountStore(tmp_path / "private" / "accounts.sqlite3")


def _admin(store: LocalAccountStore):
    return store.bootstrap_administrator("owner", "Owner", "correct horse battery staple")


def test_bootstrap_creates_private_admin_and_hashes_password(tmp_path):
    store = _store(tmp_path)

    admin = _admin(store)

    assert admin.role is Role.ADMINISTRATOR
    assert admin.status == AccountStatus.ACTIVE
    assert store.authenticate("owner", "correct horse battery staple") == admin
    assert store.authenticate("owner", "wrong password") is None
    assert os.stat(store.path).st_mode & 0o077 == 0

    with sqlite3.connect(store.path) as conn:
        row = conn.execute(
            "SELECT password_salt, password_digest FROM accounts WHERE username = 'owner'",
        ).fetchone()
    assert row[0] != b"correct horse battery staple"
    assert row[1] != b"correct horse battery staple"


def test_request_is_pending_until_admin_assigns_role_and_team(tmp_path):
    store = _store(tmp_path)
    admin = _admin(store).actor()
    team = store.create_team(admin, "Operaciones")

    requested = store.request_access(
        "ana", "Ana Analista", "password for ana 123", "Operaciones",
    )

    assert requested.status == AccountStatus.PENDING
    assert store.authenticate("ana", "password for ana 123") is None
    assert [account.username for account in store.list_pending_requests(admin)] == ["ana"]

    approved = store.approve_request(admin, "ana", Role.ANALYST, team.team_id)

    assert approved.status == AccountStatus.ACTIVE
    assert approved.role is Role.ANALYST
    assert approved.team_id == team.team_id
    assert store.authenticate("ana", "password for ana 123").actor().role is Role.ANALYST


def test_only_administrator_can_manage_requests_and_no_extra_admin_can_be_approved(tmp_path):
    store = _store(tmp_path)
    admin = _admin(store).actor()
    team = store.create_team(admin, "Operaciones")
    store.request_access("maria", "María", "password for maria 123")
    store.request_access("juan", "Juan", "password for juan 123")
    analyst = store.approve_request(admin, "maria", Role.ANALYST, team.team_id).actor()

    with pytest.raises(LocalAccountAccessError):
        store.list_pending_requests(analyst)
    with pytest.raises(LocalAccountError, match="roles de equipo"):
        store.approve_request(admin, "juan", Role.ADMINISTRATOR, team.team_id)


def test_admin_can_reassign_and_disable_team_member_with_audit(tmp_path):
    store = _store(tmp_path)
    admin = _admin(store).actor()
    first_team = store.create_team(admin, "Operaciones")
    second_team = store.create_team(admin, "Control")
    store.request_access("dani", "Daniela", "password for daniela 123")
    store.approve_request(admin, "dani", Role.DATA_ENTRY, first_team.team_id)

    reassigned = store.update_active_account(
        admin, "dani", Role.MANAGEMENT, second_team.team_id,
    )
    disabled = store.disable_account(admin, "dani")
    audit_events = [event["event_type"] for event in store.list_audit(admin)]

    assert reassigned.role is Role.MANAGEMENT
    assert reassigned.team_id == second_team.team_id
    assert disabled.status == AccountStatus.DISABLED
    assert store.authenticate("dani", "password for daniela 123") is None
    assert "ACCOUNT_REASSIGNED" in audit_events
    assert "ACCOUNT_DISABLED" in audit_events


def test_local_account_validation_and_single_administrator_rules(tmp_path):
    store = _store(tmp_path)
    _admin(store)

    with pytest.raises(LocalAccountError, match="Ya existe"):
        store.bootstrap_administrator("other", "Other", "another secure password")
    with pytest.raises(LocalAccountError, match="12"):
        store.request_access("short", "Short", "small")
    with pytest.raises(LocalAccountError, match="usuario"):
        store.request_access("No spaces", "Name", "long enough password")


def test_account_database_is_rejected_inside_repository():
    repository_root = Path(__file__).resolve().parents[1]

    with pytest.raises(LocalAccountError, match="fuera del repositorio"):
        LocalAccountStore(repository_root / "local-accounts-test.sqlite3")
