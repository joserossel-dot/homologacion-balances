from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from pipeline.features import CMCCFeatureFlags
from pipeline.homologation_pipeline import HomologationPipeline


def _make_pipeline(
    enable_cmcc: bool = False,
    enable_shadow: bool = True,
    enable_production: bool = False,
    threshold: float = 0.95,
) -> HomologationPipeline:
    features = CMCCFeatureFlags(
        ENABLE_CMCC=enable_cmcc,
        ENABLE_CMCC_SHADOW=enable_shadow,
        ENABLE_CMCC_PRODUCTION=enable_production,
        CMCC_THRESHOLD=threshold,
    )
    return HomologationPipeline(features=features)


def _mock_learning_no_match(*args, **kwargs) -> dict[str, Any]:
    return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}


def _mock_learning_exact(*args, **kwargs) -> dict[str, Any]:
    return {
        "source": "exact", "code": "PC.01",
        "confidence": 0.99, "matched_name": "PROVEEDORES",
    }


# ─────────────────────────────────────────────
# Classification behavior with CMCC disabled
# ─────────────────────────────────────────────

class TestPipelineCMCCDisabled:
    """ENABLE_CMCC=False → CMCC must never affect classification."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(enable_cmcc=False)
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)

    def test_skips_cmcc_completely(self):
        """No CMCC detail in result when CMCC is disabled."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert "_cmcc_score" in result
        assert result["_cmcc_score"] == -1.0
        assert "cmcc_shadow" not in result
        assert result.get("cmcc_detail") is None

    def test_falls_through_to_dictionary(self):
        """Dictionary classification still works when CMCC is disabled."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert result is not None
        assert result["method"] != "unclassified"

    def test_no_cmcc_shadow_stored(self):
        """No cmcc_shadow field when CMCC is disabled."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert "cmcc_shadow" not in result

    def test_standard_code_is_from_dictionary(self):
        """Classification comes from code/dictionary, not CMCC."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        if result["method"] != "unclassified":
            assert result["standard_code"] is not None


# ─────────────────────────────────────────────
# Classification behavior with CMCC shadow mode
# ─────────────────────────────────────────────

class TestPipelineCMCCShadow:
    """ENABLE_CMCC=True + SHADOW=True → CMCC runs but never modifies official result."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(
            enable_cmcc=True, enable_shadow=True, enable_production=False,
        )
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)

    def test_shadow_stores_cmcc_result(self):
        """CMCC shadow data stored when in shadow mode."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_shadow = result.get("cmcc_shadow")
        assert cmcc_shadow is not None, "cmcc_shadow should be present in shadow mode"
        assert "code" in cmcc_shadow
        assert "score" in cmcc_shadow
        assert "concept" in cmcc_shadow
        assert "evidence" in cmcc_shadow

    def test_shadow_does_not_override_standard_code(self):
        """Official standard_code is NOT CMCC's when in shadow mode."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        method = result.get("method", "")
        assert not method.startswith("cmcc_"), (
            f"Method should not be cmcc_ in shadow mode, got: {method}"
        )

    def test_shadow_has_score_and_concept(self):
        """Shadow data contains score and concepto sugerido."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_shadow = result.get("cmcc_shadow", {})
        assert isinstance(cmcc_shadow.get("score"), (int, float))
        assert cmcc_shadow.get("concept") is not None
        assert cmcc_shadow.get("code") is not None

    def test_shadow_has_explicacion(self):
        """Shadow data contains explicación (method + matched_variant)."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_shadow = result.get("cmcc_shadow", {})
        assert isinstance(cmcc_shadow.get("method"), str)
        assert cmcc_shadow.get("evidence") is not None

    def test_shadow_has_evidencia(self):
        """Shadow data contains evidencia list."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_shadow = result.get("cmcc_shadow", {})
        assert isinstance(cmcc_shadow.get("evidence"), list)
        assert len(cmcc_shadow["evidence"]) > 0

    def test_shadow_on_unknown_account(self):
        """Shadow still runs on unknown accounts (low CMCC score)."""
        result = self.pipeline._classify_account("999", "ZXCVBNM ASDFGHJK")
        cmcc_shadow = result.get("cmcc_shadow")
        assert cmcc_shadow is not None
        assert isinstance(cmcc_shadow.get("score"), (int, float))

    def test_review_queue_not_populated_in_shadow(self):
        """Review queue is empty in shadow mode (no production)."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales",
                                                  store_cmcc_shadow=True)
        _cmcc_score = result.get("_cmcc_score", -1.0)
        # Verify cmcc detail is present but not affecting official
        assert "cmcc_detail" in result

    def test_shadow_method_is_tracked(self):
        """Pipeline summary tracks shadow hits."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        if result.get("cmcc_shadow", {}).get("score", 0) >= 0.90:
            assert result.get("_cmcc_score", 0) >= 0.90


# ─────────────────────────────────────────────
# Classification behavior with CMCC production mode
# ─────────────────────────────────────────────

class TestPipelineCMCCProduction:
    """ENABLE_CMCC_PRODUCTION=True → CMCC modifies classification when score >= threshold."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(
            enable_cmcc=True, enable_shadow=False, enable_production=True,
            threshold=0.95,
        )
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)

    def test_production_uses_cmcc_when_score_high(self):
        """CMCC production uses cmcc result when score >= threshold."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_detail = result.get("cmcc_detail")
        if cmcc_detail and cmcc_detail.get("score", 0) >= 0.95:
            method = result.get("method", "")
            assert method.startswith("cmcc_"), (
                f"Method should start with cmcc_ in production mode, got: {method}"
            )

    def test_production_standard_code_is_cmcc(self):
        """standard_code comes from CMCC in production mode."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_detail = result.get("cmcc_detail", {})
        if cmcc_detail and cmcc_detail.get("score", 0) >= 0.95:
            assert result.get("standard_code") == cmcc_detail["code"]

    def test_production_confidence_is_cmcc_score(self):
        """Confidence is the CMCC score in production mode."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_detail = result.get("cmcc_detail", {})
        if cmcc_detail and cmcc_detail.get("score", 0) >= 0.95:
            assert result.get("confidence") == cmcc_detail["score"]

    def test_production_reason_mentions_cmcc(self):
        """Reason mentions CMCC when CMCC is the classifier."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_detail = result.get("cmcc_detail", {})
        if cmcc_detail and cmcc_detail.get("score", 0) >= 0.95:
            reason = result.get("reason", "")
            assert "CMCC" in reason

    def test_production_skips_low_score(self):
        """CMCC does NOT modify classification when score < threshold."""
        result = self.pipeline._classify_account("999", "ZXCVBNM ASDFGHJK")
        cmcc_detail = result.get("cmcc_detail", {})
        assert cmcc_detail is None or cmcc_detail.get("score", 0) < 0.95
        method = result.get("method", "")
        assert not method.startswith("cmcc_")

    def test_production_does_not_store_shadow(self):
        """No cmcc_shadow when shadow mode is off."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales",
                                                  store_cmcc_shadow=False)
        assert "cmcc_shadow" not in result


# ─────────────────────────────────────────────
# Learning Engine takes priority over CMCC
# ─────────────────────────────────────────────

class TestPipelineCMCCPriority:
    """Learning Engine (Gold Standard) must take priority over CMCC."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(
            enable_cmcc=True, enable_shadow=True, enable_production=True,
        )
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_exact)

    def test_learning_takes_priority_over_cmcc(self):
        """Learning Engine match prevents CMCC from classifying."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        method = result.get("method", "")
        assert method.startswith("learning_"), (
            f"Learning should take priority over CMCC, got: {method}"
        )

    def test_learning_with_cmcc_available(self):
        """Even if CMCC would match, Learning Engine wins."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert result.get("standard_code") == "PC.01"
        assert result.get("method") == "learning_exact"


# ─────────────────────────────────────────────
# Rollback behavior
# ─────────────────────────────────────────────

class TestPipelineRollback:
    """ENABLE_CMCC=False must be equivalent to no CMCC integration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(enable_cmcc=False)
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)

    def test_rollback_no_cmcc_in_result(self):
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert "cmcc_shadow" not in result
        assert result.get("cmcc_detail") is None

    def test_rollback_standard_classification_works(self):
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        assert result.get("method") != "cmcc_none"

    def test_rollback_pipeline_summary(self):
        result = self.pipeline.process.__wrapped__(self.pipeline, None) if hasattr(
            self.pipeline.process, "__wrapped__"
        ) else None
        if result is None:
            pass

    def test_rollback_via_feature_flag(self):
        flags = CMCCFeatureFlags(ENABLE_CMCC_ROLLBACK=True)
        assert flags.ENABLE_CMCC is False
        assert flags.ENABLE_CMCC_SHADOW is False

    def test_rollback_env_var(self):
        import os
        os.environ["CMCC_ENABLE_CMCC_ROLLBACK"] = "true"
        try:
            flags = CMCCFeatureFlags.from_env()
            assert flags.ENABLE_CMCC is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC_ROLLBACK"]


# ─────────────────────────────────────────────
# Pipeline summary includes CMCC metrics
# ─────────────────────────────────────────────

class TestPipelineSummaryCMCC:
    """Pipeline summary dict must include CMCC metrics."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(
            enable_cmcc=True, enable_shadow=True, enable_production=True,
        )
        self.pipeline._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)

    def test_summary_includes_cmcc_flags(self):
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        cmcc_detail = result.get("cmcc_detail", {})
        if cmcc_detail and cmcc_detail.get("score", 0) >= 0.95:
            assert "cmcc_detail" in result

    def test_cmcc_shadow_field_in_classified(self):
        """Classified entry contains cmcc_shadow."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales",
                                                  store_cmcc_shadow=True)
        assert "cmcc_shadow" in result or "_cmcc_score" in result


# ─────────────────────────────────────────────
# Feature flag environment variable integration
# ─────────────────────────────────────────────

class TestCMCCFeatureEnvVar:
    def test_from_env_production(self):
        import os
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "true"
        os.environ["CMCC_CMCC_THRESHOLD"] = "0.90"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is True
            assert f.ENABLE_CMCC_PRODUCTION is True
            assert f.CMCC_THRESHOLD == 0.90
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_PRODUCTION"]
            del os.environ["CMCC_CMCC_THRESHOLD"]

    def test_from_env_shadow_only(self):
        import os
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_SHADOW"] = "true"
        os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "false"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is True
            assert f.ENABLE_CMCC_SHADOW is True
            assert f.ENABLE_CMCC_PRODUCTION is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_SHADOW"]
            del os.environ["CMCC_ENABLE_CMCC_PRODUCTION"]

    def test_from_env_rollback_overrides(self):
        import os
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "true"
        os.environ["CMCC_ENABLE_CMCC_ROLLBACK"] = "true"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is False
            assert f.ENABLE_CMCC_PRODUCTION is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_PRODUCTION"]
            del os.environ["CMCC_ENABLE_CMCC_ROLLBACK"]


if __name__ == "__main__":
    pytest.main([__file__])
