"""Tests para SemanticMatcher v1."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from semantic.matcher import SemanticMatcher
from semantic.models import SemanticMatch
from semantic.normalizer import SemanticNormalizer
from semantic.scorer import Scorer

# ── Minimal test catalog ──────────────────────────────────────────────

MINI_CATALOG = {
    "catalog": {"version": "1.0", "generated_date": "2026-07-22", "total_concepts": 6},
    "concepts": [
        {
            "id": "CONCEPT_001", "name": "CAJA", "type": "ACTIVO",
            "expected_cmcc_code": "AC.01", "confidence": "ALTA",
            "keywords": ["caja", "caja general", "caja chica", "efectivo"],
            "synonyms": ["disponible", "efectivo y equivalente"],
            "abbreviations": ["c", "cja"],
            "ocr_variants": ["caxa"], "common_errors": [],
            "frequency": 106, "family_count": 16, "pct_of_gap": 1.06,
        },
        {
            "id": "CONCEPT_002", "name": "BANCOS", "type": "ACTIVO",
            "expected_cmcc_code": "AC.01", "confidence": "ALTA",
            "keywords": ["banco", "bancos", "cuenta corriente"],
            "synonyms": ["disponible bancario", "efectivo en banco"],
            "abbreviations": ["cta cte", "cc", "bco"],
            "ocr_variants": ["banc0s"], "common_errors": [],
            "frequency": 320, "family_count": 125, "pct_of_gap": 3.2,
        },
        {
            "id": "CONCEPT_003", "name": "CLIENTES", "type": "ACTIVO",
            "expected_cmcc_code": "AC.03", "confidence": "ALTA",
            "keywords": ["clientes", "deudores comerciales", "cuentas cobrar"],
            "synonyms": ["deudores", "cuentas por cobrar"],
            "abbreviations": ["cxc"],
            "ocr_variants": [], "common_errors": ["clentes"],
            "frequency": 249, "family_count": 84, "pct_of_gap": 2.49,
        },
        {
            "id": "CONCEPT_004", "name": "PROVEEDORES", "type": "PASIVO",
            "expected_cmcc_code": "PC.01", "confidence": "ALTA",
            "keywords": ["proveedores", "cuentas pagar", "acreedores"],
            "synonyms": ["acreedores comerciales", "cuentas por pagar"],
            "abbreviations": ["cxp"],
            "ocr_variants": [], "common_errors": ["provedores"],
            "frequency": 280, "family_count": 75, "pct_of_gap": 2.8,
        },
        {
            "id": "CONCEPT_005", "name": "CAPITAL", "type": "PATRIMONIO",
            "expected_cmcc_code": "PAT.01", "confidence": "ALTA",
            "keywords": ["capital", "capital emitido", "capital pagado", "capital social"],
            "synonyms": ["aporte capital", "capital suscrito"],
            "abbreviations": ["cap"],
            "ocr_variants": [], "common_errors": ["capìtal"],
            "frequency": 137, "family_count": 20, "pct_of_gap": 1.37,
        },
        {
            "id": "CONCEPT_006", "name": "DEPRECIACION", "type": "PERDIDA",
            "expected_cmcc_code": "ER.07", "confidence": "MEDIA",
            "keywords": ["depreciacion", "amortizacion", "deterioro"],
            "synonyms": ["depreciacion acumulada", "amortizacion acumulada"],
            "abbreviations": ["depr"],
            "ocr_variants": ["depresacion"], "common_errors": [],
            "frequency": 321, "family_count": 142, "pct_of_gap": 3.21,
        },
    ],
}


@pytest.fixture
def matcher():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(MINI_CATALOG, f, ensure_ascii=False)
        f.flush()
        tmp_path = f.name
    m = SemanticMatcher(tmp_path)
    yield m
    import os
    os.unlink(tmp_path)


@pytest.fixture
def normalizer():
    return SemanticNormalizer(MINI_CATALOG["concepts"])


# ── Normalizer Tests ──────────────────────────────────────────────────

class TestNormalizer:
    def test_normalize_basic(self, normalizer):
        assert normalizer.normalize("CAJA GENERAL") == "caja general"
        assert normalizer.normalize("Remuneración") == "remuneracion"
        assert normalizer.normalize("  Cta.  Cte.  ") == "cta cte"

    def test_normalize_ocr(self, normalizer):
        assert normalizer.normalize("banc0s") == "bancos"

    def test_stop_words_removal(self, normalizer):
        cleaned = normalizer.remove_noise("gastos de la administracion y ventas")
        assert "de" not in cleaned
        assert "la" not in cleaned
        assert "y" not in cleaned
        assert "gastos" in cleaned
        assert "administracion" in cleaned
        assert "ventas" in cleaned

    def test_root_word(self, normalizer):
        assert normalizer.root_word("CAPITAL EMITIDO") == "capital"
        assert normalizer.root_word("MUEBLES Y UTILES") == "muebles"
        assert normalizer.root_word("") is None


# ── Tier Tests ────────────────────────────────────────────────────────

class TestTier1ExactKeyword:
    def test_exact_keyword_match(self, matcher):
        m = matcher.match("caja")
        assert m.concept_name == "CAJA"
        assert m.match_tier == 1
        assert m.confidence == "EXACT"
        assert m.expected_cmcc == "AC.01"

    def test_exact_keyword_multiple_words(self, matcher):
        m = matcher.match("cuenta corriente")
        assert m.concept_name == "BANCOS"
        assert m.match_tier == 1


class TestTier2ExactSynonym:
    def test_exact_synonym(self, matcher):
        m = matcher.match("cuentas por cobrar")
        assert m.concept_name == "CLIENTES"
        assert m.match_tier == 2
        assert m.matched_synonym is not None

    def test_exact_synonym_aporte(self, matcher):
        m = matcher.match("aporte capital")
        assert m.concept_name == "CAPITAL"
        assert m.match_tier == 2


class TestTier3Abbreviation:
    def test_abbreviation_cxc(self, matcher):
        m = matcher.match("cxc")
        assert m.concept_name == "CLIENTES"
        assert m.match_tier == 3, f"Expected tier 3, got {m.match_tier}: {m}"

    def test_abbreviation_cxp(self, matcher):
        m = matcher.match("cxp")
        assert m.concept_name == "PROVEEDORES"
        assert m.match_tier == 3, f"Expected tier 3, got {m.match_tier}: {m}"

    def test_abbreviation_depr(self, matcher):
        m = matcher.match("depr")
        assert m.concept_name == "DEPRECIACION"
        assert m.match_tier == 3, f"Expected tier 3, got {m.match_tier}: {m}"


class TestTier4FuzzyKeyword:
    def test_fuzzy_keyword_provedores(self, matcher):
        m = matcher.match("provedores")
        assert m.concept_name == "PROVEEDORES"
        assert m.match_tier == 4
        assert m.confidence in ("HIGH", "VERY_HIGH")

    def test_fuzzy_keyword_depresacion(self, matcher):
        m = matcher.match("depresacion")
        assert m.concept_name == "DEPRECIACION"
        assert m.match_tier == 4


class TestTier5FuzzySynonym:
    def test_fuzzy_synonym(self, matcher):
        m = matcher.match("acreedor comercial")
        assert m.concept_name == "PROVEEDORES"
        assert m.match_tier == 5


class TestTier6RootWord:
    def test_root_word_standalone(self, matcher):
        """'capital' alone matches as exact keyword (Tier 1), not root word."""
        m = matcher.match("capital")
        assert m.concept_name == "CAPITAL"
        assert m.match_tier == 1

    def test_root_word_with_unknown_words(self, matcher):
        """Name where only the root word matches the concept."""
        m = matcher.match("bancos internacionales regionales")
        assert m.concept_name == "BANCOS"


# ── UNKNOWN / Edge Cases ─────────────────────────────────────────────

class TestUnknown:
    def test_empty_name(self, matcher):
        m = matcher.match("")
        assert m.is_unknown
        assert m.concept_id is None

    def test_short_name(self, matcher):
        m = matcher.match("ab")
        assert m.is_unknown

    def test_noise_only(self, matcher):
        m = matcher.match("total de la cuenta")
        assert m.is_unknown

    def test_nonsense_text(self, matcher):
        m = matcher.match("zxqwyz klmnop")
        assert m.is_unknown


# ── Integration Tests ────────────────────────────────────────────────

class TestIntegration:
    def test_batch_match(self, matcher):
        names = ["caja", "clientes", "bancos", "capital social", "xyzxyz"]
        results = matcher.match_batch(names)
        assert len(results) == 5
        assert all(isinstance(r, SemanticMatch) for r in results)
        assert not results[0].is_unknown
        assert not results[1].is_unknown
        assert not results[2].is_unknown
        assert not results[3].is_unknown
        assert results[4].is_unknown

    def test_explain(self, matcher):
        expl = matcher.explain("caja")
        assert "CAJA" in expl
        assert "AC.01" in expl
        assert "keyword exacto" in expl

        expl2 = matcher.explain("zxqwyz klmnop")
        assert "UNKNOWN" in expl2

    def test_get_concept(self, matcher):
        c = matcher.get_concept("CONCEPT_001")
        assert c is not None
        assert c["name"] == "CAJA"

        c2 = matcher.get_concept("CONCEPT_999")
        assert c2 is None


class TestScorer:
    def test_scorer_direct(self):
        scorer = Scorer()
        concept = {
            "id": "CONCEPT_001", "name": "CAJA", "type": "ACTIVO",
            "expected_cmcc_code": "AC.01",
            "keywords": ["caja", "efectivo"],
            "synonyms": ["disponible"],
            "abbreviations": ["c"],
        }
        # Exact match
        result = scorer.evaluate_concept("caja", concept, "caja")
        assert result is not None
        assert result.score >= 0.95
        assert result.match_tier == 1

        # Fuzzy match
        result = scorer.evaluate_concept("caxa", concept, None)
        assert result is not None
        assert result.match_tier == 4
        assert result.score >= 0.50

        # No match — different concept
        result = scorer.evaluate_concept("proveedores", concept, None)
        assert result is None  # score < 0.50 → None
