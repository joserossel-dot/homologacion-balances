from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from knowledge.unknown_cluster import load_unclassified, normalize_name, cluster_accounts, summarize_clusters
from knowledge.rule_suggester import suggest_rules
from knowledge.synonym_detector import detect_synonyms
from knowledge.improvement_ranker import rank_improvements

logging.disable(logging.CRITICAL)

SHADOW_PATH = Path("reports/semantic_shadow/shadow_data.json")


def _load_fixture() -> list[dict]:
    if not SHADOW_PATH.exists():
        return []
    with open(SHADOW_PATH) as f:
        data = json.load(f)
    return data.get("accounts", [])


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

def test_normalize_name_lowercase():
    assert normalize_name("CAJA GENERAL") == "caja general"


def test_normalize_name_accents():
    assert normalize_name("Depreciación Acumulada") == "depreciacion acumulada"


def test_normalize_name_punctuation():
    assert normalize_name("IVA CRÉDITO FISCAL!") == "iva credito fiscal"


def test_normalize_name_extra_spaces():
    assert normalize_name("  Caja   y  Bancos  ") == "caja y bancos"


def test_normalize_name_empty():
    assert normalize_name("") == ""


# ---------------------------------------------------------------------------
# load_unclassified
# ---------------------------------------------------------------------------

def test_load_unclassified_returns_list():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    assert isinstance(accounts, list)


def test_load_unclassified_all_unclassified():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    for a in accounts:
        assert a.get("method") in ("unclassified", "", None) or a.get("final_code") is None


def test_load_unclassified_smaller_than_total():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    with open(SHADOW_PATH) as f:
        total = len(json.load(f)["accounts"])
    unclassified = len(load_unclassified(str(SHADOW_PATH)))
    assert unclassified < total


# ---------------------------------------------------------------------------
# cluster_accounts
# ---------------------------------------------------------------------------

def test_cluster_accounts_empty():
    assert cluster_accounts([]) == {}


def test_cluster_accounts_single():
    accts = [{"account_name": "Caja General", "method": "unclassified", "nature": "deudora", "source_path": "test.xlsx"}]
    result = cluster_accounts(accts, min_cluster_size=1)
    assert isinstance(result, dict)


def test_cluster_accounts_similar():
    accts = [
        {"account_name": "Caja General", "method": "unclassified", "nature": "deudora", "source_path": "a.xlsx"},
        {"account_name": "Caja M/N", "method": "unclassified", "nature": "deudora", "source_path": "b.xlsx"},
    ]
    result = cluster_accounts(accts, threshold=50.0, min_cluster_size=2)
    assert len(result) >= 1


def test_cluster_accounts_different():
    accts = [
        {"account_name": "Caja General", "method": "unclassified", "nature": "deudora", "source_path": "a.xlsx"},
        {"account_name": "Depreciación Acumulada", "method": "unclassified", "nature": "acreedora", "source_path": "b.xlsx"},
    ]
    result = cluster_accounts(accts, threshold=90.0, min_cluster_size=2)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# cluster_accounts with real data
# ---------------------------------------------------------------------------

def test_cluster_accounts_real_data():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    clusters = cluster_accounts(accounts)
    assert isinstance(clusters, dict)
    for cid, info in clusters.items():
        assert cid.startswith("cluster_")
        assert info["size"] >= 2
        assert len(info["members"]) >= 2
        assert info["representative"]


def test_cluster_summary_fields():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    clusters = cluster_accounts(accounts)
    summary = summarize_clusters(clusters)
    for row in summary:
        assert "cluster_id" in row
        assert "size" in row
        assert "representative" in row
        assert "num_files" in row


# ---------------------------------------------------------------------------
# suggest_rules
# ---------------------------------------------------------------------------

def test_suggest_rules_empty():
    result = suggest_rules({})
    assert result == []


def test_suggest_rules_basic():
    clusters = {
        "cluster_0000": {
            "cluster_id": "cluster_0000",
            "size": 5,
            "members": [
                {"account_name": "Caja General", "method": "unclassified", "nature": "deudora", "source_path": "a.xlsx"},
                {"account_name": "Caja M/N", "method": "unclassified", "nature": "deudora", "source_path": "b.xlsx"},
            ],
            "representative": "caja general",
            "normalized_samples": ["caja general", "caja mn"],
            "source_files": ["a.xlsx", "b.xlsx"],
        }
    }
    result = suggest_rules(clusters)
    assert len(result) >= 1
    assert result[0]["suggested_semantic_type"] == "asset"


def test_suggest_rules_deudora_asset():
    clusters = {
        "cluster_0000": {
            "cluster_id": "cluster_0000",
            "size": 3,
            "members": [
                {"account_name": "Banco", "method": "unclassified", "nature": "deudora", "source_path": "a.xlsx"},
                {"account_name": "Bancos", "method": "unclassified", "nature": "deudora", "source_path": "b.xlsx"},
            ],
            "representative": "banco",
            "normalized_samples": ["banco", "bancos"],
            "source_files": ["a.xlsx", "b.xlsx"],
        }
    }
    result = suggest_rules(clusters)
    assert result[0]["suggested_semantic_type"] == "asset"


def test_suggest_rules_loss_expense():
    clusters = {
        "cluster_0000": {
            "cluster_id": "cluster_0000",
            "size": 3,
            "members": [
                {"account_name": "Gastos Generales", "method": "unclassified", "nature": "loss", "source_path": "a.xlsx"},
                {"account_name": "Gastos Adm", "method": "unclassified", "nature": "loss", "source_path": "b.xlsx"},
            ],
            "representative": "gastos generales",
            "normalized_samples": ["gastos generales", "gastos adm"],
            "source_files": ["a.xlsx", "b.xlsx"],
        }
    }
    result = suggest_rules(clusters)
    assert result[0]["suggested_semantic_type"] == "expense"


def test_suggest_rules_keywords_extracted():
    clusters = {
        "cluster_0000": {
            "cluster_id": "cluster_0000",
            "size": 3,
            "members": [
                {"account_name": "Proveedores Nacionales", "method": "unclassified", "nature": "acreedora", "source_path": "a.xlsx"},
                {"account_name": "Proveedores Extranjero", "method": "unclassified", "nature": "acreedora", "source_path": "b.xlsx"},
            ],
            "representative": "proveedores nacionales extranjero",
            "normalized_samples": ["proveedores nacionales", "proveedores extranjero"],
            "source_files": ["a.xlsx", "b.xlsx"],
        }
    }
    result = suggest_rules(clusters)
    assert len(result) >= 1
    assert "proveedores" in result[0].get("suggested_keywords", [])


def test_suggest_rules_real_data():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    clusters = cluster_accounts(accounts)
    result = suggest_rules(clusters)
    assert isinstance(result, list)
    assert all("suggested_semantic_type" in c for c in result)
    assert all("suggested_keywords" in c for c in result)
    assert all("confidence_score" in c for c in result)


# ---------------------------------------------------------------------------
# detect_synonyms
# ---------------------------------------------------------------------------

def test_detect_synonyms_empty():
    result = detect_synonyms([])
    assert isinstance(result, list)


def test_detect_synonyms_caja():
    accounts = [
        {"account_name": "Caja General"},
        {"account_name": "Caja M/N"},
        {"account_name": "Caja Central"},
    ]
    result = detect_synonyms(accounts, threshold=80.0)
    caja_groups = [g for g in result if "Caja" in g["group_label"]]
    assert len(caja_groups) >= 1


def test_detect_synonyms_known_group():
    accounts = [
        {"account_name": "Caja"},
        {"account_name": "Caja General"},
        {"account_name": "Banco Estado"},
        {"account_name": "Banco Chile"},
    ]
    result = detect_synonyms(accounts)
    labels = [g["group_label"] for g in result]
    assert "Caja" in labels
    assert "Banco" in labels


def test_detect_synonyms_real_data():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    result = detect_synonyms(accounts)
    assert isinstance(result, list)
    for g in result:
        assert "group_label" in g
        assert "variants" in g
        assert g["num_variants"] >= 2


# ---------------------------------------------------------------------------
# rank_improvements
# ---------------------------------------------------------------------------

def test_rank_improvements_empty():
    result = rank_improvements([], [], total_unclassified=100)
    assert isinstance(result, list)


def test_rank_improvements_order():
    candidates = [
        {"confidence_score": 0.9, "size": 50, "suggested_semantic_type": "asset",
         "suggested_keywords": ["caja"], "suggested_financial_statement": "balance_sheet",
         "representative": "caja", "cluster_id": "c0", "num_files": 5, "dominant_nature": "deudora",
         "num_known_classifications": 10, "known_codes": [], "source_files": []},
        {"confidence_score": 0.5, "size": 10, "suggested_semantic_type": "expense",
         "suggested_keywords": ["gastos"], "suggested_financial_statement": "income_statement",
         "representative": "gastos", "cluster_id": "c1", "num_files": 3, "dominant_nature": "loss",
         "num_known_classifications": 2, "known_codes": [], "source_files": []},
    ]
    synonyms = [
        {"group_label": "Caja", "num_variants": 3, "detected_by": "keyword_group", "variants": ["Caja", "Caja General", "Caja M/N"]},
    ]
    result = rank_improvements(candidates, synonyms, total_unclassified=100)
    assert len(result) == 3
    assert result[0]["priority"] == 1
    assert result[1]["priority"] == 2
    assert result[2]["priority"] == 3


def test_rank_improvements_has_priority():
    candidates = [
        {"confidence_score": 0.8, "size": 20, "suggested_semantic_type": "asset",
         "suggested_keywords": ["banco"], "suggested_financial_statement": "balance_sheet",
         "representative": "banco", "cluster_id": "c0", "num_files": 4, "dominant_nature": "deudora",
         "num_known_classifications": 5, "known_codes": [], "source_files": []},
    ]
    result = rank_improvements(candidates, [], total_unclassified=50)
    assert len(result) == 1
    assert result[0]["priority"] == 1
    assert result[0]["weighted_impact"] > 0


# ---------------------------------------------------------------------------
# Integration: full pipeline
# ---------------------------------------------------------------------------

def test_full_pipeline():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    assert len(accounts) > 0

    clusters = cluster_accounts(accounts)
    assert len(clusters) > 0

    summary = summarize_clusters(clusters)
    assert len(summary) > 0

    candidates = suggest_rules(clusters)
    assert len(candidates) > 0

    synonyms = detect_synonyms(accounts)
    assert len(synonyms) > 0

    ranked = rank_improvements(candidates, synonyms, len(accounts))
    assert len(ranked) > 0


def test_full_pipeline_types():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    accounts = load_unclassified(str(SHADOW_PATH))
    clusters = cluster_accounts(accounts)
    candidates = suggest_rules(clusters)

    for c in candidates[:10]:
        assert isinstance(c["suggested_keywords"], list)
        assert isinstance(c["confidence_score"], (int, float))
        assert c["confidence_score"] >= 0.0

    synonyms = detect_synonyms(accounts)
    for s in synonyms[:10]:
        assert isinstance(s["variants"], list)
        assert s["num_variants"] == len(s["variants"])


# ---------------------------------------------------------------------------
# RuleGenerator
# ---------------------------------------------------------------------------


def test_generate_rule_for_candidate_basic():
    from knowledge.rule_generator import generate_rule_for_candidate

    candidate = {
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["caja", "bancos"],
        "dominant_nature": "deudora",
        "size": 10,
        "confidence_score": 0.6,
        "source_files": ["a.xlsx", "b.xlsx"],
        "cluster_id": "cluster_0000",
    }
    result = generate_rule_for_candidate(candidate)
    assert "error" not in result
    assert result["rule_name"] == "caja_bancos"
    assert result["priority"] >= 60
    assert result["code"]
    assert result["suggested_semantic_type"] == "asset"


def test_generate_rule_for_candidate_expense():
    from knowledge.rule_generator import generate_rule_for_candidate

    candidate = {
        "suggested_semantic_type": "expense",
        "suggested_keywords": ["gastos", "generales"],
        "dominant_nature": "loss",
        "size": 25,
        "confidence_score": 0.5,
        "source_files": [],
        "cluster_id": "cluster_0001",
    }
    result = generate_rule_for_candidate(candidate)
    assert result["suggested_semantic_type"] == "expense"
    assert "perdida" in result.get("acceptable_column", "")
    assert "income_statement" in result["code"]


def test_generate_rule_no_keywords():
    from knowledge.rule_generator import generate_rule_for_candidate

    result = generate_rule_for_candidate({
        "suggested_semantic_type": "asset",
        "suggested_keywords": [],
    })
    assert "error" in result


def test_generate_rule_code_contains_context_rule():
    from knowledge.rule_generator import generate_rule_for_candidate

    result = generate_rule_for_candidate({
        "suggested_semantic_type": "liability",
        "suggested_keywords": ["proveedores"],
        "dominant_nature": "acreedora",
        "size": 5,
        "confidence_score": 0.7,
        "source_files": [],
        "cluster_id": "cluster_0002",
    })
    assert "_context_rule(" in result["code"]
    assert 'name="proveedores"' in result["code"]
    assert 'acceptable_columns=["pasivo"]' in result["code"] or 'acceptable_columns=["activo"]' in result["code"]


# ---------------------------------------------------------------------------
# CodeGenerator — dictionary
# ---------------------------------------------------------------------------


def test_generate_dictionary_entries_empty():
    from knowledge.code_generator import generate_dictionary_entries

    result = generate_dictionary_entries([], [])
    assert result == []


def test_generate_dictionary_entries_from_rules():
    from knowledge.code_generator import generate_dictionary_entries

    rules = [{
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["caja"],
        "confidence_score": 0.6,
        "cluster_id": "c0",
        "source_files": ["a.xlsx"],
        "size": 10,
    }]
    result = generate_dictionary_entries(rules, [])
    assert len(result) >= 1
    assert result[0]["cuenta_original"] == "caja"
    assert result[0]["codigo_estandar"] == "AC.01"


def test_generate_dictionary_entries_from_synonyms():
    from knowledge.code_generator import generate_dictionary_entries

    synonyms = [{
        "group_label": "Caja",
        "num_variants": 3,
        "detected_by": "keyword_group",
        "variants": ["Caja General", "Caja M/N", "Caja Central"],
    }]
    result = generate_dictionary_entries([], synonyms, max_per_synonym=2)
    assert len(result) >= 1
    assert all(e["fuente"] == "knowledge_generator_synonyms" for e in result)


# ---------------------------------------------------------------------------
# CodeGenerator — gold standard
# ---------------------------------------------------------------------------


def test_generate_gold_standard_entries_empty():
    from knowledge.code_generator import generate_gold_standard_entries

    result = generate_gold_standard_entries([])
    assert result == []


def test_generate_gold_standard_entries_basic():
    from knowledge.code_generator import generate_gold_standard_entries

    candidates = [{
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["caja"],
        "confidence_score": 0.6,
        "cluster_id": "c0",
        "source_files": ["file1.xlsx", "file2.xlsx"],
        "size": 10,
    }]
    result = generate_gold_standard_entries(candidates, max_per_candidate=2)
    assert len(result) == 2
    assert result[0]["suggested_code"] == "AC.01"
    assert "Sugerido por Knowledge Generator" in result[0]["comments"]


def test_generate_gold_standard_entries_dedup():
    from knowledge.code_generator import generate_gold_standard_entries

    candidates = [{
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["caja"],
        "confidence_score": 0.6,
        "cluster_id": "c0",
        "source_files": ["same.xlsx"],
        "size": 10,
    }, {
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["banco"],
        "confidence_score": 0.5,
        "cluster_id": "c1",
        "source_files": ["same.xlsx"],
        "size": 5,
    }]
    result = generate_gold_standard_entries(candidates, max_per_candidate=1)
    assert len(result) == 1  # deduped by (source_file, semantic_type)


# ---------------------------------------------------------------------------
# TestGenerator
# ---------------------------------------------------------------------------


def test_generate_tests_for_rules_empty():
    from knowledge.test_generator import generate_tests_for_rules

    code = generate_tests_for_rules([])
    assert "Auto-generado" in code


def test_generate_tests_for_rules_basic():
    from knowledge.test_generator import generate_tests_for_rules

    rules = [{
        "rule_name": "test_rule",
        "suggested_semantic_type": "asset",
        "keywords": ["caja"],
        "priority": 60,
        "code": "    _context_rule(...)",
        "confidence_score": 0.6,
    }]
    code = generate_tests_for_rules(rules)
    assert "def test_test_rule_match" in code
    assert "def test_test_rule_no_match" in code
    assert 'semantic_type == "asset"' in code


def test_generate_tests_for_dictionary_basic():
    from knowledge.test_generator import generate_tests_for_dictionary

    entries = [
        {"cuenta_original": "Caja General", "codigo_estandar": "AC.01"},
        {"cuenta_original": "Banco Estado", "codigo_estandar": "AC.01"},
    ]
    code = generate_tests_for_dictionary(entries, max_examples=2)
    assert "def test_dictionary_entry_caja_general" in code
    assert 'standard_code == "AC.01"' in code


# ---------------------------------------------------------------------------
# ProposalBuilder
# ---------------------------------------------------------------------------


def test_build_proposals_empty():
    from knowledge.proposal_builder import build_proposals

    result = build_proposals([], [], {}, [])
    assert result["generated_rules"] == []
    assert result["dictionary_entries"] == []
    assert result["gold_standard_entries"] == []


def test_build_proposals_with_ranked():
    from knowledge.proposal_builder import build_proposals

    ranked = [
        {"type": "new_semantic_rule", "priority": 1,
         "representative": "caja general",
         "cluster_size": 5, "confidence": 0.6,
         "description": "Nueva regla: 'caja' -> asset"},
    ]
    clusters = {
        "cluster_0000": {
            "cluster_id": "cluster_0000", "size": 5,
            "members": [
                {"account_name": "Caja General", "method": "unclassified",
                 "nature": "deudora", "source_path": "a.xlsx"},
            ],
            "representative": "caja general",
            "normalized_samples": ["caja general"],
            "source_files": ["a.xlsx"],
        }
    }
    candidates = [{
        "representative": "caja general",
        "suggested_semantic_type": "asset",
        "suggested_keywords": ["caja", "general"],
        "suggested_financial_statement": "balance_sheet",
        "suggested_economic_nature": "debit",
        "dominant_nature": "deudora",
        "size": 5,
        "confidence_score": 0.6,
        "source_files": [],
        "cluster_id": "cluster_0000",
    }]
    result = build_proposals(ranked, [], clusters, candidates)
    assert len(result["generated_rules"]) >= 1
    assert result["generated_rules"][0]["suggested_semantic_type"] == "asset"


def test_export_proposals(tmp_path):
    from knowledge.proposal_builder import export_proposals

    proposals = {
        "config": {"min_priority": 1},
        "generated_rules": [],
        "dictionary_entries": [],
        "gold_standard_entries": [],
        "generated_rules_code": "# rules code",
        "generated_tests_code": "# tests code",
        "summary": {
            "num_rule_proposals": 0,
            "num_dictionary_entries": 0,
            "num_gold_standard_entries": 0,
            "tests_lines": 1,
            "rules_lines": 1,
        },
    }
    paths = export_proposals(proposals, tmp_path)
    assert len(paths) == 5
    for p in paths.values():
        assert p.exists()
