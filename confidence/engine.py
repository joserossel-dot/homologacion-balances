from __future__ import annotations

from confidence.models import ConfidenceBreakdown, ConfidenceResult


class ConfidenceEngine:
    """Calcula confianza 0-100 combinando señales de toda la pipeline.

    Fórmula:
        score = base - tier_penalty + source_bonus + type_bonus + dict_bonus
        clamped to [0, 100]

    Donde:
        base       = score del método ganador × 100
        tier_penalty = penalización por tier SM (más alto = menos confianza)
        source_bonus = bono por fuente de decisión
        type_bonus   = +5 si tipo compatible, -10 si no
        dict_bonus   = +5 si dictionary_exact, +2 si dictionary_fuzzy
    """

    TIER_PENALTY = {0: 0, 1: 0, 2: 3, 3: 5, 4: 10, 5: 15, 6: 20}

    SOURCE_BONUS = {
        "SM_AND_REGEX_AGREE": 10,
        "SM_HIGH_CONFIDENCE": 5,
        "SM_ONLY": 0,
        "REGEX_EXACT": 5,
        "REGEX_ONLY": 0,
        "CONFLICT_UNRESOLVED": -20,
        "BOTH_UNKNOWN": 0,
    }

    DICT_BONUS = {"dictionary_exact": 5, "dictionary_fuzzy": 2}

    def compute(
        self,
        *,
        sm_score: float | None,
        sm_tier: int | None,
        regex_score: float | None = None,
        regex_method: str | None = None,
        decision_source: str,
        type_compatible: bool | None = None,
        dict_method: str | None = None,
    ) -> ConfidenceResult:
        bd = ConfidenceBreakdown()

        # --- base score del método ganador ---
        base_score = 0.0
        if decision_source in ("SM_AND_REGEX_AGREE", "SM_HIGH_CONFIDENCE", "SM_ONLY"):
            base_score = sm_score if sm_score is not None else 0.0
        elif decision_source in ("REGEX_EXACT", "REGEX_ONLY"):
            base_score = regex_score if regex_score is not None else 0.70
        elif decision_source == "CONFLICT_UNRESOLVED":
            base_score = max(
                sm_score if sm_score is not None else 0.0,
                regex_score if regex_score is not None else 0.0,
            )
        bd.base_score = base_score

        raw = int(base_score * 100)

        # --- tier_penalty ---
        tier = sm_tier if sm_tier is not None else 0
        tp = self.TIER_PENALTY.get(tier, 10)
        bd.tier_penalty = tp

        # --- source_bonus ---
        sb = self.SOURCE_BONUS.get(decision_source, 0)
        bd.source_bonus = sb

        # --- type_bonus ---
        tb = 5 if type_compatible else (-10 if type_compatible is False else 0)
        bd.type_bonus = tb

        # --- dict_bonus ---
        db = self.DICT_BONUS.get(dict_method, 0)
        bd.dict_bonus = db

        total = raw - tp + sb + tb + db
        total = max(0, min(100, total))
        bd.total = total

        label = ConfidenceResult.label_for(total)

        return ConfidenceResult(score=total, label=label, breakdown=bd)
