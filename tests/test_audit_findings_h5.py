"""
test_audit_findings_h5.py - Verificación de Mitigación de Hallazgo H5:
Cobertura léxica y reglas para verticales agrícola, vitivinícola y banca multidivisa.
"""

import pytest
from pipeline.homologation_pipeline import HomologationPipeline


@pytest.fixture
def pipeline():
    return HomologationPipeline()


class TestAuditFindingH5MulticurrencyBanking:
    """Verifica la correcta clasificación de cuentas bancarias multidivisa e instrumentos de tesorería (AC.01 / AC.02)."""

    @pytest.mark.parametrize(
        "name,expected_code",
        [
            ("BANCO HSBC (DOLAR)", "AC.01"),
            ("BANCO HSBC (DOLAR CANADIENSE)", "AC.01"),
            ("BANCO HSBC (RMB)", "AC.01"),
            ("BANCO JPMORGAN (LIBRA)", "AC.01"),
            ("BANCO JPMORGAN (EURO)", "AC.01"),
            ("BANCO SANTANDER (EURO)", "AC.01"),
            ("BANCO SANTANDER (LIBRA)", "AC.01"),
            ("BANCO SANTANDER SANTIAGO", "AC.01"),
            ("BANCO DE A. EDWARDS/CHILE", "AC.01"),
            ("BANCO ITAU PESOS", "AC.01"),
            ("BANCO BCI", "AC.01"),
            ("Banco Crédito Moneda Extranjera", "AC.01"),
            ("CORPBANCA", "AC.01"),
            ("SECURITY DOLAR", "AC.01"),
            ("CAJA PESOS", "AC.01"),
            ("Valores Disponibles", "AC.01"),
            ("Operaciones en Tránsito", "AC.01"),
            ("DEP/ABONO BANCARIO X APLICAR", "AC.01"),
            ("VALES VISTAS NO RETIRADOS", "AC.01"),
            ("CHEQUES CADUCOS", "AC.01"),
        ],
    )
    def test_multicurrency_banking_ac01(self, pipeline, name, expected_code):
        res = pipeline._classify_account("110101", name, account_tipo="ACTIVO")
        assert res.get("standard_code") == expected_code, f"Fallo al clasificar {name}: {res}"
        assert res.get("confidence") >= 0.80

    @pytest.mark.parametrize(
        "name,expected_code",
        [
            ("DEPOSITOS A PLAZO EN PESOS", "AC.02"),
            ("DEPOSITOS A PLAZO EN US$", "AC.02"),
            ("FONDOS MUTUOS PESOS", "AC.02"),
        ],
    )
    def test_term_deposits_and_mutual_funds_ac02(self, pipeline, name, expected_code):
        res = pipeline._classify_account("110201", name, account_tipo="ACTIVO")
        assert res.get("standard_code") == expected_code, f"Fallo al clasificar {name}: {res}"


class TestAuditFindingH5AgriculturalFixedAssets:
    """Verifica la clasificación de infraestructura, plantaciones y activos fijos agrícolas (ANC.01)."""

    @pytest.mark.parametrize(
        "name",
        [
            "Parronales",
            "Viñedos",
            "Pozos Profundos",
            "Salas de Bombas",
            "Bocatomas, Piscinas y Canales",
            "Galpones",
            "Bodegas",
            "Taller",
            "Casas Habitación",
            "Oficinas",
            "Colectivos",
            "Obras en Ejecución",
            "Azufradoras",
            "Carros Cosecheros",
            "Tractores",
        ],
    )
    def test_agricultural_ppe_anc01(self, pipeline, name):
        res = pipeline._classify_account("120101", name, account_tipo="ACTIVO")
        assert res.get("standard_code") == "ANC.01", f"Fallo al clasificar {name}: {res}"
        assert res.get("confidence") >= 0.80


class TestAuditFindingH5AgriculturalInventoryAndCosts:
    """Verifica clasificación de existencias, futuras cosechas y costos de explotación (AC.05 / ER.02)."""

    @pytest.mark.parametrize(
        "name,tipo,expected_code",
        [
            ("Gastos Futuras Cosechas", "ACTIVO", "AC.05"),
            ("Insumos Agrícolas", "ACTIVO", "AC.05"),
            ("Uva y Vino", "ACTIVO", "AC.05"),
            ("Materiales Conducción Agrícola", "ACTIVO", "AC.05"),
            ("COSTO DE VTA.EMBOTellado", "PERDIDA", "ER.02"),
            ("COSTO DE VENTA GRANEL", "PERDIDA", "ER.02"),
            ("COSTO VTA INSUMO Y MAT.PRIMAS", "PERDIDA", "ER.02"),
            ("MERMA PROCESO PRODUCTIVO", "PERDIDA", "ER.02"),
        ],
    )
    def test_agricultural_inventory_and_costs(self, pipeline, name, tipo, expected_code):
        res = pipeline._classify_account("110501", name, account_tipo=tipo)
        assert res.get("standard_code") == expected_code, f"Fallo al clasificar {name}: {res}"


class TestAuditFindingH5AgriculturalPersonnelAndLiabilities:
    """Verifica cuentas corrientes de personal (AC.07), provisiones laborales (PC.06) y proveedores (PC.01)."""

    @pytest.mark.parametrize(
        "name,tipo,expected_code",
        [
            ("Ctas ctes del personal", "ACTIVO", "AC.07"),
            ("Anticipos al Personal", "ACTIVO", "AC.07"),
            ("Sobregiros del Personal", "ACTIVO", "AC.07"),
            ("PROVEEDORES UVA Y VINO", "PASIVO", "PC.01"),
            ("SERVICIOS POR DOCUMENTAR", "PASIVO", "PC.01"),
            ("RECEPCIONES POR DOCUMENTAR (STOCK)", "PASIVO", "PC.01"),
            ("PROVIS.VACACIONES ROL GENERAL", "PASIVO", "PC.06"),
            ("PROVIS.VACACIONES ROL PRIVADO", "PASIVO", "PC.06"),
            ("RET TRABAJ POR PAGAR", "PASIVO", "PC.06"),
            ("ESTIMACIÓN DEUDA INCOBRABLE (EDI)", "ACTIVO", "AC.03"),
        ],
    )
    def test_personnel_and_liabilities(self, pipeline, name, tipo, expected_code):
        res = pipeline._classify_account("210101", name, account_tipo=tipo)
        assert res.get("standard_code") == expected_code, f"Fallo al clasificar {name}: {res}"