from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class SubtotalTrace:
    source_file: str = ""
    subtotal_name: str = ""
    subtotal_line: int = 0
    expected: float = 0.0
    actual: float = 0.0
    difference: float = 0.0
    pct_diff: float = 0.0
    children_considered: list[dict] = field(default_factory=list)
    children_found: list[dict] = field(default_factory=list)
    excluded_accounts: list[dict] = field(default_factory=list)
    nearby_accounts: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)


@dataclass
class HierarchyComparison:
    account_name: str = ""
    account_code: str = ""
    amount: float = 0.0
    exists: bool = False
    under_correct_parent: Optional[bool] = None
    in_other_section: bool = False
    in_other_subtotal: bool = False
    correct_level: Optional[bool] = None
    found_section: str = ""
    expected_section: str = ""
    found_parent: str = ""
    expected_parent: str = ""


@dataclass
class RootCauseResult:
    cause: str = ""
    certainty: float = 0.0
    evidence: list[str] = field(default_factory=list)
    candidate_account: str = ""
    trace: Optional[SubtotalTrace] = None


@dataclass
class PatternResult:
    account_name: str = ""
    original_name: str = ""
    frequency: int = 0
    avg_difference: float = 0.0
    total_difference: float = 0.0
    typical_cause: str = ""
    files: list[str] = field(default_factory=list)


@dataclass
class FormatMatrix:
    format_name: str = ""
    total_differences: int = 0
    by_cause: dict[str, int] = field(default_factory=dict)
    by_file: list[str] = field(default_factory=list)


class SubtotalTracer:

    @staticmethod
    def build_trace(
        source_file: str,
        subtotal_name: str,
        subtotal_line: int,
        expected: float,
        actual: float,
        difference: float,
        pct_diff: float,
        children: list[dict],
        all_accounts: list[dict],
        tolerance_pct: float = 1.0,
    ) -> SubtotalTrace:
        trace = SubtotalTrace(
            source_file=source_file,
            subtotal_name=subtotal_name,
            subtotal_line=subtotal_line,
            expected=expected,
            actual=actual,
            difference=difference,
            pct_diff=pct_diff,
        )

        trace.children_considered = children

        found = []
        excluded = []
        for child in children:
            amt = child.get("amount", 0) or 0
            if amt == 0 and not child.get("es_total", False):
                excluded.append(child)
            else:
                found.append(child)

        trace.children_found = found
        trace.excluded_accounts = excluded

        trace.nearby_accounts = SubtotalTracer._find_nearby_accounts(
            subtotal_line, all_accounts, window=10
        )

        trace.candidates = SubtotalTracer._find_candidates(
            difference, all_accounts, subtotal_line, tolerance_pct
        )

        return trace

    @staticmethod
    def _find_nearby_accounts(
        line_number: int,
        all_accounts: list[dict],
        window: int = 10,
    ) -> list[dict]:
        nearby = []
        for acct in all_accounts:
            ln = acct.get("linea", acct.get("source_line", -1))
            if isinstance(ln, str):
                try:
                    ln = int(ln)
                except (ValueError, TypeError):
                    ln = -1
            if ln < 0:
                continue
            if abs(ln - line_number) <= window:
                nearby.append(acct)
        return nearby

    @staticmethod
    def _find_candidates(
        difference: float,
        all_accounts: list[dict],
        subtotal_line: int,
        tolerance_pct: float = 1.0,
    ) -> list[dict]:
        candidates = []
        target = abs(difference)

        for acct in all_accounts:
            ln = acct.get("linea", acct.get("source_line", -1))
            if isinstance(ln, str):
                try:
                    ln = int(ln)
                except (ValueError, TypeError):
                    ln = -1
            if ln == subtotal_line:
                continue

            amt = acct.get("amount", acct.get("monto", 0)) or 0
            if isinstance(amt, str):
                try:
                    amt = float(amt.replace(".", "").replace(",", "."))
                except (ValueError, TypeError):
                    amt = 0.0
            amt = float(amt)
            if amt == 0:
                continue

            name = acct.get("nombre", acct.get("account_name", ""))
            code = acct.get("codigo", acct.get("account_code", ""))

            if abs(amt - target) <= max(0.01, target * 0.0001):
                candidates.append({
                    "account_name": name,
                    "account_code": code,
                    "amount": amt,
                    "line": ln,
                    "match_type": "exact",
                    "similarity": 100.0,
                })

        for acct in all_accounts:
            ln = acct.get("linea", acct.get("source_line", -1))
            if isinstance(ln, str):
                try:
                    ln = int(ln)
                except (ValueError, TypeError):
                    ln = -1
            if ln == subtotal_line:
                continue

            amt = acct.get("amount", acct.get("monto", 0)) or 0
            if isinstance(amt, str):
                try:
                    amt = float(amt.replace(".", "").replace(",", "."))
                except (ValueError, TypeError):
                    amt = 0.0
            amt = float(amt)
            if amt == 0:
                continue

            name = acct.get("nombre", acct.get("account_name", ""))
            code = acct.get("codigo", acct.get("account_code", ""))

            if target > 0:
                ratio = min(amt, target) / max(amt, target) * 100
                if 100 - tolerance_pct <= ratio <= 100 + tolerance_pct:
                    candidates.append({
                        "account_name": name,
                        "account_code": code,
                        "amount": amt,
                        "line": ln,
                        "match_type": "similar",
                        "similarity": round(ratio, 1),
                    })

        for acct in all_accounts:
            ln = acct.get("linea", acct.get("source_line", -1))
            if isinstance(ln, str):
                try:
                    ln = int(ln)
                except (ValueError, TypeError):
                    ln = -1
            if ln == subtotal_line:
                continue

            amt = acct.get("amount", acct.get("monto", 0)) or 0
            if isinstance(amt, str):
                try:
                    amt = float(amt.replace(".", "").replace(",", "."))
                except (ValueError, TypeError):
                    amt = 0.0
            amt = float(amt)
            if amt == 0:
                continue

            name = acct.get("nombre", acct.get("account_name", ""))
            code = acct.get("codigo", acct.get("account_code", ""))

            if abs(amt + target) <= max(0.01, target * 0.0001):
                candidates.append({
                    "account_name": name,
                    "account_code": code,
                    "amount": amt,
                    "line": ln,
                    "match_type": "sign_flip",
                    "similarity": 100.0,
                })

            if abs(abs(amt) - target) <= max(0.01, target * 0.0001) and amt < 0:
                candidates.append({
                    "account_name": name,
                    "account_code": code,
                    "amount": amt,
                    "line": ln,
                    "match_type": "negative_exact",
                    "similarity": 100.0,
                })

        seen = set()
        unique = []
        for c in candidates:
            key = (c["line"], round(c["amount"], 2))
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique[:15]
