import pytest
from parser_universal import (
    CuentaRaw,
    _INTERLEAVED_COLUMN_BLEED,
    _separar_tokens_monto_adherido,
    marcar_cuenta_sospechosa,
    parsear_linea,
    FormatoCodigo,
)
from pipeline.homologation_pipeline import HomologationPipeline


def test_h3_separar_tokens_monto_adherido():
    tokens = ["Remuneración", "Personal", "Permanente101.002.375", "133.943", "100.868.432"]
    separados = _separar_tokens_monto_adherido(tokens)
    assert separados == [
        "Remuneración", "Personal", "Permanente", "101.002.375", "133.943", "100.868.432"
    ]


def test_h3_interleaved_bleed_regex_detection():
    # Detecta colisiones de caracteres
    assert bool(_INTERLEAVED_COLUMN_BLEED.search("Constru1c0c.9i77.447"))
    assert bool(_INTERLEAVED_COLUMN_BLEED.search("Pers9o.n296.006"))
    assert bool(_INTERLEAVED_COLUMN_BLEED.search("Extran4je9r0a.079.373"))
    assert bool(_INTERLEAVED_COLUMN_BLEED.search("Cobra1d0o.s128.885"))
    assert bool(_INTERLEAVED_COLUMN_BLEED.search("Alimentac6ió8.961.634"))

    # NO da falsos positivos en nombres contables o legales legítimos
    assert not bool(_INTERLEAVED_COLUMN_BLEED.search("Seguro Cesantía Ley 19.728"))
    assert not bool(_INTERLEAVED_COLUMN_BLEED.search("Articulo 33 bis"))
    assert not bool(_INTERLEAVED_COLUMN_BLEED.search("Credito Ley 18.392"))
    assert not bool(_INTERLEAVED_COLUMN_BLEED.search("Banco Santander Cta 123456"))
    assert not bool(_INTERLEAVED_COLUMN_BLEED.search("PPM Tasa 1.5%"))


def test_h3_marcar_cuenta_sospechosa_no_afecta_leyes():
    cuenta_ley = CuentaRaw(
        linea=1,
        codigo="2.1.60.271",
        nombre="Seguro Cesantía Ley 19.728",
        monto=150000.0,
    )
    marcar_cuenta_sospechosa(cuenta_ley, "2.1.60.271 Seguro Cesantía Ley 19.728 150.000", [])
    assert cuenta_ley.requiere_revision_extraccion is False
    assert len(cuenta_ley.razones_revision_extraccion) == 0


def test_h3_parsear_linea_corrige_desplazamiento_8_columnas():
    # Línea con monto adherido al nombre
    linea = "3.1.10.101 Remuneración Personal Permanente101.002.375 133.943 100.868.432 0 0 0 100.868.432 0"
    cuenta = parsear_linea(
        linea=linea,
        numero_linea=130,
        formato_codigo=FormatoCodigo.PUNTO,
        separador_miles=".",
    )
    assert cuenta is not None
    assert cuenta.nombre == "Remuneración Personal Permanente"
    assert cuenta.montos_columnas["debitos"] == 101002375.0
    assert cuenta.montos_columnas["creditos"] == 133943.0
    assert cuenta.montos_columnas["saldo_deudor"] == 100868432.0
    assert cuenta.montos_columnas["perdida"] == 100868432.0


def test_h3_desenredado_colision_limpia_nombre_y_columnas():
    linea_colision = "2.1.60.266 Serv.Medico Cam.Chilena de la Constru1c0c.9i77.447 10.525.036 452.411 0 452.411 0 0 0"
    cuenta_raw = parsear_linea(
        linea=linea_colision,
        numero_linea=111,
        formato_codigo=FormatoCodigo.PUNTO,
        separador_miles=".",
    )
    assert cuenta_raw is not None
    assert cuenta_raw.nombre == "Serv.Medico Cam.Chilena de la Construcci"
    assert cuenta_raw.montos_columnas["debitos"] == 10977447.0
    assert cuenta_raw.montos_columnas["creditos"] == 10525036.0
    assert cuenta_raw.montos_columnas["saldo_deudor"] == 452411.0
    assert cuenta_raw.monto == 452411.0
    assert cuenta_raw.requiere_revision_extraccion is False


def test_h3_marcar_cuenta_sospechosa_si_queda_colision_no_resuelta():
    cuenta_contaminada = CuentaRaw(
        linea=1,
        codigo="2.1.60.266",
        nombre="Serv.Medico Cam.Chilena Constru1c0c.9i77.447",
        monto=452411.0,
    )
    marcar_cuenta_sospechosa(cuenta_contaminada, "2.1.60.266 Serv.Medico Cam.Chilena Constru1c0c.9i77.447 452.411", [])
    assert cuenta_contaminada.requiere_revision_extraccion is True
    assert "nombre_contaminado_por_fusion_de_columnas" in cuenta_contaminada.razones_revision_extraccion

