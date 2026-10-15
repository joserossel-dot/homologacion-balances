import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
import parser_universal as p


def test_suplemento_clasificado_se_omite_solo_despues_de_tabla_tributaria():
    tributario = "BALANCE TRIBUTARIO (a nivel 3) CUENTA DEBITO CREDITOS"
    clasificado = "BALANCE CLASIFICADO (Valores Nominales)"
    resultados = "ESTADO DE RESULTADO (Valores Nominales)"

    assert p._es_balance_tributario(tributario)
    assert not p._es_balance_clasificado_suplementario(clasificado, False)
    assert p._es_balance_clasificado_suplementario(clasificado, True)
    assert p._es_estado_resultado(resultados)


def test_numeric_name_suffix_is_not_merged_into_debit():
    headers = ["Cuenta", "Debe", "Haber", "Deudor", "Acreedor", "Activo", "Pasivo", "Pérdidas", "Ganancias"]
    words = [{"text": text, "x0": i*100, "x1": i*100+30, "top": 10} for i, text in enumerate(headers)]
    words += [{"text": "BANCOESTADO", "x0": 0, "x1": 45, "top": 30},
              {"text": "1", "x0": 65, "x1": 69, "top": 30}]
    words += [{"text": text, "x0": (i+1)*100, "x1": (i+1)*100+30, "top": 30}
              for i, text in enumerate(["120", "20", "100", "0", "100", "0", "0", "0"])]
    lines, _ = p._extraer_tabla_balance_por_coordenadas(SimpleNamespace(extract_words=lambda **kw: words))
    assert lines == ["BANCOESTADO 1 120 20 100 0 100 0 0 0"]


def test_coordinate_header_accepts_plural_cuentas():
    headers = [
        "Cuentas", "Debe", "Haber", "Deudor", "Acreedor", "Activo",
        "Pasivo", "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 100, "x1": index * 100 + 40, "top": 10}
        for index, text in enumerate(headers)
    ]
    words += [
        {"text": "Caja", "x0": 0, "x1": 35, "top": 30},
        *[
            {"text": text, "x0": (index + 1) * 100, "x1": (index + 1) * 100 + 35, "top": 30}
            for index, text in enumerate(["120", "20", "100", "0", "100", "0", "0", "0"])
        ],
    ]

    lines, _ = p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words)
    )

    assert lines == ["Caja 120 20 100 0 100 0 0 0"]


def test_empty_pdfplumber_page_list_uses_rasterizable_page_count(monkeypatch, tmp_path):
    source = tmp_path / "escaneado.pdf"
    source.write_bytes(b"placeholder")
    parser = p.ParserPDF()

    class EmptyPDF:
        pages = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    seen = []
    monkeypatch.setattr(p.pdfplumber, "open", lambda _path: EmptyPDF())
    monkeypatch.setattr(parser, "_contar_paginas_rasterizables", lambda _path: 2)
    monkeypatch.setattr(
        parser,
        "_ocr_documento",
        lambda _path, pages: (seen.append(pages) or (["Caja 1"], True, 270)),
    )

    lines, requires_ocr, rotation = parser._extraer_lineas(source)

    assert seen == [2]
    assert lines == ["Caja 1"]
    assert requires_ocr is True
    assert rotation == 270


def test_texto_nativo_lateral_usa_layout_de_poppler(monkeypatch, tmp_path):
    source = tmp_path / "lateral.pdf"
    source.write_bytes(b"placeholder")

    texto_lateral = "\n".join([
        "ATNEUC", "ERBMON", "SOTIBED", "SOTIDERC", "RODUED",
        "RODEERCA", "OVITCA", "OVISAP", "ADIDREP", "AICNANAG",
    ])
    texto_layout = "\n".join([
        "Cuenta Nombre Debitos Creditos Deudor Acreedor Activo Pasivo Perdida Ganancia",
        "110101 CAJA 100 0 100 0 100 0 0 0",
        "210101 PROVEEDORES 0 100 0 100 0 100 0 0",
        "510101 GASTO 100 0 100 0 0 0 100 0",
    ])

    class NativePage:
        def extract_text(self):
            return texto_lateral

        def extract_words(self, **_kwargs):
            return []

        def extract_tables(self):
            return []

    class NativePdf:
        pages = [NativePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(p.pdfplumber, "open", lambda _path: NativePdf())
    monkeypatch.setattr(p.shutil, "which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        p.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, stdout=texto_layout, stderr="",
        ),
    )
    instance = p.ParserPDF()
    instance._ocr_advertencias = []

    lines, requires_ocr, rotation = instance._extraer_lineas(source)

    assert p._texto_nativo_parece_lateral(texto_lateral.splitlines())
    assert not p._texto_nativo_parece_lateral(["Cuenta Nombre Debitos"])
    assert lines == texto_layout.splitlines()
    assert requires_ocr is False
    assert rotation == 0
    assert instance._extraction_method == "native_layout_8_columns"
    assert any("encabezados laterales invertidos" in warning for warning in instance._ocr_advertencias)


def test_layout_nativo_lateral_no_reemplaza_salida_sin_tabla(monkeypatch, tmp_path):
    source = tmp_path / "lateral-sin-tabla.pdf"
    source.write_bytes(b"placeholder")
    monkeypatch.setattr(p.shutil, "which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(
        p.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, stdout="Texto sin importes", stderr="",
        ),
    )

    assert p._extraer_texto_nativo_layout(source) == []


def test_result_statement_egreso_propagates_loss_across_page_headers():
    accounts = [
        p.CuentaRaw(1, None, "ESTADO DE RESULTADO", None),
        p.CuentaRaw(2, None, "INGRESO", None),
        p.CuentaRaw(3, None, "Venta de servicios", 100.0),
        p.CuentaRaw(4, None, "EGRESO", None),
        p.CuentaRaw(
            5, None, "Servicio externo", 80.0,
            origen_columna=p.OrigenColumna.GANANCIA,
        ),
        p.CuentaRaw(6, None, "ESTADO DE RESULTADO", None),
        p.CuentaRaw(7, None, "Servicio continuado", 60.0),
    ]

    annotated = p.anotar_secciones_balance_clasificado(accounts)

    assert annotated == 3
    assert accounts[2].origen_columna is p.OrigenColumna.GANANCIA
    assert accounts[4].origen_columna is p.OrigenColumna.PERDIDA
    assert accounts[6].origen_columna is p.OrigenColumna.PERDIDA


def test_result_statement_subheadings_replace_false_gain_origin():
    accounts = [
        p.CuentaRaw(1, None, "ESTADO DE RESULTADOS", None),
        p.CuentaRaw(2, None, "(+) Ingresos de la Explotación", None),
        p.CuentaRaw(3, None, "Ventas", 100.0),
        p.CuentaRaw(4, None, "(-) Costos de la Explotación", None),
        p.CuentaRaw(
            5, None, "Costo de Ventas", 80.0,
            origen_columna=p.OrigenColumna.GANANCIA,
        ),
        p.CuentaRaw(6, None, "! mn (+) Gastos de Administracion y ventas", None),
        p.CuentaRaw(
            7, None, "Materiales de Oficina", 20.0,
            origen_columna=p.OrigenColumna.GANANCIA,
        ),
        p.CuentaRaw(8, None, "(-) Gastos Fianacieros", None),
        p.CuentaRaw(
            9, None, "Intereses Pagados", 10.0,
            origen_columna=p.OrigenColumna.GANANCIA,
        ),
    ]

    annotated = p.anotar_secciones_balance_clasificado(accounts)

    assert annotated == 4
    assert accounts[2].origen_columna is p.OrigenColumna.GANANCIA
    assert accounts[4].origen_columna is p.OrigenColumna.PERDIDA
    assert accounts[6].origen_columna is p.OrigenColumna.PERDIDA
    assert accounts[8].origen_columna is p.OrigenColumna.PERDIDA


def test_formulario_tributario_y_continuacion_se_omiten_sin_perder_balance():
    omit_form, active = p._debe_omitir_pagina_formulario_tributario(
        "REPUBLICA DE CHILE SERVICIO DE IMPUESTOS INTERNOS "
        "AÑO TRIBUTARIO 2016 FORM. 22",
        False,
    )
    omit_continuation, active = p._debe_omitir_pagina_formulario_tributario(
        "Declaro bajo juramento que esta información es fiel de la verdad.",
        active,
    )
    omit_balance, active = p._debe_omitir_pagina_formulario_tributario(
        "BALANCE GENERAL ESTADO DE RESULTADOS",
        active,
    )

    assert (omit_form, omit_continuation, omit_balance, active) == (
        True, True, False, False,
    )
    assert p._debe_omitir_pagina_formulario_tributario(
        "REPUBLICA DE CHILE AÑO TRIBUTARIO 2016 "
        "IMPUESTOS ANUALES A LA RENTA",
        False,
    ) == (True, True)


def test_hierarchical_parent_requires_prefix_and_amount_evidence():
    lines = ["11012 Bancos 120 20 100 0 100 0 0 0",
             "1101201 Banco uno 70 10 60 0 60 0 0 0",
             "1101202 Banco dos 50 10 40 0 40 0 0 0"]
    accounts = [p.parsear_linea(l, i, p.FormatoCodigo.COMPACTO, ".") for i,l in enumerate(lines)]
    values = [dict(c.montos_columnas) for c in accounts]
    assert p.marcar_subtotales_jerarquicos(accounts) == 1
    assert accounts[0].es_total
    assert [c.montos_columnas for c in accounts] == values
    accounts[0].es_total = False
    accounts[1].codigo = "9999999"
    assert p.marcar_subtotales_jerarquicos(accounts) == 0
    accounts[1].codigo = "1101201"
    accounts[0].montos_columnas["debitos"] += 1
    assert p.marcar_subtotales_jerarquicos(accounts) == 0
    accounts[0].montos_columnas["creditos"] += 1
    assert p.marcar_subtotales_jerarquicos(accounts) == 1
    assert accounts[0].montos_columnas["debitos"] == 121


def test_classified_page_does_not_inherit_eight_column_geometry():
    words = []
    for row in range(6):
        words.extend([{"text": "Cuenta", "x0": 10, "x1": 80, "top": row*20},
                      {"text": "100", "x0": 500, "x1": 530, "top": row*20}])
    assert p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100))
    ) == ([], None)


def _continuation_words_with_amount_positions(amount_positions):
    """Construye filas sin encabezado sobre una grilla monetaria heredada."""
    words = []
    centers = list(range(0, 900, 100))
    for row, positions in enumerate(amount_positions):
        top = (row + 1) * 20
        words.append({
            "text": f"Cuenta{row}", "x0": 10, "x1": 80, "top": top,
        })
        for column, value in positions.items():
            center = centers[column + 1]
            words.append({
                "text": str(value), "x0": center - 15, "x1": center + 15,
                "top": top,
            })
    return words


def test_sparse_eight_column_continuation_inherits_geometry_when_positions_cover_grid():
    """Celdas vacías no convierten una continuación de ocho columnas en rechazo."""
    words = _continuation_words_with_amount_positions([
        {0: 100, 1: 100, 3: 100, 5: 100},
        {0: 110, 1: 110, 2: 110, 4: 110},
        {0: 120, 1: 120, 3: 120, 5: 120},
        {0: 130, 1: 130, 2: 130, 4: 130},
        {0: 140, 1: 140, 3: 140, 5: 140},
        {0: 150, 1: 150, 6: 150, 7: 150},
    ])

    lines, centers = p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100)),
    )

    assert centers == list(range(0, 900, 100))
    assert len(lines) == 6
    assert lines[0] == "Cuenta0 100 100 0 100 0 100 0 0"
    assert lines[-1] == "Cuenta5 150 150 0 0 0 0 150 150"


def test_sparse_continuation_keeps_initial_rows_with_fewer_observed_importes():
    words = _continuation_words_with_amount_positions([
        {0: 100, 1: 100, 3: 100},
        {0: 110, 1: 110, 3: 110},
        {0: 120, 1: 120, 3: 120},
        {0: 130, 1: 130, 3: 130, 5: 130},
        {0: 140, 1: 140, 2: 140, 4: 140},
        {0: 150, 1: 150, 6: 150, 7: 150},
    ])

    lines, _ = p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100)),
    )

    assert len(lines) == 6
    assert lines[0] == "Cuenta0 100 100 0 100 0 0 0 0"


def test_sparse_continuation_ignores_metadata_before_and_after_the_table():
    words = _continuation_words_with_amount_positions([
        {0: 100, 1: 100, 3: 100, 5: 100},
        {0: 110, 1: 110, 2: 110, 4: 110},
        {0: 120, 1: 120, 3: 120, 5: 120},
        {0: 130, 1: 130, 2: 130, 4: 130},
        {0: 140, 1: 140, 3: 140, 5: 140},
        {0: 150, 1: 150, 6: 150, 7: 150},
    ])
    for word in words:
        word["top"] += 40
    words.extend([
        {"text": "Dirección", "x0": 10, "x1": 80, "top": 0},
        {"text": "119", "x0": 470, "x1": 500, "top": 0},
        {"text": "Continua", "x0": 10, "x1": 80, "top": 180},
    ])

    lines, _ = p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100)),
    )

    assert len(lines) == 6
    assert all("Dirección" not in line and "Continua" not in line for line in lines)


def test_four_column_state_does_not_inherit_eight_column_geometry():
    """Cuatro posiciones fijas no prueban una continuación de ocho columnas."""
    words = _continuation_words_with_amount_positions([
        {0: 100, 1: 100, 2: 100, 3: 100},
        {0: 110, 1: 110, 2: 110, 3: 110},
        {0: 120, 1: 120, 2: 120, 3: 120},
        {0: 130, 1: 130, 2: 130, 3: 130},
        {0: 140, 1: 140, 2: 140, 3: 140},
        {0: 150, 1: 150, 2: 150, 3: 150},
    ])

    assert p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words), list(range(0, 900, 100)),
    ) == ([], None)


def test_coordinate_header_without_account_label_falls_back_without_crashing():
    """OCR may lose CUENTA while preserving the eight monetary headings."""
    headers = [
        "Debe", "Haber", "Deudor", "Acreedor", "Activo", "Pasivo",
        "Pérdidas", "Ganancias",
    ]
    words = [
        {"text": text, "x0": index * 80, "x1": index * 80 + 35, "top": 10}
        for index, text in enumerate(headers)
    ]

    lines, centers = p._extraer_tabla_balance_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words)
    )

    assert lines == []
    assert centers is None


def _classified_double_column_words(include_header=True):
    words = []

    def add(text, x0, top):
        words.append({"text": text, "x0": x0, "x1": x0 + 45, "top": top})

    if include_header:
        add("Activo", 100, 10)
        add("Circulante", 155, 10)
        add("Pasivo", 620, 10)
        add("Circulante", 680, 10)
    for index in range(5):
        top = 30 + index * 20
        add(f"CuentaActiva{index}", 100, top)
        add(str(100 + index), 365, top)
        add(f"CuentaPasiva{index}", 620, top)
        add(str(200 + index), 880, top)
    add("TOTAL", 100, 150)
    add("ACTIVOS", 155, 150)
    add("600", 365, 150)
    # Simula la T inicial que OCR perdió en la última fila paralela.
    add("OFAL", 620, 150)
    add("PASIVOS", 675, 150)
    add("600", 880, 150)
    return words


def test_classified_double_column_ocr_preserves_observed_side():
    rows = p._extraer_balance_clasificado_doble_columna_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: _classified_double_column_words())
    )

    assert ("CuentaActiva0 100", p.OrigenColumna.ACTIVO) in rows
    assert ("CuentaPasiva0 200", p.OrigenColumna.PASIVO) in rows
    assert ("TOTAL ACTIVOS 600", p.OrigenColumna.ACTIVO) in rows
    assert ("TOTAL PASIVOS 600", p.OrigenColumna.PASIVO) in rows


def test_classified_double_column_ocr_preserves_amount_cell_evidence():
    rows, evidences = p._extraer_balance_clasificado_doble_columna_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: _classified_double_column_words()),
        incluir_evidencia_importes=True,
    )

    index = rows.index(("CuentaActiva0 100", p.OrigenColumna.ACTIVO))
    assert len(evidences) == len(rows)
    assert evidences[index] is not None
    assert evidences[index]["token"] == "100"
    assert evidences[index]["bbox"][:2] == (365.0, 30.0)


def test_classified_double_column_keeps_equity_section_separate_from_physical_side():
    words = _classified_double_column_words()

    def add(text, x0, top):
        words.append({"text": text, "x0": x0, "x1": x0 + 45, "top": top})

    # La cabecera no tiene monto y por eso no se transforma en cuenta. Las
    # filas siguientes siguen físicamente al lado derecho, pero pertenecen a
    # patrimonio y no a pasivo.
    add("Patrimonio", 620, 180)
    add("Neto", 690, 180)
    add("Capital", 620, 200)
    add("Emitido", 690, 200)
    add("40", 880, 200)

    rows = p._extraer_balance_clasificado_doble_columna_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words),
        incluir_seccion_contable=True,
    )

    assert ("Capital Emitido 40", p.OrigenColumna.PASIVO, "patrimonio") in rows
    # La columna física no se reescribe: queda disponible para auditoría.
    assert all(row[1] is p.OrigenColumna.PASIVO for row in rows if row[0] == "Capital Emitido 40")


def test_classified_double_column_ignores_zero_leaked_from_left_total():
    words = _classified_double_column_words()

    def add(text, x0, top):
        words.append({"text": text, "x0": x0, "x1": x0 + 45, "top": top})

    # El importe cero del total izquierdo cae al otro lado del corte; no debe
    # convertir el control derecho en una cuenta llamada "0 TOTAL ...".
    add("0", 500, 180)
    add("TOTAL", 620, 180)
    add("Patrimonio", 680, 180)
    add("40", 880, 180)

    rows = p._extraer_balance_clasificado_doble_columna_por_coordenadas(
        SimpleNamespace(extract_words=lambda **kw: words),
        incluir_seccion_contable=True,
    )

    assert any(
        row[0] == "TOTAL Patrimonio 40" and row[1] is p.OrigenColumna.PASIVO
        for row in rows
    )


def test_celda_clasificada_observada_conserva_digito_que_es_parte_de_la_glosa():
    account = p.parsear_linea_clasificada_observada(
        "CUENTA BCO. ESTADO 1 778.835", 1, ".",
    )

    assert account is not None
    assert account.nombre == "CUENTA BCO. ESTADO 1"
    assert account.monto == 778_835


def test_patrimonio_neto_total_se_conserva_como_control_no_clasificable():
    account = p.parsear_linea(
        "Patrimonio Neto Total 25.995.932.723", 1,
        p.FormatoCodigo.SIN_CODIGO, ".", 0.75,
    )

    assert account is not None
    assert account.es_total is True


def test_anota_estado_resultados_separado_sin_reclasificar_el_balance():
    accounts = [
        p.CuentaRaw(
            1, None, "Capital Emitido", 100,
            origen_columna=p.OrigenColumna.PASIVO,
            seccion_contable="patrimonio",
        ),
        p.CuentaRaw(2, None, "Estados de Resultados Intermedios", 0),
        p.CuentaRaw(3, None, "Ingresos Ordinarios", 80),
        p.CuentaRaw(4, None, "Gastos de Administracion", 20),
    ]

    annotated = p.anotar_estado_financiero(accounts)

    assert annotated == 4
    assert accounts[0].estado_financiero == "balance"
    assert [account.estado_financiero for account in accounts[1:]] == [
        "resultados", "resultados", "resultados",
    ]


def test_classified_double_column_ocr_requires_structural_header():
    rows = p._extraer_balance_clasificado_doble_columna_por_coordenadas(
        SimpleNamespace(
            extract_words=lambda **kw: _classified_double_column_words(
                include_header=False
            )
        )
    )

    assert rows == []


def test_parser_keeps_geometric_classified_origin(monkeypatch, tmp_path):
    parser = p.ParserPDF()
    source = tmp_path / "clasificado.pdf"
    source.write_bytes(b"placeholder")

    monkeypatch.setattr(p, "validar_archivo", lambda path: (True, ""))
    monkeypatch.setattr(parser, "_analizar_documento", lambda path: None)

    def fake_extract(path, context):
        parser._origenes_lineas_ocr = [
            p.OrigenColumna.ACTIVO,
            p.OrigenColumna.PASIVO,
        ]
        parser._secciones_lineas_ocr = ["activo", "patrimonio"]
        parser._extraction_method = "ocr_classified_two_columns"
        return ["IVA CREDITO FISCAL 100", "PROVEEDORES 100"], True, 0

    monkeypatch.setattr(parser, "_extraer_lineas", fake_extract)

    result = parser.parsear(source)

    assert [(account.nombre, account.origen_columna) for account in result.cuentas] == [
        ("IVA CREDITO FISCAL", p.OrigenColumna.ACTIVO),
        ("PROVEEDORES", p.OrigenColumna.PASIVO),
    ]
    assert [account.seccion_contable for account in result.cuentas] == [
        "activo", "patrimonio",
    ]


def test_native_classified_extractor_preserves_geometric_side(monkeypatch, tmp_path):
    class NativePage:
        def extract_text(self):
            return "BALANCE CLASIFICADO\nACTIVO CIRCULANTE PASIVO CIRCULANTE"

        def extract_words(self, **_kwargs):
            return _classified_double_column_words()

    class NativePdf:
        pages = [NativePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    source = tmp_path / "clasificado-nativo.pdf"
    source.write_bytes(b"placeholder")
    instance = p.ParserPDF()
    instance._ocr_advertencias = []
    monkeypatch.setattr(p.pdfplumber, "open", lambda _path: NativePdf())

    lines, requires_ocr, rotation = instance._extraer_lineas(source)

    assert requires_ocr is False
    assert rotation == 0
    assert instance._extraction_method == "native_classified_two_columns"
    assert ("CuentaActiva0 100") in lines
    assert instance._origenes_lineas_ocr[0] is p.OrigenColumna.ACTIVO
    assert instance._origenes_lineas_ocr[1] is p.OrigenColumna.PASIVO


@pytest.mark.parametrize("filename,pages,finals_valid", [
    ("parque_cultural_valparaiso_2024.pdf", None, True),
    ("london38_balance.pdf", [1], True),
    ("afuminsal_2016.pdf", None, True),
    ("fundacion_arte_solidaridad_2024.pdf", None, False),
])
def test_documento_real_opcional(filename, pages, finals_valid, tmp_path):
    """Documentos privados externos: no se incorporan al repositorio."""
    folder = os.environ.get("BALANCE_REAL_TEST_DIR")
    if not folder:
        pytest.skip("Defina BALANCE_REAL_TEST_DIR para la matriz privada")
    from document_scope import select_pdf
    source = Path(folder) / filename
    content = source.read_bytes()
    path = tmp_path / filename
    path.write_bytes(select_pdf(content, pages) if pages else content)
    result = p.ParserPDF().parsear(path)
    cert = result.certificacion_extraccion
    assert (cert.estado == "certificada" or cert.columnas_finales_validadas) is finals_valid
    if filename.startswith(("parque_", "london")):
        assert cert.estado == "certificada"
        assert not any(cert.diferencias.values())
        assert not cert.filas_inconsistentes
        if filename.startswith("parque_"):
            assert cert.columnas_finales_validadas
            assert all(c.es_total for c in result.cuentas if not c.codigo and c.monto)
    elif filename.startswith("afuminsal"):
        assert cert.resultado_ejercicio == 9910945
        assert any(c.codigo == "2301001" and c.monto == 15201792 for c in result.cuentas)
    else:
        assert cert.estado == "fallida"
        assert cert.filas_inconsistentes
    assert source.read_bytes() == content
