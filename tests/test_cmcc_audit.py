from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from knowledge.cmcc_audit.auditor import CMCCAuditor


def make_cmcc_fixture(tmp_path: Path) -> Path:
    cmcc = tmp_path / "cmcc.json"
    conceptos = [
        {"codigo": "ER.10", "nombre": "Impuesto a la Renta", "categoria": "resultado",
         "variantes": ["impuesto", "impuesto renta"], "sinonimos": [],
         "ejemplos": ["Impuesto a la Renta 2023", "Impuesto Renta"], "empresas": [],
         "metadata": {}},
        {"codigo": "PNC.02", "nombre": "Leasing LP", "categoria": "pasivo_no_corriente",
         "variantes": ["leasing lp", "arriendo financiero lp"], "sinonimos": ["arriendo lp"],
         "ejemplos": ["Leasing LP Banco"], "empresas": [], "metadata": {}},
        {"codigo": "PC.01", "nombre": "Proveedores", "categoria": "pasivo_corriente",
         "variantes": ["proveedores", "proveedores varios"], "sinonimos": [],
         "ejemplos": ["Proveedores Locales"], "empresas": [], "metadata": {}},
        {"codigo": "AC.01", "nombre": "Caja y Bancos", "categoria": "activo_corriente",
         "variantes": ["caja", "bancos", "caja y bancos", "banco estado", "banco chile",
                       "banco santander", "banco bci", "banco itau", "banco internacional",
                       "banco bbva", "vale vista", "efectivo", "moneda extranjera"],
         "sinonimos": ["dinero", "efectivo"],
         "ejemplos": ["Caja General", "Banco Estado Cta Cte"], "empresas": [],
         "metadata": {}},
        {"codigo": "ER.01", "nombre": "Ventas", "categoria": "resultado",
         "variantes": ["ventas", "ingresos"], "sinonimos": [],
         "ejemplos": ["Ventas Netas"], "empresas": [], "metadata": {}},
        {"codigo": "ER.04", "nombre": "Gastos de Administración", "categoria": "resultado",
         "variantes": ["gastos admin"], "sinonimos": [],
         "ejemplos": [], "empresas": [], "metadata": {}},
    ]
    with open(cmcc, "w", encoding="utf-8") as f:
        json.dump(conceptos, f)
    return cmcc


def make_audit_fixture(tmp_path: Path) -> Path:
    ap = tmp_path / "audit_data.json"
    accounts = []
    classified_codes = ["ER.10", "ER.10", "PC.01", "AC.01", "AC.01", "AC.01"]
    classified_sources = ["file_A.pdf", "file_A.pdf", "file_B.pdf", "file_B.pdf", "file_C.pdf", "file_A.pdf"]
    for i, (code, src) in enumerate(zip(classified_codes, classified_sources)):
        accounts.append({
            "account_code": f"ACC{i:04d}",
            "account_name": f"account_{i}",
            "final_code": code,
            "standard_code": code,
            "method": "dictionary_exact",
            "classification_amount": 1000 * (i + 1),
            "source_file": src,
            "source_path": src,
        })
    for i in range(5):
        accounts.append({
            "account_code": f"UNK{i:04d}",
            "account_name": f"unknown_{i}",
            "final_code": None,
            "standard_code": None,
            "method": "unclassified",
            "classification_amount": 0,
            "source_file": f"file_F.pdf",
            "source_path": f"file_F.pdf",
        })
    data = {"accounts": accounts, "files": [], "total_elapsed": 0, "generated_at": ""}
    with open(ap, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return ap


def make_clusters_fixture(tmp_path: Path) -> Path:
    cp = tmp_path / "clusters.xlsx"
    pd.DataFrame([
        {"id": "VC001", "n_members": 3, "members": "A | B | C", "frecuencia": 10,
         "n_empresas": 2, "monto_acumulado": 5000, "suggested_concept": "ER.10 — Impuesto a la Renta", "confidence": 0.95},
        {"id": "VC002", "n_members": 2, "members": "D | E", "frecuencia": 5,
         "n_empresas": 1, "monto_acumulado": 2000, "suggested_concept": "PC.01 — Proveedores", "confidence": 0.85},
        {"id": "VC003", "n_members": 4, "members": "F | G | H | I", "frecuencia": 15,
         "n_empresas": 3, "monto_acumulado": 8000, "suggested_concept": "PNC.02 — Leasing LP", "confidence": 0.90},
        {"id": "VC004", "n_members": 2, "members": "J | K", "frecuencia": 3,
         "n_empresas": 1, "monto_acumulado": 1000, "suggested_concept": "AC.01 — Caja y Bancos", "confidence": 0.70},
        {"id": "VC005", "n_members": 2, "members": "L | M", "frecuencia": 8,
         "n_empresas": 2, "monto_acumulado": 3000, "suggested_concept": "ER.04 — Gastos de Administración", "confidence": 0.60},
        {"id": "VC006", "n_members": 1, "members": "N", "frecuencia": 2,
         "n_empresas": 1, "monto_acumulado": 500, "suggested_concept": "ER.01 — Ventas", "confidence": 0.55},
    ]).to_excel(cp, index=False)
    return cp


def make_top_accounts_fixture(tmp_path: Path) -> Path:
    tp = tmp_path / "top_accounts.xlsx"
    pd.DataFrame([
        {"cuenta": "unknown impuesto", "frecuencia": 5, "empresas_distintas": 2, "documentos_distintos": 2, "total_montos": 10000, "longitud_nombre": 16},
        {"cuenta": "unknown leasing", "frecuencia": 3, "empresas_distintas": 1, "documentos_distintos": 1, "total_montos": 5000, "longitud_nombre": 14},
    ]).to_excel(tp, index=False)
    return tp


def make_shadow_fixture(tmp_path: Path) -> Path:
    sp = tmp_path / "cmcc_shadow.xlsx"
    pd.DataFrame([
        {"Cuenta": "impuesto pendiente", "Código sugerido": "ER.10", "Concepto": "Impuesto a la Renta", "Score": 1, "Método": "cmcc_variante", "Variante utilizada": "impuesto", "Evidencia": "matched_variante: impuesto", "Empresa": "X", "Documento": "doc1"},
        {"Cuenta": "leasing", "Código sugerido": "PNC.02", "Concepto": "Leasing LP", "Score": 1, "Método": "cmcc_variante", "Variante utilizada": "leasing lp", "Evidencia": "matched_variante: leasing lp", "Empresa": "Y", "Documento": "doc2"},
    ]).to_excel(sp, index=False)
    return sp


def make_calib_fixture(tmp_path: Path) -> Path:
    cal_dir = tmp_path / "calib"
    cal_dir.mkdir()
    pd.DataFrame([
        {"threshold": 0.90, "recovered": 50, "total": 100},
        {"threshold": 0.85, "recovered": 55, "total": 100},
    ]).to_excel(cal_dir / "threshold_comparison.xlsx", index=False)
    return cal_dir


@pytest.fixture
def fixtures(tmp_path: Path):
    cmcc = make_cmcc_fixture(tmp_path)
    audit = make_audit_fixture(tmp_path)
    clusters = make_clusters_fixture(tmp_path)
    top_acc = make_top_accounts_fixture(tmp_path)
    shadow = make_shadow_fixture(tmp_path)
    cal_dir = make_calib_fixture(tmp_path)
    return cmcc, audit, clusters, top_acc, shadow, cal_dir


class TestCMCCAuditor:
    def test_init_defaults(self):
        a = CMCCAuditor()
        assert a.cmcc_path.name == "cmcc.json"
        assert a.conceptos == []

    def test_init_custom(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(
            cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
            top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir,
        )
        assert a.cmcc_path == cmcc

    def test_load(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert len(a.conceptos) == 6
        assert len(a.entries) == 6
        assert a.total_unknown == 5

    def test_entries_have_all_fields(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        expected = ["Código", "Nombre", "N° Variantes", "N° Sinónimos", "N° Ejemplos",
                     "Empresas Distintas", "Frecuencia Total", "UNKNOWN Recuperables (Shadow)",
                     "UNKNOWN Recuperables (Clusters)", "Recuperaciones Potenciales",
                     "Score Promedio", "Score Máximo", "Score Mínimo"]
        for e in a.entries:
            for field in expected:
                assert field in e, f"Missing field: {field}"

    def test_composite_indicators_present(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        indicators = ["Coverage Score", "Knowledge Density", "Recovery Score",
                       "Ambiguity Score", "Business Impact", "ROI Score"]
        for e in a.entries:
            for ind in indicators:
                assert ind in e, f"Missing indicator: {ind}"
                assert isinstance(e[ind], (int, float))

    def test_coverage_score_range(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        for e in a.entries:
            assert 0 <= e["Coverage Score"] <= 100

    def test_roi_variants_relationship(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        # AC.01 has 13 variants (many) -> should have lower ROI than ER.10 with 2
        ac01 = next(e for e in a.entries if e["Código"] == "AC.01")
        er10 = next(e for e in a.entries if e["Código"] == "ER.10")
        assert er10["ROI Score"] > ac01["ROI Score"]

    def test_shadow_counts(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        er10 = next(e for e in a.entries if e["Código"] == "ER.10")
        assert er10["UNKNOWN Recuperables (Shadow)"] >= 1

    def test_cluster_member_counts(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        pnc02 = next(e for e in a.entries if e["Código"] == "PNC.02")
        assert pnc02["UNKNOWN Recuperables (Clusters)"] >= 4

    def test_calculation_known_values(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        pc01 = next(e for e in a.entries if e["Código"] == "PC.01")
        assert pc01["Frecuencia Total"] >= 1
        assert pc01["N° Variantes"] == 2

    def test_top10_roi_nonempty(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert len(a.top10_roi) == 6  # only 6 concepts total in fixture
        assert a.top10_roi[0]["ROI Score"] >= a.top10_roi[-1]["ROI Score"]

    def test_top10_gaps_nonempty(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert len(a.top10_gaps) == 6  # only 6 concepts in fixture
        # First entry should have lowest coverage
        assert a.top10_gaps[0]["Coverage Score"] <= a.top10_gaps[-1]["Coverage Score"]

    def test_answers_present(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert hasattr(a, "answers")
        assert "q1_most_profitable" in a.answers
        assert "q2_top5_pct" in a.answers
        assert "q5_unknown_disappear_no_parser" in a.answers

    def test_answers_reasonable(self, fixtures):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert 0 <= a.answers["q2_top5_pct"] <= 100
        assert a.answers["q5_unknown_disappear_no_parser"] >= 0

    def test_generate_reports_all_files(self, fixtures, tmp_path):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        out = tmp_path / "output"
        reports = a.generate_reports(out)
        expected = [
            "cmcc_audit.xlsx", "concept_statistics.xlsx", "concept_heatmap.xlsx",
            "coverage_curve.xlsx", "roi_matrix.xlsx", "priority_backlog.xlsx",
            "top10_roi.xlsx", "top10_gaps.xlsx", "top10_complete.xlsx",
            "concept_network.xlsx", "business_impact.xlsx",
            "cmcc_audit.md", "summary.md", "audit_statistics.json",
        ]
        for name in expected:
            assert (out / name).exists(), f"{name} not found"

    def test_statistics_json_content(self, fixtures, tmp_path):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        out = tmp_path / "output"
        a.generate_reports(out)
        with open(out / "audit_statistics.json") as f:
            s = json.load(f)
        assert s["total_concepts"] == 6
        assert s["total_variants"] >= 20
        assert "answers" in s
        assert s["total_unknown_in_audit"] == 5

    def test_markdown_content(self, fixtures, tmp_path):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        out = tmp_path / "output"
        a.generate_reports(out)
        md = (out / "cmcc_audit.md").read_text(encoding="utf-8")
        assert "CMCC Coverage Audit" in md
        assert "Conceptos más rentables" in md
        assert "Top 5 concentración" in md

    def test_summary_content(self, fixtures, tmp_path):
        cmcc, audit, clusters, top_acc, shadow, cal_dir = fixtures
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        out = tmp_path / "output"
        a.generate_reports(out)
        md = (out / "summary.md").read_text(encoding="utf-8")
        assert "Resumen Ejecutivo" in md
        assert "Archivos generados" in md

    def test_empty_audit(self, tmp_path):
        cmcc = make_cmcc_fixture(tmp_path)
        ap = tmp_path / "audit_empty.json"
        with open(ap, "w") as f:
            json.dump({"accounts": []}, f)
        clusters = make_clusters_fixture(tmp_path)
        top_acc = make_top_accounts_fixture(tmp_path)
        shadow = make_shadow_fixture(tmp_path)
        cal_dir = make_calib_fixture(tmp_path)
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=ap, clusters_path=clusters,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert a.total_unknown == 0
        assert len(a.entries) == 6

    def test_no_clusters(self, tmp_path):
        cmcc = make_cmcc_fixture(tmp_path)
        audit = make_audit_fixture(tmp_path)
        cp = tmp_path / "empty_clusters.xlsx"
        pd.DataFrame(columns=["id", "suggested_concept"]).to_excel(cp, index=False)
        top_acc = make_top_accounts_fixture(tmp_path)
        shadow = make_shadow_fixture(tmp_path)
        cal_dir = make_calib_fixture(tmp_path)
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=audit, clusters_path=cp,
                         top_accounts_path=top_acc, shadow_path=shadow, calibration_dir=cal_dir)
        a.load()
        assert a.total_unknown == 5
        for e in a.entries:
            assert e["UNKNOWN Recuperables (Clusters)"] == 0

    def test_concept_with_empresas(self, tmp_path):
        cmcc = make_cmcc_fixture(tmp_path)
        ap = tmp_path / "audit_emp.json"
        accounts = []
        for i in range(6):
            accounts.append({
                "account_code": f"A{i:04d}", "account_name": f"name_{i}",
                "final_code": "ER.10", "standard_code": "ER.10",
                "method": "exact", "classification_amount": 100,
                "source_file": f"company_{i % 3}.pdf",
                "source_path": f"company_{i % 3}.pdf",
            })
        with open(ap, "w") as f:
            json.dump({"accounts": accounts}, f)
        a = CMCCAuditor(cmcc_path=cmcc, audit_path=ap)
        a.load()
        er10 = next(e for e in a.entries if e["Código"] == "ER.10")
        assert er10["Empresas Distintas"] <= 3
        assert er10["Frecuencia Total"] == 6


class TestRunner:
    def test_import(self):
        from scripts import run_cmcc_audit
        assert hasattr(run_cmcc_audit, "main")

    def test_runner_module(self):
        import importlib
        mod = importlib.import_module("scripts.run_cmcc_audit")
        assert mod is not None
