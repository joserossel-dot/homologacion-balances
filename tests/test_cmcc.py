import pytest
import tempfile
from pathlib import Path
from knowledge.cmcc import CMCC
from knowledge.concept import Concept


@pytest.fixture
def cmcc(tmp_path):
    c = CMCC(tmp_path / "test_cmcc.json")
    c.load()
    # seed some concepts
    c.create_concept(Concept(
        id="AC.01", codigo="AC.01", nombre="Caja y Bancos",
        categoria="activo_corriente", tipo_estado_financiero="balance",
        sinonimos=["Efectivo"], abreviaturas=["efvo"],
        variantes=["Caja Gral"], palabras_clave=["caja", "bancos"],
        confidence=0.9, version="1.0.0", ultima_revision="2026-07-08",
    ))
    c.create_concept(Concept(
        id="PC.01", codigo="PC.01", nombre="Proveedores",
        categoria="pasivo_corriente", tipo_estado_financiero="balance",
        sinonimos=["Cuentas por Pagar"], abreviaturas=["cxp"],
        variantes=["Prov Nac"], palabras_clave=["proveedores"],
        confidence=0.85, version="1.0.0", ultima_revision="2026-07-08",
    ))
    return c


class TestCMCC:
    def test_normalize(self, cmcc):
        r = cmcc.normalize("Caja y Bancos")
        assert r.text is not None
        assert len(r.transformations) > 0

    def test_match(self, cmcc):
        results = cmcc.match("Caja Gral")
        assert len(results) >= 1

    def test_match_returns_top_n(self, cmcc):
        results = cmcc.match("Caja", top_n=1)
        assert len(results) <= 1

    def test_add_variant(self, cmcc):
        assert cmcc.add_variant("AC.01", "Caja Chica USD")
        c = cmcc.find_by_codigo("AC.01")
        assert "Caja Chica USD" in c.variantes

    def test_add_variant_nonexistent(self, cmcc):
        assert not cmcc.add_variant("NONEXIST", "test")

    def test_add_synonym(self, cmcc):
        assert cmcc.add_synonym("PC.01", "Acreedores")
        c = cmcc.find_by_codigo("PC.01")
        assert "Acreedores" in c.sinonimos

    def test_add_abbreviation(self, cmcc):
        assert cmcc.add_abbreviation("AC.01", "cjt")
        c = cmcc.find_by_codigo("AC.01")
        assert "cjt" in c.abreviaturas

    def test_create_concept(self, cmcc):
        c = Concept(id="NEW.01", codigo="NEW.01", nombre="New Concept",
                     categoria="gasto", tipo_estado_financiero="resultado",
                     confidence=0.7, version="1.0.0", ultima_revision="2026-07-08")
        cmcc.create_concept(c)
        assert cmcc.count == 3

    def test_find_by_id(self, cmcc):
        c = cmcc.find_by_id("AC.01")
        assert c is not None
        assert c.nombre == "Caja y Bancos"

    def test_find_by_codigo(self, cmcc):
        c = cmcc.find_by_codigo("PC.01")
        assert c is not None

    def test_find_by_name_exact(self, cmcc):
        results = cmcc.find_by_name("Caja y Bancos", exact=True)
        assert len(results) >= 1

    def test_find_by_name_partial(self, cmcc):
        results = cmcc.find_by_name("Caja", exact=False)
        assert len(results) >= 1

    def test_metrics(self, cmcc):
        m = cmcc.metrics
        assert m.concept_count == 2
        assert m.average_variants >= 0

    def test_save_and_load(self, cmcc, tmp_path):
        cmcc.save()
        c2 = CMCC(tmp_path / "test_cmcc.json")
        c2.load()
        assert c2.count == 2

    def test_concepts_property(self, cmcc):
        assert len(cmcc.concepts) == 2

    def test_count_property(self, cmcc):
        assert cmcc.count == 2


if __name__ == "__main__":
    pytest.main([__file__])
