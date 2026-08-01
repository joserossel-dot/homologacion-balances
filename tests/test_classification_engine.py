"""Tests del motor de clasificación por cuenta (classification_engine).

Cubre:
  1. Modelos de decisión (Candidate, RankedCandidate, TopNResult,
     EvidenceSource) y su serialización.
  2. DocumentProcessingContextAdapter (dict plano + DocumentContext real).
  3. WeightConfig (validación, from_dict/from_json, sobrescritura).
  4. Scorer (agregación, orden, empates, label de confianza).
  5. CandidateGenerator (capas code/catalog/synonyms/special/context).
  6. Explainer (reasons, breakdown, candidate_explanations).
  7. DecisionEngine end-to-end (rankings, UNKNOWN, context, métricas).

El motor es 100% desacoplado: no requiere PDFs ni Document Intelligence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from classification_engine import DecisionEngine
from classification_engine.candidate import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    KnowledgeLoader,
)
from classification_engine.decision import (
    Candidate,
    DocumentProcessingContextAdapter,
    EvidenceSource,
    RankedCandidate,
    TopNResult,
)
from classification_engine.explainer import Explainer
from classification_engine.metrics import compute_metrics
from classification_engine.score import (
    CANDIDATE_LAYERS,
    DEFAULT_LAYER_WEIGHTS,
    Scorer,
    WeightConfig,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loader():
    return KnowledgeLoader()


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine()


@pytest.fixture
def balance_context():
    return {
        "die_report": {
            "classification": {"document_type": "BALANCE_GENERAL", "confidence": 0.97},
            "family": {"family": "BALANCE_ESTANDAR", "confidence": 0.95},
            "profile": {"document_type": "BALANCE_GENERAL", "family": "BALANCE_ESTANDAR",
                        "layout": "TABULAR"},
            "template": {"template_id": "T1", "template_name": "Plantilla A"},
            "parser": {"parser_name": "parser_balance"},
            "confidence": {"confidence_pct": 0.97},
            "coverage": {"coverage_pct": 0.85},
        }
    }


@pytest.fixture
def resultados_context():
    return {
        "die_report": {
            "classification": {"document_type": "ESTADO_RESULTADOS", "confidence": 0.96},
        }
    }


# ---------------------------------------------------------------------------
# KnowledgeLoader
# ---------------------------------------------------------------------------


class TestKnowledgeLoader:
    def test_loads_catalogo_and_synonyms(self, loader):
        assert len(loader.catalogo) >= 61
        assert len(loader.synonyms) >= 61
        assert not loader.warnings

    def test_missing_file_degrades_gracefully(self, tmp_path):
        l = KnowledgeLoader(
            catalogo_path=str(tmp_path / "no_existe.json"),
            synonyms_path=str(tmp_path / "no_existe.json"),
        )
        assert l.is_loaded() is False
        assert l.warnings

    def test_invalid_json_degrades(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{no es json", encoding="utf-8")
        l = KnowledgeLoader(
            catalogo_path=str(bad),
            synonyms_path=str(bad),
        )
        assert l.warnings

    def test_account_meta_and_synonyms_for(self, loader):
        meta = loader.account_meta("AC.01")
        assert meta.get("codigo_estandar") == "AC.01"
        assert meta.get("tipo_estado") == "balance"
        syn = loader.synonyms_for("AC.01")
        assert syn.get("codigo") == "AC.01"
        assert syn.get("sinonimos")


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class TestEvidenceSource:
    def test_to_dict_roundtrip(self):
        ev = EvidenceSource(
            layer="catalog_exact", code="AC.01", score=1.0, weight=0.9,
            source="catalogo_maestro.json", detail="match", matched_value="Caja",
        )
        d = ev.to_dict()
        assert d["layer"] == "catalog_exact"
        assert d["code"] == "AC.01"
        assert d["score"] == 1.0
        assert d["weight"] == 0.9


class TestCandidate:
    def test_add_evidence_and_layers(self):
        c = Candidate(code="AC.01", name="Caja")
        c.add_evidence(EvidenceSource(layer="code", code="AC.01", score=0.97))
        c.add_evidence(EvidenceSource(layer="catalog_exact", code="AC.01", score=1.0))
        assert c.has_layer("code")
        assert not c.has_layer("synonyms_exact")
        assert c.layer_scores() == {"code": 0.97, "catalog_exact": 1.0}

    def test_to_dict(self):
        c = Candidate(code="AC.01", name="Caja", category="activo_corriente")
        c.add_evidence(EvidenceSource(layer="code", code="AC.01", score=0.97))
        d = c.to_dict()
        assert d["code"] == "AC.01"
        assert len(d["evidence"]) == 1


class TestTopNResult:
    def test_top_code_and_score(self):
        res = TopNResult(
            account_name="Caja",
            top_n=[
                RankedCandidate(code="AC.01", score=0.9, rank=1),
                RankedCandidate(code="AC.02", score=0.5, rank=2),
            ],
        )
        assert res.top_code == "AC.01"
        assert res.top_score == 0.9

    def test_empty_top_n_properties(self):
        res = TopNResult(account_name="X")
        assert res.top_code is None
        assert res.top_score == 0.0

    def test_to_dict_serialization(self):
        res = TopNResult(
            account_name="Caja",
            top_n=[RankedCandidate(code="AC.01", score=0.9, rank=1)],
        )
        d = res.to_dict()
        assert d["top_code"] == "AC.01"
        assert d["top_n"][0]["rank"] == 1
        assert "timestamp" in d


# ---------------------------------------------------------------------------
# DocumentProcessingContextAdapter
# ---------------------------------------------------------------------------


class TestDocumentProcessingContextAdapter:
    def test_flat_dict(self, balance_context):
        a = DocumentProcessingContextAdapter(balance_context)
        assert a.document_type == "BALANCE_GENERAL"
        assert a.family == "BALANCE_ESTANDAR"
        assert a.layout == "TABULAR"
        assert a.template == "Plantilla A"
        assert a.selected_parser == "parser_balance"
        assert a.confidence_expected == 0.97
        assert a.coverage_expected == 0.85
        assert a.tipo_estado == "balance"
        assert a.has_document_context
        assert not a.is_empty()

    def test_resultados_context_tipo(self, resultados_context):
        a = DocumentProcessingContextAdapter(resultados_context)
        assert a.tipo_estado == "resultados"

    def test_none_context_is_empty(self):
        a = DocumentProcessingContextAdapter(None)
        assert a.is_empty()
        assert a.tipo_estado is None

    def test_real_document_context(self, balance_context):
        from document_context.context import DocumentContext

        ctx = DocumentContext(source_file="test.pdf")
        ctx.set_custom("die_report", balance_context["die_report"])
        a = DocumentProcessingContextAdapter(ctx)
        assert a.document_type == "BALANCE_GENERAL"
        assert a.family == "BALANCE_ESTANDAR"
        assert a.tipo_estado == "balance"

    def test_adapter_never_writes_to_context(self):
        from document_context.context import DocumentContext

        ctx = DocumentContext(source_file="test.pdf")
        ctx.set_custom("die_report", {})
        DocumentProcessingContextAdapter(ctx)
        assert ctx.get_custom("die_report") == {}
        assert ctx.get_custom("classification_engine_marker") is None

    def test_unknown_family_no_tipo(self):
        a = DocumentProcessingContextAdapter({"family": "FAMILIA_X", "document_type": "OTRO"})
        assert a.tipo_estado is None


# ---------------------------------------------------------------------------
# WeightConfig
# ---------------------------------------------------------------------------


class TestWeightConfig:
    def test_defaults(self):
        cfg = WeightConfig()
        assert cfg.weight("catalog_exact") == DEFAULT_LAYER_WEIGHTS["catalog_exact"]
        assert cfg.weight("nope") == 0.0
        assert cfg.fuzzy_threshold == 0.88
        assert cfg.top_n == 5

    def test_validate_rejects_bad_weights(self):
        with pytest.raises(ValueError):
            WeightConfig(weights={"catalog_exact": -1})
        with pytest.raises(ValueError):
            WeightConfig(weights={})

    def test_validate_rejects_bad_thresholds(self):
        with pytest.raises(ValueError):
            WeightConfig(confidence_thresholds=[])
        with pytest.raises(ValueError):
            WeightConfig(confidence_thresholds=[(0.5, "A"), (0.9, "B")])
        with pytest.raises(ValueError):
            WeightConfig(fuzzy_threshold=1.5)
        with pytest.raises(ValueError):
            WeightConfig(min_consensus_layers=1)
        with pytest.raises(ValueError):
            WeightConfig(consensus_bonus=0.5)

    def test_set_weight(self):
        cfg = WeightConfig()
        cfg.set_weight("context", 0.7)
        assert cfg.weight("context") == 0.7
        with pytest.raises(ValueError):
            cfg.set_weight("context", -0.1)

    def test_from_dict_partial_override(self):
        cfg = WeightConfig.from_dict({"weights": {"context": 0.6}})
        assert cfg.weight("context") == 0.6
        assert cfg.weight("catalog_exact") == DEFAULT_LAYER_WEIGHTS["catalog_exact"]
        assert cfg.top_n == 5

    def test_from_dict_full(self):
        cfg = WeightConfig.from_dict({
            "weights": {"code": 0.5},
            "fuzzy_threshold": 0.9,
            "consensus_bonus": 1.2,
            "min_consensus_layers": 3,
            "confidence_thresholds": [{"min_score": 0.9, "label": "HIGH"},
                                      {"min_score": 0.0, "label": "LOW"}],
            "top_n": 10,
        })
        assert cfg.weight("code") == 0.5
        assert cfg.fuzzy_threshold == 0.9
        assert cfg.top_n == 10
        assert Scorer(cfg).confidence_label(0.95) == "HIGH"

    def test_from_json_roundtrip(self, tmp_path):
        cfg = WeightConfig()
        p = tmp_path / "weights.json"
        import json
        p.write_text(json.dumps(cfg.to_dict()), encoding="utf-8")
        cfg2 = WeightConfig.from_json(str(p))
        assert cfg2.to_dict() == cfg.to_dict()

    def test_candidate_layers_constants(self):
        assert "code" in CANDIDATE_LAYERS
        assert "context" not in CANDIDATE_LAYERS
        assert "catalog_exact" in CANDIDATE_LAYERS


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


class TestScorer:
    def test_single_candidate_single_layer(self):
        c = Candidate(code="AC.01", name="Caja")
        c.add_evidence(EvidenceSource(layer="catalog_exact", code="AC.01", score=1.0,
                                      weight=1.0))
        r = Scorer().score([c])[0]
        assert r.score == 1.0
        assert r.confidence == "EXACT"
        assert r.rank == 1

    def test_multi_layer_weighted(self):
        c = Candidate(code="AC.01", name="Caja")
        c.add_evidence(EvidenceSource(layer="code", code="AC.01", score=0.9, weight=0.9))
        c.add_evidence(EvidenceSource(layer="synonyms_exact", code="AC.01", score=0.95,
                                      weight=0.95))
        # (0.9*0.9 + 0.95*0.95) / (0.9+0.95) * 1.10 (consensus bonus)
        raw = (0.9*0.9 + 0.95*0.95) / (0.9 + 0.95)
        expected = min(raw * 1.10, 1.0)
        r = Scorer().score([c])[0]
        assert r.score == pytest.approx(round(expected, 4), abs=1e-3)

    def test_no_evidence_scores_zero(self):
        c = Candidate(code="X", name="Sin evidencia")
        r = Scorer().score([c])[0]
        assert r.score == 0.0
        assert r.confidence == "UNKNOWN"

    def test_ranking_order(self):
        a = Candidate(code="AC.01", name="A")
        a.add_evidence(EvidenceSource(layer="catalog_exact", code="AC.01", score=1.0, weight=1.0))
        b = Candidate(code="AC.02", name="B")
        b.add_evidence(EvidenceSource(layer="synonyms_fuzzy", code="AC.02", score=0.4, weight=0.7))
        ranked = Scorer().score([b, a])
        assert [r.code for r in ranked] == ["AC.01", "AC.02"]
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2

    def test_confidence_label(self):
        s = Scorer()
        assert s.confidence_label(0.99) == "EXACT"
        assert s.confidence_label(0.90) == "VERY_HIGH"
        assert s.confidence_label(0.80) == "HIGH"
        assert s.confidence_label(0.60) == "MEDIUM"
        assert s.confidence_label(0.40) == "LOW"
        assert s.confidence_label(0.1) == "UNKNOWN"


# ---------------------------------------------------------------------------
# CandidateGenerator
# ---------------------------------------------------------------------------


class TestCandidateGenerator:
    def test_code_layer(self, loader):
        gen = CandidateGenerator(loader=loader)
        cands = gen.generate("Banco Bci", account_code="1-01-01-02-01")
        assert any(c.code == "AC.01" and c.has_layer("code") for c in cands)

    def test_catalog_exact_layer(self, loader):
        gen = CandidateGenerator(loader=loader)
        cands = gen.generate("Caja y Bancos")
        ac01 = next(c for c in cands if c.code == "AC.01")
        assert ac01.has_layer("catalog_exact")
        ev = next(e for e in ac01.evidence if e.layer == "catalog_exact")
        assert ev.score == 1.0
        assert ev.source == "catalogo_maestro.json"

    def test_synonyms_exact_layer(self, loader):
        gen = CandidateGenerator(loader=loader)
        cands = gen.generate("caja general")
        assert any(c.code == "AC.01" and c.has_layer("synonyms_exact") for c in cands)

    def test_special_rules_layer(self, loader):
        gen = CandidateGenerator(loader=loader)
        cands = gen.generate("Cuenta Particular Socios")
        assert any(c.has_layer("special_rules") for c in cands)

    def test_context_boost(self, loader, balance_context):
        gen = CandidateGenerator(loader=loader)
        with_ctx = gen.generate("Caja y Bancos", context=balance_context)
        without_ctx = gen.generate("Caja y Bancos")
        ac01_w = next(c for c in with_ctx if c.code == "AC.01")
        ac01_o = next(c for c in without_ctx if c.code == "AC.01")
        assert ac01_w.has_layer("context")
        assert not ac01_o.has_layer("context")

    def test_context_does_not_create_candidates(self, loader):
        gen = CandidateGenerator(loader=loader)
        # Contexto por sí solo no propone códigos nuevos
        cands = gen.generate("Palabra Inventada Xyz", context={
            "family": "BALANCE_ESTANDAR",
            "document_type": "BALANCE_GENERAL",
        })
        assert cands == []

    def test_resultados_context_only_boosts_resultados(self, loader, resultados_context):
        gen = CandidateGenerator(loader=loader)
        cands = gen.generate("Ingresos por ventas", context=resultados_context)
        # ER.01 debe tener contexto; un candidato balance no debería
        for c in cands:
            if c.has_layer("context"):
                assert c.tipo_estado == "resultados"

    def test_max_candidates_limit(self, loader):
        gen = CandidateGenerator(
            loader=loader, gen_config=CandidateGeneratorConfig(max_candidates=3)
        )
        cands = gen.generate("Caja y Bancos")
        assert len(cands) <= 3

    def test_disabled_layers(self, loader):
        gen = CandidateGenerator(
            loader=loader,
            gen_config=CandidateGeneratorConfig(
                enable_catalog_exact=False,
                enable_synonyms_exact=False,
                enable_synonyms_fuzzy=False,
                enable_special_rules=False,
                enable_code=False,
            ),
        )
        cands = gen.generate("Caja y Bancos", account_code="1-01-01-02-01")
        assert cands == []

    def test_empty_name_no_candidates(self, loader):
        gen = CandidateGenerator(loader=loader)
        assert gen.generate("") == []

    def test_no_knowledge_degrades(self, tmp_path):
        l = KnowledgeLoader(
            catalogo_path=str(tmp_path / "nope.json"),
            synonyms_path=str(tmp_path / "nope.json"),
        )
        gen = CandidateGenerator(loader=l)
        cands = gen.generate("Caja y Bancos")
        assert cands == []


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------


class TestExplainer:
    def test_explain_top1(self, engine):
        res = engine.classify("Caja y Bancos")
        assert res.explanation is not None
        assert res.explanation.reasons
        assert res.explanation.confidence_breakdown
        assert len(res.explanation.candidate_explanations) == len(res.top_n)

    def test_explain_unknown(self, engine):
        res = engine.classify("No Existe Cuenta Zzz")
        assert res.top_code is None
        assert res.explanation.reasons
        assert any("no hay evidencia" in r for r in res.explanation.reasons)

    def test_candidate_explanations_have_layers(self, engine):
        res = engine.classify("Caja y Bancos")
        ce = res.explanation.candidate_explanations[0]
        assert ce["code"] == "AC.01"
        assert ce["rank"] == 1
        assert "layers" in ce


# ---------------------------------------------------------------------------
# DecisionEngine end-to-end
# ---------------------------------------------------------------------------


class TestDecisionEngine:
    def test_exact_classification(self, engine):
        res = engine.classify("Caja y Bancos")
        assert res.top_code == "AC.01"
        assert res.confidence == "EXACT"
        assert res.account_tipo == "balance"
        assert res.decision_source in ("catalog_exact", "code", "synonyms_exact")

    def test_code_classification(self, engine):
        res = engine.classify("Banco Bci", account_code="1-01-01-02-01")
        assert res.top_code == "AC.01"
        assert res.decision_source == "code"

    def test_unknown_no_candidates(self, engine):
        res = engine.classify("Nada Que Ver Aqui 12345")
        assert res.top_code is None
        assert res.confidence == "UNKNOWN"
        assert res.decision_source == "UNKNOWN"
        assert len(res.top_n) == 1
        assert res.top_n[0].code is None

    def test_always_returns_top_n(self, engine):
        res = engine.classify("Caja y Bancos")
        assert 1 <= len(res.top_n) <= engine.config.top_n
        assert res.top_n[0].rank == 1

    def test_top_n_honors_config(self, loader):
        cfg = WeightConfig(top_n=3)
        eng = DecisionEngine(loader=loader, config=cfg)
        res = eng.classify("Caja y Bancos")
        assert len(res.top_n) <= 3

    def test_serialization_full(self, engine):
        res = engine.classify("Caja y Bancos")
        d = res.to_dict()
        assert d["top_code"] == "AC.01"
        assert d["explanation"] is not None
        assert d["top_n"][0]["rank"] == 1
        assert "timestamp" in d

    def test_custom_weights_change_score(self, loader):
        cfg = WeightConfig.from_dict({
            "weights": {"catalog_exact": 1.0, "synonyms_fuzzy": 0.1,
                        "synonyms_exact": 1.0, "code": 1.0, "special_rules": 1.0,
                        "context": 0.0, "extractor": 0.0, "profile": 0.0},
        })
        eng = DecisionEngine(loader=loader, config=cfg)
        res = eng.classify("Caja y Bancos")
        assert res.top_code == "AC.01"

    def test_reconstruction_from_dict(self, engine):
        res = engine.classify("Caja y Bancos")
        d = res.to_dict()
        assert d["top_n"][0]["evidence"]  # toda la evidencia está trazada
        for ev in d["top_n"][0]["evidence"]:
            assert ev["layer"]
            assert "score" in ev
            assert "source" in ev


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_compute_metrics_hits(self, engine):
        results = [
            engine.classify("Caja y Bancos"),
            engine.classify("Ingresos por ventas"),
            engine.classify("No Existe 9999"),
        ]
        expected = {
            "Caja y Bancos": "AC.01",
            "Ingresos por ventas": "ER.01",
            "No Existe 9999": None,
        }
        m = compute_metrics(results, expected)
        assert m.total == 3
        assert m.top1_hits >= 1
        assert m.top1_accuracy > 0
        assert m.top5_accuracy > 0
        assert m.mrr > 0
        assert m.coverage == pytest.approx(2 / 3, abs=0.01)
        assert m.confidence_distribution

    def test_compute_metrics_empty(self):
        m = compute_metrics([], {})
        assert m.total == 0
        assert m.top1_accuracy == 0.0
        assert m.mrr == 0.0

    def test_metrics_to_dict(self, engine):
        res = engine.classify("Caja y Bancos")
        m = compute_metrics([res], {"Caja y Bancos": "AC.01"})
        d = m.to_dict()
        assert d["total"] == 1
        assert "top1_accuracy" in d
