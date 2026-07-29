from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pytest

from decision_engine import (
    Decision, DecisionEvidence, DecisionConflict, DecisionScore,
    DecisionExplanation, DecisionStatistics, DecisionType, ConflictSeverity,
    EvidenceCollector, EvidenceAggregator, ConflictResolver,
    ConfidenceCalculator, DEFAULT_WEIGHTS, ExplanationGenerator,
    Scorer, DecisionStatisticsCollector,
)
from decision_engine.models import DecisionEvidence as DE

from document_context import DocumentContext
from document_context.models import (
    DocumentMetadata, ParserData, KnowledgeData, ValidationData,
    StructureData, PredictionData,
)


# =========================================================================
# Models Tests
# =========================================================================

class TestDecisionModels:
    def test_decision_evidence_defaults(self):
        e = DecisionEvidence(source="parser", field="accounts", value=10)
        assert e.confidence == 0.0
        assert e.detail == ""

    def test_decision_evidence_to_dict(self):
        e = DecisionEvidence(source="parser", field="accounts", value=10, confidence=0.95)
        d = e.to_dict()
        assert d["source"] == "parser"
        assert d["confidence"] == 0.95

    def test_decision_conflict_defaults(self):
        a = DecisionEvidence(source="p1", field="f1", value="A")
        b = DecisionEvidence(source="p2", field="f2", value="B")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.HIGH, reason="test")
        assert c.resolution == ""

    def test_decision_conflict_to_dict(self):
        a = DecisionEvidence(source="p1", field="f1", value="A")
        b = DecisionEvidence(source="p2", field="f2", value="B")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.CRITICAL, reason="conflict")
        d = c.to_dict()
        assert d["severity"] == "CRITICAL"
        assert d["reason"] == "conflict"

    def test_decision_score_defaults(self):
        s = DecisionScore()
        assert s.confidence == 0.0
        assert s.weighted_total == 0.0

    def test_decision_score_weighted_total(self):
        s = DecisionScore(confidence=0.9, coverage=0.8, evidence_quality=0.7, consistency=0.6, learning_weight=0.5)
        expected = 0.40 * 0.9 + 0.25 * 0.8 + 0.15 * 0.7 + 0.10 * 0.6 + 0.10 * 0.5
        assert s.weighted_total == round(expected, 4)

    def test_decision_score_to_dict(self):
        s = DecisionScore(confidence=0.85, coverage=0.75)
        d = s.to_dict()
        assert "confidence" in d
        assert "weighted_total" in d

    def test_decision_explanation_defaults(self):
        exp = DecisionExplanation()
        assert exp.account_code == ""

    def test_decision_explanation_to_dict(self):
        exp = DecisionExplanation(
            account_code="AC.01", account_name="Caja",
            classified_code="AC.01", final_confidence=0.95,
            reasons=["Alta confianza"],
            confidence_breakdown={"parser": 0.9},
        )
        d = exp.to_dict()
        assert d["account_code"] == "AC.01"
        assert d["final_confidence"] == 0.95

    def test_decision_statistics_defaults(self):
        s = DecisionStatistics()
        assert s.total_decisions == 0

    def test_decision_statistics_to_dict(self):
        s = DecisionStatistics(total_decisions=10, avg_confidence=0.85)
        d = s.to_dict()
        assert d["total_decisions"] == 10

    def test_decision_defaults(self):
        d = Decision()
        assert d.decision_type == DecisionType.CONTINUE
        assert d.final_code == ""

    def test_decision_to_dict(self):
        d = Decision(
            account_code="AC.01", account_name="Caja",
            decision_type=DecisionType.CONTINUE, final_code="AC.01",
            confidence=0.95,
        )
        dd = d.to_dict()
        assert dd["account_code"] == "AC.01"
        assert dd["confidence"] == 0.95

    def test_decision_with_evidence(self):
        ev = DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.9)
        d = Decision(account_code="AC.01", evidence=[ev])
        assert len(d.evidence) == 1

    def test_decision_with_conflicts(self):
        a = DecisionEvidence(source="p1", field="f", value="A")
        b = DecisionEvidence(source="p2", field="f", value="B")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.HIGH, reason="x")
        d = Decision(account_code="X", conflicts=[c])
        assert d.conflicts[0].severity == ConflictSeverity.HIGH

    def test_decision_with_score(self):
        s = DecisionScore(confidence=0.8)
        d = Decision(account_code="X", score=s)
        assert d.score.confidence == 0.8

    def test_decision_with_explanation(self):
        exp = DecisionExplanation(final_confidence=0.9)
        d = Decision(account_code="X", explanation=exp)
        assert d.explanation.final_confidence == 0.9

    def test_decision_timestamp(self):
        d = Decision()
        assert d.timestamp is not None

    def test_conflict_severity_values(self):
        assert ConflictSeverity.CRITICAL.value == "CRITICAL"
        assert ConflictSeverity.HIGH.value == "HIGH"
        assert ConflictSeverity.MEDIUM.value == "MEDIUM"
        assert ConflictSeverity.LOW.value == "LOW"
        assert ConflictSeverity.NONE.value == "NONE"

    def test_decision_type_values(self):
        assert DecisionType.CONTINUE.value == "CONTINUE"
        assert DecisionType.MANUAL_REVIEW.value == "MANUAL_REVIEW"
        assert DecisionType.REJECT.value == "REJECT"
        assert DecisionType.STRESS.value == "STRESS"
        assert DecisionType.LEARNING.value == "LEARNING"


# =========================================================================
# EvidenceCollector Tests
# =========================================================================

class TestEvidenceCollector:
    def test_collect_all_empty_context(self):
        ctx = DocumentContext()
        ev = EvidenceCollector.collect_all(ctx)
        assert isinstance(ev, list)

    def test_collect_all_with_parser(self):
        ctx = DocumentContext()
        ctx._parser = ParserData(selected_parser="PDF", raw_accounts=[1, 2, 3])
        ctx._write_once.add("parser")
        ev = EvidenceCollector.collect_all(ctx)
        parser_ev = [e for e in ev if e.source == "parser"]
        assert len(parser_ev) > 0

    def test_collect_from_parser_empty(self):
        ctx = DocumentContext()
        ev = EvidenceCollector._from_parser(ctx)
        assert ev == []

    def test_collect_from_parser_with_data(self):
        ctx = DocumentContext()
        ctx._parser = ParserData(selected_parser="PDF", raw_accounts=[1])
        ctx._write_once.add("parser")
        ev = EvidenceCollector._from_parser(ctx)
        assert len(ev) >= 2

    def test_collect_from_knowledge_empty(self):
        ctx = DocumentContext()
        ev = EvidenceCollector._from_knowledge(ctx)
        assert ev == []

    def test_collect_from_knowledge_with_data(self):
        ctx = DocumentContext()
        ctx._knowledge = KnowledgeData(learning_hits=[{"a": 1}], dictionary_matches=[{"b": 2}])
        ctx._write_once.add("knowledge")
        ev = EvidenceCollector._from_knowledge(ctx)
        assert len(ev) >= 2

    def test_collect_from_structure_empty(self):
        ctx = DocumentContext()
        ev = EvidenceCollector._from_structure(ctx)
        assert ev == []

    def test_collect_from_structure_with_data(self):
        ctx = DocumentContext()
        ctx._structure = StructureData(family="BALANCE", template="T1", column_layout="estandar")
        ctx._write_once.add("structure")
        ev = EvidenceCollector._from_structure(ctx)
        assert len(ev) >= 3

    def test_collect_from_validation_empty(self):
        ctx = DocumentContext()
        ev = EvidenceCollector._from_validation(ctx)
        assert ev == []

    def test_collect_from_validation_with_data(self):
        ctx = DocumentContext()
        ctx._validation = ValidationData()
        ctx._write_once.add("validation")
        ev = EvidenceCollector._from_validation(ctx)
        assert len(ev) >= 1

    def test_collect_from_die_no_data(self):
        ctx = DocumentContext()
        ev = EvidenceCollector._from_die(ctx)
        assert ev == []

    def test_collect_from_die_with_prediction(self):
        ctx = DocumentContext()
        ctx._prediction = PredictionData(confidence_expected=0.85, coverage_expected=0.75)
        ctx._write_once.add("prediction")
        ev = EvidenceCollector._from_die(ctx)
        assert len(ev) >= 2

    def test_collect_from_die_with_report(self):
        ctx = DocumentContext()
        ctx.set_custom("die_report", {"type": "balance"})
        ctx._prediction = PredictionData()
        ctx._write_once.add("prediction")
        ev = EvidenceCollector._from_die(ctx)
        assert len(ev) >= 1

    def test_collect_validation_with_errors(self):
        ctx = DocumentContext()
        ctx._validation = ValidationData(errors=["err1"])
        ctx._write_once.add("validation")
        ev = EvidenceCollector._from_validation(ctx)
        assert any(e.field == "errors" for e in ev)

    def test_collect_validation_with_warnings(self):
        ctx = DocumentContext()
        ctx._validation = ValidationData(warnings=["warn1"])
        ctx._write_once.add("validation")
        ev = EvidenceCollector._from_validation(ctx)
        assert any(e.field == "warnings" for e in ev)


# =========================================================================
# ConflictResolver Tests
# =========================================================================

class TestConflictResolver:
    def test_resolve_no_conflicts(self):
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01"),
            DecisionEvidence(source="kb", field="match", value="AC.01"),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        assert len(conflicts) == 0

    def test_resolve_detects_conflict(self):
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.9),
            DecisionEvidence(source="kb", field="code", value="PC.01", confidence=0.9),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        assert len(conflicts) >= 1

    def test_resolve_critical_severity(self):
        ev = [
            DecisionEvidence(source="parser", field="account_type", value="ACTIVO", confidence=0.9),
            DecisionEvidence(source="kb", field="account_type", value="PASIVO", confidence=0.9),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        assert any(c.severity == ConflictSeverity.CRITICAL for c in conflicts)

    def test_resolve_same_source_no_conflict(self):
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01"),
            DecisionEvidence(source="parser", field="code", value="AC.01"),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        assert len(conflicts) == 0

    def test_resolve_different_fields_no_conflict(self):
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01"),
            DecisionEvidence(source="kb", field="match", value="yes"),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        assert len(conflicts) == 0

    def test_determine_severity_high(self):
        cr = ConflictResolver()
        a = DecisionEvidence(source="a", field="f", value="X", confidence=0.7)
        b = DecisionEvidence(source="b", field="f", value="Y", confidence=0.7)
        sev = cr._determine_severity(a, b)
        assert sev == ConflictSeverity.HIGH

    def test_determine_severity_medium(self):
        cr = ConflictResolver()
        a = DecisionEvidence(source="a", field="f", value="X", confidence=0.4)
        b = DecisionEvidence(source="b", field="f", value="Y", confidence=0.4)
        sev = cr._determine_severity(a, b)
        assert sev == ConflictSeverity.MEDIUM

    def test_group_by_field(self):
        ev = [
            DecisionEvidence(source="a", field="code", value="X"),
            DecisionEvidence(source="b", field="code", value="Y"),
            DecisionEvidence(source="c", field="type", value="Z"),
        ]
        cr = ConflictResolver()
        grouped = cr._group_by_field(ev)
        assert "code" in grouped
        assert "type" in grouped
        assert len(grouped["code"]) == 2

    def test_resolve_empty_list(self):
        cr = ConflictResolver()
        assert cr.resolve([]) == []


# =========================================================================
# ConfidenceCalculator Tests
# =========================================================================

class TestConfidenceCalculator:
    def test_default_weights_exist(self):
        calc = ConfidenceCalculator()
        assert "parser" in calc.weights
        assert "knowledge" in calc.weights

    def test_default_weights_sum_to_one(self):
        calc = ConfidenceCalculator()
        total = sum(calc.weights.values())
        assert abs(total - 1.0) < 0.001

    def test_compute_single_evidence(self):
        calc = ConfidenceCalculator()
        ev = [DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.9)]
        score = calc.compute(ev)
        assert 0 < score <= 1.0

    def test_compute_multiple_evidence(self):
        calc = ConfidenceCalculator()
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.9),
            DecisionEvidence(source="knowledge", field="match", value="yes", confidence=0.8),
        ]
        score = calc.compute(ev)
        assert 0 < score <= 1.0

    def test_compute_empty_evidence(self):
        calc = ConfidenceCalculator()
        assert calc.compute([]) == 0.0

    def test_compute_per_module(self):
        calc = ConfidenceCalculator()
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.9),
            DecisionEvidence(source="knowledge", field="match", value="yes", confidence=0.8),
        ]
        by_mod = calc.compute_per_module(ev)
        assert "parser" in by_mod
        assert "knowledge" in by_mod

    def test_custom_weights(self):
        w = {"parser": 0.5, "knowledge": 0.5}
        calc = ConfidenceCalculator(weights=w)
        assert calc.weights["parser"] == 0.5

    def test_weights_partial_override_no_normalize(self):
        w = {"parser": 1.0, "knowledge": 1.0}
        calc = ConfidenceCalculator(weights=w)
        assert calc.weights["parser"] == 1.0
        assert calc.weights["knowledge"] == 1.0

    def test_compute_averages_by_module(self):
        calc = ConfidenceCalculator()
        ev = [
            DecisionEvidence(source="parser", field="a", value="x", confidence=0.9),
            DecisionEvidence(source="parser", field="b", value="x", confidence=0.7),
            DecisionEvidence(source="knowledge", field="c", value="x", confidence=0.8),
        ]
        total = calc.compute(ev)
        assert 0 < total <= 1.0


# =========================================================================
# Scorer Tests
# =========================================================================

class TestScorer:
    def test_scorer_defaults(self):
        s = Scorer()
        score = s.compute([], None)
        assert score.confidence == 0.0
        assert score.coverage == 0.0

    def test_scorer_confidence(self):
        s = Scorer()
        ev = [DecisionEvidence(source="p", field="f", confidence=0.9)]
        score = s.compute(ev)
        assert score.confidence == 0.9

    def test_scorer_coverage(self):
        s = Scorer()
        ctx = DocumentContext()
        ctx.set_custom("classified", [{"a": 1}])
        ctx.set_custom("ignored", [{"b": 2}])
        score = s.compute([], ctx)
        assert score.coverage == 0.5

    def test_scorer_coverage_no_data(self):
        s = Scorer()
        score = s.compute([], None)
        assert score.coverage == 0.0

    def test_scorer_evidence_quality_high(self):
        s = Scorer()
        ev = [
            DecisionEvidence(source="p", field="f", confidence=0.9),
            DecisionEvidence(source="k", field="f", confidence=0.8),
        ]
        score = s.compute(ev)
        assert score.evidence_quality == 1.0

    def test_scorer_evidence_quality_mixed(self):
        s = Scorer()
        ev = [
            DecisionEvidence(source="p", field="f", confidence=0.9),
            DecisionEvidence(source="k", field="f", confidence=0.3),
        ]
        score = s.compute(ev)
        assert 0 < score.evidence_quality < 1.0

    def test_scorer_consistency_perfect(self):
        s = Scorer()
        ev = [
            DecisionEvidence(source="p", field="f", confidence=0.8),
            DecisionEvidence(source="k", field="f", confidence=0.8),
        ]
        score = s.compute(ev)
        assert score.consistency == 1.0

    def test_scorer_consistency_single(self):
        s = Scorer()
        ev = [DecisionEvidence(source="p", field="f", confidence=0.8)]
        score = s.compute(ev)
        assert score.consistency == 1.0

    def test_scorer_learning_weight(self):
        s = Scorer()
        ctx = DocumentContext()
        ctx._knowledge = KnowledgeData(learning_hits=[{"a": 1}, {"b": 2}], dictionary_matches=[{"c": 3}])
        ctx._write_once.add("knowledge")
        score = s.compute([], ctx)
        assert score.learning_weight > 0

    def test_scorer_learning_weight_no_knowledge(self):
        s = Scorer()
        score = s.compute([], None)
        assert score.learning_weight == 0.0

    def test_scorer_learning_weight_capped(self):
        s = Scorer()
        ctx = DocumentContext()
        ctx._knowledge = KnowledgeData(learning_hits=[{"a": 1}] * 50)
        ctx._write_once.add("knowledge")
        score = s.compute([], ctx)
        assert score.learning_weight == 1.0


# =========================================================================
# ExplanationGenerator Tests
# =========================================================================

class TestExplanationGenerator:
    def test_generate_basic(self):
        gen = ExplanationGenerator()
        ev = [DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.95)]
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, [])
        assert exp.account_code == "AC.01"
        assert exp.final_confidence > 0

    def test_generate_reasons_high_confidence(self):
        gen = ExplanationGenerator()
        ev = [
            DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.95),
            DecisionEvidence(source="knowledge", field="match", value="yes", confidence=0.9),
        ]
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, [])
        assert any("Alta confianza" in r for r in exp.reasons)

    def test_generate_reasons_medium_confidence(self):
        gen = ExplanationGenerator()
        ev = [DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.6)]
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, [])
        assert any("Confianza media" in r for r in exp.reasons)

    def test_generate_conflict_in_reasons(self):
        gen = ExplanationGenerator()
        ev = [
            DecisionEvidence(source="parser", field="type", value="ACTIVO", confidence=0.9),
            DecisionEvidence(source="kb", field="type", value="PASIVO", confidence=0.9),
        ]
        cr = ConflictResolver()
        conflicts = cr.resolve(ev)
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, conflicts)
        assert any("Conflicto" in r for r in exp.reasons)

    def test_generate_evidence_summary(self):
        gen = ExplanationGenerator()
        ev = [DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.95)]
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, [])
        assert len(exp.evidence_summary) >= 1

    def test_generate_confidence_breakdown(self):
        gen = ExplanationGenerator()
        ev = [DecisionEvidence(source="parser", field="code", value="AC.01", confidence=0.95)]
        exp = gen.generate("AC.01", "Caja", "AC.01", ev, [])
        assert "parser" in exp.confidence_breakdown

    def test_generate_summary_empty(self):
        gen = ExplanationGenerator()
        summary = gen.generate_summary([])
        assert "No hay explicaciones" in summary

    def test_generate_summary_with_explanations(self):
        gen = ExplanationGenerator()
        exp = DecisionExplanation(
            account_code="AC.01", account_name="Caja",
            classified_code="AC.01", final_confidence=0.95,
            reasons=["Alta confianza"],
        )
        summary = gen.generate_summary([exp])
        assert "AC.01" in summary
        assert "Caja" in summary


# =========================================================================
# EvidenceAggregator Tests
# =========================================================================

class TestEvidenceAggregator:
    def test_aggregate_empty_context(self):
        agg = EvidenceAggregator()
        ctx = DocumentContext()
        result = agg.aggregate(ctx)
        assert "evidence" in result
        assert "conflicts" in result
        assert "score" in result
        assert "confidence" in result

    def test_aggregate_with_data(self):
        agg = EvidenceAggregator()
        ctx = DocumentContext()
        ctx._parser = ParserData(selected_parser="PDF", raw_accounts=[1, 2])
        ctx._write_once.add("parser")
        result = agg.aggregate(ctx)
        assert len(result["evidence"]) > 0

    def test_aggregate_custom_weights(self):
        w = {"parser": 0.5, "knowledge": 0.5}
        agg = EvidenceAggregator(weights=w)
        ctx = DocumentContext()
        result = agg.aggregate(ctx)
        assert result["confidence"] == 0.0


# =========================================================================
# DecisionStatisticsCollector Tests
# =========================================================================

class TestDecisionStatisticsCollector:
    def test_empty_collector(self):
        dsc = DecisionStatisticsCollector()
        assert dsc.count == 0

    def test_add_decision(self):
        dsc = DecisionStatisticsCollector()
        dsc.add(Decision(account_code="AC.01", confidence=0.9))
        assert dsc.count == 1

    def test_add_many(self):
        dsc = DecisionStatisticsCollector()
        dsc.add_many([Decision(), Decision()])
        assert dsc.count == 2

    def test_decisions_property(self):
        dsc = DecisionStatisticsCollector()
        d = Decision(account_code="AC.01")
        dsc.add(d)
        assert len(dsc.decisions) == 1
        assert dsc.decisions[0].account_code == "AC.01"

    def test_compute_empty(self):
        dsc = DecisionStatisticsCollector()
        stats = dsc.compute()
        assert stats.total_decisions == 0

    def test_compute_single_decision(self):
        dsc = DecisionStatisticsCollector()
        dsc.add(Decision(account_code="AC.01", decision_type=DecisionType.CONTINUE, confidence=0.9))
        stats = dsc.compute()
        assert stats.total_decisions == 1
        assert stats.decisions_by_type.get("CONTINUE") == 1

    def test_compute_multiple_by_type(self):
        dsc = DecisionStatisticsCollector()
        dsc.add(Decision(decision_type=DecisionType.CONTINUE))
        dsc.add(Decision(decision_type=DecisionType.MANUAL_REVIEW))
        dsc.add(Decision(decision_type=DecisionType.CONTINUE))
        stats = dsc.compute()
        assert stats.decisions_by_type["CONTINUE"] == 2
        assert stats.decisions_by_type["MANUAL_REVIEW"] == 1

    def test_compute_avg_confidence(self):
        dsc = DecisionStatisticsCollector()
        dsc.add(Decision(confidence=0.9))
        dsc.add(Decision(confidence=0.7))
        stats = dsc.compute()
        assert stats.avg_confidence == 0.8

    def test_compute_confidence_by_module(self):
        dsc = DecisionStatisticsCollector()
        ev = [DecisionEvidence(source="parser", field="f", confidence=0.9)]
        dsc.add(Decision(evidence=ev))
        stats = dsc.compute()
        assert "parser" in stats.confidence_by_module

    def test_compute_conflicts_detected(self):
        dsc = DecisionStatisticsCollector()
        a = DecisionEvidence(source="a", field="f", value="X")
        b = DecisionEvidence(source="b", field="f", value="Y")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.HIGH, reason="test")
        dsc.add(Decision(conflicts=[c]))
        stats = dsc.compute()
        assert stats.conflicts_detected == 1

    def test_compute_conflicts_by_severity(self):
        dsc = DecisionStatisticsCollector()
        a = DecisionEvidence(source="a", field="f", value="X")
        b = DecisionEvidence(source="b", field="f", value="Y")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.CRITICAL, reason="test")
        dsc.add(Decision(conflicts=[c, c]))
        stats = dsc.compute()
        assert stats.conflicts_by_severity.get("CRITICAL", 0) == 2

    def test_compute_explanations_count(self):
        dsc = DecisionStatisticsCollector()
        dsc.add(Decision(explanation=DecisionExplanation()))
        dsc.add(Decision(explanation=DecisionExplanation()))
        dsc.add(Decision())
        stats = dsc.compute()
        assert stats.explanations_generated == 2


# =========================================================================
# DecisionAdapter Tests
# =========================================================================

class TestDecisionAdapter:
    def test_adapter_init(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        assert da._conflict_resolver is not None
        assert da._confidence is not None

    def test_adapter_run_adds_decisions(self, tmp_path):
        from adapters.decision_adapter import DecisionAdapter
        from adapters.sie_adapter import SIEAdapter
        from adapters.parser_adapter import ParserAdapter
        from adapters.kb_adapter import KBAdapter

        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapter.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        da = DecisionAdapter()
        ctx = da.run(ctx)
        assert ctx.get_custom("decisions") is not None

    def test_adapter_decision_stats(self, tmp_path):
        from adapters.decision_adapter import DecisionAdapter
        from adapters.sie_adapter import SIEAdapter
        from adapters.parser_adapter import ParserAdapter
        from adapters.kb_adapter import KBAdapter

        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapter.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        da = DecisionAdapter()
        ctx = da.run(ctx)
        stats = ctx.get_custom("decision_stats", {})
        assert isinstance(stats, dict)

    def test_determine_continue(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        dt = da._determine_decision_type("code", 0.9, DecisionScore(confidence=0.8, coverage=0.8, evidence_quality=0.8, consistency=0.8), [])
        assert dt == DecisionType.CONTINUE

    def test_determine_manual_review(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        dt = da._determine_decision_type("unclassified", 0.0, DecisionScore(), [])
        assert dt == DecisionType.MANUAL_REVIEW

    def test_determine_reject(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        dt = da._determine_decision_type("ignored", 0.0, DecisionScore(), [])
        assert dt == DecisionType.REJECT

    def test_determine_learning(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        dt = da._determine_decision_type("learning_exact", 0.95, DecisionScore(confidence=0.8), [])
        assert dt == DecisionType.LEARNING

    def test_determine_critical_conflict(self):
        from adapters.decision_adapter import DecisionAdapter
        from decision_engine import ConflictResolver
        da = DecisionAdapter()
        a = DecisionEvidence(source="a", field="f", value="X", confidence=0.9)
        b = DecisionEvidence(source="b", field="f", value="Y", confidence=0.9)
        c = ConflictResolver().resolve([a, b])
        dt = da._determine_decision_type("code", 0.9, DecisionScore(), c)
        assert dt == DecisionType.MANUAL_REVIEW

    def test_determine_stress(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        dt = da._determine_decision_type("dictionary_exact", 0.5, DecisionScore(confidence=0.4), [])
        assert dt == DecisionType.STRESS

    def test_compute_coverage(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        ctx = DocumentContext()
        ctx.set_custom("classified", [{"a": 1}, {"b": 2}])
        ctx.set_custom("ignored", [{"c": 3}])
        cov = da._compute_coverage(ctx)
        assert cov == round(2/3, 4)

    def test_compute_coverage_zero(self):
        from adapters.decision_adapter import DecisionAdapter
        da = DecisionAdapter()
        ctx = DocumentContext()
        cov = da._compute_coverage(ctx)
        assert cov == 0.0


# =========================================================================
# Edge Cases
# =========================================================================

class TestDecisionEdgeCases:
    def test_conflict_none_severity(self):
        cr = ConflictResolver()
        a = DecisionEvidence(source="a", field="f", value="X", confidence=0.3)
        b = DecisionEvidence(source="b", field="f", value="X", confidence=0.3)
        sev = cr._determine_severity(a, b)
        assert sev == ConflictSeverity.NONE

    def test_empty_evidence_no_conflicts(self):
        cr = ConflictResolver()
        assert cr.resolve([]) == []

    def test_confidence_zero_weights(self):
        calc = ConfidenceCalculator(weights={"parser": 0.0, "knowledge": 0.0})
        ev = [DecisionEvidence(source="parser", field="f", value="x", confidence=0.9)]
        score = calc.compute(ev)
        assert score == 0.0

    def test_scorer_empty_evidence_quality(self):
        s = Scorer()
        assert s._evidence_quality([]) == 0.0

    def test_scorer_empty_consistency(self):
        s = Scorer()
        assert s._consistency_score([]) == 1.0

    def test_decision_to_dict_roundtrip(self):
        d = Decision(account_code="AC.01", confidence=0.85)
        dd = d.to_dict()
        assert dd["account_code"] == "AC.01"
        assert dd["confidence"] == 0.85

    def test_explanation_to_dict_roundtrip(self):
        exp = DecisionExplanation(account_code="AC.01", final_confidence=0.9, reasons=["ok"])
        ed = exp.to_dict()
        assert ed["account_code"] == "AC.01"
        assert len(ed["reasons"]) == 1

    def test_statistics_to_dict_roundtrip(self):
        s = DecisionStatistics(total_decisions=5, avg_confidence=0.8)
        sd = s.to_dict()
        assert sd["total_decisions"] == 5

    def test_evidence_with_zero_confidence(self):
        e = DecisionEvidence(source="test", field="f", value=None, confidence=0.0)
        assert e.confidence == 0.0

    def test_evidence_with_none_value(self):
        e = DecisionEvidence(source="test", field="f", value=None)
        d = e.to_dict()
        assert d["value"] is None

    def test_conflict_with_resolution(self):
        a = DecisionEvidence(source="a", field="f", value="X")
        b = DecisionEvidence(source="b", field="f", value="Y")
        c = DecisionConflict(evidence_a=a, evidence_b=b, severity=ConflictSeverity.HIGH, reason="r", resolution="pick a")
        assert c.resolution == "pick a"

    def test_decision_with_all_fields(self):
        d = Decision(
            account_code="AC.01", account_name="Caja",
            decision_type=DecisionType.CONTINUE, final_code="AC.01",
            confidence=0.95,
            evidence=[DecisionEvidence(source="p", field="f", value="v", confidence=0.9)],
            conflicts=[],
            score=DecisionScore(confidence=0.9),
            explanation=DecisionExplanation(final_confidence=0.95),
        )
        dd = d.to_dict()
        assert dd["evidence_count"] == 1
        assert dd["score"] is not None
        assert dd["explanation"] is not None

    def test_weights_are_configurable(self):
        custom = {"parser": 0.40, "knowledge": 0.30, "validation": 0.15, "structure": 0.10, "die": 0.05}
        calc = ConfidenceCalculator(weights=custom)
        assert abs(calc.weights["parser"] - 0.40) < 0.001

    def test_weights_partial_override(self):
        custom = {"parser": 0.50}
        calc = ConfidenceCalculator(weights=custom)
        assert calc.weights["parser"] == 0.50
        assert calc.weights["knowledge"] == 0.30

    def test_decision_evidence_different_modules(self):
        ev = EvidenceCollector.collect_all(DocumentContext())
        modules = set(e.source for e in ev)
        assert len(modules) >= 0

    def test_explanation_empty_reasons(self):
        gen = ExplanationGenerator()
        exp = gen.generate("A", "B", "C", [], [])
        assert exp.reasons == []

    def test_explanation_empty_evidence_summary(self):
        gen = ExplanationGenerator()
        exp = gen.generate("A", "B", "C", [], [])
        assert exp.evidence_summary == []


# =========================================================================
# Full Pipeline Integration with Decision Engine
# =========================================================================

class TestPipelineWithDecisionEngine:
    def test_pipeline_v2_with_decision_engine(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdfs[0]))
        decisions = ctx.get_custom("decisions", [])
        assert len(decisions) > 0

    def test_decisions_match_classified_count(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdfs[0]))
        classified = ctx.get_custom("classified", [])
        decisions = ctx.get_custom("decisions", [])
        assert len(decisions) == len(classified)

    def test_all_decisions_have_explanations(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdfs[0]))
        decisions = ctx.get_custom("decisions", [])
        for d in decisions:
            assert "explanation" in d
            assert d["explanation"] is not None

    def test_all_decisions_have_confidence(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdfs[0]))
        decisions = ctx.get_custom("decisions", [])
        for d in decisions:
            assert d["confidence"] >= 0

    def test_decision_stats_in_pipeline_output(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pipe = HomologationPipelineV2()
        d = pipe.process_to_dict(str(pdfs[0]))
        assert "decision_stats" in d

    def test_v1_v2_results_still_match_with_de(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:1]
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        v1 = HomologationPipeline().process(str(pdfs[0]))
        v2 = HomologationPipelineV2()
        ctx = v2.process(str(pdfs[0]))
        v1_count = v1.get("accounts_classified", 0)
        v2_count = len(ctx.get_custom("classified", []))
        assert v1_count == v2_count

    def test_pipeline_v2_optimized_performance(self):
        import time
        from pipeline.homologation_pipeline import HomologationPipeline
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:3]
        if len(pdfs) < 3:
            pytest.skip("Need 3 HOLDOUT files")

        t0 = time.time()
        for pdf in pdfs:
            HomologationPipeline().process(str(pdf))
        v1_total = time.time() - t0

        t0 = time.time()
        for pdf in pdfs:
            HomologationPipelineV2().process(str(pdf))
        v2_total = time.time() - t0

        print(f"\nV1 total: {v1_total:.2f}s, V2 total: {v2_total:.2f}s, ratio: {v2_total/v1_total:.2f}x")
        assert v2_total < v1_total * 2.5


# =========================================================================
# Helpers
# =========================================================================

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
    b"xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n"
    b"0000000058 00000 n \ntrailer<</Size 3/Root 1 0 R>>\n"
    b"startxref\n109\n%%EOF"
)


def _make_pdf(tmp_path: Path, name: str = "test_2023.pdf") -> Path:
    pdf = tmp_path / name
    pdf.write_bytes(MINIMAL_PDF_BYTES)
    return pdf
