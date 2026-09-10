"""Real migration smoke. Opt in with RUN_POSTGRES_MIGRATIONS=1 and Docker.

Uses a disposable container, no host ports, volumes or production credentials.
This checks common constraints, not complete repository/API parity.
"""
import os
from pathlib import Path
import sqlite3
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("dialect", ["sqlite", "postgres"])
def test_policy_migrations_repeat_and_reject_invalid_roles(dialect):
    container = None
    connection = None
    if dialect == "postgres":
        if os.environ.get("RUN_POSTGRES_MIGRATIONS") != "1":
            pytest.skip("explicit Docker integration opt-in required")
        container = subprocess.check_output([
            "docker", "run", "--rm", "-d", "--network", "none",
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:16-alpine",
        ], text=True).strip()
    else:
        connection = sqlite3.connect(":memory:")
        connection.execute("PRAGMA foreign_keys=ON")
    try:
        if container:
            for _ in range(60):
                ready = subprocess.run([
                    "docker", "exec", container, "pg_isready", "-U", "postgres",
                ], capture_output=True)
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                pytest.fail("temporary PostgreSQL did not become ready")

        def execute(sql):
            if connection:
                try:
                    connection.executescript(sql)
                    return True
                except sqlite3.IntegrityError:
                    connection.rollback()
                    return False
            result = subprocess.run([
                "docker", "exec", "-i", container, "psql", "-U", "postgres",
                "-v", "ON_ERROR_STOP=1",
            ], input=sql, text=True, capture_output=True)
            return result.returncode == 0

        folder = ROOT / "persistence" / ("local/migrations" if connection else "migrations")
        for _ in range(2):
            for name in ("003_promotion_policy_metadata.sql", "004_promotion_outcomes.sql"):
                assert execute((folder / name).read_text())
            if container:
                for name in ("005_promotion_outcome_batches.sql", "006_policy_append_only.sql", "007_outcomes_append_only.sql"):
                    assert execute((folder / name).read_text())
        table = "local_promotion_policy_metadata" if connection else "promotion_policy_metadata"
        reasons = "decision_reasons_json" if connection else "decision_reasons"
        evidence = "evidence_json" if connection else "evidence"
        allowed = "1" if connection else "TRUE"
        template = f"""INSERT INTO {table}
            (evaluation_id,subject_id,policy_mode,decision_allowed,{reasons},{evidence},
             supervisor_actor_id,supervisor_role,organization_id,conflict_count,
             evaluated_at,expires_at,reversal_reference,record_fingerprint,created_at)
            VALUES ('00000000-0000-0000-0000-000000000001','synthetic',
            'manual_supervisor',{allowed},'[]','{{}}','test-actor','ROLE','test-org',0,
            '2026-01-01','2026-01-02','test','{'a' * 64}','2026-01-01');"""
        assert not execute(template.replace("ROLE", "unknown"))
        assert execute(template.replace("ROLE", "supervisor"))
        assert not execute(template.replace("ROLE", "supervisor")), "duplicate primary key accepted"
        outcome_table = "local_promotion_outcomes" if connection else "promotion_outcomes"
        assert execute(f"""INSERT INTO {outcome_table}
            (record_fingerprint,evaluation_id,subject_id,organization_id,actor_id,status,occurred_at,created_at)
            VALUES ('{'b' * 64}','00000000-0000-0000-0000-000000000001',
            'synthetic','test-org','test-actor','FAILED','2026-01-01','2026-01-01');""")
        for protected in (table, outcome_table):
            assert not execute(f"UPDATE {protected} SET subject_id='changed';")
            assert not execute(f"DELETE FROM {protected};")
            if container:
                assert not execute(f"TRUNCATE {protected} CASCADE;")
        # Reapplying protection with existing records must remain possible.
        if container:
            for name in ("005_promotion_outcome_batches.sql", "006_policy_append_only.sql", "007_outcomes_append_only.sql"):
                assert execute((folder / name).read_text())
    finally:
        if connection:
            connection.close()
        if container:
            subprocess.run(["docker", "stop", container], check=True, capture_output=True)
