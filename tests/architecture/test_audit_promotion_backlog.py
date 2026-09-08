from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_promotion_backlog.py"
SPEC = importlib.util.spec_from_file_location("audit_promotion_backlog", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, *, audit_view: bool = True) -> None:
        self.audit_view = audit_view
        self.queries: list[str] = []
        self.params: list[tuple | None] = []
        self._one = None
        self._all = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        compact = " ".join(str(query).split())
        self.queries.append(compact)
        self.params.append(params)
        if compact.startswith("SET TRANSACTION"):
            self._one, self._all = None, []
        elif "to_regclass" in compact:
            relation = params[0]
            exists = relation == audit.VALIDATION_TABLE or (
                relation == audit.AUDIT_VIEW and self.audit_view
            )
            self._one, self._all = ((relation if exists else None,), [])
        elif "FROM public.log_validaciones" in compact:
            self._one = (
                12, 2, 1,
                datetime(2026, 8, 1, tzinfo=timezone.utc),
                datetime(2026, 8, 29, tzinfo=timezone.utc),
            )
            self._all = []
        elif "GROUP BY status" in compact:
            self._one = None
            self._all = [
                ("REJECTED", 1, datetime(2026, 8, 20, tzinfo=timezone.utc)),
                ("PENDING", 4, datetime(2026, 8, 10, tzinfo=timezone.utc)),
            ]
        elif "FROM public.promotion_backlog_audit_v1" in compact:
            self._one = (
                5, 2, 1,
                datetime(2026, 8, 10, tzinfo=timezone.utc),
                datetime(2026, 8, 29, tzinfo=timezone.utc),
            )
            self._all = []
        else:  # pragma: no cover - hace visible SQL nuevo no modelado
            raise AssertionError(f"Consulta inesperada: {compact}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)


class FakeConnection:
    def __init__(self, *, audit_view: bool = True, set_session: bool = True) -> None:
        self.cursor_instance = FakeCursor(audit_view=audit_view)
        self.readonly = None
        self.autocommit = None
        self.rolled_back = False
        self.closed = False
        if not set_session:
            self.set_session = None

    def cursor(self):
        return self.cursor_instance

    def set_session(self, *, readonly, autocommit):
        self.readonly = readonly
        self.autocommit = autocommit

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_without_database_url_is_explicitly_not_verified(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    report = audit.audit_promotion_backlog(now=NOW)
    assert report["verification"] == {
        "status": "not_verified",
        "reason_code": "database_url_unavailable",
    }
    assert report["promotion_backlog"] is None
    assert report["validation_activity"] is None
    assert report["safety"]["mutations_performed"] is False


def test_complete_view_returns_only_aggregates_and_policy_contrast():
    conn = FakeConnection()
    report = audit.audit_promotion_backlog(
        database_url="postgresql://placeholder",
        connect=lambda _url: conn,
        now=NOW,
    )
    assert report["verification"]["status"] == "verified"
    assert report["promotion_backlog"] == {
        "total": 5,
        "distinct_reviewer_count": 2,
        "missing_reviewer_count": 1,
        "oldest_record_at": "2026-08-10T00:00:00+00:00",
        "newest_record_at": "2026-08-29T00:00:00+00:00",
        "by_status": [
            {
                "status": "PENDING",
                "count": 4,
                "oldest_record_at": "2026-08-10T00:00:00+00:00",
            },
            {
                "status": "REJECTED",
                "count": 1,
                "oldest_record_at": "2026-08-20T00:00:00+00:00",
            },
        ],
    }
    assert report["policy_contrast"]["status"] == "requires_attention"
    assert report["policy"]["manual_approval_required"] is True
    assert report["policy"]["supervisor_identity_required"] is True
    assert conn.readonly is True
    assert conn.rolled_back and conn.closed


def test_validations_are_not_misrepresented_as_backlog():
    conn = FakeConnection(audit_view=False)
    report = audit.audit_promotion_backlog(
        database_url="postgresql://placeholder",
        connect=lambda _url: conn,
        now=NOW,
    )
    assert report["verification"] == {
        "status": "verified_partial",
        "reason_code": "promotion_audit_view_unavailable",
    }
    assert report["promotion_backlog"] is None
    assert report["validation_activity"]["records"] == 12
    assert report["validation_activity"]["is_promotion_backlog"] is False


def test_report_never_contains_sensitive_columns_or_connection_url():
    conn = FakeConnection()
    secret_url = "postgresql://secret-user:secret-password@private/db"
    report = audit.audit_promotion_backlog(
        database_url=secret_url,
        connect=lambda _url: conn,
        now=NOW,
    )
    payload = json.dumps(report, sort_keys=True).lower()
    for forbidden in (
        "secret-user", "secret-password", "cuenta_original", "account_name",
        "rut", "monto", "amount", "archivo_origen", '"reviewer_id":',
    ):
        assert forbidden not in payload
    sql = " ".join(conn.cursor_instance.queries).upper()
    for mutation in (" INSERT ", " UPDATE ", " DELETE ", " DROP ", " ALTER "):
        assert mutation not in f" {sql} "


def test_connection_failure_omits_exception_message_and_secret():
    def fail(_url):
        raise RuntimeError("failed postgresql://user:password@private/db")

    report = audit.audit_promotion_backlog(
        database_url="postgresql://user:password@private/db",
        connect=fail,
        now=NOW,
    )
    payload = json.dumps(report, sort_keys=True)
    assert report["verification"]["status"] == "not_verified"
    assert report["verification"]["reason_code"] == "read_only_query_failed"
    assert "password" not in payload
    assert "private" not in payload


def test_cli_require_verified_fails_closed(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert audit.main(["--require-verified"]) == 2
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["verification"]["status"] == "not_verified"
