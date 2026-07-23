import pytest
import tempfile
from pathlib import Path
from knowledge.concept import Concept
from knowledge.repository import Repository
from knowledge.metrics import Metrics


@pytest.fixture
def repo():
    r = Repository("/tmp/_test_metrics.json")
    r.add(Concept(id="AC.01", codigo="AC.01", nombre="Caja",
                  categoria="activo_corriente", tipo_estado_financiero="balance",
                  sinonimos=["Efectivo"], abreviaturas=["efvo"],
                  variantes=["Caja Chica"], confidence=0.9,
                  version="1.0.0", ultima_revision="2026-07-08"))
    r.add(Concept(id="PC.01", codigo="PC.01", nombre="Proveedores",
                  categoria="pasivo_corriente", tipo_estado_financiero="balance",
                  sinonimos=[], abreviaturas=[],
                  variantes=[], confidence=0.5,
                  version="1.0.0", ultima_revision="2026-07-08"))
    r.add(Concept(id="ER.01", codigo="ER.01", nombre="Ingresos",
                  categoria="ingreso", tipo_estado_financiero="resultado",
                  sinonimos=["Ventas"], abreviaturas=["ing"],
                  variantes=["Venta A", "Venta B", "Venta C"],
                  confidence=0.3, version="1.0.0", ultima_revision="2026-07-08"))
    return r


class TestMetrics:
    def test_concept_count(self, repo):
        m = Metrics(repo)
        assert m.concept_count == 3

    def test_total_variants(self, repo):
        m = Metrics(repo)
        assert m.total_variants == 4  # 1 + 0 + 3

    def test_average_variants(self, repo):
        m = Metrics(repo)
        assert m.average_variants == pytest.approx(4/3, 0.01)

    def test_total_synonyms(self, repo):
        m = Metrics(repo)
        assert m.total_synonyms == 2  # 1 + 0 + 1

    def test_total_abbreviations(self, repo):
        m = Metrics(repo)
        assert m.total_abbreviations == 2  # 1 + 0 + 1

    def test_total_examples(self, repo):
        m = Metrics(repo)
        assert m.total_examples == 0

    def test_top_concepts(self, repo):
        m = Metrics(repo)
        top = m.top_concepts
        assert len(top) >= 1

    def test_confidence_distribution(self, repo):
        m = Metrics(repo)
        dist = m.confidence_distribution
        assert dist["alta (>0.8)"] == 1
        assert dist["media (0.5-0.8)"] == 1
        assert dist["baja (<0.5)"] == 1

    def test_category_distribution(self, repo):
        m = Metrics(repo)
        dist = m.category_distribution
        assert dist.get("activo_corriente") == 1

    def test_financial_statement_distribution(self, repo):
        m = Metrics(repo)
        dist = m.financial_statement_distribution
        assert dist.get("balance") == 2
        assert dist.get("resultado") == 1

    def test_coverage_potential(self, repo):
        m = Metrics(repo)
        cov = m.coverage_potential
        assert cov["total"] == 3

    def test_report(self, repo):
        m = Metrics(repo)
        r = m.report()
        assert r["cantidad_conceptos"] == 3
        assert "distribucion_confianza" in r


if __name__ == "__main__":
    pytest.main([__file__])
