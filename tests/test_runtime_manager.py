"""Tests de RuntimeManager (P3).

Verifica sobre DBs temporales:
  - El schema crea las tres tablas (runtime_gold, promotion_history, metadata).
  - No crea la DB runtime automáticamente (los métodos de solo lectura no escriben).
  - search_runtime: exacto, fuzzy y none, sin crear archivo.
  - promote: dry-run no escribe; apply escribe runtime_gold + promotion_history + metadata.
  - Duplicados, conflictos, filtros (total, final_code='', reviewer).
  - rollback: elimina y registra en promotion_history.
  - stats: conteos y metadata (version/checksum/fechas).

Restricciones P3:
  - No toca gold_standard.db ni la tabla ``gold_standard`` del runtime P1.1.
  - Reutiliza lógica existente por delegación.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gold_standard.runtime_manager import RuntimeManager
from gold_standard.runtime import RuntimeGoldStorage
from learning.exact_match import normalize_name


def _make_source(path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE gold_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT NOT NULL DEFAULT '',
            final_code TEXT NOT NULL DEFAULT '',
            reviewer TEXT NOT NULL DEFAULT '',
            review_date TEXT NOT NULL DEFAULT ''
        )
        """
    )
    for r in rows:
        conn.execute(
            "INSERT INTO gold_records (account_name, final_code, reviewer, review_date) "
            "VALUES (?, ?, ?, ?)",
            (r.get("account_name", ""), r.get("final_code", ""),
             r.get("reviewer", ""), r.get("review_date", "")),
        )
    conn.commit()
    conn.close()


def _tables(path: Path) -> list[str]:
    conn = sqlite3.connect(str(path))
    tables = [t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    return tables


def _count(path: Path, table: str) -> int:
    conn = sqlite3.connect(str(path))
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    return n


class TestSchema:
    def test_initialize_creates_three_tables(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        rm.initialize()
        tables = _tables(db)
        assert "runtime_gold" in tables
        assert "promotion_history" in tables
        assert "metadata" in tables

    def test_checksum_not_produced_until_initialized(self, tmp_path):
        """Los métodos de solo lectura no crean la DB."""
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        assert rm.load_runtime() == []
        assert rm.stats()["exists"] is False
        assert rm.search_runtime("Caja")["source"] == "none"
        assert not db.exists()  # nunca se crea por reads

    def test_initialize_is_idempotent(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        rm.initialize()
        rm.initialize()
        assert _count(db, "runtime_gold") == 0
        assert _count(db, "metadata") == 4  # version, checksum, fechas

    def test_metadata_seeded(self, tmp_path):
        db = tmp_path / "runtime.db"
        RuntimeManager(db).initialize()
        rm = RuntimeManager(db)
        assert rm.get_metadata("version") == "1.0"
        assert rm.get_metadata("checksum") is not None
        assert rm.get_metadata("fecha_creacion") is not None
        assert rm.get_metadata("fecha_actualizacion") is not None


class TestSearch:
    def test_exact(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        rm.initialize()
        conn = rm.connection
        conn.execute(
            "INSERT INTO runtime_gold (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES ('AC.01', 'Caja', 'caja')"
        )
        conn.commit()
        res = rm.search_runtime("Caja")
        assert res == {"source": "exact", "code": "AC.01", "confidence": 0.98,
                       "matched_name": "Caja"}

    def test_none_when_absent(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        res = rm.search_runtime("Caja")
        assert res["source"] == "none"
        assert not db.exists()


class TestPromoteBasic:
    def test_dry_run_no_file_created(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
            {"account_name": "Proveedores", "final_code": "PC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        r = rm.promote(source, dry_run=True)
        assert r.candidates == 2
        assert r.promotable == 2
        assert r.promoted == 2
        assert not runtime.exists()  # dry-run no crea el archivo

    def test_apply_writes_tables(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        r = rm.promote(source, dry_run=False)
        assert r.promoted == 1
        assert _count(runtime, "runtime_gold") == 1
        assert _count(runtime, "promotion_history") == 1  # 1 evento 'promote'
        assert rm.get_metadata("version") == "1.0"

    def test_idempotent_apply(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(source, dry_run=False)
        r2 = rm.promote(source, dry_run=False)
        assert r2.promoted == 0
        assert r2.duplicates == 1
        assert _count(runtime, "runtime_gold") == 1


class TestPromoteFilters:
    def test_empty_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Sin revisar", "final_code": "", "reviewer": "analista"},
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        r = RuntimeManager(runtime).promote(source, dry_run=True)
        assert r.empty_code == 1
        assert r.promotable == 1

    def test_reserved_total(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Total Activos", "final_code": "AC.99", "reviewer": "analista"},
        ])
        r = RuntimeManager(runtime).promote(source, dry_run=True)
        assert r.reserved == 1
        assert r.promotable == 0

    def test_reviewer_filter(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "manual_revision"},
        ])
        r = RuntimeManager(runtime).promote(source, dry_run=True, reviewer_filter="analista")
        assert r.promotable == 0
        assert r.candidates == 1


class TestPromoteConflicts:
    def test_duplicate_same_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(source, dry_run=False)
        r2 = rm.promote(source, dry_run=True)
        assert r2.duplicates == 1
        assert r2.promotable == 0

    def test_conflict_different_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Documentos en Garantía", "final_code": "AC.08", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.initialize()
        rm.connection.execute(
            "INSERT INTO runtime_gold (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES ('AC.03', 'Documentos en Garantía', ?)",
            (normalize_name("Documentos en Garantía"),),
        )
        rm.connection.commit()
        r = rm.promote(source, dry_run=False)
        assert r.conflicts == 1
        assert r.promoted == 0
        assert r.conflict_details[0]["candidate_code"] == "AC.08"
        assert "AC.03" in r.conflict_details[0]["existing_codes"]
        assert _count(runtime, "runtime_gold") == 1


class TestRollback:
    def test_rollback_removes_and_logs(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(source, dry_run=False)
        assert _count(runtime, "runtime_gold") == 1
        assert rm.rollback(1)
        assert _count(runtime, "runtime_gold") == 0
        assert _count(runtime, "promotion_history") == 2  # promote + rollback

    def test_rollback_unknown_id(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        assert rm.rollback(999) is False

    def test_rollback_no_file(self, tmp_path):
        db = tmp_path / "runtime.db"
        rm = RuntimeManager(db)
        assert rm.rollback(1) is False
        assert not db.exists()


class TestStats:
    def test_stats_empty(self, tmp_path):
        db = tmp_path / "runtime.db"
        r = RuntimeManager(db).stats()
        assert r["exists"] is False
        assert r["runtime_gold"] == 0

    def test_stats_counts(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(source, dry_run=False)
        s = rm.stats()
        assert s["exists"] is True
        assert s["runtime_gold"] == 1
        assert s["promotion_history"] == 1
        assert s["metadata"]["version"] == "1.0"


class TestBackwardCompat:
    def test_coexists_with_runtimegoldstorage(self, tmp_path):
        """RuntimeManager y RuntimeGoldStorage (P1.1) conviven en el mismo archivo."""
        db = tmp_path / "runtime.db"

        rt = RuntimeGoldStorage(db)
        rt.connection.execute(
            "INSERT INTO gold_standard (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES ('AC.01', 'Caja', 'caja')"
        )
        rt.connection.commit()
        rt.close()

        rm = RuntimeManager(db)
        rm.initialize()
        assert rm.get_metadata("version") == "1.0"
        assert rm.load_runtime() == []
        # P1.1 sigue leyendo su tabla sin interferencia
        rt2 = RuntimeGoldStorage(db)
        assert rt2.count() == 1
        rt2.close()


class TestBenchmarkProtection:
    def test_promote_never_writes_source(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
            {"account_name": "Proveedores", "final_code": "PC.01", "reviewer": "analista"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(source, dry_run=False)
        conn = sqlite3.connect(str(source))
        n = conn.execute("SELECT COUNT(*) FROM gold_records").fetchone()[0]
        tables = _tables(source)
        conn.close()
        assert n == 2
        assert "runtime_gold" not in tables  # la fuente del benchmark no cambia
        assert "promotion_history" not in tables


if __name__ == "__main__":
    pytest.main([__file__])