"""Política explícita y conservadora de promoción al diccionario runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

DEFAULT_PROMOTION_MODE = "manual_supervisor"
MINIMUM_EVIDENCE = frozenset({"source_document", "human_decision", "classification_reason"})
DEFAULT_EXPIRATION_DAYS = 365


@dataclass
class PromotionDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    mode: str = DEFAULT_PROMOTION_MODE
    expires_in_days: int = DEFAULT_EXPIRATION_DAYS
    reversible: bool = True
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def expires_at(self) -> str:
        return (
            datetime.fromisoformat(self.evaluated_at)
            + timedelta(days=self.expires_in_days)
        ).isoformat()


def evaluate_promotion(*, supervisor: str, evidence: set[str], conflicts: int,
                       approved: bool, expires_in_days: int = DEFAULT_EXPIRATION_DAYS) -> PromotionDecision:
    reasons = []
    if not approved: reasons.append("Falta aprobación manual del supervisor")
    if not supervisor.strip(): reasons.append("Falta identificar al supervisor")
    missing = sorted(MINIMUM_EVIDENCE - set(evidence))
    if missing: reasons.append("Falta evidencia mínima: " + ", ".join(missing))
    if conflicts: reasons.append(f"Existen {conflicts} conflicto(s) sin resolver")
    if expires_in_days <= 0: reasons.append("La vigencia debe ser mayor que cero")
    return PromotionDecision(not reasons, reasons, expires_in_days=expires_in_days)
