from __future__ import annotations

from pathlib import Path

import pytest

from document_context import DocumentContext
from document_context.models import (
    DocumentMetadata,
    ProcessingState,
    StructureData,
    ParserData,
)

from adapters import (
    DIEAdapter,
    KBAdapter,
    ParserAdapter,
    ReviewAdapter,
    SIEAdapter,
    ValidationAdapter,
)
from adapters.sie_adapter import SIEAdapter as SIEAdapterCls
from orchestrator.pipeline_v2 import HomologationPipelineV2


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


def _make_real_pdf() -> Path | None:
    pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))
    return pdfs[0] if pdfs else None


# =========================================================================
# SIEAdapter Tests
# =========================================================================

class TestSIEAdapter:
    def test_sie_run_sets_metadata(self):
        ctx = DocumentContext(source_file="empresa_2023_balance.pdf")
        ctx = SIEAdapterCls.run(ctx)
        assert ctx.metadata is not None
        assert ctx.metadata.company == "empresa"
        assert ctx.metadata.year == 2023

    def test_sie_run_sets_structure(self):
        ctx = DocumentContext(source_file="balance_8_columnas_2023.pdf")
        ctx = SIEAdapterCls.run(ctx)
        assert ctx.structure is not None
        assert ctx.structure.column_layout == "8_columnas"

    def test_sie_run_state_transition(self):
        ctx = DocumentContext(source_file="test.pdf")
        assert ctx.state == ProcessingState.NEW
        ctx = SIEAdapterCls.run(ctx)
        assert ctx.state == ProcessingState.STRUCTURED

    def test_sie_infer_company_standard(self):
        assert SIEAdapterCls._infer_company("empresa_2023.pdf") == "empresa"

    def test_sie_infer_company_with_prefix(self):
        assert SIEAdapterCls._infer_company("001_empresa_2023.pdf") == "empresa"

    def test_sie_infer_company_unknown(self):
        assert SIEAdapterCls._infer_company("document.pdf") == "document"

    def test_sie_infer_year_found(self):
        assert SIEAdapterCls._infer_year("balance_2023.pdf") == 2023

    def test_sie_infer_year_missing(self):
        assert SIEAdapterCls._infer_year("balance.pdf") == 0

    def test_sie_infer_layout_8columnas(self):
        assert SIEAdapterCls._infer_layout("balance_8_columnas_2023.pdf") == "8_columnas"

    def test_sie_infer_layout_tributario(self):
        assert SIEAdapterCls._infer_layout("tributario_2023.pdf") == "tributario"

    def test_sie_infer_layout_excel(self):
        assert SIEAdapterCls._infer_layout("balances.xlsx") == "excel"

    def test_sie_infer_layout_default(self):
        assert SIEAdapterCls._infer_layout("normal.pdf") == "pdf_estandar"

    def test_sie_run_twice_fails_write_once(self):
        ctx = SIEAdapterCls.run(DocumentContext(source_file="test.pdf"))
        with pytest.raises(Exception):
            SIEAdapterCls.run(ctx)

    def test_sie_snapshots_created(self):
        ctx = SIEAdapterCls.run(DocumentContext(source_file="test.pdf"))
        assert len(ctx.snapshots) >= 2

    def test_sie_events_recorded(self):
        ctx = SIEAdapterCls.run(DocumentContext(source_file="test.pdf"))
        assert len(ctx.events) >= 2


# =========================================================================
# DIEAdapter Tests
# =========================================================================

class TestDIEAdapter:
    def test_die_init(self):
        adapter = DIEAdapter()
        assert adapter._engine is not None

    def test_die_run_missing_file(self, tmp_path):
        ctx = DocumentContext(source_file=str(tmp_path / "nonexistent.pdf"))
        adapter = DIEAdapter()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("die_error") is not None

    def test_die_run_sets_prediction(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = DocumentContext(source_file=str(pdf))
        adapter = DIEAdapter()
        ctx = adapter.run(ctx)
        assert ctx.prediction is not None

    def test_die_run_sets_custom_report(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = DocumentContext(source_file=str(pdf))
        adapter = DIEAdapter()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("die_report") is not None


# =========================================================================
# ParserAdapter Tests
# =========================================================================

class TestParserAdapter:
    def test_parser_init(self):
        adapter = ParserAdapter()
        assert adapter._parser is not None

    def test_parser_run_missing_file(self, tmp_path):
        ctx = DocumentContext(source_file=str(tmp_path / "nonexistent.pdf"))
        adapter = ParserAdapter()
        ctx = adapter.run(ctx)
        assert ctx.get_custom("parser_error") is not None

    def test_parser_run_sets_parser_data(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        assert ctx.parser is not None

    def test_parser_selected_parser(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        assert ctx.parser is not None

    def test_parser_raw_accounts_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        assert isinstance(ctx.parser.raw_accounts, list)

    def test_parser_state_transition(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        assert ctx.state == ProcessingState.PARSED

    def test_parser_custom_resultado(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        assert ctx.get_custom("parser_resultado") is not None

    def test_parser_pdf_parse_error(self, tmp_path):
        from unittest.mock import patch
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        adapter = ParserAdapter()
        with patch.object(adapter._parser, "parsear", side_effect=ValueError("mock parse error")):
            ctx = adapter.run(ctx)
            assert ctx.get_custom("parser_error") is not None
            assert "mock parse error" in ctx.get_custom("parser_error")

    def test_parser_xlsx_handling(self, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_text("not a real xlsx")
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(xlsx)))
        ctx = ParserAdapter().run(ctx)
        assert ctx.get_custom("parser_error") is not None


# =========================================================================
# KBAdapter Tests
# =========================================================================

class TestKBAdapter:
    def test_kb_init(self):
        adapter = KBAdapter()
        assert adapter._pipeline is not None

    def test_kb_run_sets_knowledge(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert ctx.knowledge is not None

    def test_knowledge_has_fields(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        k = ctx.knowledge
        assert hasattr(k, "cmcc_matches")
        assert hasattr(k, "learning_hits")
        assert hasattr(k, "dictionary_matches")

    def test_kb_state_transition(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert ctx.state == ProcessingState.CLASSIFIED

    def test_kb_stores_classified_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert isinstance(ctx.get_custom("classified"), list)

    def test_kb_stores_ignored_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert isinstance(ctx.get_custom("ignored"), list)

    def test_kb_extract_v1_summary_from_custom(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        summary = KBAdapter.extract_v1_summary(ctx)
        assert "source_file" in summary
        assert "accounts_total" in summary

    def test_kb_extract_v1_summary_empty(self):
        ctx = DocumentContext(source_file="nonexistent.pdf")
        summary = KBAdapter.extract_v1_summary(ctx)
        assert "source_file" in summary

    def test_kb_missing_file(self, tmp_path):
        ctx = DocumentContext(source_file=str(tmp_path / "nonexistent.pdf"))
        ctx = KBAdapter().run(ctx)
        assert ctx.get_custom("kb_error") is not None

    def test_kb_snapshots_after_run(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert len(ctx.snapshots) >= 3


# =========================================================================
# ValidationAdapter Tests
# =========================================================================

class TestValidationAdapter:
    def test_validation_init(self):
        adapter = ValidationAdapter()
        assert adapter._validator is not None

    def test_validation_run_sets_validation_data(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        assert ctx.validation is not None

    def test_validation_state_transition(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        assert ctx.state == ProcessingState.VALIDATED

    def test_validation_has_warnings_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        assert hasattr(ctx.validation, "warnings")

    def test_validation_custom_result(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        assert ctx.get_custom("validation_result") is not None


# =========================================================================
# ReviewAdapter Tests
# =========================================================================

class TestReviewAdapter:
    def test_review_run_marks_reviewed(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        ctx = ReviewAdapter().run(ctx)
        assert ctx.state == ProcessingState.REVIEWED

    def test_review_sets_execution(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        ctx = ReviewAdapter().run(ctx)
        assert ctx.execution is not None

    def test_review_queue_exists(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        ctx = ReviewAdapter().run(ctx)
        assert isinstance(ctx.get_custom("review_queue"), list)

    def test_review_count(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        ctx = ReviewAdapter().run(ctx)
        assert isinstance(ctx.get_custom("review_count"), int)


# =========================================================================
# HomologationPipelineV2 Tests
# =========================================================================

class TestHomologationPipelineV2:
    def test_pipeline_init(self):
        pipe = HomologationPipelineV2()
        assert pipe._adapter_sie is not None
        assert pipe._adapter_die is not None
        assert pipe._adapter_parser is not None
        assert pipe._adapter_kb is not None
        assert pipe._adapter_validation is not None
        assert pipe._adapter_review is not None

    def test_pipeline_process_returns_context(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert isinstance(ctx, DocumentContext)

    def test_pipeline_process_has_all_sections(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert ctx.metadata is not None
        assert ctx.structure is not None
        assert ctx.execution is not None

    def test_pipeline_process_has_snapshots(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert len(ctx.snapshots) >= 7

    def test_pipeline_process_has_events(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert len(ctx.events) >= 7

    def test_pipeline_process_to_dict(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        d = pipe.process_to_dict(str(pdf))
        assert isinstance(d, dict)
        assert "dce_state" in d

    def test_pipeline_to_dict_has_elapsed(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        d = pipe.process_to_dict(str(pdf))
        assert "elapsed_seconds_v2" in d

    def test_pipeline_lifecycle_order(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        states = [e.to_state for e in ctx.events if e.to_state != ProcessingState.NEW]
        expected_order = [
            ProcessingState.IDENTIFIED,
            ProcessingState.STRUCTURED,
            ProcessingState.REVIEWED,
            ProcessingState.COMPLETED,
        ]
        for exp in expected_order:
            assert exp in states, f"Missing state {exp} in lifecycle"

    def test_pipeline_identity_has_sha256(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert ctx.sha256 != ""

    def test_pipeline_version_present(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert ctx.version != ""


# =========================================================================
# Full Pipeline Integration Tests
# =========================================================================

class TestFullPipeline:
    def test_full_pipeline_with_real_pdf(self):
        pdf = _make_real_pdf()
        if pdf is None:
            pytest.skip("No HOLDOUT PDFs available")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert ctx.state == ProcessingState.COMPLETED
        assert ctx.metadata is not None

    def test_full_pipeline_multiple_real_pdfs(self):
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:3]
        if len(pdfs) < 1:
            pytest.skip("Not enough HOLDOUT PDFs")
        pipe = HomologationPipelineV2()
        for p in pdfs:
            ctx = pipe.process(str(p))
            assert ctx.state == ProcessingState.COMPLETED

    def test_full_pipeline_matches_v1_classified_count(self):
        pdf = _make_real_pdf()
        if pdf is None:
            pytest.skip("No HOLDOUT PDFs available")

        from pipeline.homologation_pipeline import HomologationPipeline
        v1_result = HomologationPipeline().process(str(pdf))

        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        classified_v2 = ctx.get_custom("classified", [])

        v1_count = v1_result.get("accounts_classified", 0)
        assert len(classified_v2) == v1_count, (
            f"V1={v1_count} vs V2={len(classified_v2)} for {pdf.name}"
        )

    def test_full_pipeline_matches_v1_ignored_count(self):
        pdf = _make_real_pdf()
        if pdf is None:
            pytest.skip("No HOLDOUT PDFs available")

        from pipeline.homologation_pipeline import HomologationPipeline
        v1_result = HomologationPipeline().process(str(pdf))

        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        ignored_v2 = ctx.get_custom("ignored", [])

        v1_count = v1_result.get("accounts_ignored", 0)
        assert len(ignored_v2) == v1_count

    def test_full_pipeline_matches_v1_total(self):
        pdf = _make_real_pdf()
        if pdf is None:
            pytest.skip("No HOLDOUT PDFs available")

        from pipeline.homologation_pipeline import HomologationPipeline
        v1_result = HomologationPipeline().process(str(pdf))

        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        summary = KBAdapter.extract_v1_summary(ctx)

        assert summary.get("accounts_total") == v1_result.get("accounts_total")
        assert summary.get("accounts_classified") == v1_result.get("accounts_classified")
        assert summary.get("accounts_ignored") == v1_result.get("accounts_ignored")


# =========================================================================
# Edge Cases
# =========================================================================

class TestEdgeCases:
    def test_context_validates_ok(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        issues = ctx.validate()
        assert isinstance(issues, list)

    def test_context_serialization_roundtrip(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))

        from document_context.serializers import DocumentContextSerializer
        data = DocumentContextSerializer.to_dict(ctx)
        restored = DocumentContextSerializer.from_dict(data)
        assert restored.state == ctx.state
        assert restored.document_id == ctx.document_id

    def test_context_json_roundtrip(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))

        from document_context.serializers import DocumentContextSerializer
        js = DocumentContextSerializer.to_json(ctx)
        restored = DocumentContextSerializer.from_json(js)
        assert restored.state == ctx.state

    def test_context_snapshot_diff(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))

        snaps = ctx.snapshots
        if len(snaps) >= 2:
            diff = ctx.diff_snapshots(snaps[0].snapshot_id, snaps[-1].snapshot_id)
            assert isinstance(diff, dict)

    def test_custom_data_isolation(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        ctx.set_custom("test_key", "test_value")
        assert ctx.get_custom("test_key") == "test_value"

    def test_pipeline_with_special_chars(self, tmp_path):
        pdf = _make_pdf(tmp_path, "empresa_nunez_2023.pdf")
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        assert ctx.state == ProcessingState.COMPLETED

    def test_pipeline_can_run_multiple_times(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx1 = pipe.process(str(pdf))
        ctx2 = pipe.process(str(pdf))
        assert ctx1.document_id != ctx2.document_id

    def test_all_sections_write_once_enforced(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        with pytest.raises(Exception):
            ctx.set_metadata(DocumentMetadata(), module="test")

    def test_pipeline_to_dict_includes_classified(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        d = pipe.process_to_dict(str(pdf))
        assert "classified" in d
        assert isinstance(d["classified"], list)

    def test_pipeline_all_events_have_timestamps(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = HomologationPipelineV2().process(str(pdf))
        for ev in ctx.events:
            assert ev.timestamp is not None

    def test_pipeline_snapshots_have_ids(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = HomologationPipelineV2().process(str(pdf))
        for s in ctx.snapshots:
            assert s.snapshot_id != ""

    def test_sie_layout_consolidado(self):
        assert SIEAdapterCls._infer_layout("consolidado_2023.pdf") == "consolidado"

    def test_sie_layout_pre_balance(self):
        assert SIEAdapterCls._infer_layout("pre_balance_2023.pdf") == "pre_balance"

    def test_pipeline_process_many_times(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        for _ in range(3):
            ctx = pipe.process(str(pdf))
            assert ctx.state == ProcessingState.COMPLETED

    def test_kb_learning_hits_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert isinstance(ctx.knowledge.learning_hits, list)

    def test_kb_dictionary_matches_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        assert isinstance(ctx.knowledge.dictionary_matches, list)

    def test_validation_errors_list(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        ctx = SIEAdapterCls.run(DocumentContext(source_file=str(pdf)))
        ctx = ParserAdapter().run(ctx)
        ctx = KBAdapter().run(ctx)
        ctx = ValidationAdapter().run(ctx)
        assert isinstance(ctx.validation.errors, list)

    def test_pipeline_to_dict_no_elapsed_on_fresh(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        d = pipe.process_to_dict(str(pdf))
        assert d.get("elapsed_seconds_v2", 0) >= 0

    def test_pipeline_idempotent_calls(self, tmp_path):
        pdf = _make_pdf(tmp_path)
        pipe = HomologationPipelineV2()
        ctx = pipe.process(str(pdf))
        ctx2 = pipe.process(str(pdf))
        assert ctx2.state == ProcessingState.COMPLETED


# =========================================================================
# Integration Comparison Tests
# =========================================================================

class TestIntegrationCompare:
    def test_comparator_init(self):
        from integration.compare_v1_v2 import PipelineComparator
        pc = PipelineComparator()
        assert pc._v1 is not None
        assert pc._v2 is not None

    def test_comparator_compare_real_pdf(self):
        from integration.compare_v1_v2 import PipelineComparator
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pc = PipelineComparator()
        diff = pc.compare_file(str(pdfs[0]))
        assert isinstance(diff, dict)

    def test_comparator_no_diffs_on_holdout(self):
        from integration.compare_v1_v2 import PipelineComparator
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))[:2]
        if len(pdfs) < 2:
            pytest.skip("Need at least 2 HOLDOUT files")
        pc = PipelineComparator()
        for pdf in pdfs:
            pc.compare_file(str(pdf))
        assert not pc.has_diffs()

    def test_comparator_diff_summary(self):
        from integration.compare_v1_v2 import PipelineComparator
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pc = PipelineComparator()
        pc.compare_file(str(pdfs[0]))
        summary = pc.diff_summary()
        assert isinstance(summary, list)

    def test_comparator_generate_report(self, tmp_path):
        from integration.compare_v1_v2 import PipelineComparator
        pdfs = sorted(Path("datasets/HOLDOUT").glob("*.pdf"))
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        pc = PipelineComparator()
        pc.compare_file(str(pdfs[0]))
        out = tmp_path / "comparison.json"
        pc.generate_report(str(out))
        assert out.exists()

    def test_comparator_compare_classified_entry(self):
        from integration.compare_v1_v2 import PipelineComparator
        pc = PipelineComparator()
        c1 = {"standard_code": "AC.01", "final_code": "AC.01", "confidence": 0.95, "method": "code"}
        c2 = {"standard_code": "AC.01", "final_code": "AC.01", "confidence": 0.95, "method": "code"}
        diff = pc._compare_classified_entry(c1, c2)
        assert diff == {}

    def test_comparator_compare_classified_entry_diff(self):
        from integration.compare_v1_v2 import PipelineComparator
        pc = PipelineComparator()
        c1 = {"standard_code": "AC.01", "final_code": "AC.01", "confidence": 0.95, "method": "code"}
        c2 = {"standard_code": "AC.02", "final_code": "AC.02", "confidence": 0.80, "method": "dictionary"}
        diff = pc._compare_classified_entry(c1, c2)
        assert "standard_code" in diff
        assert "confidence" in diff
        assert "method" in diff
