import pandas as pd
from pandas.testing import assert_frame_equal

from pipeline.operational_quality import analyze_operational_quality


def _frame(unclassified: bool = True) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "codigo_original": "110101", "nombre_original": "Caja",
            "monto": 100.0, "origen_columna": "activo",
            "origen_columna_efectiva": "activo", "es_total": False,
            "codigo_clasificado": "AC.01", "metodo": "dictionary_exact",
            "confianza": 0.98,
        },
        {
            "codigo_original": "110102", "nombre_original": "Banco",
            "monto": 50.0, "origen_columna": "activo",
            "origen_columna_efectiva": "activo", "es_total": False,
            "codigo_clasificado": "" if unclassified else "AC.01",
            "metodo": "unclassified", "confianza": 0.0,
        },
        {
            "codigo_original": "", "nombre_original": "SUMAS",
            "monto": 150.0, "origen_columna": "activo",
            "origen_columna_efectiva": "activo", "es_total": True,
            "codigo_clasificado": "", "metodo": "", "confianza": 0.0,
        },
    ])


def test_shadow_mide_no_clasificadas_sin_modificar_resultado():
    source = _frame(unclassified=True)
    before = source.copy(deep=True)

    result = analyze_operational_quality(
        source, balance_squared=True, enforce_export=False,
    )

    assert_frame_equal(source, before)
    assert result.mode == "shadow"
    assert result.requires_review is True
    assert result.export_allowed is True
    assert result.coverage["monetary"]["coverage_pct"] == 0.6667
    assert result.coverage["semantic"]["unknown_count"] == 1
    assert "1 cuenta(s)" in result.reasons[0]


def test_enforcement_bloquea_solo_exportacion_si_hay_revision():
    result = analyze_operational_quality(
        _frame(unclassified=True), balance_squared=True,
        enforce_export=True,
    )

    assert result.mode == "enforced"
    assert result.export_allowed is False


def test_control_aprueba_balance_completo_y_cuadrado():
    result = analyze_operational_quality(
        _frame(unclassified=False), balance_squared=True,
        enforce_export=True,
    )

    assert result.export_allowed is True
    assert result.coverage["monetary"]["coverage_pct"] == 1.0
    assert result.coverage["semantic"]["overall"] == 1.0


def test_descuadre_pide_revision_y_bloquea_al_aplicar_politica():
    result = analyze_operational_quality(
        _frame(unclassified=False), balance_squared=False,
        enforce_export=True,
    )

    assert result.export_allowed is False
    assert "no cuadra" in " ".join(result.reasons)
