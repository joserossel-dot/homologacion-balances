#!/usr/bin/env python3
"""Aggregate local promotion evidence without creating or modifying databases."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from gold_standard.runtime_manager import RuntimeManager


def _open(path: Path, stack: ExitStack):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    stack.callback(conn.close)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    return conn


def audit_local_backlog(source_db: str | Path, runtime_db: str | Path) -> dict:
    report = {
        "schema_version": 1,
        "verification": "not_verified",
        "reason_codes": [],
        "aggregate": None,
        "organization_isolation_verified": False,
        "supervisor_policy_verified": False,
        "safety": {"read_only": True, "account_data_returned": False,
                   "external_transmission": False},
    }
    source, runtime = Path(source_db), Path(runtime_db)
    if not source.is_file() or not runtime.is_file():
        report["reason_codes"] = ["source_or_runtime_missing"]
        return report
    if source.resolve() == runtime.resolve():
        report["reason_codes"] = ["source_runtime_must_be_distinct"]
        return report
    try:
        with ExitStack() as stack:
            src = _open(source, stack)
            run = _open(runtime, stack)
            # Preflight avoids runtime helpers converting missing schema to empty state.
            run.execute("SELECT normalized, codigo_estandar FROM runtime_gold LIMIT 0")
            events = run.execute(
                "SELECT id, source_record_id, state FROM promotion_history ORDER BY id"
            ).fetchall()
            rows = src.execute(
                "SELECT id, account_name, final_code, reviewer FROM gold_records ORDER BY id"
            ).fetchall()
            manager = RuntimeManager(runtime)
            manager._conn = run  # existing classification semantics, read-only connection
            classification, states = Counter(), Counter()
            source_ids = {row["id"] for row in rows}
            latest = {row["source_record_id"]: row["state"] for row in events}
            unknown = missing_reviewer = candidates = 0
            for row in rows:
                kind = manager._classify(row)["status"]
                classification[kind] += 1
                if kind in {"skip_reviewer", "empty_code", "reserved"}:
                    continue
                candidates += 1
                missing_reviewer += not str(row["reviewer"] or "").strip()
                # Blank historical states are ambiguous, not assumed approvals/pending.
                state = latest.get(row["id"], "PENDING")
                if state not in {"PENDING", "APPROVED", "REJECTED", "ROLLED_BACK"}:
                    state = "UNKNOWN"
                    unknown += 1
                states[state] += 1
            report["aggregate"] = {
                "source_records": len(rows), "eligible_candidates": candidates,
                "excluded_records": len(rows) - candidates,
                "classification_counts": dict(sorted(classification.items())),
                "candidate_state_counts": dict(sorted(states.items())),
                "candidate_missing_reviewer_count": missing_reviewer,
                "history_events": len(events),
                "history_events_without_source_record": sum(
                    event["source_record_id"] not in source_ids for event in events),
            }
            report["verification"] = "verified_partial"
            report["reason_codes"] = [
                "organization_binding_unavailable",
                "supervisor_approval_evidence_not_audited",
                "cross_database_snapshot_not_certified",
            ]
            if unknown:
                report["reason_codes"].append("unknown_candidate_state")
    except (sqlite3.Error, OSError, ValueError) as exc:
        report["verification"] = "not_verified"
        report["aggregate"] = None
        report["reason_codes"] = ["source_read_failed"]
        report["error_type"] = type(exc).__name__
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--runtime-db", required=True)
    parser.add_argument("--require-verified", action="store_true")
    args = parser.parse_args(argv)
    report = audit_local_backlog(args.source_db, args.runtime_db)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if args.require_verified and report["verification"] != "verified" else 0


if __name__ == "__main__":
    raise SystemExit(main())
