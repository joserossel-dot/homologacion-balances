import pytest
from knowledge.discovery.token_statistics import TokenStatistics


class TestTokenStatistics:
    def test_empty(self):
        ts = TokenStatistics()
        r = ts.analyze([])
        assert r['total_names'] == 0

    def test_single_name(self):
        ts = TokenStatistics()
        r = ts.analyze(["Caja y Bancos"])
        assert r['total_names'] == 1
        assert r['total_tokens'] >= 1

    def test_multiple_names(self):
        ts = TokenStatistics()
        r = ts.analyze(["Caja General", "Banco Estado", "Proveedores Nacionales"])
        assert r['total_names'] == 3
        assert r['unique_tokens'] >= 5

    def test_top_tokens(self):
        ts = TokenStatistics()
        r = ts.analyze(["Gastos Administracion", "Gastos Ventas", "Gastos Generales"])
        top = r['top_tokens']
        gastos_found = any(t == 'gastos' for t, _ in top)
        assert gastos_found
        assert r['unique_tokens'] >= 3

    def test_first_token_clusters(self):
        ts = TokenStatistics()
        r = ts.analyze([
            "Gastos Administracion",
            "Gastos Ventas",
            "Banco Estado",
            "Banco Chile",
        ])
        clusters = r['first_token_clusters']
        assert 'gastos' in clusters
        assert 'banco' in clusters

    def test_custom_stopwords(self):
        ts = TokenStatistics(stopwords={"de", "la", "y"})
        r = ts.analyze(["Gastos de la casa y el auto"])
        # "de", "la", "y" should be filtered from tokens
        tokens_set = set(t for t, _ in r['top_tokens'])
        assert 'de' not in tokens_set
        assert 'y' not in tokens_set


if __name__ == "__main__":
    pytest.main([__file__])
