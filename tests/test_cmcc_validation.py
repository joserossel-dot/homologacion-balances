from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from knowledge.cmcc_validation.validator import CMCCValidator


def make_csv(src: str) -> str:
    """Strip leading whitespace from multi-line string for test readability."""
    return "\n".join(line.strip() for line in src.strip().splitlines())


@pytest.fixture
def fixtures(tmp_path: Path):
    hc = tmp_path / "high_confidence.xlsx"
    cs = tmp_path / "concept_suggestions.xlsx"
    cmcc = tmp_path / "cmcc.json"

    pd.DataFrame([
        {"id": "VC001", "members": "Proveedores Locales | Proveedores del Exterior | Proveedores Varios",
         "n_members": 3, "frecuencia": 15, "n_empresas": 5, "monto_acumulado": 100000.0,
         "suggested_concept": "PC.01 — Proveedores", "confidence": 1.0},
        {"id": "VC002", "members": "Capital Social | Capital Suscripto | Capital Autorizado",
         "n_members": 3, "frecuencia": 20, "n_empresas": 8, "monto_acumulado": 500000.0,
         "suggested_concept": "PAT.01 — Capital", "confidence": 0.95},
        {"id": "VC003", "members": "Gastos Administrativos | Gastos de Admin.",
         "n_members": 2, "frecuencia": 10, "n_empresas": 3, "monto_acumulado": 30000.0,
         "suggested_concept": "ER.04 — Gastos de Administración", "confidence": 0.85},
        {"id": "VC004", "members": "Maquinaria | Equipo de Oficina",
         "n_members": 2, "frecuencia": 4, "n_empresas": 2, "monto_acumulado": 75000.0,
         "suggested_concept": "ANC.01 — Activo Fijo", "confidence": 0.70},
        {"id": "VC005", "members": "Ingresos por Ventas | Ventas Netas",
         "n_members": 2, "frecuencia": 3, "n_empresas": 1, "monto_acumulado": 200000.0,
         "suggested_concept": "ER.01 — Ingresos", "confidence": 0.60},
    ]).to_excel(hc, index=False)

    pd.DataFrame([
        {"id": "VC001", "members_sample": "Proveedores Locales | Proveedores del Exterior",
         "n_members": 3, "frecuencia": 15, "suggested_concept": "PC.01 — Proveedores", "confidence": 1.0},
        {"id": "VC002", "members_sample": "Capital Social | Capital Suscripto",
         "n_members": 3, "frecuencia": 20, "suggested_concept": "PAT.01 — Capital", "confidence": 0.95},
        {"id": "VC003", "members_sample": "Gastos Administrativos",
         "n_members": 2, "frecuencia": 10, "suggested_concept": "ER.04 — Gastos de Administración", "confidence": 0.85},
    ]).to_excel(cs, index=False)

    cmcc_data = {
        "conceptos": [
            {"codigo": "PC.01", "nombre": "Proveedores",
             "variantes": ["Proveedores Locales", "Proveedores"]},
            {"codigo": "PAT.01", "nombre": "Capital",
             "variantes": ["Capital Social", "Capital"]},
        ]
    }
    with open(cmcc, "w", encoding="utf-8") as f:
        json.dump(cmcc_data, f)

    return hc, cs, cmcc


class TestCMCCValidator:
    def test_init(self):
        v = CMCCValidator("hc.xlsx", "cs.xlsx", "cmcc.json")
        assert v.hc_path.name == "hc.xlsx"
        assert v.cs_path.name == "cs.xlsx"
        assert v.cmcc_path.name == "cmcc.json"
        assert v.entries == []

    def test_load(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        assert v.total_entries == 5

    def test_load_sorted_by_impact(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        impacts = [e["Impacto"] for e in v.entries]
        assert impacts == sorted(impacts, reverse=True)

    def test_impact_calculation(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        # VC002 (20*8*0.95=152) sorts before VC001 (15*5*1.0=75)
        assert v.entries[0]["Cluster ID"] == "VC002"
        assert v.entries[0]["Impacto"] == 152.0
        assert v.entries[1]["Cluster ID"] == "VC001"
        assert v.entries[1]["Impacto"] == 75.0

    def test_entries_have_all_fields(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        for e in v.entries:
            assert "Cluster ID" in e
            assert "Concepto sugerido" in e
            assert "Código sugerido" in e
            assert "Confianza" in e
            assert "Impacto" in e
            assert "Frecuencia" in e
            assert "Empresas" in e
            assert "Variantes detectadas" in e
            assert "Decisión" in e
            assert "Código definitivo" in e
            assert e["Decisión"] == ""
            assert e["Código definitivo"] == ""
            assert isinstance(e["Confianza"], float)
            assert isinstance(e["Impacto"], float)

    def test_decision_fields_empty(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        for e in v.entries:
            assert e["Decisión"] == ""
            assert e["Código definitivo"] == ""

    def test_code_extracted_from_concept(self, fixtures):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        # VC002 (PAT.01) sorts first by impact
        assert v.entries[0]["Código sugerido"] == "PAT.01"
        assert v.entries[1]["Código sugerido"] == "PC.01"

    def test_code_empty_when_no_dash(self, tmp_path):
        hc = tmp_path / "hc.xlsx"
        cs = tmp_path / "cs.xlsx"
        pd.DataFrame([
            {"id": "VC001", "members": "A", "n_members": 1, "frecuencia": 1,
             "n_empresas": 1, "monto_acumulado": 0.0,
             "suggested_concept": "Proveedores", "confidence": 1.0},
        ]).to_excel(hc, index=False)
        pd.DataFrame([
            {"id": "VC001", "members_sample": "A", "n_members": 1,
             "frecuencia": 1, "suggested_concept": "Proveedores", "confidence": 1.0},
        ]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        assert v.entries[0]["Código sugerido"] == ""

    @pytest.mark.parametrize("n", [1, 3, 5, 10, 50])
    def test_top_n(self, fixtures, n):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        top = v.top_n(n)
        assert len(top) == min(n, v.total_entries)
        if top:
            assert top[0]["Impacto"] >= top[-1]["Impacto"]

    def test_top_n_empty_when_no_entries(self):
        v = CMCCValidator(Path("/tmp/nonexistent"), Path("/tmp/nonexistent"))
        assert v.top_n(5) == []

    def test_generate_reports_all_files(self, fixtures, tmp_path):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        reports = v.generate_reports(tmp_path)

        expected = ["review_package.xlsx", "top100.xlsx", "top200.xlsx",
                     "top400.xlsx", "validation_statistics.json", "review_summary.md"]
        for name in expected:
            path = reports.get(name.replace(".", "_") if name.endswith(".md") else name.replace(".", "_"))
            if path is None:
                path = tmp_path / name
            assert (tmp_path / name).exists(), f"{name} not found"

    def test_review_package_columns(self, fixtures, tmp_path):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        v.generate_reports(tmp_path)
        df = pd.read_excel(tmp_path / "review_package.xlsx")
        assert "Cluster ID" in df.columns
        assert "Decisión" in df.columns
        assert "Código definitivo" in df.columns
        assert "Impacto" in df.columns
        assert "Variantes detectadas" in df.columns

    def test_statistics_json(self, fixtures, tmp_path):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        v.generate_reports(tmp_path)
        with open(tmp_path / "validation_statistics.json") as f:
            stats = json.load(f)
        assert stats["total_entries"] == 5
        assert stats["total_variants"] == 12
        assert stats["total_frequency"] == 52
        assert stats["max_impact"] > 0
        assert "impact_distribution" in stats
        assert "confidence_distribution" in stats
        assert "top_codes" in stats
        assert "top_concepts" in stats
        assert "generated_at" in stats

    def test_statistics_distributions(self, fixtures, tmp_path):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        v.generate_reports(tmp_path)
        with open(tmp_path / "validation_statistics.json") as f:
            stats = json.load(f)
        # All 5 entries have confidence >= 0.95 -> all in 0.95-1.0
        # VC001 (1.0) and VC002 (0.95) → 2 in 0.95-1.0
        assert stats["confidence_distribution"].get("0.95-1.0", 0) >= 2
        idist = stats["impact_distribution"]
        total_in_buckets = sum(idist.values())
        assert total_in_buckets == 5

    def test_review_summary_content(self, fixtures, tmp_path):
        hc, cs, _ = fixtures
        v = CMCCValidator(hc, cs)
        v.load()
        v.generate_reports(tmp_path)
        text = (tmp_path / "review_summary.md").read_text(encoding="utf-8")
        assert "# CMCC Validation Package" in text
        assert "Cómo usar" in text
        assert "Distribución por Impacto" in text
        assert "Top 5 clusters" in text
        assert "Ningún archivo del pipeline fue modificado" in text

    def test_empty_high_confidence(self, tmp_path):
        hc = tmp_path / "empty_hc.xlsx"
        cs = tmp_path / "empty_cs.xlsx"
        pd.DataFrame(columns=["id", "members", "frecuencia", "n_empresas",
                               "suggested_concept", "confidence"]).to_excel(hc, index=False)
        pd.DataFrame(columns=["id", "members_sample", "suggested_concept",
                               "confidence"]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        assert v.total_entries == 0
        reports = v.generate_reports(tmp_path)
        assert (tmp_path / "review_package.xlsx").exists()
        df = pd.read_excel(tmp_path / "review_package.xlsx")
        assert len(df) == 0

    def test_empty_statistics(self, tmp_path):
        hc = tmp_path / "empty_hc.xlsx"
        cs = tmp_path / "empty_cs.xlsx"
        pd.DataFrame(columns=["id", "members", "frecuencia", "n_empresas",
                               "suggested_concept", "confidence"]).to_excel(hc, index=False)
        pd.DataFrame(columns=["id", "members_sample", "suggested_concept",
                               "confidence"]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        v.generate_reports(tmp_path)
        with open(tmp_path / "validation_statistics.json") as f:
            stats = json.load(f)
        assert stats["total_entries"] == 0
        assert stats["max_impact"] == 0
        assert stats["min_impact"] == 0
        assert stats["avg_impact"] == 0

    def test_single_entry(self, tmp_path):
        hc = tmp_path / "single.xlsx"
        cs = tmp_path / "single_cs.xlsx"
        pd.DataFrame([
            {"id": "VC001", "members": "Proveedores Locales",
             "n_members": 1, "frecuencia": 3, "n_empresas": 1, "monto_acumulado": 1000.0,
             "suggested_concept": "PC.01 — Proveedores", "confidence": 1.0},
        ]).to_excel(hc, index=False)
        pd.DataFrame([
            {"id": "VC001", "members_sample": "Proveedores Locales",
             "n_members": 1, "frecuencia": 3, "suggested_concept": "PC.01 — Proveedores", "confidence": 1.0},
        ]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        assert v.total_entries == 1
        assert v.entries[0]["Impacto"] == 3.0

    def test_impact_precision(self, tmp_path):
        hc = tmp_path / "hc.xlsx"
        cs = tmp_path / "cs.xlsx"
        pd.DataFrame([
            {"id": "VC001", "members": "A | B", "n_members": 2,
             "frecuencia": 7, "n_empresas": 3, "monto_acumulado": 0.0,
             "suggested_concept": "ER.01 — Ingresos", "confidence": 0.85},
        ]).to_excel(hc, index=False)
        pd.DataFrame([
            {"id": "VC001", "members_sample": "A", "n_members": 2,
             "frecuencia": 7, "suggested_concept": "ER.01 — Ingresos", "confidence": 0.85},
        ]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        # 7 * 3 * 0.85 = 17.85
        assert v.entries[0]["Impacto"] == 17.85

    def test_members_example_fallback(self, tmp_path):
        hc = tmp_path / "hc.xlsx"
        cs = tmp_path / "cs.xlsx"
        pd.DataFrame([
            {"id": "VC001", "members": "Var1 | Var2 | Var3",
             "n_members": 3, "frecuencia": 5, "n_empresas": 2, "monto_acumulado": 0.0,
             "suggested_concept": "ER.01 — Ingresos", "confidence": 1.0},
        ]).to_excel(hc, index=False)
        # No corresponding row in concept_suggestions
        pd.DataFrame(columns=["id", "members_sample", "n_members", "frecuencia",
                               "suggested_concept", "confidence"]).to_excel(cs, index=False)
        v = CMCCValidator(hc, cs)
        v.load()
        assert v.entries[0]["Muestra variantes"] == "Var1 | Var2 | Var3"


class TestRunner:
    def test_import(self):
        from scripts import run_cmcc_validation
        assert hasattr(run_cmcc_validation, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_cmcc_validation")
        assert mod is not None
