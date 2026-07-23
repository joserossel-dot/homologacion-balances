from __future__ import annotations

from decision.engine import DecisionEngine


def test_rule_1_sm_regex_agree():
    de = DecisionEngine()
    r = de.decide(
        sm_code="ER.04", sm_score=0.85, sm_tier=4, sm_confidence="HIGH",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final == "ER.04"
    assert r.decision_source == "SM_AND_REGEX_AGREE"
    assert r.confidence == "VERY_HIGH"
    assert not r.review_required


def test_rule_2_sm_high_confidence():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.97, sm_tier=1, sm_confidence="EXACT",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final == "PC.06"
    assert r.decision_source == "SM_HIGH_CONFIDENCE"
    assert r.confidence == "VERY_HIGH"
    assert not r.review_required


def test_rule_2_boundary_095():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.951, sm_tier=4, sm_confidence="HIGH",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final == "PC.06"
    assert r.decision_source == "SM_HIGH_CONFIDENCE"


def test_rule_2_below_095():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.94, sm_tier=4, sm_confidence="MEDIUM",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final is None
    assert r.decision_source == "CONFLICT_UNRESOLVED"
    assert r.review_required


def test_rule_3_regex_exact_sm_low():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.60, sm_tier=6, sm_confidence="LOW",
        regex_code="ER.04", regex_method="dictionary_exact",
    )
    assert r.codigo_final == "ER.04"
    assert r.decision_source == "REGEX_EXACT"
    assert r.confidence == "HIGH"
    assert not r.review_required


def test_rule_3_regex_exact_sm_high():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.80, sm_tier=4, sm_confidence="MEDIUM",
        regex_code="ER.04", regex_method="dictionary_exact",
    )
    assert r.codigo_final is None
    assert r.decision_source == "CONFLICT_UNRESOLVED"
    assert r.review_required


def test_rule_3_regex_not_exact():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.60, sm_tier=6, sm_confidence="LOW",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final is None
    assert r.decision_source == "CONFLICT_UNRESOLVED"
    assert r.review_required


def test_sm_only():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.80, sm_tier=4, sm_confidence="HIGH",
        regex_code=None, regex_method=None,
    )
    assert r.codigo_final == "PC.06"
    assert r.decision_source == "SM_ONLY"
    assert not r.review_required


def test_regex_only():
    de = DecisionEngine()
    r = de.decide(
        sm_code=None, sm_score=None, sm_tier=None, sm_confidence=None,
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert r.codigo_final == "ER.04"
    assert r.decision_source == "REGEX_ONLY"
    assert not r.review_required


def test_both_unknown():
    de = DecisionEngine()
    r = de.decide(
        sm_code=None, sm_score=None, sm_tier=None, sm_confidence=None,
        regex_code=None, regex_method=None,
    )
    assert r.codigo_final is None
    assert r.decision_source == "BOTH_UNKNOWN"
    assert r.review_required


def test_evidence_present():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.97, sm_tier=1, sm_confidence="EXACT",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    assert len(r.evidence) == 1
    assert r.evidence[0].rule == "rule_2_sm_high_confidence"
    assert r.evidence[0].score_sm == 0.97


def test_to_dict():
    de = DecisionEngine()
    r = de.decide(
        sm_code="PC.06", sm_score=0.97, sm_tier=1, sm_confidence="EXACT",
        regex_code="ER.04", regex_method="regex_fallback",
    )
    d = r.to_dict()
    assert d["codigo_final"] == "PC.06"
    assert d["decision_source"] == "SM_HIGH_CONFIDENCE"
    assert d["review_required"] is False
    assert len(d["evidence"]) == 1
