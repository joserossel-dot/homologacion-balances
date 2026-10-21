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


class NativeFakePage(FakePage):
    def __init__(self, rows, text):
        super().__init__(rows)
        self._text = text

    def extract_text(self):
        return self._text

    def extract_tables(self):
        return []


class NativeFakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_orientacion_ocr_prueba_las_cuatro_rotaciones_y_exige_evidencia(monkeypatch, tmp_path):
    textos = {
        0: "texto lateral sin estructura 123 456",
        90: (
            "RAZON SOCIAL RUT CUENTA DEBE HABER DEUDOR ACREEDOR "
            "ACTIVO PASIVO PERDIDA GANANCIA TOTAL"
        ),
        180: "texto invertido 123 456",
        270: "texto lateral alternativo 123 456",
    }
    llamadas = []

    def probe(_path, rotacion):
        llamadas.append(rotacion)
        return textos[rotacion]

    monkeypatch.setattr(parser, "_ocr_pagina_orientacion", probe)

    evidencia = parser._seleccionar_orientacion_ocr(tmp_path / "pagina.png")

    assert llamadas == [0, 90, 180, 270]
    assert evidencia["rotacion"] == 90
    assert evidencia["certificada"] is True
    assert evidencia["margen"] > 0


def test_orientacion_ocr_ambigua_bloquea_estado_automatico(monkeypatch, tmp_path):
    monkeypatch.setattr(
        parser,
        "_ocr_pagina_orientacion",
        lambda _path, _rotacion: "texto suelto 123 456",
    )
    certificacion = parser.CertificacionExtraccion(estado="certificada")

    evidencia = parser._seleccionar_orientacion_ocr(tmp_path / "pagina.png")
    resultado = parser._anotar_certificacion_orientacion(
        certificacion, [{"pagina": 1, **evidencia}],
    )

    assert evidencia["certificada"] is False
    assert resultado.orientacion_certificada is False
    assert resultado.estado == "parcial"
    assert "orientación OCR" in resultado.razones[-1]


def test_orientacion_ocr_de_formulario_descartado_no_bloquea_balance():
    certificacion = parser.CertificacionExtraccion(estado="certificada")

    resultado = parser._anotar_certificacion_orientacion(
        certificacion,
        [
            {"pagina": 1, "certificada": True, "utilizada_en_extraccion": True},
            {"pagina": 2, "certificada": False, "utilizada_en_extraccion": False},
        ],
    )

    assert resultado.estado == "certificada"
    assert resultado.orientacion_certificada is True
    assert len(resultado.orientaciones_paginas) == 2


def test_orientacion_ocr_ambigua_se_recupera_por_lectura_tabular(monkeypatch, tmp_path):
    texto_legible = (
        "RAZON SOCIAL RUT CUENTA DEBE HABER DEUDOR ACREEDOR ACTIVO PASIVO "
        "CAJA GENERAL 100 0 100 0 100 0 0 0"
    )

    llamadas = []

    def lectura_tabular(_path, rotacion, psm=6):
        assert psm == 4
        llamadas.append(rotacion)
        return texto_legible if rotacion == 90 else "000 111 222 333"

    monkeypatch.setattr(parser, "ocr_pagina", lectura_tabular)
    texto, rotacion, evidencia = parser._recuperar_orientacion_por_tabla_ocr(
        tmp_path / "pagina.png",
        {
            "pagina": 1,
            "rotacion": 180,
            "puntaje": 12.0,
            "margen": 6.0,
            "certificada": False,
            "candidatos": [
                {"rotacion": 180}, {"rotacion": 90},
                {"rotacion": 0}, {"rotacion": 270},
            ],
        },
    )

    assert llamadas == [180, 90]
    assert rotacion == 90
    assert texto == texto_legible
    assert evidencia["certificada"] is True
    assert evidencia["rotacion_sondeo"] == 180
    assert evidencia["metodo_certificacion"] == "lectura_tabular_ocr"


def test_orientacion_ocr_acepta_pagina_intermedia_con_varias_glosas_contables():
    metricas = parser._puntuar_orientacion_ocr(
        "BANCO ESTADO PROVEEDORES RENDICION ANTICIPO PRESTAMO IMPUESTOS"
    )

    assert metricas["grupos"]["partida_contable"] >= 4
    assert metricas["puntaje"] >= parser.OCR_ORIENTATION_MIN_SCORE


def test_consenso_documental_certifica_rotacion_repetida_con_senal_moderada():
    evidencias = parser._certificar_consenso_documental_orientacion([
        {
            "pagina": 1, "rotacion": 0, "puntaje": 20.0, "margen": 9.0,
            "certificada": False, "utilizada_en_extraccion": True,
        },
        {
            "pagina": 2, "rotacion": 0, "puntaje": 18.0, "margen": 8.5,
            "certificada": False, "utilizada_en_extraccion": True,
        },
        {
            "pagina": 3, "rotacion": 0, "puntaje": 15.0, "margen": 10.0,
            "certificada": False, "utilizada_en_extraccion": True,
        },
    ])

    assert all(evidencia["certificada"] for evidencia in evidencias)
    assert {
        evidencia["metodo_certificacion"] for evidencia in evidencias
    } == {"consenso_documental"}


def test_consenso_documental_no_promueve_paginas_con_rotaciones_distintas():
    evidencias = parser._certificar_consenso_documental_orientacion([
        {
            "pagina": 1, "rotacion": 0, "puntaje": 20.0, "margen": 9.0,
            "certificada": False, "utilizada_en_extraccion": True,
        },
        {
            "pagina": 2, "rotacion": 90, "puntaje": 18.0, "margen": 8.5,
            "certificada": False, "utilizada_en_extraccion": True,
        },
    ])

    assert not any(evidencia["certificada"] for evidencia in evidencias)


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


def test_puente_utilidad_perdida_con_barra_no_se_trata_como_cuenta():
    cuenta = parser.parsear_linea(
        "Utilidad/Perdida Utilidad/Perdida 880.472.936",
        7,
        parser.FormatoCodigo.COMPACTO,
        ".",
    )

    assert cuenta is not None
    assert cuenta.codigo is None
    assert cuenta.es_total is True


def test_ocho_columnas_sin_saldo_final_no_usa_movimiento_como_monto_vigente():
    cuenta = parser.parsear_linea(
        "1.1.01.02 Deposito transitorio 500 500 0 0 0 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", years=["2023"],
    )

    assert cuenta is not None
    assert cuenta.monto == 0
    assert cuenta.origen_columna is parser.OrigenColumna.DESCONOCIDO


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


def _lineas_ocho_columnas(cantidad, *, activo=True):
    lineas = []
    for indice in range(1, cantidad + 1):
        if activo:
            montos = "100 0 100 0 100 0 0 0"
        else:
            # Sigue siendo aritméticamente consistente, aunque el importe se
            # haya desplazado de ACTIVO a PASIVO en la geometría.
            montos = "100 0 100 0 0 100 0 0"
        lineas.append(f"1-01-01-{indice:02d} CUENTA {indice:02d} {montos}")
    return lineas


def test_texto_nativo_ocho_columnas_se_prefiere_solo_con_mejor_cobertura():
    coordenadas = _lineas_ocho_columnas(8, activo=False)
    texto_nativo = "\n".join([
        "BALANCE TRIBUTARIO",
        *_lineas_ocho_columnas(9, activo=True),
        "Sub-Totales 900 0 900 0 900 0 0 0",
    ])

    candidato = parser.preparar_candidato_texto_nativo_ocho_columnas(
        coordenadas, texto_nativo,
    )

    assert candidato is not None
    assert candidato["cuentas_coordenadas"] == 8
    assert candidato["cuentas_nativas"] == 9
    assert candidato["controles_certificables"] == 1
    assert parser.debe_preferirse_texto_nativo_ocho_columnas([candidato], 1)
    assert candidato["lineas"][-1].startswith("Sub-Totales")


def test_texto_nativo_ocho_columnas_no_reemplaza_si_no_mejora_cobertura():
    coordenadas = _lineas_ocho_columnas(8, activo=False)
    texto_nativo = "\n".join([
        *_lineas_ocho_columnas(8, activo=True),
        "Sub-Totales 800 0 800 0 800 0 0 0",
    ])

    candidato = parser.preparar_candidato_texto_nativo_ocho_columnas(
        coordenadas, texto_nativo,
    )

    assert candidato is not None
    assert not parser.debe_preferirse_texto_nativo_ocho_columnas([candidato], 1)


def test_parser_prioriza_texto_nativo_validado_sobre_geometria_desplazada(
    monkeypatch, tmp_path,
):
    filas_geometricas = [_header()]
    for indice in range(1, 9):
        filas_geometricas.append(_row(
            10 + indice * 10,
            f"1-01-01-{indice:02d}",
            f"CUENTA {indice:02d}",
            ["100", "0", "100", "0", "0", "100", "0", "0"],
        ))
    texto_nativo = "\n".join([
        "BALANCE TRIBUTARIO",
        *_lineas_ocho_columnas(9, activo=True),
        "Sub-Totales 900 0 900 0 900 0 0 0",
    ])
    page = NativeFakePage(filas_geometricas, texto_nativo)
    monkeypatch.setattr(
        parser.pdfplumber, "open", lambda _path: NativeFakePdf([page]),
    )
    monkeypatch.setattr(parser, "validar_archivo", lambda _path: (True, ""))
    monkeypatch.setattr(
        parser.ParserPDF, "_analizar_documento", lambda *_args: None,
    )

    resultado = parser.ParserPDF().parsear(tmp_path / "balance.pdf")

    assert resultado.certificacion_extraccion.metodo == (
        "native_text_8_columns_validated"
    )
    assert resultado.certificacion_extraccion.estado == "certificada"
    assert len(resultado.cuentas) == 10
    primera = next(
        cuenta for cuenta in resultado.cuentas if cuenta.codigo == "1-01-01-01"
    )
    assert primera.montos_columnas["activo"] == 100
    assert primera.montos_columnas["pasivo"] == 0


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


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1102-03", "AC.01"),
        ("1104-09", "AC.03"),
        ("1108-05", "AC.05"),
        ("1204-03", "ANC.01.01"),
        ("1205-06", "ER.04"),
        ("1301-01", "ANC.03"),
        ("2202-01", "PC.01"),
        ("2207-05", "PC.05"),
        ("2301-01", "PNC.01"),
        ("2402-12", "PAT.03"),
        ("4101-01", "ER.02"),
        ("4203-14", "ER.09"),
        ("5101-05", "ER.01"),
    ],
)
def test_codigo_nubox_agrupado_clasifica_familias_verificadas(code, expected):
    result = ClasificadorCodigo().clasificar(code)

    assert result is not None
    assert result.tipo_formato == "nubox_4x2"
    assert result.codigo_estandar == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1108001", "AC.07"),
        ("1101202", "AC.01"),
        ("2201001", "PNC.01"),
        ("2301001", "PAT.01"),
        ("3202006", "ER.04"),
        ("3202014", "ER.09"),
        ("3301002", "ER.07"),
        ("3401005", "ER.09"),
        ("3601001", "ER.10"),
        ("4101002", "ER.01"),
    ],
)
def test_codigo_compacto_siete_digitos_clasifica_familias_verificadas(code, expected):
    result = ClasificadorCodigo().clasificar(code)

    assert result is not None
    assert result.tipo_formato == "compacto"
    assert result.codigo_estandar == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1.1.01.11", "AC.01"),
        ("1.1.01.15", "AC.01"),
        ("1.1.08.03", "AC.05"),
        ("1.2.02.03", "ANC.01"),
        ("1.2.04.03", "ANC.01"),
        ("1.3.09.01", "ANC.06"),
        ("2.1.01.01", "PC.02"),
        ("2.1.02.01", "PC.02"),
        ("2.1.07.01", "PC.07"),
        ("2.1.09.04", "PC.06"),
        ("2.1.09.07", "PC.06"),
        ("2.1.09.10", "PC.06"),
        ("2.1.09.22", "PC.05"),
        ("2.1.09.23", "PC.08"),
        ("2.2.01.01", "PNC.01"),
        ("2.4.01.04", "PAT.03"),
        ("3.1.01.01", "ER.01"),
        ("3.1.01.04", "ER.01"),
        ("4.2.02.02", "ER.09"),
    ],
)
def test_codigo_punto_corto_clasifica_familias_verificadas(code, expected):
    result = ClasificadorCodigo().clasificar(code)

    assert result is not None
    assert result.tipo_formato == "punto_separado"
    assert result.codigo_estandar == expected


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


def test_parsear_linea_ocr_reconstruye_columna_final_desde_movimiento_y_saldo():
    cuenta = parser.parsear_linea(
        "1.2.01.01 Terrenos 9.973.017.220 2.102.300.225 "
        "7.870.716.995 0 7.870.718.995 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["activo"] == 7_870_716_995
    assert cuenta.monto == 7_870_716_995
    assert cuenta.columnas_derivadas == ["activo"]


def test_parsear_linea_nativa_no_reconstruye_columna_final_discrepante():
    cuenta = parser.parsear_linea(
        "1.2.01.01 Terrenos 9.973.017.220 2.102.300.225 "
        "7.870.716.995 0 7.870.718.995 0 0 0",
        1, parser.FormatoCodigo.PUNTO, ".", confianza_base=1.0,
    )

    assert cuenta is not None
    assert cuenta.montos_columnas["activo"] == 7_870_718_995
    assert cuenta.columnas_derivadas == []


def test_candidato_ocr_no_desplaza_una_fila_completa_para_agregar_ceros():
    cuenta = parser._cuenta_desde_candidato_ocr(
        "1.2.01.01 Terrenos 9.973.017.220 2.102.300.225 "
        "7.870.716.995 0 7.870.718.995 0 0 0",
        1, exigir_consistencia=False,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Terrenos"
    assert cuenta.montos_columnas["debitos"] == 9_973_017_220
    assert cuenta.montos_columnas["creditos"] == 2_102_300_225
    assert cuenta.montos_columnas["activo"] == 7_870_716_995


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
    assert certification.diagnostico == "CONTROLES_VALIDADOS"


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
    assert certification.diagnostico == "SIN_FILAS_CONTABLES"


def test_certificacion_diagnostica_subtotal_no_detectado_sin_atribuir_causa():
    detail = parser.parsear_linea(
        "110101 CAJA 100 0 100 0 100 0 0 0",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas([detail])

    assert certification.estado == "no_evaluable"
    assert certification.diagnostico == "SUBTOTAL_NO_DETECTADO"
    assert certification.senales_diagnostico == ["SUBTOTAL_NO_DETECTADO"]


def test_certificacion_diagnostica_inconsistencias_masivas_de_fila():
    details = [
        parser.parsear_linea(
            f"{code} CUENTA {amount} 0 {amount - 20} 0 {amount - 20} 0 0 0",
            line, parser.FormatoCodigo.COMPACTO, ".",
        )
        for line, code, amount in (
            (1, "110101", 100),
            (2, "110102", 200),
            (3, "110103", 300),
        )
    ]
    subtotal = parser.parsear_linea(
        "SUBTOTALES 600 0 540 0 540 0 0 0",
        4, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas([*details, subtotal])

    assert certification.estado == "fallida"
    assert certification.diagnostico == "INCONSISTENCIAS_MASIVAS_DE_FILA"
    assert "INCONSISTENCIAS_MASIVAS_DE_FILA" in certification.senales_diagnostico


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
    assert certification.diagnostico == "FILA_FINAL_INCOMPLETA"
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
    assert certification.ecuacion_contable_fuente_valida is False
    assert certification.diferencia_ecuacion_contable_fuente == 100


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
    assert certification.ecuacion_contable_fuente_valida is True
    assert certification.diferencia_ecuacion_contable_fuente == 0


def test_certificacion_reconoce_suma_singular_y_ganancia_ejercicio():
    details = [
        parser.parsear_linea(
            "110101 CAJA 110 0 110 0 110 0 0 0",
            1, parser.FormatoCodigo.COMPACTO, ".",
        ),
        parser.parsear_linea(
            "410101 VENTAS 0 110 0 110 0 0 0 110",
            2, parser.FormatoCodigo.COMPACTO, ".",
        ),
    ]
    subtotal = parser.parsear_linea(
        "SUMA 110 110 110 110 110 0 0 110",
        3, parser.FormatoCodigo.COMPACTO, ".",
    )
    bridge = parser.parsear_linea(
        "GANANCIA EJERCICIO 0 0 0 0 0 110 110 0",
        4, parser.FormatoCodigo.COMPACTO, ".",
    )
    final = parser.parsear_linea(
        "TOTALES 110 110 110 110 110 110 110 110",
        5, parser.FormatoCodigo.COMPACTO, ".",
    )

    certification = parser.certificar_extraccion_columnas(
        [*details, subtotal, bridge, final],
    )

    assert subtotal.es_total is True
    assert bridge.es_total is True
    assert certification.estado == "certificada"
    assert certification.totales_finales_validos is True
    assert certification.resultado_ejercicio == 110


def test_ganancia_ejercicio_codificada_permanece_detalle():
    account = parser.parsear_linea(
        "410101 GANANCIA EJERCICIO 0 110 0 110 0 0 0 110",
        1, parser.FormatoCodigo.COMPACTO, ".",
    )

    assert account is not None
    assert account.codigo == "410101"
    assert account.es_total is False


def test_ganancia_sin_etiqueta_de_cierre_permanece_detalle():
    account = parser.parsear_linea(
        "Ganancia por venta de activo 0 110 0 110 0 0 0 110",
        1, parser.FormatoCodigo.SIN_CODIGO, ".",
    )

    assert account is not None
    assert account.es_total is False


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
    assert certification.diagnostico == "ECUACION_FINAL_VALIDA_CON_REVISION"


def test_balance_clasificado_descuadrado_falla():
    accounts = [
        parser.CuentaRaw(1, None, "TOTAL ACTIVOS", 500),
        parser.CuentaRaw(2, None, "TOTAL PASIVOS Y PATRIMONIO", 450),
    ]

    certification = parser.certificar_totales_clasificados(accounts)

    assert certification.estado == "fallida"
    assert certification.totales_finales_validos is False
    assert certification.diagnostico == "ECUACION_FINAL_NO_CONCILIA"


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
    assert certification.diagnostico == "SUBTOTALES_SECCION_NO_CONCILIAN"


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


def test_balance_clasificado_conserva_el_metodo_del_extractor_especializado():
    accounts = [
        parser.CuentaRaw(1, None, "Total activos", 100, es_total=True),
        parser.CuentaRaw(
            2, None, "Total pasivos y patrimonio", 100, es_total=True,
        ),
    ]

    certification = parser.certificar_totales_clasificados(
        accounts, metodo="ocr_classified_two_columns",
    )

    assert certification.estado == "parcial"
    assert certification.metodo == "ocr_classified_two_columns"


def test_balance_clasificado_nativo_valida_columnas_finales_con_subtotales_en_ambos_lados():
    accounts = [
        parser.CuentaRaw(1, None, "Caja", 100, origen_columna=parser.OrigenColumna.ACTIVO),
        parser.CuentaRaw(
            2, None, "Total Activo Circulante", 100,
            origen_columna=parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(3, None, "Proveedor", 40, origen_columna=parser.OrigenColumna.PASIVO),
        parser.CuentaRaw(
            4, None, "Total Pasivo Circulante", 40,
            origen_columna=parser.OrigenColumna.PASIVO, es_total=True,
        ),
        parser.CuentaRaw(5, None, "Capital", 60, origen_columna=parser.OrigenColumna.PASIVO),
        parser.CuentaRaw(
            6, None, "Total Patrimonio", 60,
            origen_columna=parser.OrigenColumna.PASIVO, es_total=True,
        ),
        parser.CuentaRaw(
            7, None, "Total Activos", 100,
            origen_columna=parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            8, None, "Total Pasivos", 100,
            origen_columna=parser.OrigenColumna.PASIVO, es_total=True,
        ),
    ]

    certification = parser.certificar_totales_clasificados(
        accounts, metodo="native_classified_two_columns",
    )

    assert certification.estado == "parcial"
    assert certification.totales_finales_validos is True
    assert certification.columnas_finales_validadas is True


def test_balance_doble_columna_conserva_los_subtotales_por_lado():
    accounts = [
        parser.CuentaRaw(1, None, "Caja", 60, parser.OrigenColumna.ACTIVO),
        parser.CuentaRaw(2, None, "Proveedor", 100, parser.OrigenColumna.PASIVO),
        parser.CuentaRaw(3, None, "Clientes", 40, parser.OrigenColumna.ACTIVO),
        parser.CuentaRaw(
            4, None, "Total Activo Circulante", 100,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            5, None, "Total Pasivo Circulante", 100,
            parser.OrigenColumna.PASIVO, es_total=True,
        ),
        parser.CuentaRaw(
            6, None, "Total Activos", 100,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            7, None, "Total Pasivos", 100,
            parser.OrigenColumna.PASIVO, es_total=True,
        ),
    ]

    certification = parser.certificar_totales_clasificados(
        accounts, metodo="ocr_classified_two_columns",
    )

    assert certification.estado == "parcial"
    assert certification.diferencias[
        "seccion:activo:total activo circulante"
    ] == 0
    assert certification.diferencias[
        "seccion:pasivo:total pasivo circulante"
    ] == 0


def test_balance_doble_columna_falla_si_un_subtotal_fisico_no_cuadra():
    accounts = [
        parser.CuentaRaw(1, None, "Caja", 60, parser.OrigenColumna.ACTIVO),
        parser.CuentaRaw(2, None, "Proveedor", 100, parser.OrigenColumna.PASIVO),
        parser.CuentaRaw(3, None, "Clientes", 20, parser.OrigenColumna.ACTIVO),
        parser.CuentaRaw(
            4, None, "Total Activo Circulante", 100,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            5, None, "Total Pasivo Circulante", 100,
            parser.OrigenColumna.PASIVO, es_total=True,
        ),
        parser.CuentaRaw(
            6, None, "Total Activos", 100,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            7, None, "Total Pasivos", 100,
            parser.OrigenColumna.PASIVO, es_total=True,
        ),
    ]

    certification = parser.certificar_totales_clasificados(
        accounts, metodo="ocr_classified_two_columns",
    )

    assert certification.estado == "fallida"
    assert certification.diferencias[
        "seccion:activo:total activo circulante"
    ] == -20


def test_balance_doble_columna_identifica_subtotal_impreso_no_verificable():
    accounts = [
        parser.CuentaRaw(
            1, None, "Depósito a plazo", 357_061_211,
            parser.OrigenColumna.ACTIVO,
        ),
        parser.CuentaRaw(
            2, None, "Aporte sociedad", 13_575_670,
            parser.OrigenColumna.ACTIVO,
        ),
        parser.CuentaRaw(
            3, None, "Total Otros Activos", 304_368,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            4, None, "Total Activos", 1_000,
            parser.OrigenColumna.ACTIVO, es_total=True,
        ),
        parser.CuentaRaw(
            5, None, "Total Pasivos", 1_000,
            parser.OrigenColumna.PASIVO, es_total=True,
        ),
    ]

    certification = parser.certificar_totales_clasificados(
        accounts, metodo="ocr_classified_two_columns",
    )

    assert certification.estado == "fallida"
    assert certification.diagnostico == "SUBTOTAL_IMPRESO_NO_VERIFICABLE"
    assert certification.senales_diagnostico == [
        "SUBTOTAL_IMPRESO_NO_VERIFICABLE",
        "SUBTOTALES_SECCION_NO_CONCILIAN",
    ]


def test_recupera_importe_doble_columna_si_texto_independiente_mejora_subtotal():
    rows = [
        ("Caja 1.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        (
            "Línea de crédito 8.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
        ("Clientes 2.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 1.000.000", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Activo Circulante 3.000.000",
            parser.OrigenColumna.ACTIVO,
            "activo",
        ),
        (
            "Total Pasivo Circulante 10.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    text = (
        "Caja 1.000.000 Línea de crédito 9.000.000\n"
        "Clientes 2.000.000 Proveedores 1.000.000\n"
        "Total Activo Circulante 3.000.000 Total Pasivo Circulante 10.000.000"
    )

    recovered, recovered_flags, replacements = (
        parser.recuperar_importes_balance_clasificado_ocr(rows, text)
    )

    assert replacements == 1
    assert recovered[1][0] == "Línea de crédito 9.000.000"
    assert recovered_flags == [False, True, False, False, False, False]


def test_recupera_importe_doble_columna_si_mejora_su_control_local():
    """No bloquea un arreglo probado por un fallo grande de otra sección."""
    rows = [
        ("Caja 1.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        (
            "Línea de crédito 1.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
        ("Clientes 2.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 1.000.000", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Activo Circulante 3.000.000",
            parser.OrigenColumna.ACTIVO,
            "activo",
        ),
        (
            "Total Pasivo Circulante 999.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    text = (
        "Caja 1.000.000 Línea de crédito 9.000.000\n"
        "Clientes 2.000.000 Proveedores 1.000.000\n"
        "Total Activo Circulante 3.000.000 Total Pasivo Circulante 999.000.000"
    )

    recovered, recovered_flags, replacements = (
        parser.recuperar_importes_balance_clasificado_ocr(
            rows, text,
            confirmar_importe=lambda indice, monto: (
                indice == 1 and monto == 9_000_000
            ),
        )
    )

    assert replacements == 1
    assert recovered[1][0] == "Línea de crédito 9.000.000"
    assert recovered_flags == [False, True, False, False, False, False]


def test_recuperacion_local_doble_columna_requiere_confirmacion_focal():
    rows = [
        ("Caja 1.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        (
            "Línea de crédito 1.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
        ("Clientes 2.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 1.000.000", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Activo Circulante 3.000.000",
            parser.OrigenColumna.ACTIVO,
            "activo",
        ),
        (
            "Total Pasivo Circulante 999.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    text = (
        "Caja 1.000.000 Línea de crédito 9.000.000\n"
        "Clientes 2.000.000 Proveedores 1.000.000\n"
        "Total Activo Circulante 3.000.000 Total Pasivo Circulante 999.000.000"
    )

    recovered, recovered_flags, replacements = (
        parser.recuperar_importes_balance_clasificado_ocr(
            rows, text,
            confirmar_importe=lambda _indice, _monto: False,
        )
    )

    assert replacements == 0
    assert recovered == rows
    assert recovered_flags == [False] * len(rows)


def test_relectura_focal_doble_columna_repara_un_digito_con_subtotal():
    rows = [
        ("Caja 100", parser.OrigenColumna.ACTIVO, "activo"),
        ("Línea de crédito 100", parser.OrigenColumna.PASIVO, "pasivo"),
        ("Total Activo Circulante 100", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 200", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Pasivo Circulante 400",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    evidences = [None, {"target": "linea"}, None, None, None]

    recovered, recovered_flags, changes = (
        parser.recuperar_importes_balance_clasificado_por_control_focal(
            rows, evidences,
            releer_importe=lambda evidence, _actual: (
                200 if evidence and evidence.get("target") == "linea" else None
            ),
        )
    )

    assert recovered[1][0] == "Línea de crédito 200"
    assert recovered_flags == [False, True, False, False, False]
    assert changes[0]["linea"] == 1


def test_relectura_focal_doble_columna_no_empeora_otro_control():
    rows = [
        ("Caja 100", parser.OrigenColumna.ACTIVO, "activo"),
        ("Línea de crédito 100", parser.OrigenColumna.PASIVO, "pasivo"),
        ("Total Activo Circulante 100", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 200", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Pasivo Circulante 400",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    evidences = [None, {"target": "linea"}, None, None, None]

    recovered, recovered_flags, changes = (
        parser.recuperar_importes_balance_clasificado_por_control_focal(
            rows, evidences,
            releer_importe=lambda evidence, _actual: (
                300 if evidence and evidence.get("target") == "linea" else None
            ),
        )
    )

    assert recovered == rows
    assert recovered_flags == [False] * len(rows)
    assert changes == []


def test_no_recupera_importe_doble_columna_si_no_mejora_subtotal():
    rows = [
        ("Caja 1.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        (
            "Línea de crédito 9.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
        ("Clientes 2.000.000", parser.OrigenColumna.ACTIVO, "activo"),
        ("Proveedores 1.000.000", parser.OrigenColumna.PASIVO, "pasivo"),
        (
            "Total Activo Circulante 3.000.000",
            parser.OrigenColumna.ACTIVO,
            "activo",
        ),
        (
            "Total Pasivo Circulante 10.000.000",
            parser.OrigenColumna.PASIVO,
            "pasivo",
        ),
    ]
    text = (
        "Caja 1.000.000 Línea de crédito 8.000.000\n"
        "Clientes 2.000.000 Proveedores 1.000.000\n"
        "Total Activo Circulante 3.000.000 Total Pasivo Circulante 10.000.000"
    )

    recovered, recovered_flags, replacements = (
        parser.recuperar_importes_balance_clasificado_ocr(rows, text)
    )

    assert replacements == 0
    assert recovered == rows
    assert recovered_flags == [False] * len(rows)


def test_recuperacion_doble_columna_no_confunde_glosas_genericas_por_pagar():
    assert parser._nombres_ocr_fuertemente_compatibles(
        "Letras por pagar", "Letras por pagar",
    ) is True
    assert parser._nombres_ocr_fuertemente_compatibles(
        "Letras por pagar", "Documentos por pagar",
    ) is False


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


def test_ocr_no_reemplaza_lectura_certificada_por_mas_texto_sin_controles():
    base = (
        "Cuenta Debe Haber Deudor Acreedor Activo Pasivo Perdida Ganancia\n"
        "Caja 100 0 100 0 100 0 0 0\n"
        "Proveedores 0 100 0 100 0 100 0 0\n"
        "SUMAS 100 100 100 100 100 100 0 0"
    )
    # La alternativa tiene más filas numéricas, pero no subtotal ni un
    # control que permita certificar la supuesta mejora.
    alternative = "\n".join(
        f"Ruido {index} {index} 0 {index} 0 {index} 0 0 0"
        for index in range(1, 8)
    )

    selected, strategy = parser._combinar_candidatos_ocr(base, alternative)

    assert selected == base
    assert strategy == "principal"


def test_ocr_acepta_tabla_certificada_aunque_tenga_menos_tokens_numericos():
    base = "\n".join(
        f"Ruido {index} {index} 0 {index} 0 {index} 0 0 0"
        for index in range(1, 6)
    )
    table = (
        "Cuenta Debe Haber Deudor Acreedor Activo Pasivo Perdida Ganancia\n"
        "Caja 100 0 100 0 100 0 0 0\n"
        "Proveedores 0 100 0 100 0 100 0 0\n"
        "SUMAS 100 100 100 100 100 100 0 0"
    )

    selected, strategy = parser._combinar_candidatos_ocr(base, table)

    assert selected == table
    assert strategy == "tabla"


def test_candidato_parcial_sin_columnas_finales_no_autoriza_sustitucion():
    base = parser.CertificacionExtraccion(estado="fallida")
    parcial_sin_columnas = parser.CertificacionExtraccion(
        estado="parcial", columnas_finales_validadas=False,
    )
    parcial_con_columnas = parser.CertificacionExtraccion(
        estado="parcial", columnas_finales_validadas=True,
    )

    assert not parser._candidato_ocr_mejora_certificacion(
        base, parcial_sin_columnas,
    )
    assert parser._candidato_ocr_mejora_certificacion(
        base, parcial_con_columnas,
    )


def test_geometria_ocr_alternativa_solo_reemplaza_si_certifica_mejor_documento():
    base = [
        "Caja 100 0 100 0 100 0 0 0",
        "Proveedores 0 100 0 100 0 100 0 0",
    ]
    alternativa_certificada = [
        *base,
        "SUMAS 100 100 100 100 100 100 0 0",
    ]
    alternativa_fallida = [
        "Caja 200 0 100 0 100 0 0 0",
        "SUMAS 200 0 100 0 100 0 0 0",
    ]

    assert parser._candidato_geometrico_ocr_mejora_certificacion(
        base, alternativa_certificada,
    )
    assert not parser._candidato_geometrico_ocr_mejora_certificacion(
        base, alternativa_fallida,
    )


def test_certificacion_ocr_incluye_filas_iva_con_i_leida_como_uno():
    lineas = [
        "1101-01 Caja 100 0 100 0 100 0 0 0",
        "2201-01 Proveedores 0 100 0 100 0 100 0 0",
        "4101-01 Cuenta sin movimiento 0 0 0 0 0 0 0 0",
        "1107-03 1.V.A. CREDITO FISCAL 50 50 0 0 0 0 0 0",
        "2207-01 1.V.A. DEBITO FISCAL 60 60 0 0 0 0 0 0",
        "SUMAS 210 210 100 100 100 100 0 0",
        "PERDIDA O GANANCIA 0 0 0 0 0 0 0 0",
        "SUMAS IGUALES 210 210 100 100 100 100 0 0",
    ]

    certificacion = parser._certificar_candidato_textual_ocr("\n".join(lineas))

    assert certificacion.estado == "certificada"
    assert certificacion.diferencias == {
        columna: 0.0 for columna in parser.RAW_MONETARY_COLUMNS
    }


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


def test_fusiona_control_total_general_partido_en_dos_mitades_complementarias():
    izquierda = parser.CuentaRaw(
        linea=25, codigo=None, nombre="TOTAL", monto=5_579,
        origen_columna=parser.OrigenColumna.ACTIVO, es_total=True,
        montos_columnas={
            "debitos": 8_000, "creditos": 0,
            "saldo_deudor": 5_579, "saldo_acreedor": 0,
            "activo": 5_579, "pasivo": 0,
            "perdida": 42, "ganancia": 0,
        },
    )
    derecha = parser.CuentaRaw(
        linea=26, codigo=None, nombre="GENERAL", monto=5_579,
        origen_columna=parser.OrigenColumna.PASIVO,
        montos_columnas={
            "debitos": 0, "creditos": 8_000,
            "saldo_deudor": 0, "saldo_acreedor": 5_579,
            "activo": 0, "pasivo": 5_579,
            "perdida": 0, "ganancia": 42,
        },
    )

    merged, count = parser.fusionar_control_total_general_partido(
        [izquierda, derecha],
    )

    assert count == 1
    assert len(merged) == 1
    assert merged[0].nombre == "TOTAL GENERAL"
    assert merged[0].es_total is True
    assert merged[0].origen_columna is parser.OrigenColumna.DESCONOCIDO
    assert merged[0].montos_columnas == {
        "debitos": 8_000, "creditos": 8_000,
        "saldo_deudor": 5_579, "saldo_acreedor": 5_579,
        "activo": 5_579, "pasivo": 5_579,
        "perdida": 42, "ganancia": 42,
    }


def test_no_fusiona_total_y_general_si_no_son_columnas_complementarias():
    total = parser.CuentaRaw(
        linea=25, codigo=None, nombre="TOTAL", monto=100,
        es_total=True,
        montos_columnas={"debitos": 100, "creditos": 10},
    )
    general = parser.CuentaRaw(
        linea=26, codigo=None, nombre="GENERAL", monto=100,
        montos_columnas={"creditos": 100},
    )

    merged, count = parser.fusionar_control_total_general_partido([total, general])

    assert count == 0
    assert merged == [total, general]


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


@pytest.mark.parametrize("ruido_terminal", ("!", ":", "¿"))
def test_no_divide_fila_ocho_columnas_por_puntuacion_terminal_ocr(ruido_terminal):
    line = (
        "1.2.01.01 Terrenos 3.547.867.266 o 3.547.887.266 o "
        f"3.547.867.266 0 o o {ruido_terminal}"
    )

    assert parser.split_side_by_side(line) == [line]
    account = parser.parsear_linea(
        line, 20, parser.FormatoCodigo.PUNTO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "Terrenos"
    assert account.montos_columnas["activo"] == 3_547_867_266
    assert account.columnas_derivadas == ["saldo_deudor"]


def test_puntuacion_intercalada_no_oculta_dos_tablas_paralelas():
    line = "Activo 10 Pasivo 1 2 ! 3 4 5 6 7 8"

    assert parser.split_side_by_side(line) == [
        "Activo 10", "Pasivo 1 2 ! 3 4 5 6 7 8",
    ]


def test_puntuacion_terminal_multiple_no_oculta_ocho_columnas():
    line = (
        "1.2.01.01 Terrenos 3.547.867.266 0 3.547.867.266 0 "
        "3.547.867.266 0 0 0 : !"
    )

    assert parser.split_side_by_side(line) == [line]


def test_dos_tablas_paralelas_con_ocho_importes_requieren_evidencia_adicional():
    line = "Activo 10 Pasivo 1 2 3 4 5 6 7 8 :"

    assert parser.split_side_by_side(line) == [
        line,
    ]
    assert parser.split_side_by_side(
        line, permitir_corte_con_ocho_columnas=True,
    ) == [
        "Activo 10", "Pasivo 1 2 3 4 5 6 7 8 :",
    ]


def test_codigo_con_numero_en_glosa_y_ocho_importes_no_se_divide():
    line = "21050400 Cuenta 10 CP 50 0 50 0 50 0 0 0 :"

    assert parser.split_side_by_side(line) == [line]
    account = parser.parsear_linea(
        line, 12, parser.FormatoCodigo.COMPACTO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "Cuenta 10 CP"
    assert account.montos_columnas["activo"] == 50


def test_glosa_sin_codigo_con_numero_se_conserva_y_se_marca_ambigua():
    line = "IVA 19 Credito 1000 0 1000 0 1000 0 0 0"

    assert parser.split_side_by_side(line) == [line]
    assert parser.split_side_by_side(
        line, permitir_corte_con_ocho_columnas=True,
    ) == ["IVA 19", "Credito 1000 0 1000 0 1000 0 0 0"]
    fragments, ambiguous = parser._separar_linea_lateral_con_evidencia(
        line, 1, parser.FormatoCodigo.SIN_CODIGO, ".", 0.75,
    )
    assert fragments == [line]
    assert ambiguous is True
    account = parser.parsear_linea(
        line, 1, parser.FormatoCodigo.SIN_CODIGO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "IVA 19 Credito"
    assert account.montos_columnas["activo"] == 1000


def test_dos_fragmentos_codificados_habilitan_corte_con_ocho_columnas():
    line = (
        "1.01.01.01 Caja 10 2.01.01.01 Proveedores "
        "50 0 50 0 0 50 0 0"
    )

    fragments, ambiguous = parser._separar_linea_lateral_con_evidencia(
        line, 1, parser.FormatoCodigo.PUNTO, ".", 0.75,
    )
    assert fragments == [
        "1.01.01.01 Caja 10",
        "2.01.01.01 Proveedores 50 0 50 0 0 50 0 0",
    ]
    assert ambiguous is False


def test_puntuacion_pegada_al_ultimo_importe_se_normaliza_sin_tocar_porcentaje():
    line = "1.2.01.01 Terrenos 1 0 1 0 1 0 0 0!"

    assert parser.normalizar_linea_ocr_tabla(line).endswith("0")
    assert parser.split_side_by_side(line) == [line]
    account = parser.parsear_linea(
        line, 20, parser.FormatoCodigo.PUNTO, ".", 0.75,
    )
    assert account is not None
    assert account.nombre == "Terrenos"
    assert account.montos_columnas["activo"] == 1
    assert parser.normalizar_linea_ocr_tabla("Pasivo 12%").endswith("12%")


def test_token_monetario_mixto_sigue_habilitando_corte_lateral():
    line = "Activo 10 Pasivo 1 2 3 4 5 6 7 12%"

    assert parser.split_side_by_side(line) == [
        "Activo 10", "Pasivo 1 2 3 4 5 6 7 12%",
    ]


def test_simbolo_monetario_suelto_sigue_habilitando_corte_lateral():
    line = "Activo 10 Pasivo 1 2 3 4 5 6 7 8 $"

    assert parser.split_side_by_side(line) == [
        "Activo 10", "Pasivo 1 2 3 4 5 6 7 8 $",
    ]


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


def test_recuperacion_ocr_conserva_evidencia_de_filas_no_reemplazadas():
    original = ["Caja 100", "Proveedor 200", "Capital 300"]
    evidencias = [
        {"linea": "Caja 100"},
        {"linea": "Proveedor 200"},
        {"linea": "Capital 300"},
    ]
    recovered = ["Caja 100", "Proveedor 250", "Capital 300"]

    resultado = parser._conservar_evidencia_celdas_no_reemplazada(
        original, evidencias, recovered,
    )

    assert resultado == [evidencias[0], None, evidencias[2]]


def test_recuperacion_ocr_descarta_evidencia_si_cambia_la_cantidad_de_filas():
    resultado = parser._conservar_evidencia_celdas_no_reemplazada(
        ["Caja 100"], [{"linea": "Caja 100"}], ["Caja 100", "Banco 20"],
    )

    assert resultado == [None, None]


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


def test_fusion_ocr_recompone_sumas_iguales_partidas_con_lectura_independiente():
    coordinate = [
        "Sumas Iguales 1.000 0 120.000 0 100.000 0 40.000 0",
        "IIA 0 1.000 0 120.000 0 120.000 0 20.000",
    ]
    alternative = "\n".join([
        "Sumas Iguales 1.000 120.000 100.000 40.000",
        "1.000 120.000 120.000 20.000",
    ])

    recovered, count = parser.recuperar_filas_tabla_ocr(coordinate, alternative)
    total = parser.parsear_linea(
        recovered[0], 0, parser.FormatoCodigo.SIN_CODIGO, ".", 0.75,
    )

    assert count == 1
    assert recovered[1] == ""
    assert total is not None
    assert total.es_total
    assert total.montos_columnas == {
        "debitos": 1_000,
        "creditos": 1_000,
        "saldo_deudor": 120_000,
        "saldo_acreedor": 120_000,
        "activo": 100_000,
        "pasivo": 120_000,
        "perdida": 40_000,
        "ganancia": 20_000,
    }


def test_recomposicion_ocr_no_fusiona_una_cuenta_como_continuacion_de_control():
    lines = [
        "Sumas Iguales 1.000 200 110 90",
        "Banco 1.000 200 110 90",
    ]

    recovered, count = parser.recomponer_controles_finales_ocr_partidos(lines)

    assert count == 0
    assert recovered == lines


def test_descarta_pie_sin_codigo_solo_despues_de_un_cierre_final_explicito():
    cuentas = [
        parser.CuentaRaw(1, "110101", "Caja", 100),
        parser.CuentaRaw(2, None, "SUMAS IGUALES", 100, es_total=True),
        parser.CuentaRaw(
            3, None, "Firma del representante", 27_790,
            montos_columnas={"creditos": 27_790},
        ),
        parser.CuentaRaw(4, "999999", "Cuenta codificada posterior", 10),
    ]

    filtered, count = parser.descartar_pie_no_contable_despues_cierre(cuentas)

    assert count == 1
    assert [cuenta.linea for cuenta in filtered] == [1, 2, 4]


def test_relectura_focal_corrige_un_digito_solo_con_identidades_y_controles():
    lineas = [
        "1.01.01.01 Caja 100 0 100 0 100 0 0 0",
        # La relectura focal corrige Crédito 225 -> 125 y Pasivo 200 -> 100.
        "2.01.10.01 PPM por pagar 25 225 0 100 0 200 0 0",
        "SUMAS 125 125 100 100 100 200 0 0",
        "PERDIDA O GANANCIA 0 0 0 0 0 0 0 0",
        "SUMAS IGUALES 125 125 100 100 100 200 0 0",
    ]

    def evidencia(**lecturas):
        return {
            "celdas": [
                ({"lectura": valor} if columna in lecturas else None)
                for columna, valor in zip(parser.RAW_MONETARY_COLUMNS, [
                    lecturas.get("debitos"), lecturas.get("creditos"),
                    lecturas.get("saldo_deudor"), lecturas.get("saldo_acreedor"),
                    lecturas.get("activo"), lecturas.get("pasivo"),
                    lecturas.get("perdida"), lecturas.get("ganancia"),
                ])
            ]
        }

    evidencias = [
        None,
        evidencia(creditos=125, pasivo=100),
        evidencia(pasivo=100),
        evidencia(),
        evidencia(pasivo=100),
    ]
    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        evidencias,
        releer_celda=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert recuperadas[1].endswith("25 125 0 100 0 100 0 0")
    assert recuperadas[2].endswith("125 125 100 100 100 100 0 0")
    assert recuperadas[4].endswith("125 125 100 100 100 100 0 0")
    assert filas == [False, True, True, False, True]
    assert [cambio["linea"] for cambio in cambios] == [1, 2, 4]
    assert certificacion.estado == "certificada"
    assert certificacion.diagnostico == "CONTROLES_VALIDADOS"


def test_relectura_focal_recupera_suma_singular_y_ganancia_ejercicio():
    lineas = [
        "110101 Caja 110 0 110 0 110 0 0 0",
        "410101 Ventas 0 110 0 110 0 0 0 110",
        "Suma 10 110 110 110 110 0 0 110",
        "Ganancia Ejercicio 0 0 0 0 0 110 110 0",
        "Totales 110 110 110 110 110 10 10 110",
    ]

    def evidencia(**lecturas):
        return {
            "celdas": [
                (
                    {"lectura": lecturas[columna]}
                    if columna in lecturas else None
                )
                for columna in parser.RAW_MONETARY_COLUMNS
            ]
        }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [
            None,
            None,
            evidencia(debitos=110),
            None,
            evidencia(pasivo=110, perdida=110),
        ],
        releer_celda=lambda celda: celda["lectura"],
        releer_celda_nativa=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert recuperadas[2].endswith("110 110 110 110 110 0 0 110")
    assert recuperadas[4].endswith("110 110 110 110 110 110 110 110")
    assert filas == [False, False, True, False, True]
    assert [cambio["linea"] for cambio in cambios] == [2, 4]
    assert certificacion.estado == "certificada"
    assert certificacion.totales_finales_validos is True


def test_relectura_focal_acepta_un_digito_ocr_insertado_solo_si_cuadra():
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 40 0 40 0 40 0 0",
        "410101 Ventas 0 60 0 60 0 0 0 60",
        "SUBTOTAL 1000 100 100 100 100 40 0 60",
        "UTILIDAD DEL EJERCICIO 0 0 0 0 0 60 60 0",
        "TOTALES 1000 100 100 100 100 100 60 60",
    ]
    evidencia = lambda: {"celdas": [{"lectura": 100}, *([None] * 7)]}

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, None, None, evidencia(), None, evidencia()],
        releer_celda=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert parser._difiere_un_digito_monetario("24.514.099.5850", 24_514_099_550)
    assert recuperadas[3].startswith("SUBTOTAL 100 100")
    assert recuperadas[5].startswith("TOTALES 100 100")
    assert filas == [False, False, False, True, False, True]
    assert [cambio["linea"] for cambio in cambios] == [3, 5]
    assert certificacion.estado == "certificada"


def test_relectura_focal_corrige_control_estructural_solo_si_lo_confirma_ocr():
    lineas = [
        "110101 Caja 100000 0 100000 0 100000 0 0 0",
        "210101 Obligacion 0 110000 0 110000 0 110000 0 0",
        "510101 Ajuste 10000 0 10000 0 0 0 10000 0",
        "SUMAS 110000 110000 110000 110000 100000 130000 40000 0",
        "PERDIDA O GANANCIA 0 0 0 0 40000 0 0 40000",
        "SUMAS IGUALES 110000 110000 110000 110000 140000 140000 40000 40000",
    ]
    evidencia_subtotal = {
        "celdas": [None, None, None, None, None, {"lectura": 140000}, None, None],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, None, None, evidencia_subtotal, None, None],
        releer_celda=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert recuperadas[3].endswith(
        "110000 110000 110000 110000 100000 140000 40000 0",
    )
    assert filas == [False, False, False, True, False, False]
    assert cambios == [{
        "linea": 3,
        "columnas": ["pasivo"],
        "origen": "relectura_focal_de_control_estructural",
    }]
    assert certificacion.ecuacion_contable_fuente_valida is True
    assert certificacion.totales_finales_validos is True
    # El detalle todavía no reproduce el subtotal corregido: la relectura del
    # control no puede convertir por sí sola el documento en entregable.
    assert certificacion.estado == "fallida"


def test_relectura_focal_estructural_rechaza_cierre_sin_confirmacion_visual():
    lineas = [
        "110101 Caja 100000 0 100000 0 100000 0 0 0",
        "210101 Obligacion 0 110000 0 110000 0 110000 0 0",
        "510101 Ajuste 10000 0 10000 0 0 0 10000 0",
        "SUMAS 110000 110000 110000 110000 100000 130000 40000 0",
        "PERDIDA O GANANCIA 0 0 0 0 40000 0 0 40000",
        "SUMAS IGUALES 110000 110000 110000 110000 140000 140000 40000 40000",
    ]
    evidencia_subtotal = {
        "celdas": [None, None, None, None, None, {"lectura": 139000}, None, None],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, None, None, evidencia_subtotal, None, None],
        releer_celda=lambda celda: celda["lectura"],
    )

    assert recuperadas == lineas
    assert filas == [False] * len(lineas)
    assert cambios == []


def test_relectura_focal_estructural_no_se_encadena_con_otra_correccion():
    lineas = [
        "1.01.01.01 Caja 100000 0 100000 0 100000 0 0 0",
        "2.01.10.01 PPM por pagar 25000 225000 0 100000 0 200000 0 0",
        "SUMAS 125000 125000 100000 100000 100000 130000 20000 0",
        "PERDIDA O GANANCIA 0 0 0 0 20000 0 0 20000",
        "SUMAS IGUALES 125000 125000 100000 100000 120000 120000 20000 20000",
    ]
    evidencia_detalle = {
        "celdas": [None, {"lectura": 125000}, None, None, None, {"lectura": 100000}, None, None],
    }
    evidencia_subtotal = {
        "celdas": [None, None, None, None, None, {"lectura": 120000}, None, None],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, evidencia_detalle, evidencia_subtotal, None, None],
        releer_celda=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert recuperadas[1].endswith("25000 125000 0 100000 0 100000 0 0")
    assert recuperadas[2].endswith(
        "125000 125000 100000 100000 100000 130000 20000 0",
    )
    assert filas == [False, True, False, False, False]
    assert cambios == [{"linea": 1, "columnas": ["creditos", "pasivo"]}]
    assert certificacion.ecuacion_contable_fuente_valida is False


def test_lectura_cruzada_sin_codigo_recupera_digito_solo_si_preserva_fila():
    lineas = [
        "Caja 100.000 1.000 90.000 0 90.000 0 0 0",
        "SUMAS 100.000 10.000 90.000 0 90.000 0 0 0",
        "UTILIDAD DEL EJERCICIO 0 0 0 0 0 0 0 0",
        "SUMAS IGUALES 100.000 10.000 90.000 0 90.000 0 0 0",
    ]
    evidencia = {
        "lectura_cruzada": "CAJA 100.000 10.000 90.000 90.000",
        "celdas": [
            {"token": "100.000"}, {"token": "1.000"},
            {"token": "90.000"}, None, {"token": "90.000"},
            None, None, None,
        ],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas, [evidencia, None, None, None],
        releer_celda=lambda _celda: None,
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)

    assert recuperadas[0].endswith("100.000 10.000 90.000 0 90.000 0 0 0")
    assert filas == [True, False, False, False]
    assert cambios == [{
        "linea": 0,
        "columnas": ["creditos"],
        "origen": "lectura_textual_cruzada",
    }]
    assert parser._error_identidades_ocho_columnas(cuentas[0]) == 0


def test_lectura_cruzada_sin_codigo_rechaza_cifra_que_no_es_un_digito():
    lineas = ["Caja 100.000 1.000 90.000 0 90.000 0 0 0"]
    evidencia = {
        "lectura_cruzada": "CAJA 100.000 20.000 90.000 90.000",
        "celdas": [
            {"token": "100.000"}, {"token": "1.000"},
            {"token": "90.000"}, None, {"token": "90.000"},
            None, None, None,
        ],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas, [evidencia], releer_celda=lambda _celda: None,
    )

    assert recuperadas == lineas
    assert filas == [False]
    assert cambios == []


def test_relectura_nativa_repara_dos_digitos_solo_si_la_fila_cuadra():
    lineas = [
        "2.1.10.01 PPM por pagar 20.516 208.182 0 185.666 0 185.686 0 0",
    ]
    evidencia = {
        "celdas": [
            {"regular": 20_516, "nativa": 20_516},
            {"regular": 208_182, "nativa": 206_182},
            None,
            {"regular": 185_666, "nativa": 185_666},
            None,
            {"regular": 185_686, "nativa": 185_666},
            None,
            None,
        ],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [evidencia],
        releer_celda=lambda celda: celda["regular"],
        releer_celda_nativa=lambda celda: celda["nativa"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)

    assert recuperadas[0].endswith(
        "20.516 206.182 0 185.666 0 185.666 0 0",
    )
    assert parser._error_identidades_ocho_columnas(cuentas[0]) == 0
    assert filas == [True]
    assert cambios == [{
        "linea": 0,
        "columnas": ["creditos", "pasivo"],
        "origen": "relectura_nativa_sin_escalar",
    }]


def test_relectura_nativa_por_residuo_control_corrige_ceros_espurios_unicos():
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Cuenta OCR 0 12 0 12 12 0 0 0",
        "410101 Ventas 0 100 0 100 0 0 0 100",
        "SUMAS 100 100 100 100 100 0 0 100",
        "PERDIDA O GANANCIA 0 0 0 0 0 100 100 0",
        "SUMAS IGUALES 100 100 100 100 100 100 100 100",
    ]
    evidencia = {
        "celdas": [
            None,
            {"nativa": 0},
            None,
            {"nativa": 0},
            {"nativa": 0},
            None,
            None,
            None,
        ],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, evidencia, None, None, None, None],
        releer_celda=lambda _celda: None,
        releer_celda_nativa=lambda celda: celda["nativa"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert recuperadas[1].endswith("0 0 0 0 0 0 0 0")
    assert filas == [False, True, False, False, False, False]
    assert cambios == [{
        "linea": 1,
        "columnas": ["activo", "creditos", "saldo_acreedor"],
        "origen": "relectura_nativa_por_residuo_de_control",
    }]
    assert certificacion.estado == "certificada"


def test_relectura_nativa_por_residuo_rechaza_lectura_que_empeora_control():
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Cuenta OCR 0 12 0 12 12 0 0 0",
        "410101 Ventas 0 100 0 100 0 0 0 100",
        "SUMAS 100 100 100 100 100 0 0 100",
        "PERDIDA O GANANCIA 0 0 0 0 0 100 100 0",
        "SUMAS IGUALES 100 100 100 100 100 100 100 100",
    ]
    evidencia = {
        "celdas": [
            None,
            {"nativa": 13},
            None,
            {"nativa": 13},
            {"nativa": 13},
            None,
            None,
            None,
        ],
    }

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, evidencia, None, None, None, None],
        releer_celda=lambda _celda: None,
        releer_celda_nativa=lambda celda: celda["nativa"],
    )

    assert recuperadas == lineas
    assert filas == [False] * len(lineas)
    assert cambios == []


def test_relectura_focal_propone_cero_espurio_de_dos_digitos():
    linea = "110101 Caja 100 0 99 0 100 0 17 0"
    evidencia = {
        "celdas": [None, None, {"lectura": 100}, None, None, None,
                    {"lectura": 0}, None],
    }

    candidatos = parser._candidatos_focales_de_linea(
        linea,
        evidencia,
        releer_celda=lambda celda: celda["lectura"],
    )

    assert candidatos == {"perdida": 0}


def test_relectura_focal_prioriza_la_unica_columna_que_puede_reparar_ambas_identidades():
    cuenta = parser.parsear_linea(
        "1101201 Banco Santander 1.008.872.600 1.004.884.955 "
        "3.987.545 0 3.987.645 0 0 0",
        0,
        parser.FormatoCodigo.COMPACTO,
        ".",
        0.75,
    )

    assert cuenta is not None
    assert parser._error_identidades_ocho_columnas(cuenta) == 200
    assert parser._columnas_posibles_para_correccion_focal(cuenta) == {
        "saldo_deudor",
    }


def test_relectura_focal_local_no_se_descarta_por_total_final_ya_invalido():
    base = parser.CertificacionExtraccion(
        estado="fallida",
        diferencias={"saldo_deudor": 100, "saldo_acreedor": -500},
        filas_inconsistentes=[0, 4],
        totales_finales_validos=False,
    )
    candidata = parser.CertificacionExtraccion(
        estado="fallida",
        diferencias={"saldo_deudor": 200, "saldo_acreedor": -600},
        filas_inconsistentes=[4],
        totales_finales_validos=False,
    )
    final_perdido = parser.CertificacionExtraccion(
        estado="fallida",
        diferencias={"saldo_deudor": 0},
        filas_inconsistentes=[4],
        totales_finales_validos=False,
    )

    assert parser._mejora_certificacion_focal(base, candidata)
    assert not parser._mejora_certificacion_focal(
        parser.CertificacionExtraccion(
            estado="certificada",
            diferencias={"saldo_deudor": 0},
            filas_inconsistentes=[0, 4],
            totales_finales_validos=True,
        ),
        final_perdido,
    )


def test_relectura_focal_acepta_dos_ediciones_solo_en_control_que_cuadra():
    lineas = [
        "110101 Caja 100 0 100 0 100 0 0 0",
        "210101 Proveedores 0 40 0 40 0 40 0 0",
        "410101 Ventas 0 60 0 60 0 0 0 60",
        "SUBTOTAL 100 100 100 100 100 40 0 60",
        "UTILIDAD DEL EJERCICIO 0 0 0 0 0 60 60 0",
        "TOTALES 100 100 100 100 100 100 60 6004",
    ]
    evidencia_final = {"celdas": [None] * 7 + [{"lectura": 60}]}

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        [None, None, None, None, None, evidencia_final],
        releer_celda=lambda celda: celda["lectura"],
    )
    cuentas, _, _ = parser._parsear_lineas_ocho_columnas_focales(recuperadas)
    certificacion = parser.certificar_extraccion_columnas(
        list(cuentas.values()), metodo="ocr_coordinates_8_amounts",
    )

    assert not parser._difiere_un_digito_monetario("6004", 60)
    assert parser._difiere_hasta_n_digitos_monetarios("6004", 60, max_edits=2)
    assert recuperadas[5].endswith("100 100 60 60")
    assert filas == [False, False, False, False, False, True]
    assert cambios == [{"linea": 5, "columnas": ["ganancia"]}]
    assert certificacion.estado == "certificada"


def test_relectura_focal_no_acepta_cifra_que_no_repara_ambas_identidades():
    lineas = [
        "1.01.01.01 Caja 100 0 100 0 100 0 0 0",
        "2.01.10.01 PPM por pagar 25 225 0 100 0 200 0 0",
        "SUMAS 125 125 100 100 100 200 0 0",
    ]
    evidencias = [
        None,
        {
            "celdas": [
                None, {"lectura": 125}, None, None,
                None, {"lectura": 110}, None, None,
            ],
        },
        None,
    ]

    recuperadas, filas, cambios = parser.recuperar_celdas_ocr_focales(
        lineas,
        evidencias,
        releer_celda=lambda celda: celda["lectura"],
    )

    assert recuperadas == lineas
    assert filas == [False, False, False]
    assert cambios == []
