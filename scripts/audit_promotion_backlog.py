#!/usr/bin/env python3
"""Audita la cola de promoción sin exponer datos contables ni personales.

El script es deliberadamente de solo lectura. Cuando ``DATABASE_URL`` está
disponible usa la conexión de ``NeonKnowledgeStore`` y consulta únicamente:

* actividad agregada de ``log_validaciones``; y
* la vista agregable ``promotion_backlog_audit_v1``, si existe.

La tabla de validaciones no equivale a una cola de promoción. Si la vista no
existe, el resultado identifica esa limitación y no fabrica estados pendientes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.neon_store import NeonKnowledgeStore  # noqa: E402
from validation.promotion_policy import (  # noqa: E402
    DEFAULT_EXPIRATION_DAYS,
    DEFAULT_PROMOTION_MODE,
    MINIMUM_EVIDENCE,
    evaluate_promotion,
)

AUDIT_VIEW = "public.promotion_backlog_audit_v1"
VALIDATION_TABLE = "public.log_validaciones"
OUTCOME_TABLE = "public.promotion_outcomes"
_SAFE_STATUS = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _int(value: Any) -> int:
    return int(value or 0)


def _safe_status(value: Any) -> str:
    normalized = str(value or "UNKNOWN").strip().upper()
    return normalized if _SAFE_STATUS.fullmatch(normalized) else "OTHER"


def _policy_snapshot() -> dict[str, Any]:
    required = set(MINIMUM_EVIDENCE)
    denied_without_approval = evaluate_promotion(
        supervisor="supervisor",
        evidence=required,
        conflicts=0,
        approved=False,
    )
    denied_without_supervisor = evaluate_promotion(
        supervisor="",
        evidence=required,
        conflicts=0,
        approved=True,
    )
    allowed_complete = evaluate_promotion(
        supervisor="supervisor",
        evidence=required,
        conflicts=0,
        approved=True,
    )
    return {
        "mode": DEFAULT_PROMOTION_MODE,
        "manual_approval_required": not denied_without_approval.allowed,
        "supervisor_identity_required": not denied_without_supervisor.allowed,
        "minimum_evidence": sorted(required),
        "conflicts_must_be_zero": True,
        "expiration_days": DEFAULT_EXPIRATION_DAYS,
        "reversible": bool(allowed_complete.reversible),
        "contract_self_check": bool(allowed_complete.allowed),
    }


def _base_report(now: datetime, *, configured: bool) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "verification": {
            "status": "not_verified",
            "reason_code": "database_url_unavailable",
        },
        "source": {
            "kind": "neon",
            "database_url_configured": configured,
        },
        "policy": _policy_snapshot(),
        "promotion_backlog": None,
        "validation_activity": None,
        "promotion_outcome_activity": None,
        "policy_contrast": {
            "status": "not_evaluable",
            "reason_code": "promotion_states_unavailable",
        },
        "safety": {
            "read_only_transaction": True,
            "aggregate_only": True,
            "reviewer_identifiers_returned": False,
            "account_data_returned": False,
            "mutations_performed": False,
        },
        "recommended_action": (
            "Configurar acceso de solo lectura y publicar la vista agregada "
            "promotion_backlog_audit_v1 antes de afirmar el tamaño de la cola."
        ),
    }


def _relation_exists(cursor: Any, relation: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)::text", (relation,))
    row = cursor.fetchone()
    return bool(row and row[0])


def _read_validation_activity(cursor: Any) -> dict[str, Any] | None:
    if not _relation_exists(cursor, VALIDATION_TABLE):
        return None
    cursor.execute(
        """SELECT COUNT(*)::bigint,
                  COUNT(DISTINCT NULLIF(BTRIM(validado_por), ''))::bigint,
                  COUNT(*) FILTER (
                      WHERE validado_por IS NULL OR BTRIM(validado_por) = ''
                  )::bigint,
                  MIN(creado_en), MAX(creado_en)
           FROM public.log_validaciones"""
    )
    row = cursor.fetchone() or (0, 0, 0, None, None)
    return {
        "records": _int(row[0]),
        "distinct_reviewer_count": _int(row[1]),
        "missing_reviewer_count": _int(row[2]),
        "oldest_record_at": _iso(row[3]),
        "newest_record_at": _iso(row[4]),
        "is_promotion_backlog": False,
    }


def _read_backlog(cursor: Any) -> dict[str, Any] | None:
    if not _relation_exists(cursor, AUDIT_VIEW):
        return None
    cursor.execute(
        """SELECT COUNT(*)::bigint,
                  COUNT(DISTINCT NULLIF(BTRIM(reviewer_id), ''))::bigint,
                  COUNT(*) FILTER (
                      WHERE reviewer_id IS NULL OR BTRIM(reviewer_id) = ''
                  )::bigint,
                  MIN(created_at), MAX(created_at)
           FROM public.promotion_backlog_audit_v1"""
    )
    overall = cursor.fetchone() or (0, 0, 0, None, None)
    cursor.execute(
        """SELECT status, COUNT(*)::bigint, MIN(created_at)
           FROM public.promotion_backlog_audit_v1
           GROUP BY status ORDER BY status"""
    )
    states = [
        {
            "status": _safe_status(row[0]),
            "count": _int(row[1]),
            "oldest_record_at": _iso(row[2]),
        }
        for row in cursor.fetchall()
    ]
    states.sort(key=lambda item: item["status"])
    return {
        "total": _int(overall[0]),
        "distinct_reviewer_count": _int(overall[1]),
        "missing_reviewer_count": _int(overall[2]),
        "oldest_record_at": _iso(overall[3]),
        "newest_record_at": _iso(overall[4]),
        "by_status": states,
    }


def _read_outcome_activity(cursor: Any) -> dict[str, Any] | None:
    """Outcomes are events, not pending candidates or their current state."""
    if not _relation_exists(cursor, OUTCOME_TABLE):
        return None
    cursor.execute(
        """SELECT status, COUNT(*)::bigint, MIN(occurred_at), MAX(occurred_at)
           FROM public.promotion_outcomes GROUP BY status ORDER BY status"""
    )
    return {
        "is_promotion_backlog": False,
        "counts_are_events_not_current_candidates": True,
        "by_status": [
            {"status": _safe_status(row[0]), "count": _int(row[1]),
             "oldest_event_at": _iso(row[2]), "newest_event_at": _iso(row[3])}
            for row in cursor.fetchall()
        ],
    }


def _contrast_policy(backlog: dict[str, Any] | None) -> dict[str, Any]:
    if backlog is None:
        return {
            "status": "not_evaluable",
            "reason_code": "promotion_states_unavailable",
        }
    missing = _int(backlog.get("missing_reviewer_count"))
    return {
        "status": "requires_attention" if missing else "not_evaluable",
        "reason_code": "missing_reviewer" if missing else "approval_evidence_unavailable",
        "manual_supervisor_policy": DEFAULT_PROMOTION_MODE,
        "records_without_reviewer": missing,
        "note": (
            "La presencia de revisor es necesaria pero no prueba por sí sola "
            "la aprobación ni la evidencia mínima."
        ),
    }


def audit_promotion_backlog(
    *,
    database_url: str | None = None,
    connect: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Genera un reporte agregado. No escribe ni retorna filas individuales."""
    current = now or _utc_now()
    url = database_url if database_url is not None else os.environ.get("DATABASE_URL", "")
    report = _base_report(current, configured=bool(url))
    if not url:
        return report

    store = NeonKnowledgeStore(url, connect=connect)
    conn = None
    try:
        conn = store._connect()  # seam existente; sólo para consulta agregada
        if callable(getattr(conn, "set_session", None)):
            conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cursor:
            if not callable(getattr(conn, "set_session", None)):
                cursor.execute("SET TRANSACTION READ ONLY")
            report["validation_activity"] = _read_validation_activity(cursor)
            report["promotion_backlog"] = _read_backlog(cursor)
            report["promotion_outcome_activity"] = _read_outcome_activity(cursor)
        if hasattr(conn, "rollback"):
            conn.rollback()
    except Exception as exc:
        if conn is not None and hasattr(conn, "rollback"):
            try:
                conn.rollback()
            except Exception:
                pass
        report["verification"] = {
            "status": "not_verified",
            "reason_code": "read_only_query_failed",
            "error_type": type(exc).__name__,
        }
        report["recommended_action"] = (
            "Verificar conectividad, privilegios SELECT y existencia del esquema; "
            "el error detallado se omite para no filtrar credenciales."
        )
        return report
    finally:
        if conn is not None and hasattr(conn, "close"):
            conn.close()

    backlog = report["promotion_backlog"]
    report["policy_contrast"] = _contrast_policy(backlog)
    if backlog is None:
        report["verification"] = {
            "status": "verified_partial",
            "reason_code": "promotion_audit_view_unavailable",
        }
        report["recommended_action"] = (
            "Definir y persistir la fuente real de candidatos y estados antes de "
            "crear promotion_backlog_audit_v1. Las validaciones y los eventos de "
            "outcome no representan la cola completa."
        )
    else:
        report["verification"] = {"status": "verified", "reason_code": None}
        report["recommended_action"] = (
            "Revisar los conteos agregados bajo la política manual de supervisor; "
            "este auditor no aprueba ni rechaza registros."
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Auditor agregado y de solo lectura de la cola de promoción.",
    )
    parser.add_argument(
        "--require-verified",
        action="store_true",
        help="retorna código 2 si la cola no pudo verificarse completamente",
    )
    args = parser.parse_args(argv)
    report = audit_promotion_backlog()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.require_verified and report["verification"]["status"] != "verified":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
