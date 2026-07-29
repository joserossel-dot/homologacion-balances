from __future__ import annotations

import statistics
from typing import Any

from .models import CoverageResult, CoverageStatistics, FAMILY_ORDER


class CoverageStatisticsCollector:
    """Genera estadísticas de cobertura a partir de múltiples CoverageResult.

    Calcula:
    - Promedios (overall, monetary, structural, semantic, document)
    - Percentiles (p25, p50, p75)
    - Distribución (rangos de cobertura)
    - Coverage por familia
    - Coverage por template
    - Coverage por parser
    - Coverage por compañía
    - Coverage por año
    """

    def __init__(self):
        self._results: list[CoverageResult] = []
        self._metadata: list[dict[str, Any]] = []

    def add(
        self,
        result: CoverageResult,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._results.append(result)
        self._metadata.append(metadata or {})

    def add_many(
        self,
        results: list[CoverageResult],
        metadata_list: list[dict[str, Any]] | None = None,
    ) -> None:
        for i, r in enumerate(results):
            meta = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
            self.add(r, meta)

    def compute(self) -> CoverageStatistics:
        if not self._results:
            return CoverageStatistics()

        scores = [r.overall for r in self._results]
        monetary_scores = [r.monetary.coverage_pct for r in self._results]
        structural_scores = [r.structural.overall for r in self._results]
        semantic_scores = [r.semantic.overall for r in self._results]
        document_scores = [r.document.coverage_pct for r in self._results]

        sorted_scores = sorted(scores)
        n = len(sorted_scores)

        overall_avg = sum(scores) / n
        overall_median = self._median(sorted_scores)
        overall_p25 = sorted_scores[max(0, int(n * 0.25))]
        overall_p75 = sorted_scores[min(n - 1, int(n * 0.75))]

        monetary_avg = sum(monetary_scores) / n
        structural_avg = sum(structural_scores) / n
        semantic_avg = sum(semantic_scores) / n
        document_avg = sum(document_scores) / n

        distribution = self._compute_distribution(scores)

        by_family = self._aggregate_by_family()
        by_template = self._aggregate_by_key("template")
        by_parser = self._aggregate_by_key("parser")
        by_company = self._aggregate_by_key("company")
        by_year = self._aggregate_by_key("year")

        return CoverageStatistics(
            total_documents=n,
            overall_avg=overall_avg,
            overall_median=overall_median,
            overall_p25=overall_p25,
            overall_p75=overall_p75,
            monetary_avg=monetary_avg,
            structural_avg=structural_avg,
            semantic_avg=semantic_avg,
            document_avg=document_avg,
            by_family=by_family,
            by_template=by_template,
            by_parser=by_parser,
            by_company=by_company,
            by_year=by_year,
            distribution=distribution,
            all_scores=scores,
        )

    def _median(self, sorted_scores: list[float]) -> float:
        n = len(sorted_scores)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return sorted_scores[n // 2]
        return (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0

    def _compute_distribution(
        self, scores: list[float],
    ) -> dict[str, int]:
        dist: dict[str, int] = {
            "0-10%": 0, "10-20%": 0, "20-30%": 0,
            "30-40%": 0, "40-50%": 0, "50-60%": 0,
            "60-70%": 0, "70-80%": 0, "80-90%": 0,
            "90-100%": 0,
        }
        for score in scores:
            pct = int(score * 100)
            if pct < 10:
                dist["0-10%"] += 1
            elif pct < 20:
                dist["10-20%"] += 1
            elif pct < 30:
                dist["20-30%"] += 1
            elif pct < 40:
                dist["30-40%"] += 1
            elif pct < 50:
                dist["40-50%"] += 1
            elif pct < 60:
                dist["50-60%"] += 1
            elif pct < 70:
                dist["60-70%"] += 1
            elif pct < 80:
                dist["70-80%"] += 1
            elif pct < 90:
                dist["80-90%"] += 1
            else:
                dist["90-100%"] += 1
        return dist

    def _aggregate_by_family(self) -> dict[str, dict[str, float]]:
        family_scores: dict[str, list[float]] = {}
        for result in self._results:
            for family, data in result.monetary.by_family.items():
                cov = data.get("coverage_pct", 0.0)
                if family not in family_scores:
                    family_scores[family] = []
                family_scores[family].append(cov)
        result: dict[str, dict[str, float]] = {}
        for family, scores in family_scores.items():
            result[family] = {
                "avg": round(sum(scores) / len(scores), 4),
                "count": len(scores),
            }
        return result

    def _aggregate_by_key(self, key: str) -> dict[str, dict[str, float]]:
        groups: dict[str, list[float]] = {}
        for i, result in enumerate(self._results):
            meta = self._metadata[i] if i < len(self._metadata) else {}
            group_key = str(meta.get(key, "unknown"))
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(result.overall)
        result: dict[str, dict[str, float]] = {}
        for gk, scores in groups.items():
            result[gk] = {
                "avg": round(sum(scores) / len(scores), 4),
                "count": len(scores),
            }
        return result

    def clear(self) -> None:
        self._results.clear()
        self._metadata.clear()

    @property
    def count(self) -> int:
        return len(self._results)

    @property
    def results(self) -> list[CoverageResult]:
        return list(self._results)
