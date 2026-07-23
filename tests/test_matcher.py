import pytest
from knowledge.concept import Concept
from knowledge.repository import Repository
from knowledge.normalizer import Normalizer
from knowledge.matcher import Matcher


@pytest.fixture
def repo():
    import tempfile
    import os
    r = Repository("/tmp/_test_cmcc_matcher.json")
    concepts = [
        Concept(id="AC.01", codigo="AC.01", nombre="Caja y Bancos",
                categoria="activo_corriente", tipo_estado_financiero="balance",
                sinonimos=["Efectivo", "Disponible"],
                abreviaturas=["efvo"],
                variantes=["Caja General", "Banco Estado"],
                palabras_clave=["caja", "bancos", "efectivo"],
                patrones=[r"\bcaja\b", r"\bbanco\b"],
                ejemplos=["Caja Chica", "Banco Santander $"],
                confidence=0.95, version="1.0.0", ultima_revision="2026-07-08"),
        Concept(id="PC.01", codigo="PC.01", nombre="Proveedores",
                categoria="pasivo_corriente", tipo_estado_financiero="balance",
                sinonimos=["Cuentas por Pagar Comerciales"],
                abreviaturas=["cxp", "prov"],
                variantes=["Proveedores Nacionales", "Proveedores Externos"],
                palabras_clave=["proveedores", "proveedor"],
                patrones=[r"\bprovee"],
                ejemplos=["Proveedores Varios"],
                confidence=0.9, version="1.0.0", ultima_revision="2026-07-08"),
        Concept(id="ER.01", codigo="ER.01", nombre="Ingresos de Actividades Ordinarias",
                categoria="ingreso", tipo_estado_financiero="resultado",
                sinonimos=["Ventas", "Ingresos Ordinarios"],
                abreviaturas=["ing"],
                variantes=["Ingresos por Ventas"],
                palabras_clave=["ingresos", "ventas", "ordinarias"],
                patrones=[r"\bingres"],
                ejemplos=["Ingresos de Actividades Ordinarias"],
                confidence=0.9, version="1.0.0", ultima_revision="2026-07-08"),
    ]
    for c in concepts:
        r.add(c)
    return r


class TestMatcher:
    def test_match_caja(self, repo):
        m = Matcher(repo)
        results = m.match("Caja General")
        assert len(results) >= 1
        assert results[0].concept.id == "AC.01"

    def test_match_proveedores(self, repo):
        m = Matcher(repo)
        results = m.match("Proveedores Nacionales")
        assert len(results) >= 1
        assert results[0].concept.id == "PC.01"

    def test_match_ingresos(self, repo):
        m = Matcher(repo)
        results = m.match("Ingresos por Ventas")
        assert len(results) >= 1
        assert "ER" in results[0].concept.id

    def test_match_abbreviation(self, repo):
        m = Matcher(repo)
        results = m.match("Caja chica efvo")
        assert len(results) >= 1

    def test_match_empty(self, repo):
        m = Matcher(repo)
        results = m.match("")
        assert results == []

    def test_match_none(self, repo):
        m = Matcher(repo)
        results = m.match(None)
        assert results == []

    def test_match_top_n(self, repo):
        m = Matcher(repo)
        results = m.match("Caja", top_n=2)
        assert len(results) <= 2

    def test_match_synonym(self, repo):
        m = Matcher(repo)
        results = m.match("Efectivo General")
        assert len(results) >= 1
        # Should match AC.01 via synonym
        ac01 = [r for r in results if r.concept.id == "AC.01"]
        assert len(ac01) >= 1

    def test_match_with_reasons(self, repo):
        m = Matcher(repo)
        results = m.match("Banco Estado")
        assert len(results) >= 1
        assert len(results[0].reasons) > 0

    def test_match_result_to_dict(self, repo):
        m = Matcher(repo)
        results = m.match("Caja", top_n=1)
        if results:
            d = results[0].to_dict()
            assert "id" in d
            assert "codigo" in d
            assert "score" in d
            assert "motivos" in d

    def test_no_match(self, repo):
        m = Matcher(repo)
        results = m.match("ZXKXYZW")
        assert len(results) == 0

    def test_match_with_pattern(self, repo):
        m = Matcher(repo)
        results = m.match("Proveedores Varios")
        prov = [r for r in results if r.concept.id == "PC.01"]
        assert len(prov) >= 1

    def test_custom_normalizer(self, repo):
        custom_norm = Normalizer(stopwords={"de", "y", "el"})
        m = Matcher(repo, normalizer=custom_norm)
        results = m.match("Caja y Bancos")
        assert len(results) >= 1


if __name__ == "__main__":
    pytest.main([__file__])
