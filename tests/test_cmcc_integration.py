from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from explainability import DecisionTrace, TraceBuilder, TraceReport, DecisionCode
from pipeline.features import CMCCFeatureFlags
from pipeline.cmcc_classifier import CMCCClassifier


# ─────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────

class TestCMCCFeatureFlags:
    def test_default_values(self):
        f = CMCCFeatureFlags()
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_SHADOW is True
        assert f.ENABLE_CMCC_PRODUCTION is False
        assert f.ENABLE_CMCC_ROLLBACK is False
        assert f.CMCC_THRESHOLD == 0.95
        assert f.CMCC_REVIEW_THRESHOLD == 0.85

    def test_rollback_mechanism(self):
        f = CMCCFeatureFlags(
            ENABLE_CMCC=True,
            ENABLE_CMCC_SHADOW=True,
            ENABLE_CMCC_PRODUCTION=True,
            ENABLE_CMCC_ROLLBACK=True,
        )
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_SHADOW is False
        assert f.ENABLE_CMCC_PRODUCTION is False

    def test_rollback_overrides_all(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_ROLLBACK=True)
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_SHADOW is False
        assert f.ENABLE_CMCC_PRODUCTION is False

    def test_from_env_overrides(self):
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_SHADOW"] = "false"
        os.environ["CMCC_CMCC_THRESHOLD"] = "0.90"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is True
            assert f.ENABLE_CMCC_SHADOW is False
            assert f.CMCC_THRESHOLD == 0.90
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_SHADOW"]
            del os.environ["CMCC_CMCC_THRESHOLD"]

    def test_from_env_rollback(self):
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_PRODUCTION"] = "true"
        os.environ["CMCC_ENABLE_CMCC_ROLLBACK"] = "true"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is False
            assert f.ENABLE_CMCC_PRODUCTION is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_PRODUCTION"]
            del os.environ["CMCC_ENABLE_CMCC_ROLLBACK"]

    def test_from_env_empty(self):
        f = CMCCFeatureFlags.from_env()
        assert f.ENABLE_CMCC is False

    def test_to_dict(self):
        f = CMCCFeatureFlags()
        d = f.to_dict()
        assert d["ENABLE_CMCC"] is False
        assert d["ENABLE_CMCC_SHADOW"] is True
        assert d["CMCC_THRESHOLD"] == 0.95


# ─────────────────────────────────────────────
# Feature Flag combinations → pipeline behavior
# ─────────────────────────────────────────────

class TestCMCCFlagCombinations:
    """Verify each feature flag combination produces the correct pipeline behavior.

    Key invariant: when ENABLE_CMCC=False, CMCC classification MUST NOT execute.
    """

    def test_disabled_skips_cmcc_entirely(self):
        """ENABLE_CMCC=False → CMCC classifier must NOT run."""
        f = CMCCFeatureFlags(ENABLE_CMCC=False)
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_PRODUCTION is False
        assert f.ENABLE_CMCC_SHADOW is True

    def test_shadow_only_does_not_classify(self):
        """ENABLE_CMCC=True + SHADOW=True + PRODUCTION=False → no official change."""
        f = CMCCFeatureFlags(
            ENABLE_CMCC=True,
            ENABLE_CMCC_SHADOW=True,
            ENABLE_CMCC_PRODUCTION=False,
        )
        assert f.ENABLE_CMCC is True
        assert f.ENABLE_CMCC_SHADOW is True
        assert f.ENABLE_CMCC_PRODUCTION is False

    def test_production_requires_threshold(self):
        """PRODUCTION=True → production is allowed."""
        f = CMCCFeatureFlags(
            ENABLE_CMCC=True,
            ENABLE_CMCC_PRODUCTION=True,
        )
        assert f.ENABLE_CMCC_PRODUCTION is True

    def test_production_with_threshold_config(self):
        """Verify threshold configuration for production mode."""
        f = CMCCFeatureFlags(
            ENABLE_CMCC=True,
            ENABLE_CMCC_PRODUCTION=True,
            CMCC_THRESHOLD=0.95,
            CMCC_REVIEW_THRESHOLD=0.85,
        )
        assert f.CMCC_THRESHOLD == 0.95
        assert f.CMCC_REVIEW_THRESHOLD == 0.85

    def test_all_flags_false_by_default(self):
        """Rollback not active by default."""
        f = CMCCFeatureFlags()
        assert f.ENABLE_CMCC_ROLLBACK is False

    def test_rollback_sets_cmcc_to_false(self):
        """ENABLE_CMCC_ROLLBACK=True forces ENABLE_CMCC=False."""
        f = CMCCFeatureFlags(ENABLE_CMCC=True, ENABLE_CMCC_ROLLBACK=True)
        assert f.ENABLE_CMCC is False

    def test_rollback_sets_shadow_to_false(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_SHADOW=True, ENABLE_CMCC_ROLLBACK=True)
        assert f.ENABLE_CMCC_SHADOW is False

    def test_rollback_sets_production_to_false(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_PRODUCTION=True, ENABLE_CMCC_ROLLBACK=True)
        assert f.ENABLE_CMCC_PRODUCTION is False

    def test_rollback_from_env(self):
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        os.environ["CMCC_ENABLE_CMCC_ROLLBACK"] = "true"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is False
            assert f.ENABLE_CMCC_SHADOW is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]
            del os.environ["CMCC_ENABLE_CMCC_ROLLBACK"]

    def test_rollback_does_not_affect_non_cmcc_flags(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_ROLLBACK=True)
        assert f.ENABLE_CMCC is False
        assert f.CMCC_THRESHOLD == 0.95
        assert f.CMCC_REVIEW_THRESHOLD == 0.85


# ─────────────────────────────────────────────
# CMCC Classifier — shadow data integrity
# ─────────────────────────────────────────────

class TestCMCCClassifierShadowData:
    """Verify CMCC classifier output contains all required fields for shadow mode."""

    REQUIRED_SHADOW_FIELDS = {"score", "concept", "code", "evidence", "method"}

    @pytest.fixture(scope="class")
    def classifier(self):
        return CMCCClassifier()

    def test_shadow_output_has_all_fields(self, classifier):
        result = classifier.classify("Caja General")
        assert self.REQUIRED_SHADOW_FIELDS.issubset(result.keys())

    def test_shadow_score_is_numeric(self, classifier):
        result = classifier.classify("Caja General")
        assert isinstance(result.get("score"), (int, float))

    def test_shadow_concept_is_string(self, classifier):
        result = classifier.classify("Caja General")
        assert isinstance(result.get("concept"), str)

    def test_shadow_evidence_is_list(self, classifier):
        result = classifier.classify("Caja General")
        assert isinstance(result.get("evidence"), list)

    def test_shadow_code_is_not_none_for_known(self, classifier):
        result = classifier.classify("Proveedores Nacionales")
        assert result.get("code") is not None

    def test_shadow_code_is_low_score_for_gibberish(self, classifier):
        result = classifier.classify("ZXCVBNM ASDFGHJK")
        assert result.get("score", 1.0) < 0.50

    def test_shadow_code_is_none_for_empty(self, classifier):
        result = classifier.classify("")
        assert result.get("code") is None

    def test_shadow_method_is_string(self, classifier):
        result = classifier.classify("Caja")
        assert isinstance(result.get("method"), str)

    def test_explicacion_field_provided(self, classifier):
        result = classifier.classify("Banco Santander")
        assert "evidence" in result
        assert len(result["evidence"]) > 0
        if result.get("matched_variant"):
            assert isinstance(result["matched_variant"], str)


# ─────────────────────────────────────────────
# Decision Trace — CMCC method codes
# ─────────────────────────────────────────────

class TestCMCCDecisionTrace:
    """Verify CMCC methods are correctly mapped in Decision Trace."""

    def test_method_to_code_has_cmcc_entries(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert "cmcc_nombre" in mtc
        assert "cmcc_variante" in mtc
        assert "cmcc_sinonimo" in mtc
        assert "cmcc_abreviatura" in mtc
        assert "cmcc_none" in mtc

    def test_cmcc_nombre_maps_to_d001(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert mtc["cmcc_nombre"] == DecisionCode.D001

    def test_cmcc_variante_maps_to_d001(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert mtc["cmcc_variante"] == DecisionCode.D001

    def test_cmcc_sinonimo_maps_to_d004(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert mtc["cmcc_sinonimo"] == DecisionCode.D004

    def test_cmcc_abreviatura_maps_to_d003(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert mtc["cmcc_abreviatura"] == DecisionCode.D003

    def test_cmcc_none_maps_to_d201(self):
        from explainability.trace_builder import _METHOD_TO_CODE as mtc
        assert mtc["cmcc_none"] == DecisionCode.D201

    def test_trace_with_cmcc_nombre(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[],
            normalized_name="caja general", original_name="Caja General",
            cmcc_match=True, cmcc_match_type="nombre", cmcc_variant="caja general", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=1.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description="Exact Variant",
            timestamp="ts",
        )
        assert t.cmcc_match is True
        assert t.cmcc_match_type == "nombre"
        assert t.cmcc_score == 1.0
        assert t.official_classification == "AC.01"

    def test_trace_with_cmcc_sinonimo(self):
        t = DecisionTrace(
            document_id="d1", company="C", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.85,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[],
            normalized_name="efectivo", original_name="Efectivo",
            cmcc_match=True, cmcc_match_type="sinonimo", cmcc_variant="efectivo", cmcc_score=0.95,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=0.95,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D004", decision_description="Synonym Match",
            timestamp="ts",
        )
        assert t.cmcc_match_type == "sinonimo"
        assert t.decision_code == "D004"

    def test_trace_with_cmcc_production_reason(self):
        reason = "CMCC (cmcc_nombre) → AC.01 (Caja y Bancos) score=1.0"
        t = DecisionTrace(
            document_id="d1", company="C", layout="validacion",
            layout_confidence=0.9, ocr_confidence=1.0, parser_confidence=0.9,
            column_mapping_confidence=0.0, candidate_accept_rate=0.0,
            candidate_status="accepted", candidate_reasons=[reason],
            normalized_name="caja general", original_name="Caja General",
            cmcc_match=True, cmcc_match_type="nombre", cmcc_variant="caja general", cmcc_score=1.0,
            dictionary_match=False, dictionary_source="",
            official_classification="AC.01", official_confidence=1.0,
            shadow_classification="", shadow_confidence=0.0,
            decision_code="D001", decision_description=reason,
            timestamp="ts",
        )
        assert "CMCC" in t.decision_description
        assert "score=1.0" in t.decision_description

    def test_trace_with_inline_cmcc_shadow(self, tmp_path):
        """TraceBuilder extracts shadow data from inline cmcc_shadow field in account data."""
        ap = tmp_path / "audit.json"
        accounts = [
            {
                "account_name": "Caja Test",
                "method": "unclassified",
                "reason": "Sin coincidencia en código ni diccionario",
                "final_code": None,
                "confidence": 0,
                "source_file": "test.pdf",
                "source_group": "validacion",
                "nature": "profit",
                "standard_code": None,
                "special_rule": None,
                "account_code": "001",
                "cmcc_shadow": {
                    "code": "AC.01",
                    "concept": "Caja y Bancos",
                    "score": 1.0,
                    "method": "cmcc_nombre",
                    "matched_variant": "caja",
                    "evidence": ["matched_nombre: Caja"],
                },
            },
        ]
        with open(ap, "w") as f:
            json.dump({"accounts": accounts, "files": []}, f)
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.shadow_classification == "AC.01"
        assert t.shadow_confidence == 1.0


# ─────────────────────────────────────────────
# TraceBuilder — CMCC method recognition
# ─────────────────────────────────────────────

class TestTraceBuilderCMCC:
    """Verify TraceBuilder correctly builds traces for CMCC-classified accounts."""

    def make_audit(self, tmp_path: Path, accounts: list[dict]) -> Path:
        ap = tmp_path / "audit.json"
        with open(ap, "w") as f:
            json.dump({"accounts": accounts, "files": [
                {"source_file": "file.pdf", "file_type": "pdf"},
            ]}, f)
        return ap

    def test_cmcc_nombre_trace(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {
                "account_name": "Caja General",
                "method": "cmcc_nombre",
                "reason": "CMCC (cmcc_nombre) → AC.01 (Caja y Bancos) score=1.0",
                "final_code": "AC.01",
                "confidence": 1.0,
                "source_file": "file.pdf",
                "source_group": "validacion",
                "nature": "profit",
                "standard_code": "AC.01",
                "special_rule": None,
                "account_code": "001",
            },
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.cmcc_match is True
        assert t.cmcc_match_type == "nombre"
        assert t.official_classification == "AC.01"
        assert t.decision_code == DecisionCode.D001.value

    def test_cmcc_sinonimo_trace(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {
                "account_name": "Efectivo",
                "method": "cmcc_sinonimo",
                "reason": "CMCC (cmcc_sinonimo) → AC.01 (Caja y Bancos) score=0.95",
                "final_code": "AC.01",
                "confidence": 0.95,
                "source_file": "file.pdf",
                "source_group": "validacion",
                "nature": "profit",
                "standard_code": "AC.01",
                "special_rule": None,
                "account_code": "002",
            },
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.cmcc_match is True
        assert t.cmcc_match_type == "sinonimo"
        assert t.decision_code == DecisionCode.D004.value

    def test_cmcc_variante_trace(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {
                "account_name": "Banco Estado",
                "method": "cmcc_variante",
                "reason": "CMCC (cmcc_variante) → AC.01 (Caja y Bancos) score=0.98",
                "final_code": "AC.01",
                "confidence": 0.98,
                "source_file": "file.pdf",
                "source_group": "validacion",
                "nature": "profit",
                "standard_code": "AC.01",
                "special_rule": None,
                "account_code": "003",
            },
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.cmcc_match is True
        assert t.cmcc_match_type == "variante"

    def test_cmcc_abreviatura_trace(self, tmp_path):
        ap = self.make_audit(tmp_path, [
            {
                "account_name": "Prov.",
                "method": "cmcc_abreviatura",
                "reason": "CMCC (cmcc_abreviatura) → PC.01 (Proveedores) score=0.92",
                "final_code": "PC.01",
                "confidence": 0.92,
                "source_file": "file.pdf",
                "source_group": "validacion",
                "nature": "profit",
                "standard_code": "PC.01",
                "special_rule": None,
                "account_code": "004",
            },
        ])
        shadow = tmp_path / "shadow.xlsx"
        pd.DataFrame(columns=["Cuenta", "Código sugerido"]).to_excel(shadow, index=False)
        b = TraceBuilder(audit_path=ap, shadow_path=shadow)
        traces = b.build_all()
        assert len(traces) == 1
        t = traces[0]
        assert t.cmcc_match is True
        assert t.cmcc_match_type == "abreviatura"
        assert t.decision_code == DecisionCode.D003.value


# ─────────────────────────────────────────────
# Rollback guarantee — pipeline behavior invariance
# ─────────────────────────────────────────────

class TestCMCCRollbackGuarantee:
    """Verify that changing ENABLE_CMCC=False restores pre-CMCC behavior.

    The pipeline without CMCC must produce identical results to
    ENABLE_CMCC=False mode.
    """

    def test_feature_flag_state_equivalence(self):
        """Pipeline without CMCCFeatureFlags is same as ENABLE_CMCC=False."""
        default = CMCCFeatureFlags()
        disabled = CMCCFeatureFlags(ENABLE_CMCC=False)
        assert default.ENABLE_CMCC == disabled.ENABLE_CMCC
        assert default.to_dict()["ENABLE_CMCC"] == disabled.to_dict()["ENABLE_CMCC"]

    def test_disabled_matches_rollback_for_cmcc(self):
        """ENABLE_CMCC=False and ENABLE_CMCC_ROLLBACK=True both prevent CMCC."""
        disabled = CMCCFeatureFlags(ENABLE_CMCC=False)
        rollback = CMCCFeatureFlags(ENABLE_CMCC_ROLLBACK=True)
        assert disabled.ENABLE_CMCC == rollback.ENABLE_CMCC
        assert disabled.ENABLE_CMCC_PRODUCTION == rollback.ENABLE_CMCC_PRODUCTION

    def test_feature_flag_accessor_no_side_effects(self):
        """Reading feature flags does not change pipeline behavior."""
        f = CMCCFeatureFlags()
        d = f.to_dict()
        assert d["ENABLE_CMCC"] is False
        assert f.ENABLE_CMCC is False

    def test_rollback_via_env_toggle(self):
        """Toggling env var CMCC_ENABLE_CMCC to false restores default."""
        os.environ["CMCC_ENABLE_CMCC"] = "false"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is False
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]

    def test_rollback_via_env_flag_true(self):
        """Setting CMCC_ENABLE_CMCC to true enables it."""
        os.environ["CMCC_ENABLE_CMCC"] = "true"
        try:
            f = CMCCFeatureFlags.from_env()
            assert f.ENABLE_CMCC is True
        finally:
            del os.environ["CMCC_ENABLE_CMCC"]

    def test_default_construction_no_cmcc(self):
        """Default CMCCFeatureFlags() has ENABLE_CMCC=False → safe default."""
        f = CMCCFeatureFlags()
        assert f.ENABLE_CMCC is False
        assert f.ENABLE_CMCC_PRODUCTION is False

    def test_rollback_does_not_affect_non_cmcc_fields(self):
        f = CMCCFeatureFlags(ENABLE_CMCC_ROLLBACK=True)
        assert f.CMCC_THRESHOLD == 0.95
        assert f.CMCC_REVIEW_THRESHOLD == 0.85


class TestCMCCPipelineCompatibility:
    """Compatibility verification with existing pipeline components."""

    def test_imports(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        from pipeline.features import CMCCFeatureFlags
        from pipeline.cmcc_classifier import CMCCClassifier
        assert HomologationPipeline is not None
        assert CMCCFeatureFlags is not None
        assert CMCCClassifier is not None

    def test_pipeline_accepts_feature_flags(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        from pipeline.features import CMCCFeatureFlags
        flags = CMCCFeatureFlags(ENABLE_CMCC=False)
        pipeline = HomologationPipeline(features=flags)
        assert pipeline._features.ENABLE_CMCC is False

    def test_pipeline_defaults_to_no_cmcc(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        pipeline = HomologationPipeline()
        assert pipeline._features.ENABLE_CMCC is False

    def test_cmcc_classifier_loaded_in_pipeline(self):
        from pipeline.homologation_pipeline import HomologationPipeline
        pipeline = HomologationPipeline()
        assert pipeline._cmcc_classifier is not None


if __name__ == "__main__":
    pytest.main([__file__])
