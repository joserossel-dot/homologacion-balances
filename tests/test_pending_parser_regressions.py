import os
from pathlib import Path
from types import SimpleNamespace
import pytest
import parser_universal as p


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
        parser._extraction_method = "ocr_classified_two_columns"
        return ["IVA CREDITO FISCAL 100", "PROVEEDORES 100"], True, 0

    monkeypatch.setattr(parser, "_extraer_lineas", fake_extract)

    result = parser.parsear(source)

    assert [(account.nombre, account.origen_columna) for account in result.cuentas] == [
        ("IVA CREDITO FISCAL", p.OrigenColumna.ACTIVO),
        ("PROVEEDORES", p.OrigenColumna.PASIVO),
    ]


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
