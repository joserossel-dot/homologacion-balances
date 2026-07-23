from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter

from knowledge.normalizer import Normalizer
from split_ac01.split_rules import (
    CAJA_DIRECT_PATTERN, CAJA_NEGATE_PATTERN,
    EFECTIVO_PATTERN, FONDO_FIJO_PATTERN, MONEDA_PATTERN,
    BILLETE_PATTERN, DIVISA_PATTERN, DINERO_PATTERN, ARQUEO_PATTERN,
    CTA_PATTERN, CHEQUE_PATTERN, SOBREGIRO_PATTERN, LINEA_CREDITO_PATTERN,
    BANK_TOKEN_MAP, BANCO_NEGATE_PATTERN,
    FONDO_MUTUO_PATTERN, INVERSION_PATTERN, VALOR_NEGOCIABLE_PATTERN,
    CORTO_PLAZO_PATTERN, DEPOSITO_PLAZO_PATTERN,
    ACCIONES_PATTERN, BONOS_PATTERN,
    has_any_token,
)

CONCEPT_LABELS = {
    "AC.01.01": "Caja",
    "AC.01.02": "Bancos",
    "AC.01.03": "Equivalentes",
}


@dataclass
class ClassificationResult:
    variant: str
    normalized: str
    original_concept: str = "AC.01"
    target_code: str | None = None
    target_name: str | None = None
    confidence: float = 0.0
    matched_rules: list[str] = field(default_factory=list)
    needs_review: bool = True


class AC01SplitEngine:
    def __init__(self, normalizer: Normalizer | None = None):
        self.normalizer = normalizer or Normalizer()

    def classify_variant(self, variant: str) -> ClassificationResult:
        normalized = self.normalizer.normalize(variant).text
        result = ClassificationResult(
            variant=variant,
            normalized=normalized,
        )

        scores: dict[str, float] = {}
        matched_rules: dict[str, list[str]] = {}

        self._test_equivalentes(normalized, scores, matched_rules)
        self._test_bancos(normalized, scores, matched_rules)
        self._test_caja(normalized, scores, matched_rules)

        if not scores:
            return result

        result.matched_rules = []
        for code, rules in matched_rules.items():
            result.matched_rules.extend(rules)

        best_code = max(scores, key=lambda k: (scores[k], k))
        best_score = scores[best_code]

        second_best = -1
        for code, score in scores.items():
            if code != best_code and score > second_best:
                second_best = score

        result.target_code = best_code
        result.target_name = CONCEPT_LABELS.get(best_code, best_code)

        total_score = sum(scores.values())
        result.confidence = round(best_score / total_score, 4) if total_score > 0 else 0.0

        if best_score == second_best:
            result.needs_review = True
        elif result.confidence < 0.5:
            result.needs_review = True
        else:
            result.needs_review = False

        return result

    def _test_caja(
        self,
        text: str,
        scores: dict[str, float],
        matched_rules: dict[str, list[str]],
    ) -> None:
        score = 0.0
        rules: list[str] = []

        if CAJA_NEGATE_PATTERN.search(text):
            return

        if CAJA_DIRECT_PATTERN.search(text):
            score += 1.0
            rules.append("caja_direct")

        for pattern, name in [
            (EFECTIVO_PATTERN, "efectivo"),
            (FONDO_FIJO_PATTERN, "fondo_fijo"),
            (MONEDA_PATTERN, "moneda"),
            (ARQUEO_PATTERN, "arqueo"),
            (DINERO_PATTERN, "dinero"),
            (DIVISA_PATTERN, "divisa"),
            (BILLETE_PATTERN, "billete"),
        ]:
            if pattern.search(text):
                score += 0.8
                rules.append(name)

        if score > 0:
            scores["AC.01.01"] = round(score, 2)
            matched_rules["AC.01.01"] = rules

    def _test_bancos(
        self,
        text: str,
        scores: dict[str, float],
        matched_rules: dict[str, list[str]],
    ) -> None:
        score = 0.0
        rules: list[str] = []

        if BANCO_NEGATE_PATTERN.search(text):
            non_negated_tokens = has_any_token(
                text, BANK_TOKEN_MAP.get("ac01_02", set())
            )
            if not non_negated_tokens:
                return

        if CTA_PATTERN.search(text):
            score += 1.0
            rules.append("cta_corriente")

        if CHEQUE_PATTERN.search(text):
            score += 0.8
            rules.append("cheque")

        if SOBREGIRO_PATTERN.search(text):
            score += 0.8
            rules.append("sobregiro")

        if LINEA_CREDITO_PATTERN.search(text):
            score += 0.8
            rules.append("linea_credito")

        matched = has_any_token(text, BANK_TOKEN_MAP.get("ac01_02", set()))
        if matched:
            score += 0.8 * len(matched)
            rules.append(f"bank_name:{','.join(sorted(matched))}")

        if score > 0:
            scores["AC.01.02"] = round(score, 2)
            matched_rules["AC.01.02"] = rules

    def _test_equivalentes(
        self,
        text: str,
        scores: dict[str, float],
        matched_rules: dict[str, list[str]],
    ) -> None:
        score = 0.0
        rules: list[str] = []

        for pattern, name, weight in [
            (FONDO_MUTUO_PATTERN, "fondo_mutuo", 1.0),
            (DEPOSITO_PLAZO_PATTERN, "deposito_plazo", 1.0),
            (VALOR_NEGOCIABLE_PATTERN, "valor_negociable", 1.0),
            (CORTO_PLAZO_PATTERN, "corto_plazo", 0.8),
            (ACCIONES_PATTERN, "acciones", 0.8),
            (BONOS_PATTERN, "bonos", 0.8),
            (INVERSION_PATTERN, "inversion", 0.7),
        ]:
            if pattern.search(text):
                score += weight
                rules.append(name)

        if score > 0:
            scores["AC.01.03"] = round(score, 2)
            matched_rules["AC.01.03"] = rules

    def classify_all(self, variants: list[str]) -> list[ClassificationResult]:
        return [self.classify_variant(v) for v in variants]

    def compute_statistics(
        self, results: list[ClassificationResult]
    ) -> dict:
        total = len(results)
        by_concept: Counter[str] = Counter()
        confidence_buckets = {"0.0-0.49": 0, "0.5-0.79": 0, "0.8-1.0": 0}
        matched_rule_counts: Counter[str] = Counter()
        needs_review = 0

        for r in results:
            code = r.target_code or "UNCLASSIFIED"
            by_concept[code] += 1

            if r.needs_review:
                needs_review += 1

            if r.confidence < 0.5:
                confidence_buckets["0.0-0.49"] += 1
            elif r.confidence < 0.8:
                confidence_buckets["0.5-0.79"] += 1
            else:
                confidence_buckets["0.8-1.0"] += 1

            for rule in r.matched_rules:
                matched_rule_counts[rule] += 1

        auto_classified = total - needs_review

        return {
            "total_variants": total,
            "by_concept": dict(by_concept),
            "needs_review": needs_review,
            "auto_classified": auto_classified,
            "auto_classification_rate": (
                round(auto_classified / total * 100, 2)
                if total > 0 else 0.0
            ),
            "confidence_buckets": confidence_buckets,
            "matched_rules": dict(matched_rule_counts.most_common(20)),
        }

    def compute_coverage(
        self, results: list[ClassificationResult]
    ) -> dict:
        total = len(results)
        auto = [r for r in results if not r.needs_review]
        manual = [r for r in results if r.needs_review]

        auto_by_concept: Counter[str] = Counter()
        for r in auto:
            code = r.target_code or "UNCLASSIFIED"
            auto_by_concept[code] += 1

        manual_by_concept: Counter[str] = Counter()
        for r in manual:
            code = r.target_code or "UNCLASSIFIED"
            manual_by_concept[code] += 1

        return {
            "total_variants": total,
            "before": {"AC.01": total, "concepts": 1},
            "after": {
                "sub_concepts": len({r.target_code for r in results if r.target_code}),
                "auto_classified": len(auto),
                "needs_review": len(manual),
                "auto_by_concept": dict(auto_by_concept),
                "manual_by_concept": dict(manual_by_concept),
            },
        }


def load_ac01_variants(cmcc_path: str | Path | None = None) -> list[str]:
    if cmcc_path is None:
        cmcc_path = Path(__file__).resolve().parent.parent / "knowledge" / "cmcc.json"
    with open(cmcc_path) as f:
        data = json.load(f)
    for concept in data:
        if concept.get("id") == "AC.01":
            return concept.get("variantes", [])
    return []
