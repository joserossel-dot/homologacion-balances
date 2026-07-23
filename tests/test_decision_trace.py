from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from explainability import (
    DecisionCode,
    DecisionTrace,
    TraceStage,
    TraceBuilder,
    TraceReport,
    TraceExporter,
)


class TestDecisionCode:
    def test_enum_values(self):
        assert DecisionCode.D001.value == "Exact Variant"
        assert DecisionCode.D101.value == "Parser Reject"
        assert DecisionCode.D201.value == "Unknown Variant"

    def test_describe(self):
        assert DecisionCode.D001.describe() == "Exact Variant"
        assert DecisionCode.D007.describe() == "Shadow CMCC"

    def test_members_count(self):
        assert len(DecisionCode) == 18

    def test_unique_values(self):
        values = [e.value for e in DecisionCode]
        assert len(values) == len(set(values))


class TestTraceStage:
    def test_values(self):
        assert TraceStage.PARSER.value == "Parser"
        assert TraceStage.CMCC.value == "CMCC"
        assert TraceStage.FINAL.value == "Final Decision"


class TestDecisionTrace:
    def test_create_minimal(self):
        t = DecisionTrace(
            document_id="doc1",
            company="Company A",
            layout="validacion",
            layout_confidence=0.9,
            ocr_confidence=0.8,
            parser_confidence=0.0,
            column_mapping_confidence=0.0,
            candidate_accept_rate=0.0,
            candidate_status="rejected",
            candidate_reasons=[],
            normalized_name="impuesto renta",
            original_name="Impuesto Renta",
            cmcc_match=False,
            cmcc_match_type="",
            cmcc_variant="",
            cmcc_score=0.0,
            dictionary_match=False,
            dictionary_source="",
            official_classification="UNKNOWN",
            official_confidence=0.0,
            shadow_classification="",
            shadow_confidence=0.0,
            decision_code="D201",
            decision_description="Unknown Variant",
            timestamp="2024-01-01T00:00:00",
        )
        assert t.document_id == "doc1"
        assert t.decision_code == "D201"
        assert t.official_classification == "UNKNOWN"

    def test_to_dict(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="l", layout_confidence=0.0,
            ocr_confidence=0.0, parser_confidence=0.0, column_mapping_confidence=0.0,
            candidate_accept_rate=0.0, candidate_status="", candidate_reasons=[],
            normalized_name="", original_name="Test Name",
            cmcc_match=True, cmcc_match_type="exact", cmcc_variant="test", cmcc_score=0.95,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=0.95,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        d = t.to_dict()
        assert d["original_name"] == "Test Name"
        assert d["cmcc_match"] is True
        assert d["decision_code"] == "D001"

    def test_explanation_unknown(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="edge_cases",
            layout_confidence=0.0, ocr_confidence=0.0, parser_confidence=0.0,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="rejected", candidate_reasons=[],
            normalized_name="unknown", original_name="Unknown Name",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        exp = t.explanation
        assert "Unknown Name" in exp
        assert "REJECT" in exp
        assert "No Match" in exp
        assert "D201" in exp

    def test_explanation_classified(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[],
            normalized_name="caja bancos", original_name="Caja Bancos",
            cmcc_match=True, cmcc_match_type="exact", cmcc_variant="caja", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=1.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        exp = t.explanation
        assert "Caja Bancos" in exp
        assert "ACCEPT" in exp
        assert "CMCC" in exp
        assert "AC.01" in exp
        assert "D001" in exp

    def test_explanation_shadow(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="edge_cases",
            layout_confidence=0.0, ocr_confidence=0.0, parser_confidence=0.0,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="rejected", candidate_reasons=[],
            normalized_name="test", original_name="Test",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="ER.10", shadow_confidence=0.95,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        exp = t.explanation
        assert "Shadow CMCC" in exp
        assert "ER.10" in exp

    def test_summary_line_classified(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="l", layout_confidence=0.0,
            ocr_confidence=0.0, parser_confidence=0.0, column_mapping_confidence=0.0,
            candidate_accept_rate=0.0, candidate_status="", candidate_reasons=[],
            normalized_name="", original_name="Banco Estado",
            cmcc_match=True, cmcc_match_type="exact", cmcc_variant="banco", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=0.98,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        s = t.summary_line()
        assert "D001" in s
        assert "AC.01" in s
        assert "0.98" in s

    def test_summary_line_unknown(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="l", layout_confidence=0.0,
            ocr_confidence=0.0, parser_confidence=0.0, column_mapping_confidence=0.0,
            candidate_accept_rate=0.0, candidate_status="", candidate_reasons=[],
            normalized_name="", original_name="Unknown Item",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        s = t.summary_line()
        assert "UNKNOWN" in s
        assert "Unknown Item" in s


class TestTraceBuilder:
    def make_audit(self, tmp_path: Path, accounts: list[dict]) -> Path:
        ap = tmp_path / "audit.json"
        data = {"accounts": accounts, "files": [], "total_elapsed": 0, "generated_at": ""}
        with open(ap, "w") as f:
            json.dump(data, f)
        return ap

    def test_build_all_empty(self, tmp_path):
        ap = self.make_audit(tmp_path, [])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 0

    def test_build_all_unknown(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Test Account", "method": "unclassified",
             "reason": "Sin coincidencia en código ni diccionario",
             "final_code": None, "confidence": 0, "source_file": "file.pdf",
             "source_group": "validacion", "nature": "profit",
             "standard_code": None, "special_rule": None, "account_code": "001"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.official_classification == "UNKNOWN"
        assert t.decision_code == DecisionCode.D201.value

    def test_build_all_exact_match(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Proveedores", "method": "learning_exact",
             "reason": "Gold Standard (exact) → PC.01 (matched: PROVEEDORES)",
             "final_code": "PC.01", "confidence": 0.98, "source_file": "file.pdf",
             "source_group": "validacion", "nature": "profit",
             "standard_code": "PC.01", "special_rule": None, "account_code": "002"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.official_classification == "PC.01"
        assert t.decision_code == DecisionCode.D001.value
        assert t.cmcc_match is True

    def test_build_all_dictionary_match(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Remuneraciones", "method": "dictionary_exact",
             "reason": "Coincidencia exacta con diccionario → ER.04",
             "final_code": "ER.04", "confidence": 0.95, "source_file": "file.xlsx",
             "source_group": "validacion", "nature": "profit",
             "standard_code": "ER.04", "special_rule": None, "account_code": "003"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.dictionary_match is True
        assert t.decision_code == DecisionCode.D002.value

    def test_build_all_shadow_match(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Impuesto Renta", "method": "unclassified",
             "reason": "Sin coincidencia en código ni diccionario",
             "final_code": None, "confidence": 0, "source_file": "file.pdf",
             "source_group": "edge_cases", "nature": "profit",
             "standard_code": None, "special_rule": None, "account_code": "004"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame([
            {"Cuenta": "Impuesto Renta", "Código sugerido": "ER.10", "Concepto": "Impuesto a la Renta",
             "Score": 1, "Método": "cmcc_variante", "Variante utilizada": "impuesto",
             "Evidencia": "matched", "Empresa": "X", "Documento": "doc"},
        ]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.shadow_classification == "ER.10"
        assert t.shadow_confidence == 1.0

    def test_build_all_multiple(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Caja", "method": "learning_exact",
             "reason": "Gold Standard (exact) → AC.01 (matched: Caja)",
             "final_code": "AC.01", "confidence": 0.99, "source_file": "f1.pdf",
             "source_group": "validacion", "nature": "profit",
             "standard_code": "AC.01", "special_rule": None, "account_code": "005"},
            {"account_name": "Unknown", "method": "unclassified",
             "reason": "Sin coincidencia en código ni diccionario",
             "final_code": None, "confidence": 0, "source_file": "f2.pdf",
             "source_group": "edge_cases", "nature": "profit",
             "standard_code": None, "special_rule": None, "account_code": "006"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 2
        assert traces[0].official_classification == "AC.01"
        assert traces[1].official_classification == "UNKNOWN"

    def test_normalize_name(self):
        assert TraceBuilder._normalize_name("Banco Estado  ") == "banco estado"
        assert TraceBuilder._normalize_name("") == ""
        assert TraceBuilder._normalize_name("  CAJA  ") == "caja"

    def test_extract_company(self):
        assert TraceBuilder._extract_company("path/to/Balance 2015 - Company ABC.pdf") == "Balance"
        assert TraceBuilder._extract_company("") == ""

    def test_safe_float(self):
        assert TraceBuilder._safe_float(5) == 5.0
        assert TraceBuilder._safe_float(None) == 0.0
        assert TraceBuilder._safe_float("abc") == 0.0


class TestTraceReport:
    def make_traces(self) -> list:
        t1 = DecisionTrace(
            document_id="doc1::001", company="A", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[],
            normalized_name="a", original_name="A",
            cmcc_match=True, cmcc_match_type="exact", cmcc_variant="a", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=0.95,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        t2 = DecisionTrace(
            document_id="doc2::002", company="B", layout="edge_cases",
            layout_confidence=0.0, ocr_confidence=0.0, parser_confidence=0.0,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="rejected", candidate_reasons=[],
            normalized_name="b", original_name="B",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        return [t1, t2]

    def test_total(self):
        r = TraceReport(self.make_traces())
        assert r.total == 2

    def test_total_classified(self):
        r = TraceReport(self.make_traces())
        assert r.total_classified == 1

    def test_total_unknown(self):
        r = TraceReport(self.make_traces())
        assert r.total_unknown == 1

    def test_distribution_by(self):
        r = TraceReport(self.make_traces())
        d = r.distribution_by("decision_code")
        assert d["D001"] == 1
        assert d["D201"] == 1

    def test_top_unknown(self):
        r = TraceReport(self.make_traces())
        assert len(r.top_unknown()) == 1

    def test_top_classified(self):
        r = TraceReport(self.make_traces())
        assert len(r.top_classified()) == 1

    def test_top_documents(self):
        r = TraceReport(self.make_traces())
        docs = r.top_documents(5)
        assert len(docs) == 2

    def test_top_concepts(self):
        r = TraceReport(self.make_traces())
        concepts = r.top_concepts(5)
        assert len(concepts) >= 1

    def test_decision_code_stats(self):
        r = TraceReport(self.make_traces())
        stats = r.decision_code_stats()
        assert len(stats) == 2
        assert stats[0]["percentage"] == 50.0

    def test_layout_stats(self):
        r = TraceReport(self.make_traces())
        stats = r.layout_stats()
        assert len(stats) == 2

    def test_match_type_stats(self):
        r = TraceReport(self.make_traces())
        stats = r.match_type_stats()
        assert len(stats) >= 2

    def test_parser_status_stats(self):
        r = TraceReport(self.make_traces())
        stats = r.parser_status_stats()
        assert len(stats) == 2

    def test_to_dict(self):
        r = TraceReport(self.make_traces())
        d = r.to_dict()
        assert d["total_accounts"] == 2
        assert d["total_classified"] == 1
        assert d["total_unknown"] == 1


class TestTraceExporter:
    def make_traces(self) -> list:
        t1 = DecisionTrace(
            document_id="doc1::001", company="A", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[],
            normalized_name="caja", original_name="Caja",
            cmcc_match=True, cmcc_match_type="exact", cmcc_variant="caja", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=0.95,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        t2 = DecisionTrace(
            document_id="doc2::002", company="B", layout="edge_cases",
            layout_confidence=0.0, ocr_confidence=0.0, parser_confidence=0.0,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="rejected", candidate_reasons=[],
            normalized_name="unknown", original_name="Unknown",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        return [t1, t2]

    def test_to_dataframe(self):
        traces = self.make_traces()
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        df = e.to_dataframe()
        assert len(df) == 2
        assert "decision_code" in df.columns
        assert "original_name" in df.columns

    def test_export_excel(self, tmp_path):
        traces = self.make_traces()
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        p = e.export_excel(tmp_path / "test.xlsx")
        assert p.exists()
        df = pd.read_excel(p)
        assert len(df) == 2

    def test_export_json(self, tmp_path):
        traces = self.make_traces()
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        p = e.export_json(tmp_path / "test.json")
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert "summary" in data
        assert "traces" in data
        assert len(data["traces"]) == 2

    def test_export_markdown(self, tmp_path):
        traces = self.make_traces()
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        p = e.export_markdown(tmp_path / "test.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Decision Trace Report" in text
        assert "D001" in text
        assert "D201" in text
        assert "Sample UNKNOWN" in text
        assert "Sample Classified" in text

    def test_export_technical_debt(self, tmp_path):
        # 3 traces: 2 UNKNOWN + 1 classified = 66.7% unknown → triggers UNKNOWN flag
        traces = self.make_traces()
        t3 = DecisionTrace(
            document_id="doc3::003", company="C", layout="edge_cases",
            layout_confidence=0.0, ocr_confidence=0.0, parser_confidence=0.0,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="rejected", candidate_reasons=[],
            normalized_name="z", original_name="Z",
            cmcc_match=False, cmcc_match_type="", cmcc_variant="", cmcc_score=0.0,
            dictionary_match=False, dictionary_source="",
            official_classification="UNKNOWN", official_confidence=0.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D201", decision_description="Unknown Variant",
            timestamp="ts",
        )
        traces.append(t3)
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        p = e.export_technical_debt(tmp_path / "debt.md")
        assert p.exists()
        text = p.read_text(encoding="utf-8")
        assert "Technical Debt Report" in text
        assert "CRITICAL" in text

    def test_export_all_formats(self, tmp_path):
        traces = self.make_traces()
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        e.export_excel(tmp_path / "trace.xlsx")
        e.export_json(tmp_path / "trace.json")
        e.export_markdown(tmp_path / "trace.md")
        e.export_technical_debt(tmp_path / "debt.md")
        assert (tmp_path / "trace.xlsx").exists()
        assert (tmp_path / "trace.json").exists()
        assert (tmp_path / "trace.md").exists()
        assert (tmp_path / "debt.md").exists()

    def test_large_trace_export(self, tmp_path):
        traces = []
        for i in range(100):
            traces.append(DecisionTrace(
                document_id=f"doc{i}::acc{i}", company="C", layout="validacion",
                layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
                column_mapping_confidence=0.0, candidate_accept_rate=0.0,
                candidate_status="accepted", candidate_reasons=[],
                normalized_name=f"name{i}", original_name=f"Name{i}",
                cmcc_match=True, cmcc_match_type="exact", cmcc_variant=f"v{i}", cmcc_score=0.95,
                dictionary_match=False, dictionary_source="",
                official_classification="ER.10", official_confidence=0.95,
                shadow_classification="", shadow_confidence=0.0,
                decision_code="D001", decision_description="Exact Variant",
                timestamp="ts",
            ))
        r = TraceReport(traces)
        e = TraceExporter(traces, r)
        p = e.export_excel(tmp_path / "large.xlsx")
        assert p.exists()
        assert p.stat().st_size > 0


class TestTraceBuilderIntegration:
    def make_audit(self, tmp_path: Path, accounts: list[dict]) -> Path:
        ap = tmp_path / "audit.json"
        with open(ap, "w") as f:
            json.dump({"accounts": accounts, "files": [
                {"source_file": "file.pdf", "file_type": "pdf"},
            ]}, f)
        return ap

    def test_fuzzy_match(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Gastos Admin", "method": "learning_fuzzy",
             "reason": "Gold Standard (fuzzy) → ER.04 (matched: Gastos)",
             "final_code": "ER.04", "confidence": 0.8655, "source_file": "file.pdf",
             "source_group": "validacion", "nature": "profit",
             "standard_code": "ER.04", "special_rule": None, "account_code": "007"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert traces[0].decision_code == "Fuzzy Match"
        assert traces[0].cmcc_match_type == "fuzzy"

    def test_manual_rule(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Test Rule", "method": "code",
             "reason": "Aplicación de regla manual → PC.01",
             "final_code": "PC.01", "confidence": 1.0, "source_file": "file.pdf",
             "source_group": "validacion", "nature": "profit",
             "standard_code": "PC.01", "special_rule": "rule_001",
             "account_code": "008"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert traces[0].decision_code == "Manual Rule"

    def test_document_id_format(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {"account_name": "Test", "method": "unclassified",
             "reason": "No match", "final_code": None, "confidence": 0,
             "source_file": "mi_archivo.pdf", "source_group": "edge_cases",
             "nature": "profit", "standard_code": None, "special_rule": None,
             "account_code": "ACC001"},
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert "mi_archivo.pdf::ACC001" in traces[0].document_id


class TestRunner:
    def test_import(self):
        from scripts import run_decision_trace
        assert hasattr(run_decision_trace, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_decision_trace")
        assert mod is not None
