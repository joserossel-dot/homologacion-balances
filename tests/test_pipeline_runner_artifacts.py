from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from document_context import DocumentContext
from backend.backend_models import BackendResult, ExecutionMetrics
from backend.execution_manager import ExecutionManager
from backend.result_builder import ResultBuilder
from backend.pipeline_runner import PipelineRunner
from backend.config import BackendConfig


# =========================================================================
# Helpers
# =========================================================================

def _ctx_with_data() -> DocumentContext:
    ctx = DocumentContext(source_file="test.pdf")
    ctx.set_custom("classified", [
        {"account": "101", "standard_code": "110101", "method": "learning_exact", "confidence": 0.95},
        {"account": "102", "standard_code": "110102", "method": "learning_fuzzy", "confidence": 0.88},
        {"account": "103", "standard_code": None, "method": "unknown", "confidence": 0.0},
    ])
    ctx.set_custom("ignored", [
        {"account": "999", "standard_code": None, "method": "ignored", "confidence": 1.0},
    ])
    ctx.set_custom("coverage", {"overall": 0.562, "classified": 63, "total": 101})
    ctx.set_custom("decisions", [
        {"account": "101", "decision": "approve", "reason": "exact_match"},
        {"account": "102", "decision": "approve", "reason": "fuzzy_match"},
    ])
    ctx.set_custom("decision_stats", {"total": 2, "approved": 2, "conflicts_detected": 0})
    ctx.set_custom("self_qa", {
        "approval_state": "APPROVED",
        "confidence": {"overall": 1.0},
        "risk": {"total_risk": 0.0},
    })
    ctx.set_custom("review_queue", [])
    return ctx


# =========================================================================
# Regression: ArtifactManager receives complete BackendResult
# =========================================================================

class TestPipelineRunnerArtifacts:

    def test_artifact_manager_receives_complete_result(self, tmp_path):
        pipeline = MagicMock()
        pipeline.process.return_value = _ctx_with_data()

        em = ExecutionManager()
        saved_result: BackendResult | None = None

        def capture_save_all(result: BackendResult) -> dict[str, str]:
            nonlocal saved_result
            saved_result = result
            return {"result_json": "/fake/result.json", "summary_md": "/fake/summary.md"}

        artifact_manager = MagicMock()
        artifact_manager.save_all.side_effect = capture_save_all

        result_builder = ResultBuilder()

        config = BackendConfig(artifacts_enabled=True, runs_dir=str(tmp_path / "runs"))

        runner = PipelineRunner(
            pipeline=pipeline,
            execution_manager=em,
            logger=MagicMock(),
            artifact_manager=artifact_manager,
            result_builder=result_builder,
            config=config,
        )
        runner._log.to_dict.return_value = [{"level": "INFO", "message": "test"}]

        pdf = tmp_path / "test.pdf"
        pdf.write_text("dummy")
        result = runner.run(str(pdf))

        assert saved_result is not None, "artifact_manager.save_all was never called"

        # execution.status = completed (not pending)
        assert saved_result.execution.status == "completed"

        # total_accounts > 0
        assert saved_result.statistics.total_accounts == 4

        # coverage no vacío
        assert saved_result.coverage
        assert saved_result.coverage.get("overall") == 0.562

        # decisions no vacío
        assert len(saved_result.decisions) == 2

        # qa no vacío
        assert saved_result.qa
        assert saved_result.qa.get("approval_state") == "APPROVED"

        # The returned result is also complete
        assert result.execution.status == "completed"
        assert result.statistics.total_accounts == 4
        assert result.coverage.get("overall") == 0.562
        assert len(result.decisions) == 2
        assert result.qa.get("approval_state") == "APPROVED"
        assert result.export_paths == {"result_json": "/fake/result.json", "summary_md": "/fake/summary.md"}

    def test_artifacts_disabled_returns_result_anyway(self, tmp_path):
        pipeline = MagicMock()
        pipeline.process.return_value = _ctx_with_data()

        result_builder = ResultBuilder()
        artifact_manager = MagicMock()
        config = BackendConfig(artifacts_enabled=False)
        em = ExecutionManager()

        runner = PipelineRunner(
            pipeline=pipeline,
            execution_manager=em,
            logger=MagicMock(),
            artifact_manager=artifact_manager,
            result_builder=result_builder,
            config=config,
        )
        runner._log.to_dict.return_value = []

        pdf = tmp_path / "test.pdf"
        pdf.write_text("dummy")
        result = runner.run(str(pdf))

        artifact_manager.save_all.assert_not_called()
        assert result.statistics.total_accounts == 4
        assert result.coverage.get("overall") == 0.562
        assert len(result.decisions) == 2
        assert result.qa.get("approval_state") == "APPROVED"
        assert result.execution.status == "completed"

    def test_pipeline_error_does_not_save_artifacts(self, tmp_path):
        pipeline = MagicMock()
        pipeline.process.side_effect = ValueError("Pipeline crashed")

        artifact_manager = MagicMock()
        result_builder = MagicMock()
        config = BackendConfig(artifacts_enabled=True)
        em = ExecutionManager()

        runner = PipelineRunner(
            pipeline=pipeline,
            execution_manager=em,
            logger=MagicMock(),
            artifact_manager=artifact_manager,
            result_builder=result_builder,
            config=config,
        )

        pdf = tmp_path / "test.pdf"
        pdf.write_text("dummy")

        with pytest.raises(ValueError, match="Pipeline crashed"):
            runner.run(str(pdf))

        artifact_manager.save_all.assert_not_called()

    def test_v1_compatibility_pipeline_returns_ctx(self, tmp_path):
        """V1 pipelines that return dict instead of DocumentContext still work."""
        pipeline = MagicMock()

        ctx = _ctx_with_data()
        pipeline.process.return_value = ctx

        em = ExecutionManager()
        result_builder = ResultBuilder()
        artifact_manager = MagicMock()
        config = BackendConfig(artifacts_enabled=True)

        runner = PipelineRunner(
            pipeline=pipeline,
            execution_manager=em,
            logger=MagicMock(),
            artifact_manager=artifact_manager,
            result_builder=result_builder,
            config=config,
        )
        runner._log.to_dict.return_value = []

        pdf = tmp_path / "test.pdf"
        pdf.write_text("dummy")
        result = runner.run(str(pdf))

        assert result.execution.status == "completed"
        assert result.statistics.total_accounts == 4
