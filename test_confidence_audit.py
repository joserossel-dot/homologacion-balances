"""
Comprehensive tests for:
- confidence/confidence_engine.py
- confidence/confidence_result.py
- audit/classification_history.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from confidence.confidence_engine import ConfidenceEngine
from confidence.confidence_result import ConfidenceResult, EvidenceItem
from audit.classification_history import ClassificationHistoryRecorder

engine = ConfidenceEngine()


# ═══════════════════════════════════════════
# ConfidenceResult
# ═══════════════════════════════════════════

def test_confidence_result_defaults():
    r = ConfidenceResult()
    assert r.standard_code is None
    assert r.confidence == 0.0
    assert r.review_required is True
    assert r.method == ""
    assert r.evidence == []
    assert r.learning_hits == 0
    assert r.conflicts == 0


def test_confidence_result_to_dict():
    ev = EvidenceItem(source="test", detail="test detail", confidence=0.9)
    r = ConfidenceResult(
        standard_code="AC.01",
        confidence=0.95,
        review_required=False,
        method="learning_exact",
        evidence=[ev],
        learning_hits=1,
        conflicts=0,
    )
    d = r.to_dict()
    assert d["standard_code"] == "AC.01"
    assert d["confidence"] == 0.95
    assert d["review_required"] is False
    assert d["method"] == "learning_exact"
    assert d["learning_hits"] == 1
    assert d["conflicts"] == 0
    assert len(d["evidence"]) == 1
    assert d["evidence"][0]["source"] == "test"
    assert d["evidence"][0]["confidence"] == 0.9


def test_evidence_item_to_dict():
    ev = EvidenceItem(source="code_classifier", detail="Clasificación por código", confidence=0.97)
    d = ev.to_dict()
    assert d["source"] == "code_classifier"
    assert d["detail"] == "Clasificación por código"
    assert d["confidence"] == 0.97


# ═══════════════════════════════════════════
# ConfidenceEngine — review thresholds
# ═══════════════════════════════════════════

def test_confidence_ge_095_no_review():
    r = engine.evaluate("AC.01", "code", 0.95)
    assert r.review_required is False


def test_confidence_097_code_no_review():
    r = engine.evaluate("AC.01", "code", 0.97)
    assert r.review_required is False


def test_confidence_085_optional_review():
    r = engine.evaluate("AC.01", "code", 0.85)
    assert r.review_required is False  # >= 0.85 → optional


def test_confidence_084_mandatory_review():
    r = engine.evaluate("AC.01", "code", 0.84)
    assert r.review_required is True


def test_confidence_000_mandatory_review():
    r = engine.evaluate(None, "unclassified", 0.0)
    assert r.review_required is True
    assert r.standard_code is None


def test_movement_only_always_review():
    r = engine.evaluate(None, "movement_only", 0.0)
    assert r.review_required is True


# ═══════════════════════════════════════════
# ConfidenceEngine — learning hits
# ═══════════════════════════════════════════

def test_learning_exact_no_review():
    r = engine.evaluate("AC.01", "learning_exact", 0.98, learning_hits=1)
    assert r.review_required is False
    assert r.learning_hits == 1
    assert r.evidence[0].source == "learning_engine"


def test_learning_fuzzy_review_optional():
    r = engine.evaluate("AC.01", "learning_fuzzy", 0.92, learning_hits=1)
    assert r.review_required is False
    assert r.learning_hits == 1


def test_learning_hits_multiples():
    r = engine.evaluate("AC.01", "learning_exact", 0.98, learning_hits=3)
    assert r.learning_hits == 3
    assert "3 hit(s)" in r.evidence[0].detail


# ═══════════════════════════════════════════
# ConfidenceEngine — evidence tracking
# ═══════════════════════════════════════════

def test_evidence_method_code():
    r = engine.evaluate("AC.01", "code", 0.97)
    sources = {e.source for e in r.evidence}
    assert "code_classifier" in sources


def test_evidence_method_dictionary_exact():
    r = engine.evaluate("ER.01", "dictionary_exact", 0.98)
    sources = {e.source for e in r.evidence}
    assert "dictionary" in sources


def test_evidence_method_dictionary_fuzzy():
    r = engine.evaluate("ER.01", "dictionary_fuzzy", 0.88)
    sources = {e.source for e in r.evidence}
    assert "dictionary" in sources


def test_evidence_method_unclassified():
    r = engine.evaluate(None, "unclassified", 0.0)
    sources = {e.source for e in r.evidence}
    assert "fallback" in sources


def test_evidence_method_movement_only():
    r = engine.evaluate(None, "movement_only", 0.0)
    sources = {e.source for e in r.evidence}
    assert "filter" in sources


def test_evidence_learning_suppresses_method_evidence():
    r = engine.evaluate("AC.01", "code", 0.97, learning_hits=1)
    sources = {e.source for e in r.evidence}
    assert "learning_engine" in sources
    assert "code_classifier" not in sources  # suppressed by learning hit


# ═══════════════════════════════════════════
# ConfidenceEngine — special rules
# ═══════════════════════════════════════════

def test_special_rule_evidence():
    r = engine.evaluate("PC.02", "code+regla_especial", 0.97, has_special_rule=True)
    assert r.review_required is False
    sources = {e.source for e in r.evidence}
    assert "special_rule" in sources


def test_special_rule_with_conflict():
    r = engine.evaluate("PC.02", "code+regla_especial", 0.97,
                        has_special_rule=True, conflicts=1)
    assert r.conflicts == 1
    assert r.confidence == round(0.97 * 0.85, 4)  # 0.8245
    assert r.review_required is True
    sources = {e.source for e in r.evidence}
    assert "special_rule" in sources
    assert "conflict" in sources


# ═══════════════════════════════════════════
# ConfidenceEngine — conflict penalty
# ═══════════════════════════════════════════

def test_conflict_penalty_drops_below_095():
    r = engine.evaluate("AC.01", "code", 0.97, conflicts=2)
    expected = round(0.97 * 0.85, 4)
    assert r.confidence == expected
    assert r.review_required is True  # 0.8245 < 0.85


def test_conflict_penalty_stays_above_optional():
    r = engine.evaluate("AC.01", "code", 0.95, conflicts=1)
    expected = round(0.95 * 0.85, 4)  # 0.8075
    assert r.confidence == expected
    assert r.review_required is True  # 0.8075 < 0.85


def test_no_conflict_no_penalty():
    r = engine.evaluate("AC.01", "code", 0.97)
    assert r.confidence == 0.97
    assert r.conflicts == 0


# ═══════════════════════════════════════════
# ConfidenceEngine — merge from dict
# ═══════════════════════════════════════════

def test_merge_from_classification_dict():
    classification = {"standard_code": "ER.01", "method": "dictionary_exact", "confidence": 0.98}
    r = engine.merge(classification, learning_hits=0, has_special_rule=False, conflicts=0)
    assert r.standard_code == "ER.01"
    assert r.confidence == 0.98
    assert r.review_required is False
    assert r.method == "dictionary_exact"


def test_merge_with_learning_hits():
    classification = {"standard_code": "ER.01", "method": "learning_exact", "confidence": 0.98}
    r = engine.merge(classification, learning_hits=1)
    assert r.learning_hits == 1
    assert r.review_required is False


def test_merge_with_conflicts():
    classification = {"standard_code": "ER.01", "method": "code", "confidence": 0.97}
    r = engine.merge(classification, conflicts=1)
    assert r.conflicts == 1
    assert r.confidence < 0.97


# ═══════════════════════════════════════════
# ConfidenceEngine — edge cases
# ═══════════════════════════════════════════

def test_confidence_one():
    r = engine.evaluate("AC.01", "learning_exact", 1.0, learning_hits=1)
    assert r.confidence == 1.0
    assert r.review_required is False


def test_confidence_zero():
    r = engine.evaluate(None, "unclassified", 0.0)
    assert r.confidence == 0.0
    assert r.review_required is True


def test_empty_method():
    r = engine.evaluate("AC.01", "", 0.5)
    assert r.method == ""
    assert r.review_required is True  # 0.5 < 0.85


def test_method_with_plus():
    r = engine.evaluate("PC.02", "code+regla_especial", 0.97)
    assert r.method == "code+regla_especial"
    sources = {e.source for e in r.evidence}
    assert "code_classifier" in sources


def test_json_serializable():
    r = engine.evaluate("AC.01", "code", 0.97, conflicts=1)
    dumped = json.dumps(r.to_dict())
    loaded = json.loads(dumped)
    assert loaded["standard_code"] == "AC.01"
    assert loaded["confidence"] == round(0.97 * 0.85, 4)
    assert loaded["review_required"] is True
    assert loaded["learning_hits"] == 0
    assert loaded["conflicts"] == 1
    assert len(loaded["evidence"]) == 2  # code_classifier + conflict


# ═══════════════════════════════════════════
# ClassificationHistoryRecorder
# ═══════════════════════════════════════════

def test_recorder_creates_db():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        assert db.exists()
        # Verify table exists
        tables = rec.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert any(r["name"] == "classification_history" for r in tables)
        rec.close()


def test_record_inserts_row():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rid = rec.record(
            archivo="balance_2024.pdf",
            cuenta="110101",
            codigo_original="1101-01",
            codigo_homologado="AC.01",
            metodo="code",
            confianza=0.97,
            tiempo=0.023,
            usuario="test_user",
        )
        assert rid > 0
        rows = rec.query(limit=10)
        assert len(rows) == 1
        assert rows[0]["archivo"] == "balance_2024.pdf"
        assert rows[0]["codigo_homologado"] == "AC.01"
        assert rows[0]["confianza"] == 0.97
        assert rows[0]["corregida"] == 0
        rec.close()


def test_record_with_corregida():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rid = rec.record(
            archivo="balance_2024.pdf",
            cuenta="110101",
            codigo_original="1101-01",
            codigo_homologado="AC.01",
            metodo="dictionary_fuzzy",
            confianza=0.88,
            corregida=True,
        )
        rows = rec.query()
        assert rows[0]["corregida"] == 1
        rec.close()


def test_record_without_codigo_homologado():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rid = rec.record(
            archivo="balance_2024.pdf",
            cuenta="999999",
            codigo_original="9999-99",
            metodo="unclassified",
            confianza=0.0,
        )
        rows = rec.query()
        assert rows[0]["codigo_homologado"] == ""
        rec.close()


def test_record_with_explicit_fecha():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rid = rec.record(
            archivo="test.pdf",
            cuenta="101",
            codigo_original="101",
            codigo_homologado="AC.01",
            metodo="code",
            confianza=0.97,
            fecha="2026-07-06T10:00:00+00:00",
        )
        rows = rec.query()
        assert rows[0]["fecha"] == "2026-07-06T10:00:00+00:00"
        rec.close()


def test_mark_corregida():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rid = rec.record(
            archivo="test.pdf",
            cuenta="101",
            codigo_original="101",
            codigo_homologado="AC.01",
            metodo="code",
            confianza=0.97,
        )
        rec.mark_corregida(rid, True)
        rows = rec.query()
        assert rows[0]["corregida"] == 1
        rec.mark_corregida(rid, False)
        rows = rec.query()
        assert rows[0]["corregida"] == 0
        rec.close()


def test_query_filter_archivo():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", metodo="code", confianza=0.9)
        rec.record(archivo="b.pdf", cuenta="2", codigo_original="2", metodo="code", confianza=0.9)
        rec.record(archivo="a.pdf", cuenta="3", codigo_original="3", metodo="code", confianza=0.9)
        rows = rec.query(archivo="a.pdf")
        assert len(rows) == 2
        rec.close()


def test_query_filter_codigo_homologado():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", codigo_homologado="AC.01", metodo="code", confianza=0.9)
        rec.record(archivo="a.pdf", cuenta="2", codigo_original="2", codigo_homologado="PC.02", metodo="code", confianza=0.9)
        rows = rec.query(codigo_homologado="AC.01")
        assert len(rows) == 1
        assert rows[0]["codigo_homologado"] == "AC.01"
        rec.close()


def test_query_filter_corregida():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", metodo="code", confianza=0.9, corregida=False)
        rec.record(archivo="a.pdf", cuenta="2", codigo_original="2", metodo="code", confianza=0.9, corregida=True)
        rows = rec.query(corregida=True)
        assert len(rows) == 1
        rec.close()


def test_query_filter_metodo():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", metodo="code", confianza=0.9)
        rec.record(archivo="a.pdf", cuenta="2", codigo_original="2", metodo="dictionary_exact", confianza=0.98)
        rows = rec.query(metodo="code")
        assert len(rows) == 1
        rec.close()


def test_query_limit_offset():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        for i in range(10):
            rec.record(archivo="a.pdf", cuenta=str(i), codigo_original=str(i), metodo="code", confianza=0.9)
        rows = rec.query(limit=3, offset=0)
        assert len(rows) == 3
        rows_page2 = rec.query(limit=3, offset=3)
        assert len(rows_page2) == 3
        rec.close()


def test_statistics():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", metodo="code", confianza=0.97)
        rec.record(archivo="a.pdf", cuenta="2", codigo_original="2", metodo="code", confianza=0.95, corregida=True)
        rec.record(archivo="a.pdf", cuenta="3", codigo_original="3", metodo="dictionary_fuzzy", confianza=0.88, corregida=True)
        stats = rec.statistics()
        assert stats["total"] == 3
        assert stats["corregidas"] == 2
        assert stats["tasa_correccion"] == round(2 / 3, 4)
        assert stats["confianza_promedio"] == round((0.97 + 0.95 + 0.88) / 3, 4)
        assert stats["metodos"]["code"] == 2
        assert stats["metodos"]["dictionary_fuzzy"] == 1
        rec.close()


def test_statistics_empty():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        stats = rec.statistics()
        assert stats["total"] == 0
        assert stats["corregidas"] == 0
        assert stats["tasa_correccion"] == 0.0
        assert stats["confianza_promedio"] == 0.0
        assert stats["metodos"] == {}
        rec.close()


def test_count():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_history.db"
        rec = ClassificationHistoryRecorder(db)
        assert rec.count() == 0
        rec.record(archivo="a.pdf", cuenta="1", codigo_original="1", metodo="code", confianza=0.9)
        assert rec.count() == 1
        rec.record(archivo="b.pdf", cuenta="2", codigo_original="2", metodo="code", confianza=0.9)
        assert rec.count() == 2
        assert rec.count(archivo="a.pdf") == 1
        rec.close()


# ═══════════════════════════════════════════
# Integration: ConfidenceEngine → dict → JSON
# ═══════════════════════════════════════════

def test_full_confidence_result_json():
    """Simulate the complete output contract for a single classification."""
    r = engine.evaluate("AC.01", "code", 0.97)
    d = r.to_dict()
    output = json.dumps(d, indent=2)
    # all required top-level keys present
    for key in ("standard_code", "confidence", "review_required", "method", "evidence", "learning_hits", "conflicts"):
        assert key in d, f"Missing key: {key}"
    assert isinstance(output, str)
    assert '"standard_code": "AC.01"' in output


def test_audit_then_confidence_consistent():
    """Verify that confidence values stored in audit match the engine output."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test_integration.db"
        rec = ClassificationHistoryRecorder(db)

        r1 = engine.evaluate("AC.01", "dictionary_exact", 0.98)
        rec.record(
            archivo="integ.pdf",
            cuenta="101",
            codigo_original="101",
            codigo_homologado=r1.standard_code,
            metodo=r1.method,
            confianza=r1.confidence,
        )

        r2 = engine.evaluate("PC.02", "dictionary_fuzzy", 0.88, conflicts=1)
        rec.record(
            archivo="integ.pdf",
            cuenta="201",
            codigo_original="201",
            codigo_homologado=r2.standard_code,
            metodo=r2.method,
            confianza=r2.confidence,
        )

        rows = rec.query()
        assert len(rows) == 2
        # rows are DESC by id -- most recent first
        assert rows[0]["codigo_homologado"] == "PC.02"
        assert rows[0]["confianza"] == round(0.88 * 0.85, 4)
        assert rows[1]["codigo_homologado"] == "AC.01"
        assert rows[1]["confianza"] == 0.98
        rec.close()


if __name__ == "__main__":
    import sys
    this = sys.modules[__name__]
    passed = 0
    failed = 0
    for name in sorted(dir(this)):
        if name.startswith("test_"):
            try:
                getattr(this, name)()
                print(f"  ✓ {name}")
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
