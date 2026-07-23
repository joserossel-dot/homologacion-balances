from __future__ import annotations

from collections import Counter
from typing import Any

from review_ui.review_models import ReviewDecision


def compute_statistics(decisions: list[ReviewDecision]) -> dict[str, Any]:
    total = len(decisions)
    if total == 0:
        return _empty_stats()

    status_counts = Counter(d.status.value for d in decisions)
    concept_counter = Counter(d.current_concept for d in decisions)
    reviewer_counter = Counter(d.reviewer for d in decisions)
    company_counter = Counter(d.company for d in decisions)

    approved = [d for d in decisions if d.status.value == "APPROVED"]
    rejected = [d for d in decisions if d.status.value == "REJECTED"]
    reassigned = [d for d in decisions if d.status.value == "REASSIGNED"]
    pending = [d for d in decisions if d.status.value == "PENDING"]

    return {
        "total_decisions": total,
        "pending": len(pending),
        "approved": len(approved),
        "rejected": len(rejected),
        "reassigned": len(reassigned),
        "approval_rate": round(len(approved) / max(total, 1) * 100, 2),
        "rejection_rate": round(len(rejected) / max(total, 1) * 100, 2),
        "reassignment_rate": round(len(reassigned) / max(total, 1) * 100, 2),
        "unique_variants_reviewed": len(set(d.variant for d in decisions)),
        "unique_concepts_impacted": len(concept_counter),
        "unique_reviewers": len(reviewer_counter),
        "unique_companies": len(company_counter),
        "top_concepts": concept_counter.most_common(10),
        "top_reviewers": reviewer_counter.most_common(10),
        "top_companies": company_counter.most_common(10),
        "avg_confidence": round(
            sum(d.confidence for d in decisions) / max(total, 1), 4
        ),
    }


def _empty_stats() -> dict[str, Any]:
    return {
        "total_decisions": 0,
        "pending": 0, "approved": 0, "rejected": 0, "reassigned": 0,
        "approval_rate": 0.0, "rejection_rate": 0.0, "reassignment_rate": 0.0,
        "unique_variants_reviewed": 0, "unique_concepts_impacted": 0,
        "unique_reviewers": 0, "unique_companies": 0,
        "top_concepts": [], "top_reviewers": [], "top_companies": [],
        "avg_confidence": 0.0,
    }
