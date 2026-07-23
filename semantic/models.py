from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SemanticMatch:
    """Resultado del matching semántico de una cuenta.

    - Si score < 0.60 o concept_id es None → UNKNOWN (sin clasificación)
    - Si score >= 0.60 → clasificado con confianza determinada
    """

    account_name: str
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    matched_keyword: Optional[str] = None
    matched_synonym: Optional[str] = None
    matched_alias: Optional[str] = None
    matched_ocr_variant: Optional[str] = None
    score: float = 0.0
    confidence: str = "UNKNOWN"
    expected_cmcc: Optional[str] = None
    expected_account_type: Optional[str] = None
    match_tier: int = 0

    @property
    def is_unknown(self) -> bool:
        return self.score < 0.60 or self.concept_id is None

    @property
    def is_exact(self) -> bool:
        return self.match_tier in (1, 2, 3)

    @property
    def is_fuzzy(self) -> bool:
        return self.match_tier in (4, 5, 6)

    def to_dict(self) -> dict:
        return {
            "account_name": self.account_name,
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "matched_keyword": self.matched_keyword,
            "matched_synonym": self.matched_synonym,
            "matched_alias": self.matched_alias,
            "matched_ocr_variant": self.matched_ocr_variant,
            "score": round(self.score, 4),
            "confidence": self.confidence,
            "expected_cmcc": self.expected_cmcc,
            "expected_account_type": self.expected_account_type,
            "match_tier": self.match_tier,
            "is_unknown": self.is_unknown,
        }
