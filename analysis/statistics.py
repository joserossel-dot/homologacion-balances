from __future__ import annotations
from collections import Counter, defaultdict
from .subtotal_trace import SubtotalTrace, RootCauseResult, PatternResult, FormatMatrix


class StatisticsGenerator:

    def __init__(self):
        self.traces: list[SubtotalTrace] = []
        self.root_causes: list[RootCauseResult] = []
        self.format_map: dict[str, str] = {}

    def add_result(self, trace: SubtotalTrace, cause: RootCauseResult, format_name: str = ""):
        self.traces.append(trace)
        self.root_causes.append(cause)
        self.format_map[trace.source_file] = format_name

    @property
    def total_differences(self) -> int:
        return len(self.root_causes)

    def cause_distribution(self) -> dict[str, int]:
        dist = Counter(r.cause for r in self.root_causes)
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    def format_distribution(self) -> dict[str, int]:
        dist = Counter(self.format_map.values())
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    def cause_by_format_matrix(self) -> list[FormatMatrix]:
        formats = set(self.format_map.values())
        matrix = []
        for fmt in sorted(formats):
            fm = FormatMatrix(format_name=fmt)
            file_set = set()
            for tr, rc in zip(self.traces, self.root_causes):
                if self.format_map.get(tr.source_file, "") == fmt:
                    fm.total_differences += 1
                    fm.by_cause[rc.cause] = fm.by_cause.get(rc.cause, 0) + 1
                    file_set.add(tr.source_file)
            fm.by_file = sorted(file_set)
            matrix.append(fm)
        return matrix

    def find_patterns(self, top_n: int = 20) -> list[PatternResult]:
        account_groups: dict[str, list] = defaultdict(list)

        for tr, rc in zip(self.traces, self.root_causes):
            name = tr.subtotal_name.strip()
            account_groups[name].append({
                "difference": tr.difference,
                "cause": rc.cause,
                "file": tr.source_file,
            })

        patterns = []
        for name, entries in account_groups.items():
            if len(entries) < 2:
                continue
            avg_diff = sum(abs(e["difference"]) for e in entries) / len(entries)
            total_diff = sum(abs(e["difference"]) for e in entries)
            causes = Counter(e["cause"] for e in entries)
            typical_cause = causes.most_common(1)[0][0] if causes else "UNKNOWN"
            files = list(set(e["file"] for e in entries))
            patterns.append(PatternResult(
                account_name=name,
                original_name=name,
                frequency=len(entries),
                avg_difference=round(avg_diff, 0),
                total_difference=round(total_diff, 0),
                typical_cause=typical_cause,
                files=files,
            ))

        patterns.sort(key=lambda p: -p.frequency)
        return patterns[:top_n]

    def find_conflictive_accounts(self, top_n: int = 20) -> list[PatternResult]:
        child_groups: dict[str, list] = defaultdict(list)

        for tr, rc in zip(self.traces, self.root_causes):
            seen_names = set()
            for child in tr.children_considered:
                child_name = child.get("nombre", child.get("account_name", ""))
                if child_name and child_name not in seen_names:
                    seen_names.add(child_name)
                    child_groups[child_name].append({
                        "difference": tr.difference,
                        "cause": rc.cause,
                        "file": tr.source_file,
                        "subtotal": tr.subtotal_name,
                    })

        patterns = []
        for name, entries in child_groups.items():
            if len(entries) < 2:
                continue
            avg_diff = sum(abs(e["difference"]) for e in entries) / len(entries)
            total_diff = sum(abs(e["difference"]) for e in entries)
            causes = Counter(e["cause"] for e in entries)
            typical_cause = causes.most_common(1)[0][0] if causes else "UNKNOWN"
            files = list(set(e["file"] for e in entries))
            patterns.append(PatternResult(
                account_name=name,
                original_name=name,
                frequency=len(entries),
                avg_difference=round(avg_diff, 0),
                total_difference=round(total_diff, 0),
                typical_cause=typical_cause,
                files=files,
            ))

        patterns.sort(key=lambda p: -p.frequency)
        return patterns[:top_n]

    def find_repeated_account_causes(self, top_n: int = 20) -> list[dict]:
        account_causes: dict[str, Counter] = defaultdict(Counter)

        for tr, rc in zip(self.traces, self.root_causes):
            for child in tr.children_considered:
                child_name = child.get("nombre", child.get("account_name", ""))
                if child_name:
                    account_causes[child_name][rc.cause] += 1

        results = []
        for name, causes in account_causes.items():
            total = sum(causes.values())
            if total < 2:
                continue
            results.append({
                "account": name,
                "total_occurrences": total,
                "causes": dict(causes.most_common()),
                "dominant_cause": causes.most_common(1)[0][0],
            })

        results.sort(key=lambda x: -x["total_occurrences"])
        return results[:top_n]

    def cross_reference_gold_standard(
        self,
        account_names: list[str],
        gold_records: list[dict],
        kb_variants: list[str],
    ) -> dict:
        results = {}
        gold_names_lower = {r.get("account_name", "").lower(): r for r in gold_records}
        kb_names_lower = {v.lower(): v for v in kb_variants}

        for name in account_names:
            nl = name.lower()
            in_gs = nl in gold_names_lower or any(
                g_nl in nl or nl in g_nl for g_nl in gold_names_lower
            )
            in_kb = nl in kb_names_lower or any(
                k_nl in nl or nl in k_nl for k_nl in kb_names_lower
            )
            resolvable = in_gs or in_kb
            results[name] = {
                "in_gold_standard": in_gs,
                "in_knowledge_base": in_kb,
                "resolvable_from_existing_knowledge": resolvable,
            }
        return results

    def calculate_impact_potential(self) -> dict:
        cause_dist = self.cause_distribution()
        total = self.total_differences
        if total == 0:
            return {}

        return {
            "parser_improvement": {
                "count": cause_dist.get("PARSER_EXTRACTION", 0) + cause_dist.get("OCR_ERROR", 0),
                "pct": round((cause_dist.get("PARSER_EXTRACTION", 0) + cause_dist.get("OCR_ERROR", 0)) / total * 100, 1),
            },
            "hierarchy_improvement": {
                "count": cause_dist.get("WRONG_PARENT", 0) + cause_dist.get("WRONG_SECTION", 0) + cause_dist.get("WRONG_LEVEL", 0),
                "pct": round((cause_dist.get("WRONG_PARENT", 0) + cause_dist.get("WRONG_SECTION", 0) + cause_dist.get("WRONG_LEVEL", 0)) / total * 100, 1),
            },
            "dictionary_improvement": {
                "count": cause_dist.get("MISSING_ACCOUNT", 0),
                "pct": round(cause_dist.get("MISSING_ACCOUNT", 0) / total * 100, 1),
            },
            "knowledge_base_improvement": {
                "count": cause_dist.get("DUPLICATED_ACCOUNT", 0) + cause_dist.get("SIGN_ERROR", 0),
                "pct": round((cause_dist.get("DUPLICATED_ACCOUNT", 0) + cause_dist.get("SIGN_ERROR", 0)) / total * 100, 1),
            },
            "human_review": {
                "count": cause_dist.get("SPECIAL_BALANCE", 0) + cause_dist.get("UNKNOWN", 0),
                "pct": round((cause_dist.get("SPECIAL_BALANCE", 0) + cause_dist.get("UNKNOWN", 0)) / total * 100, 1),
            },
            "total_differences": total,
        }
