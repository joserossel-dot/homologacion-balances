from __future__ import annotations
from collections import Counter
from knowledge.repository import Repository
from knowledge.concept import Concept


class Metrics:
    def __init__(self, repository: Repository):
        self.repository = repository

    @property
    def concept_count(self) -> int:
        return self.repository.count()

    @property
    def total_variants(self) -> int:
        return sum(len(c.variantes) for c in self.repository.list_all())

    @property
    def average_variants(self) -> float:
        n = self.concept_count
        return round(self.total_variants / n, 2) if n > 0 else 0.0

    @property
    def total_synonyms(self) -> int:
        return sum(len(c.sinonimos) for c in self.repository.list_all())

    @property
    def total_abbreviations(self) -> int:
        return sum(len(c.abreviaturas) for c in self.repository.list_all())

    @property
    def total_examples(self) -> int:
        return sum(len(c.ejemplos) for c in self.repository.list_all())

    @property
    def top_concepts(self) -> list[tuple[str, float]]:
        scored = [(c.nombre, c.coverage_score) for c in self.repository.list_all()]
        scored.sort(key=lambda x: -x[1])
        return scored[:10]

    @property
    def confidence_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {"alta (>0.8)": 0, "media (0.5-0.8)": 0,
                                "baja (<0.5)": 0, "sin_confianza": 0}
        for c in self.repository.list_all():
            if c.confidence >= 0.8:
                dist["alta (>0.8)"] += 1
            elif c.confidence >= 0.5:
                dist["media (0.5-0.8)"] += 1
            elif c.confidence > 0:
                dist["baja (<0.5)"] += 1
            else:
                dist["sin_confianza"] += 1
        return dist

    @property
    def category_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for c in self.repository.list_all():
            cat = c.categoria or "sin_categoria"
            dist[cat] = dist.get(cat, 0) + 1
        return dist

    @property
    def financial_statement_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for c in self.repository.list_all():
            fs = c.tipo_estado_financiero or "sin_estado"
            dist[fs] = dist.get(fs, 0) + 1
        return dist

    @property
    def coverage_potential(self) -> dict[str, int]:
        total_accounts = 0
        matched_accounts = 0
        for c in self.repository.list_all():
            total_accounts += 1
            if c.variantes or c.sinonimos or c.abreviaturas:
                matched_accounts += 1
        return {
            "con_cobertura": matched_accounts,
            "sin_cobertura": total_accounts - matched_accounts,
            "total": total_accounts,
            "porcentaje": round(matched_accounts / total_accounts * 100, 1) if total_accounts else 0.0,
        }

    def report(self) -> dict:
        return {
            "cantidad_conceptos": self.concept_count,
            "cantidad_variantes": self.total_variants,
            "promedio_variantes": self.average_variants,
            "cantidad_sinonimos": self.total_synonyms,
            "cantidad_abreviaturas": self.total_abbreviations,
            "cantidad_ejemplos": self.total_examples,
            "top_conceptos": self.top_concepts,
            "distribucion_confianza": self.confidence_distribution,
            "distribucion_categoria": self.category_distribution,
            "distribucion_estado_financiero": self.financial_statement_distribution,
            "cobertura_potencial": self.coverage_potential,
        }
