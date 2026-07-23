from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ChangeType(str, Enum):
    NEW_VARIANT = "NEW_VARIANT"
    NEW_SYNONYM = "NEW_SYNONYM"
    NEW_RULE = "NEW_RULE"
    NEW_PATTERN = "NEW_PATTERN"
    REMOVED_VARIANT = "REMOVED_VARIANT"
    MERGED_VARIANT = "MERGED_VARIANT"
    SPLIT_VARIANT = "SPLIT_VARIANT"
    RENAMED_VARIANT = "RENAMED_VARIANT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    CMCC_EXTENSION = "CMCC_EXTENSION"


@dataclass
class KnowledgeChange:
    change_id: str
    date: str
    source: str
    change_type: str
    concept: str
    old_value: str
    new_value: str
    reason: str
    impact_accounts: int
    impact_documents: int
    impact_companies: int
    approved: bool = False
    reviewed_by: str = ""
    review_date: str = ""

    def to_dict(self) -> dict:
        return {
            "change_id": self.change_id,
            "date": self.date,
            "source": self.source,
            "change_type": self.change_type,
            "concept": self.concept,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "impact_accounts": self.impact_accounts,
            "impact_documents": self.impact_documents,
            "impact_companies": self.impact_companies,
            "approved": self.approved,
            "reviewed_by": self.reviewed_by,
            "review_date": self.review_date,
        }


class KnowledgeDiff:
    def __init__(self, snapshot_a: dict, snapshot_b: dict):
        self.a = snapshot_a
        self.b = snapshot_b

    def variant_diff(self) -> dict[str, dict]:
        sa = self.a.get("variants_by_code", {})
        sb = self.b.get("variants_by_code", {})
        all_codes = set(sa.keys()) | set(sb.keys())
        result: dict[str, dict] = {}
        for code in sorted(all_codes):
            va = set(sa.get(code, []))
            vb = set(sb.get(code, []))
            added = vb - va
            removed = va - vb
            if added or removed:
                result[code] = {
                    "added": sorted(added),
                    "removed": sorted(removed),
                    "total_before": len(va),
                    "total_after": len(vb),
                    "delta": len(vb) - len(va),
                }
        return result

    def concept_count_diff(self) -> int:
        ca = len(self.a.get("variants_by_code", {}))
        cb = len(self.b.get("variants_by_code", {}))
        return cb - ca

    def variant_count_diff(self) -> int:
        return self.b.get("variant_count", 0) - self.a.get("variant_count", 0)

    def unknown_diff(self) -> int:
        return self.b.get("statistics", {}).get("total_unknown", 0) - self.a.get("statistics", {}).get("total_unknown", 0)

    def classify_rate_diff(self) -> float:
        return round(
            self.b.get("statistics", {}).get("classify_rate", 0)
            - self.a.get("statistics", {}).get("classify_rate", 0),
            1,
        )

    def generate_changes(self, source: str = "simulation") -> list[KnowledgeChange]:
        changes: list[KnowledgeChange] = []
        vdiff = self.variant_diff()
        now = datetime.now(timezone.utc).isoformat()
        for code, diff_info in vdiff.items():
            for variant in diff_info.get("added", []):
                changes.append(KnowledgeChange(
                    change_id=f"CHG-{code}-{variant[:20]}",
                    date=now,
                    source=source,
                    change_type=ChangeType.NEW_VARIANT.value,
                    concept=code,
                    old_value="",
                    new_value=variant,
                    reason="Variant added via simulation",
                    impact_accounts=0,
                    impact_documents=0,
                    impact_companies=0,
                    approved=False,
                ))
            for variant in diff_info.get("removed", []):
                changes.append(KnowledgeChange(
                    change_id=f"CHG-RM-{code}-{variant[:20]}",
                    date=now,
                    source=source,
                    change_type=ChangeType.REMOVED_VARIANT.value,
                    concept=code,
                    old_value=variant,
                    new_value="",
                    reason="Variant removed via simulation",
                    impact_accounts=0,
                    impact_documents=0,
                    impact_companies=0,
                    approved=False,
                ))
        return changes

    def summary(self) -> dict:
        return {
            "snapshot_a_version": self.a.get("version", "unknown"),
            "snapshot_b_version": self.b.get("version", "unknown"),
            "concept_diff": self.concept_count_diff(),
            "variant_diff": self.variant_count_diff(),
            "unknown_diff": self.unknown_diff(),
            "classify_rate_diff": self.classify_rate_diff(),
            "concepts_changed": list(self.variant_diff().keys()),
            "changes_count": sum(
                len(d.get("added", [])) + len(d.get("removed", []))
                for d in self.variant_diff().values()
            ),
        }
