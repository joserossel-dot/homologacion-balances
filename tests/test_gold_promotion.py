"""Tests del módulo de promoción del Learning Loop (P1.1).

Verifica que la promoción gold_records -> gold_standard_runtime:
  - No escribe nunca sobre la DB del benchmark (gold_standard.db).
  - Filtra candidatos sin final_code.
  - Respeta palabras reservadas (total).
  - Omite duplicados (idempotencia).
  - Detecta conflictos (mismo normalized, código distinto) sin promover.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gold_standard.promotion import promote
from gold_standard.runtime import RuntimeGoldStorage
from learning.exact_match import normalize_name


def _make_source_db(path: Path, rows: list[dict]) -> None:
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


def _seed_runtime(path: Path, rows: list[tuple[str, str]]) -> None:
    """Inserta filas (codigo_estandar, normalized) en el runtime ya existente."""
    rt = RuntimeGoldStorage(path)
    for code, norm in rows:
        rt.connection.execute(
            "INSERT INTO gold_standard (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES (?, ?, ?)",
            (code, norm, normalize_name(norm)),
        )
    rt.connection.commit()
    rt.close()


def _count(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    n = conn.execute("SELECT COUNT(*) FROM gold_standard").fetchone()[0]
    conn.close()
    return n


class TestPromoteBasics:
    def test_promotes_new_records(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
            {"account_name": "Proveedores", "final_code": "PC.01", "reviewer": "analista"},
        ])
        r = promote(source, runtime, dry_run=True)
        assert r.candidates == 2
        assert r.promotable == 2
        assert r.promoted == 2  # dry-run reports promotable as promoted
        assert r.conflicts == 0
        assert r.duplicates == 0
        assert not runtime.exists()  # dry-run no crea ni escribe el runtime

    def test_apply_writes_runtime(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        r = promote(source, runtime, dry_run=False)
        assert r.promoted == 1
        assert _count(runtime) == 1

    def test_idempotent_apply(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        promote(source, runtime, dry_run=False)
        r2 = promote(source, runtime, dry_run=False)
        assert r2.promoted == 0
        assert r2.duplicates == 1
        assert _count(runtime) == 1  # sin duplicar


class TestPromoteFilters:
    def test_filters_empty_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Sin revisar", "final_code": "", "reviewer": "analista"},
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        r = promote(source, runtime, dry_run=True)
        assert r.empty_code == 1
        assert r.promotable == 1

    def test_respects_reserved_total_token(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Total Activos", "final_code": "AC.99", "reviewer": "analista"},
        ])
        r = promote(source, runtime, dry_run=True)
        assert r.reserved == 1
        assert r.promotable == 0

    def test_reviewer_filter(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "manual_revision"},
        ])
        r = promote(source, runtime, dry_run=True, reviewer_filter="analista")
        assert r.promotable == 0
        assert r.candidates == 1  # fue clasificado, pero saltado por reviewer


class TestPromoteDuplicatesAndConflicts:
    def test_duplicate_same_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        _seed_runtime(runtime, [("AC.01", "caja")])
        r = promote(source, runtime, dry_run=True)
        assert r.duplicates == 1
        assert r.promotable == 0

    def test_conflict_different_code(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Documentos en Garantía", "final_code": "AC.08", "reviewer": "analista"},
        ])
        _seed_runtime(runtime, [("AC.03", "documentos en garantía")])
        r = promote(source, runtime, dry_run=True)
        assert r.conflicts == 1
        assert r.promotable == 0
        assert r.conflict_details[0]["candidate_code"] == "AC.08"
        assert "AC.03" in r.conflict_details[0]["existing_codes"]

    def test_conflict_not_promoted_on_apply(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Documentos en Garantía", "final_code": "AC.08", "reviewer": "analista"},
        ])
        _seed_runtime(runtime, [("AC.03", "documentos en garantía")])
        r = promote(source, runtime, dry_run=False)
        assert r.conflicts == 1
        assert r.promoted == 0
        assert _count(runtime) == 1  # solo la fila original


class TestBenchmarkProtection:
    def test_source_db_never_modified(self, tmp_path):
        source = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source_db(source, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
            {"account_name": "Proveedores", "final_code": "PC.01", "reviewer": "analista"},
        ])
        promote(source, runtime, dry_run=False)

        conn = sqlite3.connect(str(source))
        n = conn.execute("SELECT COUNT(*) FROM gold_records").fetchone()[0]
        tables = [t[0] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert n == 2  # sin borrar ni modificar filas
        assert "gold_standard" not in tables  # no crea tabla en la fuente

    def test_defaults_never_write_benchmark(self, tmp_path, monkeypatch):
        """promote() con dry_run=True no crea ni escribe la DB del benchmark."""
        bench = tmp_path / "gold_standard.db"
        monkeypatch.setattr("gold_standard.promotion.BENCHMARK_DB", str(bench))
        _make_source_db(bench, [
            {"account_name": "Caja", "final_code": "AC.01", "reviewer": "analista"},
        ])
        runtime = tmp_path / "runtime.db"
        r = promote(bench, runtime, dry_run=True)
        assert r.promotable == 1
        # la DB del benchmark conserva solo gold_records (schema de prueba), sin gold_standard
        conn = sqlite3.connect(str(bench))
        tables = [t[0] for t in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "gold_standard" not in tables


if __name__ == "__main__":
    pytest.main([__file__])
