from __future__ import annotations

from typing import Any

from .models import QAIssue


SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
    "INFO": 4,
}


class IssueAnalyzer:
    """Consolida issues de todos los motores en una lista única.

    Fuentes:
    - Coverage Engine (coverage issues)
    - Validation Engine (errores/advertencias)
    - Decision Engine (conflictos)
    - Parser (ignored accounts)
    - Knowledge Base (falta de matches)

    Deduplica por (source, issue_type, detail) y ordena por severidad.
    """

    def consolidate(
        self,
        coverage_issues: list[dict[str, Any]] | None = None,
        validation_data: Any = None,
        decision_stats: dict[str, Any] | None = None,
        parser_data: Any = None,
        knowledge_data: Any = None,
        decisions: list[dict[str, Any]] | None = None,
    ) -> list[QAIssue]:
        all_issues: list[QAIssue] = []

        all_issues.extend(self._from_coverage(coverage_issues))
        all_issues.extend(self._from_validation(validation_data))
        all_issues.extend(self._from_decision(decision_stats, decisions))
        all_issues.extend(self._from_parser(parser_data))
        all_issues.extend(self._from_knowledge(knowledge_data))

        return self._deduplicate(all_issues)

    def _from_coverage(
        self, issues: list[dict[str, Any]] | None,
    ) -> list[QAIssue]:
        result: list[QAIssue] = []
        if not issues:
            return result
        for iss in issues:
            result.append(QAIssue(
                source="coverage",
                issue_type=iss.get("issue_type", "unknown"),
                severity=iss.get("severity", "INFO"),
                detail=iss.get("detail", ""),
                impact=float(iss.get("monetary_impact", 0.0) or 0.0),
            ))
        return result

    def _from_validation(
        self, validation_data: Any = None,
    ) -> list[QAIssue]:
        result: list[QAIssue] = []
        if validation_data is None:
            return result
        errors = getattr(validation_data, "errors", []) or []
        warnings = getattr(validation_data, "warnings", []) or []
        for err in errors:
            result.append(QAIssue(
                source="validation",
                issue_type="validation_error",
                severity="CRITICAL",
                detail=str(err),
                impact=0.0,
            ))
        for warn in warnings:
            result.append(QAIssue(
                source="validation",
                issue_type="validation_warning",
                severity="MEDIUM",
                detail=str(warn),
                impact=0.0,
            ))
        return result

    def _from_decision(
        self,
        stats: dict[str, Any] | None = None,
        decisions: list[dict[str, Any]] | None = None,
    ) -> list[QAIssue]:
        result: list[QAIssue] = []
        if stats:
            conflicts = stats.get("conflicts_detected", 0) or 0
            if conflicts > 0:
                result.append(QAIssue(
                    source="decision",
                    issue_type="decision_conflicts",
                    severity="HIGH",
                    detail=f"{conflicts} conflictos detectados en decisiones",
                    impact=0.0,
                ))
            by_type = stats.get("decisions_by_type", {}) or {}
            manual = by_type.get("MANUAL_REVIEW", 0) or 0
            if manual > 0:
                result.append(QAIssue(
                    source="decision",
                    issue_type="manual_review_required",
                    severity="MEDIUM",
                    detail=f"{manual} cuentas requieren revisión manual",
                    impact=0.0,
                ))
        if decisions:
            rejected = sum(
                1 for d in decisions
                if d.get("decision_type") == "REJECT"
            )
            if rejected > 0:
                result.append(QAIssue(
                    source="decision",
                    issue_type="rejected_accounts",
                    severity="CRITICAL",
                    detail=f"{rejected} cuentas rechazadas",
                    impact=0.0,
                ))
        return result

    def _from_parser(
        self, parser_data: Any = None,
    ) -> list[QAIssue]:
        result: list[QAIssue] = []
        if parser_data is None:
            return result
        ignored = getattr(parser_data, "total_ignored", 0) or 0
        if ignored > 0:
            result.append(QAIssue(
                source="parser",
                issue_type="ignored_accounts",
                severity="LOW",
                detail=f"{ignored} cuentas ignoradas por el parser",
                impact=0.0,
            ))
        selected = getattr(parser_data, "selected_parser", "") or ""
        if not selected:
            result.append(QAIssue(
                source="parser",
                issue_type="no_parser_selected",
                severity="CRITICAL",
                detail="No se seleccionó ningún parser",
                impact=0.0,
            ))
        return result

    def _from_knowledge(
        self, knowledge_data: Any = None,
    ) -> list[QAIssue]:
        result: list[QAIssue] = []
        if knowledge_data is None:
            return result
        cmcc = len(getattr(knowledge_data, "cmcc_matches", []) or [])
        learning = len(getattr(knowledge_data, "learning_hits", []) or [])
        dictionary = len(getattr(knowledge_data, "dictionary_matches", []) or [])
        total = cmcc + learning + dictionary
        if total == 0:
            result.append(QAIssue(
                source="knowledge",
                issue_type="no_kb_matches",
                severity="HIGH",
                detail="Sin matches en Knowledge Base",
                impact=0.0,
            ))
        return result

    def _deduplicate(self, issues: list[QAIssue]) -> list[QAIssue]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[QAIssue] = []
        for issue in issues:
            key = (issue.source, issue.issue_type, issue.detail)
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        unique.sort(
            key=lambda x: SEVERITY_ORDER.get(x.severity, 99),
        )
        return unique
