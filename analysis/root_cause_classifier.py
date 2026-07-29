from __future__ import annotations
from .subtotal_trace import SubtotalTrace, RootCauseResult
from .hierarchy_comparator import HierarchyComparator


VALID_CAUSES = [
    "MISSING_ACCOUNT",
    "WRONG_PARENT",
    "WRONG_SECTION",
    "WRONG_LEVEL",
    "DUPLICATED_ACCOUNT",
    "SIGN_ERROR",
    "OCR_ERROR",
    "PARSER_EXTRACTION",
    "SPECIAL_BALANCE",
    "UNKNOWN",
]


class RootCauseClassifier:

    def __init__(self):
        self.comparator = HierarchyComparator()

    @staticmethod
    def is_special_balance(name: str) -> bool:
        n = name.lower().replace("_", " ").replace("-", " ")
        if any(w in n for w in [
            "nota", "anexo", "cpt ", "cpt_", "informe tasa", "inventario",
            "detalle", "conciliacion", "formulario", "sii", "tributario",
        ]):
            return True
        if any(w in n.split() for w in [
            "cpt", "cpt_",
        ]):
            return True
        return False

    def classify(
        self,
        trace: SubtotalTrace,
        all_accounts: list[dict],
        subtotal_results: list,
    ) -> RootCauseResult:
        result = RootCauseResult(trace=trace)

        if self.is_special_balance(trace.subtotal_name):
            result.cause = "SPECIAL_BALANCE"
            result.certainty = 0.7
            result.evidence.append(f"Subtotal name suggests special format: {trace.subtotal_name}")
            return result

        candidates = trace.candidates
        diff = trace.difference
        children_found = trace.children_found

        if not children_found:
            if candidates:
                best = candidates[0]
                mt = best["match_type"]
                if mt == "exact":
                    result.cause = "WRONG_PARENT"
                    result.certainty = 0.85
                    result.candidate_account = best["account_name"]
                    result.evidence.append(
                        f"Exact match for difference ({diff:.0f}) found in "
                        f"'{best['account_name']}' at line {best['line']} — "
                        f"account exists under wrong parent"
                    )
                    return result
                elif mt == "sign_flip":
                    result.cause = "SIGN_ERROR"
                    result.certainty = 0.80
                    result.candidate_account = best["account_name"]
                    result.evidence.append(
                        f"Sign-flip match: negative '{best['account_name']}' "
                        f"({best['amount']:.0f}) accounts for difference ({diff:.0f})"
                    )
                    return result
                elif mt == "similar":
                    result.cause = "WRONG_PARENT"
                    result.certainty = 0.65
                    result.candidate_account = best["account_name"]
                    result.evidence.append(
                        f"Similar amount ({best['similarity']:.0f}%) matches "
                        f"'{best['account_name']}' — likely under wrong subtotal"
                    )
                    return result
                elif mt == "negative_exact":
                    result.cause = "SIGN_ERROR"
                    result.certainty = 0.75
                    result.candidate_account = best["account_name"]
                    result.evidence.append(
                        f"Negative exact match: '{best['account_name']}' "
                        f"({best['amount']:.0f}) = -(diff)"
                    )
                    return result

        if children_found:
            expected_parent = trace.subtotal_name.lower()
            for child in children_found:
                child_name = child.get("nombre", child.get("account_name", ""))
                child_line = child.get("linea", child.get("source_line", -1))

                duplicates = self.comparator.find_duplicates(child_name, all_accounts)
                if len(duplicates) > 1:
                    result.cause = "DUPLICATED_ACCOUNT"
                    result.certainty = 0.75
                    result.candidate_account = child_name
                    result.evidence.append(
                        f"'{child_name}' appears {len(duplicates)} times "
                        f"(e.g. lines {[d['line'] for d in duplicates[:3]]})"
                    )
                    return result

                hc = self.comparator.compare(child_name, child["amount"], child_line, all_accounts, subtotal_results)
                if hc.in_other_section:
                    result.cause = "WRONG_SECTION"
                    result.certainty = 0.80
                    result.candidate_account = child_name
                    result.evidence.append(
                        f"'{child_name}' found in section '{hc.found_section}' "
                        f"but expected in '{hc.expected_section}'"
                    )
                    return result
                if hc.in_other_subtotal:
                    result.cause = "WRONG_PARENT"
                    result.certainty = 0.60
                    result.candidate_account = child_name
                    result.evidence.append(
                        f"'{child_name}' appears under wrong subtotal"
                    )
                    return result

            sum_found = sum(c.get("amount", 0) for c in children_found)
            sum_all = sum(c.get("amount", 0) for c in trace.children_considered)
            if abs(sum_found - sum_all) > 0.01 and sum_all > 0:
                excluded_total = sum_all - sum_found
                if abs(excluded_total - abs(diff)) <= max(1, abs(diff) * 0.01):
                    result.cause = "MISSING_ACCOUNT"
                    result.certainty = 0.70
                    result.evidence.append(
                        f"Excluded accounts sum ({excluded_total:.0f}) matches "
                        f"difference ({abs(diff):.0f}) — {len(trace.excluded_accounts)} "
                        f"accounts with amount=0 excluded"
                    )
                    return result

        if abs(diff) > 0 and len(children_found) > 0 and candidates:
            pass

        if hasattr(trace, "pct_diff") and trace.pct_diff < 5 and abs(diff) > 0:
            result.cause = "PARSER_EXTRACTION"
            result.certainty = 0.50
            result.evidence.append(
                f"Small difference ({trace.pct_diff:.1f}%) suggests parser extraction "
                f"precision issue (parsing formatting diff)"
            )
            return result

        result.cause = "UNKNOWN"
        result.certainty = 0.30
        result.evidence.append(
            f"No clear pattern detected for difference {diff:.0f} ({trace.pct_diff:.1f}%) "
            f"in '{trace.subtotal_name}'"
        )
        return result
