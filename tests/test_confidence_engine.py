from __future__ import annotations

from confidence.engine import ConfidenceEngine


def _de(score: int = 70) -> ConfidenceEngine:
    return ConfidenceEngine()


def test_agree_exact_tier1():
    r = _de().compute(
        sm_score=1.0, sm_tier=1,
        regex_score=0.90, regex_method="regex_fallback",
        decision_source="SM_AND_REGEX_AGREE",
        type_compatible=True,
    )
    # base=100 - tp(0) + sb(10) + tb(5) + db(0) = 115 → cap 100
    assert r.score == 100
    assert r.label == "VERY_HIGH"


def test_sm_high_confidence():
    r = _de().compute(
        sm_score=0.97, sm_tier=1,
        regex_score=0.88, regex_method="regex_fallback",
        decision_source="SM_HIGH_CONFIDENCE",
        type_compatible=True,
    )
    # base=97 - 0 + 5 + 5 + 0 = 107 → cap 100
    assert r.score == 100
    assert r.label == "VERY_HIGH"


def test_sm_only_tier4():
    r = _de().compute(
        sm_score=0.75, sm_tier=4,
        decision_source="SM_ONLY",
        type_compatible=True,
    )
    # base=75 - 10 + 0 + 5 + 0 = 70
    assert r.score == 70
    assert r.label == "HIGH"


def test_sm_only_tier6():
    r = _de().compute(
        sm_score=0.60, sm_tier=6,
        decision_source="SM_ONLY",
        type_compatible=True,
    )
    # base=60 - 20 + 0 + 5 + 0 = 45
    assert r.score == 45
    assert r.label == "MEDIUM"


def test_regex_exact():
    r = _de().compute(
        sm_score=0.60, sm_tier=6,
        regex_score=0.90, regex_method="regex_fallback",
        decision_source="REGEX_EXACT",
        type_compatible=True,
    )
    # base=90 - 20 + 5 + 5 + 0 = 80
    assert r.score == 80
    assert r.label == "HIGH"


def test_regex_only():
    r = _de().compute(
        sm_score=None, sm_tier=None,
        regex_score=0.88, regex_method="regex_fallback",
        decision_source="REGEX_ONLY",
        type_compatible=True,
    )
    # base=88 - 0 + 0 + 5 + 0 = 93
    assert r.score == 93
    assert r.label == "VERY_HIGH"


def test_conflict_unresolved():
    r = _de().compute(
        sm_score=0.70, sm_tier=4,
        regex_score=0.88, regex_method="regex_fallback",
        decision_source="CONFLICT_UNRESOLVED",
        type_compatible=True,
    )
    # base=max(70, 88)=88 - 10 + (-20) + 5 + 0 = 63
    assert r.score == 63
    assert r.label == "HIGH"


def test_both_unknown():
    r = _de().compute(
        sm_score=None, sm_tier=None,
        decision_source="BOTH_UNKNOWN",
    )
    # base=0 - 0 + 0 + 0 + 0 = 0
    assert r.score == 0
    assert r.label == "UNKNOWN"


def test_type_incompatible_penalty():
    r = _de().compute(
        sm_score=0.85, sm_tier=1,
        decision_source="SM_ONLY",
        type_compatible=False,
    )
    # base=85 - 0 + 0 + (-10) + 0 = 75
    assert r.score == 75
    assert r.label == "HIGH"


def test_dict_exact_bonus():
    r = _de().compute(
        sm_score=0.85, sm_tier=2,
        decision_source="SM_ONLY",
        type_compatible=True,
        dict_method="dictionary_exact",
    )
    # base=85 - 3 + 0 + 5 + 5 = 92
    assert r.score == 92
    assert r.label == "VERY_HIGH"


def test_floor_zero():
    r = _de().compute(
        sm_score=0.0, sm_tier=6,
        decision_source="SM_ONLY",
        type_compatible=False,
    )
    # base=0 - 20 + 0 + (-10) + 0 = -30 → 0
    assert r.score == 0
    assert r.label == "UNKNOWN"


def test_breakdown_present():
    r = _de().compute(
        sm_score=0.75, sm_tier=4,
        decision_source="SM_ONLY",
        type_compatible=True,
    )
    b = r.breakdown
    assert b.base_score == 0.75
    assert b.tier_penalty == 10
    assert b.source_bonus == 0
    assert b.type_bonus == 5
    assert b.total == 70


def test_to_dict():
    r = _de().compute(
        sm_score=0.75, sm_tier=4,
        decision_source="SM_ONLY",
        type_compatible=True,
    )
    d = r.to_dict()
    assert d["score"] == 70
    assert d["label"] == "HIGH"
    assert "breakdown" in d
