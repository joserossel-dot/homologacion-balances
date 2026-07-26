"""Tests de integración para DocumentAnalyzer + ParserPDF.

Verifica que:
  1. La integración no rompe el parseo existente
  2. El análisis documental se agrega correctamente
  3. Las advertencias del análisis se transmiten
  4. Los metadatos están accesibles
  5. Casos extremos: PDFs escaneados, sin código, con tabla
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parser_universal import ParserPDF
from parsers.analyzer import DocumentAnalyzer
from parsers.integration import EnhancedParseResult, parse_with_analysis

BASE_DIR = Path(__file__).resolve().parent.parent
DATASETS = {
    "balance_2016": BASE_DIR / "datasets" / "validacion" / "BALANCE 2016.pdf",
    "balance_dalmacia": BASE_DIR / "datasets" / "validacion" / "BALANCE DALMACIA 1 2016.pdf",
    "balance_dain": BASE_DIR / "datasets" / "validacion" / "BALANCE DAIN 2015 hoja 1.pdf",
}


def test_enhanced_parse_result_imports():
    """Los símbolos se importan correctamente desde parsers."""
    from parsers import EnhancedParseResult as EPR, parse_with_analysis as pwa
    assert EPR is not None
    assert pwa is not None


class TestEnhancedParseResultStructure:
    """Estructura y propiedades de EnhancedParseResult."""

    def test_wraps_resultado_parseo(self, native_pdf):
        result = _parse(native_pdf)
        assert hasattr(result, "resultado")
        assert hasattr(result, "analysis")

    def test_passthrough_properties(self, native_pdf):
        result = _parse(native_pdf)
        assert result.archivo == result.resultado.archivo
        assert result.cuentas is result.resultado.cuentas
        assert result.advertencias is result.resultado.advertencias
        assert result.formato_codigo == result.resultado.formato_codigo
        assert result.separador_miles == result.resultado.separador_miles
        assert result.requirio_ocr == result.resultado.requirio_ocr

    def test_analysis_properties(self, native_pdf):
        result = _parse(native_pdf)
        assert result.tipo_documento == result.analysis.file.file_type
        assert result.necesita_ocr == result.analysis.needs_ocr
        assert result.orientacion_detectada == result.analysis.orientation.rotation
        assert result.layout_confidence == result.analysis.layout.confidence
        assert result.confianza_global == result.analysis.overall_confidence
        assert result.tiene_texto_nativo == result.analysis.text.has_native_text
        assert result.tiene_codigos == result.analysis.code.has_codes
        assert result.tiene_tablas == result.analysis.tables.has_tables

    def test_formato_codigo_detectado(self, native_pdf):
        result = _parse(native_pdf)
        # El formato detectado por el analyzer puede ser None o un string
        assert result.formato_codigo_detectado is None or isinstance(
            result.formato_codigo_detectado, str
        )

    def test_deteccion_tabla(self, native_pdf):
        result = _parse(native_pdf)
        td = result.deteccion_tabla
        assert "has_tables" in td
        assert "table_count" in td
        assert "confidence" in td

    def test_to_dict_includes_both(self, native_pdf):
        result = _parse(native_pdf)
        d = result.to_dict()
        assert "archivo" in d
        assert "formato_codigo" in d
        assert "total_cuentas" in d
        assert "analysis" in d
        assert "file" in d["analysis"]
        assert "orientation" in d["analysis"]

    def test_to_dict_flat(self, native_pdf):
        result = _parse(native_pdf)
        d = result.to_dict_flat()
        assert "archivo" in d
        assert "tipo_documento" in d
        assert "necesita_ocr" in d
        assert "orientacion_detectada" in d
        assert "confianza_global" in d
        assert "layout_confianza" in d
        assert "analysis_time_ms" in d


class TestParseWithAnalysis:
    """parse_with_analysis orquesta analyzer + parser correctamente."""

    def test_returns_enhanced_result(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        assert isinstance(result, EnhancedParseResult)

    def test_parseo_no_rompe(self, native_pdf):
        """El parseo produce las mismas cuentas que sin analyzer."""
        enhanced = parse_with_analysis(native_pdf)
        direct = ParserPDF().parsear(native_pdf)
        assert len(enhanced.cuentas) == len(direct.cuentas)

    def test_cuentas_extraidas(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        assert len(result.cuentas) > 0

    def test_warnings_se_agregan(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        # Las advertencias del analyzer deben estar en resultado.advertencias
        analysis_warnings = result.analysis.warnings
        for w in analysis_warnings:
            assert w in result.advertencias, f"Advertencia faltante: {w}"

    def test_sin_duplicar_warnings(self, native_pdf):
        """Las advertencias no deben duplicarse si parser y analyzer coinciden."""
        result = parse_with_analysis(native_pdf)
        assert len(result.advertencias) == len(set(result.advertencias))


class TestScannedPDF:
    """PDFs escaneados (sin texto nativo).

    Usamos DocumentAnalyzer directamente (sin ParserPDF) porque
    el parseo real activaría OCR, que es lento y no necesario
    para validar la metadata de análisis.
    """

    def test_detecta_sin_texto_nativo(self, scanned_pdf):
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(scanned_pdf)
        assert not analysis.text.has_native_text

    def test_detecta_needs_ocr(self, scanned_pdf):
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(scanned_pdf)
        assert analysis.needs_ocr

    def test_confianza_baja(self, scanned_pdf):
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(scanned_pdf)
        assert analysis.overall_confidence < 0.5

    def test_advertencia_ocr_se_agrega(self):
        """Verificar que _merge_warnings agrega advertencia de OCR."""
        from parser_universal import FormatoCodigo, ResultadoParseo
        from parsers.integration import _merge_warnings
        from parsers.analyzer import (
            CodeAnalysis, DocumentAnalysis, FileInfo,
            OrientationAnalysis, SeparatorAnalysis, TableAnalysis, TextAnalysis,
        )
        from parsers.layout_detector import DetectedLayout

        analysis = DocumentAnalysis()
        analysis.file = FileInfo(
            file_path="test.pdf", file_name="test.pdf", file_type="pdf",
            file_size_bytes=100, is_valid=True, validation_message="OK",
        )
        analysis.needs_ocr = True

        resultado = ResultadoParseo(
            archivo="test.pdf", formato_codigo=FormatoCodigo.SIN_CODIGO,
            separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
        )

        _merge_warnings(resultado, analysis)
        assert any("OCR" in w for w in resultado.advertencias)


class TestNativeTextPDF:
    """PDFs con texto nativo."""

    def test_detecta_texto_nativo(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        assert result.tiene_texto_nativo

    def test_no_requiere_ocr(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        assert not result.requirio_ocr


class TestTablePDF:
    """PDFs con tablas detectables."""

    def test_detecta_tablas(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        # El BALANCE 2016.pdf tiene tablas en varias páginas
        if result.tiene_tablas:
            assert result.deteccion_tabla["table_count"] > 0

    def test_tabla_metadata(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        td = result.deteccion_tabla
        assert isinstance(td["has_tables"], bool)
        assert isinstance(td["table_count"], int)
        assert 0.0 <= td["confidence"] <= 1.0


class TestNoCodePDF:
    """PDFs sin códigos numéricos de cuenta."""

    def test_detecta_sin_codigos(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        # El BALANCE 2016.pdf no tiene códigos numéricos detectables
        if not result.tiene_codigos:
            assert result.formato_codigo_detectado is None

    def test_advertencia_sin_codigos(self):
        """Verificar que la advertencia se genera cuando corresponde."""
        from parser_universal import FormatoCodigo, ParserPDF, ResultadoParseo
        from parsers.integration import _merge_warnings
        from parsers.analyzer import (
            CodeAnalysis,
            DocumentAnalysis,
            FileInfo,
            OrientationAnalysis,
            SeparatorAnalysis,
            TableAnalysis,
            TextAnalysis,
        )
        from parsers.layout_detector import DetectedLayout

        analysis = DocumentAnalysis()
        analysis.file = FileInfo(
            file_path="test.pdf", file_name="test.pdf", file_type="pdf",
            file_size_bytes=100, is_valid=True, validation_message="OK",
        )
        analysis.code = CodeAnalysis(
            has_codes=False, code_format=None, confidence=0.0,
        )

        resultado = ResultadoParseo(
            archivo="test.pdf", formato_codigo=FormatoCodigo.SIN_CODIGO,
            separador_miles=".", requirio_ocr=False, rotacion_aplicada=0,
        )

        _merge_warnings(resultado, analysis)

        assert any("Sin códigos" in w for w in resultado.advertencias)


class TestBackwardCompatibility:
    """El EnhancedParseResult debe ser usable como un ResultadoParseo normal."""

    def test_iterar_cuentas(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        for cuenta in result.cuentas:
            assert cuenta.nombre is not None
            assert len(cuenta.nombre) > 0

    def test_advertencias_accesibles(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        assert isinstance(result.advertencias, list)

    def test_acceso_a_campos_directos(self, native_pdf):
        result = parse_with_analysis(native_pdf)
        # Debe tener los mismos campos que un ResultadoParseo
        assert hasattr(result, "archivo")
        assert hasattr(result, "formato_codigo")
        assert hasattr(result, "cuentas")

    def test_puede_usarse_en_pipeline(self, native_pdf):
        """Verificar que se puede usar donde se espera un ResultadoParseo."""
        result = parse_with_analysis(native_pdf)
        # El pipeline itera sobre resultado.cuentas
        for cr in result.cuentas:
            assert hasattr(cr, "codigo")
            assert hasattr(cr, "nombre")
            assert hasattr(cr, "monto")


class TestCustomAnalyzer:
    """Se puede inyectar un analyzer o parser custom."""

    def test_custom_analyzer(self, native_pdf):
        custom_analyzer = DocumentAnalyzer()
        result = parse_with_analysis(native_pdf, analyzer=custom_analyzer)
        assert isinstance(result, EnhancedParseResult)

    def test_custom_parser(self, native_pdf):
        custom_parser = ParserPDF()
        result = parse_with_analysis(native_pdf, parser=custom_parser)
        assert isinstance(result, EnhancedParseResult)

    def test_both_custom(self, native_pdf):
        result = parse_with_analysis(
            native_pdf,
            analyzer=DocumentAnalyzer(),
            parser=ParserPDF(),
        )
        assert isinstance(result, EnhancedParseResult)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def native_pdf() -> Path:
    path = DATASETS["balance_2016"]
    if not path.exists():
        pytest.skip(f"PDF no encontrado: {path}")
    return path


@pytest.fixture
def scanned_pdf() -> Path:
    path = DATASETS["balance_dain"]
    if not path.exists():
        pytest.skip(f"PDF no encontrado: {path}")
    return path


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _parse(path: Path) -> EnhancedParseResult:
    return parse_with_analysis(path)
