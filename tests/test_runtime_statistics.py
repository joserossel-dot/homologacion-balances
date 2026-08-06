"""Tests de RuntimeStatistics (P5.5 — Runtime Observability).

Verifica sobre DBs temporales y un LearningEngine en memoria:
  - capture() combina métricas de uso (engine) + eventos/cobertura (RuntimeManager).
  - Métricas mínimas: runtime_exact/fuzzy, gold_exact/fuzzy, runtime_miss,
    fallback_to_gold, rollback_count, reject_count, promotion_count.
  - Derivados de cobertura (runtime/gold/uso/aprendizaje) y % de fallback.
  - Impacto por promoción: marcado como impactante si su código fue usado.
  - La UI no lee SQL: RuntimeStatistics es la única fuente.
  - Benchmark protegido: gold_standard.db real byte-idéntica.

Reglas P5.5:
  - Solo observabilidad: no promueve, no revierte, no puebla.
  - gold_standard.db nunca se escribe.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gold_standard.runtime_manager import RuntimeManager
from gold_standard.runtime_stats import RuntimeStatistics
from learning.engine import LearningEngine

GOLD_DB = Path(__file__).resolve().parent.parent / "gold_standard.db"

GOLD_RECORDS_SQL = """
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
"""


def _make_source(path: Path, records: list[dict]) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(GOLD_RECORDS_SQL)
    for i, r in enumerate(records, start=1):
        conn.execute(
            "INSERT INTO gold_records (source_file, account_name, suggested_confidence, "
            "final_code, reviewer, review_date) VALUES (?, ?, ?, ?, ?, ?)",
            (r.get("origen", f"f{i}.pdf"), r["account_name"], r.get("confidence", 0.9),
             r["final_code"], "analista", "2026-01-01"),
        )
    conn.commit()
    conn.close()


def _make_gold(path: Path, rows: list[dict]) -> None:
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
            (r["code"], r["name"], r["name"].lower()),
        )
    conn.commit()
    conn.close()


def _seed_runtime(runtime: Path, rows: list[dict]) -> None:
    rm = RuntimeManager(runtime)
    rm.initialize()
    conn = rm.connection
    for r in rows:
        conn.execute(
            "INSERT INTO runtime_gold (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES (?, ?, ?)",
            (r["code"], r["name"], r["name"].lower()),
        )
    conn.commit()
    rm.close()


class TestRuntimeStatisticsBasics:
    def test_metricas_minimas_presentes(self, tmp_path):
        gold = tmp_path / "gold.db"
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"}])
        eng = LearningEngine(db_path=gold, runtime_db_path=tmp_path / "rt.db",
                             queue_path=tmp_path / "q.json")
        stats = RuntimeStatistics.capture(engine=eng)

        for key in ("runtime_exact_hits", "runtime_fuzzy_hits", "gold_exact_hits",
                    "gold_fuzzy_hits", "runtime_miss", "fallback_to_gold",
                    "rollback_count", "reject_count", "promotion_count"):
            assert hasattr(stats, key)
            assert getattr(stats, key) == 0

    def test_capture_con_metricas_snapshot(self, tmp_path):
        m = {
            "runtime_exact_hits": 3, "runtime_fuzzy_hits": 1,
            "gold_exact_hits": 2, "gold_fuzzy_hits": 0,
            "runtime_miss": 1, "fallback_to_gold": 1, "total_requests": 6,
            "runtime_hits_by_code": {"AC.01": 4},
        }
        stats = RuntimeStatistics.capture(metrics=m)
        assert stats.runtime_exact_hits == 3
        assert stats.fallback_to_gold == 1
        assert stats.total_requests == 6
        assert stats.runtime_hit_codes == {"AC.01": 4}

    def test_derivados_cobertura(self, tmp_path):
        m = {"runtime_exact_hits": 4, "runtime_fuzzy_hits": 1, "gold_exact_hits": 2,
             "gold_fuzzy_hits": 1, "runtime_miss": 2, "fallback_to_gold": 0,
             "total_requests": 8}
        stats = RuntimeStatistics.capture(metrics=m)
        assert stats.runtime_resolved == 5
        assert stats.gold_resolved == 3
        assert stats.runtime_usage_pct == 62.5
        assert stats.gold_usage_pct == 37.5
        assert stats.learning_used_pct == 62.5
        assert stats.runtime_miss == 2

    def test_total_requests_por_lookups_engine(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "rt.db"
        _make_gold(gold, [{"code": "AC.03", "name": "Clientes"}])
        eng = LearningEngine(db_path=gold, runtime_db_path=runtime,
                             queue_path=tmp_path / "q.json")
        eng.best_match("Clientes")
        eng.best_match("Otra cuenta")
        stats = RuntimeStatistics.capture(engine=eng)
        assert stats.total_requests == 2

    def test_fallback_se_cuenta_tras_miss_de_runtime(self, tmp_path):
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "rt.db"
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"},
                          {"code": "AC.03", "name": "Clientes"}])
        _seed_runtime(runtime, [{"code": "RT.01", "name": "Caja"}])
        eng = LearningEngine(db_path=gold, runtime_db_path=runtime,
                             queue_path=tmp_path / "q.json")

        eng.best_match("Caja")      # runtime exact -> sin fallback
        eng.best_match("Clientes")  # runtime miss -> fallback al gold exact

        stats = RuntimeStatistics.capture(engine=eng)
        assert stats.runtime_exact_hits == 1
        assert stats.gold_exact_hits == 1
        assert stats.runtime_miss == 1
        assert stats.fallback_to_gold == 1


class TestRuntimeStatisticsEvents:
    def test_eventos_y_cobertura_desde_rm(self, tmp_path):
        src = tmp_path / "src.db"
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "rt.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"},
                          {"code": "AC.03", "name": "Clientes"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False, source_ids=[1])
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")

        stats = RuntimeStatistics.capture(runtime=rm, gold_db=str(gold))
        assert stats.promotion_count == 1
        assert stats.reject_count == 1
        assert stats.rollback_count == 0
        assert stats.runtime_size == 1
        assert stats.gold_size == 2
        assert stats.runtime_catalog_coverage == 50.0

    def test_rollback_contado(self, tmp_path):
        src = tmp_path / "src.db"
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "rt.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False, source_ids=[1])
        rm.rollback(rm.load_runtime()[0]["id"], usuario="analista")

        stats = RuntimeStatistics.capture(runtime=rm, gold_db=str(gold))
        assert stats.rollback_count == 1
        assert stats.promotion_count == 1

    def test_impacto_por_promocion(self, tmp_path):
        src = tmp_path / "src.db"
        gold = tmp_path / "gold.db"
        runtime = tmp_path / "rt.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])
        _make_gold(gold, [{"code": "AC.01", "name": "Caja"},
                          {"code": "AC.03", "name": "Clientes"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False, source_ids=[1, 2])  # 2 promociones

        eng = LearningEngine(db_path=gold, runtime_db_path=runtime,
                             queue_path=tmp_path / "q.json")
        eng.best_match("Caja")  # usa AC.01 del runtime

        stats = RuntimeStatistics.capture(engine=eng, runtime=rm, gold_db=str(gold))
        assert len(stats.promotion_impact) == 2
        by_account = {p["account_name"]: p for p in stats.promotion_impact}
        assert by_account["Caja"]["impactful"] is True
        assert by_account["Caja"]["hits"] >= 1
        assert by_account["Clientes"]["impactful"] is False
        assert stats.impactful_promotions == 1

    def test_stub_reads_bare_subdir(self, tmp_path):
        # La captura no crea la DB runtime si solo se lee.
        runtime = tmp_path / "rt.db"
        stats = RuntimeStatistics.capture(runtime=RuntimeManager(runtime))
        assert not runtime.exists()
        assert stats.runtime_size == 0


@pytest.mark.skipif(not GOLD_DB.exists(), reason="gold_standard.db no disponible")
class TestBenchmarkProtected:
    def test_gold_db_intacta_tras_captura(self, tmp_path):
        runtime = tmp_path / "rt.db"
        _seed_runtime(runtime, [{"code": "AC.01", "name": "Caja"}])
        eng = LearningEngine(db_path=GOLD_DB, runtime_db_path=runtime,
                             queue_path=tmp_path / "q.json")
        eng.best_match("Caja")
        eng.best_match("Vehículos")

        before = GOLD_DB.read_bytes()
        stats = RuntimeStatistics.capture(engine=eng, runtime=RuntimeManager(runtime),
                                          gold_db=str(GOLD_DB))
        assert stats.total_requests == 2
        assert GOLD_DB.read_bytes() == before


if __name__ == "__main__":
    pytest.main([__file__])