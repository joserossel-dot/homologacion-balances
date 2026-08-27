import app_validacion
from extractor_metadata import MetadataEmpresa
from io import BytesIO


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
        ["Estado de situación financiera", "Nota 2019 2018 acumulado"],
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

    monkeypatch.setattr(app_validacion, "_contenido_para_extraer", lambda _archivo: b"pdf")
    monkeypatch.setattr("pdfplumber.open", lambda _contenido: FakePDF())
    monkeypatch.setattr(app_validacion, "render_page", lambda _contenido, _pagina: b"png")
    monkeypatch.setattr(
        app_validacion, "ocr_pagina",
        lambda _imagen, _rotacion, psm=6: (
            "Estado de Situación Financiera\nNota 2018 2017\nM$ M$"
        ),
    )

    lineas = app_validacion._extraer_lineas_encabezado(Upload(b"pdf"))

    assert app_validacion._detectar_periodos_comparativos(lineas, 2026) == (
        "2018", "2017",
    )


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
