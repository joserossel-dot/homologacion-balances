from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from knowledge_evolution import KnowledgeSnapshot, KnowledgeDiff, ChangeType, ImpactAnalyzer, EvolutionReport
from knowledge_evolution.knowledge_diff import KnowledgeChange


SAMPLE_CMCC = [
    {"codigo": "AC.01", "nombre": "Caja y Bancos", "variantes": ["caja", "bancos", "banco estado"],
     "sinonimos": ["efectivo"], "patrones": [], "ejemplos": [], "empresas": [], "metadata": {}},
    {"codigo": "ER.01", "nombre": "Ventas", "variantes": ["ventas", "ingresos"],
     "sinonimos": [], "patrones": [], "ejemplos": [], "empresas": [], "metadata": {}},
    {"codigo": "PC.01", "nombre": "Proveedores", "variantes": ["proveedores"],
     "sinonimos": [], "patrones": [], "ejemplos": [], "empresas": [], "metadata": {}},
]


def make_snapshot_dict() -> dict:
    return {
        "timestamp": "2024-01-01T00:00:00",
        "version": "1.0",
        "cmcc_hash": "abc123",
        "dictionary_hash": "abc123",
        "variant_count": 6,
        "concept_count": 3,
        "rule_count": 0,
        "synonym_count": 1,
        "parser_version": "3.0",
        "shadow_version": "1.0",
        "decision_trace_version": "1.0",
        "statistics": {
            "total_accounts": 100,
            "total_classified": 18,
            "total_unknown": 82,
            "classify_rate": 18.0,
            "unknown_rate": 82.0,
            "companies": 5,
            "files": 10,
        },
        "variants_by_code": {
            "AC.01": ["caja", "bancos", "banco estado"],
            "ER.01": ["ventas", "ingresos"],
            "PC.01": ["proveedores"],
        },
        "unknown_names": [
            "caja general", "banco estado cta cte", "banco de chile",
            "proveedores varios", "ventas netas", "ingresos brutos",
            "gastos administrativos", "activo fijo", "maquinarias",
        ],
        "concept_counts": {"AC.01": 8, "ER.01": 6, "PC.01": 4},
        "shadow_count": 5,
    }


class TestKnowledgeSnapshot:
    def test_capture_with_real_data(self):
        snap = KnowledgeSnapshot()
        data = snap.capture()
        assert data["concept_count"] == 52
        assert data["variant_count"] >= 3000
        assert "cmcc_hash" in data
        assert "statistics" in data
        assert "variants_by_code" in data
        assert "unknown_names" in data

    def test_save_and_load(self, tmp_path):
        snap = KnowledgeSnapshot()
        data = snap.capture()
        p = tmp_path / "snapshot.json"
        snap.save(p)
        assert p.exists()
        loaded = KnowledgeSnapshot.load(p)
        assert loaded["cmcc_hash"] == data["cmcc_hash"]
        assert loaded["variant_count"] == data["variant_count"]

    def test_capture_has_all_fields(self):
        snap = KnowledgeSnapshot(
            cmcc_path="nonexistent.json",
            audit_path="nonexistent.json",
            shadow_path="nonexistent.xlsx",
            trace_path="nonexistent.json",
        )
        data = snap.capture()
        assert data["variant_count"] == 0
        assert data["concept_count"] == 0
        assert "timestamp" in data


class TestKnowledgeDiff:
    def test_variant_diff_added(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        b["variants_by_code"]["AC.01"] = ["caja", "bancos", "banco estado", "caja general"]
        b["variant_count"] = 7
        diff = KnowledgeDiff(a, b)
        vd = diff.variant_diff()
        assert "AC.01" in vd
        assert "caja general" in vd["AC.01"]["added"]
        assert vd["AC.01"]["delta"] == 1

    def test_variant_diff_removed(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        b["variants_by_code"]["AC.01"] = ["caja", "bancos"]
        b["variant_count"] = 5
        diff = KnowledgeDiff(a, b)
        vd = diff.variant_diff()
        assert "AC.01" in vd
        assert "banco estado" in vd["AC.01"]["removed"]
        assert vd["AC.01"]["delta"] == -1

    def test_no_diff_when_identical(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        diff = KnowledgeDiff(a, b)
        vd = diff.variant_diff()
        assert vd == {}

    def test_concept_count_diff(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        del b["variants_by_code"]["ER.01"]
        b["variant_count"] = 4
        diff = KnowledgeDiff(a, b)
        assert diff.concept_count_diff() <= 0

    def test_unknown_diff(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        b["statistics"]["total_unknown"] = 72
        diff = KnowledgeDiff(a, b)
        assert diff.unknown_diff() == -10

    def test_classify_rate_diff(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        b["statistics"]["classify_rate"] = 25.0
        diff = KnowledgeDiff(a, b)
        assert diff.classify_rate_diff() == 7.0

    def test_summary(self):
        a = make_snapshot_dict()
        b = make_snapshot_dict()
        b["variants_by_code"]["AC.01"].append("caja general")
        b["variant_count"] = 7
        b["statistics"]["unknown_count"] = 80
        diff = KnowledgeDiff(a, b)
        s = diff.summary()
        assert "snapshot_a_version" in s
        assert "variant_diff" in s
        assert s["concepts_changed"] == ["AC.01"]


class TestKnowledgeChange:
    def test_create(self):
        chg = KnowledgeChange(
            change_id="CHG-001", date="2024-01-01", source="test",
            change_type="NEW_VARIANT", concept="AC.01",
            old_value="", new_value="caja general",
            reason="test", impact_accounts=10, impact_documents=5,
            impact_companies=3,
        )
        assert chg.change_id == "CHG-001"
        assert not chg.approved

    def test_to_dict(self):
        chg = KnowledgeChange(
            change_id="CHG-001", date="2024-01-01", source="test",
            change_type="NEW_VARIANT", concept="AC.01",
            old_value="", new_value="caja general",
            reason="test", impact_accounts=10, impact_documents=5,
            impact_companies=3,
        )
        d = chg.to_dict()
        assert d["change_id"] == "CHG-001"
        assert d["approved"] is False

    def test_approved_flag(self):
        chg = KnowledgeChange(
            change_id="CHG-002", date="2024-01-01", source="test",
            change_type="NEW_VARIANT", concept="ER.01",
            old_value="", new_value="new variant",
            reason="test", impact_accounts=5, impact_documents=2,
            impact_companies=1, approved=True, reviewed_by="reviewer",
            review_date="2024-01-02",
        )
        assert chg.approved
        assert chg.reviewed_by == "reviewer"


class TestChangeType:
    def test_values(self):
        assert ChangeType.NEW_VARIANT.value == "NEW_VARIANT"
        assert ChangeType.REMOVED_VARIANT.value == "REMOVED_VARIANT"
        assert ChangeType.MANUAL_OVERRIDE.value == "MANUAL_OVERRIDE"

    def test_members_count(self):
        assert len(ChangeType) == 10


class TestImpactAnalyzer:
    def test_simulate_add_variant_new(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_add_variant("AC.01", "caja general")
        assert result["already_exists"] is False
        assert result["new_matched_accounts"] >= 1
        assert result["concept_code"] == "AC.01"

    def test_simulate_add_variant_existing(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_add_variant("AC.01", "caja")
        assert result["already_exists"] is True
        assert result["new_matched_accounts"] >= 1  # "caja" matches "caja general"

    def test_simulate_add_empty_variant(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_add_variant("AC.01", "")
        assert "error" in result

    def test_simulate_add_variant_no_match(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_add_variant("AC.01", "xyz_nonexistent_123")
        assert result["new_matched_accounts"] == 0

    def test_simulate_bulk(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_bulk({
            "AC.01": ["caja general", "banco de chile"],
            "ER.01": ["ventas netas"],
        })
        assert result["total_new_accounts"] >= 2
        assert "AC.01" in result["concept_gains"]
        assert "ER.01" in result["concept_gains"]
        assert len(result["changes"]) >= 3
        assert "snapshot_before" in result
        assert "snapshot_after" in result

    def test_simulate_bulk_empty(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        result = analyzer.simulate_bulk({})
        assert result["total_new_accounts"] == 0
        assert result["changes"] == []

    def test_coverage_before(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        cov = analyzer.coverage_before()
        assert cov["total_accounts"] == 100
        assert cov["classify_rate"] == 18.0

    def test_unknown_analysis(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        ua = analyzer.unknown_analysis()
        assert ua["total_unknown"] == 9
        assert ua["unique_names"] == 9
        assert len(ua["top_tokens"]) > 0

    def test_unknown_analysis_empty(self):
        snap = make_snapshot_dict()
        snap["unknown_names"] = []
        analyzer = ImpactAnalyzer(snap)
        ua = analyzer.unknown_analysis()
        assert ua["total_unknown"] == 0

    def test_simulate_add_all_variants(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        results = analyzer.simulate_add_all_variants({
            "AC.01": ["new1", "new2"],
        })
        assert len(results) == 2


class TestEvolutionReport:
    def make_fixture(self):
        snap = make_snapshot_dict()
        analyzer = ImpactAnalyzer(snap)
        impact = analyzer.simulate_bulk({
            "AC.01": ["caja general", "banco de chile"],
        })
        diff = {"diff_summary": impact.get("diff_summary", {})}
        return EvolutionReport(snap, impact, diff)

    def test_generate_changes_xlsx(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_changes_xlsx(tmp_path / "changes.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) >= 2

    def test_generate_timeline_xlsx(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_timeline_xlsx(tmp_path / "timeline.xlsx")
        assert p.exists()

    def test_generate_impact_summary_xlsx(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_impact_summary_xlsx(tmp_path / "impact.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 4

    def test_generate_concept_growth_xlsx(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_concept_growth_xlsx(tmp_path / "growth.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) >= 1

    def test_generate_knowledge_diff_xlsx(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_knowledge_diff_xlsx(tmp_path / "diff.xlsx")
        assert p.exists()

    def test_generate_markdown(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_markdown(tmp_path / "report.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Knowledge Evolution Report" in text
        assert "Total Changes" in text
        assert "AC.01" in text
        assert "Shadow Mode" in text or "Simulation" in text or "simulation" in text

    def test_generate_statistics_json(self, tmp_path):
        report = self.make_fixture()
        p = report.generate_statistics_json(tmp_path / "stats.json")
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert "snapshot" in data
        assert "impact" in data
        assert "diff" in data

    def test_generate_all_outputs(self, tmp_path):
        report = self.make_fixture()
        report.generate_changes_xlsx(tmp_path / "changes.xlsx")
        report.generate_timeline_xlsx(tmp_path / "timeline.xlsx")
        report.generate_impact_summary_xlsx(tmp_path / "impact.xlsx")
        report.generate_concept_growth_xlsx(tmp_path / "growth.xlsx")
        report.generate_knowledge_diff_xlsx(tmp_path / "diff.xlsx")
        report.generate_markdown(tmp_path / "report.md")
        report.generate_statistics_json(tmp_path / "stats.json")
        assert len(list(tmp_path.iterdir())) == 7


class TestRunner:
    def test_import(self):
        from scripts import run_knowledge_evolution
        assert hasattr(run_knowledge_evolution, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_knowledge_evolution")
        assert mod is not None
