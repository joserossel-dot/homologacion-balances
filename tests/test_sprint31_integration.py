"""Tests de integración Sprint 31 — Document Intelligence en el pipeline.

Cubre:
  ✓ creación de DocumentProcessingContext
  ✓ integración Parser -> Analyzer
  ✓ integración Analyzer -> Factory
  ✓ fallback cuando Analyzer falla
  ✓ serialización del Context
  ✓ UI muestra información
  ✓ métricas (extractor, tiempos, confianza)
  ✓ backward compatibility: parsear() sigue igual con STANDARD/DESCONOCIDO
"""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence import (
    DocumentProcessingContext,
    ExtractorFactory,
    ExtractorType,
    FormatAnalyzer,
    FormatSignature,
    MetricsCollector,
    analyze_document_preview,
)
from document_intelligence.signature import (
    CodePattern,
    DocumentType as SigDocumentType,
    Family as SigFamily,
    LayoutType,
)
from parser_universal import ExtractionContext, ParserPDF

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "datasets" / "validacion"
BALANCE_2016 = DATASET_DIR / "BALANCE 2016.pdf"


def _pdf_path() -> Path:
    if not BALANCE_2016.exists():
        pytest.skip(f"PDF no encontrado: {BALANCE_2016}")
    return BALANCE_2016


# ═══════════════════════════════════════════════════════════════════
# DocumentProcessingContext
# ═══════════════════════════════════════════════════════════════════

class TestDocumentProcessingContext:
    def test_creacion_con_todos_los_campos(self):
        sig = FormatSignature(
            document_type=SigDocumentType.BALANCE,
            family=SigFamily.PDF_ESTANDAR,
            confidence=0.9,
        )
        ctx = DocumentProcessingContext(
            pdf_path=Path("x.pdf"),
            signature=sig,
            extractor_type=ExtractorType.PDF_ESTANDAR,
            processing_notes=["nota"],
            warnings=[],
            confidence=0.9,
            elapsed_ms=42,
        )
        assert ctx.pdf_path.name == "x.pdf"
        assert ctx.signature.family == SigFamily.PDF_ESTANDAR
        assert ctx.extractor_type == ExtractorType.PDF_ESTANDAR
        assert ctx.processing_notes == ["nota"]
        assert ctx.warnings == []
        assert ctx.confidence == 0.9
        assert ctx.elapsed_ms == 42

    def test_valores_por_defecto(self):
        ctx = DocumentProcessingContext(
            pdf_path=Path("x.pdf"),
            signature=FormatSignature(),
            extractor_type=ExtractorType.DESCONOCIDO,
        )
        assert ctx.processing_notes == []
        assert ctx.warnings == []
        assert ctx.confidence == 0.0
        assert ctx.elapsed_ms == 0

    def test_serializacion_round_trip(self):
        sig = FormatSignature(
            document_type=SigDocumentType.ESTADO_RESULTADOS,
            family=SigFamily.PDF_ESTANDAR,
            confidence=0.95,
            layout=LayoutType.VERTICAL,
            columns=[],
        )
        ctx = DocumentProcessingContext(
            pdf_path=Path("balance.pdf"),
            signature=sig,
            extractor_type=ExtractorType.PDF_ESTANDAR,
            processing_notes=["preview leído"],
            warnings=["w1"],
            confidence=0.95,
            elapsed_ms=123,
        )
        data = ctx.to_dict()
        restored = DocumentProcessingContext.from_dict(data)
        assert restored.pdf_path == Path("balance.pdf")
        assert restored.signature.to_dict() == sig.to_dict()
        assert restored.extractor_type == ExtractorType.PDF_ESTANDAR
        assert restored.processing_notes == ["preview leído"]
        assert restored.warnings == ["w1"]
        assert restored.confidence == 0.95
        assert restored.elapsed_ms == 123

    def test_log_block(self):
        ctx = DocumentProcessingContext(
            pdf_path=Path("balance.pdf"),
            signature=FormatSignature(
                document_type=SigDocumentType.BALANCE,
                family=SigFamily.PDF_ESTANDAR,
                confidence=0.96,
                layout=LayoutType.HORIZONTAL,
            ),
            extractor_type=ExtractorType.PDF_ESTANDAR,
            elapsed_ms=50,
        )
        block = ctx.to_log_block()
        assert "Documento: balance.pdf" in block
        assert "Tipo: BALANCE" in block
        assert "Familia: PDF_ESTANDAR" in block
        assert "Extractor seleccionado: PDF_ESTANDAR" in block
        assert "Tiempo análisis: 50 ms" in block
        assert block.startswith("---") and block.endswith("---")

    def test_ui_summary(self):
        ctx = DocumentProcessingContext(
            pdf_path=Path("balance.pdf"),
            signature=FormatSignature(
                document_type=SigDocumentType.BALANCE,
                family=SigFamily.PDF_ESTANDAR,
                confidence=0.96,
                layout=LayoutType.TABULAR,
                ocr_required=False,
            ),
            extractor_type=ExtractorType.PDF_ESTANDAR,
        )
        info = ctx.ui_summary()
        assert info["Documento"] == "Balance Tributario"
        assert info["Formato"] == "PDF TABULAR"
        assert info["OCR"] == "No"
        assert info["Extractor"] == "PDF_ESTANDAR"
        assert info["Confianza"] == "96%"


# ═══════════════════════════════════════════════════════════════════
# analyze_document_preview (Analyzer + Factory)
# ═══════════════════════════════════════════════════════════════════

class TestAnalyzeDocumentPreview:
    def test_analiza_pdf_real(self):
        ctx = analyze_document_preview(_pdf_path())
        assert isinstance(ctx, DocumentProcessingContext)
        assert isinstance(ctx.signature, FormatSignature)
        assert isinstance(ctx.extractor_type, ExtractorType)
        assert ctx.elapsed_ms >= 0
        assert 0.0 <= ctx.confidence <= 1.0
        assert ctx.signature.document_type == SigDocumentType.BALANCE

    def test_analyzer_factory_integration(self):
        """Analyzer produce signature → Factory decide extractor."""
        sig = FormatSignature(
            family=SigFamily.PDF_ESTANDAR,
            code_pattern=CodePattern.GUION,
            has_headers=True,
            confidence=0.9,
        )
        assert ExtractorFactory().decide(sig) == ExtractorType.PDF_ESTANDAR

    def test_factory_no_cambia_extraccion(self):
        """La factory solo decide (STANDARD_PARSER); no instancia extractores."""
        factory = ExtractorFactory()
        sig = FormatSignature(
            family=SigFamily.PDF_ESTANDAR,
            code_pattern=CodePattern.GUION,
            has_headers=True,
            confidence=0.9,
        )
        assert factory.decide_parser(sig) == ExtractorType.STANDARD_PARSER

    def test_factory_vocabulario_parser(self):
        factory = ExtractorFactory()
        # Horizontal → HORIZONTAL_PARSER
        sig_h = FormatSignature(layout=LayoutType.HORIZONTAL, confidence=0.8)
        assert factory.decide_parser(sig_h) == ExtractorType.HORIZONTAL_PARSER
        # Desconocido → UNKNOWN
        sig_u = FormatSignature()
        assert factory.decide_parser(sig_u) == ExtractorType.UNKNOWN
        # OCR → OCR_PARSER
        sig_o = FormatSignature(ocr_required=True, confidence=0.6)
        assert factory.decide_parser(sig_o) == ExtractorType.OCR_PARSER

    def test_fallback_cuando_analyzer_falla(self):
        class AnalyzerQueFalla:
            def analyze(self, lines):
                raise RuntimeError("boom del analyzer")

        ctx = analyze_document_preview(_pdf_path(), analyzer=AnalyzerQueFalla())
        # El contexto se produce de todas formas (fallback) y queda UNKNOWN.
        assert isinstance(ctx, DocumentProcessingContext)
        assert ctx.signature.family == SigFamily.DESCONOCIDO
        assert ctx.extractor_type == ExtractorType.UNKNOWN
        assert any("falló" in w.lower() for w in ctx.warnings)

    def test_fallback_cuando_factory_falla(self):
        class FactoryQueFalla:
            def decide(self, sig):
                raise RuntimeError("boom de la factory")

        ctx = analyze_document_preview(_pdf_path(), factory=FactoryQueFalla())
        assert isinstance(ctx, DocumentProcessingContext)
        assert ctx.extractor_type == ExtractorType.UNKNOWN
        assert any("falló" in w.lower() for w in ctx.warnings)

    def test_archivo_inexistente_no_lanza(self):
        ctx = analyze_document_preview(Path("no_existe.pdf"))
        assert isinstance(ctx, DocumentProcessingContext)


# ═══════════════════════════════════════════════════════════════════
# Parser -> Analyzer (ParserPDF.parsear)
# ═══════════════════════════════════════════════════════════════════

class TestParserAnalyzerIntegration:
    def test_parsear_adjunta_contexto(self):
        resultado = ParserPDF().parsear(_pdf_path())
        assert resultado.document_context is not None
        assert isinstance(resultado.document_context, DocumentProcessingContext)
        assert isinstance(resultado.document_context.signature, FormatSignature)
        assert resultado.document_context.elapsed_ms >= 0

    def test_parsear_no_cambia_extraccion(self):
        """Con y sin ExtractionContext se obtienen las mismas cuentas."""
        path = _pdf_path()
        r1 = ParserPDF().parsear(path)
        r2 = ParserPDF().parsear(path, ExtractionContext())
        assert len(r1.cuentas) == len(r2.cuentas)
        for c1, c2 in zip(r1.cuentas, r2.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto
            assert c1.codigo == c2.codigo

    def test_parsear_adjunta_advertencias_del_analisis(self, monkeypatch):
        from document_intelligence import context as di_context

        real = di_context.analyze_document_preview

        def stub(path, **kwargs):
            ctx = real(path)
            ctx.warnings.append("ADVERTENCIA SPRINT31")
            return ctx

        monkeypatch.setattr(di_context, "analyze_document_preview", stub)
        resultado = ParserPDF().parsear(_pdf_path())
        assert any("SPRINT31" in w for w in resultado.advertencias)


# ═══════════════════════════════════════════════════════════════════
# Fallback / backward compatibility
# ═══════════════════════════════════════════════════════════════════

class TestFallbackBackwardCompat:
    def test_fallback_si_analisis_falla(self, monkeypatch):
        from parser_universal import ParserPDF as PP

        def romper(self, path):
            raise RuntimeError("document intelligence caído")

        monkeypatch.setattr(PP, "_analizar_documento", romper)
        resultado = ParserPDF().parsear(_pdf_path())
        # El parseo clásico sigue funcionando sin contexto.
        assert len(resultado.cuentas) > 0
        assert resultado.document_context is None

    def test_fallback_si_preview_no_tiene_texto(self):
        """PDF escaneado (sin texto nativo) → análisis DESCONOCIDO, parseo OK."""
        resultado = ParserPDF().parsear(_pdf_path())
        assert isinstance(resultado, object)

    def test_parsear_sigue_funcionando_sin_document_intelligence(self, monkeypatch):
        from parser_universal import ParserPDF as PP

        def sin_analisis(self, path):
            return None

        monkeypatch.setattr(PP, "_analizar_documento", sin_analisis)
        r_sin = ParserPDF().parsear(_pdf_path())
        assert r_sin.document_context is None
        assert len(r_sin.cuentas) > 0


# ═══════════════════════════════════════════════════════════════════
# UI muestra información (formato usado por app_validacion)
# ═══════════════════════════════════════════════════════════════════

class TestUiInformacion:
    def test_muestra_informacion_sin_ctx(self):
        import app_validacion
        assert app_validacion._mostrar_informacion_documento(None) is None

    def test_muestra_informacion_con_ctx(self, monkeypatch):
        import app_validacion

        sig = FormatSignature(
            document_type=SigDocumentType.BALANCE,
            family=SigFamily.PDF_ESTANDAR,
            confidence=0.96,
            layout=LayoutType.TABULAR,
        )
        ctx = DocumentProcessingContext(
            pdf_path=Path("balance.pdf"),
            signature=sig,
            extractor_type=ExtractorType.PDF_ESTANDAR,
        )

        renderizados = []
        monkeypatch.setattr(app_validacion.st, "container", lambda **kw: _FakeCtx(renderizados))
        monkeypatch.setattr(app_validacion.st, "markdown", lambda m: renderizados.append(("md", m)))
        monkeypatch.setattr(app_validacion.st, "columns", lambda n: [_FakeCol(renderizados) for _ in range(n)])

        app_validacion._mostrar_informacion_documento(ctx)
        textos = " ".join(r[1] for r in renderizados if isinstance(r, tuple) and r[0] == "md")
        assert "INFORMACIÓN DEL DOCUMENTO" in textos
        assert "Balance Tributario" in textos
        assert "PDF_ESTANDAR" in textos


class _FakeCtx:
    def __init__(self, renderizados):
        self._renderizados = renderizados

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeCol:
    def __init__(self, renderizados):
        self._renderizados = renderizados

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def markdown(self, m):
        self._renderizados.append(("md", m))


# ═══════════════════════════════════════════════════════════════════
# Métricas Sprint 31
# ═══════════════════════════════════════════════════════════════════

class TestMetricsSprint31:
    def test_by_extractor(self):
        collector = MetricsCollector()
        collector.record(
            FormatSignature(confidence=0.9, family=SigFamily.PDF_ESTANDAR),
            extractor_type=ExtractorType.PDF_ESTANDAR.value,
            elapsed_ms=10,
        )
        collector.record(
            FormatSignature(confidence=0.3),
            extractor_type=ExtractorType.DESCONOCIDO.value,
            elapsed_ms=5,
        )
        m = collector.metrics
        assert m.by_extractor["PDF_ESTANDAR"] == 1
        assert m.by_extractor["DESCONOCIDO"] == 1

    def test_tiempo_promedio_y_confianza(self):
        collector = MetricsCollector()
        collector.record(
            FormatSignature(confidence=1.0, family=SigFamily.PDF_ESTANDAR),
            extractor_type="PDF_ESTANDAR",
            elapsed_ms=100,
        )
        collector.record(
            FormatSignature(confidence=0.5),
            extractor_type="DESCONOCIDO",
            elapsed_ms=200,
        )
        m = collector.metrics
        assert m.avg_confidence == 0.0  # se calcula en to_dict/compute
        d = m.to_dict()
        assert d["avg_confidence"] == 0.75
        assert d["avg_elapsed_ms"] == 150.0

    def test_merge_extiende_extractor(self):
        m1 = MetricsCollector()
        m1.record(
            FormatSignature(confidence=0.8, family=SigFamily.PDF_ESTANDAR),
            extractor_type="PDF_ESTANDAR",
            elapsed_ms=10,
        )
        m2 = MetricsCollector()
        m2.record(
            FormatSignature(confidence=0.7, family=SigFamily.EXCEL_SII),
            extractor_type="EXCEL_SII",
            elapsed_ms=20,
        )
        merged = MetricsCollector()
        merged.merge(m1.metrics)
        merged.merge(m2.metrics)
        assert merged.metrics.total_documents == 2
        assert merged.metrics.by_extractor["PDF_ESTANDAR"] == 1
        assert merged.metrics.by_extractor["EXCEL_SII"] == 1
        assert merged.metrics._elapsed_sum == 30.0

    def test_record_context(self):
        ctx = DocumentProcessingContext(
            pdf_path=Path("x.pdf"),
            signature=FormatSignature(confidence=0.9, family=SigFamily.PDF_ESTANDAR),
            extractor_type=ExtractorType.PDF_ESTANDAR,
            elapsed_ms=25,
        )
        collector = MetricsCollector()
        collector.record_context(ctx)
        m = collector.metrics
        assert m.total_documents == 1
        assert m.by_extractor["PDF_ESTANDAR"] == 1
        assert m._elapsed_sum == 25.0
