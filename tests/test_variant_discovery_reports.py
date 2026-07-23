import pytest
import json
from pathlib import Path

from knowledge.variant_discovery.clusterer import VariantCluster, VariantClusterer
from knowledge.variant_discovery.engine import VariantDiscoveryEngine
from knowledge.variant_discovery.reports import generate_reports


def _make_result(n_accounts: int = 10):
    """Build a realistic result dict for report generation."""
    clusterer = VariantClusterer(threshold=0.60)
    accounts = [
        {"account_name": f"Cuenta {i}", "frecuencia": i + 1}
        for i in range(n_accounts)
    ]
    clusterer.cluster(accounts)
    clusterer.compute_confidences()
    clusterer.suggest_concepts([
        {"codigo": "AC.01", "nombre": "Caja y Bancos",
         "variantes": ["Caja General", "Caja Chica"]},
        {"codigo": "ER.01", "nombre": "Ventas", "variantes": []},
    ])

    clusters = clusterer.clusters
    multi = clusterer.get_multi_member()
    singletons = clusterer.get_singletons()
    high_conf = [c for c in multi if c.confidence >= 0.70]
    needs_review = [c for c in multi if c.confidence < 0.70]

    return {
        "clusters": clusters,
        "multi_member": multi,
        "singletons": singletons,
        "high_confidence": high_conf,
        "needs_review": needs_review,
        "total_accounts": n_accounts,
        "total_clusters": len(clusters),
        "multi_clusters": len(multi),
        "singleton_count": len(singletons),
        "high_confidence_count": len(high_conf),
        "needs_review_count": len(needs_review),
    }


class TestReports:
    def test_clusters_xlsx(self, tmp_path):
        result = _make_result(15)
        paths = generate_reports(result, tmp_path)
        assert (tmp_path / "clusters.xlsx").exists()
        assert paths["clusters"] == tmp_path / "clusters.xlsx"

    def test_concept_suggestions_xlsx(self, tmp_path):
        result = _make_result(20)
        paths = generate_reports(result, tmp_path)
        assert (tmp_path / "concept_suggestions.xlsx").exists()

    def test_high_confidence_xlsx(self, tmp_path):
        result = _make_result(30)
        generate_reports(result, tmp_path)
        assert (tmp_path / "high_confidence.xlsx").exists()

    def test_needs_review_xlsx(self, tmp_path):
        result = _make_result(30)
        # Set some clusters to low confidence
        for c in result["multi_member"]:
            c.confidence = 0.5
        result["high_confidence"] = []
        result["needs_review"] = result["multi_member"]
        result["high_confidence_count"] = 0
        result["needs_review_count"] = len(result["needs_review"])
        paths = generate_reports(result, tmp_path)
        assert (tmp_path / "needs_review.xlsx").exists()

    def test_variant_statistics_json(self, tmp_path):
        result = _make_result(25)
        generate_reports(result, tmp_path)
        p = tmp_path / "variant_statistics.json"
        assert p.exists()
        with open(p) as f:
            data = json.load(f)
        assert data["total_accounts"] == 25
        assert data["total_clusters"] >= 1

    def test_clusters_md(self, tmp_path):
        result = _make_result(20)
        generate_reports(result, tmp_path)
        assert (tmp_path / "clusters.md").exists()
        md = (tmp_path / "clusters.md").read_text(encoding="utf-8")
        assert "Variant Discovery Report" in md

    def test_all_outputs_exist(self, tmp_path):
        result = _make_result(50)
        paths = generate_reports(result, tmp_path)
        expected = ["clusters.xlsx", "concept_suggestions.xlsx",
                    "high_confidence.xlsx", "needs_review.xlsx",
                    "variant_statistics.json", "clusters.md"]
        for name in expected:
            assert (tmp_path / name).exists(), f"Missing {name}"

    def test_large_result(self, tmp_path):
        clusterer = VariantClusterer(threshold=0.60)
        accounts = [
            {"account_name": f"Gasto de {chr(65+i)}", "frecuencia": i}
            for i in range(100)
        ]
        clusterer.cluster(accounts)
        clusterer.compute_confidences()
        clusterer.suggest_concepts([])
        result = {
            "clusters": clusterer.clusters,
            "multi_member": clusterer.get_multi_member(),
            "singletons": clusterer.get_singletons(),
            "high_confidence": [c for c in clusterer.clusters if c.confidence >= 0.70],
            "needs_review": [c for c in clusterer.clusters if 0 < c.confidence < 0.70],
            "total_accounts": 100,
            "total_clusters": len(clusterer.clusters),
            "multi_clusters": len(clusterer.get_multi_member()),
            "singleton_count": len(clusterer.get_singletons()),
            "high_confidence_count": sum(1 for c in clusterer.clusters if c.confidence >= 0.70),
            "needs_review_count": sum(1 for c in clusterer.clusters if 0 < c.confidence < 0.70),
        }
        generate_reports(result, tmp_path)
        assert (tmp_path / "clusters.xlsx").exists()


if __name__ == "__main__":
    pytest.main([__file__])
