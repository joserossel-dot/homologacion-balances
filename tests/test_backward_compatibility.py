from __future__ import annotations

from pathlib import Path

import pytest

from orchestrator.pipeline_v2 import HomologationPipelineV2
from adapters.kb_adapter import KBAdapter
from document_context.models import ProcessingState


HOLDOUT_DIR = Path("datasets/HOLDOUT")
TRAINING_DIR = Path("datasets/TRAINING")
STRESS_DIR = Path("datasets/STRESS")


def _get_files(directory: Path, limit: int = 5) -> list[Path]:
    if not directory.exists():
        return []
    pdfs = sorted(directory.glob("*.pdf"))
    return pdfs[:limit]


# =========================================================================
# Shared fixtures — process once, reuse across tests
# =========================================================================

@pytest.fixture(scope="session")
def v1_v2_holdout_results():
    from pipeline.homologation_pipeline import HomologationPipeline
    files = _get_files(HOLDOUT_DIR, 5)
    if not files:
        pytest.skip("No HOLDOUT files available")
    v1_pipe = HomologationPipeline()
    v2_pipe = HomologationPipelineV2()
    results = []
    for pdf in files:
        v1_res = v1_pipe.process(str(pdf))
        ctx = v2_pipe.process(str(pdf))
        v2_res = KBAdapter.extract_v1_summary(ctx)
        v2_classified = ctx.get_custom("classified", [])
        v2_ignored = ctx.get_custom("ignored", [])
        results.append({
            "file": pdf,
            "v1": v1_res,
            "v2_summary": v2_res,
            "v2_classified": v2_classified,
            "v2_ignored": v2_ignored,
            "ctx": ctx,
        })
    return results


@pytest.fixture(scope="session")
def v1_v2_training_results():
    from pipeline.homologation_pipeline import HomologationPipeline
    files = _get_files(TRAINING_DIR, 5)
    if not files:
        pytest.skip("No TRAINING files available")
    v1_pipe = HomologationPipeline()
    v2_pipe = HomologationPipelineV2()
    results = []
    for pdf in files:
        v1_res = v1_pipe.process(str(pdf))
        ctx = v2_pipe.process(str(pdf))
        results.append({
            "file": pdf,
            "v1": v1_res,
            "v2_classified": ctx.get_custom("classified", []),
            "v2_ignored": ctx.get_custom("ignored", []),
        })
    return results


@pytest.fixture(scope="session")
def v1_v2_stress_results():
    from pipeline.homologation_pipeline import HomologationPipeline
    if not STRESS_DIR.exists():
        pytest.skip("No STRESS directory")
    pdfs = sorted(STRESS_DIR.glob("**/*.pdf"))[:3]
    if not pdfs:
        pytest.skip("No STRESS files available")
    v1_pipe = HomologationPipeline()
    v2_pipe = HomologationPipelineV2()
    results = []
    for pdf in pdfs:
        v1_res = v1_pipe.process(str(pdf))
        ctx = v2_pipe.process(str(pdf))
        results.append({
            "file": pdf,
            "v1": v1_res,
            "v2_classified": ctx.get_custom("classified", []),
        })
    return results


# =========================================================================
# HOLDOUT Tests
# =========================================================================

class TestHoldoutBackwardCompat:
    def test_classified_count(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_count = r["v1"].get("accounts_classified", 0)
            v2_count = len(r["v2_classified"])
            assert v1_count == v2_count, (
                f"Classified count mismatch for {r['file'].name}: V1={v1_count} V2={v2_count}"
            )

    def test_ignored_count(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_count = r["v1"].get("accounts_ignored", 0)
            v2_count = len(r["v2_ignored"])
            assert v1_count == v2_count, (
                f"Ignored count mismatch for {r['file'].name}: V1={v1_count} V2={v2_count}"
            )

    def test_total_count(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_total = r["v1"].get("accounts_total", 0)
            v2_total = r["v2_summary"].get("accounts_total", 0)
            assert v1_total == v2_total, (
                f"Total count mismatch for {r['file'].name}: V1={v1_total} V2={v2_total}"
            )

    def test_standard_codes(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            assert len(v1_cls) == len(v2_cls)
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("standard_code") == c2.get("standard_code"), (
                    f"Code mismatch at {i} for {r['file'].name}: "
                    f"V1={c1.get('standard_code')} V2={c2.get('standard_code')}"
                )
                assert c1.get("account_code") == c2.get("account_code")

    def test_methods_match(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("method") == c2.get("method"), (
                    f"Method mismatch at {i} for {r['file'].name}: "
                    f"V1={c1.get('method')} V2={c2.get('method')}"
                )

    def test_final_codes(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("final_code") == c2.get("final_code"), (
                    f"Final code mismatch at {i} for {r['file'].name}: "
                    f"V1={c1.get('final_code')} V2={c2.get('final_code')}"
                )

    def test_confidence_within_tolerance(self, v1_v2_holdout_results):
        tolerance = 0.001
        for r in v1_v2_holdout_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                diff = abs(float(c1.get("confidence", 0)) - float(c2.get("confidence", 0)))
                assert diff <= tolerance, (
                    f"Confidence mismatch at {i} for {r['file'].name}: "
                    f"V1={c1.get('confidence')} V2={c2.get('confidence')}"
                )

    def test_account_names(self, v1_v2_holdout_results):
        for r in v1_v2_holdout_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("account_name") == c2.get("account_name")


# =========================================================================
# TRAINING Tests
# =========================================================================

class TestTrainingBackwardCompat:
    def test_training_classified_count(self, v1_v2_training_results):
        for r in v1_v2_training_results:
            v1_count = r["v1"].get("accounts_classified", 0)
            v2_count = len(r["v2_classified"])
            assert v1_count == v2_count, (
                f"Classified mismatch for {r['file'].name}"
            )

    def test_training_ignored_count(self, v1_v2_training_results):
        for r in v1_v2_training_results:
            v1_count = r["v1"].get("accounts_ignored", 0)
            v2_count = len(r["v2_ignored"])
            assert v1_count == v2_count, (
                f"Ignored mismatch for {r['file'].name}"
            )

    def test_training_standard_codes(self, v1_v2_training_results):
        for r in v1_v2_training_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("standard_code") == c2.get("standard_code")


# =========================================================================
# STRESS Tests
# =========================================================================

class TestStressBackwardCompat:
    def test_stress_classified_count(self, v1_v2_stress_results):
        for r in v1_v2_stress_results:
            v1_count = r["v1"].get("accounts_classified", 0)
            v2_count = len(r["v2_classified"])
            assert v1_count == v2_count, (
                f"Classified mismatch for {r['file'].name}"
            )

    def test_stress_standard_codes(self, v1_v2_stress_results):
        for r in v1_v2_stress_results:
            v1_cls = r["v1"].get("classified", [])
            v2_cls = r["v2_classified"]
            for i, (c1, c2) in enumerate(zip(v1_cls, v2_cls)):
                assert c1.get("standard_code") == c2.get("standard_code")


# =========================================================================
# V1 Still Works
# =========================================================================

class TestV1StillWorks:
    def test_v1_process_returns_dict(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        pipe = HomologationPipeline()
        pdfs = _get_files(HOLDOUT_DIR, 1)
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        result = pipe.process(str(pdfs[0]))
        assert isinstance(result, dict)
        assert "classified" in result

    def test_v1_has_required_keys(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        pipe = HomologationPipeline()
        pdfs = _get_files(HOLDOUT_DIR, 1)
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        result = pipe.process(str(pdfs[0]))
        for key in ("source_file", "accounts_total", "classified", "ignored"):
            assert key in result, f"Missing key: {key}"

    def test_v1_v2_can_coexist(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        v1 = HomologationPipeline()
        v2 = HomologationPipelineV2()
        assert type(v1).__name__ != type(v2).__name__

    def test_v1_not_modified(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        import inspect
        source = inspect.getsource(HomologationPipeline.process)
        assert "DocumentContext" not in source

    def test_v2_process_returns_document_context(self):
        pdfs = _get_files(HOLDOUT_DIR, 1)
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        v2 = HomologationPipelineV2()
        ctx = v2.process(str(pdfs[0]))
        assert ctx.state == ProcessingState.COMPLETED

    def test_v2_process_to_dict(self):
        pdfs = _get_files(HOLDOUT_DIR, 1)
        if not pdfs:
            pytest.skip("No HOLDOUT files")
        v2 = HomologationPipelineV2()
        d = v2.process_to_dict(str(pdfs[0]))
        assert "classified" in d
        assert "dce_state" in d
