import pytest
from knowledge.concept import Concept


class TestConcept:
    def test_create_minimal(self):
        c = Concept(
            id="TEST.01",
            codigo="TEST.01",
            nombre="Test Concept",
            categoria="activo_corriente",
            tipo_estado_financiero="balance",
        )
        assert c.id == "TEST.01"
        assert c.codigo == "TEST.01"
        assert c.nombre == "Test Concept"
        assert c.categoria == "activo_corriente"
        assert c.tipo_estado_financiero == "balance"
        assert c.confidence == 0.5
        assert c.version == "1.0.0"

    def test_create_full(self):
        c = Concept(
            id="TEST.02",
            codigo="TEST.02",
            nombre="Full Concept",
            categoria="pasivo_corriente",
            tipo_estado_financiero="balance",
            sinonimos=["Alt 1", "Alt 2"],
            abreviaturas=["abr1"],
            variantes=["var1", "var2"],
            palabras_clave=["key1"],
            patrones=[r"gasto"],
            ejemplos=["Gasto X"],
            empresas=["Emp1"],
            confidence=0.9,
            version="2.0.0",
            ultima_revision="2026-07-08",
            metadata={"source": "manual"},
        )
        assert c.confidence == 0.9
        assert len(c.sinonimos) == 2
        assert c.metadata["source"] == "manual"

    def test_add_variant(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        c.add_variant("Variant A")
        assert "Variant A" in c.variantes
        c.add_variant("Variant A")  # duplicate
        assert len(c.variantes) == 1

    def test_add_synonym(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        c.add_synonym("Sinónimo 1")
        assert "Sinónimo 1" in c.sinonimos

    def test_add_abbreviation(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        c.add_abbreviation("abbr1")
        assert "abbr1" in c.abreviaturas

    def test_add_example(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        c.add_example("Ejemplo 1")
        assert "Ejemplo 1" in c.ejemplos

    def test_add_empresa(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance")
        c.add_empresa("Empresa SA")
        assert "Empresa SA" in c.empresas

    def test_to_dict(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Test",
                     categoria="activo_corriente", tipo_estado_financiero="balance",
                     sinonimos=["Alt"])
        d = c.to_dict()
        assert d["id"] == "T.01"
        assert d["sinonimos"] == ["Alt"]

    def test_from_dict(self):
        data = {
            "id": "T.01", "codigo": "T.01", "nombre": "Test",
            "categoria": "activo_corriente", "tipo_estado_financiero": "balance",
            "sinonimos": ["Alt"], "abreviaturas": [], "variantes": [],
            "palabras_clave": [], "patrones": [], "ejemplos": [], "empresas": [],
            "confidence": 0.8, "version": "1.0.0", "ultima_revision": "",
            "metadata": {},
        }
        c = Concept.from_dict(data)
        assert c.id == "T.01"
        assert c.confidence == 0.8

    def test_all_tokens(self):
        c = Concept(id="T.01", codigo="T.01", nombre="Caja y Bancos",
                     categoria="activo_corriente", tipo_estado_financiero="balance",
                     sinonimos=["Efectivo"], abreviaturas=["efvo"],
                     variantes=["Caja General"], palabras_clave=["disponible"])
        tokens = c.all_tokens
        assert "caja" in tokens
        assert "bancos" in tokens
        assert "efectivo" in tokens
        assert "efvo" in tokens
        assert "disponible" in tokens

    def test_coverage_score(self):
        c1 = Concept(id="T.01", codigo="T.01", nombre="Basic",
                      categoria="activo_corriente", tipo_estado_financiero="balance")
        c2 = Concept(id="T.02", codigo="T.02", nombre="Full",
                      categoria="activo_corriente", tipo_estado_financiero="balance",
                      sinonimos=["A", "B", "C"], abreviaturas=["x", "y"],
                      variantes=["v1", "v2"], patrones=[r".*"], ejemplos=["e1"])
        assert c1.coverage_score < c2.coverage_score


if __name__ == "__main__":
    pytest.main([__file__])
