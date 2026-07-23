from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz

from semantic.models import SemanticMatch


# Pesos de cada tier (multiplicador del ratio de similitud)
TIER_WEIGHTS: dict[int, float] = {
    1: 1.00,
    2: 0.95,
    3: 0.90,
    4: 0.85,
    5: 0.75,
    6: 0.60,
}

CONFIDENCE_BY_SCORE: list[tuple[float, str]] = [
    (0.95, "EXACT"),
    (0.90, "VERY_HIGH"),
    (0.80, "HIGH"),
    (0.70, "MEDIUM"),
    (0.60, "LOW"),
]

TIER_NAMES: dict[int, str] = {
    1: "keyword_exact",
    2: "synonym_exact",
    3: "abbreviation",
    4: "keyword_fuzzy",
    5: "synonym_fuzzy",
    6: "root_word",
}

TYPE_BONUS = 1.10


def compute_confidence(score: float) -> str:
    if score >= 0.95:
        return "EXACT"
    if score >= 0.90:
        return "VERY_HIGH"
    if score >= 0.80:
        return "HIGH"
    if score >= 0.70:
        return "MEDIUM"
    if score >= 0.60:
        return "LOW"
    return "UNKNOWN"


class Scorer:
    """Evalúa el matching entre un nombre normalizado y un concepto."""

    def __init__(self):
        self._cache: dict[str, dict[str, float]] = {}

    def _cached_ratio(self, a: str, b: str) -> float:
        key = (a, b) if a <= b else (b, a)
        cache_key = f"{key[0]}|{key[1]}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        ratio = fuzz.token_sort_ratio(a, b) / 100.0
        self._cache[cache_key] = ratio
        return ratio

    def evaluate_concept(
        self,
        norm_name: str,
        concept: dict,
        root_word: Optional[str],
        account_type: Optional[str] = None,
    ) -> Optional[SemanticMatch]:
        """Evalúa los 6 tiers contra un concepto. Retorna el mejor match."""
        best = SemanticMatch(account_name=norm_name)
        cid = concept["id"]
        cname = concept["name"]
        expected_cmcc = concept.get("expected_cmcc_code", "POR_DEFINIR")
        expected_type = concept.get("type", "")

        # Tier 1: keyword exacto
        for kw in concept.get("keywords", []):
            kw_norm = self._normalize_str(kw)
            if norm_name == kw_norm:
                score = 1.0 * TIER_WEIGHTS[1]
                return self._build_match(
                    concept, norm_name, score, 1,
                    matched_keyword=kw,
                    account_type=account_type,
                )

        # Tier 2: sinónimo exacto
        for syn in concept.get("synonyms", []):
            syn_norm = self._normalize_str(syn)
            if norm_name == syn_norm:
                score = 1.0 * TIER_WEIGHTS[2]
                return self._build_match(
                    concept, norm_name, score, 2,
                    matched_synonym=syn,
                    account_type=account_type,
                )

        # Tier 3: abreviatura exacta
        for abbr in concept.get("abbreviations", []):
            abbr_norm = self._normalize_str(abbr)
            if norm_name == abbr_norm:
                score = 1.0 * TIER_WEIGHTS[3]
                return self._build_match(
                    concept, norm_name, score, 3,
                    matched_alias=abbr,
                    account_type=account_type,
                )

        # Tier 4: fuzzy keyword
        for kw in concept.get("keywords", []):
            kw_norm = self._normalize_str(kw)
            ratio = self._cached_ratio(norm_name, kw_norm)
            score = ratio * TIER_WEIGHTS[4]
            if score > best.score:
                best = self._build_match(
                    concept, norm_name, score, 4,
                    matched_keyword=kw,
                    account_type=account_type,
                )

        # Tier 5: fuzzy sinónimo
        for syn in concept.get("synonyms", []):
            syn_norm = self._normalize_str(syn)
            ratio = self._cached_ratio(norm_name, syn_norm)
            score = ratio * TIER_WEIGHTS[5]
            if score > best.score:
                best = self._build_match(
                    concept, norm_name, score, 5,
                    matched_synonym=syn,
                    account_type=account_type,
                )

        # Tier 6: raíz léxica
        if root_word:
            concept_root = self._concept_root_word(concept)
            if concept_root and root_word == concept_root:
                score = 1.0 * TIER_WEIGHTS[6]
                if score > best.score:
                    best = self._build_match(
                        concept, norm_name, score, 6,
                        account_type=account_type,
                    )

        return best if best.score >= 0.50 else None

    def _build_match(
        self,
        concept: dict,
        account_name: str,
        score: float,
        tier: int,
        matched_keyword: Optional[str] = None,
        matched_synonym: Optional[str] = None,
        matched_alias: Optional[str] = None,
        account_type: Optional[str] = None,
    ) -> SemanticMatch:
        confidence = compute_confidence(score)
        match = SemanticMatch(
            account_name=account_name,
            concept_id=concept["id"],
            concept_name=concept["name"],
            matched_keyword=matched_keyword,
            matched_synonym=matched_synonym,
            matched_alias=matched_alias,
            score=score,
            confidence=confidence,
            expected_cmcc=concept.get("expected_cmcc_code"),
            expected_account_type=concept.get("type", ""),
            match_tier=tier,
        )
        return match

    @staticmethod
    def _normalize_str(text: str) -> str:
        import unicodedata, re
        s = text.lower().strip()
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode("ascii")
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    @staticmethod
    def _concept_root_word(concept: dict) -> Optional[str]:
        name = concept.get("name", "")
        if not name:
            return None
        normalized = Scorer._normalize_str(name)
        return normalized.split()[0] if normalized else None
