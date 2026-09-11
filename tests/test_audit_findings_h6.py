"""
test_audit_findings_h6.py - Verificación de Mitigación de Hallazgo H6:
Abreviaturas contables ERP, maquinaria/flota industrial, derivados, intangibles y gastos operacionales.
"""

import pytest
from pipeline.homologation_pipeline import HomologationPipeline


@pytest.fixture
def pipeline():
    return HomologationPipeline()


class TestAuditFindingH6Abbreviations:
    """Verifica la correcta expansión y clasificación de abreviaturas contables de ERP."""

    @pytest.mark.parametrize(
        "name,tipo,expected_code",
        [
            ("BCO CHILE", "ACTIVO", "AC.01"),
            ("BCO BCI CURICO", "ACTIVO", "AC.01"),
            ("BCO SANTANDER CURICO", "ACTIVO", "AC.01"),
            ("DEP. ACUM. MUEBLES", "ACTIVO", "ANC.01.01"),
            ("DEP. ACUM. EQ. COMPUTACIONALES", "ACTIVO", "ANC.01.01"),
            ("GTOS POR RECUPERAR", "ACTIVO", "AC.07"),
            ("Puentes Caminos/Otras O.O.C.C", "ACTIVO", "ANC.01"),
            ("Eq. Procesamiento de Datos", "ACTIVO", "ANC.01"),
            ("Otrs Eq. y Maq. Agrícolas", "ACTIVO", "ANC.01"),
            ("DOCTOS POR PAGAR", "PASIVO", "PC.01"),
            ("DOCUMENTOS POR PAGAR", "PASIVO", "PC.01"),
        ],
    )
    def test_abbreviations_expansion(self, pipeline, name, tipo, expected_code):
        res = pipeline._classify_account("110101", name, account_tipo=tipo)
        assert res.get("standard_code") == expected_code, f"Fallo en {name}: {res}"


class TestAuditFindingH6FleetAndMachinery:
    """Verifica la clasificación de flota, maquinaria, obras e instalaciones (ANC.01)."""

    @pytest.mark.parametrize(
        "name",
        [
            "Camiones",
            "Camionetas",
            "Motocicletas",
            "Cuatrimotos",
            "Grua Horquilla",
            "Pulverizadoras",
            "Rastras",
            "Arados",
            "Tractores y Maquinaria Agrícola",
            "Utilaje y Herramientas",
            "Equipos de Riego",
            "Sistema de Riego Tecnificado",
            "Equipos de Bombeo",
            "Packing",
            "Casino",
            "Plantas Faenadoras",
            "Obras Civiles",
            "Instalaciones Eléctricas",
            "Instalaciones de Packing",
            "Líneas de Distribución",
            "Tranque de Acumulación",
            "Plantaciones Frutales",
            "Ganado",
        ],
    )
    def test_fleet_and_machinery_anc01(self, pipeline, name):
        res = pipeline._classify_account("120101", name, account_tipo="ACTIVO")
        assert res.get("standard_code") == "ANC.01", f"Fallo en {name}: {res}"


class TestAuditFindingH6IntangiblesAndDerivatives:
    """Verifica clasificación de derechos de agua (ANC.03), derivados (AC.08/PC.02) y tributarios (AC.07)."""

    @pytest.mark.parametrize(
        "name,tipo,expected_code",
        [
            ("Derechos de Agua", "ACTIVO", "ANC.03"),
            ("Derechos de Aprovechamiento de Aguas", "ACTIVO", "ANC.03"),
            ("DERECHO / FAIR VALUE DERIVADOS (ACTIVO)", "ACTIVO", "AC.08"),
            ("OBLIGACION / FAIR VALUE DERIVADOS (PASIVO)", "PASIVO", "PC.02"),
            ("SENCE", "ACTIVO", "AC.07"),
            ("Crédito SENCE", "ACTIVO", "AC.07"),
            ("Reclamos al Seguro", "ACTIVO", "AC.07"),
            ("Anticipo Acreedores", "ACTIVO", "AC.07"),
        ],
    )
    def test_intangibles_and_derivatives(self, pipeline, name, tipo, expected_code):
        res = pipeline._classify_account("110401", name, account_tipo=tipo)
        assert res.get("standard_code") == expected_code, f"Fallo en {name}: {res}"


class TestAuditFindingH6OperatingExpenses:
    """Verifica clasificación de gastos de administración y operacionales en pérdidas (ER.04)."""

    @pytest.mark.parametrize(
        "name",
        [
            "Combustibles y Lubricantes",
            "Energía Eléctrica y Suministros",
            "Asesorías Técnicas y Agronómicas",
            "Fletes y Transportes",
            "Mantención y Reparación Maquinaria",
            "Seguros Agrícolas y Generales",
            "Sueldos y Remuneraciones",
            "Leyes Sociales e Imposiciones",
            "Gastos de Viaje",
            "Patentes Municipales",
        ],
    )
    def test_operating_expenses_er04(self, pipeline, name):
        res = pipeline._classify_account("410101", name, account_tipo="PERDIDA")
        assert res.get("standard_code") == "ER.04", f"Fallo en {name}: {res}"