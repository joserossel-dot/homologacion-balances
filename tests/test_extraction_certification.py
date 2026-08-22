from __future__ import annotations

from types import SimpleNamespace

import app_validacion as app
import parser_universal as parser


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
