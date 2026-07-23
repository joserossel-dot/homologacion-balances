from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from review_ui.review_models import ReviewDecision, DecisionStatus
from review_ui.review_repository import ReviewRepository


def _update_timestamp(d: ReviewDecision) -> None:
    object.__setattr__(d, "updated_at", datetime.now(timezone.utc).isoformat())


def approve(
    decision: ReviewDecision,
    repo: ReviewRepository,
    reviewer: str = "",
    reason: str = "",
    comments: str = "",
) -> ReviewDecision:
    if decision.status != DecisionStatus.PENDING:
        raise ValueError(f"Cannot approve: status is {decision.status.value}, expected PENDING")
    object.__setattr__(decision, "status", DecisionStatus.APPROVED)
    object.__setattr__(decision, "reviewer", reviewer)
    object.__setattr__(decision, "reason", reason)
    object.__setattr__(decision, "comments", comments)
    _update_timestamp(decision)
    repo.save(decision)
    return decision


def reject(
    decision: ReviewDecision,
    repo: ReviewRepository,
    reviewer: str = "",
    reason: str = "",
    comments: str = "",
) -> ReviewDecision:
    if decision.status != DecisionStatus.PENDING:
        raise ValueError(f"Cannot reject: status is {decision.status.value}, expected PENDING")
    object.__setattr__(decision, "status", DecisionStatus.REJECTED)
    object.__setattr__(decision, "reviewer", reviewer)
    object.__setattr__(decision, "reason", reason)
    object.__setattr__(decision, "comments", comments)
    _update_timestamp(decision)
    repo.save(decision)
    return decision


def reassign(
    decision: ReviewDecision,
    repo: ReviewRepository,
    new_concept: str,
    new_concept_name: str = "",
    reviewer: str = "",
    reason: str = "",
    comments: str = "",
) -> ReviewDecision:
    if decision.status != DecisionStatus.PENDING:
        raise ValueError(f"Cannot reassign: status is {decision.status.value}, expected PENDING")
    object.__setattr__(decision, "status", DecisionStatus.REASSIGNED)
    object.__setattr__(decision, "suggested_concept", new_concept)
    object.__setattr__(decision, "suggested_concept_name", new_concept_name)
    object.__setattr__(decision, "reviewer", reviewer)
    object.__setattr__(decision, "reason", reason)
    object.__setattr__(decision, "comments", comments)
    _update_timestamp(decision)
    repo.save(decision)
    return decision


def undo(
    decision: ReviewDecision,
    repo: ReviewRepository,
    reason: str = "undo",
) -> ReviewDecision:
    if decision.status == DecisionStatus.PENDING:
        raise ValueError("Cannot undo: decision is already PENDING")
    object.__setattr__(decision, "status", DecisionStatus.PENDING)
    object.__setattr__(decision, "suggested_concept", decision.current_concept)
    object.__setattr__(decision, "suggested_concept_name", decision.current_concept_name)
    object.__setattr__(decision, "reason", reason)
    _update_timestamp(decision)
    repo.save(decision)
    return decision
