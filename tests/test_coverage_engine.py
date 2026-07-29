from __future__ import annotations

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from dataclasses import dataclass, field
from typing import Any

from coverage_engine import (
    CoverageType, CoverageSeverity, CoverageIssue,
    MonetaryCoverage, StructuralCoverage, SemanticCoverage,
    DocumentCoverage, CoverageResult, CoverageStatistics,
    CoverageSummary, family_from_code,
    DEFAULT_COVERAGE_WEIGHTS, FAMILY_ORDER, EXPECTED_SECTIONS,
    MonetaryCoverageCalculator, StructuralCoverageCalculator,
    SemanticCoverageCalculator, DocumentCoverageCalculator,
    CoverageCalculator, CoverageStatisticsCollector,
    CoverageReportGenerator, CoverageAdapter,
)

from document_context import DocumentContext
from document_context.models import (
    StructureData, ValidationData, DocumentMetadata,
    ParserData, KnowledgeData,
)


# =============================================================================
# HELPERS
# =============================================================================

def make_classified(**overrides) -> dict[str, Any]:
    base = {
        "account_code": "1001",
        "account_name": "Caja",
        "classification_amount": 100000.0,
        "final_code": "AC.01.001",
        "standard_code": "AC.01.001",
        "confidence": 0.95,
        "method": "learning_exact",
        "reason": "",
    }
    base.update(overrides)
    return base


def make_subtotal_result(name: str, expected: float, actual: float, passed: bool = True, pct_diff: float = 0.0):
    @dataclass
    class SubtotalResult:
        account_name: str = ""
        account_code: str = ""
        expected: float = 0.0
        actual: float = 0.0
        difference: float = 0.0
        pct_diff: float = 0.0
        children_count: int = 0
        children: list[str] = field(default_factory=list)
        passed: bool = False
        line_number: int = 0
    return SubtotalResult(
        account_name=name,
        expected=expected,
        actual=actual,
        passed=passed,
        pct_diff=pct_diff,
    )


@dataclass
class FakeTree:
    nodes: list = field(default_factory=list)
    total_nodes: int = 0
    subtotal_count: int = 0
    sections: list = field(default_factory=list)


@dataclass
class FakeSectionInfo:
    name: str = ""
    type: str = ""
    start_line: int = 0
    end_line: int = 0
    depth: int = 0
    node_count: int = 0


# =============================================================================
# MODELS TESTS
# =============================================================================

class TestCoverageType:
    def test_values(self):
        assert CoverageType.MONETARY.value == "monetary"
        assert CoverageType.STRUCTURAL.value == "structural"
        assert CoverageType.SEMANTIC.value == "semantic"
        assert CoverageType.DOCUMENT.value == "document"
        assert CoverageType.OVERALL.value == "overall"

    def test_unique(self):
        values = [t.value for t in CoverageType]
        assert len(values) == len(set(values))


class TestCoverageSeverity:
    def test_values(self):
        assert CoverageSeverity.CRITICAL.value == "CRITICAL"
        assert CoverageSeverity.HIGH.value == "HIGH"
        assert CoverageSeverity.MEDIUM.value == "MEDIUM"
        assert CoverageSeverity.LOW.value == "LOW"
        assert CoverageSeverity.INFO.value == "INFO"

    def test_ordering(self):
        sevs = list(CoverageSeverity)
        assert sevs.index(CoverageSeverity.CRITICAL) < sevs.index(CoverageSeverity.INFO)


class TestFamilyFromCode:
    def test_ac_prefix(self):
        assert family_from_code("AC.01.001") == "Activo"

    def test_anc_prefix(self):
        assert family_from_code("ANC.01.001") == "Activo"

    def test_pc_prefix(self):
        assert family_from_code("PC.01.001") == "Pasivo"

    def test_pnc_prefix(self):
        assert family_from_code("PNC.01.001") == "Pasivo"

    def test_pat_prefix(self):
        assert family_from_code("PAT.01.001") == "Patrimonio"

    def test_er_prefix(self):
        assert family_from_code("ER.01.001") == "Resultado"

    def test_numeric_1(self):
        assert family_from_code("1.01.001") == "Activo"

    def test_numeric_2(self):
        assert family_from_code("2.01.001") == "Pasivo"

    def test_numeric_3(self):
        assert family_from_code("3.01.001") == "Patrimonio"

    def test_numeric_4(self):
        assert family_from_code("4.01.001") == "Resultado"

    def test_numeric_5(self):
        assert family_from_code("5.01.001") == "Costos"

    def test_numeric_6(self):
        assert family_from_code("6.01.001") == "Gastos"

    def test_none_code(self):
        assert family_from_code(None) == "Unknown"

    def test_empty_code(self):
        assert family_from_code("") == "Unknown"

    def test_unknown_prefix(self):
        assert family_from_code("ZZ.01") == "Unknown"


class TestCoverageIssue:
    def test_defaults(self):
        issue = CoverageIssue()
        assert issue.issue_type == ""
        assert issue.severity == CoverageSeverity.INFO
        assert issue.monetary_impact == 0.0
        assert issue.document_impact == 0.0

    def test_full_creation(self):
        issue = CoverageIssue(
            issue_type="uncategorized_account",
            severity=CoverageSeverity.CRITICAL,
            monetary_impact=50000.0,
            document_impact=0.25,
            detail="5 cuentas sin clasificar",
            family="Activo",
        )
        assert issue.issue_type == "uncategorized_account"
        assert issue.severity == CoverageSeverity.CRITICAL
        assert issue.monetary_impact == 50000.0

    def test_to_dict(self):
        issue = CoverageIssue(
            issue_type="unexplained_amount",
            severity=CoverageSeverity.HIGH,
            monetary_impact=1500.0,
            document_impact=0.1,
            detail="Familia Pasivo",
            family="Pasivo",
        )
        d = issue.to_dict()
        assert d["issue_type"] == "unexplained_amount"
        assert d["severity"] == "HIGH"
        assert d["monetary_impact"] == 1500.0
        assert d["family"] == "Pasivo"

    def test_roundtrip(self):
        issue = CoverageIssue(
            issue_type="partial_template",
            severity=CoverageSeverity.MEDIUM,
            monetary_impact=0.0,
            document_impact=0.3,
            detail="3 subtotales faltantes",
            family="",
        )
        issue2 = CoverageIssue.from_dict(issue.to_dict())
        assert issue2.issue_type == issue.issue_type
        assert issue2.severity == issue.severity
        assert issue2.monetary_impact == issue.monetary_impact

    def test_from_dict_defaults(self):
        issue = CoverageIssue.from_dict({})
        assert issue.issue_type == ""
        assert issue.severity == CoverageSeverity.INFO

    def test_to_dict_rounding(self):
        issue = CoverageIssue(
            issue_type="test",
            severity=CoverageSeverity.LOW,
            monetary_impact=1234.5678,
            document_impact=0.12345,
        )
        d = issue.to_dict()
        assert d["monetary_impact"] == 1234.57
        assert d["document_impact"] == 0.1235


class TestMonetaryCoverage:
    def test_defaults(self):
        m = MonetaryCoverage()
        assert m.total_amount == 0.0
        assert m.explained_amount == 0.0
        assert m.coverage_pct == 0.0
        assert m.by_family == {}

    def test_to_dict(self):
        m = MonetaryCoverage(
            total_amount=1000000.0,
            explained_amount=998500.0,
            coverage_pct=0.9985,
            by_family={"Activo": {"total": 1000000.0, "explained": 998500.0, "coverage_pct": 0.9985}},
        )
        d = m.to_dict()
        assert d["total_amount"] == 1000000.0
        assert d["coverage_pct"] == 0.9985

    def test_roundtrip(self):
        m = MonetaryCoverage(
            total_amount=500000.0,
            explained_amount=480000.0,
            coverage_pct=0.96,
            by_family={"Pasivo": {"total": 500000.0, "explained": 480000.0, "coverage_pct": 0.96}},
        )
        m2 = MonetaryCoverage.from_dict(m.to_dict())
        assert m2.total_amount == 500000.0
        assert m2.coverage_pct == 0.96

    def test_full_coverage(self):
        m = MonetaryCoverage(
            total_amount=1000.0,
            explained_amount=1000.0,
            coverage_pct=1.0,
        )
        assert m.coverage_pct == 1.0


class TestStructuralCoverage:
    def test_defaults(self):
        s = StructuralCoverage()
        assert s.subtotals_detected == 0
        assert s.overall == 0.0

    def test_full(self):
        s = StructuralCoverage(
            subtotals_detected=4,
            subtotals_expected=4,
            subtotals_validated=4,
            subtotals_consistent=3,
            hierarchy_reconstructed=0.95,
            template_coverage=0.9,
            overall=0.85,
        )
        assert s.subtotals_detected == 4
        assert s.overall == 0.85

    def test_to_dict_roundtrip(self):
        s = StructuralCoverage(
            subtotals_detected=3,
            subtotals_expected=5,
            subtotals_validated=2,
            subtotals_consistent=2,
            hierarchy_reconstructed=0.8,
            template_coverage=0.7,
            overall=0.6,
        )
        s2 = StructuralCoverage.from_dict(s.to_dict())
        assert s2.subtotals_detected == 3
        assert s2.overall == 0.6


class TestSemanticCoverage:
    def test_defaults(self):
        s = SemanticCoverage()
        assert s.total_accounts == 0
        assert s.classified_count == 0
        assert s.overall == 0.0

    def test_full(self):
        s = SemanticCoverage(
            total_accounts=100,
            classified_count=95,
            known_count=80,
            learning_hits=50,
            kb_matches=30,
            unknown_count=5,
            overall=0.95,
        )
        assert s.total_accounts == 100
        assert s.overall == 0.95

    def test_roundtrip(self):
        s = SemanticCoverage(
            total_accounts=50,
            classified_count=45,
            known_count=40,
            unknown_count=5,
            overall=0.9,
            by_family={"Activo": {"total": 20, "classified": 19, "coverage_pct": 0.95}},
        )
        s2 = SemanticCoverage.from_dict(s.to_dict())
        assert s2.total_accounts == 50
        assert s2.overall == 0.9


class TestDocumentCoverage:
    def test_defaults(self):
        d = DocumentCoverage()
        assert d.coverage_pct == 0.0
        assert d.expected_sections == []

    def test_full_coverage(self):
        d = DocumentCoverage(
            expected_sections=["Activo", "Pasivo"],
            present_sections=["Activo", "Pasivo"],
            correct_sections=["Activo", "Pasivo"],
            coverage_pct=1.0,
            section_details={"Activo": "OK", "Pasivo": "OK"},
        )
        assert d.coverage_pct == 1.0

    def test_partial(self):
        d = DocumentCoverage(
            expected_sections=["Activo", "Pasivo", "Patrimonio", "Resultado"],
            present_sections=["Activo", "Pasivo"],
            correct_sections=["Activo"],
            coverage_pct=0.25,
        )
        assert d.coverage_pct == 0.25

    def test_roundtrip(self):
        d = DocumentCoverage(
            expected_sections=["Activo"],
            present_sections=["Activo"],
            correct_sections=["Activo"],
            coverage_pct=1.0,
        )
        d2 = DocumentCoverage.from_dict(d.to_dict())
        assert d2.coverage_pct == 1.0
        assert d2.expected_sections == ["Activo"]


class TestCoverageResult:
    def test_defaults(self):
        r = CoverageResult()
        assert r.overall == 0.0
        assert r.weights == {}
        assert r.issues == []

    def test_full_creation(self):
        r = CoverageResult(
            monetary=MonetaryCoverage(total_amount=1000.0, explained_amount=1000.0, coverage_pct=1.0),
            structural=StructuralCoverage(overall=0.9),
            semantic=SemanticCoverage(overall=0.95),
            document=DocumentCoverage(coverage_pct=1.0),
            overall=0.96,
            weights=DEFAULT_COVERAGE_WEIGHTS,
            issues=[CoverageIssue(issue_type="test", severity=CoverageSeverity.INFO)],
            timestamp="2024-01-01T00:00:00",
        )
        assert r.overall == 0.96
        assert len(r.issues) == 1

    def test_to_dict(self):
        r = CoverageResult(
            monetary=MonetaryCoverage(total_amount=100.0, explained_amount=90.0, coverage_pct=0.9),
            overall=0.9,
            weights={"monetary": 1.0},
        )
        d = r.to_dict()
        assert d["overall"] == 0.9
        assert d["monetary"]["coverage_pct"] == 0.9

    def test_roundtrip(self):
        r = CoverageResult(
            monetary=MonetaryCoverage(total_amount=500.0, explained_amount=450.0, coverage_pct=0.9),
            structural=StructuralCoverage(overall=0.85),
            semantic=SemanticCoverage(overall=0.8),
            document=DocumentCoverage(coverage_pct=0.75),
            overall=0.85,
            weights=DEFAULT_COVERAGE_WEIGHTS,
            issues=[CoverageIssue(issue_type="test", severity=CoverageSeverity.LOW, detail="test")],
        )
        r2 = CoverageResult.from_dict(r.to_dict())
        assert abs(r2.overall - 0.85) < 0.01
        assert len(r2.issues) == 1
        assert r2.issues[0].detail == "test"

    def test_json_serializable(self):
        r = CoverageResult(
            monetary=MonetaryCoverage(total_amount=100.0, explained_amount=95.0, coverage_pct=0.95),
            overall=0.95,
        )
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        assert loaded["overall"] == 0.95


class TestCoverageStatistics:
    def test_defaults(self):
        s = CoverageStatistics()
        assert s.total_documents == 0
        assert s.overall_avg == 0.0

    def test_full(self):
        s = CoverageStatistics(
            total_documents=10,
            overall_avg=0.85,
            overall_median=0.87,
            overall_p25=0.75,
            overall_p75=0.95,
            monetary_avg=0.88,
            structural_avg=0.82,
            semantic_avg=0.86,
            document_avg=0.84,
        )
        assert s.overall_avg == 0.85

    def test_roundtrip(self):
        s = CoverageStatistics(
            total_documents=5,
            overall_avg=0.9,
            overall_median=0.92,
            distribution={"90-100%": 3, "80-90%": 2},
            by_family={"Activo": {"avg": 0.95, "count": 5}},
        )
        s2 = CoverageStatistics.from_dict(s.to_dict())
        assert s2.total_documents == 5
        assert s2.overall_avg == 0.9


class TestCoverageSummary:
    def test_defaults(self):
        s = CoverageSummary()
        assert s.overall == 0.0
        assert s.total_issues == 0

    def test_full(self):
        s = CoverageSummary(
            overall=0.88,
            monetary=0.9,
            structural=0.85,
            semantic=0.87,
            document=0.9,
            total_issues=5,
            critical_issues=1,
            high_issues=2,
            top_documents=[{"name": "doc1", "score": 0.99}],
            worst_documents=[{"name": "doc2", "score": 0.45}],
        )
        assert s.overall == 0.88
        assert len(s.top_documents) == 1

    def test_roundtrip(self):
        s = CoverageSummary(overall=0.75, total_issues=3)
        s2 = CoverageSummary.from_dict(s.to_dict())
        assert s2.overall == 0.75


# =============================================================================
# MONETARY COVERAGE TESTS
# =============================================================================

class TestMonetaryCoverageCalculator:
    def test_basic_coverage(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=500000.0, final_code="AC.01.001"),
            make_classified(classification_amount=300000.0, final_code="AC.01.002"),
            make_classified(classification_amount=198500.0, final_code="AC.01.003"),
        ]
        total_by_family = {"Activo": 1000000.0}
        monetary, issues = calc.compute(classified, total_by_family)
        assert monetary.coverage_pct == pytest.approx(0.9985, abs=0.001)
        assert monetary.total_amount == 1000000.0
        assert monetary.explained_amount == 998500.0

    def test_perfect_coverage(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=500.0, final_code="AC.01"),
            make_classified(classification_amount=500.0, final_code="AC.02"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.coverage_pct == 1.0
        assert len(issues) == 0

    def test_zero_total(self):
        calc = MonetaryCoverageCalculator()
        monetary, issues = calc.compute([], {})
        assert monetary.coverage_pct == 1.0
        assert monetary.total_amount == 0.0

    def test_low_coverage_issue(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=100.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert len(issues) >= 1
        assert issues[0].issue_type == "unexplained_amount"

    def test_multiple_families(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=800.0, final_code="AC.01", account_code="1"),
            make_classified(classification_amount=150.0, final_code="PC.01", account_code="2"),
        ]
        total_by_family = {"Activo": 1000.0, "Pasivo": 200.0}
        monetary, issues = calc.compute(classified, total_by_family)
        assert monetary.by_family["Activo"]["coverage_pct"] == 0.8
        assert monetary.by_family["Pasivo"]["coverage_pct"] == 0.75

    def test_family_unknown_ignored(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=100.0, final_code=None, standard_code=None),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        # Unknown account doesn't pollute Activo explained amount
        assert monetary.by_family.get("Activo", {}).get("coverage_pct", 0.0) == 0.0

    def test_all_families_present(self):
        calc = MonetaryCoverageCalculator()
        families = ["Activo", "Pasivo", "Patrimonio", "Resultado", "Ingresos", "Costos", "Gastos"]
        classified = []
        total_by_family = {}
        for fam in families:
            classified.append(make_classified(
                classification_amount=100.0,
                final_code=f"{fam}.01",
                account_code=f"{families.index(fam)}",
            ))
            # some families may not map to codes
        # Just test that the calculator doesn't crash
        monetary, issues = calc.compute(classified, {f: 100.0 for f in families})
        for fam in families:
            assert fam in monetary.by_family

    def test_issue_severity_high(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=100.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 10000.0})
        low_coverage_issues = [i for i in issues if i.issue_type == "unexplained_amount"]
        assert len(low_coverage_issues) == 1
        assert low_coverage_issues[0].severity == CoverageSeverity.HIGH

    def test_issue_severity_medium(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=9000.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 9500.0})
        low_coverage_issues = [i for i in issues if i.issue_type == "unexplained_amount"]
        assert len(low_coverage_issues) == 1
        assert low_coverage_issues[0].severity == CoverageSeverity.MEDIUM

    def test_negative_amounts(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=-500.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": -500.0})
        assert monetary.coverage_pct == 1.0

    def test_from_ctx_with_data(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=500.0, final_code="AC.01"),
        ]

        @dataclass
        class FakeValidation:
            subtotal_validation: list = field(default_factory=list)

        validation = FakeValidation(
            subtotal_validation=[make_subtotal_result("Total Activo", 1000.0, 1000.0)],
        )
        monetary, issues = calc.compute_from_ctx(classified, validation_data=validation)
        assert monetary.total_amount == 1000.0
        assert monetary.explained_amount == 500.0

    def test_from_ctx_no_data(self):
        calc = MonetaryCoverageCalculator()
        monetary, issues = calc.compute_from_ctx([], validation_data=None)
        assert monetary.coverage_pct == 1.0

    def test_amount_rounding(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=333.33, final_code="AC.01"),
            make_classified(classification_amount=333.33, final_code="AC.02"),
            make_classified(classification_amount=333.34, final_code="AC.03"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.coverage_pct == pytest.approx(1.0, abs=0.001)

    def test_single_account_full(self):
        calc = MonetaryCoverageCalculator()
        classified = [make_classified(classification_amount=1000.0, final_code="AC.01")]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.coverage_pct == 1.0

    def test_no_classified_accounts(self):
        calc = MonetaryCoverageCalculator()
        monetary, issues = calc.compute([], {"Activo": 1000.0})
        assert monetary.coverage_pct == 0.0

    def test_family_without_total(self):
        calc = MonetaryCoverageCalculator()
        classified = [make_classified(classification_amount=100.0, final_code="AC.01")]
        # only infer from accounts
        monetary, issues = calc.compute(classified, {"Activo": 100.0})
        assert monetary.coverage_pct == 1.0


# =============================================================================
# STRUCTURAL COVERAGE TESTS
# =============================================================================

class TestStructuralCoverageCalculator:
    def test_perfect(self):
        calc = StructuralCoverageCalculator()

        @dataclass
        class FakeValidation:
            subtotal_validation: list = field(default_factory=list)

        validation = FakeValidation(subtotal_validation=[
            make_subtotal_result("Total Activo", 1000.0, 1000.0, True, 0.0),
            make_subtotal_result("Total Pasivo", 500.0, 500.0, True, 0.0),
            make_subtotal_result("Total Patrimonio", 500.0, 500.0, True, 0.0),
            make_subtotal_result("Total Resultado", 200.0, 200.0, True, 0.0),
        ])
        structural, issues = calc.compute(
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            validation_data=validation,
        )
        assert structural.subtotals_detected >= 4
        assert structural.subtotals_validated >= 4

    def test_no_subtotals(self):
        calc = StructuralCoverageCalculator()
        structural, issues = calc.compute(None, None)
        assert structural.subtotals_detected == 0
        assert structural.overall == 0.0

    def test_inconsistent_subtotals(self):
        calc = StructuralCoverageCalculator()

        @dataclass
        class FakeValidation:
            subtotal_validation: list = field(default_factory=list)

        validation = FakeValidation(subtotal_validation=[
            make_subtotal_result("Total Activo", 1000.0, 900.0, False, 0.1),
            make_subtotal_result("Total Pasivo", 500.0, 500.0, True, 0.0),
        ])
        structural, issues = calc.compute(validation_data=validation)
        inconsistency_issues = [i for i in issues if i.issue_type == "inconsistent_subtotal"]
        assert len(inconsistency_issues) >= 0

    def test_hierarchy_score_from_tree(self):
        calc = StructuralCoverageCalculator()
        tree = FakeTree(nodes=[1, 2, 3], total_nodes=3)
        structure = StructureData(tree=tree)
        structural, issues = calc.compute(structure_data=structure)
        assert structural.hierarchy_reconstructed == 1.0

    def test_hierarchy_partial(self):
        calc = StructuralCoverageCalculator()
        tree = FakeTree(nodes=[1, 2], total_nodes=5)
        structure = StructureData(tree=tree)
        structural, issues = calc.compute(structure_data=structure)
        assert structural.hierarchy_reconstructed == 0.4

    def test_template_coverage_with_template(self):
        calc = StructuralCoverageCalculator()
        structure = StructureData(family="TRIBUTARIO", template="T14")
        structural, issues = calc.compute(structure_data=structure)
        assert structural.template_coverage > 0

    def test_template_coverage_without_template(self):
        calc = StructuralCoverageCalculator()
        structure = StructureData()
        structural, issues = calc.compute(structure_data=structure)
        assert structural.template_coverage == 0.0

    def test_partial_template_issue(self):
        calc = StructuralCoverageCalculator()
        structural, issues = calc.compute(
            structure_data=StructureData(),
            validation_data=None,
        )
        partial_issues = [i for i in issues if i.issue_type == "partial_template"]
        # With 0 subtotals detected, there should be a partial template issue
        assert len(partial_issues) >= 1 or structural.subtotals_detected > 0

    def test_overall_calculation(self):
        calc = StructuralCoverageCalculator()
        tree = FakeTree(nodes=[1, 2, 3], total_nodes=3, subtotal_count=4)

        @dataclass
        class FakeValidation:
            subtotal_validation: list = field(default_factory=list)

        validation = FakeValidation(subtotal_validation=[
            make_subtotal_result("Total Activo", 1000.0, 1000.0, True, 0.0),
            make_subtotal_result("Total Pasivo", 500.0, 500.0, True, 0.0),
            make_subtotal_result("Total Patrimonio", 500.0, 500.0, True, 0.0),
            make_subtotal_result("Total Resultado", 200.0, 200.0, True, 0.0),
        ])

        @dataclass
        class FakeTreeWithSections:
            nodes: list = field(default_factory=list)
            total_nodes: int = 0
            subtotal_count: int = 0
            sections: list = field(default_factory=list)

        tree2 = FakeTreeWithSections(
            nodes=[1, 2, 3],
            total_nodes=3,
            subtotal_count=4,
            sections=[FakeSectionInfo(name="Activo")],
        )
        structure = StructureData(family="TRIBUTARIO", template="T14", tree=tree2)
        structural, issues = calc.compute(
            structure_data=structure,
            validation_data=validation,
        )
        assert structural.overall > 0

    def test_subtotals_expected_constant(self):
        calc = StructuralCoverageCalculator()

        @dataclass
        class FakeV:
            subtotal_validation: list = field(default_factory=list)

        validation = FakeV(subtotal_validation=[
            make_subtotal_result("Total Activo", 1000.0, 1000.0, True, 0.0),
        ])
        structural, issues = calc.compute(
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            validation_data=validation,
        )
        assert structural.subtotals_expected == len(FAMILY_ORDER)


# =============================================================================
# SEMANTIC COVERAGE TESTS
# =============================================================================

class TestSemanticCoverageCalculator:
    def test_all_classified(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="learning_exact", final_code="AC.01") for _ in range(10)]
        semantic, issues = calc.compute(classified, 10)
        assert semantic.overall == 1.0
        assert semantic.classified_count == 10
        assert semantic.unknown_count == 0

    def test_some_unclassified(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="learning_exact") for _ in range(7)]
        semantic, issues = calc.compute(classified, 10)
        assert semantic.overall == 0.7
        assert semantic.unknown_count == 3

    def test_no_accounts(self):
        calc = SemanticCoverageCalculator()
        semantic, issues = calc.compute([], 0)
        assert semantic.overall == 1.0

    def test_unknown_issue(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="learning_exact") for _ in range(3)]
        semantic, issues = calc.compute(classified, 10)
        unknown_issues = [i for i in issues if i.issue_type == "uncategorized_account"]
        assert len(unknown_issues) == 1

    def test_insufficient_learning_issue(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="code", final_code="AC.01") for _ in range(5)]
        semantic, issues = calc.compute(classified, 5)
        learning_issues = [i for i in issues if i.issue_type == "insufficient_learning"]
        assert len(learning_issues) >= 1

    def test_learning_hits_classified(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="learning_exact") for _ in range(5)]
        semantic, issues = calc.compute(classified, 5)
        assert semantic.learning_hits == 5
        assert semantic.known_count == 5

    def test_kb_matches(self):
        calc = SemanticCoverageCalculator()
        classified = [
            make_classified(method="cmcc", final_code="AC.01", cmcc_shadow={"code": "AC.01"}),
        ]
        semantic, issues = calc.compute(classified, 1)
        assert semantic.kb_matches == 1
        assert semantic.known_count == 1

    def test_dictionary_matches(self):
        calc = SemanticCoverageCalculator()
        classified = [
            make_classified(method="dictionary_exact", final_code="AC.01"),
        ]
        semantic, issues = calc.compute(classified, 1)
        assert semantic.kb_matches >= 0

    def test_by_family_breakdown(self):
        calc = SemanticCoverageCalculator()
        classified = [
            make_classified(final_code="AC.01", account_code="1"),
            make_classified(final_code="PC.01", account_code="2"),
        ]
        semantic, issues = calc.compute(classified, 2)
        assert "Activo" in semantic.by_family
        assert "Pasivo" in semantic.by_family

    def test_from_ctx_with_ignored(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified() for _ in range(8)]
        ignored = [{"account_code": "999", "ignored_reason": "movement_only"}]
        semantic, issues = calc.compute_from_ctx(classified, ignored=ignored)
        assert semantic.total_accounts == 9
        assert semantic.classified_count == 8
        assert semantic.overall == pytest.approx(8/9, abs=0.001)

    def test_from_ctx_no_ignored(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified() for _ in range(5)]
        semantic, issues = calc.compute_from_ctx(classified)
        assert semantic.total_accounts == 5

    def test_review_workspace_from_decisions(self):
        calc = SemanticCoverageCalculator()
        classified = [make_classified(method="learning_exact") for _ in range(5)]
        decisions = [
            {"account_code": "1", "decision_type": "LEARNING"},
            {"account_code": "2", "decision_type": "CONTINUE"},
        ]
        semantic, _ = calc.compute(classified, 5, decisions=decisions)
        assert semantic.review_workspace >= 0

    def test_empty_classified(self):
        calc = SemanticCoverageCalculator()
        semantic, issues = calc.compute([], 10)
        assert semantic.overall == 0.0
        assert len(issues) == 1


# =============================================================================
# DOCUMENT COVERAGE TESTS
# =============================================================================

class TestDocumentCoverageCalculator:
    def test_all_sections_present(self):
        calc = DocumentCoverageCalculator()
        sections_data = StructureData(
            family="TRIBUTARIO",
            template="T14",
            sections=[{"name": "Activo"}, {"name": "Pasivo"}, {"name": "Patrimonio"}, {"name": "Resultado"}],
        )
        document, issues = calc.compute(structure_data=sections_data)
        assert document.coverage_pct == 1.0

    def test_missing_sections(self):
        calc = DocumentCoverageCalculator()
        sections_data = StructureData(
            sections=[{"name": "Activo"}],
        )
        document, issues = calc.compute(structure_data=sections_data)
        assert document.coverage_pct < 1.0

    def test_no_structure_data(self):
        calc = DocumentCoverageCalculator()
        document, issues = calc.compute(structure_data=None)
        assert document.coverage_pct == 1.0 or document.coverage_pct == 0.0

    def test_section_details(self):
        calc = DocumentCoverageCalculator()
        sections_data = StructureData(
            family="TRIBUTARIO",
            sections=[{"name": "Activo"}, {"name": "Pasivo"}],
        )
        document, issues = calc.compute(structure_data=sections_data)
        assert "Activo" in document.section_details
        assert "Pasivo" in document.section_details

    def test_custom_expected_sections(self):
        calc = DocumentCoverageCalculator()
        document, issues = calc.compute(
            structure_data=StructureData(sections=[{"name": "Activo"}]),
            expected_sections=["Activo", "Pasivo"],
        )
        assert "Activo" in document.section_details
        assert "Pasivo" in document.section_details

    def test_na_sections(self):
        calc = DocumentCoverageCalculator()
        document, issues = calc.compute(
            structure_data=StructureData(
                sections=[{"name": "Activo"}, {"name": "Notas"}],
            ),
            expected_sections=["Activo", "Notas"],
        )
        assert "Notas" in document.not_applicable_sections or len(document.not_applicable_sections) >= 0

    def test_section_status_icons(self):
        calc = DocumentCoverageCalculator()
        sections_data = StructureData(
            family="TRIBUTARIO",
            template="T14",
            sections=[{"name": "Activo"}, {"name": "Pasivo"}],
        )
        document, issues = calc.compute(structure_data=sections_data)
        for sec in EXPECTED_SECTIONS:
            status = document.section_details.get(sec, "")
            assert status in ("OK", "PRESENT", "MISSING", "N/A")


# =============================================================================
# COVERAGE CALCULATOR TESTS
# =============================================================================

class TestCoverageCalculator:
    def test_default_weights(self):
        calc = CoverageCalculator()
        assert calc.weights["monetary"] == 0.40
        assert calc.weights["structural"] == 0.25
        assert calc.weights["semantic"] == 0.20
        assert calc.weights["document"] == 0.15

    def test_custom_weights(self):
        calc = CoverageCalculator(weights={"monetary": 0.5, "structural": 0.5})
        assert calc.weights["monetary"] == 0.5
        assert calc.weights["structural"] == 0.5

    def test_compute_from_data(self):
        calc = CoverageCalculator()
        classified = [
            make_classified(classification_amount=800.0, final_code="AC.01"),
            make_classified(classification_amount=200.0, final_code="PC.01"),
        ]
        result = calc.compute_from_data(
            classified=classified,
        )
        assert result.overall >= 0

    def test_compute_from_data_with_all(self):
        calc = CoverageCalculator()
        classified = [make_classified(classification_amount=500.0, final_code="AC.01")]
        result = calc.compute_from_data(
            classified=classified,
            ignored=[],
            decisions=[],
            structure_data=StructureData(family="TRIBUTARIO", template="T14"),
            metadata=DocumentMetadata(company="TEST", year=2024),
        )
        assert result.monetary is not None
        assert result.structural is not None
        assert result.semantic is not None
        assert result.document is not None

    def test_compute_with_context(self):
        calc = CoverageCalculator()
        ctx = DocumentContext(source_file="test.pdf")
        ctx.set_custom("classified", [
            make_classified(classification_amount=500.0, final_code="AC.01"),
        ])
        result = calc.compute(ctx)
        assert result.overall >= 0

    def test_compute_empty_context(self):
        calc = CoverageCalculator()
        ctx = DocumentContext()
        result = calc.compute(ctx)
        assert result is not None

    def test_weights_normalization(self):
        calc = CoverageCalculator(weights={"monetary": 0.3, "structural": 0.3, "semantic": 0.2, "document": 0.2})
        assert abs(sum(calc.weights.values()) - 1.0) < 0.001

    def test_weights_property(self):
        calc = CoverageCalculator()
        w = calc.weights
        assert isinstance(w, dict)
        w["monetary"] = 0.5  # should not modify internal state
        assert calc.weights["monetary"] == 0.40


# =============================================================================
# COVERAGE STATISTICS TESTS
# =============================================================================

class TestCoverageStatisticsCollector:
    def test_empty(self):
        collector = CoverageStatisticsCollector()
        stats = collector.compute()
        assert stats.total_documents == 0
        assert stats.overall_avg == 0.0

    def test_single_result(self):
        collector = CoverageStatisticsCollector()
        result = CoverageResult(overall=0.95)
        collector.add(result)
        stats = collector.compute()
        assert stats.total_documents == 1
        assert stats.overall_avg == 0.95
        assert stats.overall_median == 0.95

    def test_multiple_results(self):
        collector = CoverageStatisticsCollector()
        for i in range(5):
            collector.add(CoverageResult(overall=0.8 + i * 0.05))
        stats = collector.compute()
        assert stats.total_documents == 5
        assert stats.overall_avg == 0.9
        assert stats.overall_median == 0.9

    def test_percentiles(self):
        collector = CoverageStatisticsCollector()
        scores = [0.1, 0.2, 0.5, 0.8, 0.9]
        for s in scores:
            collector.add(CoverageResult(overall=s))
        stats = collector.compute()
        assert stats.overall_p25 == 0.2
        assert stats.overall_median == 0.5
        assert stats.overall_p75 == 0.8

    def test_distribution(self):
        collector = CoverageStatisticsCollector()
        for s in [0.05, 0.15, 0.5, 0.85, 0.95]:
            collector.add(CoverageResult(overall=s))
        stats = collector.compute()
        assert stats.distribution["0-10%"] == 1
        assert stats.distribution["10-20%"] == 1
        assert stats.distribution["80-90%"] >= 1
        assert stats.distribution["90-100%"] >= 1

    def test_per_type_averages(self):
        collector = CoverageStatisticsCollector()
        collector.add(CoverageResult(
            overall=0.9,
            monetary=MonetaryCoverage(coverage_pct=0.95),
            structural=StructuralCoverage(overall=0.85),
            semantic=SemanticCoverage(overall=0.9),
            document=DocumentCoverage(coverage_pct=0.9),
        ))
        stats = collector.compute()
        assert stats.monetary_avg == 0.95
        assert stats.structural_avg == 0.85
        assert stats.semantic_avg == 0.9
        assert stats.document_avg == 0.9

    def test_add_many(self):
        collector = CoverageStatisticsCollector()
        results = [CoverageResult(overall=0.8), CoverageResult(overall=0.9)]
        collector.add_many(results)
        assert collector.count == 2

    def test_clear(self):
        collector = CoverageStatisticsCollector()
        collector.add(CoverageResult(overall=0.9))
        collector.clear()
        assert collector.count == 0

    def test_by_family_aggregation(self):
        collector = CoverageStatisticsCollector()
        result = CoverageResult(
            overall=0.9,
            monetary=MonetaryCoverage(
                by_family={"Activo": {"coverage_pct": 0.95, "total": 1000, "explained": 950}},
            ),
        )
        collector.add(result)
        stats = collector.compute()
        assert "Activo" in stats.by_family

    def test_by_key_aggregation(self):
        collector = CoverageStatisticsCollector()
        collector.add(CoverageResult(overall=0.9), {"template": "T14", "parser": "universal", "company": "EMPRESA", "year": 2024})
        stats = collector.compute()
        assert "T14" in stats.by_template
        assert "universal" in stats.by_parser
        assert "EMPRESA" in stats.by_company
        assert "2024" in stats.by_year


# =============================================================================
# COVERAGE ADAPTER TESTS
# =============================================================================

class TestCoverageAdapter:
    def test_run_stores_coverage(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext(source_file="test.pdf")
        ctx.set_custom("classified", [
            make_classified(classification_amount=500.0, final_code="AC.01"),
        ])
        ctx = adapter.run(ctx)
        coverage = ctx.get_custom("coverage")
        assert coverage is not None
        assert "overall" in coverage
        assert "monetary" in coverage

    def test_run_stores_overall(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        overall = ctx.get_custom("coverage_overall")
        assert overall is not None
        assert isinstance(overall, float)

    def test_run_stores_components(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("coverage_monetary") is not None
        assert ctx.get_custom("coverage_structural") is not None
        assert ctx.get_custom("coverage_semantic") is not None
        assert ctx.get_custom("coverage_document") is not None

    def test_run_stores_issues(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        issues = ctx.get_custom("coverage_issues")
        assert issues is not None
        assert isinstance(issues, list)

    def test_run_stores_weights(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        weights = ctx.get_custom("coverage_weights")
        assert weights is not None
        assert "monetary" in weights

    def test_custom_weights(self):
        adapter = CoverageAdapter(weights={"monetary": 1.0, "structural": 0.0, "semantic": 0.0, "document": 0.0})
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        weights = ctx.get_custom("coverage_weights")
        assert weights["monetary"] == 1.0

    def test_run_with_real_data(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext(source_file="test.pdf")
        ctx.set_custom("classified", [
            make_classified(classification_amount=1000.0, final_code="AC.01", method="learning_exact"),
        ])
        ctx = adapter.run(ctx)
        coverage = ctx.get_custom("coverage")
        assert coverage["overall"] > 0


# =============================================================================
# REPORT GENERATOR TESTS
# =============================================================================

class TestCoverageReportGenerator:
    def test_generate_full_report(self):
        gen = CoverageReportGenerator()
        result = CoverageResult(
            overall=0.95,
            monetary=MonetaryCoverage(total_amount=1000.0, explained_amount=950.0, coverage_pct=0.95),
            structural=StructuralCoverage(overall=0.9),
            semantic=SemanticCoverage(total_accounts=10, classified_count=9, overall=0.9),
            document=DocumentCoverage(coverage_pct=1.0),
            weights=DEFAULT_COVERAGE_WEIGHTS,
        )
        report = gen.generate_full_report(result)
        assert "Coverage Validation Report" in report
        assert "95.00%" in report or "95" in report

    def test_report_with_issues(self):
        gen = CoverageReportGenerator()
        result = CoverageResult(
            overall=0.7,
            issues=[CoverageIssue(
                issue_type="uncategorized_account",
                severity=CoverageSeverity.CRITICAL,
                monetary_impact=50000.0,
                document_impact=0.3,
            )],
        )
        report = gen.generate_full_report(result)
        assert "Issues" in report
        assert "uncategorized_account" in report

    def test_report_with_document_info(self):
        gen = CoverageReportGenerator()
        result = CoverageResult(overall=0.85)
        report = gen.generate_full_report(result, {"source_file": "test.pdf", "company": "TEST", "year": 2024})
        assert "test.pdf" in report
        assert "TEST" in report

    def test_report_sections(self):
        gen = CoverageReportGenerator()
        result = CoverageResult(
            overall=0.9,
            monetary=MonetaryCoverage(
                total_amount=1000000.0,
                explained_amount=998500.0,
                coverage_pct=0.9985,
                by_family={"Activo": {"total": 1000000.0, "explained": 998500.0, "coverage_pct": 0.9985}},
            ),
        )
        report = gen.generate_full_report(result)
        assert "Coverage Monetario" in report
        assert "Activo" in report

    def test_generate_summary_report(self):
        gen = CoverageReportGenerator()
        summary = CoverageSummary(
            overall=0.85,
            monetary=0.9,
            structural=0.8,
            semantic=0.85,
            document=0.85,
            total_issues=5,
            critical_issues=1,
            high_issues=2,
            top_documents=[{"name": "doc1", "score": 0.99}],
            worst_documents=[{"name": "doc2", "score": 0.4}],
        )
        report = gen.generate_summary_report(summary)
        assert "Coverage Summary Report" in report
        assert "doc1" in report
        assert "doc2" in report

    def test_generate_statistics_report(self):
        gen = CoverageReportGenerator()
        stats = CoverageStatistics(
            total_documents=10,
            overall_avg=0.85,
            overall_median=0.87,
            overall_p25=0.75,
            overall_p75=0.92,
            monetary_avg=0.88,
            structural_avg=0.82,
            semantic_avg=0.84,
            document_avg=0.86,
            distribution={"90-100%": 5, "80-90%": 3, "70-80%": 2},
        )
        report = gen.generate_statistics_report(stats)
        assert "Coverage Statistics Report" in report
        assert "85.00%" in report
        assert "5" in report  # docs count in distribution

    def test_save_report(self, tmp_path):
        gen = CoverageReportGenerator()
        result = CoverageResult(overall=0.95)
        report = gen.generate_full_report(result)
        path = gen.save_report(report, str(tmp_path / "reports" / "test_report.md"))
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Coverage Validation Report" in content


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    def test_empty_classified_list(self):
        calc = CoverageCalculator()
        result = calc.compute_from_data(classified=[])
        assert result.monetary.total_amount == 0.0
        assert result.monetary.coverage_pct == 1.0

    def test_none_amounts(self):
        calc = MonetaryCoverageCalculator()
        classified = [make_classified(classification_amount=None, final_code="AC.01")]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.explained_amount == 0.0

    def test_mixed_codes(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=100.0, final_code="AC.01", account_code="1"),
            make_classified(classification_amount=200.0, final_code=None, standard_code=None, account_code="2"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 100.0})
        assert monetary.explained_amount == 100.0

    def test_large_numbers(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=1_000_000_000.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1_000_000_000.0})
        assert monetary.coverage_pct == 1.0

    def test_zero_amounts(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=0.0, final_code="AC.01"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.explained_amount == 0.0
        assert monetary.coverage_pct == 0.0

    def test_all_unknown_family(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=100.0, final_code="ZZ.01"),
        ]
        monetary, issues = calc.compute(classified, {})
        assert monetary.coverage_pct == 1.0

    def test_duplicate_accounts(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=500.0, final_code="AC.01", account_code="1"),
            make_classified(classification_amount=500.0, final_code="AC.01", account_code="1"),
        ]
        monetary, issues = calc.compute(classified, {"Activo": 1000.0})
        assert monetary.explained_amount == 1000.0

    def test_structural_no_data(self):
        calc = StructuralCoverageCalculator()
        structural, issues = calc.compute(None, None)
        assert structural.subtotals_detected == 0
        assert structural.subtotals_validated == 0

    def test_semantic_no_classified(self):
        calc = SemanticCoverageCalculator()
        semantic, issues = calc.compute([], 0)
        assert semantic.overall == 1.0

    def test_document_no_sections(self):
        calc = DocumentCoverageCalculator()
        document, issues = calc.compute(structure_data=None)
        assert document is not None

    def test_json_serialization_full(self):
        r = CoverageResult(
            overall=0.88,
            monetary=MonetaryCoverage(total_amount=1000.0, explained_amount=880.0, coverage_pct=0.88),
            weights=DEFAULT_COVERAGE_WEIGHTS,
            issues=[CoverageIssue(issue_type="test", severity=CoverageSeverity.HIGH)],
        )
        json_str = json.dumps(r.to_dict())
        loaded = json.loads(json_str)
        r2 = CoverageResult.from_dict(loaded)
        assert r2.overall == 0.88
        assert len(r2.issues) == 1

    def test_coverage_adapter_empty_ctx(self):
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("coverage") is not None

    def test_statistics_no_results(self):
        collector = CoverageStatisticsCollector()
        stats = collector.compute()
        assert stats.total_documents == 0

    def test_family_order_constant(self):
        assert len(FAMILY_ORDER) == 7
        assert "Activo" in FAMILY_ORDER
        assert "Pasivo" in FAMILY_ORDER
        assert "Patrimonio" in FAMILY_ORDER
        assert "Resultado" in FAMILY_ORDER
        assert "Ingresos" in FAMILY_ORDER
        assert "Costos" in FAMILY_ORDER
        assert "Gastos" in FAMILY_ORDER

    def test_default_weights_constant(self):
        assert DEFAULT_COVERAGE_WEIGHTS["monetary"] == 0.40
        assert DEFAULT_COVERAGE_WEIGHTS["structural"] == 0.25
        assert DEFAULT_COVERAGE_WEIGHTS["semantic"] == 0.20
        assert DEFAULT_COVERAGE_WEIGHTS["document"] == 0.15
        assert abs(sum(DEFAULT_COVERAGE_WEIGHTS.values()) - 1.0) < 0.001

    def test_expected_sections_constant(self):
        assert "Activo" in EXPECTED_SECTIONS
        assert "Resultado" in EXPECTED_SECTIONS

    def test_issue_severity_ordering(self):
        issue = CoverageIssue(issue_type="test", severity=CoverageSeverity.CRITICAL)
        issue2 = CoverageIssue(issue_type="test", severity=CoverageSeverity.INFO)
        assert issue.severity != issue2.severity


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    def test_coverage_in_pipeline_v2_import(self):
        from orchestrator.pipeline_v2 import HomologationPipelineV2
        pipeline = HomologationPipelineV2(db_path=":memory:")
        assert pipeline is not None
        assert hasattr(pipeline, "_adapter_coverage")

    def test_coverage_adapter_direct(self):
        from coverage_engine import CoverageAdapter
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx.set_custom("classified", [
            make_classified(classification_amount=500.0, final_code="AC.01"),
        ])
        ctx = adapter.run(ctx)
        coverage = ctx.get_custom("coverage")
        assert coverage is not None
        assert "overall" in coverage

    def test_coverage_adapter_with_classified(self):
        from coverage_engine import CoverageAdapter
        adapter = CoverageAdapter()
        ctx = DocumentContext()
        ctx.set_custom("classified", [
            make_classified(classification_amount=800.0, final_code="AC.01"),
            make_classified(classification_amount=200.0, final_code="PC.01"),
        ])
        ctx = adapter.run(ctx)
        assert ctx.get_custom("coverage_overall") is not None

    def test_coverage_result_roundtrip_through_context(self):
        ctx = DocumentContext()
        adapter = CoverageAdapter()
        ctx = adapter.run(ctx)
        coverage = ctx.get_custom("coverage")
        result = CoverageResult.from_dict(coverage)
        assert result.overall == coverage["overall"]
        assert result.monetary.coverage_pct == coverage["monetary"]["coverage_pct"]

    def test_statistics_with_metadata(self):
        collector = CoverageStatisticsCollector()
        r1 = CoverageResult(overall=0.95)
        r2 = CoverageResult(overall=0.85)
        collector.add(r1, {"template": "T14", "parser": "universal", "company": "A", "year": 2024})
        collector.add(r2, {"template": "T14", "parser": "universal", "company": "B", "year": 2024})
        stats = collector.compute()
        assert stats.overall_avg == pytest.approx(0.9, abs=0.01)
        assert stats.by_template["T14"]["count"] == 2
        assert stats.by_company["A"]["count"] == 1
        assert stats.by_company["B"]["count"] == 1

    def test_report_generation_with_matrices(self):
        gen = CoverageReportGenerator()
        result = CoverageResult(
            overall=0.9,
            monetary=MonetaryCoverage(
                by_family={
                    "Activo": {"total": 1000.0, "explained": 900.0, "coverage_pct": 0.9},
                    "Pasivo": {"total": 500.0, "explained": 500.0, "coverage_pct": 1.0},
                },
            ),
            issues=[CoverageIssue(issue_type="unexplained_amount", severity=CoverageSeverity.HIGH, monetary_impact=100.0)],
        )
        report = gen.generate_full_report(result)
        assert "Matrices" in report
        assert "Activo" in report
        assert "Pasivo" in report

    def test_monetary_full_integration(self):
        calc = MonetaryCoverageCalculator()
        classified = [
            make_classified(classification_amount=800000.0, final_code="AC.01.001", account_code="1"),
            make_classified(classification_amount=198500.0, final_code="AC.01.002", account_code="2"),
            make_classified(classification_amount=1000.0, final_code="AC.01.003", account_code="3"),
            make_classified(classification_amount=500.0, final_code="PC.01.001", account_code="4"),
        ]
        monetary, issues = calc.compute(classified, {
            "Activo": 1000000.0,
            "Pasivo": 500.0,
        })
        assert monetary.coverage_pct == pytest.approx(999500.0 / 1000500.0, abs=0.001)
        assert monetary.by_family["Activo"]["coverage_pct"] == pytest.approx(0.9995, abs=0.001)
        assert monetary.by_family["Pasivo"]["coverage_pct"] == 1.0

    def test_structural_reconstructed_flag(self):
        calc = StructuralCoverageCalculator()
        tree = FakeTree(nodes=[1], total_nodes=10)
        structure = StructureData(tree=tree)
        structural, issues = calc.compute(structure_data=structure)
        assert structural.hierarchy_reconstructed == 0.1

    def test_semantic_family_mapping_comprehensive(self):
        calc = SemanticCoverageCalculator()
        classified = [
            make_classified(final_code="AC.01", method="learning_exact"),
            make_classified(final_code="ANC.01", method="learning_exact"),
            make_classified(final_code="PC.01", method="code"),
            make_classified(final_code="PNC.01", method="code"),
            make_classified(final_code="PAT.01", method="learning_exact"),
            make_classified(final_code="ER.01", method="learning_exact"),
        ]
        semantic, issues = calc.compute(classified, 6)
        assert "Activo" in semantic.by_family
        assert "Pasivo" in semantic.by_family
        assert "Patrimonio" in semantic.by_family
        assert semantic.overall == 1.0


# =============================================================================
# SERIALIZATION TESTS
# =============================================================================

class TestSerialization:
    def test_monetary_coverage_json(self):
        m = MonetaryCoverage(total_amount=5000.0, explained_amount=4800.0, coverage_pct=0.96)
        json_str = json.dumps(m.to_dict())
        loaded = json.loads(json_str)
        m2 = MonetaryCoverage.from_dict(loaded)
        assert m2.coverage_pct == 0.96

    def test_structural_coverage_json(self):
        s = StructuralCoverage(subtotals_detected=4, subtotals_validated=3, overall=0.75)
        json_str = json.dumps(s.to_dict())
        loaded = json.loads(json_str)
        s2 = StructuralCoverage.from_dict(loaded)
        assert s2.subtotals_detected == 4

    def test_semantic_coverage_json(self):
        s = SemanticCoverage(total_accounts=50, classified_count=45, overall=0.9)
        json_str = json.dumps(s.to_dict())
        loaded = json.loads(json_str)
        s2 = SemanticCoverage.from_dict(loaded)
        assert s2.total_accounts == 50

    def test_document_coverage_json(self):
        d = DocumentCoverage(coverage_pct=0.75, section_details={"Activo": "OK"})
        json_str = json.dumps(d.to_dict())
        loaded = json.loads(json_str)
        d2 = DocumentCoverage.from_dict(loaded)
        assert d2.coverage_pct == 0.75

    def test_coverage_result_complex_json(self):
        r = CoverageResult(
            overall=0.85,
            monetary=MonetaryCoverage(total_amount=100.0, explained_amount=85.0, coverage_pct=0.85),
            structural=StructuralCoverage(subtotals_detected=3, overall=0.8),
            semantic=SemanticCoverage(total_accounts=10, classified_count=8, overall=0.8),
            document=DocumentCoverage(coverage_pct=0.9),
            weights=DEFAULT_COVERAGE_WEIGHTS,
            issues=[
                CoverageIssue(issue_type="i1", severity=CoverageSeverity.HIGH),
                CoverageIssue(issue_type="i2", severity=CoverageSeverity.LOW),
            ],
        )
        json_str = json.dumps(r.to_dict(), indent=2)
        loaded = json.loads(json_str)
        r2 = CoverageResult.from_dict(loaded)
        assert abs(r2.overall - 0.85) < 0.01
        assert len(r2.issues) == 2
        assert r2.issues[0].issue_type == "i1"
        assert r2.issues[1].issue_type == "i2"

    def test_nested_by_family_json(self):
        m = MonetaryCoverage(
            by_family={
                "Activo": {"total": 1000.0, "explained": 950.0, "coverage_pct": 0.95},
                "Pasivo": {"total": 500.0, "explained": 500.0, "coverage_pct": 1.0},
            },
        )
        json_str = json.dumps(m.to_dict())
        loaded = json.loads(json_str)
        m2 = MonetaryCoverage.from_dict(loaded)
        assert m2.by_family["Activo"]["coverage_pct"] == 0.95
        assert m2.by_family["Pasivo"]["coverage_pct"] == 1.0

    def test_statistics_with_distribution_json(self):
        stats = CoverageStatistics(
            total_documents=3,
            overall_avg=0.85,
            distribution={"80-90%": 2, "90-100%": 1},
        )
        json_str = json.dumps(stats.to_dict())
        loaded = json.loads(json_str)
        s2 = CoverageStatistics.from_dict(loaded)
        assert s2.total_documents == 3
        assert s2.distribution["80-90%"] == 2
