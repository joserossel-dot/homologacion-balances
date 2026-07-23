import pytest
import json
from pathlib import Path

from pipeline.cmcc_classifier import CMCCClassifier


@pytest.fixture(scope="module")
def classifier():
    return CMCCClassifier()


class TestCMCCClassifier:
    def test_classify_empty(self, classifier):
        r = classifier.classify("")
        assert r["code"] is None
        assert r["score"] == 0.0

    def test_classify_none(self, classifier):
        r = classifier.classify(None)
        assert r["code"] is None

    def test_classify_exact_variant(self, classifier):
        r = classifier.classify("Caja General")
        assert r["code"] == "AC.01"
        assert r["score"] >= 0.90

    def test_classify_exact_variant_case(self, classifier):
        r = classifier.classify("caja general")
        assert r["score"] >= 0.90

    def test_classify_bank(self, classifier):
        r = classifier.classify("Banco Santander")
        assert r["code"] == "AC.01"
        assert r["score"] >= 0.90

    def test_classify_bank_bci(self, classifier):
        r = classifier.classify("Banco Bci USD")
        assert r["code"] == "AC.01"
        assert r["score"] >= 0.90

    def test_classify_unknown(self, classifier):
        r = classifier.classify("ZXCVBNM ASDFGHJK")
        assert r["score"] < 0.90

    def test_classify_proveedores(self, classifier):
        r = classifier.classify("Proveedores Nacionales")
        assert r["code"] is not None

    def test_classify_depreciacion(self, classifier):
        r = classifier.classify("Depreciacion Acumulada")
        if r["score"] >= 0.90:
            assert r["code"] is not None

    def test_classify_returns_all_keys(self, classifier):
        r = classifier.classify("Caja")
        expected = {"code", "concept", "score", "matched_variant",
                    "matched_concept", "method", "evidence"}
        assert set(r.keys()) == expected

    def test_classify_batch(self, classifier):
        results = classifier.classify_batch(["Caja General", "Banco", "XYZ Unknown"])
        assert len(results) == 3
        assert results[0]["score"] >= 0.90
        assert results[2]["score"] < 0.90


class TestCMCCClassifierEdgeCases:
    def test_special_chars(self, classifier):
        r = classifier.classify("CAJA 5.519,080 PROVEEDORES")
        assert r["code"] is not None

    def test_mixed_case(self, classifier):
        r = classifier.classify("cAjA y BaNcOs")
        assert r["score"] >= 0.90

    def test_partial_match(self, classifier):
        r = classifier.classify("CAJA")
        assert r["score"] > 0

    def test_with_numbers(self, classifier):
        r = classifier.classify("Banco BCI 123")
        assert r["code"] is not None


if __name__ == "__main__":
    pytest.main([__file__])
