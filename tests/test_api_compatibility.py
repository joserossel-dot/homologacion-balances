"""Validación: ParserPDF.parsear(path) == ParserPDF.parsear(path, ExtractionContext()).

Garantiza que introducir ExtractionContext no cambió el comportamiento
histórico del parser. Compara resultado sin contexto vs con contexto vacío.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parser_universal import ExtractionContext, ParserPDF

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "datasets" / "validacion"

PDFS = [
    "BALANCE 2016.pdf",
    "BALANCE DALMACIA 1 2016.pdf",
    "Balance Gonzagri S.A.pdf",
]

SCANNED_PDFS = [
    "BALANCE DAIN 2015 hoja 1.pdf",
    "Balance Agricola San Felix S A  2013.pdf",
]

ALL_PDFS = PDFS + SCANNED_PDFS


def _resolve(name: str) -> Path:
    p = DATASET_DIR / name
    if not p.exists():
        pytest.skip(f"PDF no encontrado: {p}")
    return p


class TestApiCompatibilidad:

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismo_numero_cuentas(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        assert len(r1.cuentas) == len(r2.cuentas), (
            f"{pdf_name}: {len(r1.cuentas)} vs {len(r2.cuentas)}"
        )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismos_codigos(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        for i, (c1, c2) in enumerate(zip(r1.cuentas, r2.cuentas)):
            assert c1.codigo == c2.codigo, (
                f"{pdf_name}: cuenta {i} codigo '{c1.codigo}' vs '{c2.codigo}'"
            )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismos_nombres(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        for i, (c1, c2) in enumerate(zip(r1.cuentas, r2.cuentas)):
            assert c1.nombre == c2.nombre, (
                f"{pdf_name}: cuenta {i} nombre '{c1.nombre}' vs '{c2.nombre}'"
            )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismos_montos(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        for i, (c1, c2) in enumerate(zip(r1.cuentas, r2.cuentas)):
            assert c1.monto == c2.monto, (
                f"{pdf_name}: cuenta {i} monto {c1.monto} vs {c2.monto}"
            )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_misma_rotacion(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        assert r1.rotacion_aplicada == r2.rotacion_aplicada, (
            f"{pdf_name}: rotacion {r1.rotacion_aplicada} vs {r2.rotacion_aplicada}"
        )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismo_formato_codigo(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        assert r1.formato_codigo == r2.formato_codigo, (
            f"{pdf_name}: formato {r1.formato_codigo} vs {r2.formato_codigo}"
        )

    @pytest.mark.parametrize("pdf_name", PDFS)
    def test_mismo_separador(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        assert r1.separador_miles == r2.separador_miles, (
            f"{pdf_name}: separador '{r1.separador_miles}' vs '{r2.separador_miles}'"
        )


class TestApiCompatibilidadOcr:
    """PDFs escaneados (OCR): verificación en un solo test por PDF (evita re-parseos)."""

    @pytest.mark.parametrize("pdf_name", SCANNED_PDFS)
    def test_ocr_compatibilidad(self, pdf_name):
        path = _resolve(pdf_name)
        parser = ParserPDF()
        r1 = parser.parsear(path)
        r2 = parser.parsear(path, ExtractionContext())
        assert len(r1.cuentas) == len(r2.cuentas)
        assert r1.rotacion_aplicada == r2.rotacion_aplicada
        assert r1.formato_codigo == r2.formato_codigo
        assert r1.separador_miles == r2.separador_miles
        for c1, c2 in zip(r1.cuentas, r2.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto
