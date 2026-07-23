"""Tests para AccountTypeFilter en HomologationPipeline.

Verifica que ENABLE_ACCOUNT_TYPE_FILTER restringe el universo de búsqueda
rechazando códigos que contradicen el tipo de cuenta resuelto.
"""

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.features import CMCCFeatureFlags


class TestCodeValidation:
    """_is_code_allowed_for_tipo — reglas de prefijo vs tipo."""

    def test_ac_permite_activo(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("AC.01", "ACTIVO")

    def test_ac_rechaza_pasivo(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("AC.01", "PASIVO")

    def test_anc_permite_activo(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("ANC.05", "ACTIVO")

    def test_anc_rechaza_patrimonio(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("ANC.05", "PATRIMONIO")

    def test_pc_permite_pasivo(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("PC.02", "PASIVO")

    def test_pc_rechaza_activo(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("PC.02", "ACTIVO")

    def test_pnc_permite_pasivo(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("PNC.03", "PASIVO")

    def test_pat_permite_patrimonio(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("PAT.01", "PATRIMONIO")

    def test_pat_rechaza_activo(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("PAT.01", "ACTIVO")

    def test_er_permite_perdida(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("ER.09", "PERDIDA")

    def test_er_permite_ganancia(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("ER.01", "GANANCIA")

    def test_er_rechaza_activo(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("ER.01", "ACTIVO")

    def test_er_rechaza_pasivo(self):
        assert not HomologationPipeline._is_code_allowed_for_tipo("ER.09", "PASIVO")

    def test_desconocido_permite_todo(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("PC.02", "DESCONOCIDO")
        assert HomologationPipeline._is_code_allowed_for_tipo("AC.01", "DESCONOCIDO")
        assert HomologationPipeline._is_code_allowed_for_tipo("PAT.01", "DESCONOCIDO")

    def test_codigo_sin_prefijo_permite(self):
        """Códigos sin prefijo conocido pasan sin restricción."""
        assert HomologationPipeline._is_code_allowed_for_tipo("ZZ.99", "ACTIVO")
        assert HomologationPipeline._is_code_allowed_for_tipo("ZZ.99", "PASIVO")

    def test_none_permite(self):
        assert HomologationPipeline._is_code_allowed_for_tipo(None, "ACTIVO")  # type: ignore

    def test_vacio_permite(self):
        assert HomologationPipeline._is_code_allowed_for_tipo("", "ACTIVO")


class TestFeatureFlag:
    """ENABLE_ACCOUNT_TYPE_FILTER default y serialización."""

    def test_default_false(self):
        f = CMCCFeatureFlags.default()
        assert f.ENABLE_ACCOUNT_TYPE_FILTER is False

    def test_to_dict_includes_flag(self):
        f = CMCCFeatureFlags(ENABLE_ACCOUNT_TYPE_FILTER=True)
        d = f.to_dict()
        assert "ENABLE_ACCOUNT_TYPE_FILTER" in d
        assert d["ENABLE_ACCOUNT_TYPE_FILTER"] is True


class TestPipelineFilterBehavior:
    """Verifica que el pipeline filtra correctamente cuando el flag está activo."""

    def test_pipeline_creates_with_flag(self):
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_ACCOUNT_TYPE_FILTER=True))
        assert hp._features.ENABLE_ACCOUNT_TYPE_FILTER is True

    def test_pipeline_creates_without_flag(self):
        hp = HomologationPipeline()
        assert hp._features.ENABLE_ACCOUNT_TYPE_FILTER is False

    def test_tipo_filtered_in_summary_when_enabled(self):
        """Cuando el flag está activo, el summary incluye tipo_filtered."""
        from pathlib import Path
        pdfs = sorted(Path("edge_cases").glob("*.pdf"))
        if not pdfs:
            pdfs = sorted(Path("datasets/edge_cases").glob("*.pdf"))
        if not pdfs:
            return  # skip if no test PDFs
        hp = HomologationPipeline(features=CMCCFeatureFlags(ENABLE_ACCOUNT_TYPE_FILTER=True))
        result = hp.process(pdfs[0])
        assert "tipo_filtered" in result
        assert isinstance(result["tipo_filtered"], int)

    def test_tipo_filtered_zero_when_disabled(self):
        """Cuando el flag está desactivado, tipo_filtered debe ser 0."""
        from pathlib import Path
        pdfs = sorted(Path("edge_cases").glob("*.pdf"))
        if not pdfs:
            pdfs = sorted(Path("datasets/edge_cases").glob("*.pdf"))
        if not pdfs:
            return
        hp = HomologationPipeline()
        result = hp.process(pdfs[0])
        assert result.get("tipo_filtered", -1) == 0
