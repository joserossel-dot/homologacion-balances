from __future__ import annotations

import json
from pathlib import Path

from learning.engine import LearningEngine
from learning.models import CorrectionEntry


def test_record_correction(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    e = eng.record("HONORARIOS", "PC.06", original_code="ER.04", user="reviewer")
    assert e.account_name == "HONORARIOS"
    assert e.corrected_code == "PC.06"
    assert e.original_code == "ER.04"
    assert e.user == "reviewer"
    assert e.frequency == 1


def test_frequency_increment(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("HONORARIOS", "PC.06", original_code="ER.04")
    e2 = eng.record("HONORARIOS", "PC.06", original_code="ER.04")
    assert e2.frequency == 2
    assert eng.total_corrections == 1


def test_get_pending(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("CTA_A", "X.01", reviewed=False)
    eng.record("CTA_B", "X.02", reviewed=True)
    eng.record("CTA_C", "X.03", reviewed=False)

    pending = eng.get_pending()
    assert len(pending) == 2
    assert all(not e.reviewed for e in pending)


def test_mark_reviewed(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("CTA_A", "X.01")
    assert eng.mark_reviewed(0) is True
    assert eng.queue[0].reviewed is True


def test_get_stats(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("HONORARIOS", "PC.06", original_code="ER.04", user="ana")
    eng.record("REMUNERACIONES", "PC.06", original_code="ER.04", user="ana")
    eng.record("HONORARIOS", "PC.06", original_code="ER.04", user="luis")

    stats = eng.get_stats()
    assert stats.total_entries == 2  # HONORARIOS duplicado incrementa frequency
    assert stats.unique_accounts == 2
    assert stats.by_user.get("ana") == 2  # primera en reportar HONORARIOS + REMUNERACIONES
    assert stats.by_user.get("luis", 0) == 0  # luis repitió HONORARIOS, no nueva entrada


def test_record_from_decision(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    decision = {"decision_source": "CONFLICT_UNRESOLVED", "codigo_final": None}
    e = eng.record_from_decision("HONORARIOS", "PC.06", decision=decision, user="reviewer")
    assert e.corrected_code == "PC.06"
    assert e.source_stage == "CONFLICT_UNRESOLVED"
    assert e.reviewed is True


def test_json_persistence(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("HONORARIOS", "PC.06", original_code="ER.04", user="test_user")
    assert queue.exists()

    raw = json.loads(queue.read_text())
    assert len(raw) == 1
    assert raw[0]["account_name"] == "HONORARIOS"
    assert raw[0]["corrected_code"] == "PC.06"


def test_load_existing_queue(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps([
        {"account_name": "TEST", "corrected_code": "X.01", "original_code": None,
         "reason": "", "user": "system", "timestamp": "2026-01-01T00:00:00",
         "frequency": 1, "source_file": None, "account_code": None,
         "source_stage": None, "reviewed": False},
    ]))

    eng = LearningEngine(db_path=":memory:", queue_path=queue)
    assert eng.total_corrections == 1
    assert eng.queue[0].account_name == "TEST"


def test_import_from_disagreements(tmp_path: Path) -> None:
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({
        "discrepancies": [
            {"account_name": "CTA_A", "regex_code": "ER.04", "sm_code": "PC.06",
             "who_wins": "Indefinido (requiere revisión)", "category": "Error OCR"},
            {"account_name": "CTA_B", "regex_code": "ER.02", "sm_code": "AC.05",
             "who_wins": "Regex", "category": ""},
        ]
    }))

    eng = LearningEngine(db_path=":memory:", queue_path=tmp_path / "queue.json")
    count = eng.import_from_disagreements(audit)
    assert count == 1
    assert eng.total_corrections == 1
    assert eng.queue[0].account_name == "CTA_A"


def test_get_most_frequent(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    eng = LearningEngine(db_path=":memory:", queue_path=queue)

    eng.record("A", "X.01")
    eng.record("A", "X.01")
    eng.record("B", "X.02")
    eng.record("B", "X.02")
    eng.record("B", "X.02")

    top = eng.get_most_frequent(2)
    assert len(top) == 2
    assert top[0].account_name == "B"
    assert top[0].frequency == 3
    assert top[1].account_name == "A"
    assert top[1].frequency == 2
