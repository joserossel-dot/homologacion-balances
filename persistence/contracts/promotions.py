"""Contrato append-only para evidencia de política de promoción."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping, Protocol, runtime_checkable


PromotionOutcomeStatus = Literal["APPLIED", "FAILED", "INCONSISTENT"]


@dataclass(frozen=True, slots=True)
class PromotionPolicyRecord:
    """Evaluación persistible; no representa ni cambia el estado de la cola."""

    evaluation_id: str
    subject_id: str
    policy_mode: str
    allowed: bool
    decision_reasons: tuple[str, ...]
    evidence: Mapping[str, str]
    supervisor_actor_id: str
    supervisor_role: str
    organization_id: str
    conflict_count: int
    evaluated_at: datetime
    expires_at: datetime
    reversal_reference: str


@dataclass(frozen=True, slots=True)
class PromotionOutcomeRecord:
    """Resultado durable de aplicar una evaluación previamente persistida."""

    evaluation_id: str
    subject_id: str
    organization_id: str
    actor_id: str
    status: PromotionOutcomeStatus
    occurred_at: datetime
    promotion_ids: tuple[str, ...] = ()
    error: str | None = None


@runtime_checkable
class PromotionPolicyRepository(Protocol):
    def save_promotion_policy_metadata(
        self, record: PromotionPolicyRecord,
    ) -> PromotionPolicyRecord: ...

    def get_promotion_policy_metadata(
        self, evaluation_id: str,
        *,
        organization_id: str,
    ) -> PromotionPolicyRecord | None: ...

    def save_promotion_outcome(
        self, record: PromotionOutcomeRecord,
    ) -> PromotionOutcomeRecord: ...

    def get_promotion_outcome(
        self, evaluation_id: str, *, organization_id: str,
    ) -> PromotionOutcomeRecord | None: ...

    def list_promotion_outcomes_for_evaluation(
        self, evaluation_id: str, *, organization_id: str,
    ) -> list[PromotionOutcomeRecord]: ...

    def list_promotion_outcomes_for_subject(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionOutcomeRecord]: ...

    def list_unresolved_promotion_evaluations(
        self, subject_id: str, *, organization_id: str, limit: int = 100,
    ) -> list[PromotionPolicyRecord]: ...
