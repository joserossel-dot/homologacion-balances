"""Tests de los métodos de dominio de RuntimeManager (P5 — Knowledge Manager).

Verifica sobre DBs temporales:
  - get_pending_promotions: clasificación + estado del candidato (PENDING/APPROVED/...).
  - Lecturas no crean el archivo runtime.
  - promote(source_ids): promueve solo el subconjunto seleccionado.
  - promotion_id (UUID) por promoción; eventos PROMOTE/ROLLBACK/REJECT.
  - reject_promotion: registra REJECT sin tocar runtime_gold ni gold.
  - get_conflicts: runtime vs gold (mismo normalized, código distinto).
  - get_runtime_statistics / get_runtime_coverage.
  - get_history filtrado.
  - Ciclo de vida PENDING → APPROVED → REJECTED / ROLLED_BACK.
  - Benchmark protegido: gold_standard.db real byte-idéntica.

Reglas P5:
  - Toda escritura ocurre solo en gold_standard_runtime.db (o temporal).
  - gold_standard.db nunca se modifica.
"""

from __future__ import annotations

import sqlite3
import uuid as uuid_lib
from pathlib import Path

import pytest

from gold_standard.runtime_manager import RuntimeManager

GOLD_DB = Path(__file__).resolve().parent.parent / "gold_standard.db"

GOLD_RECORDS_SQL = """
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
"""


def _make_source(path: Path, records: list[dict], gold: list[dict] | None = None) -> None:
    """Crea una DB fuente con gold_records (+ opcional gold_standard)."""
    conn = sqlite3.connect(str(path))
    conn.executescript(GOLD_RECORDS_SQL)
    if gold:
        conn.executescript(
            """
            CREATE TABLE gold_standard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_estandar TEXT NOT NULL,
                nombre_cuenta TEXT NOT NULL,
                normalized TEXT NOT NULL
            );
            """
        )
        for g in gold:
            conn.execute(
                "INSERT INTO gold_standard (codigo_estandar, nombre_cuenta, normalized) "
                "VALUES (?, ?, ?)",
                (g["code"], g["name"], g.get("normalized", g["name"].lower())),
            )
    for i, r in enumerate(records, start=1):
        conn.execute(
            """
            INSERT INTO gold_records (source_file, account_name, suggested_confidence,
                                      final_code, reviewer, review_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (r.get("origen", f"f{i}.pdf"), r["account_name"],
             r.get("confidence", 0.9), r["final_code"],
             r.get("reviewer", "analista"), r.get("fecha", "2026-01-01")),
        )
    conn.commit()
    conn.close()


def _conn(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(path))


def _events(runtime: Path) -> list[dict]:
    conn = _conn(runtime)
    rows = conn.execute("SELECT * FROM promotion_history ORDER BY id").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM promotion_history").description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


class TestPendingPromotions:
    def test_candidatos_clasificados_pending(self, tmp_path):
        src = tmp_path / "src.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])
        rm = RuntimeManager(tmp_path / "runtime.db")
        pend = rm.get_pending_promotions(src)

        assert len(pend) == 2
        assert all(p["status"] == "promotable" for p in pend)
        assert all(p["state"] == "PENDING" for p in pend)
        assert pend[0]["account_name"] == "Caja"
        assert pend[0]["candidate_code"] == "AC.01"

    def test_sin_runtime_no_crea_archivo(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])

        rm = RuntimeManager(runtime)
        pend = rm.get_pending_promotions(src)

        assert len(pend) == 1
        assert not runtime.exists()

    def test_fuente_ausente_retorna_vacio(self, tmp_path):
        rm = RuntimeManager(tmp_path / "runtime.db")
        assert rm.get_pending_promotions(tmp_path / "no_existe.db") == []


class TestPromoteSourceIds:
    def test_promueve_solo_subconjunto(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
            {"account_name": "Vehículos", "final_code": "ANC.03"},
        ])
        rm = RuntimeManager(runtime)
        res = rm.promote(src, dry_run=False, source_ids=[2])

        assert res.promoted == 1
        assert len(rm.load_runtime()) == 1
        assert rm.load_runtime()[0]["nombre_cuenta"] == "Clientes"

        pend = rm.get_pending_promotions(src)
        states = {p["account_name"]: p["state"] for p in pend}
        assert states["Clientes"] == "APPROVED"
        assert states["Caja"] == "PENDING"
        assert states["Vehículos"] == "PENDING"

    def test_evento_promote_con_uuid(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)

        evs = _events(runtime)
        assert len(evs) == 1
        assert evs[0]["accion"] == "PROMOTE"
        assert evs[0]["state"] == "APPROVED"
        uuid_lib.UUID(evs[0]["promotion_id"])  # noqa: B018 — valida formato UUID
        assert evs[0]["source_record_id"] == 1
        assert evs[0]["account_name"] == "Caja"


class TestReject:
    def test_reject_registra_reject(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        rm = RuntimeManager(runtime)

        assert rm.reject_promotion(
            source_record_id=1, account_name="Caja", candidate_code="AC.01",
            usuario="analista",
        )
        evs = _events(runtime)
        assert evs[-1]["accion"] == "REJECT"
        assert evs[-1]["state"] == "REJECTED"
        assert evs[-1]["usuario"] == "analista"
        assert len(rm.load_runtime()) == 0  # no toca runtime_gold

        pend = rm.get_pending_promotions(src)
        assert pend[0]["state"] == "REJECTED"

    def test_reject_crea_runtime_si_ausente(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        rm = RuntimeManager(runtime)
        rm.reject_promotion(source_record_id=1, account_name="Caja", candidate_code="AC.01")

        assert runtime.exists()  # escribir es una operación explícita
        evs = _events(runtime)
        assert evs[0]["accion"] == "REJECT"


class TestRollbackLifecycle:
    def test_rollback_reusa_promotion_id_y_estado(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)

        entry_id = rm.load_runtime()[0]["id"]
        assert rm.rollback(entry_id, usuario="analista")

        evs = _events(runtime)
        assert evs[0]["accion"] == "PROMOTE"
        assert evs[1]["accion"] == "ROLLBACK"
        assert evs[1]["state"] == "ROLLED_BACK"
        assert evs[1]["promotion_id"] == evs[0]["promotion_id"]  # mismo UUID
        assert len(rm.load_runtime()) == 0

    def test_ciclo_completo_estados(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
            {"account_name": "Vehículos", "final_code": "ANC.03"},
        ])
        rm = RuntimeManager(runtime)

        rm.promote(src, dry_run=False, source_ids=[1])
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")
        rm.promote(src, dry_run=False, source_ids=[3])
        entry_id = [r["id"] for r in rm.load_runtime()
                    if r["nombre_cuenta"] == "Vehículos"][0]
        rm.rollback(entry_id, usuario="analista")

        pend = rm.get_pending_promotions(src)
        states = {p["account_name"]: p["state"] for p in pend}
        assert states["Caja"] == "APPROVED"
        assert states["Clientes"] == "REJECTED"
        assert states["Vehículos"] == "ROLLED_BACK"


class TestConflicts:
    def test_conflicto_runtime_vs_gold(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
        ], gold=[{"code": "AC.01", "name": "Caja"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)

        # insertar entrada runtime con código distinto al gold para la misma cuenta
        conn = _conn(runtime)
        conn.execute(
            "INSERT INTO runtime_gold (codigo_estandar, nombre_cuenta, normalized) "
            "VALUES ('AC.99', 'Caja Modificada', 'caja')"
        )
        conn.commit()
        conn.close()

        conf = rm.get_conflicts(src)
        assert len(conf) == 1
        assert conf[0]["codigo_runtime"] == "AC.99"
        assert conf[0]["codigo_gold"] == "AC.01"

    def test_sin_conflicto_mismo_codigo(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
        ], gold=[{"code": "AC.01", "name": "Caja"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)

        assert rm.get_conflicts(src) == []

    def test_sin_runtime_no_conflictos(self, tmp_path):
        src = tmp_path / "src.db"
        _make_source(src, [{"account_name": "Caja", "final_code": "AC.01"}],
                     gold=[{"code": "AC.01", "name": "Caja"}])
        assert RuntimeManager(tmp_path / "runtime.db").get_conflicts(src) == []


class TestStatistics:
    def test_estadisticas_por_evento(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ], gold=[{"code": "AC.01", "name": "Caja"}, {"code": "AC.03", "name": "Clientes"}])
        rm = RuntimeManager(runtime)

        rm.promote(src, dry_run=False, source_ids=[1])
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")

        s = rm.get_runtime_statistics(src)
        assert s["promotions"] == 1
        assert s["rejects"] == 1
        assert s["rollbacks"] == 0
        assert s["runtime_size"] == 1
        assert s["history_events"] == 2

    def test_cobertura(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
        ], gold=[{"code": "AC.01", "name": "Caja"}, {"code": "AC.03", "name": "Clientes"}])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)

        cov = rm.get_runtime_coverage(src)
        assert cov["runtime_distinct"] == 1
        assert cov["gold_size"] == 2
        assert cov["coverage"] == 50.0

    def test_stats_sin_runtime(self, tmp_path):
        rm = RuntimeManager(tmp_path / "runtime.db")
        s = rm.get_runtime_statistics(tmp_path / "no.db")
        assert s["runtime_size"] == 0
        assert s["promotions"] == 0
        assert s["rejects"] == 0
        assert s["rollbacks"] == 0


class TestHistory:
    def test_get_history_filtra_por_cuenta(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])
        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False, source_ids=[1])
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")

        hist_caja = rm.get_history(account_name="Caja")
        assert len(hist_caja) == 1
        assert hist_caja[0]["account_name"] == "Caja"
        assert hist_caja[0]["accion"] == "PROMOTE"

        hist_total = rm.get_history()
        assert len(hist_total) == 2
        assert hist_total[0]["accion"] == "REJECT"  # más reciente primero


@pytest.mark.skipif(not GOLD_DB.exists(), reason="gold_standard.db no disponible")
class TestBenchmarkProtected:
    def test_gold_db_byte_identica(self, tmp_path):
        src = tmp_path / "src.db"
        runtime = tmp_path / "runtime.db"
        _make_source(src, [
            {"account_name": "Caja", "final_code": "AC.01"},
            {"account_name": "Clientes", "final_code": "AC.03"},
        ])
        before = GOLD_DB.read_bytes()

        rm = RuntimeManager(runtime)
        rm.promote(src, dry_run=False)
        rm.reject_promotion(source_record_id=2, account_name="Clientes",
                            candidate_code="AC.03", usuario="analista")
        rm.get_conflicts(GOLD_DB)
        rm.get_runtime_statistics(GOLD_DB)
        rm.rollback(rm.load_runtime()[0]["id"], usuario="analista")

        assert GOLD_DB.read_bytes() == before


if __name__ == "__main__":
    pytest.main([__file__])
