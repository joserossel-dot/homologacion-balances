"""Construcción conservadora de metadata para una promoción supervisada."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Mapping
from uuid import UUID, uuid4

from persistence.contracts.identity import AuthenticatedActor, require_role
from persistence.contracts.promotions import PromotionOutcomeRecord, PromotionPolicyRecord
from validation.promotion_policy import (
    DEFAULT_EXPIRATION_DAYS,
    DEFAULT_PROMOTION_MODE,
    evaluate_promotion,
)


_SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,299}$")
_GENERIC_ACTOR_IDS = frozenset({"analista", "supervisor", "admin", "system", "sistema"})


def _reference(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not _SAFE_REFERENCE.fullmatch(normalized):
        raise ValueError(f"{field} inválido")
    return normalized


def _error_text(value: str) -> str:
    normalized = " ".join(str(value or "").split())
    if not normalized or len(normalized) > 500:
        raise ValueError("error normalizado inválido")
    return normalized


def build_promotion_policy_record(
    *,
    subject_id: str,
    actor: AuthenticatedActor | None,
    evidence: Mapping[str, str],
    conflicts: int,
    approved: bool,
    reversal_reference: str,
    evaluated_at: datetime | None = None,
    expires_in_days: int = DEFAULT_EXPIRATION_DAYS,
    evaluation_id: str | None = None,
) -> PromotionPolicyRecord:
    """Evalúa la política y genera metadata sin aplicar una promoción.

    No existe actor predeterminado. Un literal heredado como ``analista`` no
    puede convertirse implícitamente en supervisor: se exige identidad
    autenticada, organización y rol supervisor o superior.
    """
    require_role(actor, "supervisor")
    assert actor is not None  # acotación para typing; require_role falla si falta
    if actor.actor_id.strip().casefold() in _GENERIC_ACTOR_IDS:
        raise ValueError("Se requiere un actor supervisor individual, no genérico")
    if int(conflicts) < 0:
        raise ValueError("conflicts no puede ser negativo")
    if int(expires_in_days) <= 0:
        raise ValueError("expires_in_days debe ser mayor que cero")
    clean_evidence = {
        _reference(key, "tipo de evidencia"): _reference(value, "referencia de evidencia")
        for key, value in evidence.items()
    }
    decision = evaluate_promotion(
        supervisor=actor.actor_id,
        evidence=set(clean_evidence),
        conflicts=int(conflicts),
        approved=bool(approved),
        expires_in_days=int(expires_in_days),
    )
    moment = evaluated_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("evaluated_at debe incluir zona horaria")
    moment = moment.astimezone(timezone.utc)
    role = "admin" if "admin" in actor.roles else "supervisor"
    raw_evaluation_id = evaluation_id or str(uuid4())
    try:
        canonical_evaluation_id = str(UUID(raw_evaluation_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError("evaluation_id inválido") from exc
    return PromotionPolicyRecord(
        evaluation_id=canonical_evaluation_id,
        subject_id=_reference(subject_id, "subject_id"),
        policy_mode=DEFAULT_PROMOTION_MODE,
        allowed=decision.allowed,
        decision_reasons=tuple(decision.reasons),
        evidence=dict(sorted(clean_evidence.items())),
        supervisor_actor_id=_reference(actor.actor_id, "supervisor_actor_id"),
        supervisor_role=role,
        organization_id=_reference(actor.organization_id, "organization_id"),
        conflict_count=int(conflicts),
        evaluated_at=moment,
        expires_at=moment + timedelta(days=int(expires_in_days)),
        reversal_reference=_reference(reversal_reference, "reversal_reference"),
    )


def validate_promotion_policy_record(record: PromotionPolicyRecord) -> None:
    """Valida defensivamente registros construidos fuera del helper canónico."""
    try:
        canonical_evaluation_id = str(UUID(record.evaluation_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError("evaluation_id inválido") from exc
    if record.evaluation_id != canonical_evaluation_id:
        raise ValueError("evaluation_id debe usar formato UUID canónico")
    if record.policy_mode != DEFAULT_PROMOTION_MODE:
        raise ValueError("Modo de política de promoción inválido")
    if record.supervisor_role not in {"supervisor", "admin"}:
        raise ValueError("Se requiere actor supervisor explícito")
    _reference(record.supervisor_actor_id, "supervisor_actor_id")
    _reference(record.organization_id, "organization_id")
    _reference(record.subject_id, "subject_id")
    _reference(record.reversal_reference, "reversal_reference")
    if record.supervisor_actor_id.strip().casefold() in _GENERIC_ACTOR_IDS:
        raise ValueError("Se requiere un actor supervisor individual, no genérico")
    if record.conflict_count < 0:
        raise ValueError("conflict_count no puede ser negativo")
    if record.evaluated_at.tzinfo is None or record.expires_at.tzinfo is None:
        raise ValueError("Las fechas deben incluir zona horaria")
    if record.expires_at <= record.evaluated_at:
        raise ValueError("La expiración debe ser posterior a la evaluación")
    for key, value in record.evidence.items():
        _reference(key, "tipo de evidencia")
        _reference(value, "referencia de evidencia")


def promotion_record_payload(record: PromotionPolicyRecord) -> dict[str, object]:
    validate_promotion_policy_record(record)
    return {
        "evaluation_id": record.evaluation_id,
        "subject_id": record.subject_id,
        "policy_mode": record.policy_mode,
        "allowed": bool(record.allowed),
        "decision_reasons": list(record.decision_reasons),
        "evidence": dict(sorted(record.evidence.items())),
        "supervisor_actor_id": record.supervisor_actor_id,
        "supervisor_role": record.supervisor_role,
        "organization_id": record.organization_id,
        "conflict_count": int(record.conflict_count),
        "evaluated_at": record.evaluated_at.astimezone(timezone.utc).isoformat(),
        "expires_at": record.expires_at.astimezone(timezone.utc).isoformat(),
        "reversal_reference": record.reversal_reference,
    }


def promotion_record_fingerprint(record: PromotionPolicyRecord) -> str:
    payload = json.dumps(
        promotion_record_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_promotion_outcome(record: PromotionOutcomeRecord) -> None:
    try:
        canonical = str(UUID(record.evaluation_id))
    except (ValueError, AttributeError) as exc:
        raise ValueError("evaluation_id inválido") from exc
    if record.evaluation_id != canonical:
        raise ValueError("evaluation_id debe usar formato UUID canónico")
    _reference(record.subject_id, "subject_id")
    _reference(record.organization_id, "organization_id")
    _reference(record.actor_id, "actor_id")
    if record.actor_id.strip().casefold() in _GENERIC_ACTOR_IDS:
        raise ValueError("Se requiere actor individual para outcome")
    if record.status not in {"APPLIED", "FAILED", "INCONSISTENT"}:
        raise ValueError("Estado de outcome inválido")
    if record.occurred_at.tzinfo is None:
        raise ValueError("occurred_at debe incluir zona horaria")
    if len(set(record.promotion_ids)) != len(record.promotion_ids):
        raise ValueError("promotion_ids no puede contener duplicados")
    for promotion_id in record.promotion_ids:
        _reference(promotion_id, "promotion_id")
    if record.error is not None:
        if record.error != _error_text(record.error):
            raise ValueError("error debe estar normalizado")
    if record.status == "APPLIED" and not record.promotion_ids:
        raise ValueError("APPLIED exige al menos un promotion_id")
    if record.status == "APPLIED" and record.error is not None:
        raise ValueError("APPLIED no permite error")
    if record.status in {"FAILED", "INCONSISTENT"} and not record.error:
        raise ValueError(f"{record.status} exige error normalizado")


def promotion_outcome_payload(record: PromotionOutcomeRecord) -> dict[str, object]:
    validate_promotion_outcome(record)
    return {
        "evaluation_id": record.evaluation_id,
        "subject_id": record.subject_id,
        "organization_id": record.organization_id,
        "actor_id": record.actor_id,
        "status": record.status,
        "promotion_ids": list(record.promotion_ids),
        "occurred_at": record.occurred_at.astimezone(timezone.utc).isoformat(),
        "error": record.error,
    }


def promotion_outcome_fingerprint(record: PromotionOutcomeRecord) -> str:
    return hashlib.sha256(json.dumps(
        promotion_outcome_payload(record), sort_keys=True,
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
