import json
import sqlite3

from scripts.audit_local_promotion_backlog import audit_local_backlog, main


def fixture_dbs(tmp_path):
    source, runtime = tmp_path / "source.sqlite", tmp_path / "runtime.sqlite"
    with sqlite3.connect(source) as conn:
        conn.executescript("""
        CREATE TABLE gold_records (id INTEGER, account_name TEXT, final_code TEXT, reviewer TEXT);
        INSERT INTO gold_records VALUES (1,'Banco secreto','AC.01','actor-1');
        INSERT INTO gold_records VALUES (2,'Caja privada','AC.01','');
        INSERT INTO gold_records VALUES (3,'Cuenta incompleta','','');
        """)
    with sqlite3.connect(runtime) as conn:
        conn.executescript("""
        CREATE TABLE runtime_gold (normalized TEXT, codigo_estandar TEXT);
        CREATE TABLE promotion_history (id INTEGER, source_record_id INTEGER, state TEXT);
        INSERT INTO promotion_history VALUES (1,1,'APPROVED');
        INSERT INTO promotion_history VALUES (2,1,'ROLLED_BACK');
        """)
    return source, runtime


def test_aggregate_counts_latest_states_without_counting_history_as_queue(tmp_path):
    source, runtime = fixture_dbs(tmp_path)
    before = source.read_bytes(), runtime.read_bytes()
    result = audit_local_backlog(source, runtime)
    assert result["verification"] == "verified_partial"
    assert result["aggregate"]["source_records"] == 3
    assert result["aggregate"]["eligible_candidates"] == 2
    assert result["aggregate"]["excluded_records"] == 1
    assert result["aggregate"]["candidate_state_counts"] == {"PENDING": 1, "ROLLED_BACK": 1}
    assert result["organization_isolation_verified"] is False
    assert (source.read_bytes(), runtime.read_bytes()) == before
    payload = json.dumps(result)
    assert "secreto" not in payload and "actor-1" not in payload


def test_missing_database_not_created(tmp_path):
    result = audit_local_backlog(tmp_path / "missing", tmp_path / "other")
    assert result["verification"] == "not_verified"
    assert list(tmp_path.iterdir()) == []


def test_broken_schema_is_not_empty_pending_queue(tmp_path):
    source, runtime = fixture_dbs(tmp_path)
    with sqlite3.connect(runtime) as conn:
        conn.execute("DROP TABLE promotion_history")
    result = audit_local_backlog(source, runtime)
    assert result["verification"] == "not_verified"
    assert result["aggregate"] is None


def test_blank_event_state_is_unknown_not_pending(tmp_path):
    source, runtime = fixture_dbs(tmp_path)
    with sqlite3.connect(runtime) as conn:
        conn.execute("INSERT INTO promotion_history VALUES (3,1,'')")
    result = audit_local_backlog(source, runtime)
    assert result["aggregate"]["candidate_state_counts"]["UNKNOWN"] == 1
    assert "unknown_candidate_state" in result["reason_codes"]


def test_gate_requires_more_than_local_counts(tmp_path, capsys):
    source, runtime = fixture_dbs(tmp_path)
    assert main(["--source-db", str(source), "--runtime-db", str(runtime),
                 "--require-verified"]) == 2
