"""Pruebas unitarias y de integración para las 4 capas de enriquecimiento semántico.

Cubre:
1. Nuevas etiquetas canónicas de estados financieros auditados (12 etiquetas).
2. Reglas regex actualizadas y ampliadas.
3. Expansión segura de abreviaturas contables sin alterar glosas originales.
4. Protección de "Facturas por pagar" (evitar falsos positivos).
5. Filtro de ruido de metadatos de ERP (Usuario, Rango de fechas, símbolos).
"""

from __future__ import annotations

import pytest
from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags


@pytest.fixture
def pipeline() -> HomologationPipeline:
    features = CMCCFeatureFlags()
    return HomologationPipeline(features=features)


class TestAuditedStatementLabels:
    """Verifica que las 12 nuevas etiquetas canónicas de estados auditados clasifiquen con alta confianza."""

    @pytest.mark.parametrize(
        ("name", "tipo", "expected_code"),
        [
            ("Acreedores comerciales", "PASIVO", "PC.01"),
            ("Acreedores comerciales y otras cuentas por pagar", "PASIVO", "PC.01"),
            ("Otros acreedores", "PASIVO", "PC.01"),
            ("Obligaciones con instituciones de crédito", "PASIVO", "PC.02"),
            ("Obligaciones con instituciones de crédito corrientes", "PASIVO", "PC.02"),
            ("Obligaciones con instituciones de crédito no corrientes", "PASIVO", "PNC.01"),
            ("Inversiones en otras empresas", "ACTIVO", "ANC.04"),
            ("Inversiones en otras sociedades", "ACTIVO", "ANC.04"),
            ("Activos biológicos", "ACTIVO", "AC.05"),
            ("Activos biológicos corrientes", "ACTIVO", "AC.05"),
            ("Capital pagado", "PATRIMONIO", "PAT.01"),
            ("Retasación técnica", "PATRIMONIO", "PAT.02"),
            ("Resultados acumulados", "PATRIMONIO", "PAT.03"),
            ("Utilidad (pérdida) del ejercicio", "PATRIMONIO", "PAT.04"),
            ("Deferred taxes", "PASIVO", "PNC.06"),
            ("Deferred taxes", "ACTIVO", "ANC.09"),
        ],
    )
    def test_canonical_audited_labels(
        self,
        pipeline: HomologationPipeline,
        name: str,
        tipo: str,
        expected_code: str,
    ) -> None:
        result = pipeline._classify_audited_statement_label(name, tipo)
        assert result is not None, f"No clasificó '{name}' con tipo {tipo}"
        assert result["standard_code"] == expected_code
        assert result["confidence"] >= 0.96
        assert result["method"] == "audited_statement_label"


class TestRegexRulesEnrichment:
    """Verifica la ampliación de REGLAS_REGEX en config/regex_rules.py."""

    @pytest.mark.parametrize(
        ("name", "tipo", "expected_code"),
        [
            ("Documetos por cobrar", "ACTIVO", "AC.04"),
            ("Inversiones en otras empresas", "ACTIVO", "ANC.04"),
            ("Inversiones en otras sociedades", "ACTIVO", "ANC.04"),
            ("Obligaciones con instituciones de crédito", "PASIVO", "PC.02"),
            ("Obligaciones instituciones financieras", "PASIVO", "PC.02"),
            ("Oblig. bancos", "PASIVO", "PC.02"),
            ("IVA D.F.", "PASIVO", "PC.05"),
            ("IVA D.F", "PASIVO", "PC.05"),
            ("Retasación técnica", "PATRIMONIO", "PAT.02"),
            ("Revaluación técnica", "PATRIMONIO", "PAT.02"),
        ],
    )
    def test_contextual_regex_rules(
        self,
        pipeline: HomologationPipeline,
        name: str,
        tipo: str,
        expected_code: str,
    ) -> None:
        result = pipeline._classify_by_regex_contextual(name, tipo)
        assert result is not None, f"No clasificó por regex contextual '{name}'"
        assert result["standard_code"] == expected_code


class TestAbbreviationExpansion:
    """Verifica la normalización y expansión de abreviaturas contables comunes."""

    def test_expand_abbreviations(self) -> None:
        raw_text = "ctas. ctes. bcos."
        normalized = HomologationPipeline._normalize_name(raw_text)
        assert "cuentas" in normalized
        assert "corrientes" in normalized
        assert "bancos" in normalized

    def test_expand_cp_lp(self) -> None:
        assert HomologationPipeline._normalize_name("doctos. por cobrar c/p") == "documentos por cobrar corto plazo"
        assert HomologationPipeline._normalize_name("oblig. inst. financ. l/p") == "obligaciones instituciones financieras largo plazo"

    def test_facturas_por_pagar_protection(self, pipeline: HomologationPipeline) -> None:
        """Asegura que 'Fras. por pagar' no se altere erróneamente ni colisione con financieras."""
        normalized = HomologationPipeline._normalize_name("Fras. por pagar")
        assert "financ" not in normalized

        result = pipeline._classify_by_regex_contextual("Facturas por pagar", account_tipo="PASIVO")
        assert result is not None
        assert result.get("standard_code") == "PC.01"

        res_fras = pipeline._classify_by_regex_contextual("Fras. por pagar", account_tipo="PASIVO")
        assert res_fras is None or res_fras.get("standard_code") != "PC.02"


class TestErpMetadataNoiseFilter:
    """Verifica que las líneas basura generadas por ERPs se aíslen correctamente."""

    @pytest.mark.parametrize(
        "noise_text",
        [
            "Usuario : GORELLANA",
            "Usuario: admin",
            "HASTA 31/12/2016 EN NIVEL 4",
            "HASTA 31/12/2020",
            "$ $",
            "$",
            "BALANCE",
            "GASTOS",
            "INGRESOS",
            "FINANCIEROS",
            "PLAZO",
        ],
    )
    def test_is_erp_noise(self, noise_text: str) -> None:
        assert HomologationPipeline._is_erp_metadata_noise(noise_text) is True

    @pytest.mark.parametrize(
        "valid_account",
        [
            "Gastos Financieros",
            "Gastos de Administración",
            "Ingresos de Explotación",
            "Banco de Chile",
            "Proveedores Nacionales",
        ],
    )
    def test_valid_account_not_noise(self, valid_account: str) -> None:
        assert HomologationPipeline._is_erp_metadata_noise(valid_account) is False
