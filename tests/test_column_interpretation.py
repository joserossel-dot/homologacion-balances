"""Tests para la capa de interpretación contable de origen_columna (OC-1)."""

from parser_universal import OrigenColumna
from parsers.column_interpretation import es_gasto, es_ingreso, normalize


class TestNormalize:
    def test_enum_se_devuelve_igual(self):
        assert normalize(OrigenColumna.ACTIVO) is OrigenColumna.ACTIVO
        assert normalize(OrigenColumna.PASIVO) is OrigenColumna.PASIVO
        assert normalize(OrigenColumna.DESCONOCIDO) is OrigenColumna.DESCONOCIDO

    def test_string_lowercase(self):
        assert normalize("activo") is OrigenColumna.ACTIVO
        assert normalize("perdida") is OrigenColumna.PERDIDA
        assert normalize("ganancia") is OrigenColumna.GANANCIA
        assert normalize("desconocido") is OrigenColumna.DESCONOCIDO

    def test_string_uppercase(self):
        assert normalize("ACTIVO") is OrigenColumna.ACTIVO
        assert normalize("PASIVO") is OrigenColumna.PASIVO
        assert normalize("DEUDOR") is OrigenColumna.DEUDOR
        assert normalize("ACREEDOR") is OrigenColumna.ACREEDOR

    def test_none_devuelve_desconocido(self):
        assert normalize(None) is OrigenColumna.DESCONOCIDO

    def test_string_vacio_devuelve_desconocido(self):
        assert normalize("") is OrigenColumna.DESCONOCIDO

    def test_string_invalido_devuelve_desconocido(self):
        assert normalize("xyz") is OrigenColumna.DESCONOCIDO
        assert normalize("  ") is OrigenColumna.DESCONOCIDO

    def test_string_con_espacios(self):
        assert normalize(" activo ") is OrigenColumna.ACTIVO

    def test_nunca_lanza(self):
        for valor in [None, "", " ", "xyz", 123, [], {}, OrigenColumna.ACTIVO]:
            normalize(valor)


class TestEsIngreso:
    def test_ganancia(self):
        assert es_ingreso(OrigenColumna.GANANCIA) is True
        assert es_ingreso("ganancia") is True
        assert es_ingreso("GANANCIA") is True

    def test_activo(self):
        assert es_ingreso(OrigenColumna.ACTIVO) is True
        assert es_ingreso("activo") is True
        assert es_ingreso("ACTIVO") is True

    def test_no_ingreso(self):
        assert es_ingreso(OrigenColumna.PERDIDA) is False
        assert es_ingreso(OrigenColumna.PASIVO) is False
        assert es_ingreso(OrigenColumna.DEUDOR) is False
        assert es_ingreso(OrigenColumna.ACREEDOR) is False
        assert es_ingreso(OrigenColumna.DESCONOCIDO) is False

    def test_ingreso_con_none_vacio(self):
        assert es_ingreso(None) is False
        assert es_ingreso("") is False
        assert es_ingreso("invalido") is False


class TestEsGasto:
    def test_perdida(self):
        assert es_gasto(OrigenColumna.PERDIDA) is True
        assert es_gasto("perdida") is True
        assert es_gasto("PERDIDA") is True

    def test_pasivo(self):
        assert es_gasto(OrigenColumna.PASIVO) is True
        assert es_gasto("pasivo") is True
        assert es_gasto("PASIVO") is True

    def test_no_gasto(self):
        assert es_gasto(OrigenColumna.GANANCIA) is False
        assert es_gasto(OrigenColumna.ACTIVO) is False
        assert es_gasto(OrigenColumna.DEUDOR) is False
        assert es_gasto(OrigenColumna.ACREEDOR) is False
        assert es_gasto(OrigenColumna.DESCONOCIDO) is False

    def test_gasto_con_none_vacio(self):
        assert es_gasto(None) is False
        assert es_gasto("") is False
        assert es_gasto("invalido") is False
