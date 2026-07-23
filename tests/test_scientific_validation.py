from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scientific_validation import (
    GoldStandardCase,
    ValidationResult,
    ErrorCategory,
    ValidationDataset,
    Agreement,
    Metrics,
    ValidationReports,
)


def make_sample_case(case_id: str = "CASE-001", status: str = "pending") -> GoldStandardCase:
    return GoldStandardCase(
        case_id=case_id,
        company="Company A",
        document="Balance 2024.pdf",
        layout="validacion",
        ocr_used=False,
        account_name="Caja General",
        original_amount=100000.0,
        expected_code="AC.01",
        expected_concept="Caja y Bancos",
        review_status=status,
        reviewer="",
        review_date="",
        confidence_human=0.0,
        comments="",
        source_document="Balance 2024.pdf",
        page=1,
        line=5,
        decision_trace_reference="doc1",
        parser_confidence=0.9,
        layout_confidence=0.8,
        column_mapping_confidence=0.7,
        candidate_accept_rate=0.85,
    )


def make_results(correct_count: int = 3, incorrect_count: int = 1) -> list[ValidationResult]:
    results = []
    for i in range(correct_count):
        results.append(ValidationResult(
            expected="AC.01", predicted="AC.01", correct=True,
            decision_type="accepted", decision_code="D001",
            confidence_system=0.95, confidence_human=1.0,
            difference_reason="", error_category="CMCC",
            review_time_seconds=30.0,
        ))
    for i in range(incorrect_count):
        results.append(ValidationResult(
            expected="ER.01", predicted="UNKNOWN", correct=False,
            decision_type="rejected", decision_code="D201",
            confidence_system=0.0, confidence_human=1.0,
            difference_reason="System could not classify",
            error_category="UNKNOWN",
            review_time_seconds=45.0,
        ))
    return results


class TestErrorCategory:
    def test_values(self):
        assert ErrorCategory.PARSER.value == "PARSER"
        assert ErrorCategory.UNKNOWN.value == "UNKNOWN"
        assert ErrorCategory.HUMAN.value == "HUMAN"

    def test_describe(self):
        assert ErrorCategory.OCR.describe() == "OCR"

    def test_members_count(self):
        assert len(ErrorCategory) == 14


class TestGoldStandardCase:
    def test_create(self):
        c = make_sample_case()
        assert c.case_id == "CASE-001"
        assert c.expected_code == "AC.01"

    def test_to_dict(self):
        c = make_sample_case()
        d = c.to_dict()
        assert d["case_id"] == "CASE-001"
        assert d["expected_code"] == "AC.01"

    def test_fields(self):
        f = GoldStandardCase.fields()
        assert "case_id" in f
        assert "expected_code" in f
        assert "parser_confidence" in f
        assert len(f) == 22


class TestValidationResult:
    def test_create_correct(self):
        r = ValidationResult(
            expected="AC.01", predicted="AC.01", correct=True,
            decision_type="accepted", decision_code="D001",
            confidence_system=0.95, confidence_human=1.0,
            difference_reason="", error_category="CMCC",
            review_time_seconds=30.0,
        )
        assert r.correct is True
        assert r.error_category == "CMCC"

    def test_create_incorrect(self):
        r = ValidationResult(
            expected="ER.01", predicted="UNKNOWN", correct=False,
            decision_type="rejected", decision_code="D201",
            confidence_system=0.0, confidence_human=1.0,
            difference_reason="No match", error_category="UNKNOWN",
            review_time_seconds=45.0,
        )
        assert r.correct is False

    def test_to_dict(self):
        r = make_results(1, 0)[0]
        d = r.to_dict()
        assert d["correct"] is True
        assert d["decision_code"] == "D001"

    def test_fields(self):
        f = ValidationResult.fields()
        assert "expected" in f
        assert "error_category" in f
        assert len(f) == 10


class TestValidationDataset:
    def test_empty(self):
        ds = ValidationDataset()
        assert ds.total == 0
        assert ds.pending == []
        assert ds.reviewed == []

    def test_add_case(self):
        ds = ValidationDataset()
        ds.add_case(make_sample_case())
        assert ds.total == 1

    def test_pending_reviewed(self):
        ds = ValidationDataset()
        ds.add_case(make_sample_case("CASE-001", "pending"))
        ds.add_case(make_sample_case("CASE-002", "reviewed"))
        assert len(ds.pending) == 1
        assert len(ds.reviewed) == 1

    def test_export_excel(self, tmp_path):
        ds = ValidationDataset()
        ds.add_case(make_sample_case())
        p = ds.export_excel(tmp_path / "dataset.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 1

    def test_export_excel_empty(self, tmp_path):
        ds = ValidationDataset()
        p = ds.export_excel(tmp_path / "empty.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 0

    def test_export_csv(self, tmp_path):
        ds = ValidationDataset()
        ds.add_case(make_sample_case())
        p = ds.export_csv(tmp_path / "dataset.csv")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "case_id" in text

    def test_export_json(self, tmp_path):
        ds = ValidationDataset()
        ds.add_case(make_sample_case())
        ds.add_result(make_results(1, 0)[0])
        p = ds.export_json(tmp_path / "dataset.json")
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert len(data["cases"]) == 1
        assert len(data["results"]) == 1

    def test_import_excel(self, tmp_path):
        ds = ValidationDataset()
        ds.add_case(make_sample_case())
        p = ds.export_excel(tmp_path / "source.xlsx")
        ds2 = ValidationDataset()
        count = ds2.import_excel(p)
        assert count == 1
        assert ds2.total == 1

    def test_generate_template(self, tmp_path):
        ds = ValidationDataset()
        p = ds.generate_template(tmp_path / "template.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 0
        assert "case_id" in df.columns

    def test_build_results_from_traces(self):
        ds = ValidationDataset()
        ds.add_case(make_sample_case("doc1"))
        traces = [
            {"document_id": "doc1", "official_classification": "AC.01",
             "candidate_status": "accepted", "decision_code": "D001",
             "official_confidence": 0.95},
            {"document_id": "doc2", "official_classification": "UNKNOWN",
             "candidate_status": "rejected", "decision_code": "D201",
             "official_confidence": 0.0},
        ]
        results = ds.build_results_from_traces(traces)
        assert len(results) == 1
        assert results[0].correct is True

    def test_build_results_from_traces_mismatch(self):
        ds = ValidationDataset()
        ds.add_case(make_sample_case("doc1"))
        traces = [
            {"document_id": "doc1", "official_classification": "ER.01",
             "candidate_status": "accepted", "decision_code": "D001",
             "official_confidence": 0.95},
        ]
        results = ds.build_results_from_traces(traces)
        assert results[0].correct is False
        assert results[0].error_category != "UNKNOWN"


class TestAgreement:
    def test_perfect_agreement(self):
        a = Agreement(["A", "B", "C"], ["A", "B", "C"])
        assert a.observed_agreement() == 1.0
        assert a.cohen_kappa() == 1.0
        assert len(a.disagreement_list()) == 0

    def test_no_agreement(self):
        a = Agreement(["A", "A"], ["B", "B"])
        assert a.observed_agreement() == 0.0
        assert a.cohen_kappa() <= 0

    def test_partial_agreement(self):
        a = Agreement(["A", "B", "C"], ["A", "B", "D"])
        assert abs(a.observed_agreement() - 2 / 3) < 0.001
        assert len(a.disagreement_list()) == 1

    def test_empty(self):
        a = Agreement([], [])
        assert a.observed_agreement() == 0.0
        assert a.cohen_kappa() == 0.0
        assert a.disagreement_list() == []

    def test_interpret_kappa(self):
        assert "Almost perfect" in Agreement.interpret_kappa(0.85)
        assert "Poor" in Agreement.interpret_kappa(-0.1)
        assert "Slight" in Agreement.interpret_kappa(0.1)

    def test_summary(self):
        a = Agreement(["X", "Y"], ["X", "Y"])
        s = a.summary()
        assert s["n"] == 2
        assert s["observed_agreement_pct"] == 100.0
        assert s["cohen_kappa"] == 1.0


class TestMetrics:
    def test_empty(self):
        m = Metrics([])
        assert m.accuracy() == 0.0
        assert m.macro_f1() == 0.0
        assert m.micro_f1() == 0.0

    def test_accuracy_perfect(self):
        results = make_results(5, 0)
        m = Metrics(results)
        assert m.accuracy() == 1.0

    def test_accuracy_partial(self):
        results = make_results(3, 1)
        m = Metrics(results)
        assert m.accuracy() == 0.75

    def test_per_label_metrics(self):
        results = make_results(3, 1)
        m = Metrics(results)
        labels = m.per_label_metrics()
        assert len(labels) > 0

    def test_macro_f1(self):
        results = make_results(3, 1)
        m = Metrics(results)
        macro = m.macro_f1()
        assert 0 <= macro <= 1

    def test_micro_f1(self):
        results = make_results(3, 1)
        m = Metrics(results)
        micro = m.micro_f1()
        assert 0 <= micro <= 1

    def test_precision_by_type(self):
        results = make_results(3, 1)
        m = Metrics(results)
        by_type = m.precision_by_type()
        assert len(by_type) > 0

    def test_precision_by_decision_code(self):
        results = make_results(3, 1)
        m = Metrics(results)
        by_code = m.precision_by_decision_code()
        assert len(by_code) > 0

    def test_precision_by_error_category(self):
        results = make_results(3, 1)
        m = Metrics(results)
        by_cat = m.precision_by_error_category()
        assert len(by_cat) > 0

    def test_confusion_matrix(self):
        results = make_results(3, 1)
        m = Metrics(results)
        cm = m.confusion_matrix()
        assert not cm.empty
        assert "expected" in cm.columns

    def test_top_errors(self):
        results = make_results(3, 1)
        m = Metrics(results)
        errors = m.top_errors(5)
        assert len(errors) > 0

    def test_error_summary(self):
        results = make_results(3, 1)
        m = Metrics(results)
        es = m.error_summary()
        assert es["total_errors"] >= 1

    def test_summary(self):
        results = make_results(3, 1)
        m = Metrics(results)
        s = m.summary()
        assert s["total"] == 4
        assert s["correct"] == 3
        assert s["accuracy"] > 0


class TestValidationReports:
    def make_fixture(self) -> tuple[ValidationDataset, Metrics, None]:
        ds = ValidationDataset()
        for i in range(5):
            ds.add_case(make_sample_case(f"CASE-{i:03d}", "reviewed"))
        for r in make_results(8, 2):
            ds.add_result(r)
        m = Metrics(ds.results)
        return ds, m, None

    def test_gold_standard_template(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_gold_standard_template(tmp_path / "template.xlsx")
        assert p.exists()

    def test_validation_dataset(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_validation_dataset(tmp_path / "dataset.xlsx")
        assert p.exists()

    def test_validation_summary(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_validation_summary(tmp_path / "summary.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) > 0

    def test_confusion_matrix(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_confusion_matrix(tmp_path / "cm.xlsx")
        assert p.exists()

    def test_error_analysis(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_error_analysis(tmp_path / "errors.xlsx")
        assert p.exists()

    def test_agreement_report_no_agreement(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_agreement_report(tmp_path / "agreement.xlsx")
        assert p.exists()

    def test_agreement_report_with_agreement(self, tmp_path):
        ds, m, _ = self.make_fixture()
        a = Agreement(["A", "B"], ["A", "B"])
        r = ValidationReports(ds, m, a)
        p = r.generate_agreement_report(tmp_path / "agreement.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert "Cohen Kappa" in df["metric"].values

    def test_precision_dashboard(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_precision_dashboard(tmp_path / "dashboard.xlsx")
        assert p.exists()

    def test_markdown_empty(self, tmp_path):
        ds = ValidationDataset()
        m = Metrics([])
        r = ValidationReports(ds, m)
        p = r.generate_markdown(tmp_path / "report.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Empty Dataset" in text

    def test_markdown_with_data(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_markdown(tmp_path / "report.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Scientific Validation Report" in text
        assert "Accuracy" in text

    def test_statistics_json(self, tmp_path):
        ds, m, _ = self.make_fixture()
        r = ValidationReports(ds, m)
        p = r.generate_statistics_json(tmp_path / "stats.json")
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert "dataset" in data
        assert "metrics" in data

    def test_generate_all(self, tmp_path):
        ds, m, _ = self.make_fixture()
        reports = ValidationReports.generate_all(ds, m, None, tmp_path)
        expected = [
            "gold_standard_template.xlsx", "validation_dataset.xlsx",
            "validation_summary.xlsx", "confusion_matrix.xlsx",
            "error_analysis.xlsx", "agreement_report.xlsx",
            "precision_dashboard.xlsx", "scientific_validation.md",
            "validation_statistics.json",
        ]
        for name in expected:
            assert (tmp_path / name).exists(), f"{name} not found"


class TestRunner:
    def test_import(self):
        from scripts import run_scientific_validation
        assert hasattr(run_scientific_validation, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_scientific_validation")
        assert mod is not None
