"""Tests de la integración P4 — Runtime → LearningEngine.

Verifica (sobre DBs temporales):
  - Runtime exact tiene prioridad sobre gold.
  - Runtime fuzzy tiene prioridad sobre gold exact.
  - Fallback correcto al gold cuando el runtime no matchea.
  - Runtime inexistente → comportamiento idéntico al gold-only.
  - Runtime vacío → fallback al gold.
  - use_runtime=False ignora el runtime.
  - Benchmark protegido: gold_standard.db no se modifica.
  - Métricas de diagnóstico.

Restricciones P4:
  - Solo se modificó learning/engine.py (módulo + tests nuevos).
  - No toca parser/*, pipeline/*, semantic/*, CMCC/*, decision/*,
    app_validacion.py, benchmark, gold_standard.db.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gold_standard.runtime_manager import RuntimeManager
from learning.engine import LearningEngine
from learning.exact_match import normalize_name

GOLD_DB = Path(__file__).resolve().parent.parent / "gold_standard.db"


def _make_gold(path: Path, rows: list[dict]) -> None:
    """Replica el schema real de gold_standard.db (gold_standard + gold_records)."""
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE gold_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file     TEXT NOT NULL DEFAULT '',
            account_code_original TEXT NOT NULL DEFAULT '',
            account_name    TEXT NOT NULL DEFAULT '',
            account_nature  TEXT NOT NULL DEFAULT '',
            suggested_code  TEXT NOT NULL DEFAULT '',
            suggested_confidence REAL NOT NULL DEFAULT 0.0,
            final_code      TEXT NOT NULL DEFAULT '',
            reviewer        TEXT NOT NULL DEFAULT '',
            review_date     TEXT NOT NULL DEFAULT '',
            comments        TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE gold_standard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_estandar TEXT NOT NULL,
            nombre_cuenta TEXT NOT NULL,
            normalized TEXT NOT NULL
        );
        """
    )
    for r in rows:
        conn.execute(
            "INSERT INTO gold_standard (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES (?, ?, ?)",
            (r["code"], r["name"], normalize_name(r["name"])),
        )
    conn.commit()
    conn.close()


def _make_runtime(path: Path, rows: list[dict]) -> None:
    rm = RuntimeManager(path)
    rm.initialize()
    conn = rm.connection
    for r in rows:
        conn.execute(
            "INSERT INTO runtime_gold (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES (?, ?, ?)",
            (r["code"], r["name"], normalize_name(r["name"])),
        )
    conn.commit()
    rm.close()


def _engine(tmp_path: Path, gold: Path, runtime: Path) -> LearningEngine:
    return LearningEngine(
        db_path=gold,
        runtime_db_path=runtime,
        queue_path=tmp_path / "queue.json",
    )


class TestRuntimePriority:
    def test_runtime_exact_tiene_prioridad(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"}])
        _make_runtime(runtime, [{"code": "RT.01", "name": "Caja"}])

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Caja")

        assert res["source"] == "exact"
        assert res["code"] == "RT.01"
        m = eng.get_metrics()
        assert m["runtime_exact_hits"] == 1
        assert m["gold_exact_hits"] == 0

    def test_runtime_fuzzy_tiene_prioridad(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "ANC.03", "name": "Depreciación de Vehículos"}])
        _make_runtime(runtime, [{"code": "RT.99", "name": "Depreciación Vehículos"}])

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Depreciación de Vehículos")

        assert res["source"] == "fuzzy"
        assert res["code"] == "RT.99"
        m = eng.get_metrics()
        assert m["runtime_fuzzy_hits"] == 1
        assert m["gold_exact_hits"] == 0


class TestFallback:
    def test_fallback_correcto_al_gold(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "AC.03", "name": "Clientes"}])
        _make_runtime(runtime, [{"code": "AC.01", "name": "Caja"}])

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Clientes")

        assert res["source"] == "exact"
        assert res["code"] == "AC.03"
        m = eng.get_metrics()
        assert m["runtime_miss"] == 1
        assert m["gold_exact_hits"] == 1

    def test_runtime_inexistente(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "ANC.01", "name": "Muebles y Útiles"}])

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Muebles y Útiles")

        assert res["source"] == "exact"
        assert res["code"] == "ANC.01"
        assert not runtime.exists()  # no se crea por reads
        m = eng.get_metrics()
        assert m["runtime_miss"] == 0
        assert m["gold_exact_hits"] == 1

    def test_runtime_vacio(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "ER.07", "name": "Depreciación"}])
        RuntimeManager(runtime).initialize()

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Depreciación")

        assert res["source"] == "exact"
        assert res["code"] == "ER.07"
        m = eng.get_metrics()
        assert m["runtime_miss"] == 1
        assert m["gold_exact_hits"] == 1

    def test_use_runtime_false_ignora_runtime(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"}])
        _make_runtime(runtime, [{"code": "RT.01", "name": "Caja"}])

        eng = _engine(tmp_path, gold, runtime)
        res = eng.best_match("Caja", use_runtime=False)

        assert res["source"] == "exact"
        assert res["code"] == "AC.01"
        m = eng.get_metrics()
        assert m["runtime_exact_hits"] == 0
        assert m["runtime_fuzzy_hits"] == 0
        assert m["gold_exact_hits"] == 1


class TestMetrics:
    def test_contadores_diagnostico(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [
            {"code": "AC.01", "name": "Caja"},
            {"code": "ANC.03", "name": "Vehículos"},
            {"code": "AC.03", "name": "Clientes"},
        ])
        _make_runtime(runtime, [
            {"code": "RT.01", "name": "Caja"},
            {"code": "RT.02", "name": "Vehículos"},
        ])

        eng = _engine(tmp_path, gold, runtime)
        eng.best_match("Caja")                        # runtime exact
        eng.best_match("Vehículos")                   # runtime exact
        eng.best_match("Clientes")                    # runtime miss → gold exact
        eng.best_match("Sin match total")             # runtime miss → gold none

        m = eng.get_metrics()
        assert m["runtime_exact_hits"] == 2
        assert m["runtime_fuzzy_hits"] == 0
        assert m["runtime_miss"] == 2
        assert m["gold_exact_hits"] == 1
        assert m["gold_fuzzy_hits"] == 0

    def test_metrics_son_copia(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "runtime.db"
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"}])
        _make_runtime(runtime, [{"code": "RT.01", "name": "Caja"}])

        eng = _engine(tmp_path, gold, runtime)
        eng.best_match("Caja")
        snapshot = eng.get_metrics()
        snapshot["runtime_exact_hits"] = 999
        assert eng.get_metrics()["runtime_exact_hits"] == 1


@pytest.mark.skipif(not GOLD_DB.exists(), reason="gold_standard.db no disponible")
class TestBenchmarkProtection:
    def test_gold_db_byte_identica(self, tmp_path):
        runtime = tmp_path / "runtime.db"
        _make_runtime(runtime, [{"code": "RT.01", "name": "Caja"}])

        before = GOLD_DB.read_bytes()
        eng = LearningEngine(
            db_path=GOLD_DB,
            runtime_db_path=runtime,
            queue_path=tmp_path / "queue.json",
        )
        eng.best_match("Caja")
        eng.best_match("Vehículos")
        eng.best_match("Provisión Vacaciones")
        eng.close()
        after = GOLD_DB.read_bytes()

        assert after == before
        assert eng.get_metrics()["runtime_exact_hits"] >= 0


if __name__ == "__main__":
    pytest.main([__file__])
