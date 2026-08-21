from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class CMCCFeatureFlags:
    """Central feature flag registry for CMCC pipeline integration.

    All flags default to OFF / safe values.
    Overridable via CMCC_<FLAG_NAME> environment variable (any truthy value).
    """

    ENABLE_CMCC: bool = False
    """Master switch. If False, no CMCC code path executes."""

    ENABLE_CMCC_SHADOW: bool = True
    """If True, CMCC runs in shadow mode on UNKNOWN accounts.
    Results are stored in cmcc_shadow but never affect standard_code.
    Has no effect if ENABLE_CMCC=False."""

    ENABLE_CMCC_PRODUCTION: bool = False
    """If True, CMCC results with score >= CMCC_THRESHOLD are written
    into standard_code/final_code, classifying the account.
    Has no effect if ENABLE_CMCC=False."""

    ENABLE_CMCC_ROLLBACK: bool = False
    """If True, ALL CMCC behavior is suppressed and the pipeline
    behaves exactly as before CMCC integration existed.
    Overrides all other flags."""

    CMCC_THRESHOLD: float = 0.95
    """Minimum CMCC score for a result to be accepted in production mode."""

    CMCC_REVIEW_THRESHOLD: float = 0.85
    """Scores between this and CMCC_THRESHOLD are flagged for human review."""

    ENABLE_CMCC_REVIEW_PIPELINE: bool = False
    """When True, UNKNOWN accounts with CMCC score==1.0 (exact variant match,
    single proposal, no conflicts) are recorded in a review queue (REVIEW_CMCC).
    The account remains UNKNOWN officially — REVIEW_CMCC is NOT a classification.
    When False, behavior is identical to pre-existing pipeline."""

    ENABLE_ACCOUNT_TYPE_FILTER: bool = False
    """When True, each classified account's standard_code is validated against
    the account type resolved by AccountTypeResolver. If the code prefix (AC,
    ANC, PC, PNC, PAT, ER) contradicts the resolved type (ACTIVO, PASIVO,
    PATRIMONIO, PERDIDA, GANANCIA), the result is demoted to unclassified.
    Only affects the final standard_code, not shadow/CMCC data."""

    ENABLE_REGEX_FALLBACK: bool = True
    """When True, REGEX_FALLBACK patterns (100% audited precision) are applied
    as the last classification stage after dictionary fuzzy. Each match is
    validated against the resolved account type before being accepted.
    When False, the pipeline behaves exactly as before Sprint 28.5A."""

    ENABLE_SEMANTIC_MATCHER: bool = False
    """When True, the SemanticMatcher stage runs AFTER dictionary fuzzy and
    BEFORE regex fallback. Uses RapidFuzz + Concept Catalog to classify
    accounts that no earlier stage could resolve.
    When False, the pipeline behaves exactly as before (Phase 2)."""

    ENABLE_DECISION_ENGINE: bool = False
    """When True, the DecisionEngine stage collects results from ALL
    classification stages (code, dictionary, SemanticMatcher, RegexFallback)
    and applies a rule-based resolution to select the final code.
    When False, the pipeline uses the original first-match-wins behavior.
    Feature flag for immediate rollback."""

    def __post_init__(self) -> None:
        if self.ENABLE_CMCC_ROLLBACK:
            self.ENABLE_CMCC = False
            self.ENABLE_CMCC_SHADOW = False
            self.ENABLE_CMCC_PRODUCTION = False

    def to_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in self.__dataclass_fields__.values()}

    @classmethod
    def from_env(cls) -> CMCCFeatureFlags:
        flags = cls()
        for field_name in cls.__dataclass_fields__:
            env_key = f"CMCC_{field_name}"
            if env_key in os.environ:
                raw = os.environ[env_key]
                type_str = cls._resolve_type(field_name)
                if type_str == "bool":
                    setattr(flags, field_name, raw.lower() in ("1", "true", "yes", "on"))
                elif type_str == "float":
                    setattr(flags, field_name, float(raw))
                elif type_str == "int":
                    setattr(flags, field_name, int(raw))
                else:
                    setattr(flags, field_name, raw)
        flags.__post_init__()
        return flags

    @classmethod
    def _resolve_type(cls, field_name: str) -> str:
        raw = cls.__dataclass_fields__[field_name].type
        if isinstance(raw, type):
            return raw.__name__
        return raw

    @classmethod
    def default(cls) -> CMCCFeatureFlags:
        return cls()
