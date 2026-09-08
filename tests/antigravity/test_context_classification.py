"""Tests for Bloque B: Clasificación Contextual (Ronda B1).

Cubre:
1. Restricciones duras de sección (impide AC/PC en no corrientes y ANC/PNC en corrientes).
2. Propagación de sección en todas las rutas incluyendo Decision Engine.
3. Rechazo de coincidencias al 100% que contradigan la sección explícita.
4. Reglas globales aprobadas (AC.08, PNC.05, ER.04).
5. Restricción estricta de ANC.01.01 exclusivamente a depreciación acumulada de PPE.
6. Cobertura del contraejemplo A0-10 y precedencia de reglas canónicas.
"""

from unittest.mock import MagicMock
import pytest

from parsers.account_type_resolver import (
    is_contra_asset_name,
    is_ppe_depreciation_name,
)
from pipeline.homologation_pipeline import HomologationPipeline


def test_b0_1_section_constraints_prevent_cross_term_classification(tmp_path):
    """Restricción dura: no permite códigos corrientes en secciones no corrientes ni viceversa."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")

    # AC en sección ANC
    assert not pipeline._is_code_allowed_for_section("AC.01", "ANC")
    assert not pipeline._is_code_allowed_for_section("AC.08", "activo no corriente")
    # ANC en sección AC
    assert not pipeline._is_code_allowed_for_section("ANC.01", "AC")
    assert not pipeline._is_code_allowed_for_section("ANC.03", "activo corriente")
    # PC en sección PNC
    assert not pipeline._is_code_allowed_for_section("PC.01", "PNC")
    assert not pipeline._is_code_allowed_for_section("PC.02", "pasivo no corriente")
    # PNC en sección PC
    assert not pipeline._is_code_allowed_for_section("PNC.01", "PC")
    assert not pipeline._is_code_allowed_for_section("PNC.05", "pasivo corriente")
    # Activo en sección Pasivo o Patrimonio
    assert not pipeline._is_code_allowed_for_section("AC.01", "PAT")
    assert not pipeline._is_code_allowed_for_section("AC.01", "PNC")
    # Válidos en su propia sección
    assert pipeline._is_code_allowed_for_section("ANC.01", "ANC")
    assert pipeline._is_code_allowed_for_section("AC.01", "AC")
    assert pipeline._is_code_allowed_for_section("PC.01", "PC")
    assert pipeline._is_code_allowed_for_section("PNC.05", "PNC")
    assert pipeline._is_code_allowed_for_section("PAT.01", "PAT")
    assert pipeline._is_code_allowed_for_section("ER.01", "ER")


def test_b0_2_learning_engine_100_percent_match_rejected_if_conflicting_section(tmp_path):
    """Un match textual al 100% en Gold/aprendizaje NO invalida una sección contradictoria."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")

    # Mock learning engine que propone AC.01 (Efectivo y equivalentes) con confianza 1.0
    pipeline._learning_engine.best_match = MagicMock(return_value={
        "source": "gold",
        "code": "AC.01",
        "confidence": 1.0,
        "matched_name": "Caja y Bancos",
    })

    # Si la cuenta está en sección Activo No Corriente (ANC), no debe aceptarse AC.01
    result = pipeline._classify_account(
        account_code="1101",
        account_name="Caja y Bancos",
        account_tipo="ACTIVO",
        account_section="ANC",
    )
    assert result.get("standard_code") != "AC.01", "No debe asignar código corriente a sección no corriente a pesar del 100% de match"


def test_b0_3_approved_global_rules(tmp_path):
    """Reglas globales aprobadas: AC.08 en corriente, PNC.05 en no corriente, ER.04 en distribución."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")

    # 1. Otros activos financieros en sección corriente -> AC.08
    r_ac = pipeline._classify_audited_statement_label(
        "otros activos financieros corrientes", account_tipo="ACTIVO", account_section="AC",
    )
    assert r_ac is not None
    assert r_ac["standard_code"] == "AC.08"

    # 2. Otros activos financieros en sección no corriente -> NO AC.08
    r_anc = pipeline._classify_audited_statement_label(
        "otros activos financieros", account_tipo="ACTIVO", account_section="ANC",
    )
    assert r_anc is None, "No debe asignar AC.08 en sección no corriente"

    # 3. Otros pasivos financieros en sección no corriente -> PNC.05
    r_pnc = pipeline._classify_audited_statement_label(
        "otros pasivos financieros", account_tipo="PASIVO", account_section="PNC",
    )
    assert r_pnc is not None
    assert r_pnc["standard_code"] == "PNC.05"

    # 4. Costos de distribución -> ER.04
    r_dist = pipeline._classify_audited_statement_label(
        "costos de distribucion", account_tipo="PERDIDA",
    )
    assert r_dist is not None
    assert r_dist["standard_code"] == "ER.04"


def test_b0_4_anc_01_01_strictly_for_ppe_depreciation(tmp_path):
    """Condición 7: ANC.01.01 es estrictamente para depreciación acumulada de PPE, nunca amortización."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")

    # is_ppe_depreciation_name distingue claramente
    assert is_ppe_depreciation_name("Depreciación acumulada maquinarias") is True
    assert is_ppe_depreciation_name("Depreciaciones acumuladas") is True
    assert is_ppe_depreciation_name("Amortización acumulada intangibles") is False
    assert is_ppe_depreciation_name("Deterioro acumulado licencias") is False

    # Depreciación de PPE puede normalizarse a ANC.01.01
    dep_res = pipeline._canonicalize_special_code(
        {"standard_code": "ANC.01"}, "Depreciación acumulada instalaciones",
    )
    assert dep_res["standard_code"] == "ANC.01.01"

    # Amortización acumulada NO debe recibir ni conservar ANC.01.01
    amort_res = pipeline._canonicalize_special_code(
        {"standard_code": "ANC.01.01"}, "Amortización acumulada software y patentes",
    )
    assert amort_res["standard_code"] != "ANC.01.01", "Amortización acumulada jamás debe usar ANC.01.01"
    assert amort_res["standard_code"] is None
    assert amort_res["confidence"] == 0
    assert amort_res["method"] == "unclassified"


def test_b0_5_decision_engine_filters_section_incompatible_candidates(tmp_path):
    """Decision Engine no recibe ni emite candidatos incompatibles con la sección contable."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")
    pipeline._features.ENABLE_DECISION_ENGINE = True
    pipeline._features.ENABLE_SEMANTIC_MATCHER = True

    # Semantic matcher propone AC.03 (corriente)
    sm_mock = MagicMock()
    sm_match = MagicMock()
    sm_match.is_unknown = False
    sm_match.expected_cmcc = "AC.03"
    sm_match.score = 0.95
    sm_match.match_tier = 1
    sm_match.confidence = "HIGH"
    sm_match.concept_name = "Deudores comerciales"
    sm_match.to_dict.return_value = {"expected_cmcc": "AC.03"}
    sm_mock.match.return_value = sm_match
    pipeline._semantic_matcher = sm_mock

    # Cuenta ubicada en sección PNC (pasivo no corriente)
    res = pipeline._classify_with_decision_engine(
        account_code="2100",
        account_name="Deudores varios",
        account_tipo="PASIVO",
        account_section="PNC",
    )
    assert res.get("standard_code") != "AC.03", "El Decision Engine no debe emitir código incompatible con la sección PNC"


def test_b0_6_counterexample_a0_10_precedence_and_reachable_paths(tmp_path):
    """A0-10: Etiquetas canónicas auditan con precedencia; rutas no canónicas alcanzan Decision Engine."""
    pipeline = HomologationPipeline(db_path=tmp_path / "gold.db")
    pipeline._features.ENABLE_DECISION_ENGINE = True

    # Caso canónico: etiqueta auditada exacta se resuelve antes de Decision Engine
    r_canon = pipeline._classify_account(
        account_code="2105",
        account_name="otros pasivos financieros",
        account_tipo="PASIVO",
        account_section="PNC",
    )
    assert r_canon["method"] == "audited_statement_label"
    assert r_canon["standard_code"] == "PNC.05"

    # Caso no canónico: cuenta operativa en PNC que sí debe consultar el flujo completo
    r_non_canon = pipeline._classify_account(
        account_code="2201",
        account_name="Obligaciones con el público largo plazo",
        account_tipo="PASIVO",
        account_section="PNC",
    )
    # No es etiqueta auditada estándar, por lo que entra al Decision Engine
    assert r_non_canon["method"].startswith("decision_") or r_non_canon["method"] == "unclassified"
    # Y si clasificó, debe respetar la sección PNC
    if r_non_canon.get("standard_code"):
        assert r_non_canon["standard_code"].startswith("PNC.")
