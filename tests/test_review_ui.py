from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from review_ui.review_models import ReviewDecision, DecisionStatus
from review_ui.review_repository import ReviewRepository
from review_ui.review_session import ReviewSession
from review_ui.review_actions import approve, reject, reassign, undo
from review_ui.review_statistics import compute_statistics
from review_ui.review_reports import generate_reports
from review_ui.review_reports import REPORTS_DIR


SAMPLE_ENTRY = {
    "account_name": "Banco Bci",
    "document_id": "Balance 2015.pdf",
    "company": "TestCo",
    "layout": "pdf_estandar",
    "concept_code": "AC.01",
    "concept_name": "Caja y Bancos",
    "score": 1,
    "matched_variant": "banco bci",
    "matching_method": "cmcc_variante",
    "evidence": "matched_variante: banco bci",
    "decision_trace_id": "abc123def456",
    "shadow_only": True,
    "review_status": "PENDING",
    "created_at": "2026-07-10T00:00:00+00:00",
}


# ═══════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_reviews.db"


@pytest.fixture
def repo(tmp_db: Path) -> ReviewRepository:
    return ReviewRepository(str(tmp_db))


@pytest.fixture
def sample_decision() -> ReviewDecision:
    return ReviewDecision.from_queue_entry(SAMPLE_ENTRY)


@pytest.fixture
def session(repo: ReviewRepository) -> ReviewSession:
    return ReviewSession(repo)


@pytest.fixture
def temp_queue(tmp_path: Path) -> Path:
    path = tmp_path / "test_queue.xlsx"
    df = pd.DataFrame([SAMPLE_ENTRY, {**SAMPLE_ENTRY, "matched_variant": "caja chica",
                                       "account_name": "Caja Chica",
                                       "decision_trace_id": "xyz789"}])
    df.to_excel(path, index=False)
    return path


# ═══════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════

class TestReviewDecisionModel:
    def test_from_queue_entry(self, sample_decision: ReviewDecision):
        assert sample_decision.variant == "banco bci"
        assert sample_decision.current_concept == "AC.01"
        assert sample_decision.status == DecisionStatus.PENDING
        assert len(sample_decision.review_id) == 16
        assert sample_decision.review_id == sample_decision.review_id  # deterministic

    def test_generate_review_id_deterministic(self):
        id1 = ReviewDecision.generate_review_id("abc", "banco")
        id2 = ReviewDecision.generate_review_id("abc", "banco")
        assert id1 == id2

    def test_generate_review_id_differs(self):
        id1 = ReviewDecision.generate_review_id("abc", "banco")
        id2 = ReviewDecision.generate_review_id("abc", "caja")
        assert id1 != id2

    def test_to_dict_contains_all_columns(self, sample_decision: ReviewDecision):
        d = sample_decision.to_dict()
        for col in ReviewDecision.columns():
            assert col in d

    def test_status_enum_values(self):
        assert DecisionStatus.PENDING.value == "PENDING"
        assert DecisionStatus.APPROVED.value == "APPROVED"
        assert DecisionStatus.REJECTED.value == "REJECTED"
        assert DecisionStatus.REASSIGNED.value == "REASSIGNED"

    def test_default_confidence(self, sample_decision: ReviewDecision):
        assert sample_decision.confidence == 1.0

    def test_default_reviewer_empty(self, sample_decision: ReviewDecision):
        assert sample_decision.reviewer == ""

    def test_default_comments_empty(self, sample_decision: ReviewDecision):
        assert sample_decision.comments == ""

    def test_default_reason_empty(self, sample_decision: ReviewDecision):
        assert sample_decision.reason == ""

    def test_columns_list(self):
        cols = ReviewDecision.columns()
        assert "review_id" in cols
        assert "trace_id" in cols
        assert "status" in cols
        assert "confidence" in cols
        assert len(cols) == 17


# ═══════════════════════════════════════════
# Repository Tests
# ═══════════════════════════════════════════

class TestReviewRepository:
    def test_save_and_get(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        loaded = repo.get(sample_decision.review_id)
        assert loaded is not None
        assert loaded.variant == sample_decision.variant
        assert loaded.status == DecisionStatus.PENDING

    def test_get_nonexistent(self, repo: ReviewRepository):
        assert repo.get("nonexistent") is None

    def test_exists(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        assert not repo.exists(sample_decision.review_id)
        repo.save(sample_decision)
        assert repo.exists(sample_decision.review_id)

    def test_load_pending(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        pending = repo.load_pending()
        assert len(pending) == 1

    def test_load_by_status(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        all_decisions = repo.load_by_status()
        assert len(all_decisions) == 1

    def test_count_pending(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        assert repo.count_pending() == 0
        repo.save(sample_decision)
        assert repo.count_pending() == 1

    def test_count_by_status_empty(self, repo: ReviewRepository):
        counts = repo.count_by_status()
        assert counts == {}

    def test_count_by_status(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        counts = repo.count_by_status()
        assert counts.get("PENDING") == 1

    def test_delete(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        assert repo.exists(sample_decision.review_id)
        repo.delete(sample_decision.review_id)
        assert not repo.exists(sample_decision.review_id)

    def test_clear(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        repo.clear()
        assert repo.count_pending() == 0

    def test_update_replaces(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        sample_decision.status = DecisionStatus.APPROVED
        repo.save(sample_decision)
        loaded = repo.get(sample_decision.review_id)
        assert loaded.status == DecisionStatus.APPROVED

    def test_all_decisions(self, repo: ReviewRepository):
        d1 = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        d2 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "caja",
                                               "decision_trace_id": "diff"})
        repo.save(d1)
        repo.save(d2)
        assert len(repo.all_decisions()) == 2

    def test_load_approved_rejected_reassigned(self, repo: ReviewRepository):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        assert len(repo.load_approved()) == 0
        assert len(repo.load_rejected()) == 0
        assert len(repo.load_reassigned()) == 0

    def test_initialization_creates_db(self, tmp_path: Path):
        db_path = tmp_path / "new_db.db"
        repo = ReviewRepository(str(db_path))
        assert db_path.exists()


# ═══════════════════════════════════════════
# Session Tests
# ═══════════════════════════════════════════

class TestReviewSession:
    def test_load_pending_from_queue(self, session: ReviewSession, temp_queue: Path):
        decisions = session.load_pending(queue_path=str(temp_queue))
        assert len(decisions) == 2

    def test_load_pending_no_duplicates(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        new = session.load_pending(queue_path=str(temp_queue))
        assert len(new) == 0

    def test_load_pending_force_reload(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        new = session.load_pending(queue_path=str(temp_queue), force=True)
        assert len(new) == 2

    def test_load_pending_missing_queue(self, session: ReviewSession):
        decisions = session.load_pending(queue_path="/tmp/nonexistent.xlsx")
        assert decisions == []

    def test_get_pending(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        pending = session.get_pending()
        assert len(pending) == 2

    def test_get_pending_with_limit(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        pending = session.get_pending(limit=1)
        assert len(pending) == 1

    def test_get_by_status(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        pending = session.get_by_status(DecisionStatus.PENDING)
        assert len(pending) == 2

    def test_get_decision(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        pending = session.get_pending(limit=1)
        d = session.get_decision(pending[0].review_id)
        assert d is not None
        assert d.variant == pending[0].variant

    def test_summary(self, session: ReviewSession, temp_queue: Path):
        session.load_pending(queue_path=str(temp_queue))
        s = session.summary()
        assert s["total_loaded"] == 2
        assert s["pending"] == 2
        assert s["approved"] == 0
        assert s["rejected"] == 0
        assert s["reassigned"] == 0


# ═══════════════════════════════════════════
# Action Tests
# ═══════════════════════════════════════════

class TestReviewActions:
    def test_approve(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        result = approve(sample_decision, repo, reviewer="juan", reason="correcto")
        assert result.status == DecisionStatus.APPROVED
        assert result.reviewer == "juan"
        assert repo.count_by_status().get("APPROVED") == 1

    def test_reject(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        result = reject(sample_decision, repo, reviewer="juan", reason="incorrecto")
        assert result.status == DecisionStatus.REJECTED
        assert result.reviewer == "juan"
        assert repo.count_by_status().get("REJECTED") == 1

    def test_reassign(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        result = reassign(sample_decision, repo, new_concept="AC.02",
                          new_concept_name="Valores Negociables",
                          reviewer="juan", reason="mejor ajuste")
        assert result.status == DecisionStatus.REASSIGNED
        assert result.suggested_concept == "AC.02"
        assert repo.count_by_status().get("REASSIGNED") == 1

    def test_undo_approved(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        approve(sample_decision, repo, reviewer="test")
        result = undo(sample_decision, repo)
        assert result.status == DecisionStatus.PENDING
        assert repo.count_by_status().get("PENDING") == 1

    def test_undo_rejected(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        reject(sample_decision, repo, reviewer="test", reason="wrong")
        result = undo(sample_decision, repo)
        assert result.status == DecisionStatus.PENDING

    def test_undo_reassigned(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        reassign(sample_decision, repo, new_concept="AC.02", new_concept_name="Valores",
                 reviewer="test", reason="reassign")
        result = undo(sample_decision, repo)
        assert result.status == DecisionStatus.PENDING
        assert result.suggested_concept == result.current_concept

    def test_approve_non_pending_raises(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        approve(sample_decision, repo, reviewer="test")
        with pytest.raises(ValueError, match="Cannot approve"):
            approve(sample_decision, repo, reviewer="test2")

    def test_reject_non_pending_raises(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        approve(sample_decision, repo, reviewer="test")
        with pytest.raises(ValueError, match="Cannot reject"):
            reject(sample_decision, repo, reviewer="test2")

    def test_reassign_non_pending_raises(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        approve(sample_decision, repo, reviewer="test")
        with pytest.raises(ValueError, match="Cannot reassign"):
            reassign(sample_decision, repo, new_concept="AC.02", new_concept_name="")

    def test_undo_pending_raises(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        with pytest.raises(ValueError, match="Cannot undo"):
            undo(sample_decision, repo)

    def test_approve_stores_comments(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        result = approve(sample_decision, repo, reviewer="test", reason="ok", comments="Looks good")
        assert result.comments == "Looks good"

    def test_reject_stores_comments(self, repo: ReviewRepository, sample_decision: ReviewDecision):
        repo.save(sample_decision)
        result = reject(sample_decision, repo, reviewer="test", reason="bad", comments="Not valid")
        assert result.comments == "Not valid"


# ═══════════════════════════════════════════
# Statistics Tests
# ═══════════════════════════════════════════

class TestReviewStatistics:
    def test_empty_decisions(self):
        stats = compute_statistics([])
        assert stats["total_decisions"] == 0
        assert stats["approval_rate"] == 0.0

    def test_single_approved(self, sample_decision: ReviewDecision):
        sample_decision.status = DecisionStatus.APPROVED
        stats = compute_statistics([sample_decision])
        assert stats["total_decisions"] == 1
        assert stats["approved"] == 1
        assert stats["approval_rate"] == 100.0

    def test_mixed_statuses(self, repo: ReviewRepository):
        d1 = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        d2 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "caja",
                                               "decision_trace_id": "d2"})
        d3 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "banco",
                                               "decision_trace_id": "d3"})
        d1.status = DecisionStatus.APPROVED
        d2.status = DecisionStatus.REJECTED
        d3.status = DecisionStatus.REASSIGNED
        stats = compute_statistics([d1, d2, d3])
        assert stats["total_decisions"] == 3
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["reassigned"] == 1
        assert stats["unique_variants_reviewed"] == 3

    def test_top_concepts(self, sample_decision: ReviewDecision):
        d2 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "caja",
                                               "decision_trace_id": "d2",
                                               "concept_code": "ER.01"})
        d2.status = DecisionStatus.APPROVED
        stats = compute_statistics([sample_decision, sample_decision, d2])
        assert stats["unique_concepts_impacted"] == 2

    def test_avg_confidence(self):
        d1 = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        d2 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "caja",
                                               "decision_trace_id": "d2"})
        stats = compute_statistics([d1, d2])
        assert stats["avg_confidence"] == 1.0


# ═══════════════════════════════════════════
# Reports Tests
# ═══════════════════════════════════════════

class TestReviewReports:
    def test_all_files_created(self, repo: ReviewRepository, tmp_path: Path):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        decisions = repo.all_decisions()
        stats = compute_statistics(decisions)
        paths = generate_reports(decisions, stats, output_dir=str(tmp_path / "reports"))
        expected = ["review_queue.xlsx", "approved.xlsx", "rejected.xlsx",
                     "reassigned.xlsx", "review_statistics.xlsx",
                     "review_summary.md", "review.json"]
        for name in expected:
            assert name in paths, f"Missing {name}"

    def test_empty_queue_creates_empty_files(self, tmp_path: Path):
        stats = compute_statistics([])
        paths = generate_reports([], stats, output_dir=str(tmp_path / "empty"))
        assert paths["review_queue.xlsx"].exists()
        content = paths["review_queue.xlsx"].stat().st_size
        assert content > 0

    def test_markdown_contains_sections(self, repo: ReviewRepository, tmp_path: Path):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        decisions = repo.all_decisions()
        stats = compute_statistics(decisions)
        paths = generate_reports(decisions, stats, output_dir=str(tmp_path / "md"))
        md = paths["review_summary.md"].read_text()
        assert "Summary" in md
        assert "Concept Distribution" in md

    def test_json_output(self, repo: ReviewRepository, tmp_path: Path):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        decisions = repo.all_decisions()
        stats = compute_statistics(decisions)
        paths = generate_reports(decisions, stats, output_dir=str(tmp_path / "json"))
        data = json.loads(paths["review.json"].read_text())
        assert "total_decisions" in data
        assert "decisions" in data

    def test_reports_respect_status_filter(self, repo: ReviewRepository, tmp_path: Path):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        approve(d, repo, reviewer="test", reason="ok")
        decisions = repo.all_decisions()
        stats = compute_statistics(decisions)
        paths = generate_reports(decisions, stats, output_dir=str(tmp_path / "filter"))
        approved_df = pd.read_excel(paths["approved.xlsx"])
        assert len(approved_df) == 1
        rejected_df = pd.read_excel(paths["rejected.xlsx"])
        assert len(rejected_df) == 0


# ═══════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════

class TestIntegration:
    def test_full_workflow(self, repo: ReviewRepository):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        assert repo.count_pending() == 1
        approve(d, repo, reviewer="juan", reason="valid")
        assert repo.count_by_status().get("APPROVED") == 1
        assert repo.count_by_status().get("PENDING", 0) == 0
        undo(d, repo)
        assert repo.count_pending() == 1
        assert repo.count_by_status().get("APPROVED", 0) == 0

    def test_approve_reject_cycle(self, repo: ReviewRepository):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        approve(d, repo, reviewer="a", reason="ok")
        undo(d, repo)
        reject(d, repo, reviewer="b", reason="bad")
        assert d.status == DecisionStatus.REJECTED
        undo(d, repo)
        assert d.status == DecisionStatus.PENDING

    def test_approve_reassign_cycle(self, repo: ReviewRepository):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        approve(d, repo, reviewer="a", reason="ok")
        undo(d, repo)
        reassign(d, repo, new_concept="ER.01", new_concept_name="Ventas",
                 reviewer="b", reason="reassign")
        assert d.suggested_concept == "ER.01"
        undo(d, repo)
        assert d.suggested_concept == d.current_concept

    def test_statistics_after_actions(self, repo: ReviewRepository):
        d1 = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        d2 = ReviewDecision.from_queue_entry({**SAMPLE_ENTRY, "matched_variant": "caja",
                                               "decision_trace_id": "d2"})
        repo.save(d1); repo.save(d2)
        approve(d1, repo, reviewer="a", reason="ok")
        reject(d2, repo, reviewer="a", reason="bad")
        stats = compute_statistics(repo.all_decisions())
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["approval_rate"] == 50.0
        assert stats["rejection_rate"] == 50.0

    def test_markdown_reflects_stats(self, repo: ReviewRepository, tmp_path: Path):
        d = ReviewDecision.from_queue_entry(SAMPLE_ENTRY)
        repo.save(d)
        approve(d, repo, reviewer="maria", reason="correcto")
        decisions = repo.all_decisions()
        stats = compute_statistics(decisions)
        paths = generate_reports(decisions, stats, output_dir=str(tmp_path / "integ"))
        md = paths["review_summary.md"].read_text()
        assert "maria" in md
        assert "100.0%" in md

    def test_default_reports_dir_constant(self):
        assert str(REPORTS_DIR) == "reports/human_review"
