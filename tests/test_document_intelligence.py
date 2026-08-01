from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from document_intelligence.detector import (
    CodePatternDetector,
    ColumnDetector,
    DocumentTypeDetector,
    HeaderDetector,
    LayoutDetector,
    NumericPatternDetector,
)
from document_intelligence.signature import (
    CodePattern,
    ColumnType,
    DocumentType,
    Family as SigFamily,
    FormatSignature,
    LayoutType,
    NumericPattern,
)
from document_intelligence.analyzer import FormatAnalyzer
from document_intelligence.repository import FormatRepository
from document_intelligence.factory import ExtractorFactory, ExtractorType
from document_intelligence.metrics import DetectionMetrics, MetricsCollector


# =============================================================================
# FIXTURES — documentos de prueba representativos
# =============================================================================

BALANCE_ESTANDAR_SII = [
    "RUT: 76.123.456-7",
    "Razón Social: Empresa Ejemplo S.A.",
    "Período: 01/01/2024 al 31/12/2024",
    "",
    "Código    Cuenta                       Monto",
    "1-01-01   Caja                         $1.500.000",
    "1-01-02   Bancos                       $5.200.000",
    "1-02-01   Clientes                     $3.100.000",
    "Total Activo Corriente                 $9.800.000",
    "2-01-01   Proveedores                  $2.100.000",
    "2-01-02   Obligaciones Bancarias       $4.000.000",
    "Total Pasivo Corriente                 $6.100.000",
    "3-01-01   Capital                      $3.700.000",
]

BALANCE_HORIZONTAL = [
    "EMPRESA DE PRUEBA LTDA.",
    "RUT 99.888.777-6",
    "Balance General al 31-12-2024",
    "",
    "ACTIVO                         PASIVO",
    "Caja              1.500.000    Proveedores       2.100.000",
    "Bancos            5.200.000    Obligaciones      4.000.000",
    "Clientes          3.100.000    Capital           3.700.000",
    "Total Activo      9.800.000    Total Pasivo      9.800.000",
]

EXCEL_LIBRE = [
    "Reporte de Cuentas",
    "",
    "Cuenta                Monto",
    "Caja                 1500000",
    "Bancos               5200000",
    "Clientes             3100000",
    "Proveedores          2100000",
]

ESTADO_RESULTADOS = [
    "Estado de Resultados",
    "Empresa Ejemplo S.A.",
    "Del 01-01-2024 al 31-12-2024",
    "",
    "Ingresos por Ventas     50.000.000",
    "Costo de Ventas        -30.000.000",
    "Margen Bruto            20.000.000",
    "Gastos Administrativos  -8.000.000",
    "Gastos Ventas          -5.000.000",
    "Resultado Operacional    7.000.000",
    "Total Gasto            -13.000.000",
    "Ganancia del Ejercicio   7.000.000",
]

SIN_ENCA_BEZAMIENTO = [
    "Caja 1500000",
    "Bancos 5200000",
    "Clientes 3100000",
    "Proveedores 2100000",
    "Capital 3700000",
]


# =============================================================================
# HEADER DETECTOR
# =============================================================================

class TestHeaderDetector:
    def test_detect_headers_sii(self):
        det = HeaderDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert result["has_headers"] is True
        assert result["confidence"] >= 0.70
        assert result["company_name"] != ""

    def test_detect_headers_horizontal(self):
        det = HeaderDetector()
        result = det.detect(BALANCE_HORIZONTAL)
        assert result["has_headers"] is True
        assert result["company_name"] != ""

    def test_detect_no_headers(self):
        det = HeaderDetector()
        result = det.detect(SIN_ENCA_BEZAMIENTO)
        assert result["has_headers"] is False

    def test_empty_lines(self):
        det = HeaderDetector()
        result = det.detect([])
        assert result["has_headers"] is False

    def test_rut_pattern(self):
        det = HeaderDetector()
        assert det.RUT_PATTERN.search("76.123.456-7") is not None
        assert det.RUT_PATTERN.search("12345678-9") is not None
        assert det.RUT_PATTERN.search("RUT 12.345.678-k") is not None


# =============================================================================
# LAYOUT DETECTOR
# =============================================================================

class TestLayoutDetector:
    def test_vertical_layout(self):
        det = LayoutDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert result["layout"] == LayoutType.VERTICAL

    def test_horizontal_layout(self):
        det = LayoutDetector()
        result = det.detect(BALANCE_HORIZONTAL)
        assert result["layout"] in (LayoutType.HORIZONTAL, LayoutType.TABULAR)

    def test_libre_layout(self):
        det = LayoutDetector()
        result = det.detect(SIN_ENCA_BEZAMIENTO)
        assert result["layout"] is not None

    def test_empty_lines(self):
        det = LayoutDetector()
        result = det.detect([])
        assert result["layout"] == LayoutType.DESCONOCIDO


# =============================================================================
# COLUMN DETECTOR
# =============================================================================

class TestColumnDetector:
    def test_standard_columns(self):
        det = ColumnDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert ColumnType.CODIGO in result["columns"]
        assert ColumnType.NOMBRE in result["columns"]
        assert ColumnType.MONTO in result["columns"]

    def test_simple_columns(self):
        det = ColumnDetector()
        result = det.detect(SIN_ENCA_BEZAMIENTO)
        assert len(result["columns"]) >= 1

    def test_empty_lines(self):
        det = ColumnDetector()
        result = det.detect([])
        assert result["columns"] == []


# =============================================================================
# CODE PATTERN DETECTOR
# =============================================================================

class TestCodePatternDetector:
    def test_guion_pattern(self):
        det = CodePatternDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert result["code_pattern"] == CodePattern.GUION
        assert result["confidence"] > 0.5

    def test_punto_pattern(self):
        det = CodePatternDetector()
        result = det.detect(BALANCE_HORIZONTAL)
        assert result["code_pattern"] in (CodePattern.GUION, CodePattern.PUNTO)

    def test_no_code(self):
        det = CodePatternDetector()
        result = det.detect(SIN_ENCA_BEZAMIENTO)
        assert result["code_pattern"] in (CodePattern.DESCONOCIDO, CodePattern.NUMERICO)

    def test_empty_lines(self):
        det = CodePatternDetector()
        result = det.detect([])
        assert result["code_pattern"] == CodePattern.DESCONOCIDO


# =============================================================================
# NUMERIC PATTERN DETECTOR
# =============================================================================

class TestNumericPatternDetector:
    def test_chilean_format(self):
        det = NumericPatternDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert result["numeric_pattern"] == NumericPattern.CHILENO

    def test_integer_format(self):
        det = NumericPatternDetector()
        result = det.detect(EXCEL_LIBRE)
        assert result["numeric_pattern"] is not None

    def test_empty_lines(self):
        det = NumericPatternDetector()
        result = det.detect([])
        assert result["numeric_pattern"] == NumericPattern.DESCONOCIDO


# =============================================================================
# DOCUMENT TYPE DETECTOR
# =============================================================================

class TestDocumentTypeDetector:
    def test_balance_type(self):
        det = DocumentTypeDetector()
        result = det.detect(BALANCE_ESTANDAR_SII)
        assert result["document_type"] == DocumentType.BALANCE
        assert result["confidence"] > 0.5

    def test_er_type(self):
        det = DocumentTypeDetector()
        result = det.detect(ESTADO_RESULTADOS)
        assert result["document_type"] == DocumentType.ESTADO_RESULTADOS

    def test_unknown_type(self):
        det = DocumentTypeDetector()
        result = det.detect(SIN_ENCA_BEZAMIENTO)
        assert result["document_type"] is not None

    def test_empty_lines(self):
        det = DocumentTypeDetector()
        result = det.detect([])
        assert result["document_type"] == DocumentType.OTRO


# =============================================================================
# FORMAT ANALYZER
# =============================================================================

class TestFormatAnalyzer:
    def test_analyze_balance_sii(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze(BALANCE_ESTANDAR_SII)
        assert sig.document_type == DocumentType.BALANCE
        assert sig.code_pattern == CodePattern.GUION
        assert sig.numeric_pattern == NumericPattern.CHILENO
        assert sig.has_headers is True
        assert sig.confidence > 0.0

    def test_analyze_horizontal(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze(BALANCE_HORIZONTAL)
        assert sig.document_type == DocumentType.BALANCE
        assert sig.layout in (LayoutType.HORIZONTAL, LayoutType.TABULAR)

    def test_analyze_er(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze(ESTADO_RESULTADOS)
        assert sig.document_type == DocumentType.ESTADO_RESULTADOS

    def test_analyze_empty(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze([])
        assert sig.document_type == DocumentType.OTRO
        assert sig.family.value == "DESCONOCIDO"
        assert sig.confidence == 0.0

    def test_analyze_text(self):
        analyzer = FormatAnalyzer()
        text = "\n".join(BALANCE_ESTANDAR_SII)
        sig = analyzer.analyze_text(text)
        assert sig.document_type == DocumentType.BALANCE

    def test_is_identified(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze(BALANCE_ESTANDAR_SII)
        assert sig.is_identified is True

    def test_not_identified_empty(self):
        analyzer = FormatAnalyzer()
        sig = analyzer.analyze([])
        assert sig.is_identified is False


# =============================================================================
# FORMAT SIGNATURE
# =============================================================================

class TestFormatSignature:
    def test_to_dict(self):
        sig = FormatSignature(
            document_type=DocumentType.BALANCE,
            family=SigFamily.PDF_ESTANDAR,
            confidence=0.85,
            layout=LayoutType.VERTICAL,
            code_pattern=CodePattern.GUION,
        )
        d = sig.to_dict()
        assert d["document_type"] == "BALANCE"
        assert d["family"] == "PDF_ESTANDAR"
        assert d["confidence"] == 0.85
        assert d["code_pattern"] == "GUION"

    def test_from_dict(self):
        d = {
            "document_type": "BALANCE",
            "family": "PDF_ESTANDAR",
            "confidence": 0.9,
            "layout": "VERTICAL",
            "orientation": "portrait",
            "columns": ["CODIGO", "NOMBRE", "MONTO"],
            "code_pattern": "GUION",
            "numeric_pattern": "CHILENO",
            "has_tables": True,
            "has_headers": True,
            "has_totals": True,
            "has_subtotals": False,
            "ocr_required": False,
            "company_name": "Empresa Test",
            "page_count": 2,
            "estimated_accounts": 50,
            "estimated_sections": 3,
        }
        sig = FormatSignature.from_dict(d)
        assert sig.document_type == DocumentType.BALANCE
        assert sig.family == SigFamily.PDF_ESTANDAR
        assert sig.confidence == 0.9
        assert len(sig.columns) == 3
        assert sig.company_name == "Empresa Test"

    def test_summary(self):
        sig = FormatSignature(
            document_type=DocumentType.BALANCE,
            family=SigFamily.CLASIFICADO,
            confidence=0.75,
            layout=LayoutType.HORIZONTAL,
        )
        summary = sig.summary()
        assert "BALANCE" in summary
        assert "CLASIFICADO" in summary
        assert "HORIZONTAL" in summary

    def test_is_identified_property(self):
        sig1 = FormatSignature(family=SigFamily.PDF_ESTANDAR, confidence=0.8)
        assert sig1.is_identified is True
        sig2 = FormatSignature(family=SigFamily.DESCONOCIDO, confidence=0.8)
        assert sig2.is_identified is False
        sig3 = FormatSignature(family=SigFamily.PDF_ESTANDAR, confidence=0.3)
        assert sig3.is_identified is False


# =============================================================================
# FORMAT REPOSITORY
# =============================================================================

class TestFormatRepository:
    @pytest.fixture
    def tmp_repo(self, tmp_path: Path) -> FormatRepository:
        return FormatRepository(str(tmp_path / "test_families.json"))

    def test_save_and_load(self, tmp_repo):
        sig = FormatSignature(
            document_type=DocumentType.BALANCE,
            family=SigFamily.PDF_ESTANDAR,
            confidence=0.85,
            code_pattern=CodePattern.GUION,
            company_name="Test Co",
        )
        tmp_repo.save_signature("PDF_ESTANDAR", sig)
        loaded = tmp_repo.load_family("PDF_ESTANDAR")
        assert len(loaded) == 1
        assert loaded[0].company_name == "Test Co"

    def test_list_families(self, tmp_repo):
        sig = FormatSignature(company_name="A", confidence=0.5)
        tmp_repo.save_signature("FAM_A", sig)
        tmp_repo.save_signature("FAM_B", sig)
        families = tmp_repo.list_families()
        assert "FAM_A" in families
        assert "FAM_B" in families

    def test_remove_family(self, tmp_repo):
        sig = FormatSignature(confidence=0.5)
        tmp_repo.save_signature("TEMP", sig)
        assert "TEMP" in tmp_repo.list_families()
        tmp_repo.remove_family("TEMP")
        assert "TEMP" not in tmp_repo.list_families()

    def test_find_by_code_pattern(self, tmp_repo):
        sig1 = FormatSignature(code_pattern=CodePattern.GUION, company_name="A", confidence=0.5)
        sig2 = FormatSignature(code_pattern=CodePattern.PUNTO, company_name="B", confidence=0.5)
        tmp_repo.save_signature("FAM1", sig1)
        tmp_repo.save_signature("FAM2", sig2)
        results = tmp_repo.find_by_code_pattern("GUION")
        assert len(results) == 1

    def test_find_by_layout(self, tmp_repo):
        sig = FormatSignature(layout=LayoutType.VERTICAL, company_name="A", confidence=0.5)
        tmp_repo.save_signature("FAM", sig)
        results = tmp_repo.find_by_layout("VERTICAL")
        assert len(results) == 1

    def test_statistics(self, tmp_repo):
        sig_a = FormatSignature(company_name="A", code_pattern=CodePattern.GUION, confidence=0.5)
        sig_b = FormatSignature(company_name="B", code_pattern=CodePattern.PUNTO, confidence=0.5)
        sig_c = FormatSignature(company_name="C", code_pattern=CodePattern.COMPACTO, confidence=0.5)
        tmp_repo.save_signature("FAM_A", sig_a)
        tmp_repo.save_signature("FAM_A", sig_b)
        tmp_repo.save_signature("FAM_B", sig_c)
        stats = tmp_repo.get_statistics()
        assert stats["total_families"] == 2
        assert stats["total_signatures"] == 3


# =============================================================================
# EXTRACTOR FACTORY
# =============================================================================

class TestExtractorFactory:
    def test_desconocido(self):
        factory = ExtractorFactory()
        sig = FormatSignature()
        assert factory.decide(sig) == ExtractorType.DESCONOCIDO

    def test_pdf_estandar(self):
        factory = ExtractorFactory()
        sig = FormatSignature(
            family=SigFamily.PDF_ESTANDAR,
            code_pattern=CodePattern.GUION,
            has_headers=True,
            confidence=0.85,
        )
        assert factory.decide(sig) == ExtractorType.PDF_ESTANDAR

    def test_excel_sii(self):
        factory = ExtractorFactory()
        sig = FormatSignature(family=SigFamily.EXCEL_SII, confidence=0.8)
        assert factory.decide(sig) == ExtractorType.EXCEL_SII

    def test_ocr_fallback(self):
        factory = ExtractorFactory()
        sig = FormatSignature(ocr_required=True, confidence=0.6)
        assert factory.decide(sig) == ExtractorType.OCR_FALLBACK

    def test_decide_with_detail(self):
        factory = ExtractorFactory()
        sig = FormatSignature(family=SigFamily.EXCEL_SII, confidence=0.8)
        detail = factory.decide_with_detail(sig)
        assert "extractor" in detail
        assert "confidence" in detail
        assert "reasons" in detail
        assert len(detail["reasons"]) >= 1


# =============================================================================
# METRICS
# =============================================================================

class TestDetectionMetrics:
    def test_record(self):
        metrics = DetectionMetrics()
        sig = FormatSignature(
            document_type=DocumentType.BALANCE,
            family=SigFamily.PDF_ESTANDAR,
            layout=LayoutType.VERTICAL,
            code_pattern=CodePattern.GUION,
            confidence=0.85,
        )
        metrics.record(sig)
        assert metrics.total_documents == 1
        assert metrics.identified == 1
        assert metrics.by_family["PDF_ESTANDAR"] == 1

    def test_unidentified(self):
        metrics = DetectionMetrics()
        sig = FormatSignature(confidence=0.3)
        metrics.record(sig)
        assert metrics.unidentified == 1

    def test_confidence_distribution(self):
        metrics = DetectionMetrics()
        for conf in [0.1, 0.3, 0.6, 0.8, 0.95]:
            metrics.record(FormatSignature(confidence=conf))
        assert metrics.confidence_distribution["0-25%"] == 1
        assert metrics.confidence_distribution["25-50%"] == 1
        assert metrics.confidence_distribution["50-75%"] == 1
        assert metrics.confidence_distribution["90-100%"] == 1

    def test_to_dict(self):
        metrics = DetectionMetrics()
        metrics.record(FormatSignature(confidence=0.8, family=SigFamily.PDF_ESTANDAR))
        d = metrics.to_dict()
        assert d["total_documents"] == 1
        assert d["identification_rate"] == 1.0


class TestMetricsCollector:
    def test_collect(self):
        collector = MetricsCollector()
        sigs = [
            FormatSignature(confidence=0.8, family=SigFamily.PDF_ESTANDAR),
            FormatSignature(confidence=0.3),
        ]
        metrics = collector.collect(sigs)
        assert metrics.total_documents == 2
        assert metrics.identified == 1
        assert metrics.unidentified == 1

    def test_merge(self):
        m1 = DetectionMetrics()
        m1.record(FormatSignature(confidence=0.8, family=SigFamily.PDF_ESTANDAR))
        m2 = DetectionMetrics()
        m2.record(FormatSignature(confidence=0.7, family=SigFamily.EXCEL_SII))

        collector = MetricsCollector()
        collector.merge(m1)
        collector.merge(m2)
        assert collector.metrics.total_documents == 2
        assert collector.metrics.by_family["PDF_ESTANDAR"] == 1
        assert collector.metrics.by_family["EXCEL_SII"] == 1
