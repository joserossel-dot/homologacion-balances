from __future__ import annotations

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import Any

from self_qa_engine import (
    RiskLevel, ApprovalState, QualityGate, QAIssue, QARisk,
    QAConfidence, QARecommendation, QAResult, QASummary,
    DEFAULT_GATE_THRESHOLDS, DEFAULT_CONFIDENCE_WEIGHTS, DEFAULT_RISK_WEIGHTS,
    risk_level_from_score, risk_score_from_coverage,
    QualityGateEvaluator, RiskCalculator, IssueAnalyzer,
    ApprovalEngine, RecommendationEngine, ConfidenceEngine,
    QAStatisticsCollector, QaReportGenerator, SelfQAAdapter,
)

from document_context import DocumentContext
from document_context.models import (
    StructureData, ParserData, ValidationData, KnowledgeData,
    PredictionData, DocumentMetadata,
)


# =============================================================================
# HELPERS
# =============================================================================

@dataclass
class FakeIntegrity:
    overall: float = 0.0


def make_coverage_data(**overrides) -> dict[str, Any]:
    data = {
        "overall": 0.92,
        "monetary": {"coverage_pct": 0.95, "total_amount": 1000000.0, "explained_amount": 950000.0, "by_family": {}},
        "structural": {"overall": 0.88, "subtotals_detected": 4, "subtotals_expected": 4, "subtotals_validated": 3},
        "semantic": {"overall": 0.90, "classified_count": 45, "total_accounts": 50, "unknown_count": 5},
        "document": {"coverage_pct": 0.95, "present_sections": 4, "expected_sections": 4},
        "issues": [],
    }
    data.update(overrides)
    return data


def make_decision_stats(**overrides) -> dict[str, Any]:
    stats = {
        "total_decisions": 50,
        "avg_confidence": 0.85,
        "decisions_by_type": {"CONTINUE": 40, "LEARNING": 5, "MANUAL_REVIEW": 3, "REJECT": 2},
        "conflicts_detected": 2,
        "conflicts_by_severity": {"LOW": 2},
    }
    stats.update(overrides)
    return stats


# =============================================================================
# MODELS TESTS
# =============================================================================

class TestRiskLevel:
    def test_values(self):
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"

    def test_ordering(self):
        levels = list(RiskLevel)
        assert levels.index(RiskLevel.LOW) < levels.index(RiskLevel.CRITICAL)


class TestApprovalState:
    def test_values(self):
        assert ApprovalState.APPROVED.value == "APPROVED"
        assert ApprovalState.REJECTED.value == "REJECTED"
        assert ApprovalState.FAILED.value == "FAILED"
        assert ApprovalState.MANUAL_REVIEW.value == "MANUAL_REVIEW"
        assert ApprovalState.LEARNING.value == "LEARNING"
        assert ApprovalState.STRESS.value == "STRESS"
        assert ApprovalState.APPROVED_WITH_WARNINGS.value == "APPROVED_WITH_WARNINGS"

    def test_unique(self):
        values = [s.value for s in ApprovalState]
        assert len(values) == len(set(values))


class TestQualityGate:
    def test_defaults(self):
        g = QualityGate()
        assert g.name == ""
        assert g.passed is False
        assert g.score == 0.0

    def test_full(self):
        g = QualityGate(name="monetary_coverage", passed=True, score=0.95, weight=0.95, detail="test")
        assert g.name == "monetary_coverage"
        assert g.passed is True
        assert g.score == 0.95

    def test_to_dict(self):
        g = QualityGate(name="test", passed=True, score=0.9, weight=0.8, detail="ok")
        d = g.to_dict()
        assert d["name"] == "test"
        assert d["passed"] is True
        assert d["score"] == 0.9

    def test_roundtrip(self):
        g = QualityGate(name="structural_coverage", passed=False, score=0.5, weight=0.85, detail="bajo")
        g2 = QualityGate.from_dict(g.to_dict())
        assert g2.name == "structural_coverage"
        assert g2.passed is False

    def test_from_dict_empty(self):
        g = QualityGate.from_dict({})
        assert g.name == ""


class TestQAIssue:
    def test_defaults(self):
        i = QAIssue()
        assert i.source == ""
        assert i.severity == "INFO"

    def test_full(self):
        i = QAIssue(source="coverage", issue_type="low_coverage", severity="HIGH", detail="test", impact=0.5)
        assert i.source == "coverage"
        assert i.severity == "HIGH"

    def test_to_dict(self):
        i = QAIssue(source="validation", issue_type="error", severity="CRITICAL", detail="fail")
        d = i.to_dict()
        assert d["severity"] == "CRITICAL"

    def test_roundtrip(self):
        i = QAIssue(source="parser", issue_type="ignored", severity="LOW", detail="5 ignored")
        i2 = QAIssue.from_dict(i.to_dict())
        assert i2.source == "parser"
        assert i2.issue_type == "ignored"

    def test_from_dict_empty(self):
        i = QAIssue.from_dict({})
        assert i.source == ""
        assert i.severity == "INFO"


class TestQARisk:
    def test_defaults(self):
        r = QARisk()
        assert r.total_risk == 0.0
        assert r.level == RiskLevel.LOW

    def test_full(self):
        r = QARisk(document_risk=20, structural_risk=30, monetary_risk=10, semantic_risk=25, operational_risk=15, total_risk=20, level=RiskLevel.MEDIUM)
        assert r.total_risk == 20
        assert r.level == RiskLevel.MEDIUM

    def test_to_dict(self):
        r = QARisk(total_risk=75, level=RiskLevel.HIGH)
        d = r.to_dict()
        assert d["total_risk"] == 75
        assert d["level"] == "HIGH"

    def test_roundtrip(self):
        r = QARisk(total_risk=90, level=RiskLevel.CRITICAL)
        r2 = QARisk.from_dict(r.to_dict())
        assert r2.total_risk == 90
        assert r2.level == RiskLevel.CRITICAL


class TestQAConfidence:
    def test_defaults(self):
        c = QAConfidence()
        assert c.overall == 0.0

    def test_full(self):
        c = QAConfidence(overall=0.85, coverage=0.9, decision=0.8)
        assert c.overall == 0.85
        assert c.coverage == 0.9

    def test_to_dict(self):
        c = QAConfidence(overall=0.75)
        d = c.to_dict()
        assert d["overall"] == 0.75

    def test_roundtrip(self):
        c = QAConfidence(overall=0.92, coverage=0.95, decision=0.9, validation=0.88)
        c2 = QAConfidence.from_dict(c.to_dict())
        assert c2.overall == 0.92
        assert c2.validation == 0.88


class TestQARecommendation:
    def test_defaults(self):
        r = QARecommendation()
        assert r.message == ""

    def test_full(self):
        r = QARecommendation(message="Test", actions=["action1", "action2"])
        assert r.message == "Test"
        assert len(r.actions) == 2

    def test_to_dict(self):
        r = QARecommendation(message="msg", actions=["a"])
        d = r.to_dict()
        assert d["message"] == "msg"

    def test_roundtrip(self):
        r = QARecommendation(message="Hello", actions=["do something"])
        r2 = QARecommendation.from_dict(r.to_dict())
        assert r2.message == "Hello"


class TestQAResult:
    def test_defaults(self):
        r = QAResult()
        assert r.approval_state == ApprovalState.MANUAL_REVIEW

    def test_full(self):
        r = QAResult(
            approval_state=ApprovalState.APPROVED,
            confidence=QAConfidence(overall=0.95),
            risk=QARisk(total_risk=10, level=RiskLevel.LOW),
            gates=[QualityGate(name="g1", passed=True, score=0.9, weight=0.9)],
            issues=[QAIssue(source="test", issue_type="warn", severity="LOW")],
            recommendations=[QARecommendation(message="ok")],
            decision_reason="All good",
        )
        assert r.approval_state == ApprovalState.APPROVED
        assert len(r.gates) == 1
        assert len(r.issues) == 1

    def test_to_dict(self):
        r = QAResult(
            approval_state=ApprovalState.REJECTED,
            confidence=QAConfidence(overall=0.3),
            risk=QARisk(total_risk=80, level=RiskLevel.CRITICAL),
            decision_reason="Bad",
        )
        d = r.to_dict()
        assert d["approval_state"] == "REJECTED"
        assert d["decision_reason"] == "Bad"

    def test_roundtrip(self):
        r = QAResult(
            approval_state=ApprovalState.APPROVED_WITH_WARNINGS,
            confidence=QAConfidence(overall=0.8),
            risk=QARisk(total_risk=30, level=RiskLevel.MEDIUM),
            gates=[QualityGate(name="g", passed=True, score=0.8, weight=0.8)],
            issues=[QAIssue(source="v", issue_type="w", severity="MEDIUM")],
            recommendations=[QARecommendation(message="check")],
            decision_reason="warnings",
        )
        r2 = QAResult.from_dict(r.to_dict())
        assert r2.approval_state == ApprovalState.APPROVED_WITH_WARNINGS
        assert len(r2.gates) == 1
        assert r2.gates[0].name == "g"

    def test_json_serializable(self):
        r = QAResult(approval_state=ApprovalState.APPROVED)
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        assert loaded["approval_state"] == "APPROVED"


class TestQASummary:
    def test_defaults(self):
        s = QASummary()
        assert s.total_documents == 0

    def test_full(self):
        s = QASummary(total_documents=10, approved=5, manual_review=3, rejected=2, avg_confidence=0.85)
        assert s.approved == 5
        assert s.avg_confidence == 0.85

    def test_to_dict(self):
        s = QASummary(total_documents=3, approved=2, rejected=1)
        d = s.to_dict()
        assert d["total_documents"] == 3
        assert d["approved"] == 2

    def test_roundtrip(self):
        s = QASummary(total_documents=5, approved=3, avg_confidence=0.9)
        s2 = QASummary.from_dict(s.to_dict())
        assert s2.total_documents == 5
        assert s2.avg_confidence == 0.9


class TestRiskHelpers:
    def test_risk_level_from_score_low(self):
        assert risk_level_from_score(10) == RiskLevel.LOW

    def test_risk_level_from_score_medium(self):
        assert risk_level_from_score(30) == RiskLevel.MEDIUM

    def test_risk_level_from_score_high(self):
        assert risk_level_from_score(60) == RiskLevel.HIGH

    def test_risk_level_from_score_critical(self):
        assert risk_level_from_score(85) == RiskLevel.CRITICAL

    def test_risk_level_boundaries(self):
        assert risk_level_from_score(24) == RiskLevel.LOW
        assert risk_level_from_score(25) == RiskLevel.MEDIUM
        assert risk_level_from_score(49) == RiskLevel.MEDIUM
        assert risk_level_from_score(50) == RiskLevel.HIGH
        assert risk_level_from_score(79) == RiskLevel.HIGH
        assert risk_level_from_score(80) == RiskLevel.CRITICAL

    def test_risk_score_from_coverage(self):
        assert risk_score_from_coverage(1.0) == 0.0
        assert risk_score_from_coverage(0.95) == 5.0
        assert risk_score_from_coverage(0.5) == 50.0
        assert risk_score_from_coverage(0.0) == 100.0


class TestConstants:
    def test_default_gate_thresholds(self):
        assert "monetary_coverage" in DEFAULT_GATE_THRESHOLDS
        assert DEFAULT_GATE_THRESHOLDS["monetary_coverage"] == 0.95

    def test_default_confidence_weights(self):
        assert abs(sum(DEFAULT_CONFIDENCE_WEIGHTS.values()) - 1.0) < 0.001
        assert "coverage" in DEFAULT_CONFIDENCE_WEIGHTS

    def test_default_risk_weights(self):
        assert abs(sum(DEFAULT_RISK_WEIGHTS.values()) - 1.0) < 0.001
        assert "monetary" in DEFAULT_RISK_WEIGHTS


# =============================================================================
# QUALITY GATE TESTS
# =============================================================================

class TestQualityGateEvaluator:
    def test_all_gates_empty(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate()
        assert len(gates) == 10

    def test_all_gates_with_data(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(
            coverage_data=make_coverage_data(),
            decision_stats=make_decision_stats(),
            validation_data=ValidationData(),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            parser_data=ParserData(selected_parser="universal", accounts=["a", "b"]),
            knowledge_data=KnowledgeData(cmcc_matches=["m1"], learning_hits=["l1"]),
            predictions=PredictionData(confidence_expected=0.8, coverage_expected=0.7),
        )
        assert len(gates) == 10
        passed = sum(1 for g in gates if g.passed)
        assert passed >= 7  # most should pass

    def test_monetary_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.99}))
        monetary_gate = [g for g in gates if g.name == "monetary_coverage"][0]
        assert monetary_gate.passed is True
        assert monetary_gate.score == 0.99

    def test_monetary_gate_fail(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.5}))
        monetary_gate = [g for g in gates if g.name == "monetary_coverage"][0]
        assert monetary_gate.passed is False

    def test_structural_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(coverage_data=make_coverage_data(structural={"overall": 0.9}))
        g = [g for g in gates if g.name == "structural_coverage"][0]
        assert g.passed is True

    def test_semantic_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(coverage_data=make_coverage_data(semantic={"overall": 0.75}))
        g = [g for g in gates if g.name == "semantic_coverage"][0]
        assert g.passed is False

    def test_document_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(coverage_data=make_coverage_data(document={"coverage_pct": 0.95, "present_sections": [1, 2, 3], "expected_sections": [1, 2, 3]}))
        g = [g for g in gates if g.name == "document_coverage"][0]
        assert g.passed is True

    def test_decision_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(decision_stats=make_decision_stats(avg_confidence=0.95))
        g = [g for g in gates if g.name == "decision_confidence"][0]
        assert g.passed is True

    def test_validation_gate_with_errors(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(validation_data=ValidationData(errors=["e1"]))
        g = [g for g in gates if g.name == "validation_integrity"][0]
        # has_errors = True so score should be low
        assert g.score < 0.5

    def test_parser_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(parser_data=ParserData(selected_parser="universal", raw_accounts=[1, 2, 3], accounts=[1, 2, 3]))
        g = [g for g in gates if g.name == "parser_success"][0]
        assert g.passed is True

    def test_structure_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(structure_data=StructureData(family="TRIBUTARIO", template="T14", document_type="BALANCE"))
        g = [g for g in gates if g.name == "structure_valid"][0]
        assert g.passed is True

    def test_knowledge_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(knowledge_data=KnowledgeData(cmcc_matches=["m1"]))
        g = [g for g in gates if g.name == "knowledge_presence"][0]
        assert g.passed is True

    def test_die_gate(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(predictions=PredictionData(confidence_expected=0.8, coverage_expected=0.7))
        g = [g for g in gates if g.name == "die_confidence"][0]
        assert g.score == 0.75
        assert g.passed is True

    def test_custom_thresholds(self):
        evaluator = QualityGateEvaluator(thresholds={"monetary_coverage": 0.50})
        gates = evaluator.evaluate(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.60}))
        g = [g for g in gates if g.name == "monetary_coverage"][0]
        assert g.passed is True

    def test_thresholds_property(self):
        evaluator = QualityGateEvaluator()
        t = evaluator.thresholds
        assert t["monetary_coverage"] == 0.95
        t["monetary_coverage"] = 0.5
        assert evaluator.thresholds["monetary_coverage"] == 0.95


# =============================================================================
# RISK CALCULATOR TESTS
# =============================================================================

class TestRiskCalculator:
    def test_default_risk(self):
        calc = RiskCalculator()
        risk = calc.compute()
        assert risk.total_risk > 0
        assert risk.level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_low_risk(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.99},
                structural={"overall": 0.95},
                semantic={"overall": 0.98},
                document={"coverage_pct": 1.0},
            ),
            validation_data=ValidationData(),
            parser_data=ParserData(selected_parser="universal"),
        )
        assert risk.total_risk < 25
        assert risk.level == RiskLevel.LOW

    def test_high_risk(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.2},
                structural={"overall": 0.3},
                semantic={"overall": 0.3},
                document={"coverage_pct": 0.2},
            ),
        )
        assert risk.total_risk > 50

    def test_monetary_risk_calculation(self):
        calc = RiskCalculator()
        risk = calc.compute(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.99}))
        assert risk.monetary_risk == 1.0

    def test_monetary_risk_with_gap(self):
        calc = RiskCalculator()
        risk = calc.compute(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.9, "total_amount": 1000000.0, "explained_amount": 800000.0}))
        # gap > 10% so extra penalty
        assert risk.monetary_risk > 10.0

    def test_operational_risk_with_errors(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(),
            validation_data=ValidationData(errors=["e1", "e2"], warnings=["w1"]),
        )
        assert risk.operational_risk > 0

    def test_operational_risk_without_parser(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(),
            parser_data=ParserData(selected_parser=""),
        )
        assert risk.operational_risk > 20

    def test_operational_risk_with_conflicts(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(),
            decision_stats=make_decision_stats(conflicts_detected=5),
        )
        assert risk.operational_risk > 0

    def test_weights_property(self):
        calc = RiskCalculator()
        w = calc.weights
        assert "monetary" in w
        w["monetary"] = 0.5
        assert calc.weights["monetary"] != 0.5  # should be immutable copy

    def test_custom_weights(self):
        calc = RiskCalculator(weights={"monetary": 1.0, "structural": 0.0, "semantic": 0.0, "operational": 0.0, "document": 0.0})
        risk = calc.compute(coverage_data=make_coverage_data(monetary={"coverage_pct": 0.95}))
        assert risk.total_risk == 5.0


# =============================================================================
# ISSUE ANALYZER TESTS
# =============================================================================

class TestIssueAnalyzer:
    def test_no_issues(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate()
        assert len(issues) == 0

    def test_coverage_issues(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            coverage_issues=[
                {"issue_type": "unexplained_amount", "severity": "HIGH", "detail": "test", "monetary_impact": 5000},
            ],
        )
        assert len(issues) == 1
        assert issues[0].source == "coverage"

    def test_validation_errors(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            validation_data=ValidationData(errors=["error 1", "error 2"]),
        )
        assert len(issues) == 2
        assert all(i.severity == "CRITICAL" for i in issues)

    def test_validation_warnings(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            validation_data=ValidationData(warnings=["warn 1"]),
        )
        assert len(issues) == 1
        assert issues[0].severity == "MEDIUM"

    def test_decision_conflicts(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            decision_stats=make_decision_stats(conflicts_detected=3),
        )
        conflict_issues = [i for i in issues if i.issue_type == "decision_conflicts"]
        assert len(conflict_issues) == 1

    def test_decision_manual_review(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            decision_stats=make_decision_stats(decisions_by_type={"CONTINUE": 10, "MANUAL_REVIEW": 5}),
        )
        manual_issues = [i for i in issues if i.issue_type == "manual_review_required"]
        assert len(manual_issues) == 1

    def test_decision_rejected(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            decisions=[{"decision_type": "REJECT"}, {"decision_type": "CONTINUE"}],
        )
        reject_issues = [i for i in issues if i.issue_type == "rejected_accounts"]
        assert len(reject_issues) == 1

    def test_parser_ignored(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            parser_data=ParserData(ignored_accounts=["a", "b", "c"]),
        )
        ignored_issues = [i for i in issues if i.issue_type == "ignored_accounts"]
        assert len(ignored_issues) == 1

    def test_parser_no_selected(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            parser_data=ParserData(selected_parser=""),
        )
        no_parser = [i for i in issues if i.issue_type == "no_parser_selected"]
        assert len(no_parser) == 1

    def test_knowledge_no_matches(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            knowledge_data=KnowledgeData(),
        )
        kb_issues = [i for i in issues if i.issue_type == "no_kb_matches"]
        assert len(kb_issues) == 1

    def test_deduplication(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            coverage_issues=[
                {"issue_type": "test", "severity": "HIGH", "detail": "same"},
                {"issue_type": "test", "severity": "HIGH", "detail": "same"},
                {"issue_type": "test", "severity": "HIGH", "detail": "different"},
            ],
        )
        assert len(issues) == 2

    def test_severity_ordering(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            coverage_issues=[
                {"issue_type": "info", "severity": "INFO", "detail": "d1"},
                {"issue_type": "critical", "severity": "CRITICAL", "detail": "d2"},
                {"issue_type": "medium", "severity": "MEDIUM", "detail": "d3"},
            ],
        )
        severities = [i.severity for i in issues]
        assert severities[0] == "CRITICAL"  # first sorted


# =============================================================================
# CONFIDENCE ENGINE TESTS
# =============================================================================

class TestConfidenceEngine:
    def test_no_data(self):
        engine = ConfidenceEngine()
        conf = engine.compute()
        assert conf.overall == 0.0

    def test_full_data(self):
        engine = ConfidenceEngine()
        conf = engine.compute(
            coverage_data=make_coverage_data(overall=0.95),
            decision_stats=make_decision_stats(avg_confidence=0.9),
            validation_data=ValidationData(integrity=FakeIntegrity(overall=0.85)),
            parser_data=ParserData(selected_parser="universal", accounts=[1, 2, 3], raw_accounts=[1, 2, 3]),
            knowledge_data=KnowledgeData(cmcc_matches=["m1"]),
            structure_data=StructureData(family="TRIBUTARIO", template="T14", sections=[{"name": "Activo"}]),
            predictions=PredictionData(confidence_expected=0.8, coverage_expected=0.7),
        )
        assert conf.overall > 0.5
        assert conf.coverage == 0.95
        assert conf.decision == 0.9

    def test_validation_confidence_with_errors(self):
        engine = ConfidenceEngine()
        conf = engine.compute(validation_data=ValidationData(errors=["e1"]))
        assert conf.validation == 0.3

    def test_validation_confidence_with_warnings(self):
        engine = ConfidenceEngine()
        conf = engine.compute(validation_data=ValidationData(warnings=["w1"]))
        assert conf.validation == 0.7

    def test_parser_confidence_no_parser(self):
        engine = ConfidenceEngine()
        conf = engine.compute(parser_data=ParserData(selected_parser=""))
        assert conf.parser == 0.0

    def test_knowledge_confidence_no_data(self):
        engine = ConfidenceEngine()
        conf = engine.compute(knowledge_data=None)
        assert conf.knowledge == 0.0

    def test_knowledge_confidence_empty(self):
        engine = ConfidenceEngine()
        conf = engine.compute(knowledge_data=KnowledgeData())
        assert conf.knowledge == 0.3

    def test_structure_confidence_no_data(self):
        engine = ConfidenceEngine()
        conf = engine.compute(structure_data=StructureData())
        assert conf.structure == 0.0

    def test_structure_confidence_full(self):
        engine = ConfidenceEngine()
        conf = engine.compute(structure_data=StructureData(family="TRIBUTARIO", template="T14", sections=[{"name": "Activo"}]))
        assert conf.structure == 1.0

    def test_die_confidence(self):
        engine = ConfidenceEngine()
        conf = engine.compute(predictions=PredictionData(confidence_expected=0.9, coverage_expected=0.8))
        assert conf.die == 0.85

    def test_weights_property(self):
        engine = ConfidenceEngine()
        w = engine.weights
        assert "coverage" in w


# =============================================================================
# APPROVAL ENGINE TESTS
# =============================================================================

class TestApprovalEngine:
    def test_approve(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.98},
                structural={"overall": 0.92},
                semantic={"overall": 0.90},
                document={"coverage_pct": 0.95},
            ),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            confidence=QAConfidence(overall=0.85),
        )
        assert state == ApprovalState.APPROVED

    def test_manual_review_low_monetary(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.60},
                structural={"overall": 0.90},
                semantic={"overall": 0.90},
                document={"coverage_pct": 0.95},
            ),
            confidence=QAConfidence(overall=0.85),
        )
        assert state == ApprovalState.MANUAL_REVIEW

    def test_manual_review_low_structural(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.98},
                structural={"overall": 0.50},
                semantic={"overall": 0.90},
                document={"coverage_pct": 0.95},
            ),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            confidence=QAConfidence(overall=0.85),
        )
        assert state == ApprovalState.MANUAL_REVIEW

    def test_rejected_not_balance(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(monetary={"coverage_pct": 0.2}),
            structure_data=StructureData(family="NOTA", document_type="ANEXO"),
        )
        assert state == ApprovalState.REJECTED

    def test_rejected_low_monetary(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.1},
                structural={"overall": 0.9},
                semantic={"overall": 0.9},
                document={"coverage_pct": 0.95},
            ),
            structure_data=StructureData(family="TRIBUTARIO"),
            confidence=QAConfidence(overall=0.85),
        )
        assert state == ApprovalState.REJECTED

    def test_learning_new_template(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.95},
                structural={"overall": 0.9},
            ),
            parser_data=ParserData(selected_parser="universal"),
            structure_data=StructureData(family="", template=""),
            confidence=QAConfidence(overall=0.8),
        )
        assert state == ApprovalState.LEARNING

    def test_stress_very_low(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.35},
                structural={"overall": 0.2},
                semantic={"overall": 0.5},
                document={"coverage_pct": 0.5},
            ),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            risk=QARisk(total_risk=85, level=RiskLevel.CRITICAL),
        )
        assert state == ApprovalState.STRESS

    def test_failed_no_parser(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(),
            parser_data=ParserData(selected_parser=""),
        )
        assert state == ApprovalState.FAILED

    def test_failed_no_coverage(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=None,
            parser_data=ParserData(selected_parser="universal"),
        )
        assert state == ApprovalState.FAILED

    def test_approve_with_warnings(self):
        engine = ApprovalEngine()
        high_issues = [QAIssue(source="test", issue_type="w", severity="HIGH")]
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.90},
                structural={"overall": 0.80},
                semantic={"overall": 0.85},
                document={"coverage_pct": 0.92},
            ),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            confidence=QAConfidence(overall=0.65),
            issues=high_issues,
        )
        assert state == ApprovalState.APPROVED_WITH_WARNINGS

    def test_critical_issues_block_approve(self):
        engine = ApprovalEngine()
        critical_issues = [QAIssue(source="test", issue_type="critical", severity="CRITICAL")]
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.98},
                structural={"overall": 0.95},
                semantic={"overall": 0.95},
                document={"coverage_pct": 0.95},
            ),
            confidence=QAConfidence(overall=0.9),
            issues=critical_issues,
        )
        assert state != ApprovalState.APPROVED
        # should be manual review or rejected

    def test_default_to_manual_review(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.70},
                structural={"overall": 0.60},
                semantic={"overall": 0.60},
                document={"coverage_pct": 0.70},
            ),
            confidence=QAConfidence(overall=0.5),
            structure_data=StructureData(family="TRIBUTARIO"),
        )
        assert state == ApprovalState.MANUAL_REVIEW


# =============================================================================
# RECOMMENDATION ENGINE TESTS
# =============================================================================

class TestRecommendationEngine:
    def test_approved(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.APPROVED)
        assert len(recs) == 1
        assert "aprobado" in recs[0].message.lower()

    def test_manual_review(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.MANUAL_REVIEW)
        assert len(recs) >= 1
        assert "revisión manual" in recs[0].message.lower()

    def test_rejected(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.REJECTED)
        assert len(recs) >= 1
        assert "rechazado" in recs[0].message.lower()

    def test_learning(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.LEARNING)
        assert len(recs) >= 1
        assert "aprendizaje" in recs[0].message.lower() or "gold standard" in recs[0].message.lower()

    def test_stress(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.STRESS)
        assert len(recs) >= 1
        assert "stress" in recs[0].message.lower() or "STRESS" in recs[0].message

    def test_failed(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.FAILED)
        assert len(recs) >= 1
        assert "falló" in recs[0].message.lower()

    def test_approved_with_warnings(self):
        engine = RecommendationEngine()
        recs = engine.generate(approval_state=ApprovalState.APPROVED_WITH_WARNINGS)
        assert len(recs) >= 1
        assert "advertencias" in recs[0].message.lower() or "warnings" in recs[0].message.lower()

    def test_risk_recommendations(self):
        engine = RecommendationEngine()
        recs = engine.generate(
            approval_state=ApprovalState.MANUAL_REVIEW,
            risk=QARisk(monetary_risk=80, structural_risk=70, operational_risk=60, total_risk=75, level=RiskLevel.HIGH),
        )
        assert len(recs) >= 3  # state + risk recs

    def test_coverage_recommendations(self):
        engine = RecommendationEngine()
        recs = engine.generate(
            approval_state=ApprovalState.MANUAL_REVIEW,
            coverage_data=make_coverage_data(monetary={"coverage_pct": 0.8, "total_amount": 1000000.0, "explained_amount": 500000.0}),
        )
        monetary_recs = [r for r in recs if "diferencia" in r.message.lower() or "monetaria" in r.message.lower()]
        assert len(monetary_recs) >= 1


# =============================================================================
# SELF QA ADAPTER TESTS
# =============================================================================

class TestSelfQAAdapter:
    def test_run_stores_self_qa(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        sqa = ctx.get_custom("self_qa")
        assert sqa is not None
        assert "approval_state" in sqa

    def test_run_stores_state(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa_state") is not None

    def test_run_stores_confidence(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa_confidence") is not None

    def test_run_stores_risk(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa_risk") is not None

    def test_run_stores_risk_level(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa_risk_level") is not None

    def test_run_stores_gates(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        gates = ctx.get_custom("self_qa_gates")
        assert gates is not None
        assert len(gates) == 10

    def test_run_stores_issues(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        issues = ctx.get_custom("self_qa_issues")
        assert issues is not None

    def test_run_stores_reason(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        reason = ctx.get_custom("self_qa_reason")
        assert reason is not None

    def test_run_with_full_data(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data(
            monetary={"coverage_pct": 0.98},
            structural={"overall": 0.95},
            semantic={"overall": 0.95},
            document={"coverage_pct": 0.95},
        ))
        ctx.set_custom("decision_stats", make_decision_stats(avg_confidence=0.9))
        ctx.set_metadata(DocumentMetadata(company="TEST"))
        ctx.set_structure(StructureData(family="TRIBUTARIO", template="T14"))
        ctx = adapter.run(ctx)
        state = ctx.get_custom("self_qa_state")
        assert state == "APPROVED" or state == "MANUAL_REVIEW"

    def test_run_roundtrip(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        sqa_dict = ctx.get_custom("self_qa")
        result = QAResult.from_dict(sqa_dict)
        assert result.approval_state is not None
        assert len(result.gates) == 10


# =============================================================================
# STATISTICS TESTS
# =============================================================================

class TestQAStatisticsCollector:
    def test_empty(self):
        collector = QAStatisticsCollector()
        summary = collector.compute()
        assert summary.total_documents == 0

    def test_single_approved(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(
            approval_state=ApprovalState.APPROVED,
            confidence=QAConfidence(overall=0.95),
            risk=QARisk(total_risk=10, level=RiskLevel.LOW),
        ))
        summary = collector.compute()
        assert summary.total_documents == 1
        assert summary.approved == 1
        assert summary.avg_confidence == 0.95

    def test_multiple_states(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)))
        collector.add(QAResult(approval_state=ApprovalState.REJECTED, confidence=QAConfidence(overall=0.3), risk=QARisk(total_risk=80)))
        collector.add(QAResult(approval_state=ApprovalState.MANUAL_REVIEW, confidence=QAConfidence(overall=0.6), risk=QARisk(total_risk=50)))
        summary = collector.compute()
        assert summary.approved == 1
        assert summary.rejected == 1
        assert summary.manual_review == 1
        assert summary.total_documents == 3

    def test_distribution(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)))
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.95), risk=QARisk(total_risk=5)))
        summary = collector.compute()
        assert summary.distribution["APPROVED"] == 2

    def test_by_template(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"template": "T14"})
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.8), risk=QARisk(total_risk=20)),
                      {"template": "T14"})
        summary = collector.compute()
        assert summary.by_template["T14"]["count"] == 2
        assert summary.by_template["T14"]["avg_confidence"] == 0.85

    def test_by_parser(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"parser": "universal"})
        summary = collector.compute()
        assert summary.by_parser["universal"]["count"] == 1

    def test_by_company(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"company": "EMPRESA"})
        summary = collector.compute()
        assert summary.by_company["EMPRESA"]["count"] == 1

    def test_by_family(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"family": "TRIBUTARIO"})
        summary = collector.compute()
        assert summary.by_family["TRIBUTARIO"]["count"] == 1

    def test_by_year(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"year": 2024})
        summary = collector.compute()
        assert summary.by_year["2024"]["count"] == 1

    def test_add_many(self):
        collector = QAStatisticsCollector()
        results = [
            QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
            QAResult(approval_state=ApprovalState.REJECTED, confidence=QAConfidence(overall=0.3), risk=QARisk(total_risk=80)),
        ]
        collector.add_many(results)
        assert collector.count == 2

    def test_clear(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)))
        collector.clear()
        assert collector.count == 0


# =============================================================================
# REPORT GENERATOR TESTS
# =============================================================================

class TestQaReportGenerator:
    def test_generate_full_report(self):
        gen = QaReportGenerator()
        result = QAResult(
            approval_state=ApprovalState.APPROVED,
            confidence=QAConfidence(overall=0.95),
            risk=QARisk(total_risk=10, level=RiskLevel.LOW),
            gates=[QualityGate(name="monetary", passed=True, score=0.98, weight=0.95, detail="OK")],
        )
        report = gen.generate_full_report(result)
        assert "Self QA Validation Report" in report
        assert "APPROVED" in report

    def test_report_with_issues(self):
        gen = QaReportGenerator()
        result = QAResult(
            approval_state=ApprovalState.MANUAL_REVIEW,
            issues=[QAIssue(source="coverage", issue_type="low", severity="HIGH", detail="test")],
        )
        report = gen.generate_full_report(result)
        assert "Issues" in report or "issues" in report

    def test_report_with_document_info(self):
        gen = QaReportGenerator()
        result = QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10))
        report = gen.generate_full_report(result, {"source_file": "test.pdf", "company": "TEST", "year": 2024})
        assert "test.pdf" in report
        assert "TEST" in report

    def test_report_with_recommendations(self):
        gen = QaReportGenerator()
        result = QAResult(
            approval_state=ApprovalState.REJECTED,
            recommendations=[QARecommendation(message="Rechazado", actions=["verificar"])],
        )
        report = gen.generate_full_report(result)
        assert "Recomendaciones" in report or "recomendaciones" in report.lower()

    def test_generate_summary_report(self):
        gen = QaReportGenerator()
        summary = QASummary(
            total_documents=10,
            approved=5,
            manual_review=3,
            rejected=2,
            avg_confidence=0.8,
            avg_risk=35.0,
        )
        report = gen.generate_summary_report(summary)
        assert "Self QA Summary Report" in report
        assert "5" in report  # approved count

    def test_summary_with_distributions(self):
        gen = QaReportGenerator()
        summary = QASummary(
            total_documents=2,
            approved=1,
            rejected=1,
            avg_confidence=0.7,
            by_template={"T14": {"avg_confidence": 0.8, "count": 2}},
            by_parser={"universal": {"avg_confidence": 0.7, "count": 2}},
        )
        report = gen.generate_summary_report(summary)
        assert "T14" in report
        assert "universal" in report

    def test_save_report(self, tmp_path):
        gen = QaReportGenerator()
        result = QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.95), risk=QARisk(total_risk=10))
        report = gen.generate_full_report(result)
        path = gen.save_report(report, str(tmp_path / "reports" / "self_qa_test.md"))
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Self QA Validation Report" in content


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    def test_empty_coverage_data(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa") is not None

    def test_risk_calculator_no_data(self):
        calc = RiskCalculator()
        risk = calc.compute()
        assert risk.total_risk >= 0
        assert risk.level in RiskLevel

    def test_quality_gate_no_data(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate()
        assert all(g.score == 0.0 for g in gates if g.name not in ("structure_valid",))
        assert all(g.passed is False for g in gates)

    def test_confidence_no_data(self):
        engine = ConfidenceEngine()
        conf = engine.compute()
        assert conf.overall == 0.0

    def test_approval_default_to_fail(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=None,
            parser_data=ParserData(selected_parser=""),
        )
        assert state in (ApprovalState.FAILED, ApprovalState.REJECTED)

    def test_approval_with_all_none(self):
        engine = ApprovalEngine()
        state, reason = engine.decide()
        # Should fail because no coverage data
        assert state == ApprovalState.FAILED

    def test_risk_all_max(self):
        calc = RiskCalculator()
        risk = calc.compute(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.0},
                structural={"overall": 0.0},
                semantic={"overall": 0.0},
                document={"coverage_pct": 0.0},
            ),
            validation_data=ValidationData(errors=["e1"]),
            parser_data=ParserData(selected_parser=""),
        )
        assert risk.total_risk > 50

    def test_serialization_complex_result(self):
        r = QAResult(
            approval_state=ApprovalState.APPROVED_WITH_WARNINGS,
            confidence=QAConfidence(overall=0.85, coverage=0.9, decision=0.8, validation=0.85, parser=0.7, knowledge=0.6, structure=0.8, die=0.5),
            risk=QARisk(document_risk=10, structural_risk=20, monetary_risk=5, semantic_risk=15, operational_risk=10, total_risk=12, level=RiskLevel.LOW),
            gates=[QualityGate(name="g1", passed=True, score=0.9, weight=0.8, detail="ok") for _ in range(10)],
            issues=[QAIssue(source="s", issue_type="t", severity="c", detail="d") for _ in range(5)],
            recommendations=[QARecommendation(message="m", actions=["a"])],
            decision_reason="test",
        )
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        r2 = QAResult.from_dict(loaded)
        assert r2.approval_state == ApprovalState.APPROVED_WITH_WARNINGS
        assert len(r2.gates) == 10
        assert len(r2.issues) == 5
        assert r2.confidence.overall == 0.85
        assert r2.risk.total_risk == 12

    def test_adapter_with_validation_errors(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx.set_custom("validation_errors", ["critical error"])
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa") is not None


# =============================================================================
# PIPELINE INTEGRATION TESTS
# =============================================================================

class TestPipelineIntegration:
    def test_sqa_in_pipeline_v2_import(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pipeline = HomologationPipelineV2(db_path=":memory:")
        assert pipeline is not None
        assert hasattr(pipeline, "_adapter_sqa")

    def test_sqa_adapter_with_coverage(self):
        from self_qa_engine import SelfQAAdapter
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data(
            monetary={"coverage_pct": 0.98},
            structural={"overall": 0.95},
            semantic={"overall": 0.95},
            document={"coverage_pct": 1.0},
        ))
        ctx.set_custom("decision_stats", make_decision_stats(avg_confidence=0.9))
        ctx = adapter.run(ctx)
        assert ctx.get_custom("self_qa_state") is not None

    def test_sqa_result_roundtrip_through_context(self):
        adapter = SelfQAAdapter()
        ctx = DocumentContext()
        ctx.set_custom("coverage", make_coverage_data())
        ctx = adapter.run(ctx)
        sqa = ctx.get_custom("self_qa")
        result = QAResult.from_dict(sqa)
        assert result.approval_state is not None
        # Re-serialize and verify
        json.dumps(result.to_dict())

    def test_statistics_with_metadata(self):
        collector = QAStatisticsCollector()
        collector.add(QAResult(approval_state=ApprovalState.APPROVED, confidence=QAConfidence(overall=0.9), risk=QARisk(total_risk=10)),
                      {"template": "T14", "parser": "universal", "company": "A", "year": 2024})
        collector.add(QAResult(approval_state=ApprovalState.MANUAL_REVIEW, confidence=QAConfidence(overall=0.6), risk=QARisk(total_risk=50)),
                      {"template": "T14", "parser": "universal", "company": "B", "year": 2024})
        summary = collector.compute()
        assert summary.by_template["T14"]["count"] == 2
        assert summary.by_company["A"]["count"] == 1
        assert summary.by_company["B"]["count"] == 1
        assert summary.by_parser["universal"]["count"] == 2


# =============================================================================
# SERIALIZATION TESTS
# =============================================================================

class TestSerialization:
    def test_quality_gate_json(self):
        g = QualityGate(name="test", passed=True, score=0.9, weight=0.8, detail="detail")
        json_str = json.dumps(g.to_dict())
        loaded = json.loads(json_str)
        g2 = QualityGate.from_dict(loaded)
        assert g2.name == "test"
        assert g2.passed is True

    def test_qa_issue_json(self):
        i = QAIssue(source="coverage", issue_type="low_coverage", severity="HIGH", detail="test", impact=5000)
        json_str = json.dumps(i.to_dict())
        loaded = json.loads(json_str)
        i2 = QAIssue.from_dict(loaded)
        assert i2.source == "coverage"
        assert i2.impact == 5000

    def test_qa_risk_json(self):
        r = QARisk(total_risk=75, level=RiskLevel.HIGH)
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        r2 = QARisk.from_dict(loaded)
        assert r2.total_risk == 75
        assert r2.level == RiskLevel.HIGH

    def test_qa_confidence_json(self):
        c = QAConfidence(overall=0.88, coverage=0.9, decision=0.85)
        json_str = json.dumps(c.to_dict())
        loaded = json.loads(json_str)
        c2 = QAConfidence.from_dict(loaded)
        assert c2.overall == 0.88

    def test_qa_recommendation_json(self):
        r = QARecommendation(message="test", actions=["a", "b"])
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        r2 = QARecommendation.from_dict(loaded)
        assert r2.message == "test"
        assert len(r2.actions) == 2

    def test_qa_summary_json(self):
        s = QASummary(total_documents=5, approved=3, avg_confidence=0.85)
        json_str = json.dumps(s.to_dict())
        loaded = json.loads(json_str)
        s2 = QASummary.from_dict(loaded)
        assert s2.total_documents == 5
        assert s2.approved == 3

    def test_risk_calculator_all_same_weights(self):
        calc = RiskCalculator(weights={"document": 0.2, "structural": 0.2, "monetary": 0.2, "semantic": 0.2, "operational": 0.2})
        risk = calc.compute(coverage_data=make_coverage_data(
            monetary={"coverage_pct": 0.9}, structural={"overall": 0.9},
            semantic={"overall": 0.9}, document={"coverage_pct": 0.9},
        ))
        assert risk.total_risk == 10.0

    def test_confidence_all_perfect(self):
        engine = ConfidenceEngine()
        conf = engine.compute(
            coverage_data=make_coverage_data(overall=1.0),
            decision_stats=make_decision_stats(avg_confidence=1.0),
            validation_data=ValidationData(integrity=FakeIntegrity(overall=1.0)),
            parser_data=ParserData(selected_parser="x", accounts=[1, 2], raw_accounts=[1, 2]),
            knowledge_data=KnowledgeData(cmcc_matches=["m1", "m2", "m3"]),
            structure_data=StructureData(family="X", template="Y", sections=[{"name": "Z"}]),
            predictions=PredictionData(confidence_expected=1.0, coverage_expected=1.0),
        )
        assert conf.overall >= 0.9

    def test_approval_stress_by_risk(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.6}, structural={"overall": 0.5},
                semantic={"overall": 0.6}, document={"coverage_pct": 0.6},
            ),
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            risk=QARisk(total_risk=85, level=RiskLevel.CRITICAL),
        )
        assert state == ApprovalState.STRESS

    def test_approval_critical_issues_reject(self):
        engine = ApprovalEngine()
        state, reason = engine.decide(
            coverage_data=make_coverage_data(
                monetary={"coverage_pct": 0.2}, structural={"overall": 0.9},
            ),
            structure_data=StructureData(family="NOTA", document_type="ANEXO"),
        )
        assert state == ApprovalState.REJECTED

    def test_quality_gate_partial_data(self):
        evaluator = QualityGateEvaluator()
        gates = evaluator.evaluate(
            coverage_data=make_coverage_data(),
            parser_data=ParserData(selected_parser="universal"),
        )
        passed = sum(1 for g in gates if g.passed)
        assert 3 <= passed <= 9

    def test_issue_analyzer_no_duplicates(self):
        analyzer = IssueAnalyzer()
        issues = analyzer.consolidate(
            coverage_issues=[
                {"issue_type": "a", "severity": "HIGH", "detail": "same"},
                {"issue_type": "a", "severity": "HIGH", "detail": "same"},
            ],
            validation_data=ValidationData(errors=["e1"]),
            decision_stats=make_decision_stats(conflicts_detected=1),
        )
        assert len(issues) == 4

    def test_qa_summary_zero_docs(self):
        s = QASummary()
        assert s.total_documents == 0
        assert s.avg_confidence == 0.0

    def test_qa_summary_full_state_counts(self):
        s = QASummary(
            total_documents=100, approved=50, approved_with_warnings=10,
            manual_review=20, learning=5, stress=3, rejected=10, failed=2,
            avg_confidence=0.75, avg_risk=30.0,
        )
        total = s.approved + s.approved_with_warnings + s.manual_review + s.learning + s.stress + s.rejected + s.failed
        assert total == 100
        assert s.avg_risk == 30.0

    def test_recommendation_engine_risk_high(self):
        engine = RecommendationEngine()
        recs = engine.generate(
            approval_state=ApprovalState.MANUAL_REVIEW,
            risk=QARisk(monetary_risk=80, structural_risk=80, operational_risk=80, total_risk=85, level=RiskLevel.CRITICAL),
        )
        risk_msgs = [r for r in recs if "riesgo" in r.message.lower() or "Riesgo" in r.message]
        assert len(risk_msgs) >= 2

    def test_statistics_with_no_data(self):
        stats = QAStatisticsCollector()
        result = stats.compute()
        assert result.total_documents == 0
