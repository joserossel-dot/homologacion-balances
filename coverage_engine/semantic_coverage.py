from __future__ import annotations

from typing import Any

from .models import (
    SemanticCoverage, CoverageIssue, CoverageSeverity,
    family_from_code, FAMILY_ORDER,
)


class SemanticCoverageCalculator:
    """Calcula cobertura semántica del documento.

    Mide:
    - Cuentas clasificadas / total
    - Cuentas conocidas (KB) / clasificadas
    - Learning hits / clasificadas
    - Unknown / total
    - Cobertura por familia (AC, ANC, PC, PNC, PAT, ER, etc.)
    """

    def compute(
        self,
        classified: list[dict[str, Any]],
        total_count: int,
        decisions: list[dict[str, Any]] | None = None,
        knowledge_data: Any = None,
    ) -> tuple[SemanticCoverage, list[CoverageIssue]]:
        issues: list[CoverageIssue] = []

        if total_count == 0:
            semantic = SemanticCoverage(overall=1.0)
            return semantic, issues

        classified_count = len(classified)
        unknown_count = total_count - classified_count

        known_count = 0
        learning_hits = 0
        kb_matches = 0
        review_workspace = 0

        for acct in classified:
            method = acct.get("method", "")
            if method.startswith("learning_"):
                known_count += 1
                learning_hits += 1
            elif method in ("cmcc", "cmcc_shadow") or acct.get("cmcc_shadow") is not None:
                known_count += 1
                kb_matches += 1
            elif "dictionary" in method:
                known_count += 1
                kb_matches += 1
            elif acct.get("final_code") or acct.get("standard_code"):
                known_count += 1
                kb_matches += 1

        by_family: dict[str, dict[str, float | int]] = {}
        accounts_by_family: dict[str, list[dict]] = {}
        for acct in classified:
            code = acct.get("final_code") or acct.get("standard_code") or ""
            family = family_from_code(code)
            if family not in accounts_by_family:
                accounts_by_family[family] = []
            accounts_by_family[family].append(acct)

        for family in FAMILY_ORDER:
            fam_accounts = accounts_by_family.get(family, [])
            fam_total = len(fam_accounts)
            fam_known = sum(
                1 for a in fam_accounts
                if (a.get("method", "") or "").startswith("learning_")
                or a.get("final_code") or a.get("standard_code")
            )
            fam_learning = sum(
                1 for a in fam_accounts
                if (a.get("method", "") or "").startswith("learning_")
            )
            fam_kb = sum(
                1 for a in fam_accounts
                if (a.get("method", "") or "") in ("cmcc", "cmcc_shadow")
                or a.get("cmcc_shadow") is not None
                or "dictionary" in (a.get("method", "") or "")
            )
            fam_unknown = sum(
                1 for a in fam_accounts
                if not (a.get("final_code") or a.get("standard_code"))
            )

            if fam_total > 0:
                cov = fam_known / fam_total
            else:
                cov = 1.0

            by_family[family] = {
                "total": fam_total,
                "classified": fam_total,
                "known": fam_known,
                "learning_hits": fam_learning,
                "kb_matches": fam_kb,
                "unknown": fam_unknown,
                "coverage_pct": round(cov, 4),
            }

        if decisions:
            for d in decisions:
                dt = d.get("decision_type", "")
                if dt in ("MANUAL_REVIEW", "REJECT"):
                    pass
                elif dt == "LEARNING":
                    review_workspace += 1

        overall = classified_count / total_count if total_count > 0 else 0.0

        if unknown_count > 0:
            issues.append(CoverageIssue(
                issue_type="uncategorized_account",
                severity=CoverageSeverity.CRITICAL,
                monetary_impact=0.0,
                document_impact=round(unknown_count / total_count, 4),
                detail=f"{unknown_count} cuentas sin clasificar de {total_count} totales",
                family="",
            ))

        if learning_hits == 0 and classified_count > 0:
            issues.append(CoverageIssue(
                issue_type="insufficient_learning",
                severity=CoverageSeverity.MEDIUM,
                monetary_impact=0.0,
                document_impact=round(1.0 - overall, 4),
                detail="Sin learning hits",
                family="",
            ))

        semantic = SemanticCoverage(
            total_accounts=total_count,
            classified_count=classified_count,
            known_count=known_count,
            learning_hits=learning_hits,
            kb_matches=kb_matches,
            review_workspace=review_workspace,
            unknown_count=unknown_count,
            by_family=by_family,
            overall=overall,
        )

        return semantic, issues

    def compute_from_ctx(
        self,
        classified: list[dict[str, Any]],
        decisions: list[dict[str, Any]] | None = None,
        knowledge_data: Any = None,
        ignored: list[dict[str, Any]] | None = None,
    ) -> tuple[SemanticCoverage, list[CoverageIssue]]:
        total_count = len(classified)
        if ignored:
            total_count += len(ignored)
        return self.compute(classified, total_count, decisions, knowledge_data)
