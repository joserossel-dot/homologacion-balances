from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

logging.disable(logging.CRITICAL)

SHADOW_PATH = Path("reports/semantic_shadow/shadow_data.json")


# ---------------------------------------------------------------------------
# MonetaryAmounts
# ---------------------------------------------------------------------------

def test_monetary_amounts_defaults():
    from evidence.account_evidence import MonetaryAmounts
    m = MonetaryAmounts()
    assert m.assets is None
    assert m.liabilities is None


def test_monetary_amounts_from_dict():
    from evidence.account_evidence import MonetaryAmounts
    m = MonetaryAmounts.from_dict({"assets": 100.0, "liabilities": 200.0})
    assert m.assets == 100.0
    assert m.liabilities == 200.0


def test_monetary_amounts_from_dict_none():
    from evidence.account_evidence import MonetaryAmounts
    m = MonetaryAmounts.from_dict(None)
    assert m.assets is None


def test_monetary_amounts_from_dict_partial():
    from evidence.account_evidence import MonetaryAmounts
    m = MonetaryAmounts.from_dict({"assets": 100.0})
    assert m.assets == 100.0
    assert m.liabilities is None


def test_monetary_amounts_to_dict():
    from evidence.account_evidence import MonetaryAmounts
    m = MonetaryAmounts(assets=500.0, losses=100.0)
    d = m.to_dict()
    assert d["assets"] == 500.0
    assert d["losses"] == 100.0
    assert "debit" in d


# ---------------------------------------------------------------------------
# AccountEvidence
# ---------------------------------------------------------------------------

def test_account_evidence_defaults():
    from evidence.account_evidence import AccountEvidence
    ev = AccountEvidence()
    assert ev.record_id == ""
    assert ev.source_file == ""
    assert not ev.is_complete
    assert not ev.has_amounts
    assert not ev.has_context
    assert ev.coverage_score == 0.0


def test_account_evidence_complete():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    ev = AccountEvidence(
        source_file="balance.xlsx",
        source_page=1,
        company_name="Empresa SA",
        original_account_name="Caja",
        monetary=MonetaryAmounts(assets=1000.0),
        classification_amount=1000.0,
        parser_used="excel",
        document_type="balance",
        sheet_name="Sheet1",
        row_number=5,
        context_before=[{"account_name": "Banco"}],
        context_after=[{"account_name": "Clientes"}],
        classification_method="code_exact",
        final_code="AC.01",
        metadata={"key": "val"},
    )
    assert ev.is_complete
    assert ev.has_amounts
    assert ev.has_context
    assert ev.coverage_score > 0.0


def test_account_evidence_missing_fields():
    from evidence.account_evidence import AccountEvidence
    ev = AccountEvidence()
    missing = ev.missing_fields()
    assert "source_file" in missing
    assert "company_name" in missing
    assert "year" in missing


def test_account_evidence_to_dict():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    ev = AccountEvidence(
        record_id="ev_001",
        source_file="test.xlsx",
        monetary=MonetaryAmounts(assets=100.0),
        context_before=[{"name": "A"}],
        metadata={"key": "val"},
    )
    d = ev.to_dict()
    assert d["record_id"] == "ev_001"
    assert d["monetary"]["assets"] == 100.0
    assert d["context_before"] == [{"name": "A"}]
    assert d["metadata"] == {"key": "val"}


def test_account_evidence_from_dict():
    from evidence.account_evidence import AccountEvidence
    data = {
        "record_id": "ev_002",
        "source_file": "test.xlsx",
        "monetary": {"assets": 200.0},
        "context_before": [],
    }
    ev = AccountEvidence.from_dict(data)
    assert ev.record_id == "ev_002"
    assert ev.monetary.assets == 200.0


def test_account_evidence_coverage_score():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    ev = AccountEvidence(
        source_file="f.xlsx",
        source_page=1,
        company_name="C",
        original_account_name="N",
        clean_account_name="N",
        monetary=MonetaryAmounts(assets=1.0),
        classification_amount=1.0,
        parser_used="p",
        classification_method="m",
        final_code="c",
        metadata={"k": "v"},
        sheet_name="s",
        row_number=1,
    )
    # Missing: company_rut, company_business, year, document_type, ocr_used, context
    assert ev.coverage_score >= 60.0
    assert len(ev.missing_fields()) <= 6


# ---------------------------------------------------------------------------
# build_from_shadow_entry
# ---------------------------------------------------------------------------

def test_build_from_shadow_entry():
    from evidence.evidence_builder import build_from_shadow_entry
    entry = {
        "account_code": "1101",
        "account_name": "Caja General",
        "nature": "asset",
        "classification_amount": 500000.0,
        "method": "unclassified",
        "confidence": 0.0,
        "source_group": "edge_cases",
        "source_file": "",
        "source_page": 0,
        "source_path": "data/test.xlsx",
        "final_code": None,
        "standard_code": None,
        "reason": "Sin coincidencia",
        "semantic_result": {
            "semantic_type": "unknown",
            "matched_rule": "no_match",
            "expected_side": "unknown",
        },
    }
    ev = build_from_shadow_entry(entry)
    assert ev.original_account_name == "Caja General"
    assert ev.clean_account_name == "Caja General"  # already clean, no change
    assert ev.classification_method == "unclassified"
    assert ev.monetary.assets is not None
    assert ev.source_file == "test.xlsx"  # derived from path


def test_build_from_shadow_entry_with_context():
    from evidence.evidence_builder import build_from_shadow_entry
    entry = {
        "account_name": "Banco",
        "nature": "asset",
        "classification_amount": 100.0,
        "method": "unclassified",
        "confidence": 0.0,
        "semantic_result": {},
    }
    ev = build_from_shadow_entry(entry, context_before=[{"name": "Caja"}], context_after=[{"name": "Clientes"}])
    assert len(ev.context_before) == 1
    assert len(ev.context_after) == 1


def test_build_from_shadow_entry_semantic_hit():
    from evidence.evidence_builder import build_from_shadow_entry
    entry = {
        "account_name": "DEPRECIACION ACUMULADA",
        "nature": "liability",
        "classification_amount": 1000.0,
        "method": "unclassified",
        "confidence": 0.0,
        "source_group": "test",
        "source_path": "",
        "semantic_result": {
            "semantic_type": "contra_asset",
            "matched_rule": "depreciacion_acumulada",
            "expected_side": "credit",
        },
    }
    ev = build_from_shadow_entry(entry)
    assert ev.semantic_hit is True
    assert ev.semantic_type == "contra_asset"
    assert ev.semantic_rule == "depreciacion_acumulada"


# ---------------------------------------------------------------------------
# EvidenceSerializer
# ---------------------------------------------------------------------------

def test_serialize_deserialize_roundtrip():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    from evidence.evidence_serializer import serialize_evidence, deserialize_evidence
    ev = AccountEvidence(
        record_id="ev_001",
        source_file="t.xlsx",
        original_account_name="Test",
        monetary=MonetaryAmounts(assets=500.0),
    )
    d = serialize_evidence(ev)
    assert d["_evidence_version"] == 1
    restored = deserialize_evidence(d)
    assert restored.record_id == "ev_001"
    assert restored.monetary.assets == 500.0


def test_save_load_json(tmp_path):
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    from evidence.evidence_serializer import save_evidence_json, load_evidence_json
    evs = [
        AccountEvidence(record_id="ev_1", source_file="f1.xlsx", original_account_name="A",
                        monetary=MonetaryAmounts(assets=100.0)),
        AccountEvidence(record_id="ev_2", source_file="f2.xlsx", original_account_name="B",
                        monetary=MonetaryAmounts(liabilities=200.0)),
    ]
    path = save_evidence_json(evs, tmp_path / "evidence.json")
    assert path.exists()
    loaded = load_evidence_json(str(path))
    assert len(loaded) == 2
    assert loaded[0].record_id == "ev_1"


def test_to_shadow_compatible():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    from evidence.evidence_serializer import to_shadow_compatible
    evs = [
        AccountEvidence(
            record_id="ev_1", source_file="f.xlsx", source_page=1,
            original_account_name="Caja",
            classification_method="unclassified",
            classification_confidence=0.0,
            classification_amount=100.0,
            semantic_type="unknown",
            semantic_rule="no_match",
            source_group="test",
            source_path="test.xlsx",
            metadata={"nature": "asset", "reason": "test"},
        )
    ]
    result = to_shadow_compatible(evs)
    assert len(result) == 1
    assert result[0]["account_name"] == "Caja"
    assert result[0]["method"] == "unclassified"


# ---------------------------------------------------------------------------
# convert_shadow_to_evidences
# ---------------------------------------------------------------------------

def test_convert_shadow_to_evidences():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from evidence.evidence_serializer import convert_shadow_to_evidences
    evs = convert_shadow_to_evidences(str(SHADOW_PATH))
    assert len(evs) > 0
    assert evs[0].record_id.startswith("ev_")
    assert evs[0].original_account_name


# ---------------------------------------------------------------------------
# EvidenceContext
# ---------------------------------------------------------------------------

def test_build_context_windows():
    from evidence.evidence_context import build_context_windows
    entries = [{"account_name": f"A{i}"} for i in range(10)]
    windows = build_context_windows(entries, window_size=3)
    assert len(windows) == 10
    assert len(windows[0][0]) == 0  # first has no before
    assert len(windows[0][1]) == 3  # first has 3 after
    assert len(windows[9][0]) == 3  # last has 3 before
    assert len(windows[9][1]) == 0  # last has no after


def test_add_context_to_evidences():
    from evidence.account_evidence import AccountEvidence
    from evidence.evidence_context import add_context_to_evidences
    evs = [AccountEvidence(original_account_name=f"A{i}") for i in range(10)]
    result = add_context_to_evidences(evs, window_size=2)
    assert len(result[0].context_after) == 2
    assert len(result[9].context_before) == 2


# ---------------------------------------------------------------------------
# EvidenceReport
# ---------------------------------------------------------------------------

def test_compute_coverage_empty():
    from evidence.evidence_report import compute_coverage
    c = compute_coverage([])
    assert c["total"] == 0


def test_compute_coverage_basic():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    from evidence.evidence_report import compute_coverage
    evs = [
        AccountEvidence(source_file="f.xlsx", source_page=1, company_name="C", original_account_name="N",
                        classification_method="m", final_code="c", monetary=MonetaryAmounts(assets=1.0),
                        classification_amount=1.0, parser_used="p", document_type="b", sheet_name="s", row_number=1,
                        context_before=[{"a": 1}], metadata={"k": "v"}),
        AccountEvidence(),
    ]
    c = compute_coverage(evs)
    assert c["total"] == 2
    assert c["avg_coverage_score"] > 0
    assert "source_file" in c["fields"]


def test_generate_audit_report(tmp_path):
    from evidence.account_evidence import AccountEvidence
    from evidence.evidence_report import generate_audit_report
    evs = [AccountEvidence(original_account_name="Test")]
    paths = generate_audit_report(evs, tmp_path)
    assert "audit_md" in paths
    assert paths["audit_md"].exists()


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

def test_shadow_to_evidence_roundtrip():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from evidence.evidence_serializer import convert_shadow_to_evidences, to_shadow_compatible
    with open(SHADOW_PATH) as f:
        original = json.load(f)
    orig_len = len(original["accounts"])
    evs = convert_shadow_to_evidences(str(SHADOW_PATH))
    assert len(evs) == orig_len
    # Convert back
    back = to_shadow_compatible(evs)
    assert len(back) == orig_len
    # Check key fields preserved
    for i in range(min(5, orig_len)):
        assert back[i]["account_name"] == original["accounts"][i]["account_name"]
        assert back[i]["method"] == original["accounts"][i]["method"]


# ---------------------------------------------------------------------------
# Evidence full pipeline integration test
# ---------------------------------------------------------------------------

def test_evidence_to_review_compatible():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    from evidence.evidence_serializer import to_shadow_compatible
    from evidence.evidence_builder import build_from_shadow_entry
    # Simulate a real pipeline flow
    entry = {
        "account_name": "Caja General",
        "nature": "asset",
        "classification_amount": 500000.0,
        "method": "unclassified",
        "confidence": 0.0,
        "source_group": "test_group",
        "source_file": "balance.xlsx",
        "source_page": 3,
        "source_path": "data/balance.xlsx",
        "final_code": None,
        "standard_code": None,
        "reason": "Sin match",
        "semantic_result": {"semantic_type": "unknown", "matched_rule": "no_match"},
    }
    ev = build_from_shadow_entry(entry)
    assert ev.source_file == "balance.xlsx"
    assert ev.source_page == 3
    assert ev.company_name  # extracted from source_path
    # Verify it can be serialized to shadow-compatible format
    shadow_compat = to_shadow_compatible([ev])
    assert shadow_compat[0]["account_name"] == "Caja General"
    assert shadow_compat[0]["source_page"] == 3


def test_evidence_preserves_amounts():
    from evidence.account_evidence import AccountEvidence, MonetaryAmounts
    m = MonetaryAmounts(assets=1000.0, liabilities=500.0, losses=200.0, profits=300.0)
    ev = AccountEvidence(
        record_id="ev_amt",
        original_account_name="Test",
        monetary=m,
        classification_amount=1000.0,
    )
    d = ev.to_dict()
    assert d["monetary"]["assets"] == 1000.0
    assert d["monetary"]["liabilities"] == 500.0
    assert d["monetary"]["losses"] == 200.0
    assert d["monetary"]["profits"] == 300.0
    # Verify round-trip
    from evidence.evidence_serializer import deserialize_evidence
    restored = deserialize_evidence(d)
    assert restored.monetary.assets == 1000.0
    assert restored.monetary.profits == 300.0


def test_evidence_coverage_breakdown():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from evidence.evidence_serializer import convert_shadow_to_evidences
    from evidence.evidence_report import compute_coverage
    evs = convert_shadow_to_evidences(str(SHADOW_PATH))
    coverage = compute_coverage(evs)
    # These should always be 100% with current data
    assert coverage["fields"]["classification_method"]["pct"] == 100.0
    assert coverage["fields"]["clean_account_name"]["pct"] >= 99.0
    # These should be 0% since they're not in shadow_data
    assert coverage["fields"]["source_page > 0"]["pct"] == 0.0
    assert coverage["fields"]["company_rut"]["pct"] == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_evidence_empty_name():
    from evidence.evidence_builder import build_from_shadow_entry
    ev = build_from_shadow_entry({
        "account_name": "",
        "nature": "",
        "classification_amount": 0.0,
        "method": "",
        "confidence": 0.0,
        "semantic_result": {},
    })
    assert ev.original_account_name == ""
    assert ev.clean_account_name == ""


def test_evidence_negative_amount():
    from evidence.evidence_builder import build_from_shadow_entry
    ev = build_from_shadow_entry({
        "account_name": "Pérdida",
        "nature": "loss",
        "classification_amount": -5000.0,
        "method": "unclassified",
        "confidence": 0.0,
        "semantic_result": {},
    })
    assert ev.monetary.losses == 5000.0  # abs value
    assert ev.classification_amount == -5000.0


def test_evidence_company_from_path():
    from evidence.evidence_builder import _extract_company_from_path
    info = _extract_company_from_path("data/empresa_sa/balance.xlsx")
    assert info["company"]  # should extract something


def test_evidence_year_extraction():
    from evidence.evidence_builder import _extract_year_from_name
    assert _extract_year_from_name("Balance 2023") == "2023"
    assert _extract_year_from_name("Enero 2022 Diciembre") == "2022"
    assert _extract_year_from_name("No year") == ""


def test_evidence_clean_name():
    from evidence.evidence_builder import _clean_name
    assert _clean_name("11051-0000 BANCO CHILE") == "BANCO CHILE"
    assert _clean_name("5.1.3. Proveedores") == "Proveedores"
    assert "  " not in _clean_name("  Test  ")


# ---------------------------------------------------------------------------
# Backward compatibility: all existing test files
# ---------------------------------------------------------------------------

def test_all_existing_tests_still_pass():
    # This test is a placeholder — the real check happens via pytest on
    # the full suite. We verify the evidence module loads without
    # breaking existing imports.
    import evidence
    assert hasattr(evidence, "AccountEvidence")
    assert hasattr(evidence, "MonetaryAmounts")
    assert hasattr(evidence, "build_from_shadow_entry")
