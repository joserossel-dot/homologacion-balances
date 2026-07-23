from __future__ import annotations

import copy
import re
from collections import Counter, defaultdict
from typing import Any

from .knowledge_diff import KnowledgeChange, KnowledgeDiff
from .knowledge_snapshot import KnowledgeSnapshot


class ImpactAnalyzer:
    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        self._unknown_names = snapshot.get("unknown_names", [])
        self._concept_counts = snapshot.get("concept_counts", {})

    def simulate_add_variant(self, concept_code: str, new_variant: str) -> dict:
        code = concept_code.upper().strip()
        variant_lower = new_variant.lower().strip()
        if not variant_lower:
            return {"error": "Empty variant"}

        original_variants = self.snapshot.get("variants_by_code", {}).get(code, [])

        matched_accounts = []
        matched_docs = set()
        matched_companies = set()

        for name in self._unknown_names:
            if not name:
                continue
            if variant_lower in name.lower():
                matched_accounts.append(name)
                matched_docs.add(name)

        matched_company_count = len(set(matched_accounts))

        already_exists = variant_lower in original_variants

        return {
            "concept_code": code,
            "new_variant": new_variant,
            "already_exists": already_exists,
            "new_matched_accounts": len(matched_accounts),
            "new_matched_companies": matched_company_count,
            "sample_accounts": matched_accounts[:5],
        }

    def simulate_add_all_variants(self, new_variants_by_code: dict[str, list[str]]) -> list[dict]:
        results = []
        for code, variants in new_variants_by_code.items():
            for v in variants:
                result = self.simulate_add_variant(code, v)
                results.append(result)
        return results

    def simulate_bulk(self, new_variants_by_code: dict[str, list[str]]) -> dict:
        snap_b = copy.deepcopy(self.snapshot)
        snap_b_variants = dict(snap_b.get("variants_by_code", {}))
        unknown_before = len(self._unknown_names)

        total_new_accounts = 0
        total_new_companies = 0
        concept_gains: dict[str, int] = {}
        concept_added_variants: dict[str, list[str]] = {}

        for code, variants in new_variants_by_code.items():
            code = code.upper().strip()
            if code not in snap_b_variants:
                snap_b_variants[code] = []
            concept_added_variants[code] = []
            for v in variants:
                vl = v.lower().strip()
                if vl not in snap_b_variants[code]:
                    snap_b_variants[code].append(vl)
                    concept_added_variants[code].append(v)

                    matched = 0
                    matched_companies = set()
                    for name in self._unknown_names:
                        if name and vl in name.lower():
                            matched += 1
                            matched_companies.add(name)
                    total_new_accounts += matched
                    total_new_companies += len(matched_companies)
                    if code not in concept_gains:
                        concept_gains[code] = 0
                    concept_gains[code] += matched

        snap_b["variants_by_code"] = snap_b_variants
        snap_b["variant_count"] = sum(len(v) for v in snap_b_variants.values())
        snap_b["statistics"] = dict(snap_b.get("statistics", {}))
        snap_b["statistics"]["total_unknown"] = unknown_before - total_new_accounts
        snap_b["statistics"]["total_classified"] = (
            snap_b["statistics"].get("total_classified", 0) + total_new_accounts
        )
        total_accts = snap_b["statistics"].get("total_accounts", 1)
        snap_b["statistics"]["classify_rate"] = round(
            snap_b["statistics"]["total_classified"] / total_accts * 100, 1
        )
        snap_b["statistics"]["unknown_rate"] = round(
            snap_b["statistics"]["total_unknown"] / total_accts * 100, 1
        )

        diff = KnowledgeDiff(self.snapshot, snap_b)
        changes = diff.generate_changes(source="impact_analysis")

        for chg in changes:
            code = chg.concept
            added_variants_list = concept_added_variants.get(code, [])
            for av in added_variants_list:
                if av.lower().strip() == chg.new_value.lower().strip():
                    chg.impact_accounts = concept_gains.get(code, 0)
                    chg.impact_documents = concept_gains.get(code, 0)
                    chg.impact_companies = concept_gains.get(code, 0)

        return {
            "snapshot_before": {
                "variant_count": self.snapshot.get("variant_count", 0),
                "concept_count": len(self.snapshot.get("variants_by_code", {})),
                "unknown_count": unknown_before,
                "classify_rate": self.snapshot.get("statistics", {}).get("classify_rate", 0),
            },
            "snapshot_after": {
                "variant_count": snap_b["variant_count"],
                "concept_count": len(snap_b_variants),
                "unknown_count": snap_b["statistics"]["total_unknown"],
                "classify_rate": snap_b["statistics"]["classify_rate"],
            },
            "total_new_accounts": total_new_accounts,
            "total_new_companies": total_new_companies,
            "concept_gains": dict(sorted(concept_gains.items(), key=lambda x: -x[1])),
            "variants_added": {
                code: len(vs) for code, vs in concept_added_variants.items() if vs
            },
            "changes": [ch.to_dict() for ch in changes],
            "diff_summary": diff.summary(),
        }

    def compute_impact(self, changes: list[KnowledgeChange]) -> dict:
        total_accounts = 0
        total_docs = 0
        total_companies = 0
        concept_impacts: Counter = Counter()

        for chg in changes:
            total_accounts += chg.impact_accounts
            total_docs += chg.impact_documents
            total_companies += chg.impact_companies
            concept_impacts[chg.concept] += chg.impact_accounts

        return {
            "total_impact_accounts": total_accounts,
            "total_impact_documents": total_docs,
            "total_impact_companies": total_companies,
            "concept_impacts": dict(concept_impacts.most_common()),
            "changes_count": len(changes),
            "pending_approval": sum(1 for chg in changes if not chg.approved),
        }

    def coverage_before(self) -> dict:
        stats = self.snapshot.get("statistics", {})
        return {
            "total_accounts": stats.get("total_accounts", 0),
            "classified": stats.get("total_classified", 0),
            "unknown": stats.get("total_unknown", 0),
            "classify_rate": stats.get("classify_rate", 0),
            "unknown_rate": stats.get("unknown_rate", 0),
        }

    def unknown_analysis(self) -> dict:
        names = self._unknown_names
        if not names:
            return {"total_unknown": 0}

        token_counter: Counter = Counter()
        for name in names:
            tokens = re.split(r"\s+", name.lower().strip())
            for t in tokens:
                if len(t) > 2:
                    token_counter[t] += 1

        return {
            "total_unknown": len(names),
            "unique_names": len(set(names)),
            "top_tokens": token_counter.most_common(30),
            "single_occurrence": sum(1 for v in token_counter.values() if v == 1),
        }
