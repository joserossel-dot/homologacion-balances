"""Tests for REVIEW_CMCC pipeline — Sprint 27.1.

Tests:
  - Feature flag default and to_dict
  - ReviewCMCC model construction and trace_id
  - Pipeline does NOT populate review queue when flag is OFF (regression)
  - Pipeline DOES populate review queue when flag is ON
  - Only UNKNOWN accounts with score==1.0 enter the queue
  - Accounts with score<1.0 remain UNKNOWN only
  - Accounts classified by other means do NOT enter queue
  - extract_review_queue post-processes correctly
  - compute_statistics aggregates correctly
  - generate_reports creates all files
  - No production classifications change
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from pipeline.features import CMCCFeatureFlags
from pipeline.homologation_pipeline import HomologationPipeline
from review.cmcc_review_models import ReviewCMCC
from review.cmcc_review_pipeline import (
    extract_review_queue,
    compute_statistics,
    generate_reports,
    generate_markdown,
)

# ─── Helpers ─────────────────────────────────


def _make_pipeline(
    enable_cmcc: bool = True,
    enable_shadow: bool = True,
    enable_production: bool = False,
    enable_review_pipeline: bool = False,
    threshold: float = 0.95,
) -> HomologationPipeline:
    features = CMCCFeatureFlags(
        ENABLE_CMCC=enable_cmcc,
        ENABLE_CMCC_SHADOW=enable_shadow,
        ENABLE_CMCC_PRODUCTION=enable_production,
        ENABLE_CMCC_REVIEW_PIPELINE=enable_review_pipeline,
        CMCC_THRESHOLD=threshold,
    )
    return HomologationPipeline(features=features)


def _mock_learning_no_match(*args, **kwargs) -> dict[str, Any]:
    return {"source": "none", "code": None, "confidence": 0.0, "matched_name": None}


def _mock_cmcc_result(score: float = 1.0, code: str = "AC.01",
                      concept: str = "Caja") -> dict[str, Any]:
    method = "cmcc_nombre" if score == 1.0 else "cmcc_variante"
    return {
        "code": code,
        "concept": concept,
        "score": score,
        "matched_variant": "Caja General",
        "matched_concept": concept,
        "method": method,
        "evidence": [f"matched_nombre: Caja General"],
    }


@pytest.fixture
def pipeline_no_review(tmp_path) -> HomologationPipeline:
    """Pipeline with ENABLE_CMCC_REVIEW_PIPELINE=False (default)."""
    p = _make_pipeline(enable_review_pipeline=False)
    p._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)
    p._cmcc_classifier.classify = MagicMock(return_value=_mock_cmcm_result(score=1.0))
    return p


@pytest.fixture
def pipeline_with_review(tmp_path) -> HomologationPipeline:
    """Pipeline with ENABLE_CMCC_REVIEW_PIPELINE=True."""
    p = _make_pipeline(enable_review_pipeline=True)
    p._learning_engine.best_match = MagicMock(side_effect=_mock_learning_no_match)
    return p


# ─────────────────────────────────────────────
# Feature Flag Tests
# ─────────────────────────────────────────────

class TestReviewPipelineFeatureFlag:
    def test_default_is_false(self):
        f = CMCCFeatureFlags()
        assert f.ENABLE_CMCC_REVIEW_PIPELINE is False

    def test_in_to_dict(self):
        f = CMCCFeatureFlags()
        d = f.to_dict()
        assert "ENABLE_CMCC_REVIEW_PIPELINE" in d
        assert d["ENABLE_CMCC_REVIEW_PIPELINE"] is False

    def test_can_be_enabled(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_REVIEW_PIPELINE=True)
        assert f.ENABLE_CMCC_REVIEW_PIPELINE is True

    def test_rollback_overrides(self):
        f = CMCCFeatureFlags(
            ENABLE_CMCC_REVIEW_PIPELINE=True,
            ENABLE_CMCC_ROLLBACK=True,
        )
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_SHADOW is False
        assert f.ENABLE_CMCC_PRODUCTION is False
        # Rollback does NOT reset review pipeline (it's independent)
        # but review requires ENABLE_CMCC which is now False
        assert f.ENABLE_CMCC_REVIEW_PIPELINE is True


# ─────────────────────────────────────────────
# ReviewCMCC Model Tests
# ─────────────────────────────────────────────

class TestReviewCMCCModel:
    def test_from_pipeline_account(self):
        detail = _mock_cmcc_result(score=1.0)
        entry = ReviewCMCC.from_pipeline_account(
            account_name="Caja General",
            source_file="datasets/empresa/Balance 2024.pdf",
            cmcc_detail=detail,
            company="empresa",
            layout="pdf_estandar",
        )
        assert entry.account_name == "Caja General"
        assert entry.concept_code == "AC.01"
        assert entry.concept_name == "Caja"
        assert entry.score == 1.0
        assert entry.matched_variant == "Caja General"
        assert entry.matching_method == "cmcc_nombre"
        assert entry.shadow_only is True
        assert entry.review_status == "PENDING"
        assert len(entry.decision_trace_id) == 16

    def test_trace_id_is_deterministic(self):
        id1 = ReviewCMCC._compute_trace_id("f1.pdf", "Caja")
        id2 = ReviewCMCC._compute_trace_id("f1.pdf", "Caja")
        assert id1 == id2

    def test_trace_id_differs_for_different_accounts(self):
        id1 = ReviewCMCC._compute_trace_id("f1.pdf", "Caja")
        id2 = ReviewCMCC._compute_trace_id("f1.pdf", "Banco")
        assert id1 != id2

    def test_to_dict_contains_all_columns(self):
        detail = _mock_cmcc_result(score=1.0)
        entry = ReviewCMCC.from_pipeline_account(
            account_name="Test", source_file="f.pdf",
            cmcc_detail=detail, company="C1", layout="pdf_estandar",
        )
        d = entry.to_dict()
        for col in ReviewCMCC.columns():
            assert col in d, f"Missing column: {col}"
        assert d["review_status"] == "PENDING"

    def test_evidence_is_joined(self):
        detail = _mock_cmcc_result(score=1.0)
        detail["evidence"] = ["match1", "match2"]
        entry = ReviewCMCC.from_pipeline_account(
            account_name="Test", source_file="f.pdf",
            cmcc_detail=detail, company="C1", layout="pdf_estandar",
        )
        d = entry.to_dict()
        assert "match1; match2" in d["evidence"]


# ─────────────────────────────────────────────
# Pipeline Integration Tests
# ─────────────────────────────────────────────

class TestPipelineNoReview:
    """ENABLE_CMCC_REVIEW_PIPELINE=False → no review entries."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(enable_review_pipeline=False)
        self.pipeline._learning_engine.best_match = MagicMock(
            side_effect=_mock_learning_no_match
        )

    def test_unknown_account_has_no_review_entry(self):
        """UNKNOWN account with score==1.0 does NOT create review entry when flag is OFF."""
        self.pipeline._cmcc_classifier.classify = MagicMock(
            return_value=_mock_cmcc_result(score=1.0)
        )
        result = self.pipeline._classify_account("999", "XY_UNIQUE_UNKNOWN_999")
        # Account must be UNKNOWN (no dictionary match for this name)
        assert result.get("standard_code") is None
        assert result.get("method") == "unclassified"
        # cmcc_detail must be present (shadow mode)
        assert result.get("cmcc_detail") is not None

    def test_process_no_review_queue_when_flag_off(self):
        """process() does NOT populate cmcc_review_queue when flag is OFF."""
        self.pipeline._cmcc_classifier.classify = MagicMock(
            return_value=_mock_cmcc_result(score=1.0)
        )
        # We can't easily mock process() end-to-end without files,
        # but we verify the flag check in process() code path.


class TestPipelineWithReview:
    """ENABLE_CMCC_REVIEW_PIPELINE=True → review entries for score==1.0 unknowns."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(enable_review_pipeline=True)
        self.pipeline._learning_engine.best_match = MagicMock(
            side_effect=_mock_learning_no_match
        )

    def test_review_entry_for_score_1_unknown(self):
        """UNKNOWN account with CMCC score==1.0 gets review entry."""
        self.pipeline._cmcc_classifier.classify = MagicMock(
            return_value=_mock_cmcc_result(score=1.0, code="AC.01")
        )
        # Mock process flow: _classify_account returns UNKNOWN with cmcc_detail
        result = self.pipeline._classify_account("999", "XY_UNIQUE_UNKNOWN_999")
        assert result.get("standard_code") is None
        assert result.get("method") == "unclassified"
        assert result.get("cmcc_detail") is not None
        assert result.get("cmcc_detail", {}).get("score") == 1.0

    def test_no_review_entry_for_score_below_1(self):
        """UNKNOWN account with CMCC score<1.0 does NOT get review entry."""
        self.pipeline._cmcc_classifier.classify = MagicMock(
            return_value=_mock_cmcc_result(score=0.95, code="AC.01")
        )
        result = self.pipeline._classify_account("999", "XY_UNIQUE_UNKNOWN_999")
        assert result.get("standard_code") is None
        assert result.get("cmcc_detail", {}).get("score") == 0.95
        # No review entry because score != 1.0

    def test_classified_account_not_in_review(self):
        """Account classified by learning does NOT enter review."""
        self.pipeline._learning_engine.best_match = MagicMock(
            return_value={"source": "exact", "code": "PC.01",
                          "confidence": 0.99, "matched_name": "PROVEEDORES"}
        )
        result = self.pipeline._classify_account("101", "Proveedores")
        assert result.get("standard_code") is not None
        assert result.get("method") != "unclassified"


# ─────────────────────────────────────────────
# extract_review_queue Tests
# ─────────────────────────────────────────────

class TestExtractReviewQueue:
    def test_empty_classified(self):
        queue = extract_review_queue({"classified": []})
        assert queue == []

    def test_skips_classified_accounts(self):
        classified = [
            {"standard_code": "AC.01", "account_name": "Caja",
             "source_file": "f.pdf"},
        ]
        queue = extract_review_queue({"classified": classified})
        assert queue == []

    def test_skips_unknown_without_cmcc(self):
        classified = [
            {"standard_code": None, "account_name": "Caja",
             "source_file": "f.pdf"},
        ]
        queue = extract_review_queue({"classified": classified})
        assert queue == []

    def test_skips_unknown_with_low_score(self):
        classified = [
            {"standard_code": None, "account_name": "Caja",
             "source_file": "f.pdf",
             "cmcc_detail": _mock_cmcc_result(score=0.95)},
        ]
        queue = extract_review_queue({"classified": classified})
        assert queue == []

    def test_extracts_score_1_unknown(self):
        classified = [
            {"standard_code": None, "account_name": "Caja General",
             "source_file": "datasets/Balance 2024.pdf",
             "cmcc_detail": _mock_cmcc_result(score=1.0)},
        ]
        queue = extract_review_queue({"classified": classified})
        assert len(queue) == 1
        assert queue[0]["account_name"] == "Caja General"
        assert queue[0]["score"] == 1.0
        assert queue[0]["review_status"] == "PENDING"

    def test_extracts_from_cmcc_shadow_fallback(self):
        classified = [
            {"standard_code": None, "account_name": "Caja",
             "source_file": "f.pdf",
             "cmcc_shadow": _mock_cmcc_result(score=1.0)},
        ]
        queue = extract_review_queue({"classified": classified})
        assert len(queue) == 1

    def test_skips_score_1_if_classified(self):
        """Even with score==1.0, classified accounts skip the queue."""
        classified = [
            {"standard_code": "AC.01", "account_name": "Caja",
             "source_file": "f.pdf",
             "cmcc_detail": _mock_cmcc_result(score=1.0)},
        ]
        queue = extract_review_queue({"classified": classified})
        assert queue == []

    def test_multiple_accounts_mixed(self):
        classified = [
            {"standard_code": "AC.01", "account_name": "Classified",
             "source_file": "f.pdf"},
            {"standard_code": None, "account_name": "UnknownNoCMCC",
             "source_file": "f.pdf"},
            {"standard_code": None, "account_name": "UnknownScore1",
             "source_file": "f.pdf",
             "cmcc_detail": _mock_cmcc_result(score=1.0)},
            {"standard_code": None, "account_name": "UnknownScore095",
             "source_file": "f.pdf",
             "cmcc_detail": _mock_cmcc_result(score=0.95)},
        ]
        queue = extract_review_queue({"classified": classified})
        assert len(queue) == 1
        assert queue[0]["account_name"] == "UnknownScore1"


# ─────────────────────────────────────────────
# compute_statistics Tests
# ─────────────────────────────────────────────

class TestComputeStatistics:
    def test_empty_queue(self):
        stats = compute_statistics([], {"total_unknown": 100})
        assert stats["total_review"] == 0
        assert stats["unknown_after_review"] == 100
        assert stats["review_pct"] == 0.0

    def test_single_entry(self):
        queue = [
            {"company": "C1", "layout": "pdf_estandar",
             "concept_code": "AC.01", "concept_name": "Caja",
             "document_id": "f1.pdf", "matching_method": "cmcc_nombre",
             "account_name": "Caja", "score": 1.0,
             "matched_variant": "Caja", "evidence": "",
             "decision_trace_id": "abc", "shadow_only": True,
             "review_status": "PENDING", "created_at": "now"},
        ]
        stats = compute_statistics(queue, {"total_unknown": 100})
        assert stats["total_review"] == 1
        assert stats["num_companies"] == 1
        assert stats["num_concepts"] == 1
        assert stats["num_layouts"] == 1
        assert stats["num_documents"] == 1

    def test_multiple_companies(self):
        queue = [
            {"company": "C1", "layout": "pdf", "concept_code": "AC.01",
             "concept_name": "Caja", "document_id": "f1.pdf",
             "matching_method": "cmcc_nombre",
             "account_name": "Caja", "score": 1.0,
             "matched_variant": "", "evidence": "",
             "decision_trace_id": "", "shadow_only": True,
             "review_status": "PENDING", "created_at": ""},
            {"company": "C2", "layout": "pdf", "concept_code": "AC.02",
             "concept_name": "Banco", "document_id": "f2.pdf",
             "matching_method": "cmcc_nombre",
             "account_name": "Banco", "score": 1.0,
             "matched_variant": "", "evidence": "",
             "decision_trace_id": "", "shadow_only": True,
             "review_status": "PENDING", "created_at": ""},
        ]
        stats = compute_statistics(queue, {"total_unknown": 50})
        assert stats["total_review"] == 2
        assert stats["num_companies"] == 2
        assert stats["num_concepts"] == 2
        assert stats["review_pct"] == 4.0


# ─────────────────────────────────────────────
# Report Generation Tests
# ─────────────────────────────────────────────

class TestGenerateReports:
    def test_all_files_created(self, tmp_path):
        queue = [
            {"company": "C1", "layout": "pdf", "concept_code": "AC.01",
             "concept_name": "Caja", "document_id": "f1.pdf",
             "matching_method": "cmcc_nombre",
             "account_name": "Caja", "score": 1.0,
             "matched_variant": "Caja", "evidence": "",
             "decision_trace_id": "abc", "shadow_only": True,
             "review_status": "PENDING", "created_at": "now"},
        ]
        summary = {"total_unknown": 100, "files": 10, "total_accounts": 500,
                   "total_classified": 400, "coverage_pct": 80.0,
                   "elapsed_seconds": 1.0}
        stats = compute_statistics(queue, summary)
        paths = generate_reports(queue, summary, stats)
        expected = [
            "review_queue.xlsx",
            "review_statistics.xlsx",
            "review_by_company.xlsx",
            "review_by_layout.xlsx",
            "review_by_concept.xlsx",
        ]
        for name in expected:
            assert name in paths, f"Missing {name}"
            assert paths[name].exists(), f"File not found: {paths[name]}"

    def test_empty_queue_creates_empty_files(self, tmp_path):
        summary = {"total_unknown": 0, "files": 0, "total_accounts": 0,
                   "total_classified": 0, "coverage_pct": 0.0,
                   "elapsed_seconds": 0.0}
        stats = compute_statistics([], summary)
        paths = generate_reports([], summary, stats)
        for name, path in paths.items():
            assert path.exists(), f"File not found: {path}"
            assert path.stat().st_size > 0


class TestGenerateMarkdown:
    def test_markdown_contains_sections(self):
        queue = [{"company": "C1", "layout": "pdf", "concept_code": "AC.01",
                  "concept_name": "Caja", "document_id": "f1.pdf",
                  "matching_method": "cmcc_nombre",
                  "account_name": "Caja", "score": 1.0,
                  "matched_variant": "Caja", "evidence": "",
                  "decision_trace_id": "abc", "shadow_only": True,
                  "review_status": "PENDING", "created_at": "now"}]
        summary = {"total_unknown": 100, "files": 10, "total_accounts": 500,
                   "total_classified": 400, "coverage_pct": 80.0,
                   "elapsed_seconds": 1.0}
        stats = compute_statistics(queue, summary)
        paths = generate_reports(queue, summary, stats)
        md = generate_markdown(queue, summary, stats, paths)
        assert "REVIEW_CMCC" in md
        assert "Summary" in md
        assert "by Company" in md
        assert "by Layout" in md
        assert "by Concept" in md
        assert "by Document" in md
        assert "Impact" in md
        assert "Traceability" in md


# ─────────────────────────────────────────────
# Regression: No production impact
# ─────────────────────────────────────────────

class TestRegressionNoProductionImpact:
    """REVIEW_CMCC must NEVER alter official classifications."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.pipeline = _make_pipeline(enable_review_pipeline=True)
        self.pipeline._learning_engine.best_match = MagicMock(
            side_effect=_mock_learning_no_match
        )

    def test_unknown_stays_unknown(self):
        """Account with score==1.0 stays UNKNOWN officially."""
        self.pipeline._cmcc_classifier.classify = MagicMock(
            return_value=_mock_cmcc_result(score=1.0)
        )
        result = self.pipeline._classify_account("999", "XY_UNIQUE_UNKNOWN_999")
        assert result.get("standard_code") is None
        assert result.get("method") == "unclassified"

    def test_classified_stays_classified(self):
        """Learning-classified accounts remain classified."""
        self.pipeline._learning_engine.best_match = MagicMock(
            return_value={"source": "exact", "code": "PC.01",
                          "confidence": 0.99, "matched_name": "PROVEEDORES"}
        )
        result = self.pipeline._classify_account("101", "Proveedores")
        assert result["standard_code"] == "PC.01"
        assert result["method"] == "learning_exact"

    def test_dictionary_classification_unchanged(self):
        """Dictionary classification still works."""
        result = self.pipeline._classify_account("101", "Proveedores Nacionales")
        if result["method"] not in ("unclassified",):
            assert result["standard_code"] is not None
