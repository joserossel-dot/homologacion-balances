from __future__ import annotations

from typing import Any

from .models import QAResult, QASummary, RiskLevel, ApprovalState, risk_level_from_score


class QAStatisticsCollector:
    """Genera estadísticas de Self QA a partir de múltiples QAResult.

    Calcula:
    - Cantidad por estado (approved, review, reject, learning, stress, failed)
    - Promedio de confianza
    - Promedio de riesgo
    - Distribución por parser, template, empresa, familia, año
    """

    def __init__(self):
        self._results: list[QAResult] = []
        self._metadata: list[dict[str, Any]] = []

    def add(
        self,
        result: QAResult,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._results.append(result)
        self._metadata.append(metadata or {})

    def add_many(
        self,
        results: list[QAResult],
        metadata_list: list[dict[str, Any]] | None = None,
    ) -> None:
        for i, r in enumerate(results):
            meta = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
            self.add(r, meta)

    def compute(self) -> QASummary:
        if not self._results:
            return QASummary()

        n = len(self._results)
        approved = 0
        approved_warn = 0
        manual_review = 0
        learning = 0
        stress = 0
        rejected = 0
        failed = 0

        total_conf = 0.0
        total_risk = 0.0

        for r in self._results:
            state = r.approval_state
            if state == ApprovalState.APPROVED:
                approved += 1
            elif state == ApprovalState.APPROVED_WITH_WARNINGS:
                approved_warn += 1
            elif state == ApprovalState.MANUAL_REVIEW:
                manual_review += 1
            elif state == ApprovalState.LEARNING:
                learning += 1
            elif state == ApprovalState.STRESS:
                stress += 1
            elif state == ApprovalState.REJECTED:
                rejected += 1
            elif state == ApprovalState.FAILED:
                failed += 1

            total_conf += r.confidence.overall
            total_risk += r.risk.total_risk

        avg_confidence = total_conf / n
        avg_risk = total_risk / n

        distribution = {
            "APPROVED": approved,
            "APPROVED_WITH_WARNINGS": approved_warn,
            "MANUAL_REVIEW": manual_review,
            "LEARNING": learning,
            "STRESS": stress,
            "REJECTED": rejected,
            "FAILED": failed,
        }

        by_template = self._aggregate_by_key("template")
        by_parser = self._aggregate_by_key("parser")
        by_company = self._aggregate_by_key("company")
        by_family = self._aggregate_by_key("family")
        by_year = self._aggregate_by_key("year")

        return QASummary(
            total_documents=n,
            approved=approved,
            approved_with_warnings=approved_warn,
            manual_review=manual_review,
            learning=learning,
            stress=stress,
            rejected=rejected,
            failed=failed,
            avg_confidence=round(avg_confidence, 4),
            avg_risk=round(avg_risk, 2),
            avg_risk_level=risk_level_from_score(avg_risk),
            by_template=by_template,
            by_parser=by_parser,
            by_company=by_company,
            by_family=by_family,
            by_year=by_year,
            distribution=distribution,
        )

    def _aggregate_by_key(self, key: str) -> dict[str, dict[str, float]]:
        groups: dict[str, list[float]] = {}
        for i, result in enumerate(self._results):
            meta = self._metadata[i] if i < len(self._metadata) else {}
            group_key = str(meta.get(key, "unknown"))
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(result.confidence.overall)
        result_dict: dict[str, dict[str, float]] = {}
        for gk, scores in groups.items():
            result_dict[gk] = {
                "avg_confidence": round(sum(scores) / len(scores), 4),
                "count": len(scores),
            }
        return result_dict

    def clear(self) -> None:
        self._results.clear()
        self._metadata.clear()

    @property
    def count(self) -> int:
        return len(self._results)

    @property
    def results(self) -> list[QAResult]:
        return list(self._results)
