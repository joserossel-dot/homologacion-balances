from __future__ import annotations

import json
from pathlib import Path

import pytest

from assessment.document_assessment import DocumentAssessment, DocumentMetrics


class TestDocumentMetrics:
    def test_default_values(self):
        m = DocumentMetrics()
        assert m.layout_confidence == 0.0
        assert m.ocr_confidence == 0.0
        assert m.parser_confidence == 0.0
        assert m.column_mapping_confidence == 0.0
        assert m.header_quality == 0.0
        assert m.candidate_accept_rate == 0.0
        assert m.contamination_rate == 0.0

    def test_to_dict(self):
        m = DocumentMetrics(
            layout_confidence=0.9,
            ocr_confidence=0.8,
            parser_confidence=0.7,
            column_mapping_confidence=0.6,
            header_quality=0.5,
            candidate_accept_rate=0.4,
            contamination_rate=0.3,
        )
        d = m.to_dict()
        assert d["layout_confidence"] == 0.9
        assert d["ocr_confidence"] == 0.8
        assert d["column_mapping_confidence"] == 0.6
        assert len(d) == 7

    def test_no_composite_score(self):
        m = DocumentMetrics(layout_confidence=0.9, ocr_confidence=0.1)
        d = m.to_dict()
        assert "composite" not in d
        assert "overall" not in d
        assert "score" not in d


class TestDocumentAssessmentConstants:
    def test_metrics_list(self):
        assert len(DocumentAssessment.METRICS) == 7
        assert "layout_confidence" in DocumentAssessment.METRICS
        assert "contamination_rate" in DocumentAssessment.METRICS


class TestLayoutConfidence:
    def make_doc(self, **overrides) -> dict:
        base = {
            "group": "validacion",
            "compatible": "SI",
            "layout_signature": "Activo|Pasivo|Perdida|Ganancia",
            "risk_score": 10,
        }
        base.update(overrides)
        return base

    def test_validacion_compatible(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="validacion", compatible="SI"))
        assert 0.9 <= m.layout_confidence <= 1.0

    def test_validacion_incompatible(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="validacion", compatible="NO"))
        assert m.layout_confidence < 0.9

    def test_edge_cases(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="edge_cases"))
        assert m.layout_confidence < 0.9

    def test_unknown_group(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="corruptos"))
        assert m.layout_confidence <= 0.5

    def test_high_risk_penalizes(self):
        a = DocumentAssessment()
        low_risk = a.assess(self.make_doc(risk_score=10))
        high_risk = a.assess(self.make_doc(risk_score=80))
        assert high_risk.layout_confidence < low_risk.layout_confidence

    def test_no_signature(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="SIN_HEADERS_DETECTADOS"))
        assert m.layout_confidence >= 0

    def test_clamped_to_range(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="validacion", compatible="NO", risk_score=100))
        assert 0.0 <= m.layout_confidence <= 1.0


class TestOcrConfidence:
    def make_doc(self, **overrides) -> dict:
        base = {
            "file_type": "pdf",
            "requirio_ocr": False,
            "ocr_noise_pct": 0,
            "total_lines": 100,
        }
        base.update(overrides)
        return base

    def test_excel_is_perfect(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(file_type="xlsx"))
        assert m.ocr_confidence == 1.0

    def test_native_text_high_confidence(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(requirio_ocr=False, total_lines=100))
        assert m.ocr_confidence >= 0.9

    def test_native_text_empty(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(requirio_ocr=False, total_lines=0))
        assert m.ocr_confidence < 0.9

    def test_ocr_lower_confidence(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(requirio_ocr=True))
        assert m.ocr_confidence < 0.9

    def test_ocr_high_noise_reduces(self):
        a = DocumentAssessment()
        clean = a.assess(self.make_doc(requirio_ocr=True, ocr_noise_pct=10))
        noisy = a.assess(self.make_doc(requirio_ocr=True, ocr_noise_pct=60))
        assert noisy.ocr_confidence < clean.ocr_confidence

    def test_ocr_pages_ratio_boosts(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            requirio_ocr=True, ocr_pages=5, pages=5, ocr_noise_pct=10,
        ))
        assert m.ocr_confidence >= 0.6

    def test_clamped_to_range(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(file_type="pdf", requirio_ocr=True, ocr_noise_pct=99))
        assert 0.0 <= m.ocr_confidence <= 1.0


class TestParserConfidence:
    def make_doc(self, **overrides) -> dict:
        base = {
            "accounts_total": 100,
            "accounts_classified": 60,
            "accounts_ignored": 20,
            "parser_error": "",
        }
        base.update(overrides)
        return base

    def test_high_classify_rate(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(accounts_classified=60, accounts_total=100))
        assert m.parser_confidence >= 0.7

    def test_low_classify_rate(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(accounts_classified=5, accounts_total=100))
        assert m.parser_confidence < 0.5

    def test_no_accounts(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(accounts_total=0, accounts_classified=0))
        assert m.parser_confidence == 0.0

    def test_parser_error(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            accounts_total=0, accounts_classified=0, parser_error="PDF corrupto",
        ))
        assert m.parser_confidence == 0.1

    def test_high_ignored_rate_penalizes(self):
        a = DocumentAssessment()
        low_ignored = a.assess(self.make_doc(accounts_ignored=10, accounts_total=100))
        high_ignored = a.assess(self.make_doc(accounts_ignored=90, accounts_total=100))
        assert high_ignored.parser_confidence < low_ignored.parser_confidence

    def test_clamped_to_range(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(accounts_total=1, accounts_classified=0))
        assert 0.0 <= m.parser_confidence <= 1.0


class TestColumnMappingConfidence:
    def make_doc(self, **overrides) -> dict:
        base = {
            "group": "validacion",
            "compatible": "SI",
            "num_headers": 4,
            "unknown_origin_pct": 5,
        }
        base.update(overrides)
        return base

    def test_validacion_compatible_high(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="validacion", compatible="SI"))
        assert m.column_mapping_confidence >= 0.8

    def test_edge_case_lower(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(group="edge_cases"))
        assert m.column_mapping_confidence < 0.8

    def test_incompatible_penalizes(self):
        a = DocumentAssessment()
        compatible = a.assess(self.make_doc(compatible="SI"))
        incompatible = a.assess(self.make_doc(compatible="NO"))
        assert incompatible.column_mapping_confidence < compatible.column_mapping_confidence

    def test_no_headers_penalizes(self):
        a = DocumentAssessment()
        with_headers = a.assess(self.make_doc(num_headers=4))
        without_headers = a.assess(self.make_doc(num_headers=0))
        assert without_headers.column_mapping_confidence < with_headers.column_mapping_confidence

    def test_high_unknown_origin(self):
        a = DocumentAssessment()
        low = a.assess(self.make_doc(unknown_origin_pct=10))
        high = a.assess(self.make_doc(unknown_origin_pct=60))
        assert high.column_mapping_confidence < low.column_mapping_confidence

    def test_clamped_to_range(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            group="edge_cases", compatible="NO", unknown_origin_pct=100,
        ))
        assert 0.0 <= m.column_mapping_confidence <= 1.0


class TestHeaderQuality:
    def make_doc(self, **overrides) -> dict:
        base = {
            "layout_signature": "Activo|Pasivo|Perdida|Ganancia",
            "num_headers": 4,
        }
        base.update(overrides)
        return base

    def test_no_headers(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="", num_headers=0))
        assert m.header_quality == 0.0

    def test_sin_headers_detected(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="SIN_HEADERS_DETECTADOS"))
        assert m.header_quality == 0.0

    def test_four_headers_high_quality(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="Activo|Pasivo|Perdida|Ganancia", num_headers=4))
        assert m.header_quality >= 0.8

    def test_two_headers_medium(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="Debe|Haber", num_headers=2))
        assert m.header_quality < 0.8

    def test_one_header_low(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(layout_signature="Activo", num_headers=1))
        assert m.header_quality < 0.5

    def test_known_pattern_bonus(self):
        a = DocumentAssessment()
        known = a.assess(self.make_doc(
            layout_signature="Activo|Pasivo|Perdida|Ganancia", num_headers=4,
        ))
        alt = a.assess(self.make_doc(
            layout_signature="Foo|Bar|Baz|Qux", num_headers=4,
        ))
        assert known.header_quality >= alt.header_quality

    def test_clamped_to_range(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            layout_signature="Debe|Haber|Activo|Pasivo|Perdida|Ganancia", num_headers=6,
        ))
        assert 0.0 <= m.header_quality <= 1.0


class TestCandidateAcceptRate:
    def make_doc(self, **overrides) -> dict:
        base = {
            "gatekeeper_accepted": 40,
            "gatekeeper_review": 10,
            "gatekeeper_rejected": 50,
        }
        base.update(overrides)
        return base

    def test_accepted_rate(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(gatekeeper_accepted=40, gatekeeper_review=10, gatekeeper_rejected=50))
        assert m.candidate_accept_rate == 0.4

    def test_all_accepted(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(gatekeeper_accepted=100, gatekeeper_review=0, gatekeeper_rejected=0))
        assert m.candidate_accept_rate == 1.0

    def test_none_accepted(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(gatekeeper_accepted=0, gatekeeper_review=0, gatekeeper_rejected=100))
        assert m.candidate_accept_rate == 0.0

    def test_fallback_to_classify_rate(self):
        a = DocumentAssessment()
        m = a.assess({
            "accounts_classified": 30,
            "accounts_total": 100,
        })
        assert m.candidate_accept_rate == 0.3

    def test_fallback_no_accounts(self):
        a = DocumentAssessment()
        m = a.assess({
            "accounts_classified": 0,
            "accounts_total": 0,
        })
        assert m.candidate_accept_rate == 0.0


class TestContaminationRate:
    def make_doc(self, **overrides) -> dict:
        base = {
            "contamination_pct": -1,
            "total_lines": 100,
            "empty_lines": 10,
            "other_noise_lines": 5,
            "header_lines": 3,
            "footer_lines": 2,
            "date_lines": 1,
            "rut_lines": 1,
            "address_lines": 0,
            "page_num_lines": 3,
        }
        base.update(overrides)
        return base

    def test_uses_contamination_pct_first(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(contamination_pct=25.0))
        assert m.contamination_rate == 0.25

    def test_calculates_from_line_counts(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            contamination_pct=-1,
            total_lines=100,
            empty_lines=10, other_noise_lines=5,
            header_lines=3, footer_lines=2,
            date_lines=1, rut_lines=1, page_num_lines=3,
        ))
        assert m.contamination_rate == 0.25

    def test_no_contamination(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(
            contamination_pct=-1, total_lines=100,
            empty_lines=0, other_noise_lines=0,
            header_lines=0, footer_lines=0,
            date_lines=0, rut_lines=0, address_lines=0, page_num_lines=0,
        ))
        assert m.contamination_rate == 0.0

    def test_no_lines(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(contamination_pct=-1, total_lines=0))
        assert m.contamination_rate == 0.0

    def test_caps_at_one(self):
        a = DocumentAssessment()
        m = a.assess(self.make_doc(contamination_pct=-1, total_lines=10, empty_lines=20))
        assert m.contamination_rate == 1.0


class TestMetricsIndependence:
    def test_each_metric_independent(self):
        a = DocumentAssessment()
        doc = {
            "group": "edge_cases",
            "file_type": "pdf",
            "requirio_ocr": True,
            "accounts_total": 50,
            "accounts_classified": 10,
            "accounts_ignored": 30,
            "compatible": "NO",
            "num_headers": 0,
            "layout_signature": "SIN_HEADERS_DETECTADOS",
            "unknown_origin_pct": 60,
            "risk_score": 65,
            "ocr_noise_pct": 40,
            "total_lines": 200,
            "empty_lines": 30,
            "other_noise_lines": 20,
        }
        m = a.assess(doc)
        assert m.layout_confidence >= 0
        assert m.ocr_confidence >= 0
        assert m.parser_confidence >= 0
        assert m.column_mapping_confidence >= 0
        assert m.header_quality >= 0
        assert m.candidate_accept_rate >= 0
        assert m.contamination_rate >= 0

    def test_metrics_do_not_influence_each_other(self):
        a = DocumentAssessment()
        doc1 = {"group": "validacion", "compatible": "SI", "file_type": "xlsx",
                "accounts_total": 100, "accounts_classified": 80}
        doc2 = {"group": "edge_cases", "compatible": "NO", "file_type": "pdf",
                "accounts_total": 10, "accounts_classified": 1}
        m1 = a.assess(doc1)
        m2 = a.assess(doc2)

        assert m1.layout_confidence != m2.layout_confidence
        assert m1.ocr_confidence != m2.ocr_confidence
        assert m1.parser_confidence != m2.parser_confidence
        assert m1.contamination_rate == m2.contamination_rate


class TestAssess:
    def test_returns_document_metrics(self):
        a = DocumentAssessment()
        doc = {"group": "validacion", "file_type": "xlsx", "accounts_total": 10,
               "accounts_classified": 5, "compatible": "SI", "num_headers": 4,
               "layout_signature": "Activo|Pasivo|Perdida|Ganancia"}
        m = a.assess(doc)
        assert isinstance(m, DocumentMetrics)

    def test_empty_doc(self):
        a = DocumentAssessment()
        m = a.assess({})
        assert isinstance(m, DocumentMetrics)
        assert all(v == 0.0 for v in m.to_dict().values())

    def test_partial_data(self):
        a = DocumentAssessment()
        m = a.assess({"group": "validacion", "file_type": "xlsx"})
        assert m.layout_confidence > 0
        assert m.ocr_confidence == 1.0
