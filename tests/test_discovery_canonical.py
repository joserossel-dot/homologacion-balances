import pytest
from knowledge.discovery.canonical_name import CanonicalNameGenerator


class TestCanonicalName:
    def setup_method(self):
        self.gen = CanonicalNameGenerator()

    def test_empty(self):
        assert self.gen.generate([]) == ""

    def test_single(self):
        assert self.gen.generate(["Caja General"]) == "Caja General"

    def test_two_members(self):
        result = self.gen.generate(["Gastos Administracion", "Gastos Administrativos"],
                                    frequencies={"Gastos Administracion": 10,
                                                 "Gastos Administrativos": 5})
        assert result is not None
        assert len(result) > 0

    def test_most_frequent(self):
        result = self.gen.generate(["Gastos Adm", "Gastos de Administracion"],
                                    frequencies={"Gastos Adm": 20,
                                                 "Gastos de Administracion": 5})
        assert "gastos" in result.lower() or "Gastos" in result

    def test_short(self):
        result = self.gen.generate_short(["Caja y Bancos Generales"],
                                          frequencies={"Caja y Bancos Generales": 5})
        assert result is not None

    def test_custom_stopwords(self):
        gen = CanonicalNameGenerator(stopwords={"de", "la", "y"})
        result = gen.generate(["Gastos de Administracion", "Gastos de Ventas"],
                               frequencies={"Gastos de Administracion": 10,
                                            "Gastos de Ventas": 8})
        assert "gastos" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__])
