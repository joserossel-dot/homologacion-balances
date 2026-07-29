from __future__ import annotations

import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from document_intelligence.models import (
    DocumentType, Family, Complexity, Recommendation, ParserName,
    DocumentProfile, DocumentClassification, FamilyClassification,
    TemplatePrediction, ParserRecommendation, ValidationRecommendation,
    ConfidencePrediction, CoveragePrediction, ProcessingRecommendation,
    IntelligenceReport,
)
from document_intelligence.document_classifier import DocumentClassifier
from document_intelligence.family_classifier import FamilyClassifier
from document_intelligence.template_classifier import TemplateClassifier
from document_intelligence.parser_selector import ParserSelector
from document_intelligence.validation_selector import ValidationSelector
from document_intelligence.confidence_predictor import ConfidencePredictor
from document_intelligence.recommendation_engine import RecommendationEngine
from document_intelligence.statistics import DocumentIntelligenceStats
from document_intelligence import DocumentIntelligence


# =============================================================================
# MODELS TESTS
# =============================================================================

class TestModels:
    def test_document_profile_defaults(self):
        p = DocumentProfile()
        assert p.pages == 0
        assert p.ocr_probability == 0.0
        assert p.estimated_complexity == Complexity.MEDIA

    def test_document_profile_to_dict(self):
        p = DocumentProfile(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            family=Family.TRIBUTARIO,
            pages=5,
            ocr_probability=0.1,
        )
        d = p.to_dict()
        assert d["document_type"] == "BALANCE_TRIBUTARIO"
        assert d["pages"] == 5

    def test_confidence_prediction_pct(self):
        c = ConfidencePrediction(global_score=0.85)
        assert c.confidence_pct == 85.0

    def test_confidence_prediction_low(self):
        c = ConfidencePrediction(global_score=0.05)
        assert c.confidence_pct == 5.0

    def test_coverage_prediction_pct(self):
        c = CoveragePrediction(global_pct=0.75)
        assert c.coverage_pct == 75.0

    def test_intelligence_report_summary(self):
        profile = DocumentProfile(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            family=Family.TRIBUTARIO,
            template="Template 14",
            pages=3, ocr_probability=0.05,
        )
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.95,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        parser = ParserRecommendation(
            parser_name=ParserName.UNIVERSAL, confidence=0.95,
            reason="PDF texto", estimated_time_ms=3000,
        )
        validation = ValidationRecommendation(ejecutar_biv=True)
        confidence = ConfidencePrediction(global_score=0.96)
        coverage = CoveragePrediction(global_pct=0.95)
        recommendation = ProcessingRecommendation(
            recommendation=Recommendation.CONTINUE,
            explanation="Confianza alta",
            complexity=Complexity.MEDIA,
            estimated_time_seconds=6.2,
            needs_ocr=False, needs_human_review=False,
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, template=None, parser=parser,
            validation=validation, confidence=confidence,
            coverage=coverage, recommendation=recommendation,
        )
        s = report.summary()
        assert "BALANCE_TRIBUTARIO" in s
        assert "TRIBUTARIO" in s
        assert "96" in s
        assert "95" in s
        assert "CONTINUE" in s

    def test_report_to_dict(self):
        profile = DocumentProfile(document_type=DocumentType.BALANCE_GENERAL)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_GENERAL, confidence=0.9,
        )
        family = FamilyClassification(family=Family.BALANCE_ESTANDAR, confidence=0.8)
        recommendation = ProcessingRecommendation(
            recommendation=Recommendation.CONTINUE, explanation="OK",
            complexity=Complexity.BAJA, estimated_time_seconds=2.0,
            needs_ocr=False, needs_human_review=False,
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, recommendation=recommendation,
        )
        d = report.to_dict()
        assert d["profile"]["document_type"] == "BALANCE_GENERAL"
        assert d["recommendation"]["recommendation"] == "CONTINUE"

    def test_parser_recommendation_fallback(self):
        rec = ParserRecommendation(
            parser_name=ParserName.OCR, confidence=0.8,
            reason="OCR needed",
            fallback_parser=ParserName.CORE2, needs_ocr=True,
        )
        d = rec.to_dict()
        assert d["fallback_parser"] == "Core2"

    def test_validation_recommendation_disable_equation(self):
        rec = ValidationRecommendation(
            ejecutar_biv=True, ejecutar_equation=False,
            ejecutar_subtotales=True, ejecutar_missing_accounts=True,
            ejecutar_integrity=True,
        )
        assert not rec.ejecutar_equation
        d = rec.to_dict()
        assert d["ejecutar_equation"] is False

    def test_complexity_enum_values(self):
        assert Complexity.BAJA.value == "BAJA"
        assert Complexity.MEDIA.value == "MEDIA"
        assert Complexity.ALTA.value == "ALTA"

    def test_recommendation_enum_values(self):
        assert Recommendation.CONTINUE.value == "CONTINUE"
        assert Recommendation.REVIEW.value == "REVIEW"
        assert Recommendation.STRESS.value == "STRESS"
        assert Recommendation.REJECT.value == "REJECT"

    def test_document_type_enum_values(self):
        assert DocumentType.BALANCE_TRIBUTARIO.value == "BALANCE_TRIBUTARIO"
        assert DocumentType.ESTADO_RESULTADOS.value == "ESTADO_RESULTADOS"

    def test_family_enum_values(self):
        assert Family.BALANCE_ESTANDAR.value == "BALANCE_ESTANDAR"
        assert Family.DESCONOCIDO.value == "DESCONOCIDO"


# =============================================================================
# DOCUMENT CLASSIFIER TESTS
# =============================================================================

class TestDocumentClassifier:
    def test_empty_lines(self):
        dc = DocumentClassifier()
        result = dc.classify([])
        assert result.document_type == DocumentType.OTRO
        assert result.confidence == 0.0

    def test_balance_tributario(self):
        dc = DocumentClassifier()
        lines = [
            "BALANCE TRIBUTARIO",
            "RUT: 76.693.319-K",
            "Al 31 de Diciembre de 2023",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.BALANCE_TRIBUTARIO
        assert result.confidence > 0.5

    def test_balance_general(self):
        dc = DocumentClassifier()
        lines = [
            "BALANCE GENERAL",
            "Activo Corriente",
            "Pasivo Corriente",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.BALANCE_GENERAL

    def test_estado_resultados(self):
        dc = DocumentClassifier()
        lines = [
            "ESTADO DE RESULTADOS",
            "Ingresos de Explotación",
            "Gastos de Administración",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.ESTADO_RESULTADOS

    def test_estado_patrimonio(self):
        dc = DocumentClassifier()
        lines = [
            "ESTADO DE PATRIMONIO NETO",
            "Capital Suscrito",
            "Reservas",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.ESTADO_PATRIMONIO

    def test_estado_flujo(self):
        dc = DocumentClassifier()
        lines = [
            "ESTADO DE FLUJO DE EFECTIVO",
            "Flujo de Operación",
            "Flujo de Inversión",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.ESTADO_FLUJO

    def test_unknown_document(self):
        dc = DocumentClassifier()
        lines = [
            "FACTURA ELECTRONICA",
            "Total: $100.000",
        ]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.OTRO
        assert result.confidence < 0.5

    def test_balance_general_variants(self):
        dc = DocumentClassifier()
        lines = ["Balance Clasificado", "Activo", "Pasivo"]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.BALANCE_GENERAL

    def test_case_insensitive(self):
        dc = DocumentClassifier()
        lines = ["balance tributario"]
        result = dc.classify(lines)
        assert result.document_type == DocumentType.BALANCE_TRIBUTARIO

    def test_raw_detected_headers(self):
        dc = DocumentClassifier()
        lines = ["BALANCE TRIBUTARIO", "Activo Corriente", "Pasivo"]
        result = dc.classify(lines)
        assert len(result.raw_detected_headers) >= 1

    def test_signals_present(self):
        dc = DocumentClassifier()
        lines = ["BALANCE GENERAL", "Activo"]
        result = dc.classify(lines)
        assert len(result.signals) > 0


# =============================================================================
# FAMILY CLASSIFIER TESTS
# =============================================================================

class TestFamilyClassifier:
    def test_tributario_by_header(self):
        fc = FamilyClassifier()
        lines = ["BALANCE TRIBUTARIO"]
        result = fc.classify(lines)
        assert result.family == Family.TRIBUTARIO

    def test_auditado_by_keyword(self):
        fc = FamilyClassifier()
        lines = ["BALANCE EEFF AUDITADOS"]
        result = fc.classify(lines)
        assert result.family == Family.EEFF_AUDITADOS

    def test_cpt_tasacion(self):
        fc = FamilyClassifier()
        lines = ["CPT TASACION"]
        result = fc.classify(lines)
        assert result.family == Family.CPT_TASACION

    def test_clasificado(self):
        fc = FamilyClassifier()
        lines = ["Balance Clasificado"]
        result = fc.classify(lines)
        assert result.family == Family.CLASIFICADO

    def test_template_family_override(self):
        fc = FamilyClassifier()
        lines = ["cualquier cosa"]
        result = fc.classify(lines, template_family="BALANCE_ESTANDAR")
        assert result.family == Family.BALANCE_ESTANDAR
        assert result.confidence > 0.9

    def test_eeff_structural(self):
        fc = FamilyClassifier()
        lines = ["Documento grande"]
        result = fc.classify(lines, section_count=5, subtotal_count=12)
        assert result.family == Family.EEFF_AUDITADOS

    def test_balance_estandar_structural(self):
        fc = FamilyClassifier()
        lines = ["Documento medio"]
        result = fc.classify(lines, section_count=3, subtotal_count=4)
        assert result.family == Family.BALANCE_ESTANDAR

    def test_balance_simple_by_lines(self):
        fc = FamilyClassifier()
        lines = ["a", "b", "c"]
        result = fc.classify(lines, total_lines=3)
        assert result.family == Family.BALANCE_SIMPLE

    def test_desconocido(self):
        fc = FamilyClassifier()
        lines = ["ZZZZ", "YYYY", "XXXX"]
        result = fc.classify(lines, total_lines=50, section_count=1, subtotal_count=0)
        assert result.family == Family.DESCONOCIDO

    def test_signals_present(self):
        fc = FamilyClassifier()
        lines = ["BALANCE TRIBUTARIO"]
        result = fc.classify(lines)
        assert len(result.signals) > 0


# =============================================================================
# TEMPLATE CLASSIFIER TESTS
# =============================================================================

class TestTemplateClassifier:
    def test_heuristic_punto(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="PUNTO", total_lines=50)
        assert result is not None
        assert result.family == "BALANCE_ESTANDAR"
        assert result.similarity > 0.5

    def test_heuristic_compaco(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="COMPACTO", total_lines=30)
        assert result is not None
        assert result.family == "TRIBUTARIO"

    def test_heuristic_sin_codigo(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="SIN_CODIGO", total_lines=20)
        assert result is not None
        assert result.family == "TRIBUTARIO"

    def test_heuristic_guion(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="GUION", total_lines=40)
        assert result is not None
        assert result.family == "BALANCE_ESTANDAR"

    def test_no_code_format_no_lines(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="", total_lines=0)
        assert result is None

    def test_signals_present(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="PUNTO", total_lines=50)
        assert result is not None
        assert len(result.signals) > 0

    def test_template_id_format(self):
        tc = TemplateClassifier()
        result = tc.predict(code_format="PUNTO", total_lines=30)
        assert result is not None
        assert "heuristic_" in result.template_id


# =============================================================================
# PARSER SELECTOR TESTS
# =============================================================================

class TestParserSelector:
    def test_pdf_text_recommends_universal(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.05, pages=3, is_pdf_text=True)
        assert result.parser_name == ParserName.UNIVERSAL
        assert result.confidence > 0.9

    def test_pdf_ocr_high(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.95, pages=5, is_pdf_text=False)
        assert result.parser_name == ParserName.OCR
        assert result.needs_ocr is True

    def test_pdf_ocr_medium(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.8, pages=3, is_pdf_text=False)
        assert result.parser_name == ParserName.OCR

    def test_pdf_low_text_density(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.4, pages=5, is_pdf_text=False)
        assert result.parser_name == ParserName.CORE2

    def test_excel_file(self):
        ps = ParserSelector()
        result = ps.recommend("test.xlsx")
        assert result.parser_name == ParserName.EXCEL
        assert result.confidence > 0.8

    def test_excel_old_format(self):
        ps = ParserSelector()
        result = ps.recommend("test.xls")
        assert result.parser_name == ParserName.EXCEL

    def test_image_file(self):
        ps = ParserSelector()
        result = ps.recommend("scan.png", pages=2)
        assert result.parser_name == ParserName.OCR
        assert result.needs_ocr is True

    def test_image_file_jpg(self):
        ps = ParserSelector()
        result = ps.recommend("photo.jpg", pages=1)
        assert result.parser_name == ParserName.OCR

    def test_unknown_extension(self):
        ps = ParserSelector()
        result = ps.recommend("data.xyz")
        assert result.parser_name == ParserName.DESCONOCIDO
        assert result.confidence < 0.5

    def test_estimated_time_scales_with_pages(self):
        ps = ParserSelector()
        r1 = ps.recommend("test.pdf", ocr_probability=0.05, pages=1, is_pdf_text=True)
        r2 = ps.recommend("test.pdf", ocr_probability=0.05, pages=10, is_pdf_text=True)
        assert r2.estimated_time_ms >= r1.estimated_time_ms

    def test_fallback_parser_ocr(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.95, pages=3, is_pdf_text=False)
        assert result.fallback_parser is not None

    def test_signals_present(self):
        ps = ParserSelector()
        result = ps.recommend("test.pdf", ocr_probability=0.05, pages=1, is_pdf_text=True)
        assert len(result.signals) > 0


# =============================================================================
# VALIDATION SELECTOR TESTS
# =============================================================================

class TestValidationSelector:
    def test_balance_full_validation(self):
        vs = ValidationSelector()
        result = vs.recommend(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            family=Family.BALANCE_ESTANDAR,
            estimated_accounts=50, estimated_sections=4,
        )
        assert result.ejecutar_biv
        assert result.ejecutar_equation
        assert result.ejecutar_subtotales
        assert result.ejecutar_missing_accounts
        assert result.ejecutar_integrity

    def test_balance_simple_skip_equation(self):
        vs = ValidationSelector()
        result = vs.recommend(
            document_type=DocumentType.BALANCE_GENERAL,
            family=Family.BALANCE_SIMPLE,
        )
        assert result.ejecutar_biv
        assert not result.ejecutar_equation

    def test_resultados_skip_equation(self):
        vs = ValidationSelector()
        result = vs.recommend(
            document_type=DocumentType.ESTADO_RESULTADOS,
        )
        assert not result.ejecutar_equation

    def test_patrimonio_skip_equation_and_missing(self):
        vs = ValidationSelector()
        result = vs.recommend(
            document_type=DocumentType.ESTADO_PATRIMONIO,
        )
        assert not result.ejecutar_equation
        assert not result.ejecutar_missing_accounts

    def test_flujo_skip_equation_and_missing(self):
        vs = ValidationSelector()
        result = vs.recommend(
            document_type=DocumentType.ESTADO_FLUJO,
        )
        assert not result.ejecutar_equation
        assert not result.ejecutar_missing_accounts

    def test_unknown_document_defaults(self):
        vs = ValidationSelector()
        result = vs.recommend()
        assert result.ejecutar_biv
        assert result.confidence < 0.7

    def test_signals_present(self):
        vs = ValidationSelector()
        result = vs.recommend(document_type=DocumentType.BALANCE_TRIBUTARIO)
        assert len(result.signals) > 0


# =============================================================================
# CONFIDENCE PREDICTOR TESTS
# =============================================================================

class TestConfidencePredictor:
    def test_high_confidence_scenario(self):
        cp = ConfidencePredictor()
        result = cp.predict(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            family=Family.BALANCE_ESTANDAR,
            ocr_probability=0.05,
            kb_coverage_pct=0.95,
            estimated_sections=4,
            has_signature=True,
        )
        assert result.global_score > 0.8
        assert result.confidence_pct > 80

    def test_low_confidence_ocr(self):
        cp = ConfidencePredictor()
        result = cp.predict(
            ocr_probability=0.95,
            kb_coverage_pct=0.3,
        )
        assert result.global_score < 0.5

    def test_ocr_penalty_scales(self):
        cp = ConfidencePredictor()
        r1 = cp.predict(ocr_probability=0.1)
        r2 = cp.predict(ocr_probability=0.8)
        assert r2.ocr_penalty > r1.ocr_penalty

    def test_kb_coverage_penalty(self):
        cp = ConfidencePredictor()
        r1 = cp.predict(kb_coverage_pct=0.95)
        r2 = cp.predict(kb_coverage_pct=0.2)
        assert r2.unknown_accounts_penalty > r1.unknown_accounts_penalty

    def test_known_family_boost(self):
        cp = ConfidencePredictor()
        r1 = cp.predict(family=Family.BALANCE_ESTANDAR)
        r2 = cp.predict(family=Family.DESCONOCIDO)
        assert r1.known_family_boost >= 0
        assert r2.known_family_boost < 0

    def test_validation_boost_with_sections(self):
        cp = ConfidencePredictor()
        r1 = cp.predict(estimated_sections=4)
        r2 = cp.predict(estimated_sections=0)
        assert r1.validation_boost >= r2.validation_boost

    def test_document_type_boost(self):
        cp = ConfidencePredictor()
        r = cp.predict(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            kb_coverage_pct=0.71,
        )
        assert r.global_score > 0.5

    def test_signals_present(self):
        cp = ConfidencePredictor()
        r = cp.predict(family=Family.BALANCE_ESTANDAR, ocr_probability=0.1)
        assert len(r.signals) > 0

    def test_global_score_bounds(self):
        cp = ConfidencePredictor()
        r1 = cp.predict(ocr_probability=0.99, kb_coverage_pct=0.0)
        assert r1.global_score >= 0.05
        r2 = cp.predict(
            document_type=DocumentType.BALANCE_TRIBUTARIO,
            family=Family.EEFF_AUDITADOS,
            ocr_probability=0.01, kb_coverage_pct=0.99,
            estimated_sections=5, has_signature=True,
        )
        assert r2.global_score <= 1.0


# =============================================================================
# RECOMMENDATION ENGINE TESTS
# =============================================================================

class TestRecommendationEngine:
    def test_continue_high_confidence(self):
        profile = DocumentProfile(pages=3)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.95,
        )
        family = FamilyClassification(family=Family.BALANCE_ESTANDAR, confidence=0.9)
        confidence = ConfidencePrediction(global_score=0.95)
        coverage = CoveragePrediction(global_pct=0.95)
        parser_rec = ParserRecommendation(
            parser_name=ParserName.UNIVERSAL, confidence=0.95,
            reason="OK", needs_ocr=False,
        )
        validation = ValidationRecommendation(ejecutar_biv=True)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, parser_rec=parser_rec,
            validation=validation, confidence=confidence,
            coverage=coverage,
        )
        assert result.recommendation == Recommendation.CONTINUE
        assert not result.needs_human_review

    def test_review_medium_confidence(self):
        profile = DocumentProfile(pages=5)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_GENERAL, confidence=0.6,
        )
        family = FamilyClassification(family=Family.DESCONOCIDO, confidence=0.3)
        confidence = ConfidencePrediction(global_score=0.55)
        coverage = CoveragePrediction(global_pct=0.50)
        parser_rec = ParserRecommendation(
            parser_name=ParserName.UNIVERSAL, confidence=0.7,
            reason="OK", needs_ocr=False,
        )
        validation = ValidationRecommendation(ejecutar_biv=True)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, parser_rec=parser_rec,
            validation=validation, confidence=confidence,
            coverage=coverage,
        )
        assert result.recommendation == Recommendation.REVIEW

    def test_stress_low_confidence(self):
        profile = DocumentProfile(pages=3)
        classification = DocumentClassification(
            document_type=DocumentType.OTRO, confidence=0.3,
        )
        family = FamilyClassification(family=Family.DESCONOCIDO, confidence=0.2)
        confidence = ConfidencePrediction(global_score=0.35)
        coverage = CoveragePrediction(global_pct=0.30)
        parser_rec = ParserRecommendation(
            parser_name=ParserName.OCR, confidence=0.5,
            reason="OCR", needs_ocr=True,
        )
        validation = ValidationRecommendation(ejecutar_biv=True)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, parser_rec=parser_rec,
            validation=validation, confidence=confidence,
            coverage=coverage,
        )
        assert result.recommendation == Recommendation.STRESS

    def test_reject_very_low_confidence(self):
        profile = DocumentProfile(pages=1)
        classification = DocumentClassification(
            document_type=DocumentType.OTRO, confidence=0.1,
        )
        family = FamilyClassification(family=Family.DESCONOCIDO, confidence=0.1)
        confidence = ConfidencePrediction(global_score=0.15)
        coverage = CoveragePrediction(global_pct=0.10)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, confidence=confidence, coverage=coverage,
        )
        assert result.recommendation == Recommendation.REJECT

    def test_high_confidence_needs_ocr_becomes_review(self):
        profile = DocumentProfile(pages=5)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.95,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        confidence = ConfidencePrediction(global_score=0.90)
        coverage = CoveragePrediction(global_pct=0.90)
        parser_rec = ParserRecommendation(
            parser_name=ParserName.OCR, confidence=0.8,
            reason="OCR", needs_ocr=True,
        )

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, parser_rec=parser_rec,
            confidence=confidence, coverage=coverage,
        )
        assert result.needs_human_review
        assert result.needs_ocr

    def test_complexity_baja_small_doc(self):
        profile = DocumentProfile(
            pages=2, estimated_accounts=10,
            estimated_complexity=Complexity.BAJA,
        )
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_GENERAL, confidence=0.9,
        )
        family = FamilyClassification(family=Family.BALANCE_SIMPLE, confidence=0.8)
        confidence = ConfidencePrediction(global_score=0.9)
        coverage = CoveragePrediction(global_pct=0.9)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, confidence=confidence, coverage=coverage,
        )
        assert result.complexity == Complexity.BAJA

    def test_complexity_alta_ocr(self):
        profile = DocumentProfile(pages=3, estimated_accounts=5)
        classification = DocumentClassification(
            document_type=DocumentType.OTRO, confidence=0.5,
        )
        family = FamilyClassification(family=Family.DESCONOCIDO, confidence=0.3)
        confidence = ConfidencePrediction(global_score=0.9)
        coverage = CoveragePrediction(global_pct=0.9)
        parser_rec = ParserRecommendation(
            parser_name=ParserName.OCR, confidence=0.8,
            reason="OCR needed", needs_ocr=True,
        )

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, parser_rec=parser_rec,
            confidence=confidence, coverage=coverage,
        )
        assert result.complexity == Complexity.ALTA

    def test_estimated_time_reasonable(self):
        profile = DocumentProfile(pages=3)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_GENERAL, confidence=0.9,
        )
        family = FamilyClassification(family=Family.BALANCE_ESTANDAR, confidence=0.9)
        confidence = ConfidencePrediction(global_score=0.95)
        coverage = CoveragePrediction(global_pct=0.95)

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, confidence=confidence, coverage=coverage,
        )
        assert result.estimated_time_seconds > 0

    def test_signals_present(self):
        profile = DocumentProfile(pages=3)
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.95,
        )
        family = FamilyClassification(family=Family.DESCONOCIDO, confidence=0.3)
        confidence = ConfidencePrediction(global_score=0.95)
        coverage = CoveragePrediction(global_pct=0.95)
        template = TemplatePrediction(
            template_id="t1", template_name="T1",
            family="BALANCE", similarity=0.9, confidence=0.9,
        )

        engine = RecommendationEngine()
        result = engine.evaluate(
            profile=profile, classification=classification,
            family=family, confidence=confidence, coverage=coverage,
            template=template,
        )
        assert len(result.signals) > 0


# =============================================================================
# STATISTICS TESTS
# =============================================================================

class TestStatistics:
    def test_empty_stats(self):
        stats = DocumentIntelligenceStats()
        assert stats.total_documents == 0
        assert stats.avg_confidence() == 0.0
        assert stats.avg_coverage() == 0.0

    def test_by_family(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        f1 = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        f2 = FamilyClassification(family=Family.BALANCE_ESTANDAR, confidence=0.9)
        report1 = IntelligenceReport(
            profile=profile, classification=classification, family=f1,
        )
        report2 = IntelligenceReport(
            profile=profile, classification=classification, family=f2,
        )
        report3 = IntelligenceReport(
            profile=profile, classification=classification, family=f1,
        )
        stats.add_reports([report1, report2, report3])
        by_fam = stats.by_family()
        assert by_fam["TRIBUTARIO"] == 2
        assert by_fam["BALANCE_ESTANDAR"] == 1

    def test_by_document_type(self):
        stats = DocumentIntelligenceStats()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        report = IntelligenceReport(
            profile=DocumentProfile(), classification=classification, family=family,
        )
        stats.add_report(report)
        by_dt = stats.by_document_type()
        assert by_dt["BALANCE_TRIBUTARIO"] == 1

    def test_by_parser(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        parser = ParserRecommendation(
            parser_name=ParserName.UNIVERSAL, confidence=0.9, reason="test",
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, parser=parser,
        )
        stats.add_report(report)
        by_p = stats.by_parser()
        assert by_p["Universal"] == 1

    def test_by_complexity(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        rec = ProcessingRecommendation(
            recommendation=Recommendation.CONTINUE, explanation="OK",
            complexity=Complexity.MEDIA, estimated_time_seconds=5.0,
            needs_ocr=False, needs_human_review=False,
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, recommendation=rec,
        )
        stats.add_report(report)
        by_c = stats.by_complexity()
        assert by_c["MEDIA"] == 1

    def test_by_confidence_range(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        confidence = ConfidencePrediction(global_score=0.95)
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, confidence=confidence,
        )
        stats.add_report(report)
        by_cr = stats.by_confidence_range()
        assert "90-100%" in by_cr

    def test_by_needs_ocr(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        rec = ProcessingRecommendation(
            recommendation=Recommendation.CONTINUE, explanation="OK",
            complexity=Complexity.MEDIA, estimated_time_seconds=5.0,
            needs_ocr=True, needs_human_review=False,
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, recommendation=rec,
        )
        stats.add_report(report)
        assert stats.by_needs_ocr()["Sí"] == 1

    def test_by_needs_review(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        rec = ProcessingRecommendation(
            recommendation=Recommendation.CONTINUE, explanation="OK",
            complexity=Complexity.MEDIA, estimated_time_seconds=5.0,
            needs_ocr=False, needs_human_review=True,
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, recommendation=rec,
        )
        stats.add_report(report)
        assert stats.by_needs_review()["Sí"] == 1

    def test_avg_confidence(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        c1 = ConfidencePrediction(global_score=0.9)
        c2 = ConfidencePrediction(global_score=0.8)
        r1 = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, confidence=c1,
        )
        r2 = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, confidence=c2,
        )
        stats.add_reports([r1, r2])
        assert stats.avg_confidence() == 0.85

    def test_generate_markdown(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        report = IntelligenceReport(
            profile=profile, classification=classification, family=family,
        )
        stats.add_report(report)
        md = stats.generate_markdown()
        assert "Document Intelligence" in md
        assert "TRIBUTARIO" in md
        assert "Resumen Global" in md

    def test_clear(self):
        stats = DocumentIntelligenceStats()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        report = IntelligenceReport(
            profile=DocumentProfile(), classification=classification, family=family,
        )
        stats.add_report(report)
        assert stats.total_documents == 1
        stats.clear()
        assert stats.total_documents == 0

    def test_total_templates_found(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile(template="Template 14")
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        report = IntelligenceReport(
            profile=profile, classification=classification, family=family,
        )
        stats.add_report(report)
        assert stats.total_templates_found() == 1

    def test_total_parsers_used(self):
        stats = DocumentIntelligenceStats()
        profile = DocumentProfile()
        classification = DocumentClassification(
            document_type=DocumentType.BALANCE_TRIBUTARIO, confidence=0.9,
        )
        family = FamilyClassification(family=Family.TRIBUTARIO, confidence=0.9)
        parser = ParserRecommendation(
            parser_name=ParserName.UNIVERSAL, confidence=0.9, reason="test",
        )
        report = IntelligenceReport(
            profile=profile, classification=classification,
            family=family, parser=parser,
        )
        stats.add_report(report)
        assert stats.total_parsers_used() == 1

    def test_to_dict(self):
        stats = DocumentIntelligenceStats()
        d = stats.to_dict()
        assert d["total_documents"] == 0


# =============================================================================
# DOCUMENT INTELLIGENCE INTEGRATION TESTS
# =============================================================================

class TestDocumentIntelligenceIntegration:
    def test_analyze_text_file(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("BALANCE TRIBUTARIO\nActivo Corriente\nCaja 100\nTotal 100\n")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            assert report.classification.document_type is not None
            assert report.profile.pages >= 1
            assert report.parser is not None
            assert report.recommendation is not None
        finally:
            os.unlink(tmp)

    def test_analyze_balance_tributario_text(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("BALANCE TRIBUTARIO\nRUT 76.693.319-K\nAl 31/12/2023\n")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            assert report.classification.document_type == DocumentType.BALANCE_TRIBUTARIO
        finally:
            os.unlink(tmp)

    def test_analyze_balance_general_text(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("BALANCE GENERAL\nActivo\nPasivo\nPatrimonio\n")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            assert report.classification.document_type == DocumentType.BALANCE_GENERAL
        finally:
            os.unlink(tmp)

    def test_summary_output(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("BALANCE TRIBUTARIO\nActivo Corriente\nCaja 100\n")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            s = report.summary()
            assert "Document Intelligence Report" in s
            assert "BALANCE_TRIBUTARIO" in s
        finally:
            os.unlink(tmp)

    def test_analyze_empty_file(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            assert report is not None
        finally:
            os.unlink(tmp)

    def test_nonexistent_file(self):
        engine = DocumentIntelligence()
        report = engine.analyze("/tmp/nonexistent_file_12345.pdf")
        assert report is not None

    def test_analyze_batch(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("BALANCE TRIBUTARIO\nActivo\n")
            p1 = f1.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            f2.write("BALANCE GENERAL\nPasivo\n")
            p2 = f2.name
        try:
            reports = engine.analyze_batch([p1, p2])
            assert len(reports) == 2
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_recommendation_continuity(self):
        engine = DocumentIntelligence()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("BALANCE TRIBUTARIO\nActivo\nCaja\nBanco\nTotal\n")
            tmp = f.name
        try:
            report = engine.analyze(tmp)
            assert report.recommendation.recommendation in (
                Recommendation.CONTINUE, Recommendation.REVIEW,
                Recommendation.STRESS, Recommendation.REJECT,
            )
        finally:
            os.unlink(tmp)
