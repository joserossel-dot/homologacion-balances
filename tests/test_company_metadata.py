import app_validacion
from extractor_metadata import MetadataEmpresa
from io import BytesIO
from parser_universal import CuentaRaw, OrigenColumna


def test_valores_periodo_metadata_detecta_ejercicio_completo():
    meta = MetadataEmpresa(
        periodo_desde="01/01/2024",
        periodo_hasta="31/12/2024",
    )

    assert app_validacion._valores_periodo_metadata(meta) == (
        "Diciembre",
        2024,
        12,
    )


def test_valores_periodo_metadata_detecta_periodo_parcial():
    meta = MetadataEmpresa(
        periodo_desde="01/10/2024",
        periodo_hasta="31/12/2024",
    )

    assert app_validacion._valores_periodo_metadata(meta) == (
        "Diciembre",
        2024,
        3,
    )


def test_fechas_periodo_seleccionado_respeta_anio_bisiesto():
    assert app_validacion._fechas_periodo_seleccionado(
        "Febrero", 2024, 1,
    ) == ("01/02/2024", "29/02/2024")


def test_fechas_periodo_seleccionado_cruza_el_cambio_de_anio():
    assert app_validacion._fechas_periodo_seleccionado(
        "Marzo", 2024, 6,
    ) == ("01/10/2023", "31/03/2024")


def test_metadata_empresa_conserva_moneda_y_periodo_confirmados():
    meta = MetadataEmpresa(
        moneda="MM",
        mes_cierre="Junio",
        anio_cierre=2025,
        numero_meses=6,
    )

    assert meta.moneda == "MM"
    assert meta.mes_cierre == "Junio"
    assert meta.anio_cierre == 2025
    assert meta.numero_meses == 6


def test_detectar_periodos_comparativos_ignora_etiquetas_narrativas():
    assert app_validacion._detectar_periodos_comparativos(
        [
            "Sociedad constituida en 1987 y reorganizada en 2010",
            "Estado de situación financiera",
            "Al 31 de diciembre de 2019 y 2018",
            "Nota M$ M$",
        ],
        2026,
    ) == ("2019", "2018")


def test_encabezado_pdf_escaneado_usa_ocr_para_detectar_periodos(monkeypatch):
    class Upload(BytesIO):
        name = "auditado.pdf"

    class FakePage:
        def extract_text(self):
            return ""

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    app_validacion._extraer_lineas_encabezado_cached.clear()
    state = {}
    monkeypatch.setattr(app_validacion.st, "session_state", state)
    monkeypatch.setattr(app_validacion.st, "warning", lambda _message: None)
    monkeypatch.setattr(app_validacion, "_contenido_para_extraer", lambda _archivo: b"pdf")
    monkeypatch.setattr("pdfplumber.open", lambda _contenido: FakePDF())
    monkeypatch.setattr(app_validacion, "render_page", lambda _contenido, _pagina: b"png")
    monkeypatch.setattr(app_validacion, "detectar_rotacion_osd", lambda _imagen: 0)
    monkeypatch.setattr(
        app_validacion, "ocr_pagina",
        lambda _imagen, _rotacion, psm=6: (
            "Estado de Situación Financiera\n"
            "Al 31 de diciembre de 2018 y 2017\nNota M$ M$"
        ),
    )

    lineas = app_validacion._extraer_lineas_encabezado(Upload(b"pdf"))

    assert app_validacion._detectar_periodos_comparativos(lineas, 2026) == (
        "2018", "2017",
    )


def test_encabezado_ocr_continua_a_cero_y_marca_contingencia_rotacion(
    monkeypatch, caplog,
):
    class Upload(BytesIO):
        name = "auditado.pdf"

    class FakePage:
        def extract_text(self):
            return ""

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    app_validacion._extraer_lineas_encabezado_cached.clear()
    state = {}
    warnings = []
    monkeypatch.setattr(app_validacion.st, "session_state", state)
    monkeypatch.setattr(app_validacion.st, "warning", warnings.append)
    monkeypatch.setattr(app_validacion, "_contenido_para_extraer", lambda _archivo: b"otro-pdf")
    monkeypatch.setattr("pdfplumber.open", lambda _contenido: FakePDF())
    monkeypatch.setattr(app_validacion, "render_page", lambda _contenido, _pagina: b"png")
    monkeypatch.setattr(
        app_validacion, "detectar_rotacion_osd",
        lambda _imagen: (_ for _ in ()).throw(RuntimeError("osd")),
    )
    monkeypatch.setattr(
        app_validacion, "detectar_rotacion_heuristica",
        lambda _imagen: (_ for _ in ()).throw(RuntimeError("heuristica")),
    )
    rotations = []
    monkeypatch.setattr(
        app_validacion, "ocr_pagina",
        lambda _imagen, rotation, psm=6: (
            rotations.append(rotation)
            or "Estado de Situación Financiera\\nAl 31 de diciembre de 2018 y 2017"
        ),
    )

    lineas = app_validacion._extraer_lineas_encabezado(Upload(b"pdf"))

    assert rotations == [0]
    assert app_validacion._detectar_periodos_comparativos(lineas, 2026) == (
        "2018", "2017",
    )
    assert state["header_ocr_rotation_warnings"]["auditado.pdf"]["rotacion_aplicada"] == "0"
    assert warnings and "rotación 0° por contingencia" in warnings[0]
    assert "header_ocr_rotation_fallback" in caplog.text


def test_reextraccion_exitosa_limpia_advertencia_previa_de_rotacion(monkeypatch):
    class Upload(BytesIO):
        name = "auditado.pdf"

    class FakePage:
        def extract_text(self):
            return ""

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    app_validacion._extraer_lineas_encabezado_cached.clear()
    state = {
        "header_ocr_rotation_warnings": {
            "auditado.pdf": {"rotacion_aplicada": "0"},
        },
    }
    monkeypatch.setattr(app_validacion.st, "session_state", state)
    monkeypatch.setattr(app_validacion.st, "warning", lambda _message: None)
    monkeypatch.setattr(app_validacion, "_contenido_para_extraer", lambda _archivo: b"pdf-ok")
    monkeypatch.setattr("pdfplumber.open", lambda _contenido: FakePDF())
    monkeypatch.setattr(app_validacion, "render_page", lambda _contenido, _pagina: b"png")
    monkeypatch.setattr(app_validacion, "detectar_rotacion_osd", lambda _imagen: 270)
    monkeypatch.setattr(
        app_validacion, "ocr_pagina",
        lambda _imagen, rotation, psm=6: "Al 31 de diciembre de 2023",
    )

    app_validacion._extraer_lineas_encabezado(Upload(b"pdf"))

    assert "auditado.pdf" not in state["header_ocr_rotation_warnings"]


def test_valor_fila_periodo_conserva_actual_y_anterior():
    import pandas as pd

    row = pd.Series({
        "monto": 107874,
        "monto_periodo_2019": 107874,
        "monto_periodo_2018": 93372,
        "monto_periodo_actual": 107874,
        "monto_periodo_anterior": 93372,
    })

    assert app_validacion._valor_fila_periodo(row, "2019", 0) == 107874
    assert app_validacion._valor_fila_periodo(row, "2018", 1) == 93372


def test_ui_usa_saldo_clasificado_del_periodo_en_balance_8_columnas(monkeypatch):
    cuenta = CuentaRaw(
        linea=1,
        codigo=None,
        nombre="BANCO",
        monto=3_320_530,
        origen_columna=OrigenColumna.ACTIVO,
        montos_columnas={
            "debitos": 1_034_578_021,
            "creditos": 1_031_257_491,
            "saldo_deudor": 3_320_530,
            "saldo_acreedor": 0,
            "activo": 3_320_530,
            "pasivo": 0,
            "perdida": 0,
            "ganancia": 0,
        },
        montos_periodos={"2022": 3_320_530, "actual": 3_320_530},
    )
    monkeypatch.setattr(app_validacion, "_periodos_seleccionados", lambda: ("2022",))

    principal, campos = app_validacion._campos_periodos_cuenta(cuenta)

    assert principal == 3_320_530
    assert campos["monto_periodo_2022"] == 3_320_530
    assert campos["monto_periodo_actual"] == 3_320_530
