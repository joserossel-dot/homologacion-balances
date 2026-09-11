"""
tests/test_audit_findings_h1_h2.py

Pruebas unitarias y de integración para verificar la mitigación de los hallazgos críticos H1 y H2:
- H1: Validación léxica de plausibilidad en nombres de cuenta antes de aceptar clasificación por código
      y degradación a revisión humana obligatoria ante ruido OCR.
- H2: Tratamiento inequívoco de documentos con 0 cuentas como fallo de extracción y bloqueo de exportación.
"""

import pandas as pd

from pipeline.homologation_pipeline import HomologationPipeline
from pipeline.operational_quality import analyze_operational_quality
from validation.prepost_balance import compare_pre_post


# ===========================================================================
# 1. Pruebas H1: Plausibilidad Léxica de Nombres de Cuenta
# ===========================================================================

def test_h1_is_plausible_account_name_rechaza_ruido_ocr_y_artefactos():
    """Verifica que el validador estático rechace cadenas de ruido OCR identificadas en la auditoría."""
    # Casos reales reproducidos en la auditoría
    assert not HomologationPipeline._is_plausible_account_name("vosrasasss")
    assert not HomologationPipeline._is_plausible_account_name("B 21430509 B 74500008 8 1390058%")
    
    # Casos sintéticos de ruido extremo
    assert not HomologationPipeline._is_plausible_account_name("")
    assert not HomologationPipeline._is_plausible_account_name(None)
    assert not HomologationPipeline._is_plausible_account_name("   ")
    assert not HomologationPipeline._is_plausible_account_name("123456789")
    assert not HomologationPipeline._is_plausible_account_name("----")
    assert not HomologationPipeline._is_plausible_account_name("a")
    assert not HomologationPipeline._is_plausible_account_name("zzzzzzz")
    assert not HomologationPipeline._is_plausible_account_name("120101 220101 330101")


def test_h1_is_plausible_account_name_acepta_nombres_contables_legitimos():
    """Verifica que el validador acepte nombres contables reales y legítimos."""
    assert HomologationPipeline._is_plausible_account_name("Caja")
    assert HomologationPipeline._is_plausible_account_name("Banco de Chile")
    assert HomologationPipeline._is_plausible_account_name("Clientes Nacionales")
    assert HomologationPipeline._is_plausible_account_name("Proveedores Varios")
    assert HomologationPipeline._is_plausible_account_name("Depreciación Acumulada")
    assert HomologationPipeline._is_plausible_account_name("IVA Crédito Fiscal")
    assert HomologationPipeline._is_plausible_account_name("P.P.E.")
    assert HomologationPipeline._is_plausible_account_name("110101 Caja Chica")
    assert HomologationPipeline._is_plausible_account_name("BANCO HSBC (RMB)")


def test_h1_clasificacion_por_codigo_degrada_confianza_y_exige_revision_en_ruido():
    """Verifica que _classify_by_code no apruebe con 0.95 un nombre no plausible."""
    pipeline = HomologationPipeline()
    
    # Código real de auditoría (2016300579 -> PC.02 por ^201[0-9]), pero nombre corrupto
    res_ruido = pipeline._classify_by_code("2016300579", account_name="vosrasasss")
    assert res_ruido is not None
    assert res_ruido["plausible_name"] is False
    assert res_ruido["confidence"] <= 0.50
    assert "no plausible" in res_ruido["reason"]

    # Código válido con nombre legítimo
    res_ok = pipeline._classify_by_code("1-01-01-01", account_name="Caja Central")
    assert res_ok is not None
    assert res_ok["plausible_name"] is True
    assert res_ok["confidence"] >= 0.90


# ===========================================================================
# 2. Pruebas H2: Tratamiento de 0 Cuentas / Fallo de Extracción
# ===========================================================================

def test_h2_compare_pre_post_con_cero_cuentas_no_cuadra_falsamente():
    """Verifica que un balance sin cuentas extraídas retorne squared=False y difference=None."""
    res = compare_pre_post(None, [])
    assert res["late"]["squared"] is False
    assert res["late"]["difference"] is None
    assert res["classification_degradation"] is False


def test_h2_operational_quality_bloquea_exportacion_si_no_hay_cuentas():
    """Verifica que analyze_operational_quality bloquee la exportación si el DataFrame está vacío."""
    df_vacio = pd.DataFrame(columns=["codigo_original", "nombre_original", "monto", "codigo_clasificado"])
    
    # Caso 1: balance_squared=True pero df vacío
    result = analyze_operational_quality(df_vacio, balance_squared=True, enforce_export=True)
    assert result.export_allowed is False
    assert result.requires_review is True
    assert any("no se extrajeron cuentas" in r for r in result.reasons)

    # Caso 2: balance_squared=False y df vacío
    result2 = analyze_operational_quality(df_vacio, balance_squared=False, enforce_export=True)
    assert result2.export_allowed is False
    assert any("no se extrajeron cuentas" in r for r in result2.reasons)
