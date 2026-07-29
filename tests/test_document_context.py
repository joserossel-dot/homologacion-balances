from __future__ import annotations

import sys, os, json, tempfile, pickle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone

from document_context import (
    DocumentContext, DocumentContextSerializer, ContextMerger,
    ContextValidator, ContextStatistics, WriteOnceError, LifecycleError,
)
from document_context.models import (
    DocumentIdentity, DocumentMetadata, StructureData, ParserData,
    KnowledgeData, ValidationData, PredictionData, ExecutionData,
    ProcessingState, ContextSnapshot, LifecycleEvent,
)
from document_context.lifecycle import LifecycleManager
from document_context.snapshot import SnapshotManager, SnapshotNotFoundError
from document_context.validators import ValidationIssue


# =============================================================================
# MODELS TESTS
# =============================================================================

class TestModels:
    def test_processing_state_order(self):
        assert ProcessingState.NEW.index == 0
        assert ProcessingState.IDENTIFIED.index > ProcessingState.NEW.index
        assert ProcessingState.COMPLETED.index == 7
        assert ProcessingState.FAILED.index == 8

    def test_processing_state_terminal(self):
        assert ProcessingState.COMPLETED.is_terminal
        assert ProcessingState.FAILED.is_terminal
        assert not ProcessingState.NEW.is_terminal
        assert not ProcessingState.PARSED.is_terminal

    def test_document_identity_to_dict(self):
        ident = DocumentIdentity(document_id="ctx_abc", source_file="test.pdf", sha256="abc123")
        d = ident.to_dict()
        assert d["document_id"] == "ctx_abc"
        assert d["source_file"] == "test.pdf"
        assert d["sha256"] == "abc123"

    def test_document_identity_roundtrip(self):
        ident = DocumentIdentity(document_id="ctx_xyz", source_file="doc.pdf", version="2.0")
        d = ident.to_dict()
        ident2 = DocumentIdentity.from_dict(d)
        assert ident2.document_id == "ctx_xyz"
        assert ident2.source_file == "doc.pdf"
        assert ident2.version == "2.0"

    def test_metadata_to_dict(self):
        meta = DocumentMetadata(company="ACME", rut="76.693.319-K", year=2024, pages=5)
        d = meta.to_dict()
        assert d["company"] == "ACME"
        assert d["rut"] == "76.693.319-K"

    def test_metadata_roundtrip(self):
        meta = DocumentMetadata(company="ACME", rut="76.693.319-K", year=2024, ocr_probability=0.15)
        meta2 = DocumentMetadata.from_dict(meta.to_dict())
        assert meta2.company == "ACME"
        assert meta2.ocr_probability == 0.15

    def test_structure_data_accounts(self):
        s = StructureData(family="TRIBUTARIO", template="T14", document_type="BALANCE")
        d = s.to_dict()
        assert d["family"] == "TRIBUTARIO"

    def test_parser_data_counts(self):
        p = ParserData(selected_parser="Universal", accounts=["a", "b", "c"])
        assert p.total_accounts == 3
        assert p.total_raw == 0
        assert p.total_ignored == 0

    def test_knowledge_data_counts(self):
        k = KnowledgeData(cmcc_matches=["m1", "m2"], dictionary_matches=["d1"])
        assert k.total_matches == 3

    def test_knowledge_data_to_dict(self):
        k = KnowledgeData(cmcc_matches=["a"], learning_hits=["b"], variants=["c"])
        d = k.to_dict()
        assert d["cmcc_matches"] == 1
        assert d["total_matches"] == 2

    def test_validation_data_errors(self):
        v = ValidationData(errors=["e1"], warnings=["w1"])
        assert v.has_errors
        assert v.has_warnings

    def test_validation_data_no_errors(self):
        v = ValidationData()
        assert not v.has_errors
        assert not v.has_warnings

    def test_prediction_data_to_dict(self):
        p = PredictionData(confidence_expected=0.85, coverage_expected=0.75, estimated_time=6.2)
        d = p.to_dict()
        assert d["confidence_expected"] == 0.85

    def test_execution_data_to_dict(self):
        e = ExecutionData(confidence_real=0.9, processing_time=5.0, status="ok")
        d = e.to_dict()
        assert d["confidence_real"] == 0.9

    def test_context_snapshot_to_dict(self):
        snap = ContextSnapshot(
            snapshot_id="s1", label="test", state=ProcessingState.PARSED,
            timestamp=datetime.now(timezone.utc), data={"a": 1},
        )
        d = snap.to_dict()
        assert d["snapshot_id"] == "s1"
        assert d["state"] == "PARSED"

    def test_lifecycle_event_to_dict(self):
        evt = LifecycleEvent(
            event_id="e1", timestamp=datetime.now(timezone.utc),
            from_state=ProcessingState.NEW, to_state=ProcessingState.IDENTIFIED,
            module="test", description="test event", snapshot_id="s1",
        )
        d = evt.to_dict()
        assert d["event_id"] == "e1"
        assert d["from_state"] == "NEW"
        assert d["to_state"] == "IDENTIFIED"


# =============================================================================
# DOCUMENT CONTEXT CREATION TESTS
# =============================================================================

class TestDocumentContextCreation:
    def test_create_default(self):
        ctx = DocumentContext()
        assert ctx.document_id.startswith("ctx_")
        assert ctx.state == ProcessingState.NEW
        assert ctx.can_process
        assert not ctx.is_terminal
        assert ctx.version == "1.0.0"

    def test_create_with_source(self):
        ctx = DocumentContext(source_file="balance.pdf")
        assert ctx.source_file == "balance.pdf"

    def test_create_with_id(self):
        ctx = DocumentContext(document_id="custom_id")
        assert ctx.document_id == "custom_id"

    def test_initial_sections_none(self):
        ctx = DocumentContext()
        assert ctx.metadata is None
        assert ctx.structure is None
        assert ctx.parser is None
        assert ctx.knowledge is None
        assert ctx.validation is None
        assert ctx.prediction is None
        assert ctx.execution is None

    def test_initial_snapshots_empty(self):
        ctx = DocumentContext()
        assert len(ctx.snapshots) == 0

    def test_initial_events_empty(self):
        ctx = DocumentContext()
        assert len(ctx.events) == 0


# =============================================================================
# WRITE-ONCE TESTS
# =============================================================================

class TestWriteOnce:
    def test_set_metadata(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        assert ctx.metadata.company == "ACME"
        assert ctx.state == ProcessingState.IDENTIFIED

    def test_set_metadata_twice_raises(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        with pytest.raises(WriteOnceError):
            ctx.set_metadata(DocumentMetadata(company="OTRA"))

    def test_set_structure(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        ctx.set_structure(StructureData(family="TRIBUTARIO"))
        assert ctx.structure.family == "TRIBUTARIO"
        assert ctx.state == ProcessingState.STRUCTURED

    def test_set_structure_twice_raises(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData(family="TRIBUTARIO"))
        with pytest.raises(WriteOnceError):
            ctx.set_structure(StructureData(family="OTRA"))

    def test_set_parser(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        ctx.set_parser(ParserData(selected_parser="Universal", accounts=["a"]))
        assert ctx.parser.selected_parser == "Universal"
        assert ctx.state == ProcessingState.PARSED

    def test_set_knowledge(self):
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData(cmcc_matches=["m1"]))
        assert ctx.knowledge.total_matches >= 1
        assert ctx.state == ProcessingState.CLASSIFIED

    def test_set_validation(self):
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        assert ctx.state == ProcessingState.VALIDATED

    def test_set_prediction_no_transition(self):
        ctx = DocumentContext()
        ctx.set_prediction(PredictionData(confidence_expected=0.85))
        assert ctx.prediction.confidence_expected == 0.85
        assert ctx.state == ProcessingState.NEW

    def test_set_execution_no_transition(self):
        ctx = DocumentContext()
        ctx.set_execution(ExecutionData(status="ok"))
        assert ctx.execution.status == "ok"

    def test_write_once_all_fields(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        ctx.set_parser(ParserData())
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        ctx.set_prediction(PredictionData())
        ctx.set_execution(ExecutionData())
        with pytest.raises(WriteOnceError):
            ctx.set_metadata(DocumentMetadata())


# =============================================================================
# LIFECYCLE STATE TRANSITION TESTS
# =============================================================================

class TestLifecycleTransitions:
    def test_full_lifecycle(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        assert ctx.state == ProcessingState.IDENTIFIED
        ctx.set_structure(StructureData())
        assert ctx.state == ProcessingState.STRUCTURED
        ctx.set_parser(ParserData())
        assert ctx.state == ProcessingState.PARSED
        ctx.set_knowledge(KnowledgeData())
        assert ctx.state == ProcessingState.CLASSIFIED
        ctx.set_validation(ValidationData())
        assert ctx.state == ProcessingState.VALIDATED
        ctx.mark_reviewed()
        assert ctx.state == ProcessingState.REVIEWED
        ctx.complete()
        assert ctx.state == ProcessingState.COMPLETED
        assert ctx.is_terminal

    def test_cannot_transition_from_terminal(self):
        ctx = DocumentContext()
        ctx.fail("error")
        assert ctx.state == ProcessingState.FAILED
        assert ctx.is_terminal
        with pytest.raises(LifecycleError):
            ctx.set_metadata(DocumentMetadata())

    def test_invalid_transition_skipping_state(self):
        ctx = DocumentContext()
        with pytest.raises(LifecycleError):
            ctx.set_structure(StructureData())

    def test_fail_from_any_state(self):
        ctx = DocumentContext()
        ctx.fail("error")
        assert ctx.state == ProcessingState.FAILED
        assert ctx.is_terminal

    def test_fail_after_transition(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.fail("metadata error")
        assert ctx.state == ProcessingState.FAILED

    def test_cannot_transition_from_failed(self):
        ctx = DocumentContext()
        ctx.fail("error")
        assert not ctx.can_process

    def test_lifecycle_events_count(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="A"))
        ctx.set_structure(StructureData(family="F"))
        ctx.set_parser(ParserData(selected_parser="P"))
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        assert len(ctx.events) == 5

    def test_mark_reviewed(self):
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        ctx.mark_reviewed()
        assert ctx.state == ProcessingState.REVIEWED

    def test_complete_requires_review(self):
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        ctx.mark_reviewed()
        ctx.complete()
        assert ctx.state == ProcessingState.COMPLETED


# =============================================================================
# CUSTOM DATA TESTS
# =============================================================================

class TestCustomData:
    def test_set_custom(self):
        ctx = DocumentContext()
        ctx.set_custom("key1", "value1")
        assert ctx.get_custom("key1") == "value1"

    def test_custom_default(self):
        ctx = DocumentContext()
        assert ctx.get_custom("nonexistent", "default") == "default"

    def test_custom_multiple(self):
        ctx = DocumentContext()
        ctx.set_custom("a", 1)
        ctx.set_custom("b", 2)
        assert ctx.custom_data == {"a": 1, "b": 2}

    def test_custom_overwrite(self):
        ctx = DocumentContext()
        ctx.set_custom("key", "first")
        ctx.set_custom("key", "second")
        assert ctx.get_custom("key") == "second"


# =============================================================================
# SNAPSHOT TESTS
# =============================================================================

class TestSnapshots:
    def test_create_snapshot(self):
        ctx = DocumentContext()
        snap = ctx.snapshot("initial")
        assert snap.label == "initial"
        assert snap.state == ProcessingState.NEW
        assert snap.snapshot_id.startswith("snap_")

    def test_multiple_snapshots(self):
        ctx = DocumentContext()
        s1 = ctx.snapshot("first")
        s2 = ctx.snapshot("second")
        assert len(ctx.snapshots) == 2
        assert ctx.snapshots[0].snapshot_id == s1.snapshot_id

    def test_snapshot_after_setting_data(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        snap = ctx.snapshot("after_metadata")
        data = snap.data
        assert data["metadata"]["company"] == "ACME"

    def test_snapshot_data_independence(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        snap = ctx.snapshot("after_metadata")
        ctx.set_structure(StructureData(family="T"))
        snap2 = ctx.snapshot("after_structure")
        assert snap.data["structure"] is None
        assert snap2.data["structure"] is not None

    def test_snapshot_manager_create(self):
        mgr = SnapshotManager()
        snap = mgr.create("test", ProcessingState.NEW, {"a": 1})
        assert mgr.count == 1
        assert snap.label == "test"

    def test_snapshot_manager_get(self):
        mgr = SnapshotManager()
        s1 = mgr.create("test", ProcessingState.NEW, {})
        s2 = mgr.get(s1.snapshot_id)
        assert s2 is s1

    def test_snapshot_manager_get_not_found(self):
        mgr = SnapshotManager()
        assert mgr.get("nonexistent") is None

    def test_snapshot_manager_by_label(self):
        mgr = SnapshotManager()
        mgr.create("pre", ProcessingState.NEW, {})
        mgr.create("post", ProcessingState.PARSED, {})
        mgr.create("pre", ProcessingState.VALIDATED, {})
        assert len(mgr.by_label("pre")) == 2
        assert len(mgr.by_label("post")) == 1

    def test_snapshot_manager_by_state(self):
        mgr = SnapshotManager()
        mgr.create("s1", ProcessingState.PARSED, {})
        mgr.create("s2", ProcessingState.PARSED, {})
        mgr.create("s3", ProcessingState.VALIDATED, {})
        assert len(mgr.by_state(ProcessingState.PARSED)) == 2

    def test_snapshot_manager_last(self):
        mgr = SnapshotManager()
        s1 = mgr.create("first", ProcessingState.NEW, {})
        s2 = mgr.create("last", ProcessingState.PARSED, {})
        assert mgr.last() is s2

    def test_snapshot_manager_last_empty(self):
        mgr = SnapshotManager()
        assert mgr.last() is None

    def test_snapshot_diff_identical(self):
        mgr = SnapshotManager()
        data = {"x": 1, "y": 2}
        s1 = mgr.create("a", ProcessingState.NEW, dict(data))
        s2 = mgr.create("b", ProcessingState.NEW, dict(data))
        diff = mgr.diff(s1.snapshot_id, s2.snapshot_id)
        assert diff.get("changed", {}) == {}
        assert diff.get("added", {}) == {}
        assert diff.get("removed", {}) == {}

    def test_snapshot_diff_changed(self):
        mgr = SnapshotManager()
        s1 = mgr.create("a", ProcessingState.NEW, {"x": 1, "y": 2})
        s2 = mgr.create("b", ProcessingState.NEW, {"x": 99, "y": 2})
        diff = mgr.diff(s1.snapshot_id, s2.snapshot_id)
        assert "x" in diff["changed"]

    def test_snapshot_diff_added(self):
        mgr = SnapshotManager()
        s1 = mgr.create("a", ProcessingState.NEW, {"x": 1})
        s2 = mgr.create("b", ProcessingState.NEW, {"x": 1, "y": 2})
        diff = mgr.diff(s1.snapshot_id, s2.snapshot_id)
        assert "y" in diff["added"]

    def test_snapshot_diff_not_found(self):
        mgr = SnapshotManager()
        with pytest.raises(SnapshotNotFoundError):
            mgr.diff("nonexistent", "also_nonexistent")

    def test_snapshot_manager_clear(self):
        mgr = SnapshotManager()
        mgr.create("test", ProcessingState.NEW, {})
        mgr.clear()
        assert mgr.count == 0

    def test_context_diff_snapshots(self):
        ctx = DocumentContext()
        s1 = ctx.snapshot("before")
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        s2 = ctx.snapshot("after")
        diff = ctx.diff_snapshots(s1.snapshot_id, s2.snapshot_id)
        assert "metadata" in diff["changed"]


# =============================================================================
# SERIALIZATION TESTS
# =============================================================================

class TestSerialization:
    def test_to_dict(self):
        ctx = _create_full_ctx()
        d = DocumentContextSerializer.to_dict(ctx)
        assert d["identity"]["document_id"] == ctx.document_id
        assert d["state"] == "VALIDATED"
        assert d["metadata"]["company"] == "ACME"

    def test_to_dict_roundtrip(self):
        ctx = _create_full_ctx()
        d = DocumentContextSerializer.to_dict(ctx)
        ctx2 = DocumentContextSerializer.from_dict(d)
        assert ctx2.document_id == ctx.document_id
        assert ctx2.metadata.company == "ACME"
        assert ctx2.state == ProcessingState.VALIDATED

    def test_to_json(self):
        ctx = _create_full_ctx()
        json_str = DocumentContextSerializer.to_json(ctx)
        data = json.loads(json_str)
        assert data["state"] == "VALIDATED"
        assert data["metadata"]["company"] == "ACME"

    def test_json_roundtrip(self):
        ctx = _create_full_ctx()
        json_str = DocumentContextSerializer.to_json(ctx)
        ctx2 = DocumentContextSerializer.from_json(json_str)
        assert ctx2.document_id == ctx.document_id
        assert ctx2.metadata.company == "ACME"

    def test_to_json_file(self):
        ctx = _create_full_ctx()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            DocumentContextSerializer.to_json_file(ctx, tmp)
            with open(tmp) as f:
                data = json.load(f)
            assert data["state"] == "VALIDATED"
        finally:
            os.unlink(tmp)

    def test_from_json_file(self):
        ctx = _create_full_ctx()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            DocumentContextSerializer.to_json_file(ctx, tmp)
            ctx2 = DocumentContextSerializer.from_json_file(tmp)
            assert ctx2.metadata.company == "ACME"
        finally:
            os.unlink(tmp)

    def test_pickle_roundtrip(self):
        ctx = _create_full_ctx()
        data = DocumentContextSerializer.to_pickle(ctx)
        ctx2 = DocumentContextSerializer.from_pickle(data)
        assert ctx2.metadata.company == "ACME"
        assert ctx2.state == ProcessingState.VALIDATED

    def test_to_markdown(self):
        ctx = _create_full_ctx()
        md = DocumentContextSerializer.to_markdown(ctx)
        assert "Document Context" in md
        assert "ACME" in md
        assert "Lifecycle" in md

    def test_to_markdown_empty(self):
        ctx = DocumentContext()
        md = DocumentContextSerializer.to_markdown(ctx)
        assert ctx.document_id in md

    def test_serialize_with_prediction(self):
        ctx = DocumentContext()
        ctx.set_prediction(PredictionData(confidence_expected=0.85, coverage_expected=0.75))
        d = DocumentContextSerializer.to_dict(ctx)
        assert d["prediction"]["confidence_expected"] == 0.85

    def test_serialize_with_execution(self):
        ctx = DocumentContext()
        ctx.set_execution(ExecutionData(status="ok"))
        d = DocumentContextSerializer.to_dict(ctx)
        assert d["execution"]["status"] == "ok"

    def test_serialize_with_custom(self):
        ctx = DocumentContext()
        ctx.set_custom("source", "api")
        d = DocumentContextSerializer.to_dict(ctx)
        assert d["custom"]["source"] == "api"
        ctx2 = DocumentContextSerializer.from_dict(d)
        assert ctx2.get_custom("source") == "api"


# =============================================================================
# MERGE TESTS
# =============================================================================

class TestMerge:
    def test_merge_full_into_empty(self):
        source = _create_full_ctx()
        target = DocumentContext()
        merged = ContextMerger.merge(target, source)
        assert merged.metadata.company == "ACME"
        assert merged.structure.family == "TRIBUTARIO"

    def test_merge_does_not_overwrite(self):
        target = DocumentContext()
        target.set_metadata(DocumentMetadata(company="EXISTENTE"))
        source = DocumentContext()
        source.set_metadata(DocumentMetadata(company="NUEVA"))
        merged = ContextMerger.merge(target, source)
        assert merged.metadata.company == "EXISTENTE"

    def test_merge_partial_metadata(self):
        ctx = DocumentContext()
        ContextMerger.merge_partial(ctx, metadata=DocumentMetadata(company="ACME"))
        assert ctx.metadata.company == "ACME"

    def test_merge_partial_no_overwrite(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ORIGINAL"))
        ContextMerger.merge_partial(ctx, metadata=DocumentMetadata(company="NUEVA"))
        assert ctx.metadata.company == "ORIGINAL"

    def test_merge_partial_structure(self):
        ctx = DocumentContext()
        ContextMerger.merge_partial(ctx, structure=StructureData(family="TRIBUTARIO"))
        assert ctx.structure.family == "TRIBUTARIO"

    def test_merge_partial_parser(self):
        ctx = DocumentContext()
        ContextMerger.merge_partial(ctx, parser=ParserData(selected_parser="Universal"))
        assert ctx.parser.selected_parser == "Universal"

    def test_merge_dict(self):
        ctx = DocumentContext()
        ContextMerger.merge_dict(ctx, {
            "metadata": {"company": "ACME", "rut": "76.693.319-K"},
            "structure": {"family": "TRIBUTARIO"},
        })
        assert ctx.metadata.company == "ACME"
        assert ctx.structure.family == "TRIBUTARIO"

    def test_merge_dict_no_overwrite(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="EXISTENTE"))
        ContextMerger.merge_dict(ctx, {"metadata": {"company": "NUEVA"}})
        assert ctx.metadata.company == "EXISTENTE"

    def test_merge_dict_custom(self):
        ctx = DocumentContext()
        ContextMerger.merge_dict(ctx, {"custom": {"key1": "val1"}})
        assert ctx.get_custom("key1") == "val1"

    def test_merge_source_into_target(self):
        source = DocumentContext()
        source.set_metadata(DocumentMetadata(company="S1"))
        source.set_structure(StructureData(family="F1"))
        target = DocumentContext()
        target.set_metadata(DocumentMetadata(company="T1"))
        merged = ContextMerger.merge(target, source)
        assert merged.metadata.company == "T1"
        assert merged.structure.family == "F1"


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestValidation:
    def test_validate_new_ctx(self):
        ctx = DocumentContext()
        issues = ctx.validate()
        assert isinstance(issues, list)

    def test_validate_parser_no_accounts(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        ctx.set_parser(ParserData(selected_parser="Universal"))
        issues = ctx.validate()
        parser_warnings = [i for i in issues if i.category == "parser"]
        assert any("vacía" in i.message for i in parser_warnings)

    def test_validate_validation_no_parser(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        ctx.set_parser(ParserData(selected_parser="U", accounts=["a"]))
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        issues = ctx.validate()
        assert isinstance(issues, list)

    def test_validate_validation_errors(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        ctx.set_parser(ParserData(selected_parser="U", accounts=["a"]))
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData(errors=["ecuación no balancea"]))
        issues = ctx.validate()
        validation_errors = [i for i in issues if i.category == "validation"]
        assert any("ecuación" in i.message for i in validation_errors)

    def test_validate_returns_list(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        issues = ctx.validate()
        assert isinstance(issues, list)

    def test_validation_issue_to_dict(self):
        issue = ValidationIssue(field="test", severity="error", message="algo mal", category="test")
        d = issue.to_dict()
        assert d["field"] == "test"
        assert d["severity"] == "error"

    def test_validator_required_fields(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        issues = ContextValidator._check_required_fields(
            ctx, ProcessingState.STRUCTURED
        )
        assert isinstance(issues, list)

    def test_validator_lifecycle_consistency(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.fail("error")
        issues = ContextValidator._check_lifecycle_consistency(ctx)
        assert isinstance(issues, list)

    def test_validator_completion_without_review(self):
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        ctx.mark_reviewed()
        ctx.complete()
        issues = ContextValidator._check_completion_issues(ctx)
        assert isinstance(issues, list)


# =============================================================================
# LIFECYCLE MANAGER UNIT TESTS
# =============================================================================

class TestLifecycleManagerUnit:
    def test_initial_state(self):
        lm = LifecycleManager()
        assert lm.state == ProcessingState.NEW
        assert lm.can_transition

    def test_valid_transition(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.IDENTIFIED, module="test", description="test")
        assert lm.state == ProcessingState.IDENTIFIED
        assert len(lm.events) == 1

    def test_invalid_transition(self):
        lm = LifecycleManager()
        with pytest.raises(LifecycleError):
            lm.transition(ProcessingState.PARSED)

    def test_transition_from_terminal(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.FAILED, module="test")
        assert not lm.can_transition
        with pytest.raises(LifecycleError):
            lm.transition(ProcessingState.IDENTIFIED)

    def test_events_by_module(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.IDENTIFIED, module="mod_a")
        lm.transition(ProcessingState.STRUCTURED, module="mod_b")
        lm.transition(ProcessingState.PARSED, module="mod_a")
        assert len(lm.events_by_module("mod_a")) == 2
        assert len(lm.events_by_module("mod_b")) == 1

    def test_last_event(self):
        lm = LifecycleManager()
        assert lm.last_event() is None
        lm.transition(ProcessingState.IDENTIFIED, module="test")
        assert lm.last_event().to_state == ProcessingState.IDENTIFIED

    def test_reset(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.IDENTIFIED, module="test")
        lm.reset()
        assert lm.state == ProcessingState.NEW
        assert len(lm.events) == 0

    def test_to_dict(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.IDENTIFIED, module="test")
        d = lm.to_dict()
        assert d["state"] == "IDENTIFIED"
        assert d["total_events"] == 1

    def test_required_data_for_state(self):
        lm = LifecycleManager()
        req = lm.required_data_for_state(ProcessingState.PARSED)
        assert "parser" in req
        assert "metadata" in req
        assert "structure" in req


# =============================================================================
# STATISTICS TESTS
# =============================================================================

class TestStatistics:
    def test_empty_stats(self):
        stats = ContextStatistics()
        assert stats.count == 0
        assert stats.avg_confidence_expected() == 0.0
        assert stats.avg_processing_time() == 0.0
        assert stats.total_snapshots() == 0

    def test_add_single_context(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        stats.add(ctx)
        assert stats.count == 1

    def test_add_batch(self):
        stats = ContextStatistics()
        stats.add_batch([DocumentContext(), DocumentContext()])
        assert stats.count == 2

    def test_by_state(self):
        stats = ContextStatistics()
        ctx1 = DocumentContext()
        ctx2 = DocumentContext()
        ctx2.set_metadata(DocumentMetadata())
        stats.add_batch([ctx1, ctx2])
        by_state = stats.by_state()
        assert by_state.get("NEW", 0) == 1
        assert by_state.get("IDENTIFIED", 0) == 1

    def test_count_with_metadata(self):
        stats = ContextStatistics()
        ctx1 = DocumentContext()
        ctx2 = DocumentContext()
        ctx2.set_metadata(DocumentMetadata())
        stats.add_batch([ctx1, ctx2])
        assert stats.count_with_metadata() == 1

    def test_count_with_parser(self):
        stats = ContextStatistics()
        ctx = _create_full_ctx()
        stats.add(ctx)
        assert stats.count_with_parser() == 1

    def test_avg_accounts(self):
        stats = ContextStatistics()
        ctx = _create_full_ctx()
        stats.add(ctx)
        assert stats.avg_accounts_per_document() > 0

    def test_total_snapshots(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.snapshot("s1")
        ctx.snapshot("s2")
        stats.add(ctx)
        assert stats.total_snapshots() == 2

    def test_total_events(self):
        stats = ContextStatistics()
        ctx = _create_minimal_ctx_with_parser()
        stats.add(ctx)
        assert stats.total_events() >= 3

    def test_to_dict(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        stats.add(ctx)
        d = stats.to_dict()
        assert d["total_documents"] == 1
        assert "by_state" in d

    def test_generate_markdown(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata(company="ACME"))
        stats.add(ctx)
        md = stats.generate_markdown()
        assert "Document Context" in md
        assert "Resumen Global" in md

    def test_clear(self):
        stats = ContextStatistics()
        stats.add(DocumentContext())
        stats.clear()
        assert stats.count == 0

    def test_avg_confidence_expected(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.set_prediction(PredictionData(confidence_expected=0.85))
        stats.add(ctx)
        assert stats.avg_confidence_expected() == 0.85

    def test_avg_coverage_expected(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.set_prediction(PredictionData(coverage_expected=0.75))
        stats.add(ctx)
        assert stats.avg_coverage_expected() == 0.75

    def test_count_completed(self):
        stats = ContextStatistics()
        ctx = _create_minimal_ctx_with_parser()
        ctx.set_knowledge(KnowledgeData())
        ctx.set_validation(ValidationData())
        ctx.mark_reviewed()
        ctx.complete()
        stats.add(ctx)
        assert stats.count_completed() == 1

    def test_count_failed(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.fail("error")
        stats.add(ctx)
        assert stats.count_failed() == 1

    def test_avg_snapshots_per_document(self):
        stats = ContextStatistics()
        ctx = DocumentContext()
        ctx.snapshot("s1")
        ctx.snapshot("s2")
        stats.add(ctx)
        assert stats.avg_snapshots_per_document() == 2.0


# =============================================================================
# GENERIC STATE MACHINE TESTS
# =============================================================================

class TestStateMachine:
    def test_transition_to_same_state_not_recorded(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        evt = ctx.events[-1]
        assert evt.from_state is None or evt.from_state == ProcessingState.NEW

    def test_cannot_complete_without_metadata(self):
        ctx = DocumentContext()
        with pytest.raises(LifecycleError):
            ctx.complete()

    def test_cannot_review_without_validation(self):
        ctx = DocumentContext()
        with pytest.raises(LifecycleError):
            ctx.mark_reviewed()

    def test_updated_at_changes_on_transition(self):
        ctx = DocumentContext()
        t1 = ctx.identity.updated_at
        ctx.set_metadata(DocumentMetadata())
        t2 = ctx.identity.updated_at
        assert t2 >= t1

    def test_events_order_preserved(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        ctx.set_structure(StructureData())
        states = [e.to_state for e in ctx.events]
        assert states == [ProcessingState.IDENTIFIED, ProcessingState.STRUCTURED]

    def test_terminal_state_events_still_recorded(self):
        lm = LifecycleManager()
        lm.transition(ProcessingState.IDENTIFIED, module="test")
        assert len(lm.events) == 1

    def test_snapshot_auto_created_on_transition(self):
        ctx = DocumentContext()
        ctx.set_metadata(DocumentMetadata())
        assert any("before_identified" in s.label for s in ctx.snapshots)

    def test_multiple_snapshots_same_label(self):
        ctx = DocumentContext()
        ctx.snapshot("checkpoint")
        ctx.set_metadata(DocumentMetadata())
        ctx.snapshot("checkpoint")
        assert len([s for s in ctx.snapshots if s.label == "checkpoint"]) == 2


# =============================================================================
# HELPERS
# =============================================================================

def _create_minimal_ctx() -> DocumentContext:
    ctx = DocumentContext()
    ctx.set_metadata(DocumentMetadata(company="ACME"))
    ctx.set_structure(StructureData(family="TRIBUTARIO"))
    return ctx


def _create_minimal_ctx_with_parser() -> DocumentContext:
    ctx = DocumentContext()
    ctx.set_metadata(DocumentMetadata(company="ACME"))
    ctx.set_structure(StructureData(family="TRIBUTARIO"))
    ctx.set_parser(ParserData(selected_parser="Universal", accounts=["a"]))
    return ctx


def _create_full_ctx() -> DocumentContext:
    ctx = DocumentContext(source_file="test.pdf")
    ctx.set_metadata(DocumentMetadata(
        company="ACME", rut="76.693.319-K", year=2024, pages=5,
        language="es", orientation="vertical", layout="DOUBLE_COLUMN",
        ocr_probability=0.05,
    ))
    ctx.set_structure(StructureData(
        family="TRIBUTARIO", template="T14", document_type="BALANCE_TRIBUTARIO",
        sections=[{"name": "ACTIVO", "count": 10}, {"name": "PASIVO", "count": 8}],
        column_layout="DOUBLE_COLUMN",
    ))
    ctx.set_parser(ParserData(
        selected_parser="Universal", parser_version="2.0", parser_time=3.2,
        accounts=[{"code": "1.1.01", "name": "Caja", "amount": 100}],
        raw_accounts=[{"line": "1  Caja  100"}],
        ignored_accounts=[],
    ))
    ctx.set_knowledge(KnowledgeData(
        cmcc_matches=[{"code": "1.1.01", "name": "Caja"}],
        learning_hits=[{"code": "1.1.01"}],
    ))
    ctx.set_validation(ValidationData(
        warnings=["subtotal cercano"],
    ))
    ctx.set_prediction(PredictionData(
        confidence_expected=0.85, coverage_expected=0.90,
        estimated_time=6.2, complexity="MEDIA",
    ))
    ctx.set_execution(ExecutionData(
        confidence_real=0.88, coverage_real=0.92,
        processing_time=5.8, review_required=False, status="ok",
    ))
    ctx.snapshot("before_validation")
    return ctx
