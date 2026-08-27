from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

import app_validacion as app
import parser_universal as parser
from clasificador_codigo_cuenta import ClasificadorCodigo


class FakePage:
    width = 612

    def __init__(self, rows):
        self._rows = rows

    def extract_words(self, **_kwargs):
        words = []
        for top, cells in self._rows:
            for x0, x1, text in cells:
                words.append({"text": text, "x0": x0, "x1": x1, "top": top})
        return words


def _header(top=10):
    return top, [
        (133, 146, "CODIGO"), (173, 190, "CUENTA"),
        (236, 250, "DEBITOS"), (268, 283, "CREDITOS"),
        (301, 314, "DEUDOR"), (331, 348, "ACREEDOR"),
        (366, 378, "ACTIVO"), (399, 411, "PASIVO"),
        (428, 444, "PERDIDAS"), (457, 475, "GANANCIAS"),
    ]


def _alternate_header(top=10):
    return top, [
        (120, 190, "DESCRIPCION"), (236, 250, "DEBE"),
        (268, 283, "HABER"), (301, 314, "DEUDOR"),
        (331, 348, "ACREEDOR"), (366, 378, "ACTIVO"),
        (399, 411, "PATRIMONIO"), (428, 444, "PERDIDA"),
        (457, 475, "GANANCIA"),
    ]


def _row(top, code, name, amounts):
    anchors = [257, 289, 321, 353, 386, 419, 449, 479]
    cells = [(133, 146, code), (150, 200, name)]
    cells.extend((anchor - 12, anchor, value) for anchor, value in zip(anchors, amounts))
    return top, cells


def test_extractor_coordenadas_preserva_codigo_nombre_y_ocho_columnas():
    page = FakePage([
        _header(),
        _row(20, "110101", "CAJA GENERAL", ["100", "0", "100", "0", "100", "0", "0", "0"]),
    ])

    lines, centers = parser._extraer_tabla_balance_10_columnas_por_coordenadas(page)
    cuenta = parser.parsear_linea(
        lines[0], 1, parser.FormatoCodigo.COMPACTO, ".", 1.0,
    )

    assert centers is not None
    assert cuenta is not None
    assert cuenta.codigo == "110101"
    assert cuenta.nombre == "CAJA GENERAL"
    assert cuenta.monto == 100
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO
    assert cuenta.montos_columnas == {
        "debitos": 100.0, "creditos": 0.0,
        "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
        "activo": 100.0, "pasivo": 0.0,
        "perdida": 0.0, "ganancia": 0.0,
    }


def test_ocho_columnas_prevalece_sobre_anio_detectado_en_cabecera():
    cuenta = parser.parsear_linea(
        "1.1.01.01 Caja 500 400 100 0 100 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", years=["2023"],
    )

    assert cuenta is not None
    assert cuenta.monto == 100
    assert cuenta.origen_columna is parser.OrigenColumna.ACTIVO


def test_balance_auditado_descarta_nota_y_alinea_dos_periodos():
    cuenta = parser.parsear_linea(
        "Efectivo y equivalentes al efectivo 6 107.874 93.372",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=["2019", "2018", "acumulado"],
        currencies=["CLP"],
        leading_note_column=True,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Efectivo y equivalentes al efectivo"
    assert cuenta.monto == 107874
    assert cuenta.montos_periodos["2019"] == 107874
    assert cuenta.montos_periodos["2018"] == 93372


def test_balance_auditado_ocr_descarta_guion_grafico_entre_periodos():
    cuenta = parser.parsear_linea(
        "Propiedad Planta y Equipo 9 13.734.230 - 12.874.543",
        1, parser.FormatoCodigo.SIN_CODIGO, ".", confianza_base=0.75,
        periodo_comparativo=True,
        years=["2018", "2017"],
        currencies=["M$"],
        leading_note_column=True,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Propiedad Planta y Equipo"
    assert cuenta.monto == 13_734_230
    assert cuenta.montos_periodos["2018"] == 13_734_230
    assert cuenta.montos_periodos["2017"] == 12_874_543


def test_balance_clasificado_reconoce_total_con_etiqueta_al_final():
    cuenta = parser.parsear_linea(
        "Activos Corrientes Totales 36.395.572 27.660.631",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True, years=["2018", "2017"],
    )

    assert cuenta is not None
    assert cuenta.es_total is True


def test_balance_auditado_detecta_columna_nota_con_encabezado_dividido():
    lines = [
        "Estados de Situación Financiera Consolidados Clasificados",
        "31 de diciembre de",
        "2018 2017",
        "ACTIVOS Nota MUS$ MUS$",
    ]
    years, _ = parser.detectar_años_y_monedas(lines)

    assert parser.detectar_columna_nota_comparativa(lines, years) is True


def test_balance_auditado_no_fusiona_nota_de_un_digito_con_importe():
    line = (
        "Deudores comerciales y otras cuentas por cobrar, corrientes "
        "6 1.357.245 2.436.366"
    )

    normalized = parser.normalizar_montos_fragmentados(
        line, preservar_columna_nota=True,
    )
    account = parser.parsear_linea(
        normalized, 1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=["2018", "2017"], currencies=["USD"],
        leading_note_column=True,
    )

    assert account is not None
    assert account.monto == 1_357_245
    assert account.montos_periodos["2018"] == 1_357_245
    assert account.montos_periodos["2017"] == 2_436_366


def test_moneda_de_cabecera_prevalece_sobre_leyenda_de_portada():
    lines = [
        "$ - Pesos chileno",
        "US$ - Dólar estadounidense",
        "Al 31 de diciembre de 2018 y 2017",
        "US$ US$",
    ]

    years, currencies = parser.detectar_años_y_monedas(lines)

    assert years == ["2018", "2017"]
    assert currencies == ["USD"]


def test_balance_auditado_descarta_nota_parentetica_y_conserva_ambos_periodos():
    lines = [
        "2018 2017",
        "Nota MUS$ MUS$",
        "Ingresos de actividades ordinarias (21) 110.193 124.879",
    ]
    years, currencies = parser.detectar_años_y_monedas(lines)
    has_note_column = parser.detectar_columna_nota_comparativa(lines, years)
    cuenta = parser.parsear_linea(
        lines[-1], 2, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=years,
        currencies=currencies,
        leading_note_column=has_note_column,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Ingresos de actividades ordinarias"
    assert cuenta.monto == 110193
    assert cuenta.montos_periodos["2018"] == 110193
    assert cuenta.montos_periodos["2017"] == 124879


def test_balance_auditado_conserva_guion_cero_despues_de_nota_parentetica():
    lines = [
        "2018 2017",
        "Nota M$ M$",
        "Pasivos por Impuestos corriente (12) 5.265.398 -",
    ]
    years, currencies = parser.detectar_años_y_monedas(lines)
    has_note_column = parser.detectar_columna_nota_comparativa(lines, years)
    cuenta = parser.parsear_linea(
        lines[-1], 2, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=years,
        currencies=currencies,
        leading_note_column=has_note_column,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Pasivos por Impuestos corriente"
    assert cuenta.monto == 5265398
    assert cuenta.montos_periodos["2018"] == 5265398
    assert cuenta.montos_periodos["2017"] == 0


def test_balance_auditado_une_glosas_partidas_con_nota_y_dos_periodos():
    lines = [
        "Inversiones contabilizadas utilizando el método",
        "de la participación (13) 689 900",
        "Participación en las pérdidas de asociadas",
        "que se contabilizan utilizando el valor patrimonial (13) (211) (600)",
        "Ganancia atribuible a los propietarios",
        "de la controladora (3.488) 800",
    ]

    merged = parser.asociar_lineas_verticales(lines)

    assert merged == [
        "Inversiones contabilizadas utilizando el método de la participación (13) 689 900",
        "Participación en las pérdidas de asociadas que se contabilizan utilizando el valor patrimonial (13) (211) (600)",
        "Ganancia atribuible a los propietarios de la controladora (3.488) 800",
    ]
    accounts = [
        parser.parsear_linea(
            line, index, parser.FormatoCodigo.SIN_CODIGO, ".",
            periodo_comparativo=True, years=["2018", "2017"],
            currencies=["MUS$"], leading_note_column=True,
        )
        for index, line in enumerate(merged)
    ]
    assert [account.nombre for account in accounts] == [
        "Inversiones contabilizadas utilizando el método de la participación",
        "Participación en las pérdidas de asociadas que se contabilizan utilizando el valor patrimonial",
        "Ganancia atribuible a los propietarios de la controladora",
    ]
    assert accounts[1].montos_periodos["2018"] == -211.0
    assert accounts[1].montos_periodos["2017"] == -600.0
    assert accounts[2].montos_periodos["2018"] == -3488.0
    assert accounts[2].montos_periodos["2017"] == 800.0


@pytest.mark.parametrize("line", [
    "Ganancia bruta 2.572 6.409",
    "Ganancia (Pérdida) antes de Impuestos (4.860) 2.058",
    "Ganancia (pérdida) procedente de operaciones continuadas (3.462) 1.069",
    "Ganancia (pérdida) del ejercicio (3.462) 1.069",
])
def test_balance_auditado_marca_resultados_calculados_como_controles(line):
    account = parser.parsear_linea(
        line, 1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True, years=["2018", "2017"],
    )

    assert account is not None
    assert account.es_total


def test_balance_auditado_no_convierte_encabezado_de_periodos_en_cuenta():
    assert parser.parsear_linea(
        "31 de diciembre de 2018 2017",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True, years=["2018", "2017"],
    ) is None


def test_balance_auditado_reproduce_subtotal_sin_sumar_referencias_de_nota():
    lines = [
        "2018 2017",
        "ACTIVOS Nota MUS$ MUS$",
        "Efectivo y equivalentes al efectivo (6) 2.566 6.839",
        "Otros activos financieros, corriente (7) - 142",
        "Otros activos no financieros, corriente (8) 629 592",
        "Deudores comerciales y otras cuentas por cobrar (9) 26.660 22.502",
        "Cuentas por cobrar a entidades relacionadas, corriente (10) 6.053 5.776",
        "Inventarios (11) 5.132 3.052",
        "Activos por impuestos corriente (12) 1.748 1.102",
        "Total activo corriente 42.788 40.005",
    ]
    years, currencies = parser.detectar_años_y_monedas(lines)
    has_note_column = parser.detectar_columna_nota_comparativa(lines, years)
    cuentas = [
        cuenta
        for index, line in enumerate(lines[2:], start=2)
        if (
            cuenta := parser.parsear_linea(
                line, index, parser.FormatoCodigo.SIN_CODIGO, ".",
                periodo_comparativo=True,
                years=years,
                currencies=currencies,
                leading_note_column=has_note_column,
            )
        )
    ]
    detalle = [cuenta for cuenta in cuentas if not cuenta.es_total]
    total = next(cuenta for cuenta in cuentas if cuenta.es_total)

    assert sum(cuenta.montos_periodos["2018"] for cuenta in detalle) == 42788
    assert sum(cuenta.montos_periodos["2017"] for cuenta in detalle) == 40005
    assert total.montos_periodos["2018"] == 42788
    assert total.montos_periodos["2017"] == 40005


def test_balance_auditado_descarta_pie_legal_de_notas():
    assert parser._es_linea_basura(
        "Las notas adjuntas números 1 al 27 forman parte integral de estos estados financieros"
    )
    assert parser._es_linea_basura(
        "al 27 forman parte integral de estos estados financieros 2"
    )
    assert parser._es_linea_basura(
        "forman parte integral de estos estados financieros 1"
    )
    assert parser._es_linea_basura("de diciembre 2018 2017")
    assert parser._es_linea_basura(
        "Estado de resultados integrales Por los períodos de 12 meses 2018 2017"
    )


def test_balance_auditado_reconoce_total_con_etiqueta_al_final():
    cuenta = parser.parsear_linea(
        "Patrimonio total 24.318.500 21.100.000",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=["2018", "2017"],
        currencies=["USD"],
    )

    assert cuenta is not None
    assert cuenta.es_total is True


def test_balance_auditado_reconoce_patrimonio_atribuible_como_subtotal():
    cuenta = parser.parsear_linea(
        "Patrimonio atribuible a los propietarios de la controladora (148) 4.352",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
        years=["2018", "2017"],
        currencies=["USD"],
        leading_note_column=True,
    )

    assert cuenta is not None
    assert cuenta.es_total is True
    assert cuenta.montos_periodos["2018"] == -148
    assert cuenta.montos_periodos["2017"] == 4352


def test_extractor_coordenadas_recupera_ceros_ocr_sin_contaminar_nombre():
    page = FakePage([
        _header(),
        _row(20, "110101", "CUENTAS SOCIOS", [
            "3.732:989.407", "seo", "3.732.989.407", "]", "3.732.989.407", "»", "o", "O",
        ]),
    ])

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(page)
    cuenta = parser.parsear_linea(
        lines[0], 1, parser.FormatoCodigo.COMPACTO, ".", 1.0,
    )

    assert cuenta is not None
    assert cuenta.nombre == "CUENTAS SOCIOS"
    assert cuenta.montos_columnas == {
        "debitos": 3732989407.0, "creditos": 0.0,
        "saldo_deudor": 3732989407.0, "saldo_acreedor": 0.0,
        "activo": 3732989407.0, "pasivo": 0.0,
        "perdida": 0.0, "ganancia": 0.0,
    }


def test_extractor_reutiliza_layout_en_paginas_sin_encabezado():
    first = FakePage([_header(), _row(20, "110101", "CAJA", ["5", "0", "5", "0", "5", "0", "0", "0"])])
    second = FakePage([_row(20, "210101", "PROVEEDORES", ["0", "5", "0", "5", "0", "5", "0", "0"])])

    _, centers = parser._extraer_tabla_balance_10_columnas_por_coordenadas(first)
    lines, reused = parser._extraer_tabla_balance_10_columnas_por_coordenadas(second, centers)

    assert reused == centers
    assert lines == ["210101 PROVEEDORES 0 5 0 5 0 5 0 0"]


def test_extraer_lineas_inicializa_layout_antes_del_fallback(monkeypatch, tmp_path):
    class NativePage:
        def extract_text(self):
            return "110101 CAJA 100"

    class NativePdf:
        pages = [NativePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    observed_centers = []

    monkeypatch.setattr(parser.pdfplumber, "open", lambda _path: NativePdf())
    monkeypatch.setattr(parser, "_extraer_tabla_balance_8_columnas", lambda _page: [])

    def coordinate_fallback(_page, centers=None):
        observed_centers.append(centers)
        return [], centers

    monkeypatch.setattr(
        parser, "_extraer_tabla_balance_por_coordenadas", coordinate_fallback,
    )

    lines, used_ocr, rotation = parser.ParserPDF()._extraer_lineas(
        tmp_path / "balance.pdf",
    )

    assert observed_centers == [None]
    assert lines == ["110101 CAJA 100"]
    assert used_ocr is False
    assert rotation == 0


def test_parsear_linea_elimina_raya_ocr_antes_del_nombre():
    for dash in ("-", "–", "—", "−"):
        cuenta = parser.parsear_linea(
            f"11010100 {dash} Fondo Fijo 400.000 0 400.000 0 400.000 0 0 0",
            1,
            parser.FormatoCodigo.COMPACTO,
            ".",
            1.0,
        )

        assert cuenta is not None
        assert cuenta.nombre == "Fondo Fijo"


def test_total_con_comilla_ocr_no_se_considera_detalle():
    cuenta = parser.parsear_linea(
        "“Total Acumulado 100 100 50 50 40 40 10 10",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert cuenta is not None
    assert cuenta.es_total is True


def test_total_foral_ocr_no_convierte_primer_importe_en_codigo():
    cuenta = parser.parsear_linea(
        "[foral] 7.608.246.111 7.608.246.111 1.259.149.847 "
        "1.259.149.847 458.598.280 458.598.280 848.102.769 848.102.769",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo is None
    assert cuenta.es_total is True


def test_resultado_con_codigo_es_cuenta_y_no_subtotal():
    cuenta = parser.parsear_linea(
        "23070200 Resultado Acumuladas 100 40 60 0 60 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert cuenta is not None
    assert cuenta.codigo == "23070200"
    assert cuenta.es_total is False


def test_codigo_compacto_120_clasifica_activo_fijo_y_depreciacion():
    classifier = ClasificadorCodigo()

    asset = classifier.clasificar("12040100")
    depreciation = classifier.clasificar("12060305")

    assert asset is not None and asset.codigo_estandar == "ANC.01"
    assert depreciation is not None and depreciation.codigo_estandar == "ANC.01"
    assert asset.confianza == 0.96


def test_certificacion_codificada_ignora_ruido_sin_codigo():
    values = {
        "debitos": 100.0, "creditos": 0.0,
        "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
        "activo": 100.0, "pasivo": 0.0,
        "perdida": 0.0, "ganancia": 0.0,
    }
    detalles = [
        parser.CuentaRaw(i, f"11010{i}", f"Caja {i}", 100,
                         montos_columnas=dict(values))
        for i in range(1, 4)
    ]
    ruido = parser.CuentaRaw(
        4, None, "REPRESENTANTE LEGAL", 999,
        montos_columnas={column: 999.0 for column in parser.RAW_MONETARY_COLUMNS},
    )
    subtotal = parser.CuentaRaw(
        5, None, "SUMAS", 300, es_total=True,
        montos_columnas={key: value * 3 for key, value in values.items()},
    )

    result = parser.certificar_extraccion_columnas([*detalles, ruido, subtotal])

    assert result.estado == "certificada"
    assert result.filas_evaluadas == 3


def test_parsear_linea_reconstruye_movimiento_ocr_desde_saldo_consistente():
    cuenta = parser.parsear_linea(
        "12020800 Termo 1.201.569.748 0 569.748 0 569.748 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 569748
    assert cuenta.columnas_derivadas == ["debitos"]


def test_parsear_linea_elimina_movimiento_fantasma_con_tres_evidencias():
    cuenta = parser.parsear_linea(
        "12060305 Depreciación Acumulada 1.148 2.730.292 0 2.730.292 0 2.730.292 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 0
    assert cuenta.montos_columnas["creditos"] == 2730292
    assert cuenta.columnas_derivadas == ["debitos"]


def test_parsear_linea_ocr_reconstruye_debito_desde_saldo_y_clasificacion():
    cuenta = parser.parsear_linea(
        "1.02.03.04 Equipos 40.269 0 640.269 0 640.269 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 640_269
    assert cuenta.columnas_derivadas == ["debitos"]


def test_parsear_linea_ocr_reconstruye_saldo_desde_movimiento_y_clasificacion():
    cuenta = parser.parsear_linea(
        "1.01.09.10 Existencias 24.421.797 0 24.821.797 0 24.421.797 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["saldo_deudor"] == 24_421_797
    assert cuenta.columnas_derivadas == ["saldo_deudor"]


def test_parsear_linea_ocr_elimina_prefijo_pegado_si_saldo_cero_exige_igualdad():
    cuenta = parser.parsear_linea(
        "2.01.01.10 Préstamo 121.866.316 1.866.316 0 0 0 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 1_866_316
    assert cuenta.montos_columnas["creditos"] == 1_866_316
    assert cuenta.columnas_derivadas == ["debitos"]


def test_parsear_linea_ocr_corrige_digito_fantasma_solo_si_mejora_identidad():
    cuenta = parser.parsear_linea(
        "3202007 Aseo 81.135 0 81.135 0 9 0 81.135 9",
        1, parser.FormatoCodigo.COMPACTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["activo"] == 0
    assert cuenta.montos_columnas["ganancia"] == 0
    assert set(cuenta.columnas_derivadas) == {"activo", "ganancia"}


def test_parsear_linea_ocr_corrige_diez_fantasma_si_mejora_identidad():
    cuenta = parser.parsear_linea(
        "4.01.03.18 Combustibles 27.196.269 10 27.196.269 0 0 0 27.196.269 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["creditos"] == 0
    assert cuenta.columnas_derivadas == ["creditos"]


def test_parsear_linea_ocr_elimina_clasificacion_marginal_con_saldo_completo():
    cuenta = parser.parsear_linea(
        "4.01.03.05 Protección 1.135.074 0 1.135.074 0 0 0 1.135.074 7.669",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["perdida"] == 1_135_074
    assert cuenta.montos_columnas["ganancia"] == 0
    assert cuenta.columnas_derivadas == ["ganancia"]


def test_parsear_linea_nativa_preserva_importe_pequeno_real():
    cuenta = parser.parsear_linea(
        "3202007 Ajuste 9 0 9 0 0 0 9 0",
        1, parser.FormatoCodigo.COMPACTO, ".", confianza_base=1.0,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["debitos"] == 9
    assert cuenta.montos_columnas["perdida"] == 9
    assert cuenta.columnas_derivadas == []


def test_correccion_humana_recertifica_y_actualiza_origen_efectivo():
    details = [
        parser.parsear_linea(
            "110101 Caja 100 0 100 0 90 0 0 0",
            1, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "210101 Proveedores 0 40 0 40 0 40 0 0",
            2, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "410101 Ventas 0 60 0 60 0 0 0 60",
            3, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "Sumas 100 100 100 100 100 40 0 60",
            4, parser.FormatoCodigo.COMPACTO, ".",
        ),
    ]
    assert all(details)
    frame = pd.DataFrame([
        {"linea": c.linea, **c.montos_columnas} for c in details
    ])
    frame.loc[frame["linea"] == 1, "activo"] = 100

    corrected, certification = app._aplicar_correcciones_extraccion(details, frame)

    assert certification.estado == "parcial"
    assert corrected[0].monto == 100
    assert corrected[0].origen_columna == parser.OrigenColumna.ACTIVO
    assert "correccion_humana" in corrected[0].columnas_derivadas


def test_diagnostico_extraccion_prioriza_fila_que_rompe_clasificacion():
    cuenta = parser.CuentaRaw(
        linea=7, codigo="110101", nombre="Caja", monto=100,
        montos_columnas={
            "debitos": 100, "creditos": 0,
            "saldo_deudor": 100, "saldo_acreedor": 0,
            "activo": 0, "pasivo": 0, "perdida": 0, "ganancia": 0,
        },
    )
    certification = SimpleNamespace(filas_inconsistentes=[7])

    diagnosis = app._diagnosticar_filas_extraccion([cuenta], certification)

    assert diagnosis[7]["prioridad"] == 1
    assert "Activo/Pasivo" in diagnosis[7]["diagnostico"]
    assert diagnosis[7]["error_movimiento"] == 0
    assert diagnosis[7]["error_clasificacion"] == 100
    assert diagnosis[7]["valores_sugeridos"] == ""


def test_diagnostico_extraccion_sugiere_debito_omitido_sin_autocorregir():
    cuenta = parser.CuentaRaw(
        linea=0, codigo=None, nombre="Caja", monto=2_309_117,
        montos_columnas={
            "debitos": 0, "creditos": 6_006_281,
            "saldo_deudor": 2_309_117, "saldo_acreedor": 0,
            "activo": 2_309_117, "pasivo": 0,
            "perdida": 0, "ganancia": 0,
        },
    )

    diagnosis = app._diagnosticar_filas_extraccion(
        [cuenta], SimpleNamespace(filas_inconsistentes=[0]),
    )

    assert "Debe: 0 → 8,315,398" in diagnosis[0]["valores_sugeridos"]
    assert cuenta.montos_columnas["debitos"] == 0


def test_crear_cuenta_manual_preserva_ocho_columnas_y_trazabilidad():
    nueva = app._crear_cuenta_manual_extraccion(
        [], codigo="2301001", nombre="Capital Social",
        montos={
            "debitos": 0, "creditos": 15_201_000,
            "saldo_deudor": 0, "saldo_acreedor": 15_201_000,
            "activo": 0, "pasivo": 15_201_000,
            "perdida": 0, "ganancia": 0,
        },
    )

    assert nueva.nombre == "Capital Social"
    assert nueva.monto == 15_201_000
    assert nueva.origen_columna is parser.OrigenColumna.PASIVO
    assert nueva.columnas_derivadas == ["ingreso_manual_analista"]
    assert nueva.montos_columnas["creditos"] == 15_201_000


def test_diagnostico_extraccion_explica_firma_y_total_sin_autocorregir():
    firma = parser.CuentaRaw(
        linea=8, codigo=None, nombre="Firma Representante Legal", monto=100,
        montos_columnas={column: 0 for column in parser.RAW_MONETARY_COLUMNS},
    )
    total = parser.CuentaRaw(
        linea=9, codigo=None, nombre="Totales Iguales", monto=100,
        es_total=False,
        montos_columnas={column: 0 for column in parser.RAW_MONETARY_COLUMNS},
    )

    diagnosis = app._diagnosticar_filas_extraccion([firma, total])

    assert diagnosis[8]["prioridad"] == 2
    assert "marque Excluir" in diagnosis[8]["accion_sugerida"]
    assert diagnosis[9]["prioridad"] == 2
    assert "marque Subtotal/total" in diagnosis[9]["accion_sugerida"]
    assert firma.monto == 100
    assert total.es_total is False

def test_total_acumulado_completa_par_de_saldos_y_certifica_detalle():
    lines = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 40 0 40 0 40 0 0",
        "410101 Ventas 0 60 0 60 0 0 0 60",
        "Total Acumulado 100 100 0 100 100 40 0 60",
    ]
    cuentas = [
        parser.parsear_linea(line, i, parser.FormatoCodigo.COMPACTO, ".")
        for i, line in enumerate(lines, 1)
    ]

    assert all(cuenta is not None for cuenta in cuentas)
    assert cuentas[-1].montos_columnas["saldo_deudor"] == 100
    result = parser.certificar_extraccion_columnas(cuentas)
    assert result.estado == "parcial"
    assert not any(result.diferencias.values())


def test_extractor_acepta_sinonimos_y_filas_sin_codigo():
    page = FakePage([
        _alternate_header(),
        (20, [
            (120, 190, "Caja principal"),
            (245, 257, "100"), (277, 289, "0"),
            (309, 321, "100"), (341, 353, "0"),
            (374, 386, "100"), (407, 419, "0"),
            (437, 449, "0"), (467, 479, "0"),
        ]),
    ])

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(page)
    cuenta = parser.parsear_linea(
        lines[0], 1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert centers is not None
    assert cuenta is not None
    assert cuenta.codigo is None
    assert cuenta.nombre == "Caja principal"
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_extractor_acepta_encabezado_ocr_con_plural_y_debitos_deformado():
    page = FakePage([
        (10, [
            (120, 190, "CUENTA"), (236, 250, "pEBITOS"),
            (268, 283, "CREDITOS"), (301, 314, "DEUDOR"),
            (331, 348, "ACREEDOR"), (366, 378, "ACTIVOS"),
            (399, 411, "PASIVOS"), (428, 444, "PERDIDA"),
            (457, 475, "GANANCIA"),
        ]),
        _row(20, "11010100", "Fondo Fijo", [
            "400.000", "0", "400.000", "0", "400.000", "0", "0", "0",
        ]),
    ])

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(page)

    assert centers is not None
    assert lines == [
        "11010100 Fondo Fijo 400.000 0 400.000 0 400.000 0 0 0",
    ]


def test_extractor_detecta_encabezado_distribuido_en_dos_lineas():
    page = FakePage([
        (10, [
            (120, 190, "CUENTA"), (236, 250, "DEBITOS"),
            (268, 283, "CREDITOS"), (366, 378, "ACTIVO"),
            (399, 411, "PASIVO"), (428, 444, "PERDIDAS"),
            (457, 475, "GANANCIAS"),
        ]),
        (15, [(301, 314, "DEUDOR"), (331, 348, "ACREEDOR")]),
        (25, [
            (120, 190, "Caja"), (245, 257, "10"), (277, 289, "0"),
            (309, 321, "10"), (341, 353, "0"), (374, 386, "10"),
            (407, 419, "0"), (437, 449, "0"), (467, 479, "0"),
        ]),
    ])

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(page)

    assert centers is not None
    assert lines == ["Caja 10 0 10 0 10 0 0 0"]


def test_extractor_tolera_encabezados_deformados_por_ocr():
    page = FakePage([
        (10, [
            (120, 190, "Cuenta"), (236, 250, "Debe$"),
            (268, 283, "Haber$"), (301, 314, "Deudor$"),
            (331, 348, "Acreeedor$"), (366, 378, "Activo$"),
            (399, 411, "Pasiwo$"), (428, 444, "Pérdida$"),
            (457, 475, "Ganancia$"),
        ]),
        (20, [
            (120, 190, "Caja"), (245, 257, "10"), (277, 289, "0"),
            (309, 321, "10"), (341, 353, "0"), (374, 386, "10"),
            (407, 419, "0"), (437, 449, "0"), (467, 479, "0"),
        ]),
    ])

    lines, centers = parser._extraer_tabla_balance_por_coordenadas(page)

    assert centers is not None
    assert lines == ["Caja 10 0 10 0 10 0 0 0"]


def test_extractor_no_pega_monto_a_nombre_largo_que_invade_columna():
    page = FakePage([
        _header(),
        (20, [
            (133, 146, "110502"),
            (150, 240, "ANTICIPO PROVEEDORES MONEDA EXTRANJERA"),
            (237, 257, "109.934.276"), (288, 289, "-"),
            (301, 321, "109.934.276"), (352, 353, "-"),
            (366, 386, "109.934.276"), (418, 419, "-"),
            (448, 449, "-"), (478, 479, "-"),
        ]),
    ])

    lines, _ = parser._extraer_tabla_balance_por_coordenadas(page)
    account = parser.parsear_linea(
        lines[0], 1, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert account is not None
    assert account.nombre == "ANTICIPO PROVEEDORES MONEDA EXTRANJERA"
    assert account.montos_columnas["debitos"] == 109_934_276
    assert len(account.montos_columnas) == 8


def test_reconstruye_movimiento_solo_con_saldo_y_clasificacion_coincidentes():
    account = parser.parsear_linea(
        "MANTENCION EQUIPO 0 0 4.732.547 0 0 0 4.732.547 0",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert account is not None
    assert account.montos_columnas["debitos"] == 4_732_547
    assert account.columnas_derivadas == ["debitos"]


def test_no_reconstruye_movimiento_si_clasificacion_no_confirma_saldo():
    account = parser.parsear_linea(
        "MANTENCION EQUIPO 0 0 4.732.547 0 0 0 4.000.000 0",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert account is not None
    assert account.montos_columnas["debitos"] == 0
    assert account.columnas_derivadas == []


def test_certificacion_compara_con_subtotal_independiente():
    rows = [
        parser.parsear_linea(
            "110101 CAJA 100 0 100 0 100 0 0 0",
            1, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "210101 PROVEEDORES 0 100 0 100 0 100 0 0",
            2, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "SUBTOTALES 100 100 100 100 100 100 0 0",
            3, parser.FormatoCodigo.COMPACTO, ".",
        ),
    ]

    certification = parser.certificar_extraccion_columnas(
        [row for row in rows if row is not None], metodo="coordinates_10_columns"
    )

    assert certification.estado == "certificada"
    assert certification.diferencias == {column: 0.0 for column in parser.RAW_MONETARY_COLUMNS}


def test_certificacion_falla_si_una_columna_no_reproduce_el_subtotal():
    detail = parser.parsear_linea(
        "110101 CAJA 90 0 90 0 90 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )
    total = parser.parsear_linea(
        "SUBTOTALES 110 0 110 0 110 0 0 0",
        2, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas(
        [detail, total], metodo="coordinates_10_columns"
    )

    assert certification.estado == "fallida"
    assert certification.diferencias["debitos"] == -20.0
    assert certification.razones


def test_sin_subtotal_no_bloquea_formatos_legacy():
    detail = parser.CuentaRaw(
        linea=1, codigo=None, nombre="Caja", monto=100,
        origen_columna=parser.OrigenColumna.ACTIVO,
    )

    certification = parser.certificar_extraccion_columnas([detail])

    assert certification.estado == "no_evaluable"


def test_certificacion_detecta_fila_internamente_inconsistente():
    detail = parser.parsear_linea(
        "110101 CAJA 100 0 80 0 80 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )
    total = parser.parsear_linea(
        "SUBTOTALES 100 0 80 0 80 0 0 0",
        2, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas([detail, total])

    assert certification.estado == "fallida"
    assert certification.filas_inconsistentes == [1]
    assert "identidades" in certification.razones[-1]


def test_certificacion_valida_totales_iguales_si_estan_presentes():
    detail = parser.parsear_linea(
        "110101 CAJA 100 100 0 0 0 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )
    subtotal = parser.parsear_linea(
        "SUBTOTALES 100 100 0 0 0 0 0 0",
        2, parser.FormatoCodigo.COMPACTO, ".",
    )
    final = parser.parsear_linea(
        "TOTALES IGUALES 100 100 0 0 50 50 25 25",
        3, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas([detail, subtotal, final])

    assert certification.estado == "certificada"
    assert certification.totales_finales_validos is True


def test_certificacion_degrada_a_parcial_si_fila_final_ocr_esta_incompleta():
    details = [
        parser.parsear_linea(
            "110101 ACTIVO 100 0 100 0 100 0 0 0",
            1, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "210101 PASIVO 0 60 0 60 0 60 0 0",
            2, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "310101 GANANCIA 0 40 0 40 0 0 0 40",
            3, parser.FormatoCodigo.COMPACTO, ".",
        ),
    ]
    subtotal = parser.parsear_linea(
        "SUBTOTAL 100 100 100 100 100 60 0 40",
        4, parser.FormatoCodigo.COMPACTO, ".",
    )
    incomplete_final = parser.parsear_linea(
        "SUMAS IGUALES 100 0 100 0 100 0 40 0",
        5, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas(
        [*details, subtotal, incomplete_final],
    )

    assert certification.estado == "parcial"
    assert certification.totales_finales_validos is None
    assert all(value == 0 for value in certification.diferencias.values())
    assert any("columnas vacías" in reason for reason in certification.razones)


def test_certificacion_no_acepta_subtotal_con_ecuacion_contable_invalida():
    detail = parser.parsear_linea(
        "110101 ACTIVO 100 0 100 0 100 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )
    subtotal = parser.parsear_linea(
        "SUBTOTAL 100 0 100 0 100 0 0 0",
        2, parser.FormatoCodigo.COMPACTO, ".",
    )
    incomplete_final = parser.parsear_linea(
        "SUMAS IGUALES 100 0 100 0 100 0 0 0",
        3, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas(
        [detail, subtotal, incomplete_final],
    )

    assert certification.estado == "fallida"
    assert any("ecuación" in reason for reason in certification.razones)


def test_certificacion_reconoce_resultado_puente_hasta_sumas_iguales():
    details = [
        parser.parsear_linea(
            "110101 ACTIVO 100 0 100 0 100 0 0 0",
            1, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "210101 PASIVO 0 60 0 60 0 60 0 0",
            2, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "310101 GANANCIA 0 40 0 40 0 0 0 40",
            3, parser.FormatoCodigo.COMPACTO, ".",
        ),
    ]
    subtotal = parser.parsear_linea(
        "SUMAS 100 100 100 100 100 60 0 40",
        4, parser.FormatoCodigo.COMPACTO, ".",
    )
    bridge = parser.parsear_linea(
        "PERDIDA O GANANCIA 0 0 0 0 0 40 40 0",
        5, parser.FormatoCodigo.COMPACTO, ".",
    )
    final = parser.parsear_linea(
        "SUMAS IGUALES 100 100 100 100 100 100 40 40",
        6, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas(
        [*details, subtotal, bridge, final], metodo="coordinates_10_columns",
    )

    assert bridge.es_total is True
    assert certification.estado == "certificada"
    assert certification.diferencias == {
        column: 0.0 for column in parser.RAW_MONETARY_COLUMNS
    }
    assert certification.totales_finales_validos is True
    assert certification.resultado_ejercicio == 40
    assert certification.tipo_resultado == "utilidad"


def test_certificacion_reconstruye_digito_final_truncado_en_controles_pdf():
    rows = [
        parser.parsear_linea(
            "CAJA 10.764.254.525 0 10.764.254.525 0 10.764.254.525 0 0 0",
            1, parser.FormatoCodigo.SIN_CODIGO, ".",
        ),
        parser.parsear_linea(
            "CAPITAL 0 10.764.254.525 0 10.764.254.525 0 10.764.254.525 0 0",
            2, parser.FormatoCodigo.SIN_CODIGO, ".",
        ),
        parser.parsear_linea(
            "SUBTOTAL 1.076.425.452 1.076.425.452 10.764.254.525 10.764.254.525 "
            "10.764.254.525 10.764.254.525 0 0",
            3, parser.FormatoCodigo.SIN_CODIGO, ".",
        ),
        parser.parsear_linea(
            "TOTALES 1.076.425.452 1.076.425.452 10.764.254.525 10.764.254.525 "
            "10.764.254.525 10.764.254.525 0 0",
            4, parser.FormatoCodigo.SIN_CODIGO, ".",
        ),
    ]

    certification = parser.certificar_extraccion_columnas(rows)

    assert certification.estado == "certificada"
    assert certification.diferencias["debitos"] == 0
    assert certification.diferencias["creditos"] == 0
    assert certification.columnas_total_reconstruidas == ["debitos", "creditos"]


def test_descarta_pie_articulo_codigo_tributario_con_numero_en_columna():
    row = parser.parsear_linea(
        "Artículo Código Tributario : Balance confeccionado 0 0 0 0 100 0 0 0",
        61, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert row is None


def test_gate_documental_detiene_anexo_identificado_como_otro():
    signature = SimpleNamespace(
        document_type=SimpleNamespace(value="OTRO"),
        has_headers=False,
        confidence=0.70,
    )

    assert app._documento_no_es_balance(signature) is True


def test_gate_documental_no_rechaza_balance_ni_diagnostico_incierto():
    balance = SimpleNamespace(
        document_type=SimpleNamespace(value="BALANCE"),
        has_headers=True,
        confidence=0.90,
    )
    uncertain = SimpleNamespace(
        document_type=SimpleNamespace(value="OTRO"),
        has_headers=False,
        confidence=0.20,
    )

    assert app._documento_no_es_balance(balance) is False
    assert app._documento_no_es_balance(uncertain) is False


def test_balance_clasificado_cuadrado_obtiene_certificacion_parcial():
    accounts = [
        parser.CuentaRaw(1, None, "Total activos", 500),
        parser.CuentaRaw(2, None, "Total pasivos y patrimonio neto", 500),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "parcial"
    assert certification.totales_finales_validos is True
    assert certification.diferencias["activo_menos_pasivo_patrimonio"] == 0


def test_balance_clasificado_descuadrado_falla():
    accounts = [
        parser.CuentaRaw(1, None, "TOTAL ACTIVOS", 500),
        parser.CuentaRaw(2, None, "TOTAL PASIVOS Y PATRIMONIO", 450),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "fallida"
    assert certification.totales_finales_validos is False


def test_balance_clasificado_falla_si_detalle_no_reproduce_subtotal():
    accounts = [
        parser.CuentaRaw(1, None, "ACTIVOS CORRIENTES", None),
        parser.CuentaRaw(2, None, "Caja", 60),
        parser.CuentaRaw(3, None, "Clientes", 20),
        parser.CuentaRaw(4, None, "TOTAL ACTIVOS CORRIENTES", 100, es_total=True),
        parser.CuentaRaw(5, None, "Total activos", 100, es_total=True),
        parser.CuentaRaw(6, None, "Total pasivos y patrimonio", 100, es_total=True),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "fallida"
    assert certification.metodo == "classified_section_totals"
    assert certification.diferencias["seccion:activos corrientes"] == -20


def test_balance_clasificado_registra_subtotal_reproducido():
    accounts = [
        parser.CuentaRaw(1, None, "ACTIVOS CORRIENTES", None),
        parser.CuentaRaw(2, None, "Caja", 60),
        parser.CuentaRaw(3, None, "Clientes", 40),
        parser.CuentaRaw(4, None, "TOTAL ACTIVOS CORRIENTES", 100, es_total=True),
        parser.CuentaRaw(5, None, "Total activos", 100, es_total=True),
        parser.CuentaRaw(6, None, "Total pasivos y patrimonio", 100, es_total=True),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "parcial"
    assert certification.diferencias["seccion:activos corrientes"] == 0
    assert "1 subtotales" in certification.razones[0]


def test_utilidad_del_ejercicio_es_detalle_del_patrimonio():
    accounts = [
        parser.CuentaRaw(1, None, "PATRIMONIO", None),
        parser.CuentaRaw(2, None, "Capital", 120),
        parser.CuentaRaw(
            3, None, "UTILIDAD DEL EJERCICIO", -20, es_total=True,
        ),
        parser.CuentaRaw(4, None, "TOTAL PATRIMONIO", 100, es_total=True),
        parser.CuentaRaw(5, None, "Total activos", 100, es_total=True),
        parser.CuentaRaw(6, None, "Total pasivos y patrimonio", 100, es_total=True),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "parcial"
    assert certification.diferencias["seccion:patrimonio"] == 0


def test_parsear_linea_descarta_metadatos_numericos_de_cabecera():
    assert parser.parsear_linea(
        "Nivel 5", 1, parser.FormatoCodigo.SIN_CODIGO, ".",
    ) is None
    assert parser.parsear_linea(
        "Desde Enero a Diciembre 2019", 2, parser.FormatoCodigo.SIN_CODIGO, ".",
    ) is None
    assert parser.parsear_linea(
        "2018 2017", 3, parser.FormatoCodigo.SIN_CODIGO, ".",
    ) is None


def test_periodo_comparativo_selecciona_actual_aunque_sea_cero():
    account = parser.parsear_linea(
        "Inversiones - 2.631.606 6.1.2",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
    )

    assert account is not None
    assert account.nombre == "Inversiones"
    assert account.monto == 0
    assert account.montos_periodos == {"actual": 0.0, "anterior": 2631606.0}


def test_periodo_comparativo_preserva_actual_y_anterior_sin_nota():
    account = parser.parsear_linea(
        "Efectivo y equivalentes 8.257 8.368",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
        periodo_comparativo=True,
    )

    assert account is not None
    assert account.monto == 8257
    assert account.montos_periodos == {"actual": 8257.0, "anterior": 8368.0}


def test_ocr_no_repite_lectura_si_ya_tiene_filas_y_totales():
    text = (
        "Cuenta Debe Haber Deudor Acreedor Activo Pasivo Perdida Ganancia\n"
        "Caja 100 0 100 0 100 0 0 0\n"
        "TOTALES 100 100 100 100 100 100 0 0"
    )

    assert parser._ocr_requiere_alternativa(text, es_ultima_pagina=True) is False


def test_ocr_solicita_alternativa_si_ultima_pagina_no_tiene_controles():
    text = (
        "Cuenta Debe Haber Deudor Acreedor Activo Pasivo Perdida Ganancia\n"
        "Caja 100 0 100 0 100 0 0 0"
    )

    assert parser._ocr_requiere_alternativa(text, es_ultima_pagina=True) is True


def test_ocr_prefiere_candidato_de_tabla_materialmente_mejor():
    base = "Caja 100 0\nProveedores 0 100"
    table = (
        "Cuenta Debe Haber Deudor Acreedor Activo Pasivo Perdida Ganancia\n"
        "Caja 100 0 100 0 100 0 0 0\n"
        "Proveedores 0 100 0 100 0 100 0 0\n"
        "SUMAS 100 100 100 100 100 100 0 0"
    )

    selected, strategy = parser._combinar_candidatos_ocr(base, table)

    assert selected == table
    assert strategy == "tabla"


def test_ocr_fusiona_totales_sin_perder_detalle_principal():
    base = (
        "Caja 100 0 100 0 100 0 0 0\n"
        "Proveedores 0 100 0 100 0 100 0 0"
    )
    alternative = "SUMAS 100 100 100 100 100 100 0 0"

    selected, strategy = parser._combinar_candidatos_ocr(base, alternative)

    assert "Caja" in selected
    assert "Proveedores" in selected
    assert "SUMAS" in selected
    assert strategy == "fusion"


def test_balance_clasificado_propaga_secciones_sin_sobrescribir_columnas():
    accounts = [
        parser.CuentaRaw(1, None, "ACTIVOS CORRIENTES", None),
        parser.CuentaRaw(2, None, "Efectivo y equivalentes", 100),
        parser.CuentaRaw(
            3, None, "Cuenta observada", 20,
            origen_columna=parser.OrigenColumna.PERDIDA,
            montos_columnas={"perdida": 20},
        ),
        parser.CuentaRaw(4, None, "PASIVOS CORRIENTES", None),
        parser.CuentaRaw(5, None, "Proveedores", 80),
        parser.CuentaRaw(6, None, "PATRIMONIO NETO", None),
        parser.CuentaRaw(7, None, "Capital", 40),
    ]

    annotated = parser.anotar_secciones_balance_clasificado(accounts)

    assert annotated == 3
    assert accounts[1].origen_columna is parser.OrigenColumna.ACTIVO
    assert accounts[2].origen_columna is parser.OrigenColumna.PERDIDA
    assert accounts[4].origen_columna is parser.OrigenColumna.PASIVO
    assert accounts[6].origen_columna is parser.OrigenColumna.PASIVO


def test_balance_clasificado_cambia_de_activo_a_pasivo_entre_paginas():
    accounts = [
        parser.CuentaRaw(1, None, "Activos no corrientes", None),
        parser.CuentaRaw(2, None, "Propiedades, planta y equipo", 100),
        parser.CuentaRaw(
            3, None, "Patrimonio y pasivos 31-12-2018 31-12-2017", None,
        ),
        parser.CuentaRaw(4, None, "Pasivos corrientes Nota", None),
        parser.CuentaRaw(
            5, None, "Otros pasivos financieros, corrientes", 80,
            origen_columna=parser.OrigenColumna.ACTIVO,
        ),
    ]

    parser.anotar_secciones_balance_clasificado(accounts)

    assert accounts[1].origen_columna is parser.OrigenColumna.ACTIVO
    assert accounts[4].origen_columna is parser.OrigenColumna.PASIVO


def test_fusiona_glosa_partida_con_importes_de_la_misma_linea():
    accounts = [
        # El "12" de la glosa puede haber sido interpretado como monto antes
        # de observar las ocho columnas del segundo fragmento.
        parser.CuentaRaw(12, "1.1.02.03", "Fondo de Inversion Cap.12", 12),
        parser.CuentaRaw(
            12, None, "PERDIDA", 127_561_879,
            origen_columna=parser.OrigenColumna.ACTIVO,
            es_total=True,
            montos_columnas={
                "debitos": 127_561_879,
                "creditos": 127_561_879,
                "saldo_deudor": 0,
                "saldo_acreedor": 0,
                "activo": 0,
                "pasivo": 0,
                "perdida": 0,
                "ganancia": 0,
            },
        ),
    ]

    merged, count = parser.fusionar_cuentas_partidas(accounts)

    assert count == 1
    assert len(merged) == 1
    assert merged[0].codigo == "1.1.02.03"
    assert merged[0].nombre == "Fondo de Inversion Cap.12 PERDIDA"
    assert merged[0].es_total is False
    assert merged[0].montos_columnas["debitos"] == 127_561_879


def test_perdida_de_inventario_es_cuenta_y_no_total():
    account = parser.parsear_linea(
        "PERDIDA DE INVENTARIO (ROBOS Y HURTOS) "
        "14542740 0 14542740 0 0 0 14542740 0",
        10,
        parser.FormatoCodigo.SIN_CODIGO,
        ".",
        1.0,
    )

    assert account is not None
    assert account.es_total is False
    assert account.nombre == "PERDIDA DE INVENTARIO (ROBOS Y HURTOS)"


def test_perdida_del_ejercicio_sigue_siendo_total():
    account = parser.parsear_linea(
        "PERDIDA DEL EJERCICIO 0 0 0 100 0 100 100 0",
        11,
        parser.FormatoCodigo.SIN_CODIGO,
        ".",
        1.0,
    )

    assert account is not None
    assert account.es_total is True


def test_no_divide_fila_ocho_columnas_por_guion_en_glosa():
    line = (
        "21050400 Prestamo JL - CP "
        "14.784.726 14.784.726 0 0 0 0 0 0"
    )

    assert parser.split_side_by_side(line) == [line]
    account = parser.parsear_linea(
        line, 12, parser.FormatoCodigo.COMPACTO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "Prestamo JL - CP"
    assert account.montos_columnas["debitos"] == 14_784_726


def test_no_divide_fila_ocho_columnas_con_ceros_ocr_como_letra_o():
    line = (
        "1.01.01.02 Banco Cta Cte BCI — "
        "1.054.433.416 1.032.171.062 22.262.354 O 22.262.354 0 0 o"
    )

    assert parser.split_side_by_side(line) == [line]
    account = parser.parsear_linea(
        line, 2, parser.FormatoCodigo.PUNTO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "Banco Cta Cte BCI"
    assert account.montos_columnas["saldo_acreedor"] == 0
    assert account.montos_columnas["activo"] == 22_262_354


def test_ocr_separa_dos_montos_agrupados_sin_espacio():
    line = (
        "1.01.01.01 Caja 0 3,100,0001,385,515 "
        "1,714,485 0 1,714,485 0 0 0"
    )

    normalized = parser.normalizar_linea_ocr_tabla(line)

    assert "3.100.000 1.385.515" in normalized
    account = parser.parsear_linea(
        normalized, 1, parser.FormatoCodigo.PUNTO, ".", 0.75,
    )
    assert account is not None
    assert account.montos_columnas["debitos"] == 3_100_000
    assert account.montos_columnas["creditos"] == 1_385_515
    assert account.montos_columnas["saldo_deudor"] == 1_714_485


def test_ocr_recupera_clasificacion_ausente_y_movimiento_desplazado():
    account = parser.parsear_linea(
        "1.02.03.01 Maquinarias y equipos "
        "0 3.630.878 3.630.878 0 0 0 o 0",
        22,
        parser.FormatoCodigo.PUNTO,
        ".",
        0.75,
    )

    assert account is not None
    assert account.montos_columnas == {
        "debitos": 3_630_878.0,
        "creditos": 0.0,
        "saldo_deudor": 3_630_878.0,
        "saldo_acreedor": 0.0,
        "activo": 3_630_878.0,
        "pasivo": 0.0,
        "perdida": 0.0,
        "ganancia": 0.0,
    }
    assert {"debitos", "creditos", "activo"}.issubset(
        account.columnas_derivadas,
    )


def test_ocr_conserva_contra_activo_en_columna_acreedora():
    account = parser.parsear_linea(
        "1.02.06.01 Depreciación Acumulada "
        "0 8.371.044 0 8.371.044 0 0 0 0",
        26,
        parser.FormatoCodigo.PUNTO,
        ".",
        0.75,
    )

    assert account is not None
    assert account.montos_columnas["pasivo"] == 8_371_044
    assert account.montos_columnas["activo"] == 0
    assert account.origen_columna is parser.OrigenColumna.PASIVO


def test_ocr_repara_monto_unido_al_cero_de_columna_siguiente():
    account = parser.parsear_linea(
        "4.01.03.03 Gastos Legales 0 9.360.900 936.090 0 0 0 0 0",
        59,
        parser.FormatoCodigo.PUNTO,
        ".",
        0.75,
    )

    assert account is not None
    assert account.montos_columnas["debitos"] == 936_090
    assert account.montos_columnas["creditos"] == 0
    assert account.montos_columnas["perdida"] == 936_090


def test_normaliza_dos_puntos_dentro_de_codigo_ocr():
    line = "4.02.:12.01 Diferencias de cambio Perdida 572 0 572 0 0 0 572 0"

    normalized = parser.normalizar_codigo_ocr(line)

    assert normalized.startswith("4.02.12.01 ")


def test_ocr_recupera_codigo_embebido_detras_de_ruido_corto():
    account = parser.parsear_linea(
        "Ú 1.01.09.19 — Plan Monitoreo 8.982.160 0 8.982.160 0 "
        "8.982.160 0 0 0",
        20,
        parser.FormatoCodigo.PUNTO,
        ".",
        0.75,
    )

    assert account.codigo == "1.01.09.19"
    assert account.nombre == "Plan Monitoreo"
    assert account.montos_columnas["activo"] == 8_982_160


def test_codigo_embebido_no_se_recupera_en_texto_nativo():
    account = parser.parsear_linea(
        "E 3.02.03.01 Utilidad en venta 0 100 0 100 0 0 0 100",
        1,
        parser.FormatoCodigo.PUNTO,
        ".",
        1.0,
    )

    assert account.codigo is None


def test_normaliza_primer_digito_separado_de_monto_con_miles():
    line = "Total de Activos 2 2.029.324,87 2 6.620.286,76"

    normalized = parser.normalizar_montos_fragmentados(line)

    assert normalized == "Total de Activos 22.029.324,87 26.620.286,76"


def test_certifica_totales_ifrs_espanol_e_ingles():
    for active_name, liability_name in (
        ("Total de Activos", "Total de Patrimonio y Pasivos"),
        ("TOTAL ASSETS", "TOTAL EQUITY AND LIABILITIES"),
    ):
        certification = parser.certificar_totales_clasificados([
            parser.CuentaRaw(1, None, active_name, 441_477, es_total=True),
            parser.CuentaRaw(2, None, liability_name, 441_477, es_total=True),
        ])

        assert certification.estado == "parcial"
        assert certification.diferencias["activo_menos_pasivo_patrimonio"] == 0


def test_total_pasivos_generico_solo_certifica_si_equivale_al_total_activos():
    matching = parser.certificar_totales_clasificados([
        parser.CuentaRaw(1, None, "Total Activos", 5_000, es_total=True),
        parser.CuentaRaw(2, None, "Total Pasivos", 5_000, es_total=True),
    ])
    mismatching = parser.certificar_totales_clasificados([
        parser.CuentaRaw(1, None, "Total Activos", 5_000, es_total=True),
        parser.CuentaRaw(2, None, "Total Pasivos", 3_000, es_total=True),
    ])

    assert matching.estado == "parcial"
    assert mismatching.estado == "no_evaluable"


def test_seccion_corrige_heuristica_de_ultima_columna_sin_evidencia_tabular():
    accounts = [
        parser.CuentaRaw(1, None, "ACTIVOS FIJOS", None),
        parser.CuentaRaw(
            2, None, "Construcciones", 200,
            origen_columna=parser.OrigenColumna.PASIVO,
        ),
        parser.CuentaRaw(3, None, "PASIVOS A LARGO PLAZO", None),
        parser.CuentaRaw(
            4, None, "Obligaciones bancarias", 150,
            origen_columna=parser.OrigenColumna.GANANCIA,
        ),
    ]

    annotated = parser.anotar_secciones_balance_clasificado(accounts)

    assert annotated == 2
    assert accounts[1].origen_columna is parser.OrigenColumna.ACTIVO
    assert accounts[3].origen_columna is parser.OrigenColumna.PASIVO


def test_balance_clasificado_propaga_resultados_por_naturaleza():
    accounts = [
        parser.CuentaRaw(1, None, "INGRESOS", None),
        parser.CuentaRaw(2, None, "Ingresos ordinarios", 150),
        parser.CuentaRaw(3, None, "GASTOS", None),
        parser.CuentaRaw(4, None, "Gastos de administración", 90),
    ]

    parser.anotar_secciones_balance_clasificado(accounts)

    assert accounts[1].origen_columna is parser.OrigenColumna.GANANCIA
    assert accounts[3].origen_columna is parser.OrigenColumna.PERDIDA


def test_seccion_no_se_filtra_hacia_otro_estado_financiero():
    accounts = [
        parser.CuentaRaw(1, None, "PATRIMONIO NETO", None),
        parser.CuentaRaw(2, None, "Capital", 100),
        parser.CuentaRaw(3, None, "TOTAL PASIVOS Y PATRIMONIO NETO", 100, es_total=True),
        parser.CuentaRaw(4, None, "ESTADO DE FLUJO DE EFECTIVO", None),
        parser.CuentaRaw(5, None, "Cobros de clientes", 80),
    ]

    parser.anotar_secciones_balance_clasificado(accounts)

    assert accounts[1].origen_columna is parser.OrigenColumna.PASIVO
    assert accounts[4].origen_columna is parser.OrigenColumna.DESCONOCIDO


def test_secciones_ifrs_con_dos_columnas_paralelas_y_encabezados_en_ingles():
    accounts = [
        parser.CuentaRaw(1, None, "NON-CURRENT ASSETS EQUITY", None),
        parser.CuentaRaw(2, None, "Vessels", 100),
        parser.CuentaRaw(2, None, "Paid capital", 40),
        parser.CuentaRaw(3, None, "Net income", 10),
        parser.CuentaRaw(4, None, "NON-CURRENT LIABILITIES", None),
        parser.CuentaRaw(5, None, "Long term debt", 60),
    ]

    parser.anotar_secciones_balance_clasificado(accounts)

    assert accounts[1].origen_columna is parser.OrigenColumna.ACTIVO
    assert accounts[2].origen_columna is parser.OrigenColumna.PASIVO
    assert accounts[3].origen_columna is parser.OrigenColumna.DESCONOCIDO
    assert accounts[5].origen_columna is parser.OrigenColumna.PASIVO


def test_encabezados_con_dos_puntos_y_total_final_cortan_la_seccion():
    accounts = [
        parser.CuentaRaw(1, None, "Activos corrientes:", None),
        parser.CuentaRaw(2, None, "Caja", 100),
        parser.CuentaRaw(
            3, None, "Total de Patrimonio y Pasivos", 100, es_total=True,
        ),
        parser.CuentaRaw(4, None, "Ingresos ordinarios", 20),
    ]

    parser.anotar_secciones_balance_clasificado(accounts)

    assert accounts[1].origen_columna is parser.OrigenColumna.ACTIVO
    assert accounts[3].origen_columna is parser.OrigenColumna.DESCONOCIDO


def test_fusion_ocr_recupera_saldo_y_movimientos_sin_duplicar_filas():
    coordinate_lines = [
        "1.01.05.06 Deudores Varios 42,389,219 0 0 0 0 0 0 0",
        "2.01.07.04 Cheques por Pagar 0 0 0 40,916,967 0 40,916,967 0 0",
    ]
    alternative = "\n".join([
        "1.01.05.06 Deudores Varios 42,389,219 0 42,389,219 0 42,389,219 0",
        "2.01.07.04 Cheques por Pagar 49,313,784 90,230,751 0 40,916,967 0 40,916,967",
    ])

    assert parser._tabla_ocr_necesita_recuperacion(coordinate_lines)
    recovered, count = parser.recuperar_filas_tabla_ocr(
        coordinate_lines, alternative,
    )
    accounts = [
        parser._cuenta_desde_candidato_ocr(line, index)
        for index, line in enumerate(recovered)
    ]

    assert count == 2
    assert len(recovered) == 2
    assert accounts[0].montos_columnas["activo"] == 42_389_219
    assert accounts[1].montos_columnas["debitos"] == 49_313_784
    assert accounts[1].montos_columnas["creditos"] == 90_230_751


def test_fusion_ocr_rechaza_alternativa_que_cambia_saldo_observado():
    coordinate = [
        "1.01.01.01 Caja 100 0 100 0 100 0 0 0",
    ]
    alternative = "1.01.01.01 Caja 200 0 200 0 200 0"

    recovered, count = parser.recuperar_filas_tabla_ocr(coordinate, alternative)

    assert count == 0
    assert recovered == coordinate


def test_fusion_ocr_agrega_fila_omitida_solo_si_es_consistente_y_no_duplicada():
    coordinate = [
        "4.01.03.19 Peajes 454.419 0 454.419 0 0 0 454.419 0",
        "4.02.09.60 Finiquitos 11.082.273 0 11.082.273 0 0 0 11.082.273 0",
    ]
    alternative = "\n".join([
        "4.01.03.18 Combustibles 27.196.269 10 27.196.269 0 0 0 27.196.269 0",
        # Mismo nombre, código OCR distinto: no debe duplicarse.
        "4.02.04.60 Finiquitos 11.082.273 0 11.082.273 0 0 0 11.082.273 0",
        # Los controles nunca son detalles recuperables.
        "[Sumas 1.000] 1.000 500 500 400 300 100 200",
    ])

    recovered, count = parser.recuperar_filas_tabla_ocr(coordinate, alternative)
    accounts = [
        parser._cuenta_desde_candidato_ocr(line, index)
        for index, line in enumerate(recovered)
    ]

    assert count == 1
    assert len(recovered) == 3
    assert accounts[-1].nombre == "Combustibles"
    assert accounts[-1].montos_columnas["creditos"] == 0


def test_fusion_ocr_recupera_control_partido_por_solapamiento_independiente():
    coordinate = [
        "Sumas J7s08246111 7.608 246.111 1.259.149.847 1.259.149:847 "
        "458.598.280 411.047.078 800.551.567 848.102.769",
    ]
    alternative = (
        "Sumas 7.608.246.111 7.608.246.111 1.259.149.847 "
        "1.259.149.847 458.598.280 411.047.078"
    )

    assert parser._tabla_ocr_necesita_recuperacion(coordinate)
    recovered, count = parser.recuperar_filas_tabla_ocr(coordinate, alternative)
    total = parser.parsear_linea(
        recovered[0], 1, parser.FormatoCodigo.SIN_CODIGO, ".", 0.75,
    )

    assert count == 1
    assert total.montos_columnas == {
        "debitos": 7_608_246_111,
        "creditos": 7_608_246_111,
        "saldo_deudor": 1_259_149_847,
        "saldo_acreedor": 1_259_149_847,
        "activo": 458_598_280,
        "pasivo": 411_047_078,
        "perdida": 800_551_567,
        "ganancia": 848_102_769,
    }
