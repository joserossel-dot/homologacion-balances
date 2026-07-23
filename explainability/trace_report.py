from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .decision_trace import DecisionTrace
from .enums import DecisionCode


class TraceReport:
    def __init__(self, traces: list[DecisionTrace]):
        self.traces = traces

    @property
    def total(self) -> int:
        return len(self.traces)

    @property
    def total_classified(self) -> int:
        return sum(1 for t in self.traces if t.official_classification != "UNKNOWN")

    @property
    def total_unknown(self) -> int:
        return sum(1 for t in self.traces if t.official_classification == "UNKNOWN")

    def distribution_by(self, attr: str) -> Counter:
        return Counter(getattr(t, attr, "unknown") for t in self.traces)

    def top_unknown(self, n: int = 20) -> list[DecisionTrace]:
        return [t for t in self.traces if t.official_classification == "UNKNOWN"][:n]

    def top_classified(self, n: int = 20) -> list[DecisionTrace]:
        return [t for t in self.traces if t.official_classification != "UNKNOWN"][:n]

    def top_documents(self, n: int = 10) -> list[tuple[str, int]]:
        doc_counter: Counter = Counter()
        for t in self.traces:
            doc = t.document_id.split("::")[0] if "::" in t.document_id else t.document_id
            doc_counter[doc] += 1
        return doc_counter.most_common(n)

    def top_concepts(self, n: int = 15) -> list[tuple[str, int]]:
        counter: Counter = Counter()
        for t in self.traces:
            if t.official_classification != "UNKNOWN":
                counter[t.official_classification] += 1
            elif t.shadow_classification:
                counter[f"{t.shadow_classification} (shadow)"] += 1
        return counter.most_common(n)

    def decision_code_stats(self) -> list[dict]:
        counter = self.distribution_by("decision_code")
        total = self.total or 1
        results = []
        for code, count in counter.most_common():
            results.append({
                "decision_code": code,
                "count": count,
                "percentage": round(count / total * 100, 1),
            })
        return results

    def layout_stats(self) -> list[dict]:
        counter = self.distribution_by("layout")
        total = self.total or 1
        results = []
        for layout, count in counter.most_common():
            results.append({
                "layout": layout,
                "count": count,
                "percentage": round(count / total * 100, 1),
                "classified": sum(
                    1 for t in self.traces
                    if t.layout == layout and t.official_classification != "UNKNOWN"
                ),
                "unknown": sum(
                    1 for t in self.traces
                    if t.layout == layout and t.official_classification == "UNKNOWN"
                ),
            })
        return results

    def match_type_stats(self) -> list[dict]:
        match_types = ["exact", "dictionary", "fuzzy", "cmcc_exact", "cmcc_fuzzy", "none", "shadow"]
        counters = {mt: 0 for mt in match_types}
        for t in self.traces:
            if t.cmcc_match:
                if t.cmcc_match_type == "exact":
                    counters["cmcc_exact"] += 1
                else:
                    counters["cmcc_fuzzy"] += 1
            elif t.dictionary_match:
                counters["dictionary"] += 1
            elif t.official_classification != "UNKNOWN":
                counters["fuzzy"] += 1
            elif t.shadow_classification and t.shadow_confidence > 0:
                counters["shadow"] += 1
            else:
                counters["none"] += 1
        total = self.total or 1
        results = []
        for mt, count in sorted(counters.items(), key=lambda x: -x[1]):
            if count > 0:
                results.append({
                    "match_type": mt,
                    "count": count,
                    "percentage": round(count / total * 100, 1),
                })
        return results

    def parser_status_stats(self) -> list[dict]:
        counter: Counter = Counter()
        for t in self.traces:
            if t.parser_confidence > 0:
                counter["ACCEPT"] += 1
            else:
                counter["REJECT"] += 1
        total = self.total or 1
        return [
            {"status": k, "count": v, "percentage": round(v / total * 100, 1)}
            for k, v in counter.most_common()
        ]

    def to_dict(self) -> dict:
        return {
            "total_accounts": self.total,
            "total_classified": self.total_classified,
            "total_unknown": self.total_unknown,
            "classify_rate": round(self.total_classified / max(self.total, 1) * 100, 1),
            "unknown_rate": round(self.total_unknown / max(self.total, 1) * 100, 1),
            "decision_code_distribution": self.decision_code_stats(),
            "layout_distribution": self.layout_stats(),
            "match_type_distribution": self.match_type_stats(),
            "parser_status_distribution": self.parser_status_stats(),
            "top_concepts": [
                {"concept": k, "count": v} for k, v in self.top_concepts(20)
            ],
            "top_documents": [
                {"document": k, "accounts": v} for k, v in self.top_documents(10)
            ],
        }
