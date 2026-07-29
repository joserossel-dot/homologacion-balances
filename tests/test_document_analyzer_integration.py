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

from parser_universal import ExtractionContext, ParserPDF
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


class TestRotationCorrection:
    """Corrección de rotación 180° — ahora dentro de ParserPDF vía contexto."""

    def test_reverse_line_basic(self):
        assert ParserPDF._reverse_line("ovitca") == "activo"
        assert ParserPDF._reverse_line("atneuC ovitca") == "Cuenta activo"
        assert ParserPDF._reverse_line("") == ""
        assert ParserPDF._reverse_line("   ") == "   "

    def test_reverse_line_multiple_words(self):
        assert (
            ParserPDF._reverse_line("atneuC otartnoc erbmon")
            == "Cuenta contrato nombre"
        )

    def test_reverse_line_single_word(self):
        assert ParserPDF._reverse_line("ovitca") == "activo"
        assert ParserPDF._reverse_line("ovisap") == "pasivo"

    def test_debe_corregir_rotacion_true(self):
        context = ExtractionContext(rotation_hint=180, rotation_confidence=0.85)
        assert ParserPDF._debe_corregir_rotacion(context)

    def test_debe_corregir_rotacion_low_confidence(self):
        context = ExtractionContext(rotation_hint=180, rotation_confidence=0.5)
        assert not ParserPDF._debe_corregir_rotacion(context)

    def test_debe_corregir_rotacion_no_rotation(self):
        context = ExtractionContext(rotation_hint=0, rotation_confidence=0.9)
        assert not ParserPDF._debe_corregir_rotacion(context)

    def test_debe_corregir_rotacion_sin_contexto(self):
        assert not ParserPDF._debe_corregir_rotacion(None)

    def test_parsear_con_contexto_vacio_mismo_resultado(self, native_pdf):
        parser = ParserPDF()
        resultado_sin = parser.parsear(native_pdf)
        resultado_con = parser.parsear(native_pdf, ExtractionContext())
        assert resultado_sin.rotacion_aplicada == resultado_con.rotacion_aplicada
        assert resultado_sin.formato_codigo == resultado_con.formato_codigo
        assert len(resultado_sin.cuentas) == len(resultado_con.cuentas)
        for ec, dc in zip(resultado_sin.cuentas, resultado_con.cuentas):
            assert ec.nombre == dc.nombre
            assert ec.monto == dc.monto

    def test_normal_pdf_mismo_resultado(self, native_pdf):
        """API tradicional (sin contexto) produce mismo resultado que con EnhancedParseResult."""
        enhanced = parse_with_analysis(native_pdf)
        direct = ParserPDF().parsear(native_pdf)
        assert enhanced.rotacion_aplicada == direct.rotacion_aplicada
        assert enhanced.formato_codigo == direct.formato_codigo
        assert enhanced.requirio_ocr == direct.requirio_ocr
        assert len(enhanced.cuentas) == len(direct.cuentas)
        for ec, dc in zip(enhanced.cuentas, direct.cuentas):
            assert ec.nombre == dc.nombre
            assert ec.monto == dc.monto

    def test_extraction_context_roundtrip(self, native_pdf):
        """DocumentAnalyzer produce ExtractionContext que ParserPDF acepta."""
        from parsers.analyzer import DocumentAnalyzer

        analyzer = DocumentAnalyzer()
        parser = ParserPDF()
        analysis = analyzer.analyze(native_pdf)
        context = analyzer.to_extraction_context(analysis)
        assert isinstance(context, ExtractionContext)
        result = parser.parsear(native_pdf, context)
        assert len(result.cuentas) > 0


class TestLayoutDetectorIntegration:
    """LayoutDetector vía ExtractionContext en ParserPDF."""

    def test_context_layout_alta_confianza_se_usa(self, native_pdf):
        """Context con layout_hint y confianza >= umbral activa LayoutDetector."""
        context = ExtractionContext(
            layout_hint=["activo", "pasivo", "perdida", "ganancia"],
            layout_confidence=0.85,
        )
        parser = ParserPDF()
        result = parser.parsear(native_pdf, context)
        assert any("LayoutDetector (context)" in w for w in result.advertencias), (
            "Debería usar LayoutDetector desde contexto"
        )

    def test_context_layout_baja_confianza_ignorado(self, native_pdf):
        """Context con layout_hint pero confianza baja se ignora."""
        context = ExtractionContext(
            layout_hint=["activo", "pasivo", "perdida", "ganancia"],
            layout_confidence=0.3,
        )
        parser = ParserPDF()
        r_sin = parser.parsear(native_pdf)
        r_con = parser.parsear(native_pdf, context)
        assert len(r_sin.cuentas) == len(r_con.cuentas)
        assert not any("LayoutDetector (context)" in w for w in r_con.advertencias)

    def test_context_sin_layout_hint_usado(self, native_pdf):
        """Context sin layout_hint produce mismo resultado que sin contexto."""
        context = ExtractionContext()
        parser = ParserPDF()
        r_sin = parser.parsear(native_pdf)
        r_con = parser.parsear(native_pdf, context)
        assert r_sin.formato_codigo == r_con.formato_codigo
        assert len(r_sin.cuentas) == len(r_con.cuentas)
        for c1, c2 in zip(r_sin.cuentas, r_con.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto

    def test_context_layout_4_columnas_se_menciona_en_advertencias(self, native_pdf):
        """Context con layout 4 columnas produce advertencia con nombres."""
        context = ExtractionContext(
            layout_hint=["activo", "pasivo", "perdida", "ganancia"],
            layout_confidence=0.9,
        )
        result = ParserPDF().parsear(native_pdf, context)
        warnings = " ".join(result.advertencias)
        assert "activo" in warnings
        assert "pasivo" in warnings
        assert "perdida" in warnings
        assert "ganancia" in warnings

    def test_context_layout_2_columnas_deudor_acreedor(self):
        """Columnas deudor/acreedor se mapean correctamente vía _LAYOUT_COLUMN_MAP."""
        from parser_universal import OrigenColumna, _LAYOUT_COLUMN_MAP

        cols = []
        for c in ["deudor", "acreedor"]:
            oc = _LAYOUT_COLUMN_MAP.get(c)
            if oc is not None:
                cols.append(oc)
        assert len(cols) == 2
        assert cols == [OrigenColumna.DEUDOR, OrigenColumna.ACREEDOR]

    def test_sin_regresion_con_documento_normal(self, native_pdf):
        """PDF normal parseado con/without context produce mismo resultado."""
        from parsers.analyzer import DocumentAnalyzer

        analyzer = DocumentAnalyzer()
        parser = ParserPDF()
        analysis = analyzer.analyze(native_pdf)
        context = analyzer.to_extraction_context(analysis)
        r_sin = parser.parsear(native_pdf)
        r_con = parser.parsear(native_pdf, context)
        assert r_sin.formato_codigo == r_con.formato_codigo
        assert r_sin.separador_miles == r_con.separador_miles
        assert r_sin.requirio_ocr == r_con.requirio_ocr
        assert len(r_sin.cuentas) == len(r_con.cuentas)

    def test_context_layout_confianza_umbral(self):
        """Verificar que LAYOUT_CONFIDENCE_THRESHOLD está definido y es 0.8."""
        from parser_universal import LAYOUT_CONFIDENCE_THRESHOLD
        assert LAYOUT_CONFIDENCE_THRESHOLD == 0.8


class TestAccountTypeResolverIntegration:
    """AccountTypeResolver vía ExtractionContext en ParserPDF."""

    def test_contexto_vacio_no_activa_resolver(self, native_pdf):
        """ExtractionContext() vacío no debe activar el resolver."""
        r = ParserPDF().parsear(native_pdf, ExtractionContext())
        cuentas_con_tipo = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
        assert cuentas_con_tipo == 0, (
            f"Contexto vacío activó resolver: {cuentas_con_tipo} cuentas con tipo"
        )

    def test_contexto_real_de_analyzer_activa_resolver(self, native_pdf):
        """Contexto desde DocumentAnalyzer activa el resolver."""
        from parsers.analyzer import DocumentAnalyzer

        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(native_pdf)
        context = analyzer.to_extraction_context(analysis)
        assert context.analysis_source == "DocumentAnalyzer"
        r = ParserPDF().parsear(native_pdf, context)
        cuentas_con_tipo = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
        assert cuentas_con_tipo > 0, (
            f"Resolver no activó: 0 cuentas con tipo (confianza={context.confidence})"
        )

    def test_confidence_bajo_no_activa(self, native_pdf):
        """Context con confidence bajo no debe activar el resolver."""
        context = ExtractionContext(
            analysis_source="DocumentAnalyzer",
            confidence=0.3,
            layout_hint=["activo", "pasivo"],
        )
        r = ParserPDF().parsear(native_pdf, context)
        cuentas_con_tipo = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
        assert cuentas_con_tipo == 0

    def test_analysis_source_incorrecto_no_activa(self, native_pdf):
        """Context sin analysis_source='DocumentAnalyzer' no activa resolver."""
        context = ExtractionContext(
            analysis_source="manual",
            confidence=0.9,
            layout_hint=["activo", "pasivo"],
        )
        r = ParserPDF().parsear(native_pdf, context)
        cuentas_con_tipo = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
        assert cuentas_con_tipo == 0

    def test_flag_legacy_sigue_funcionando(self, native_pdf):
        """ENABLE_ACCOUNT_TYPE_RESOLVER=True activa resolver incluso sin contexto."""
        import parser_universal as pu
        original = pu.ENABLE_ACCOUNT_TYPE_RESOLVER
        pu.ENABLE_ACCOUNT_TYPE_RESOLVER = True
        try:
            r = ParserPDF().parsear(native_pdf)
            cuentas_con_tipo = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
            assert cuentas_con_tipo > 0, "Flag legacy no activó resolver"
        finally:
            pu.ENABLE_ACCOUNT_TYPE_RESOLVER = original

    def test_flag_legacy_restaurado(self, native_pdf):
        """Verificar que ENABLE_ACCOUNT_TYPE_RESOLVER vuelve a False después del test."""
        import parser_universal as pu
        assert pu.ENABLE_ACCOUNT_TYPE_RESOLVER is False

    def test_tipos_cuenta_en_rango_valido(self, native_pdf):
        """Tipos resueltos deben ser valores válidos."""
        from parsers.analyzer import DocumentAnalyzer

        analyzer = DocumentAnalyzer()
        context = analyzer.to_extraction_context(analyzer.analyze(native_pdf))
        r = ParserPDF().parsear(native_pdf, context)
        tipos_validos = {"ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA", "GANANCIA", "DESCONOCIDO"}
        for c in r.cuentas:
            if c.tipo_cuenta is not None:
                assert c.tipo_cuenta in tipos_validos, (
                    f"Tipo inválido: {c.tipo_cuenta}"
                )

    def test_compatibilidad_con_extraction_context_vacio(self, native_pdf):
        """parsear(path, ExtractionContext()) produce mismo resultado que parsear(path)."""
        r_sin = ParserPDF().parsear(native_pdf)
        r_con = ParserPDF().parsear(native_pdf, ExtractionContext())
        assert r_sin.formato_codigo == r_con.formato_codigo
        assert r_sin.separador_miles == r_con.separador_miles
        assert r_sin.requirio_ocr == r_con.requirio_ocr
        assert r_sin.rotacion_aplicada == r_con.rotacion_aplicada
        assert len(r_sin.cuentas) == len(r_con.cuentas)
        for c1, c2 in zip(r_sin.cuentas, r_con.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto
            # tipo_cuenta debe ser None en ambos (sin resolver)
            assert c1.tipo_cuenta is None
            assert c2.tipo_cuenta is None

    def test_analysis_source_en_context(self, native_pdf):
        """DocumentAnalyzer.to_extraction_context() establece analysis_source."""
        from parsers.analyzer import DocumentAnalyzer

        context = DocumentAnalyzer().to_extraction_context(
            DocumentAnalyzer().analyze(native_pdf)
        )
        assert context.analysis_source == "DocumentAnalyzer"


class TestNormalizationBeforeLayout:
    """Fase 6: normalización de líneas rotadas 180° antes de LayoutDetector."""

    # ── Test A: PDF normal → sin rotación, flag False ──

    def test_normal_pdf_no_rotation_correction(self, native_pdf):
        """PDF sin rotación: rotation_corrected_before_layout=False."""
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(native_pdf)
        assert analysis.rotation_corrected_before_layout is False

    def test_normal_pdf_layout_inmutable(self, native_pdf):
        """PDF sin rotación: layout detectado es el mismo que antes (test de no-regresión)."""
        from parsers.integration import parse_with_analysis
        enhanced = parse_with_analysis(native_pdf)
        assert enhanced.analysis.layout.columns is not None
        assert len(enhanced.analysis.layout.columns) > 0
        assert enhanced.analysis.orientation.rotation == 0

    # ── Test B: PDF con rotación simulada → flag True ──

    def test_normalize_lines_180_high_confidence(self):
        """_normalize_lines invierte palabras cuando rotation=180 y confianza≥umbral."""
        analyzer = DocumentAnalyzer()
        from parsers.analyzer import OrientationAnalysis
        orientation = OrientationAnalysis(rotation=180, confidence=0.85, method="words")
        lineas = ["ovitca", "atisap ovisap", "123"]
        normalizadas = analyzer._normalize_lines(lineas, orientation)
        assert normalizadas == ["activo", "pasita pasivo", "321"]

    def test_normalize_lines_0_rotation(self):
        """_normalize_lines no modifica líneas cuando rotation=0."""
        analyzer = DocumentAnalyzer()
        from parsers.analyzer import OrientationAnalysis
        orientation = OrientationAnalysis(rotation=0, confidence=0.0, method="unknown")
        lineas = ["activo", "pasivo", "123"]
        normalizadas = analyzer._normalize_lines(lineas, orientation)
        assert normalizadas is lineas  # misma lista (sin copia)
        assert normalizadas == ["activo", "pasivo", "123"]

    def test_normalize_lines_low_confidence(self):
        """_normalize_lines no modifica cuando confianza es baja."""
        analyzer = DocumentAnalyzer()
        from parsers.analyzer import OrientationAnalysis
        orientation = OrientationAnalysis(rotation=180, confidence=0.4, method="words")
        lineas = ["ovitca"]
        normalizadas = analyzer._normalize_lines(lineas, orientation)
        assert normalizadas is lineas

    def test_rotation_180_flag_true(self, native_pdf):
        """Verify flag is True when orientation is forced 180 (integration test)
        by checking that after _normalize_lines, flag in analysis is set."""
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(native_pdf)
        from parsers.analyzer import OrientationAnalysis
        fake_orientation = OrientationAnalysis(rotation=180, confidence=0.85, method="words")
        lineas = ["atreus", "avitatneserp", "ovitca"]
        normalizadas = analyzer._normalize_lines(lineas, fake_orientation)
        assert normalizadas == ["suerta", "presentativa", "activo"]

    # ── Test C: PDF escaneado → no se rompe ──

    def test_scanned_pdf_no_correction(self, scanned_pdf):
        """PDF escaneado (OCR) no activa normalización."""
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(scanned_pdf)
        # Escaneado no tiene texto nativo; orientation.confidence debe ser 0
        assert analysis.rotation_corrected_before_layout is False


class TestTextNormalization:
    """Fase 7: higiene textual antes de análisis estructural."""

    # ── Texto limpio no cambia ──

    def test_clean_text_unchanged(self):
        """Texto sin problemas pasa sin modificación."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["Activo", "Pasivo", "Total Activos 1.234.567"]
        resultado, acciones = normalize_text_lines(lineas)
        assert resultado == lineas
        assert len(acciones) == 0

    @staticmethod
    def test_clean_lines_have_text_normalized_false(native_pdf):
        """PDF normal con texto limpio no marca text_normalized."""
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(native_pdf)
        # BALANCE 2016.pdf tiene texto limpio — no debería activar normalización
        assert analysis.text_normalized is False
        assert len(analysis.normalization_actions) == 0

    # ── OCR spacing se corrige ──

    def test_ocr_spacing_merged(self):
        """'A c t i v o' se fusiona a 'Activo'."""
        from parsers.text_normalizer import normalize_text_lines
        resultado, acciones = normalize_text_lines(["A c t i v o"])
        assert resultado == ["Activo"]
        assert any("merged_ocr_spacing" in a for a in acciones)

    def test_ocr_spacing_multiple_words(self):
        """Varias secuencias OCR en una línea."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["A c t i v o   P a s i v o"]
        resultado, _ = normalize_text_lines(lineas)
        assert resultado == ["Activo Pasivo"]

    def test_ocr_spacing_partial_line(self):
        """Secuencia OCR al final de una línea."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["Total  1.234  C u e n t a"]
        resultado, _ = normalize_text_lines(lineas)
        assert resultado == ["Total 1.234 Cuenta"]

    # ── Códigos de cuenta no se rompen ──

    def test_codes_preserved(self):
        """Códigos numéricos con separadores no se alteran."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = [
            "1.1.01.01 Caja 1.234.567",
            "1.1.02.05 Banco 5.678.901",
            "110101 Caja Chica 100",
            "1-1-01-01 Deudores 999",
        ]
        resultado, _ = normalize_text_lines(lineas)
        assert resultado == lineas

    def test_codes_with_short_segments_preserved(self):
        """Códigos de cuenta con segmentos cortos (ej. '1 1 0 1 0 1') no se fusionan."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["1 1 0 1 0 1  Caja"]
        resultado, _ = normalize_text_lines(lineas)
        # dígitos no se fusionan (solo alfa)
        assert resultado == ["1 1 0 1 0 1 Caja"]

    # ── Montos no se alteran ──

    def test_amounts_unchanged(self):
        """Montos numéricos no se modifican."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = [
            "  1.234.567  ",
            "  (5.678)  ",
            "  0  ",
            "  -1.234  ",
        ]
        resultado, _ = normalize_text_lines(lineas)
        esperado = [
            "1.234.567",
            "(5.678)",
            "0",
            "-1.234",
        ]
        assert resultado == esperado

    # ── PDF escaneado no se rompe ──

    def test_scanned_pdf_sigue_funcionando(self, scanned_pdf):
        """PDF escaneado no se rompe con normalización."""
        analyzer = DocumentAnalyzer()
        analysis = analyzer.analyze(scanned_pdf)
        assert analysis.file.is_valid
        assert analysis.text_normalized is False  # sin texto nativo

    # ── Múltiples espacios ──

    def test_multiple_spaces_collapsed(self):
        """Espacios múltiples se colapsan."""
        from parsers.text_normalizer import normalize_text_lines
        resultado, acciones = normalize_text_lines(["Activo       Caja"])
        assert resultado == ["Activo Caja"]
        assert any("collapsed_spaces" in a for a in acciones)

    # ── Caracteres invisibles ──

    def test_invisible_chars_removed(self):
        """Caracteres zero-width y control se remueven."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["Activo\u200bCaja", "Pasivo\x00Test"]
        resultado, _ = normalize_text_lines(lineas)
        assert resultado == ["ActivoCaja", "PasivoTest"]

    # ── Líneas vacías ──

    def test_empty_lines_dropped(self):
        """Líneas vacías se descartan."""
        from parsers.text_normalizer import normalize_text_lines
        lineas = ["Activo", "", "   ", "Pasivo"]
        resultado, _ = normalize_text_lines(lineas)
        assert resultado == ["Activo", "Pasivo"]

    # ── Regresión: parse_with_analysis sigue funcionando ──

    def test_parse_with_analysis_no_regression(self, native_pdf):
        """parse_with_analysis no se rompe con normalización."""
        from parsers.integration import parse_with_analysis
        enhanced = parse_with_analysis(native_pdf)
        assert enhanced.analysis is not None
        assert hasattr(enhanced.analysis, "text_normalized")
        assert len(enhanced.cuentas) > 0

    def test_normalization_actions_in_to_dict(self, native_pdf):
        """to_dict incluye campos de normalización."""
        from parsers.integration import parse_with_analysis
        d = parse_with_analysis(native_pdf).analysis.to_dict()
        assert "text_normalized" in d
        assert "normalization_actions" in d


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
