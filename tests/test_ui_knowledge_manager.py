"""Tests UI mínimos del Knowledge Manager (P5).

Verifica:
  - La pestaña `_tab_knowledge_manager` y sus helpers existen en app_validacion.py.
  - La UI no ejecuta SQL ni abre SQLite (todo pasa por RuntimeManager).
  - Flujo end-to-end que replica exactamente las llamadas de la UI.
  - Benchmark protegido: gold_standard.db real byte-idéntica.
"""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from gold_standard.runtime_manager import RuntimeManager

GOLD_DB = Path(__file__).resolve().parent.parent / "gold_standard.db"

import app_validacion as app  # noqa: E402

KM_FUNCTIONS = [
    "_tab_knowledge_manager",
    "_km_pendientes",
    "_km_conflictos",
    "_km_runtime",
    "_km_historial",
    "_km_estadisticas",
]


def _make_source(path: Path, records: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE gold_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL DEFAULT '',
            account_code_original TEXT NOT NULL DEFAULT '',
            account_name TEXT NOT NULL DEFAULT '',
            account_nature TEXT NOT NULL DEFAULT '',
            suggested_code TEXT NOT NULL DEFAULT '',
            suggested_confidence REAL NOT NULL DEFAULT 0.0,
            final_code TEXT NOT NULL DEFAULT '',
            reviewer TEXT NOT NULL DEFAULT '',
            review_date TEXT NOT NULL DEFAULT '',
            comments TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE gold_standard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estandar TEXT NOT NULL,
            nombre_cuenta TEXT NOT NULL,
            normalized TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO gold_standard (codigo_estandar, nombre_cuenta, normalized) "
        "VALUES ('AC.01', 'Caja', 'caja')"
    )
    for i, r in enumerate(records, start=1):
        conn.execute(
            "INSERT INTO gold_records (source_file, account_name, suggested_confidence, "
            "final_code, reviewer, review_date) VALUES (?, ?, ?, ?, ?, ?)",
            (r.get("origen", f"f{i}.pdf"), r["account_name"], r.get("confidence", 0.9),
             r["final_code"], "analista", "2026-01-01"),
        )
    conn.commit()
    conn.close()


class TestTabPresence:
    def test_tab_function_exists(self):
        assert callable(app._tab_knowledge_manager)

    def test_helpers_exist(self):
        for name in KM_FUNCTIONS:
            assert callable(getattr(app, name)), f"falta {name}"

    def test_tab_registrada_en_st_tabs(self):
        src = inspect.getsource(app.main)
        assert "tab_km" in src
        assert "Knowledge Manager" in src

    @pytest.mark.parametrize("name", KM_FUNCTIONS)
    def test_ui_no_ejecuta_sql(self, name):
        """La UI debe delegar en RuntimeManager; no SQL ni conexiones SQLite."""
        src = inspect.getsource(getattr(app, name))
        for token in ("sqlite3", ".execute(", "SELECT ", "INSERT INTO", "CREATE TABLE"):
            assert token not in src, f"{name} contiene SQL/SQLite prohibido ({token})"


class TestEndToEnd:
    def test_flujo_ui_sobre_runtime_temporal(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])

        rm = RuntimeManager(runtime)
        # TAB 1: pendientes
        pend = rm.get_pending_promotions(src)
        assert len(pend) == 2
        assert all(p["state"] == "PENDING" for p in pend)

        # TAB 1: aprobar selección (solo Caja, source_record_id=1)
        res = rm.promote(src, dry_run=False, source_ids=[1], usuario="analista")
        assert res.promoted == 1

        # TAB 1: rechazar selección (Clientes)
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")

        # TAB 2: conflictos runtime vs gold
        conf = rm.get_conflicts(src)
        assert conf == []  # runtime Caja=AC.01 == gold AC.01

        # TAB 3: cuentas activas + rollback
        rows = rm.load_runtime()
        assert len(rows) == 1
        rm.rollback(rows[0]["id"], usuario="analista")
        assert len(rm.load_runtime()) == 0

        # TAB 4: historial
        hist = rm.get_history()
        actions = [h["accion"] for h in hist]
        assert actions == ["ROLLBACK", "REJECT", "PROMOTE"]  # más reciente primero

        # TAB 5: estadísticas
        s = rm.get_runtime_statistics(src)
        assert s["promotions"] == 1
        assert s["rejects"] == 1
        assert s["rollbacks"] == 1


@pytest.mark.skipif(not GOLD_DB.exists(), reason="gold_standard.db no disponible")
class TestBenchmarkProtected:
    def test_gold_db_intacta_tras_operaciones_km(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])

        before = GOLD_DB.read_bytes()
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)
        rm.get_conflicts(GOLD_DB)
        rm.get_runtime_statistics(GOLD_DB)
        rm.get_pending_promotions(GOLD_DB)
        assert GOLD_DB.read_bytes() == before

    def test_no_se_crea_runtime_en_import(self):
        rt = Path(__file__).resolve().parent.parent / "gold_standard_runtime.db"
        assert not rt.exists()


if __name__ == "__main__":
    pytest.main([__file__])
