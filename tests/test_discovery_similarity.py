import pytest
from knowledge.discovery.similarity import SimilarityScorer, AccountNormalizer


class TestAccountNormalizer:
    def test_normalize(self):
        n = AccountNormalizer()
        r = n.normalize("Caja y Bancos")
        assert r is not None
        assert isinstance(r, str)

    def test_normalize_empty(self):
        n = AccountNormalizer()
        assert n.normalize("") == ""
        assert n.normalize(None) == ""


class TestSimilarityScorer:
    def setup_method(self):
        self.s = SimilarityScorer()

    def test_token_overlap_identical(self):
        assert self.s.token_overlap({"a", "b"}, {"a", "b"}) == 1.0

    def test_token_overlap_empty(self):
        assert self.s.token_overlap(set(), {"a"}) == 0.0

    def test_jaccard_identical(self):
        assert self.s.jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_jaccard_empty(self):
        assert self.s.jaccard(set(), {"a"}) == 0.0

    def test_rapidfuzz_ratio(self):
        r = self.s.rapidfuzz_ratio("caja bancos", "caja bancos")
        assert r >= 0.9

    def test_rapidfuzz_ratio_empty(self):
        assert self.s.rapidfuzz_ratio("", "test") == 0.0

    def test_rapidfuzz_partial(self):
        r = self.s.rapidfuzz_partial("caja bancos", "caja")
        assert r >= 0.5

    def test_rapidfuzz_token_sort(self):
        r = self.s.rapidfuzz_token_sort("bancos caja", "caja bancos")
        assert r >= 0.9

    def test_rapidfuzz_token_set(self):
        r = self.s.rapidfuzz_token_set("caja y bancos", "caja bancos")
        assert r >= 0.8

    def test_abbreviation_score(self):
        s = self.s.abbreviation_score("cta cte", "cuenta corriente")
        assert s > 0

    def test_abbreviation_score_none(self):
        s = self.s.abbreviation_score("casa", "perro")
        assert s == 0.0

    def test_word_order_score(self):
        s = self.s.word_order_score({"a", "b", "c"}, {"a", "b", "d"})
        assert s > 0

    def test_prefix_suffix_score(self):
        s = self.s.prefix_suffix_score("administracion", "administrativo")
        assert s > 0

    def test_combined_score(self):
        result = self.s.combined_score("Gastos de Administración", "Gastos Administrativos")
        assert 'final' in result
        assert result['final'] > 0

    def test_are_equivalent_true(self):
        eq, score, _ = self.s.are_equivalent("Caja General", "Caja General")
        assert eq

    def test_are_equivalent_false(self):
        eq, score, _ = self.s.are_equivalent("Caja", "Depreciacion Acumulada")
        assert not eq

    def test_custom_stopwords(self):
        s = SimilarityScorer(stopwords={"de", "la"})
        r = s.combined_score("Caja de la", "Caja")
        assert r['final'] > 0


if __name__ == "__main__":
    pytest.main([__file__])
