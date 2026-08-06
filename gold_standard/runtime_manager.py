"""gold_standard/runtime_manager.py — RuntimeManager del Learning Loop (P3/P5).

Administra la base de conocimiento runtime con tres tablas separadas:

  - runtime_gold         : conocimiento en evolución (espejo del gold + proveniencia).
  - promotion_history    : auditoría de promociones, rollbacks y rechazos.
  - metadata             : versión, checksum, fecha de creación/actualización.

P5 (Knowledge Manager):
  - RuntimeManager es la ÚNICA puerta de acceso a gold_standard_runtime.db.
  - Eventos registrados: PROMOTE / ROLLBACK / REJECT (nunca se borran).
  - Cada promoción tiene un ``promotion_id`` (UUID) que agrupa sus eventos.
  - Estado actual del candidato: PENDING / APPROVED / REJECTED / ROLLED_BACK.
  - Métodos de dominio: get_pending_promotions, reject_promotion, get_conflicts,
    get_runtime_statistics, get_runtime_coverage, get_history.

Reutiliza lógica existente por delegación (sin duplicar):
  - normalize_name                -> learning.exact_match
  - RESERVED_TOKENS, PromotionResult, _fetch_candidates -> gold_standard.promotion
  - fuzzy_score                   -> learning.fuzzy_match

Restricciones P3/P5 respetadas:
  - NO modifica learning/*, parser/*, pipeline/*, semantic/*, CMCC/* ni el benchmark.
  - NO toca gold_standard.db (solo lectura para comparaciones) ni la tabla
    ``gold_standard`` del runtime P1.1 (coexisten sin interferir).
  - NO ejecuta promociones automáticas: dry_run=True por defecto.
  - NO crea la DB runtime automáticamente: solo métodos de escritura explícitos
    (promote/rollback/reject/initialize) crean o escriben el archivo.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gold_standard.promotion import (
    RESERVED_TOKENS,
    PromotionResult,
    _fetch_candidates,
)
from learning.exact_match import normalize_name
from learning.fuzzy_match import fuzzy_score

logger = logging.getLogger(__name__)

RUNTIME_DB_DEFAULT = "gold_standard_runtime.db"
RUNTIME_SCHEMA_VERSION = "1.0"

# Eventos y estados del ciclo de vida de una promoción (P5)
EVENT_PROMOTE = "PROMOTE"
EVENT_ROLLBACK = "ROLLBACK"
EVENT_REJECT = "REJECT"
EVENT_DISABLE = "DISABLE"
EVENT_ENABLE = "ENABLE"
STATE_PENDING = "PENDING"
STATE_APPROVED = "APPROVED"
STATE_REJECTED = "REJECTED"
STATE_ROLLED_BACK = "ROLLED_BACK"
STATE_ACTIVE = "ACTIVE"
STATE_INACTIVE = "INACTIVE"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runtime_gold (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estandar  TEXT NOT NULL,
    nombre_cuenta    TEXT NOT NULL,
    normalized       TEXT NOT NULL,
    activa           INTEGER NOT NULL DEFAULT 1,
    source_record_id INTEGER NOT NULL DEFAULT 0,
    reviewer         TEXT NOT NULL DEFAULT '',
    review_date      TEXT NOT NULL DEFAULT '',
    promoted_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS promotion_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    promotion_id     TEXT NOT NULL DEFAULT '',
    fecha            TEXT NOT NULL,
    usuario          TEXT NOT NULL DEFAULT '',
    origen           TEXT NOT NULL DEFAULT '',
    accion           TEXT NOT NULL DEFAULT '',
    source_record_id INTEGER NOT NULL DEFAULT 0,
    account_name     TEXT NOT NULL DEFAULT '',
    codigo_anterior  TEXT,
    codigo_nuevo     TEXT,
    state            TEXT NOT NULL DEFAULT '',
    comentario       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

_INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_gold_norm_code
    ON runtime_gold(normalized, codigo_estandar);
CREATE INDEX IF NOT EXISTS idx_runtime_gold_source
    ON runtime_gold(source_record_id);
CREATE INDEX IF NOT EXISTS idx_promotion_history_fecha
    ON promotion_history(fecha);
CREATE INDEX IF NOT EXISTS idx_promotion_history_source
    ON promotion_history(source_record_id);
"""


class RuntimeManager:
    """Gestiona la DB runtime (runtime_gold + promotion_history + metadata).

    Es la única implementación nueva de P3. No modifica la DB del benchmark ni
    la infraestructura existente (P1.1); convive con ella en el mismo archivo.
    """

    def __init__(self, db_path: str | Path = RUNTIME_DB_DEFAULT) -> None:
        self._path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Conexión / schema
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connect()

    def exists(self) -> bool:
        return self._path.exists()

    def initialize(self) -> None:
        """Crea el schema (idempotente). Llamada explícita: no se auto-crea."""
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.executescript(_INDEXES)
        self._ensure_activa_column()
        self._init_metadata()
        conn.commit()

    def _ensure_activa_column(self) -> None:
        """Migración idempotente: agrega la columna ``activa`` a runtime_gold.

        ``activa`` controla si una entrada participa en las búsquedas del
        runtime (1) o está desactivada (0) sin eliminar el registro (auditable).
        """
        conn = self._connect()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(runtime_gold)").fetchall()]
        if "activa" not in cols:
            conn.execute(
                "ALTER TABLE runtime_gold ADD COLUMN activa INTEGER NOT NULL DEFAULT 1"
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _checksum(self) -> str:
        """SHA-256 sobre el contenido actual de runtime_gold."""
        if not self._path.exists():
            return ""
        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT id, codigo_estandar, nombre_cuenta, normalized, activa "
                "FROM runtime_gold ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return ""
        payload = "\n".join(
            f"{r['id']}|{r['codigo_estandar']}|{r['nombre_cuenta']}|{r['normalized']}|{r['activa']}"
            for r in rows
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _init_metadata(self) -> None:
        now = self._now()
        conn = self._connect()
        conn.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES ('version', ?)",
            (RUNTIME_SCHEMA_VERSION,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES ('fecha_creacion', ?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('fecha_actualizacion', ?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('checksum', ?)",
            (self._checksum(),),
        )

    def get_metadata(self, key: str) -> str | None:
        if not self._path.exists():
            return None
        try:
            row = self._connect().execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return row["value"] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        self.initialize()
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES ('fecha_actualizacion', ?)",
            (self._now(),),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def load_runtime(self) -> list[dict[str, Any]]:
        """Todas las filas de runtime_gold (ordenadas por id)."""
        if not self._path.exists():
            return []
        try:
            rows = self._connect().execute(
                "SELECT * FROM runtime_gold ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def search_runtime(self, account_name: str) -> dict[str, Any]:
        """Busca en runtime_gold: exacto primero, luego fuzzy.

        Solo considera entradas ``activa = 1`` (las desactivadas quedan
        excluidas de la búsqueda pero se conservan para auditoría).

        Contrato de salida idéntico al de ``LearningEngine.best_match`` para
        permitir un wiring futuro sin cambios de interfaz.
        """
        if not self._path.exists():
            return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT codigo_estandar, nombre_cuenta, normalized "
                "FROM runtime_gold WHERE activa = 1 ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

        norm = normalize_name(account_name)

        exact = next(
            (r for r in rows if normalize_name(r["normalized"]) == norm), None
        )
        if exact is not None:
            return {
                "source": "exact",
                "code": exact["codigo_estandar"],
                "confidence": 0.98,
                "matched_name": exact["nombre_cuenta"],
            }

        best_score = 0
        best_row = None
        for row in rows:
            score = fuzzy_score(norm, normalize_name(row["normalized"]))
            if score > best_score:
                best_score = score
                best_row = row

        if best_score >= 92 and best_row is not None:
            confidence = min(0.80 + (best_score - 92) * 0.01, 0.97)
            return {
                "source": "fuzzy",
                "code": best_row["codigo_estandar"],
                "confidence": round(confidence, 4),
                "matched_name": best_row["nombre_cuenta"],
            }

        return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}

    # ------------------------------------------------------------------
    # Promoción / rollback
    # ------------------------------------------------------------------

    def _classify(
        self,
        row: sqlite3.Row,
        *,
        reviewer_filter: str | None = None,
    ) -> dict[str, Any]:
        """Clasifica un candidato contra runtime_gold (espejo de promotion._classify)."""
        if reviewer_filter and row["reviewer"] != reviewer_filter:
            return {"status": "skip_reviewer"}

        final_code = (row["final_code"] or "").strip()
        name = (row["account_name"] or "").strip()
        if not final_code or not name:
            return {"status": "empty_code"}

        norm = normalize_name(name)
        if not norm:
            return {"status": "empty_code"}

        if any(token in norm.split() for token in RESERVED_TOKENS):
            return {"status": "reserved", "norm": norm}

        try:
            existing = self._connect().execute(
                "SELECT codigo_estandar FROM runtime_gold WHERE normalized = ?",
                (norm,),
            ).fetchall()
        except sqlite3.OperationalError:
            existing = []
        existing_codes = {r["codigo_estandar"] for r in existing}
        if existing_codes:
            if final_code in existing_codes:
                return {"status": "duplicate", "norm": norm, "code": final_code}
            return {
                "status": "conflict",
                "norm": norm,
                "code": final_code,
                "existing_codes": sorted(existing_codes),
                "name": name,
            }
        return {"status": "promotable", "norm": norm}

    def promote(
        self,
        source_db: str | Path,
        *,
        dry_run: bool = True,
        reviewer_filter: str | None = None,
        usuario: str = "system",
        origen: str = "gold_records",
        source_ids: list[int] | None = None,
    ) -> PromotionResult:
        """Promueve feedback humano (gold_records) a runtime_gold.

        Por defecto ``dry_run=True``: solo clasifica y cuenta, sin escribir.
        Con ``dry_run=False`` escribe runtime_gold + promotion_history + metadata.
        ``source_ids`` limita la promoción a un subconjunto de gold_records.
        Nunca modifica la DB fuente (benchmark).
        """
        result = PromotionResult(dry_run=dry_run)

        source_path = Path(source_db)
        if not source_path.exists():
            logger.warning("DB fuente no encontrada: %s", source_db)
            return result

        source_conn = sqlite3.connect(str(source_path))
        source_conn.row_factory = sqlite3.Row
        candidates = _fetch_candidates(source_conn)
        if source_ids is not None:
            allowed = set(source_ids)
            candidates = [c for c in candidates if c["id"] in allowed]
        result.candidates = len(candidates)

        # Clasificación contra runtime_gold. En dry-run sobre runtime inexistente
        # se usa una DB en memoria para NO crear el archivo (misma estrategia que
        # gold_standard.promotion:147).
        if dry_run and not self._path.exists():
            runtime = RuntimeManager(":memory:")
            runtime.initialize()
        else:
            runtime = self
            if not dry_run:
                runtime.initialize()

        promoted_rows: list[dict[str, Any]] = []
        now = self._now()
        for row in candidates:
            cls = runtime._classify(row, reviewer_filter=reviewer_filter)
            status = cls["status"]
            if status == "skip_reviewer":
                continue
            if status == "empty_code":
                result.empty_code += 1
                continue
            if status == "reserved":
                result.reserved += 1
                continue
            if status == "duplicate":
                result.duplicates += 1
                continue
            if status == "conflict":
                result.conflicts += 1
                result.conflict_details.append({
                    "name": cls["name"],
                    "candidate_code": cls["code"],
                    "existing_codes": ", ".join(cls["existing_codes"]),
                })
                continue
            result.promotable += 1
            promoted_rows.append({
                "source_record_id": row["id"],
                "account_name": row["account_name"],
                "final_code": row["final_code"],
                "reviewer": row["reviewer"] or "",
                "review_date": row["review_date"] or "",
            })

        if not dry_run:
            conn = runtime._connect()
            for pr in promoted_rows:
                try:
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO runtime_gold
                            (codigo_estandar, nombre_cuenta, normalized,
                             source_record_id, reviewer, review_date, promoted_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (pr["final_code"], pr["account_name"],
                         normalize_name(pr["account_name"]),
                         pr["source_record_id"], pr["reviewer"],
                         pr["review_date"], now),
                    )
                    if cur.rowcount == 0:
                        continue  # ya existía (ignorado por índice único)
                    promotion_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO promotion_history
                            (promotion_id, fecha, usuario, origen, accion,
                             source_record_id, account_name, codigo_anterior,
                             codigo_nuevo, state, comentario)
                        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                        """,
                        (promotion_id, now, usuario, origen, EVENT_PROMOTE,
                         pr["source_record_id"], pr["account_name"],
                         pr["final_code"], STATE_APPROVED,
                         f"{pr['account_name']} -> {pr['final_code']}"),
                    )
                    result.promoted += 1
                except sqlite3.IntegrityError as e:
                    logger.warning("Error promoviendo '%s' -> %s: %s",
                                   pr["account_name"], pr["final_code"], e)
                    result.errors += 1
            self._init_metadata()
            conn.commit()
        else:
            result.promoted = result.promotable

        source_conn.close()
        return result

    def rollback(
        self,
        entry_id: int,
        *,
        usuario: str = "system",
        comentario: str = "",
    ) -> bool:
        """Elimina una fila de runtime_gold y registra el evento en promotion_history.

        Reutiliza el ``promotion_id`` de la promoción original (si existe) y
        actualiza el estado del candidato a ROLLED_BACK. Nunca toca el benchmark.
        """
        if not self._path.exists():
            return False
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT codigo_estandar, nombre_cuenta, source_record_id "
                "FROM runtime_gold WHERE id = ?",
                (entry_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        if row is None:
            return False

        now = self._now()
        source_record_id = row["source_record_id"] or 0
        promotion_id = self._promotion_id_for(source_record_id)
        conn.execute("DELETE FROM runtime_gold WHERE id = ?", (entry_id,))
        conn.execute(
            """
            INSERT INTO promotion_history
                (promotion_id, fecha, usuario, origen, accion,
                 source_record_id, account_name, codigo_anterior,
                 codigo_nuevo, state, comentario)
            VALUES (?, ?, ?, 'runtime_gold', ?, ?, ?, ?, NULL, ?, ?)
            """,
            (promotion_id, now, usuario, EVENT_ROLLBACK,
             source_record_id, row["nombre_cuenta"], row["codigo_estandar"],
             STATE_ROLLED_BACK,
             comentario or f"rollback {row['nombre_cuenta']}"),
        )
        self._init_metadata()
        conn.commit()
        return True

    def set_active(
        self,
        entry_id: int,
        *,
        activa: bool,
        usuario: str = "system",
        comentario: str = "",
    ) -> bool:
        """Activa (activa=True) o desactiva (activa=False) una entrada del runtime.

        No elimina el registro: conserva ``runtime_gold`` completo para
        trazabilidad. Registra el evento ENABLE/DISABLE en promotion_history.
        Solo las entradas ``activa = 1`` participan en ``search_runtime``.
        """
        if not self._path.exists():
            return False
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT codigo_estandar, nombre_cuenta, source_record_id "
                "FROM runtime_gold WHERE id = ?",
                (entry_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return False
        if row is None:
            return False

        valor = 1 if activa else 0
        conn.execute(
            "UPDATE runtime_gold SET activa = ? WHERE id = ?", (valor, entry_id)
        )

        now = self._now()
        source_record_id = row["source_record_id"] or 0
        promotion_id = self._promotion_id_for(source_record_id)
        accion = EVENT_ENABLE if activa else EVENT_DISABLE
        state = STATE_ACTIVE if activa else STATE_INACTIVE
        conn.execute(
            """
            INSERT INTO promotion_history
                (promotion_id, fecha, usuario, origen, accion,
                 source_record_id, account_name, codigo_anterior,
                 codigo_nuevo, state, comentario)
            VALUES (?, ?, ?, 'runtime_gold', ?, ?, ?, ?, ?, ?, ?)
            """,
            (promotion_id, now, usuario, accion,
             source_record_id, row["nombre_cuenta"], row["codigo_estandar"],
             row["codigo_estandar"], state,
             comentario or f"{accion} {row['nombre_cuenta']}"),
        )
        self._init_metadata()
        conn.commit()
        return True

    def deactivate(
        self,
        entry_id: int,
        *,
        usuario: str = "system",
        comentario: str = "",
    ) -> bool:
        return self.set_active(entry_id, activa=False, usuario=usuario, comentario=comentario)

    def activate(
        self,
        entry_id: int,
        *,
        usuario: str = "system",
        comentario: str = "",
    ) -> bool:
        return self.set_active(entry_id, activa=True, usuario=usuario, comentario=comentario)

    def get_active_keys(self) -> list[dict[str, Any]]:
        """Entradas de runtime_gold activas (activa = 1)."""
        if not self._path.exists():
            return []
        try:
            rows = self._connect().execute(
                "SELECT * FROM runtime_gold WHERE activa = 1 ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        if not self._path.exists():
            return {
                "exists": False,
                "runtime_gold": 0,
                "promotion_history": 0,
                "metadata": {},
            }
        try:
            conn = self._connect()
            gold = conn.execute(
                "SELECT COUNT(*) FROM runtime_gold"
            ).fetchone()[0]
            hist = conn.execute(
                "SELECT COUNT(*) FROM promotion_history"
            ).fetchone()[0]
            meta = {r["key"]: r["value"] for r in conn.execute(
                "SELECT key, value FROM metadata"
            ).fetchall()}
        except sqlite3.OperationalError:
            return {
                "exists": True,
                "runtime_gold": 0,
                "promotion_history": 0,
                "metadata": {},
            }
        return {
            "exists": True,
            "runtime_gold": gold,
            "promotion_history": hist,
            "metadata": meta,
        }

    def load_history(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            rows = self._connect().execute(
                "SELECT * FROM promotion_history ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Knowledge Manager (P5) — métodos de dominio
    # ------------------------------------------------------------------

    def get_pending_promotions(
        self, source_db: str | Path = "gold_standard.db",
    ) -> list[dict[str, Any]]:
        """Candidatos de gold_records (fuente, solo lectura) clasificados contra runtime_gold.

        Cada fila incluye el estado del ciclo de vida (PENDING/APPROVED/REJECTED/
        ROLLED_BACK) derivado de promotion_history. No escribe ni crea el runtime.
        """
        source_path = Path(source_db)
        if not source_path.exists():
            return []

        runtime = self if self._path.exists() else RuntimeManager(":memory:")
        conn = None
        try:
            conn = sqlite3.connect(str(source_path))
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT id, account_name, final_code, reviewer, review_date, "
                    "source_file, suggested_confidence FROM gold_records ORDER BY id"
                ).fetchall()
                has_detail = True
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "SELECT id, account_name, final_code, reviewer, review_date "
                    "FROM gold_records ORDER BY id"
                ).fetchall()
                has_detail = False
        except sqlite3.OperationalError:
            return []
        finally:
            if conn is not None:
                conn.close()

        pending: list[dict[str, Any]] = []
        for row in rows:
            cls = runtime._classify(row)
            status = cls["status"]
            if status in ("skip_reviewer", "empty_code", "reserved"):
                continue
            pending.append({
                "source_record_id": row["id"],
                "account_name": row["account_name"],
                "candidate_code": row["final_code"],
                "origen": row["source_file"] if has_detail else "",
                "reviewer": row["reviewer"] or "",
                "confidence": row["suggested_confidence"] if has_detail else 0.0,
                "fecha": row["review_date"] or "",
                "status": status,
                "state": self._candidate_state(row["id"]),
            })
        return pending

    def reject_promotion(
        self,
        *,
        source_record_id: int,
        account_name: str,
        candidate_code: str,
        usuario: str = "system",
        comentario: str = "",
    ) -> bool:
        """Registra un rechazo de promoción (evento REJECT) en promotion_history.

        No modifica runtime_gold ni el benchmark. El rechazo es una decisión del
        analista y queda completamente auditable.
        """
        self.initialize()
        conn = self._connect()
        now = self._now()
        promotion_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO promotion_history
                (promotion_id, fecha, usuario, origen, accion,
                 source_record_id, account_name, codigo_anterior,
                 codigo_nuevo, state, comentario)
            VALUES (?, ?, ?, 'gold_records', ?, ?, ?, NULL, ?, ?, ?)
            """,
            (promotion_id, now, usuario, EVENT_REJECT,
             source_record_id, account_name, candidate_code, STATE_REJECTED,
             comentario or f"Promoción rechazada: {account_name} -> {candidate_code}"),
        )
        self._init_metadata()
        conn.commit()
        return True

    def get_conflicts(
        self, gold_db: str | Path = "gold_standard.db",
    ) -> list[dict[str, Any]]:
        """Entradas de runtime_gold que difieren del gold oficial (mismo normalized, código distinto)."""
        if not self._path.exists():
            return []
        gold_map = self._gold_code_map(gold_db)
        if not gold_map:
            return []
        conflicts: list[dict[str, Any]] = []
        for r in self.load_runtime():
            norm = r["normalized"]
            gold_code = gold_map.get(norm)
            if gold_code is not None and gold_code != r["codigo_estandar"]:
                conflicts.append({
                    "runtime_id": r["id"],
                    "account_name": r["nombre_cuenta"],
                    "normalized": norm,
                    "codigo_runtime": r["codigo_estandar"],
                    "codigo_gold": gold_code,
                })
        return conflicts

    def get_runtime_coverage(
        self, gold_db: str | Path = "gold_standard.db",
    ) -> dict[str, Any]:
        """Cobertura del runtime frente al gold oficial (solo lectura)."""
        if self._path.exists():
            try:
                conn = self._connect()
                runtime_size = conn.execute(
                    "SELECT COUNT(*) FROM runtime_gold"
                ).fetchone()[0]
                runtime_distinct = conn.execute(
                    "SELECT COUNT(DISTINCT normalized) FROM runtime_gold"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                runtime_size = 0
                runtime_distinct = 0
        else:
            runtime_size = 0
            runtime_distinct = 0
        gold_map = self._gold_code_map(gold_db)
        gold_size = len(gold_map)
        gold_distinct = len({n.strip().lower() for n in gold_map})
        coverage = (runtime_distinct / gold_distinct * 100.0) if gold_distinct else 0.0
        return {
            "runtime_size": runtime_size,
            "runtime_distinct": runtime_distinct,
            "gold_size": gold_distinct,
            "coverage": round(coverage, 2),
        }

    def get_runtime_statistics(
        self, gold_db: str | Path = "gold_standard.db",
    ) -> dict[str, Any]:
        """Estadísticas del runtime: tamaño, promociones, rechazos, rollbacks y cobertura."""
        coverage = self.get_runtime_coverage(gold_db)
        events: Counter[str] = Counter()
        for h in self.load_history():
            events[h.get("accion", "").upper()] += 1
        return {
            "runtime_size": coverage["runtime_size"],
            "coverage": coverage["coverage"],
            "gold_size": coverage["gold_size"],
            "promotions": events.get(EVENT_PROMOTE, 0),
            "rollbacks": events.get(EVENT_ROLLBACK, 0),
            "rejects": events.get(EVENT_REJECT, 0),
            "history_events": sum(events.values()),
        }

    def get_history(
        self, account_name: str | None = None, limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Historial de promotion_history, más reciente primero, opcionalmente filtrado por cuenta."""
        rows = self.load_history()
        if account_name:
            needle = account_name.lower()
            rows = [
                r for r in rows
                if needle in (r.get("account_name") or "").lower()
                or needle in (r.get("comentario") or "").lower()
            ]
        return list(reversed(rows[-limit:]))

    # ------------------------------------------------------------------
    # Internal: estado del candidato y helpers de lectura
    # ------------------------------------------------------------------

    def _candidate_state(self, source_record_id: int) -> str:
        event = self._latest_event_for(source_record_id)
        if event is None:
            return STATE_PENDING
        return event.get("state") or STATE_PENDING

    def _latest_event_for(self, source_record_id: int) -> dict[str, Any] | None:
        if not self._path.exists() or not source_record_id:
            return None
        try:
            row = self._connect().execute(
                "SELECT * FROM promotion_history "
                "WHERE source_record_id = ? ORDER BY id DESC LIMIT 1",
                (source_record_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None

    def _promotion_id_for(self, source_record_id: int) -> str:
        if source_record_id:
            event = self._latest_event_for(source_record_id)
            if event and event.get("promotion_id"):
                return event["promotion_id"]
        return str(uuid.uuid4())

    def _gold_code_map(self, gold_db: str | Path) -> dict[str, str]:
        """Mapa normalized -> codigo_estandar del gold oficial (solo lectura)."""
        path = Path(gold_db)
        if not path.exists():
            return {}
        conn = sqlite3.connect(str(path))
        try:
            rows = conn.execute(
                "SELECT normalized, codigo_estandar FROM gold_standard"
            ).fetchall()
            return {r[0]: r[1] for r in rows}
        except sqlite3.OperationalError:
            return {}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> RuntimeManager:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
