"""Audit evidence must not turn historical events into queue certification."""
from datetime import datetime, timezone

from scripts.audit_promotion_backlog import (
    OUTCOME_TABLE, _contrast_policy, _read_outcome_activity,
)


class Cursor:
    def __init__(self, exists=True):
        self.exists = exists
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return (OUTCOME_TABLE if self.exists else None,)

    def fetchall(self):
        moment = datetime(2026, 9, 7, tzinfo=timezone.utc)
        return [("APPLIED", 2, moment, moment), ("FAILED", 1, moment, moment)]


def test_reviewers_do_not_prove_supervisor_approval_or_evidence():
    result = _contrast_policy({"missing_reviewer_count": 0, "total": 3})
    assert result["status"] == "not_evaluable"
    assert result["reason_code"] == "approval_evidence_unavailable"


def test_missing_outcome_table_is_unknown_not_zero():
    cursor = Cursor(False)
    assert _read_outcome_activity(cursor) is None
    assert len(cursor.queries) == 1


def test_outcomes_remain_events_and_no_sensitive_rows_are_queried():
    cursor = Cursor()
    result = _read_outcome_activity(cursor)
    assert result["is_promotion_backlog"] is False
    assert result["counts_are_events_not_current_candidates"] is True
    assert result["by_status"][0]["count"] == 2
    query = cursor.queries[1][0]
    assert "GROUP BY status" in query
    for forbidden in ("actor_id", "subject_id", "error", "organization_id", "INSERT", "UPDATE"):
        assert forbidden not in query
