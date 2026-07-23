from __future__ import annotations
from typing import Optional
from knowledge.normalizer import Normalizer
from knowledge.repository import Repository
from knowledge.concept import Concept


class MatchResult:
    def __init__(self, concept: Concept, score: float, reasons: list[str]):
        self.concept = concept
        self.score = score
        self.reasons = reasons

    def __repr__(self):
        return (f"MatchResult(concept={self.concept.id}, score={self.score}, "
                f"reasons={self.reasons})")

    def to_dict(self) -> dict:
        return {
            "id": self.concept.id,
            "codigo": self.concept.codigo,
            "nombre": self.concept.nombre,
            "score": self.score,
            "motivos": self.reasons,
        }


class Matcher:
    def __init__(self, repository: Repository, normalizer: Optional[Normalizer] = None):
        self.repository = repository
        self.normalizer = normalizer or Normalizer()

    def match(self, text: str, top_n: int = 10) -> list[MatchResult]:
        if not text or not isinstance(text, str):
            return []

        result = self.normalizer.normalize(text)
        normalized = result.text
        tokens = set(normalized.split()) if normalized else set()

        candidates = self.repository.find_candidates(tokens)
        scored = []

        for concept, base_score in candidates:
            reasons = []
            score = base_score

            name_parts = set(concept.nombre.lower().split())
            token_match = len(tokens & name_parts)
            if token_match > 0:
                reasons.append(f"coinciden_{token_match}_palabras_clave")
                score += 0.1 * token_match

            norm_name = self.normalizer.normalize(concept.nombre).text
            if normalized == norm_name:
                reasons.append("coincidencia_exacta_normalizada")
                score = 1.0

            for syn in concept.sinonimos:
                syn_norm = self.normalizer.normalize(syn).text
                if normalized == syn_norm:
                    reasons.append(f"coincide_con_sinonimo_{syn[:30]}")
                    score = max(score, 0.95)
                    break

            for pattern in concept.patrones:
                import re
                try:
                    if re.search(pattern, normalized):
                        reasons.append(f"coincide_patron_{pattern[:30]}")
                        score += 0.2
                except re.error:
                    pass

            for ej in concept.ejemplos[:5]:
                ej_norm = self.normalizer.normalize(ej).text
                if normalized == ej_norm:
                    reasons.append(f"coincide_con_ejemplo")
                    score = max(score, 0.9)
                    break

            for abbr in concept.abreviaturas:
                if abbr in normalized.split():
                    reasons.append(f"contiene_abreviatura_{abbr}")
                    score += 0.05

            for variant in concept.variantes:
                var_norm = self.normalizer.normalize(variant).text
                if normalized == var_norm:
                    reasons.append("coincide_con_variante")
                    score = max(score, 0.85)
                    break

            score = round(min(score, 1.0), 4)
            if reasons:
                scored.append(MatchResult(concept, score, reasons))
            elif score >= 0.15:
                scored.append(MatchResult(concept, score, ["coincidencia_parcial"]))

        scored.sort(key=lambda x: (-x.score, x.concept.nombre))
        return scored[:top_n]
