from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest

logging.disable(logging.CRITICAL)

SHADOW_PATH = Path("reports/semantic_shadow/shadow_data.json")

# =========================================================================
# PatternNormalizer
# =========================================================================


def test_normalizer_empty():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    assert n.normalize("") == ""
    assert n.normalize(None) == ""


def test_normalizer_basic():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    assert n.normalize("Dep.Ac. Vehículos") == "DEP AC VEHICULOS"


def test_normalizer_accents():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    assert n.normalize("DEPRECIACIÓN ACUMULADA") == "DEPRECIACION ACUMULADA"
    assert n.normalize("AMORTIZACIÓN") == "AMORTIZACION"


def test_normalizer_cxc_expansion():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("CxC Proveedores")
    assert "CUENTAS" in result
    assert "COBRAR" in result


def test_normalizer_cxp_expansion():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("CxP Documentos")
    assert "CUENTAS" in result
    assert "PAGAR" in result


def test_normalizer_eerr():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("E.E.R.R.")
    assert result == "E E R R"


def test_normalizer_punctuation_removed():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("1105-0000 BANCO CHILE")
    assert "1105" not in result  # leading numbers get cleaned
    assert result == "BANCO CHILE"


def test_normalizer_preserve_case():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize_preserve_case("Dep.Ac. Vehículos")
    assert "Dep" in result
    assert "Ac" in result


def test_normalizer_multiple_spaces():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("  CAJA   GENERAL  ")
    assert result == "CAJA GENERAL"


def test_normalizer_parentheses():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("DEPRECIACION ACUMULADA (VEHICULOS)")
    assert "(" not in result
    assert ")" not in result
    assert result == "DEPRECIACION ACUMULADA VEHICULOS"


def test_normalizer_acum_abbrev():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("DEP ACUM.")
    assert "ACUM" in result


def test_normalizer_dep_abbrev():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("DEP.")
    assert result == "DEP"


def test_normalizer_colon():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("IVA: CREDITO FISCAL")
    assert ":" not in result


# =========================================================================
# AccountingPattern
# =========================================================================


def test_pattern_dataclass_defaults():
    from patterns.pattern_catalog import AccountingPattern
    p = AccountingPattern(
        pattern_id="test",
        family="TEST",
        description="Test pattern",
        priority=50,
        confidence=0.8,
        regex=re.compile(r"\bTEST\b"),
    )
    assert p.pattern_id == "test"
    assert p.learnable is True
    assert p.keywords_forbidden == []
    assert p.semantic_type == ""
    assert p.examples == []


# =========================================================================
# PatternCatalog
# =========================================================================

def test_catalog_returns_all():
    from patterns.pattern_catalog import PatternCatalog
    all_p = PatternCatalog.get_all()
    assert len(all_p) == 15


def test_catalog_by_family():
    from patterns.pattern_catalog import PatternCatalog
    ps = PatternCatalog.get_by_family("CAJA")
    assert len(ps) == 1
    assert ps[0].pattern_id == "caja"


def test_catalog_by_id():
    from patterns.pattern_catalog import PatternCatalog
    p = PatternCatalog.get_by_id("depreciacion_acumulada")
    assert p is not None
    assert p.family == "DEPRECIACION_ACUMULADA"


def test_catalog_by_id_missing():
    from patterns.pattern_catalog import PatternCatalog
    assert PatternCatalog.get_by_id("nonexistent") is None


def test_catalog_families_summary():
    from patterns.pattern_catalog import PatternCatalog
    summary = PatternCatalog.families_summary()
    assert len(summary) == 15
    assert all("family" in s for s in summary)


# =========================================================================
# PatternCatalog — specific family validations
# =========================================================================

def _check_examples(pattern_id: str):
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_normalizer import PatternNormalizer
    from patterns.pattern_matcher import PatternMatcher
    p = PatternCatalog.get_by_id(pattern_id)
    assert p is not None, f"Pattern {pattern_id} not found"
    n = PatternNormalizer()
    m = PatternMatcher(n)
    for ex in p.examples:
        match = m.match(ex, p)
        assert match is not None, (
            f"Pattern {pattern_id} should match example '{ex}'"
        )


def _check_negative_examples(pattern_id: str):
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_normalizer import PatternNormalizer
    from patterns.pattern_matcher import PatternMatcher
    p = PatternCatalog.get_by_id(pattern_id)
    assert p is not None, f"Pattern {pattern_id} not found"
    n = PatternNormalizer()
    m = PatternMatcher(n)
    for ex in p.negative_examples:
        match = m.match(ex, p)
        assert match is None, (
            f"Pattern {pattern_id} should NOT match negative example '{ex}'"
        )


def test_depreciacion_acumulada_examples():
    _check_examples("depreciacion_acumulada")


def test_depreciacion_acumulada_negative():
    _check_negative_examples("depreciacion_acumulada")


def test_amortizacion_acumulada_examples():
    _check_examples("amortizacion_acumulada")


def test_amortizacion_acumulada_negative():
    _check_negative_examples("amortizacion_acumulada")


def test_depreciacion_del_ejercicio_examples():
    _check_examples("depreciacion_del_ejercicio")


def test_depreciacion_del_ejercicio_negative():
    _check_negative_examples("depreciacion_del_ejercicio")


def test_amortizacion_del_ejercicio_examples():
    _check_examples("amortizacion_del_ejercicio")


def test_amortizacion_del_ejercicio_negative():
    _check_negative_examples("amortizacion_del_ejercicio")


def test_empresas_relacionadas_examples():
    _check_examples("empresas_relacionadas")


def test_iva_credito_examples():
    _check_examples("iva_credito")


def test_iva_credito_negative():
    _check_negative_examples("iva_credito")


def test_iva_debito_examples():
    _check_examples("iva_debito")


def test_iva_debito_negative():
    _check_negative_examples("iva_debito")


def test_cuentas_por_cobrar_examples():
    _check_examples("cuentas_por_cobrar")


def test_cuentas_por_pagar_examples():
    _check_examples("cuentas_por_pagar")


def test_caja_examples():
    _check_examples("caja")


def test_bancos_examples():
    _check_examples("bancos")


def test_provisiones_examples():
    _check_examples("provisiones")


def test_provisiones_negative():
    _check_negative_examples("provisiones")


def test_honorarios_examples():
    _check_examples("honorarios")


def test_remuneraciones_examples():
    _check_examples("remuneraciones")


def test_capital_examples():
    _check_examples("capital")


# =========================================================================
# PatternMatcher
# =========================================================================

def test_matcher_no_match():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    p = PatternCatalog.get_by_id("caja")
    assert p is not None
    result = m.match("BANCO SANTANDER", p)
    assert result is None


def test_matcher_empty_name():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    p = PatternCatalog.get_by_id("caja")
    assert p is not None
    assert m.match("", p) is None
    assert m.match("  ", p) is None


def test_matcher_match_all():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    all_p = PatternCatalog.get_all()
    results = m.match_all("DEPRECIACION ACUMULADA VEHICULOS", all_p)
    assert len(results) >= 1
    families = {r.family for r in results}
    assert "DEPRECIACION_ACUMULADA" in families


def test_matcher_best_match():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    all_p = PatternCatalog.get_all()
    best = m.best_match("DEPRECIACION ACUMULADA VEHICULOS", all_p)
    assert best is not None
    assert best.family == "DEPRECIACION_ACUMULADA"


def test_matcher_best_match_no_match():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    all_p = PatternCatalog.get_all()
    best = m.best_match("ZZZZZ SIN COINCIDENCIA", all_p)
    assert best is None


def test_matcher_forbidden_keyword():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    p = PatternCatalog.get_by_id("provisiones")
    assert p is not None
    assert m.match("PROVISION VACACIONES", p) is None


def test_matcher_multiple_matches():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    all_p = PatternCatalog.get_all()
    results = m.match_all("CAJA GENERAL", all_p)
    families = {r.family for r in results}
    assert "CAJA" in families


def test_matcher_returns_patternmatch():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher, PatternMatch
    m = PatternMatcher()
    p = PatternCatalog.get_by_id("caja")
    assert p is not None
    result = m.match("CAJA GENERAL", p)
    assert isinstance(result, PatternMatch)
    assert result.pattern_id == "caja"
    assert result.family == "CAJA"
    assert result.confidence > 0
    assert result.explanation


def test_match_unclassified():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    all_p = PatternCatalog.get_all()
    result = m.match_unclassified(
        {"account_name": "CAJA MN", "method": "unclassified"}, all_p
    )
    assert len(result) == 1
    assert result[0].family == "CAJA"


def test_match_unclassified_no_name():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    result = m.match_unclassified({}, [])
    assert result == []


def test_match_unclassified_empty_name():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    all_p = PatternCatalog.get_all()
    m = PatternMatcher()
    result = m.match_unclassified(
        {"account_name": "", "method": "unclassified"}, all_p
    )
    assert result == []


# =========================================================================
# match_patterns_on_accounts
# =========================================================================

def test_match_patterns_on_accounts():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import match_patterns_on_accounts
    accounts = [
        {"account_name": "CAJA GENERAL"},
        {"account_name": "BANCO SANTANDER"},
        {"account_name": "NO MATCH HERE"},
    ]
    all_p = PatternCatalog.get_all()
    results = match_patterns_on_accounts(accounts, all_p)
    assert len(results) == 3
    assert len(results["account_0"]) > 0
    assert len(results["account_1"]) > 0
    assert len(results["account_2"]) == 0


# =========================================================================
# PatternEngine
# =========================================================================

def test_engine_initialization():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    assert len(e.patterns) == 15


def test_engine_analyze_account():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    matches = e.analyze_account(
        {"account_name": "DEPRECIACION ACUMULADA", "method": "unclassified"}
    )
    assert len(matches) == 1
    assert matches[0].family == "DEPRECIACION_ACUMULADA"


def test_engine_analyze_account_no_name():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    matches = e.analyze_account(
        {"account_name": "", "method": "unclassified"}
    )
    assert matches == []


def test_engine_analyze_accounts():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    accounts = [
        {"account_name": "CAJA MN", "method": "unclassified"},
        {"account_name": "BANCO CHILE", "method": "unclassified"},
        {"account_name": "SIN COINCIDENCIA", "method": "unclassified"},
    ]
    results = e.analyze_accounts(accounts)
    assert len(results) == 3
    assert results[0]["total_matches"] > 0
    assert results[1]["total_matches"] > 0
    assert results[2]["total_matches"] == 0


def test_engine_compute_coverage_all_matched():
    from patterns.pattern_engine import PatternEngine
    from patterns.pattern_matcher import PatternMatch
    engine = PatternEngine()
    results = [
        {
            "is_classified": False,
            "total_matches": 1,
            "matches": [
                PatternMatch(
                    pattern_id="caja",
                    family="CAJA",
                    confidence=0.8,
                    priority=60,
                )
            ],
            "account": {"account_name": "CAJA"},
            "best_match": None,
            "normalized_name": "CAJA",
        },
        {
            "is_classified": False,
            "total_matches": 0,
            "matches": [],
            "account": {"account_name": "ZZZ"},
            "best_match": None,
            "normalized_name": "ZZZ",
        },
    ]
    coverage = engine.compute_coverage(results)
    assert coverage["total_accounts"] == 2
    assert coverage["total_unclassified"] == 2
    assert coverage["matched_unclassified"] == 1
    assert coverage["coverage_unclassified_pct"] == 50.0


def test_engine_compute_coverage_empty():
    from patterns.pattern_engine import PatternEngine
    engine = PatternEngine()
    coverage = engine.compute_coverage([])
    assert coverage["total_accounts"] == 0
    assert coverage["coverage_unclassified_pct"] == 0.0


def test_engine_compute_coverage_all_classified():
    from patterns.pattern_engine import PatternEngine
    from patterns.pattern_matcher import PatternMatch
    engine = PatternEngine()
    results = [
        {
            "is_classified": True,
            "total_matches": 1,
            "matches": [PatternMatch(pattern_id="caja", family="CAJA", confidence=0.8, priority=60)],
            "account": {"account_name": "CAJA"},
            "best_match": None,
            "normalized_name": "CAJA",
        },
    ]
    coverage = engine.compute_coverage(results)
    assert coverage["total_accounts"] == 1
    assert coverage["total_unclassified"] == 0
    assert coverage["coverage_unclassified_pct"] == 0.0


def test_engine_get_pattern_by_id():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    p = e.get_pattern_by_id("capital")
    assert p is not None
    assert p.family == "CAPITAL"


def test_engine_get_patterns_by_family():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    ps = e.get_patterns_by_family("BANCOS")
    assert len(ps) == 1


def test_engine_families_summary():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    summary = e.families_summary()
    assert len(summary) == 15


def test_engine_load_shadow_data():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    accounts = e.load_shadow_data(SHADOW_PATH)
    assert len(accounts) > 0
    assert "account_name" in accounts[0]


def test_engine_load_and_analyze():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    results, coverage = e.load_and_analyze(SHADOW_PATH)
    assert len(results) > 0
    assert coverage["total_accounts"] > 0
    assert "family_counts" in coverage


# =========================================================================
# PatternBuilder
# =========================================================================

def test_builder_build():
    from patterns.pattern_builder import PatternBuilder
    b = PatternBuilder()
    p = b.build(
        pattern_id="test_pattern",
        family="TEST_FAMILY",
        description="Test pattern",
        priority=50,
        confidence=0.85,
        regex_pattern=r"\bTEST\b",
    )
    assert p.pattern_id == "test_pattern"
    assert p.family == "TEST_FAMILY"
    assert p.regex.search("TEST VALUE")
    assert not p.regex.search("NO MATCH")


def test_builder_from_dict():
    from patterns.pattern_builder import PatternBuilder
    b = PatternBuilder()
    data = {
        "pattern_id": "from_dict",
        "family": "DICT_FAMILY",
        "description": "From dict test",
        "priority": 30,
        "confidence": 0.9,
        "regex_pattern": r"\bDICT\b",
        "examples": ["DICT TEST"],
        "semantic_type": "asset",
        "standard_code": "AC.99",
    }
    p = b.from_dict(data)
    assert p.pattern_id == "from_dict"
    assert p.semantic_type == "asset"
    assert p.standard_code == "AC.99"
    assert p.examples == ["DICT TEST"]


def test_builder_from_dict_minimal():
    from patterns.pattern_builder import PatternBuilder
    b = PatternBuilder()
    data = {
        "pattern_id": "minimal",
        "family": "MINIMAL",
        "regex_pattern": r"\bMIN\b",
    }
    p = b.from_dict(data)
    assert p.pattern_id == "minimal"
    assert p.confidence == 0.7


def test_builder_validate_valid():
    from patterns.pattern_builder import PatternBuilder
    from patterns.pattern_catalog import AccountingPattern
    import re
    b = PatternBuilder()
    p = AccountingPattern(
        pattern_id="valid", family="VALID", description="Valid pattern",
        priority=1, confidence=0.9, regex=re.compile(r"\bVALID\b"),
    )
    assert b.validate_pattern(p) == []


def test_builder_validate_invalid():
    from patterns.pattern_builder import PatternBuilder
    from patterns.pattern_catalog import AccountingPattern
    import re
    b = PatternBuilder()
    p = AccountingPattern(
        pattern_id="", family="", description="",
        priority=1, confidence=0.9, regex=re.compile(r""),
    )
    errors = b.validate_pattern(p)
    assert len(errors) >= 3


def test_builder_validate_confidence():
    from patterns.pattern_builder import PatternBuilder
    from patterns.pattern_catalog import AccountingPattern
    import re
    b = PatternBuilder()
    p = AccountingPattern(
        pattern_id="test", family="TEST", description="Test",
        priority=1, confidence=1.5, regex=re.compile(r"\bTEST\b"),
    )
    errors = b.validate_pattern(p)
    assert any("confidence" in e for e in errors)


def test_builder_test_on_examples():
    from patterns.pattern_builder import PatternBuilder
    from patterns.pattern_catalog import PatternCatalog
    b = PatternBuilder()
    p = PatternCatalog.get_by_id("caja")
    assert p is not None
    results = b.test_pattern_on_examples(p)
    assert len(results["failed_positive"]) == 0
    assert len(results["failed_negative"]) == 0


def test_builder_test_on_examples_fails():
    from patterns.pattern_builder import PatternBuilder
    from patterns.pattern_catalog import AccountingPattern
    import re
    b = PatternBuilder()
    p = AccountingPattern(
        pattern_id="bad",
        family="BAD",
        description="Bad pattern",
        priority=1,
        confidence=0.5,
        regex=re.compile(r"\bNONEXISTENT\b"),
        examples=["CAJA GENERAL", "BANCO CHILE"],
    )
    results = b.test_pattern_on_examples(p)
    assert len(results["failed_positive"]) == 2


# =========================================================================
# PatternReport
# =========================================================================

def test_report_generate_coverage_md(tmp_path):
    from patterns.pattern_report import PatternReport
    from patterns.pattern_matcher import PatternMatch
    r = PatternReport(output_dir=tmp_path)
    results = [
        {"account": {"account_name": "CAJA"}, "matches": [
            PatternMatch(pattern_id="caja", family="CAJA", confidence=0.8, priority=60,
                         tokens_found=["CAJA"]),
        ], "normalized_name": "CAJA", "total_matches": 1, "is_classified": False, "best_match": None},
    ]
    coverage = {"total_accounts": 1, "total_unclassified": 1,
                "matched_all": 1, "matched_unclassified": 1,
                "coverage_unclassified_pct": 100.0, "coverage_all_pct": 100.0,
                "family_counts": {"CAJA": 1}, "family_unclassified": {"CAJA": 1}}
    path = r.generate_coverage_md(results, coverage)
    assert path.exists()
    content = path.read_text()
    assert "CAJA" in content
    assert "100.0%" in content or "100%" in content


def test_report_generate_statistics_xlsx(tmp_path):
    from patterns.pattern_report import PatternReport
    r = PatternReport(output_dir=tmp_path)
    coverage = {"total_accounts": 10, "total_unclassified": 5,
                "matched_all": 3, "matched_unclassified": 2,
                "coverage_unclassified_pct": 40.0, "coverage_all_pct": 30.0,
                "family_counts": {"CAJA": 2, "BANCOS": 1},
                "family_unclassified": {"CAJA": 2}}
    path = r.generate_statistics_xlsx([], coverage)
    assert path is not None
    assert path.exists()


def test_report_generate_unmatched_xlsx(tmp_path):
    from patterns.pattern_report import PatternReport
    r = PatternReport(output_dir=tmp_path)
    results = [
        {"account": {"account_name": "CAJA", "method": "unclassified",
                     "nature": "asset", "source_group": "test"},
         "matches": [type("Match", (), {"family": "CAJA"})()],
         "normalized_name": "CAJA", "total_matches": 1, "is_classified": False,
         "best_match": None},
        {"account": {"account_name": "ZZZZ", "method": "unclassified",
                     "nature": "unknown", "source_group": "test"},
         "matches": [], "normalized_name": "ZZZZ", "total_matches": 0,
         "is_classified": False, "best_match": None},
    ]
    path = r.generate_unmatched_xlsx(results)
    assert path is not None and path.exists()


def test_report_generate_examples_xlsx(tmp_path):
    from patterns.pattern_report import PatternReport
    from patterns.pattern_matcher import PatternMatch
    r = PatternReport(output_dir=tmp_path)
    results = [
        {"account": {"account_name": "CAJA", "method": "unclassified"},
         "matches": [PatternMatch(pattern_id="caja", family="CAJA",
                                  confidence=0.8, priority=60,
                                  matched_patterns=[r"\bCAJA\b"],
                                  tokens_found=["CAJA"],
                                  explanation="Match en CAJA")],
         "normalized_name": "CAJA", "total_matches": 1, "is_classified": False,
         "best_match": None},
    ]
    path = r.generate_examples_xlsx(results)
    assert path is not None and path.exists()


def test_report_generate_json(tmp_path):
    from patterns.pattern_report import PatternReport
    from patterns.pattern_matcher import PatternMatch
    r = PatternReport(output_dir=tmp_path)
    results = [
        {"account": {"account_name": "CAJA", "method": "unclassified",
                     "nature": "asset", "source_group": "test"},
         "matches": [PatternMatch(pattern_id="caja", family="CAJA",
                                  confidence=0.8, priority=60)],
         "normalized_name": "CAJA", "total_matches": 1, "is_classified": False,
         "best_match": PatternMatch(pattern_id="caja", family="CAJA",
                                    confidence=0.8, priority=60),
         },
    ]
    coverage = {"total_accounts": 1, "total_unclassified": 1,
                "matched_all": 1, "matched_unclassified": 1,
                "coverage_unclassified_pct": 100.0, "coverage_all_pct": 100.0,
                "family_counts": {"CAJA": 1}, "family_unclassified": {"CAJA": 1}}
    paths = r.generate_all(results, coverage)
    assert "json" in paths
    assert paths["json"].exists()


def test_report_generate_all(tmp_path):
    from patterns.pattern_report import PatternReport
    from patterns.pattern_matcher import PatternMatch
    r = PatternReport(output_dir=tmp_path)
    results = [
        {"account": {"account_name": "CAJA"}, "matches": [
            PatternMatch(pattern_id="caja", family="CAJA", confidence=0.8, priority=60)],
         "normalized_name": "CAJA", "total_matches": 1, "is_classified": False,
         "best_match": None},
    ]
    coverage = {"total_accounts": 1, "total_unclassified": 1,
                "matched_all": 1, "matched_unclassified": 1,
                "coverage_unclassified_pct": 100.0, "coverage_all_pct": 100.0,
                "family_counts": {"CAJA": 1}, "family_unclassified": {"CAJA": 1}}
    paths = r.generate_all(results, coverage)
    assert "coverage_md" in paths


# =========================================================================
# Integration — real data
# =========================================================================

def test_real_data_depreciacion_acumulada():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from patterns.pattern_engine import PatternEngine
    engine = PatternEngine()
    accounts = engine.load_shadow_data(SHADOW_PATH)
    names_with_dep = [
        a for a in accounts
        if "dep" in a.get("account_name", "").lower()
    ]
    assert len(names_with_dep) > 0, "No depreciation accounts found"
    matched = 0
    for acct in names_with_dep:
        matches = engine.analyze_account(acct)
        for m in matches:
            if m.family in ("DEPRECIACION_ACUMULADA", "DEPRECIACION_DEL_EJERCICIO"):
                matched += 1
                break
    assert matched > 0, (
        "No depreciation accounts matched by patterns"
    )


def test_real_data_unclassified_coverage():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from patterns.pattern_engine import PatternEngine
    engine = PatternEngine()
    results, coverage = engine.load_and_analyze(SHADOW_PATH)
    assert coverage["total_unclassified"] > 0
    assert coverage["matched_unclassified"] > 0
    assert coverage["coverage_unclassified_pct"] > 0


# =========================================================================
# Edge cases
# =========================================================================

def test_pattern_with_all_fields():
    from patterns.pattern_catalog import AccountingPattern
    import re
    p = AccountingPattern(
        pattern_id="full",
        family="FULL",
        description="Full test",
        priority=1,
        confidence=0.99,
        regex=re.compile(r"\bFULL\b"),
        keywords_forbidden=["NO"],
        examples=["FULL MATCH"],
        negative_examples=["NO MATCH"],
        semantic_type="asset",
        standard_code="AC.99",
        financial_statement="balance_sheet",
        economic_nature="debit",
        expected_side="debit",
        contra_account="TEST",
        learnable=True,
    )
    assert p.pattern_id == "full"
    assert p.keywords_forbidden == ["NO"]


def test_normalizer_cxp_variations():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    assert n.normalize("CXP") == "CUENTAS POR PAGAR"
    assert n.normalize("CxP") == "CUENTAS POR PAGAR"
    assert n.normalize("cxp") == "CUENTAS POR PAGAR"


def test_normalizer_cxc_variations():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    assert n.normalize("CXC") == "CUENTAS POR COBRAR"
    assert n.normalize("CxC") == "CUENTAS POR COBRAR"


def test_normalizer_with_special_chars():
    from patterns.pattern_normalizer import PatternNormalizer
    n = PatternNormalizer()
    result = n.normalize("CUENTA [CORRIENTE] {N° 123}")
    assert "[" not in result
    assert "]" not in result
    assert "{" not in result
    assert "}" not in result
    assert "°" not in result


def test_matcher_match_returns_correct_fields():
    from patterns.pattern_catalog import PatternCatalog
    from patterns.pattern_matcher import PatternMatcher
    m = PatternMatcher()
    p = PatternCatalog.get_by_id("iva_credito")
    assert p is not None
    result = m.match("IVA CREDITO FISCAL", p)
    assert result is not None
    assert result.pattern_id == "iva_credito"
    assert result.family == "IVA_CREDITO"
    assert result.confidence == p.confidence
    assert result.priority == p.priority
    assert len(result.tokens_found) > 0


def test_engine_analyze_already_classified():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    matches = e.analyze_account({
        "account_name": "CAJA GENERAL",
        "method": "code",
        "final_code": "AC.07",
    })
    assert len(matches) == 1


def test_engine_families_summary_keys():
    from patterns.pattern_engine import PatternEngine
    e = PatternEngine()
    summary = e.families_summary()
    for s in summary:
        assert "family" in s
        assert "patterns" in s
        assert "min_priority" in s


def test_builder_from_dict_missing_fields():
    from patterns.pattern_builder import PatternBuilder
    b = PatternBuilder()
    data = {
        "pattern_id": "test",
        "family": "TEST",
        "description": "Test",
        "priority": 5,
        "confidence": 0.8,
    }
    # Missing regex_pattern defaults to empty pattern (matches anything)
    p = b.from_dict(data)
    assert p.pattern_id == "test"
    assert p.regex.search("ANYTHING")


def test_report_output_dir_creation(tmp_path):
    from patterns.pattern_report import PatternReport
    sub = tmp_path / "nested" / "dir"
    r = PatternReport(output_dir=sub)
    assert sub.exists()


# =========================================================================
# Shadow mode — pattern runner
# =========================================================================

def test_run_pattern_analysis_script():
    if not SHADOW_PATH.exists():
        pytest.skip("shadow_data.json not found")
    from patterns.run_pattern_analysis import main
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        main(shadow_path=SHADOW_PATH, output_dir=out)
        assert (out / "pattern_coverage.md").exists()
        assert (out / "pattern_analysis.json").exists()


def test_run_pattern_analysis_missing_shadow(tmp_path):
    from patterns.run_pattern_analysis import main
    fake = tmp_path / "nonexistent.json"
    with pytest.raises(SystemExit):
        main(shadow_path=fake, output_dir=tmp_path)
