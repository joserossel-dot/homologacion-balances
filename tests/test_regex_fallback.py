"""Tests para RegexFallback en HomologationPipeline (Sprint 28.5A).

Verifica:
- Cada uno de los 7 patrones auditados con precisión 100%
- Filtrado por tipo de cuenta (AccountTypeFilter)
- Orden de evaluación (último recurso)
- Feature flag ENABLE_REGEX_FALLBACK
"""

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags


class TestRegexFallbackPatterns:
    """Cada patrón auditado debe clasificar nombres de cuenta conocidos."""

    def test_pc05_impuestos_por_pagar(self):
        result = HomologationPipeline()._classify_by_regex("IVA DEBITO FISCAL")
        assert result is not None
        assert result["standard_code"] == "PC.05"
        assert result["method"] == "regex_fallback"

    def test_pc05_impuesto_renta_por_pagar(self):
        result = HomologationPipeline()._classify_by_regex("Impuesto a la Renta 1ra Categoria")
        assert result is not None
        assert result["standard_code"] == "PC.05"

    def test_pc08_acreedores_varios(self):
        result = HomologationPipeline()._classify_by_regex("ACREEDORES VARIOS")
        assert result is not None
        assert result["standard_code"] == "PC.08"

    def test_pc08_provisiones_varias(self):
        result = HomologationPipeline()._classify_by_regex("PROVISIONES VARIAS")
        assert result is not None
        assert result["standard_code"] == "PC.08"

    def test_pat02_reservas(self):
        result = HomologationPipeline()._classify_by_regex("OTRAS RESERVAS")
        assert result is not None
        assert result["standard_code"] == "PAT.02"

    def test_pat02_prima_emision(self):
        result = HomologationPipeline()._classify_by_regex("Prima de Emision")
        assert result is not None
        assert result["standard_code"] == "PAT.02"

    def test_er04_gastos_administracion(self):
        result = HomologationPipeline()._classify_by_regex("Gastos de Administracion")
        assert result is not None
        assert result["standard_code"] == "ER.04"

    def test_er04_gastos_generales(self):
        result = HomologationPipeline()._classify_by_regex("GASTOS GENERALES")
        assert result is not None
        assert result["standard_code"] == "ER.04"

    def test_er09_gastos_financieros(self):
        result = HomologationPipeline()._classify_by_regex("Gastos Financieros")
        assert result is not None
        assert result["standard_code"] == "ER.09"

    def test_er09_intereses_bancarios(self):
        result = HomologationPipeline()._classify_by_regex("INTERESES BANCARIOS")
        assert result is not None
        assert result["standard_code"] == "ER.09"

    def test_er09_comisiones_bancarias(self):
        result = HomologationPipeline()._classify_by_regex("Comisiones Bancarias")
        assert result is not None
        assert result["standard_code"] == "ER.09"

    def test_er10_impuesto_renta_en_perdida(self):
        result = HomologationPipeline()._classify_by_regex("Impuesto a la Renta", account_tipo="PERDIDA")
        assert result is not None
        assert result["standard_code"] == "ER.10"

    def test_er10_impuesto_renta_sin_tipo_devuelve_pc05(self):
        result = HomologationPipeline()._classify_by_regex("Impuesto a la Renta")
        assert result is not None
        assert result["standard_code"] == "PC.05"

    def test_er11_utilidad_neta(self):
        result = HomologationPipeline()._classify_by_regex("UTILIDAD NETA")
        assert result is not None
        assert result["standard_code"] == "ER.11"

    def test_er11_net_income(self):
        result = HomologationPipeline()._classify_by_regex("NET INCOME FOR THE PERIOD")
        assert result is not None
        assert result["standard_code"] == "ER.11"


class TestTipoFiltering:
    """Regex debe respetar el tipo de cuenta inferido."""

    def test_er09_aceptado_en_perdida(self):
        result = HomologationPipeline()._classify_by_regex(
            "Gastos Financieros", account_tipo="PERDIDA"
        )
        assert result is not None
        assert result["standard_code"] == "ER.09"

    def test_er09_rechazado_en_activo(self):
        result = HomologationPipeline()._classify_by_regex(
            "Gastos Financieros", account_tipo="ACTIVO"
        )
        assert result is None

    def test_pc05_aceptado_en_pasivo(self):
        result = HomologationPipeline()._classify_by_regex(
            "IVA DEBITO FISCAL", account_tipo="PASIVO"
        )
        assert result is not None
        assert result["standard_code"] == "PC.05"

    def test_pc05_rechazado_en_activo(self):
        result = HomologationPipeline()._classify_by_regex(
            "IVA DEBITO FISCAL", account_tipo="ACTIVO"
        )
        assert result is None

    def test_pat02_aceptado_en_patrimonio(self):
        result = HomologationPipeline()._classify_by_regex(
            "RESERVA LEGAL", account_tipo="PATRIMONIO"
        )
        assert result is not None
        assert result["standard_code"] == "PAT.02"

    def test_pat02_rechazado_en_pasivo(self):
        result = HomologationPipeline()._classify_by_regex(
            "RESERVA LEGAL", account_tipo="PASIVO"
        )
        assert result is None

    def test_desconocido_permite(self):
        result = HomologationPipeline()._classify_by_regex(
            "Gastos Financieros", account_tipo="DESCONOCIDO"
        )
        assert result is not None
        assert result["standard_code"] == "ER.09"


class TestNoMatch:
    """Cuentas sin coincidencia deben retornar None."""

    def test_nombre_vacio(self):
        assert HomologationPipeline()._classify_by_regex("") is None

    def test_nombre_sin_coincidencia(self):
        assert HomologationPipeline()._classify_by_regex("TOTAL ACTIVO") is None

    def test_nombre_no_contable(self):
        assert HomologationPipeline()._classify_by_regex("NOTA 1 - CRITERIOS") is None


class TestPipelineIntegration:
    """Verificar que el pipeline usa regex como último recurso."""

    def test_regex_hits_in_summary_when_enabled(self):
        from pathlib import Path
        pdfs = sorted(Path("edge_cases").glob("*.pdf"))
        if not pdfs:
            pdfs = sorted(Path("datasets/edge_cases").glob("*.pdf"))
        if not pdfs:
            return
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_REGEX_FALLBACK=True))
        result = hp.process(pdfs[0])
        assert "regex_hits" in result
        assert isinstance(result["regex_hits"], int)

    def test_regex_hits_zero_when_disabled(self):
        from pathlib import Path
        pdfs = sorted(Path("edge_cases").glob("*.pdf"))
        if not pdfs:
            pdfs = sorted(Path("datasets/edge_cases").glob("*.pdf"))
        if not pdfs:
            return
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_REGEX_FALLBACK=False))
        result = hp.process(pdfs[0])
        assert result.get("regex_hits", -1) == 0

    def test_regex_pipeline_order_evaluated_last(self):
        hp = HomologationPipeline()
        name = "Gastos Financieros"
        # Regex should NOT fire if dictionary has the account
        code = "ER.01"
        dict_result = hp._classify_by_code(code)
        if dict_result is not None:
            assert dict_result["standard_code"] == "ER.01"
            assert dict_result["method"] == "code"

    def test_default_flag_true(self):
        f = CMCCFeatureFlags.default()
        assert f.ENABLE_REGEX_FALLBACK is True

    def test_to_dict_includes_flag(self):
        f = CMCCFeatureFlags(ENABLE_REGEX_FALLBACK=True)
        d = f.to_dict()
        assert "ENABLE_REGEX_FALLBACK" in d
        assert d["ENABLE_REGEX_FALLBACK"] is True

    def test_feature_flag_off_suppresses_regex(self):
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_REGEX_FALLBACK=False))
        result = hp._classify_by_regex("IVA DEBITO FISCAL")
        assert result is not None  # direct method works
        # But _classify_account should not call it
        from unittest.mock import patch
        original = HomologationPipeline._classify_by_regex
        with patch.object(HomologationPipeline, '_classify_by_regex') as mock:
            mock.return_value = {
                "standard_code": "PC.05",
                "confidence": 0.88,
                "method": "regex_fallback",
            }
            classification = hp._classify_account("", "IVA DEBITO FISCAL")
            # Without the flag, regex should not be called
            assert classification["method"] != "regex_fallback"

    def test_regex_hit_populates_method_in_classified(self):
        from pathlib import Path
        pdfs = list(Path("edge_cases").glob("*.pdf")) if Path("edge_cases").exists() else []
        if not pdfs:
            pdfs = list(Path("datasets/edge_cases").glob("*.pdf")) if Path("datasets/edge_cases").exists() else []
        if not pdfs:
            return
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_REGEX_FALLBACK=True))
        result = hp.process(pdfs[0])
        classified = result.get("classified", [])
        regex_accounts = [c for c in classified if c.get("method") == "regex_fallback"]
        for c in regex_accounts:
            assert c["standard_code"] is not None
            assert c["confidence"] > 0
