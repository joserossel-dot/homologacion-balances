from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class ReviewCMCC:
    account_name: str
    document_id: str
    company: str
    layout: str
    concept_code: str
    concept_name: str
    score: float
    matched_variant: str
    matching_method: str
    evidence: list[str]
    decision_trace_id: str = ""
    shadow_only: bool = True
    review_status: str = "PENDING"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_pipeline_account(
        cls,
        account_name: str,
        source_file: str,
        cmcc_detail: dict[str, Any],
        company: str = "",
        layout: str = "",
    ) -> ReviewCMCC:
        trace_id = cls._compute_trace_id(source_file, account_name)
        return cls(
            account_name=account_name,
            document_id=source_file,
            company=company,
            layout=layout,
            concept_code=str(cmcc_detail.get("code", "")),
            concept_name=str(cmcc_detail.get("concept", "")),
            score=float(cmcc_detail.get("score", 0.0)),
            matched_variant=str(cmcc_detail.get("matched_variant", "")),
            matching_method=str(cmcc_detail.get("method", "")),
            evidence=cmcc_detail.get("evidence", []),
            decision_trace_id=trace_id,
            shadow_only=True,
            review_status="PENDING",
        )

    @staticmethod
    def _compute_trace_id(source_file: str, account_name: str) -> str:
        raw = f"{source_file}::{account_name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_name": self.account_name,
            "document_id": self.document_id,
            "company": self.company,
            "layout": self.layout,
            "concept_code": self.concept_code,
            "concept_name": self.concept_name,
            "score": self.score,
            "matched_variant": self.matched_variant,
            "matching_method": self.matching_method,
            "evidence": "; ".join(self.evidence) if self.evidence else "",
            "decision_trace_id": self.decision_trace_id,
            "shadow_only": self.shadow_only,
            "review_status": self.review_status,
            "created_at": self.created_at,
        }

    @staticmethod
    def columns() -> list[str]:
        return [
            "account_name", "document_id", "company", "layout",
            "concept_code", "concept_name", "score", "matched_variant",
            "matching_method", "evidence", "decision_trace_id",
            "shadow_only", "review_status", "created_at",
        ]
