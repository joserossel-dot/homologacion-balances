from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DecisionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REASSIGNED = "REASSIGNED"


@dataclass
class ReviewDecision:
    review_id: str
    trace_id: str
    variant: str
    account_name: str
    document_id: str
    company: str
    current_concept: str
    current_concept_name: str
    suggested_concept: str = ""
    suggested_concept_name: str = ""
    status: DecisionStatus = DecisionStatus.PENDING
    reviewer: str = ""
    reason: str = ""
    confidence: float = 1.0
    comments: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def generate_review_id(trace_id: str, variant: str) -> str:
        raw = f"{trace_id}::{variant}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def from_queue_entry(entry: dict[str, Any]) -> ReviewDecision:
        trace_id = entry.get("decision_trace_id", "")
        variant = entry.get("matched_variant", "")
        return ReviewDecision(
            review_id=ReviewDecision.generate_review_id(trace_id, variant),
            trace_id=trace_id,
            variant=variant,
            account_name=entry.get("account_name", ""),
            document_id=entry.get("document_id", ""),
            company=entry.get("company", ""),
            current_concept=entry.get("concept_code", ""),
            current_concept_name=entry.get("concept_name", ""),
            suggested_concept=entry.get("concept_code", ""),
            suggested_concept_name=entry.get("concept_name", ""),
            confidence=float(entry.get("score", 1.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "trace_id": self.trace_id,
            "variant": self.variant,
            "account_name": self.account_name,
            "document_id": self.document_id,
            "company": self.company,
            "current_concept": self.current_concept,
            "current_concept_name": self.current_concept_name,
            "suggested_concept": self.suggested_concept,
            "suggested_concept_name": self.suggested_concept_name,
            "status": self.status.value,
            "reviewer": self.reviewer,
            "reason": self.reason,
            "confidence": self.confidence,
            "comments": self.comments,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def columns() -> list[str]:
        return [
            "review_id", "trace_id", "variant", "account_name", "document_id",
            "company", "current_concept", "current_concept_name",
            "suggested_concept", "suggested_concept_name",
            "status", "reviewer", "reason", "confidence", "comments",
            "created_at", "updated_at",
        ]
