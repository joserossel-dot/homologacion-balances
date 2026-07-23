import pytest
import json
import tempfile
from pathlib import Path

from knowledge.variant_discovery.similarity import (
    tokenize, trigrams, jaccard_similarity, trigram_similarity,
    levenshtein_similarity, _levenshtein, TFIDFVectorizer, MultiMetricScorer,
)
from knowledge.variant_discovery.clusterer import VariantCluster, VariantClusterer
from knowledge.variant_discovery.engine import VariantDiscoveryEngine


# ─── Similarity Tests ──────────────────────────────────────────────

class TestTokenize:
    def test_basic(self):
        assert tokenize("Gastos de Administracion") == ["gastos", "administracion"]

    def test_stopwords_removed(self):
        assert "de" not in tokenize("Gastos de Administracion")

    def test_punctuation(self):
        t = tokenize("Caja, y Bancos")
        assert "caja" in t
        assert "bancos" in t

    def test_short_tokens_removed(self):
        assert tokenize("A B C") == []

    def test_empty(self):
        assert tokenize("") == []


class TestTrigrams:
    def test_basic(self):
        t = trigrams("caja")
        assert len(t) >= 1

    def test_short_string(self):
        assert trigrams("a") == set()

    def test_similarity(self):
        a = trigrams("administracion")
        b = trigrams("administrativo")
        assert len(a & b) > 0


class TestJaccard:
    def test_identical(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0

    def test_partial(self):
        s = jaccard_similarity({"a", "b"}, {"a", "c"})
        assert 0 < s < 1.0


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein_similarity("caja", "caja") == 1.0

    def test_completely_different(self):
        s = levenshtein_similarity("abc", "xyz")
        assert s < 0.5

    def test_similar(self):
        s = levenshtein_similarity("administracion", "administrativo")
        assert s > 0.5

    def test_empty(self):
        assert levenshtein_similarity("", "test") == 0.0

    def test_both_empty(self):
        assert levenshtein_similarity("", "") == 0.0

    def test_prefix(self):
        s = levenshtein_similarity("casa", "caso")
        assert s > 0.5


class TestTFIDF:
    def test_vectorizer(self):
        tfidf = TFIDFVectorizer(["gastos administracion", "gastos ventas"])
        vec = tfidf.transform("gastos administracion")
        assert len(vec) > 0

    def test_cosine_similar(self):
        tfidf = TFIDFVectorizer(["caja general", "banco estado"])
        va = tfidf.transform("caja general")
        vb = tfidf.transform("caja general")
        assert tfidf.cosine_similarity(va, vb) >= 0.99

    def test_cosine_different(self):
        tfidf = TFIDFVectorizer(["caja general", "banco estado", "gastos ventas"])
        va = tfidf.transform("caja general")
        vb = tfidf.transform("banco estado")
        assert tfidf.cosine_similarity(va, vb) < 1.0

    def test_empty_vector(self):
        tfidf = TFIDFVectorizer(["test"])
        assert tfidf.cosine_similarity({}, {"a": 1.0}) == 0.0


class TestMultiMetricScorer:
    def test_identical_names(self):
        ss = MultiMetricScorer()
        s = ss.combined_score("Caja General", "Caja General")
        # Without TF-IDF corpus, max is 0.85 (0.20+0.15+0.10+0.20+0.20+0)
        assert s >= 0.80

    def test_similar_names(self):
        ss = MultiMetricScorer()
        s = ss.combined_score("Gastos de Administracion", "Gastos Administrativos")
        assert s > 0.3

    def test_different_names(self):
        ss = MultiMetricScorer()
        s = ss.combined_score("Caja", "Depreciacion")
        assert s < 0.5

    def test_empty(self):
        ss = MultiMetricScorer()
        s = ss.combined_score("", "test")
        assert s == 0.0

    def test_are_equivalent_true(self):
        ss = MultiMetricScorer()
        eq, s = ss.are_equivalent("Caja General", "Caja General")
        assert eq

    def test_are_equivalent_normalized(self):
        ss = MultiMetricScorer()
        eq, s = ss.are_equivalent("Caja General", "caja general")
        assert eq

    def test_are_equivalent_false(self):
        ss = MultiMetricScorer()
        eq, s = ss.are_equivalent("Caja", "Depreciacion Acumulada")
        assert not eq

    def test_from_names(self):
        ss = MultiMetricScorer.from_names(["caja general", "banco estado"])
        s = ss.combined_score("caja general", "caja general")
        assert s >= 0.90


# ─── Cluster Tests ─────────────────────────────────────────────────

class TestVariantCluster:
    def test_create(self):
        c = VariantCluster("VC00001")
        assert c.id == "VC00001"
        assert c.n_members == 0

    def test_add_member(self):
        c = VariantCluster("VC00001")
        c.add_member("Cuenta 1", freq=5, empresa="Emp1", monto=100.0)
        assert c.n_members == 1
        assert c.frecuencia == 5
        assert c.n_empresas == 1
        assert c.monto_acumulado == 100.0

    def test_add_duplicate(self):
        c = VariantCluster("VC00001")
        c.add_member("C1")
        c.add_member("C1")
        assert c.n_members == 1

    def test_add_member_with_doc(self):
        c = VariantCluster("VC00001")
        c.add_member("C1", documento="doc1")
        c.add_member("C2", documento="doc2")
        assert c.n_documentos == 2

    def test_to_dict(self):
        c = VariantCluster("VC00001")
        c.add_member("C1", freq=5, empresa="E1")
        d = c.to_dict()
        assert d["id"] == "VC00001"
        assert d["n_members"] == 1
        assert d["frecuencia"] == 5


class TestVariantClusterer:
    def test_empty(self):
        c = VariantClusterer()
        clusters = c.cluster([])
        assert clusters == []

    def test_single(self):
        c = VariantClusterer()
        clusters = c.cluster([{"account_name": "Caja", "frecuencia": 1}])
        assert len(clusters) == 1
        assert len(c.get_singletons()) == 1

    def test_identical_names(self):
        c = VariantClusterer(threshold=0.60)
        clusters = c.cluster([
            {"account_name": "Caja General", "frecuencia": 5},
            {"account_name": "Caja General", "frecuencia": 3},
        ])
        # Same name → same cluster, n_members=1 (unique), but frecuencia=8
        assert len(clusters) == 1
        assert clusters[0].frecuencia == 8

    def test_similar_names(self):
        c = VariantClusterer(threshold=0.60)
        clusters = c.cluster([
            {"account_name": "Gastos de Administracion", "frecuencia": 10},
            {"account_name": "Gastos Administrativos", "frecuencia": 5},
        ])
        multi = c.get_multi_member()
        assert len(multi) >= 1

    def test_different_names(self):
        c = VariantClusterer(threshold=0.60)
        clusters = c.cluster([
            {"account_name": "Caja", "frecuencia": 1},
            {"account_name": "Depreciacion", "frecuencia": 1},
        ])
        assert len(c.get_multi_member()) == 0
        assert len(c.get_singletons()) == 2

    def test_compute_confidences(self):
        c = VariantClusterer()
        c.cluster([
            {"account_name": "Caja", "frecuencia": 5},
            {"account_name": "Banco", "frecuencia": 3},
        ])
        c.compute_confidences()
        for cl in c.clusters:
            assert 0 < cl.confidence <= 1.0

    def test_suggest_concepts(self):
        c = VariantClusterer()
        c.cluster([{"account_name": "Caja General", "frecuencia": 1}])
        concept_db = [
            {"codigo": "AC.01", "nombre": "Caja y Bancos",
             "variantes": ["Caja General", "Caja Chica"]},
        ]
        c.suggest_concepts(concept_db)
        assert "AC.01" in c.clusters[0].suggested_concept

    def test_suggest_concepts_empty_db(self):
        c = VariantClusterer()
        c.cluster([{"account_name": "Caja", "frecuencia": 1}])
        c.suggest_concepts([])
        assert "SIN CONCEPTO" in c.clusters[0].suggested_concept

    def test_name_with_nan(self):
        c = VariantClusterer()
        clusters = c.cluster([
            {"account_name": "Caja", "frecuencia": 1},
            {"account_name": "nan", "frecuencia": 1},
        ])
        assert len(clusters) >= 1


# ─── Engine Tests ──────────────────────────────────────────────────

class TestEngine:
    def test_init(self, tmp_path):
        cmcc = tmp_path / "cmcc.json"
        cmcc.write_text("[]", encoding="utf-8")
        e = VariantDiscoveryEngine(cmcc_path=cmcc, threshold=0.60)
        assert e.threshold == 0.60

    def test_load_unclassified(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({
            "account_name": ["Caja General", "Banco Estado"],
            "frecuencia": [5, 3],
            "classification_amount": [100.0, 200.0],
        })
        p = tmp_path / "test.xlsx"
        df.to_excel(p, index=False)
        e = VariantDiscoveryEngine(cmcc_path=tmp_path / "nonexistent.json")
        e.load_unclassified(p)
        assert len(e.accounts) == 2

    def test_load_cmcc_shadow(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({
            "Cuenta": ["Caja Chica"],
            "Documento": ["test.pdf"],
            "Score": [1.0],
            "Código sugerido": ["AC.01"],
        })
        p = tmp_path / "shadow.xlsx"
        df.to_excel(p, index=False)
        e = VariantDiscoveryEngine()
        e.load_cmcc_shadow(p)
        assert len(e.accounts) == 1

    def test_run_simple(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({
            "account_name": ["Caja General", "Caja Chica", "Banco Estado"],
            "frecuencia": [5, 3, 2],
            "classification_amount": [100.0, 50.0, 200.0],
        })
        p = tmp_path / "test.xlsx"
        df.to_excel(p, index=False)
        cmcc = tmp_path / "cmcc.json"
        cmcc.write_text(json.dumps([
            {"codigo": "AC.01", "nombre": "Caja y Bancos",
             "variantes": ["Caja General"]},
        ]), encoding="utf-8")
        e = VariantDiscoveryEngine(cmcc_path=cmcc, threshold=0.60)
        e.load_unclassified(p)
        r = e.run()
        assert r["total_accounts"] == 3
        assert r["total_clusters"] > 0


# ─── Runner test ──────────────────────────────────────────────────

class TestRunner:
    def test_import(self):
        from scripts.run_variant_discovery import main as runner_main
        assert callable(runner_main)


if __name__ == "__main__":
    pytest.main([__file__])
