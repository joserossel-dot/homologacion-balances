from __future__ import annotations

import csv
import sqlite3
import tempfile
from pathlib import Path

import pytest

from analysis.review_priority import (
    _load_unknowns_all,
    _infer_familia,
    compute_priorities,
    estimate_impact,
    run_prioritization,
    export_prioritized_csv,
    generate_report,
)
from review_workspace.pre_review_cleaner import classify, KEEP


class TestInferFamilia:
    def test_activo(self):
        assert _infer_familia("Caja") == "AC"
        assert _infer_familia("Banco Santander") == "AC"
        assert _infer_familia("Disponible") == "AC"
        assert _infer_familia("Inversiones") == "AC"
        assert _infer_familia("Clientes") == "AC"

    def test_activo_no_corriente(self):
        assert _infer_familia("Maquinaria") == "ANC"
        assert _infer_familia("Vehículo") == "ANC"
        assert _infer_familia("Instalaciones") == "ANC"
        assert _infer_familia("Terreno") == "ANC"

    def test_pasivo(self):
        assert _infer_familia("Proveedores") == "PC"
        assert _infer_familia("Honorarios por Pagar") == "PC"
        assert _infer_familia("PPM") == "PC"
        assert _infer_familia("IVA") == "PC"

    def test_patrimonio(self):
        assert _infer_familia("Capital Pagado") == "PAT"
        assert _infer_familia("Reserva") == "PAT"
        assert _infer_familia("Utilidades Acumuladas") == "PAT"

    def test_resultado(self):
        assert _infer_familia("Ingresos") == "ER"
        assert _infer_familia("Gastos de Administracion") == "ER"
        assert _infer_familia("Gasto") == "ER"
        assert _infer_familia("Costo") == "ER"

    def test_no_match(self):
        assert _infer_familia("XYZ") == ""


class TestLoadUnknowns:
    def test_load_all_pending(self):
        records = _load_unknowns_all()
        assert len(records) >= 700  # KEEP-only after PreReview Cleaner filter
        for r in records[:5]:
            assert "account_id" in r
            assert "nombre_original" in r
            assert "empresa" in r

    def test_load_missing_db(self):
        records = _load_unknowns_all("/nonexistent/db.db")
        assert records == []

    def test_load_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE unknown_accounts ("
                "account_id TEXT, nombre_original TEXT, empresa TEXT, archivo TEXT, "
                "codigo_original TEXT, monto REAL, confidence REAL, metodo TEXT, "
                "tipo_columna TEXT, nivel_jerarquia INTEGER, account_type TEXT, periodo TEXT, "
                "review_status TEXT)"
            )
            conn.commit()
            conn.close()
            records = _load_unknowns_all(db_path)
            assert records == []
        finally:
            Path(db_path).unlink(missing_ok=True)


class TestComputePriorities:
    def test_run_on_real_data(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        assert len(groups) >= 200
        assert len(groups) <= 700

    def test_groups_have_required_fields(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        required = [
            "grupo", "nombre_representativo", "total_occurrences",
            "distinct_companies", "distinct_years", "familia",
            "candidato_cmcc", "confianza_mejor", "prioridad", "motivo_dominante",
        ]
        for g in groups[:10]:
            for field in required:
                assert field in g, f"Missing field {field} in group"

    def test_sorted_by_priority_desc(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        for i in range(len(groups) - 1):
            assert groups[i]["prioridad"] >= groups[i + 1]["prioridad"]

    def test_group_with_multiple_variants(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        multi = [g for g in groups if g["distinct_names"] > 1]
        assert len(multi) >= 1

    def test_small_dataset(self):
        records = [
            {"account_id": "1", "nombre_original": "Caja", "empresa": "E1",
             "archivo": "a.pdf", "periodo": "2024", "codigo_original": "",
             "monto": 100.0, "confidence": 0.0, "metodo": "",
             "tipo_columna": "", "nivel_jerarquia": 0, "account_type": ""},
            {"account_id": "2", "nombre_original": "Caja Chica", "empresa": "E1",
             "archivo": "a.pdf", "periodo": "2024", "codigo_original": "",
             "monto": 50.0, "confidence": 0.0, "metodo": "",
             "tipo_columna": "", "nivel_jerarquia": 0, "account_type": ""},
            {"account_id": "3", "nombre_original": "Banco", "empresa": "E2",
             "archivo": "b.pdf", "periodo": "2023", "codigo_original": "",
             "monto": 200.0, "confidence": 0.0, "metodo": "",
             "tipo_columna": "", "nivel_jerarquia": 0, "account_type": ""},
        ]
        groups = compute_priorities(records)
        assert len(groups) >= 1
        # Caja + Caja Chica should be grouped
        caja_group = [g for g in groups if "caja" in g["grupo"]]
        assert len(caja_group) >= 1


class TestEstimateImpact:
    def test_estimate_impact(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        impact = estimate_impact(groups, 10)
        assert impact["reviews"] == 10
        assert impact["groups_covered"] == 10
        assert impact["unique_accounts_covered"] >= 10
        assert 0 < impact["pct_of_unknown"] <= 100

    def test_impact_increases_with_more_reviews(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        i10 = estimate_impact(groups, 10)
        i50 = estimate_impact(groups, 50)
        assert i50["unique_accounts_covered"] >= i10["unique_accounts_covered"]

    def test_impact_zero_groups(self):
        impact = estimate_impact([], 10)
        assert impact["reviews"] == 10
        assert impact["groups_covered"] == 0
        assert impact["unique_accounts_covered"] == 0


class TestRunPrioritization:
    def test_run_returns_all_fields(self):
        result = run_prioritization()
        assert "total_records" in result
        assert "total_groups" in result
        assert "total_unknown" in result
        assert "groups" in result
        assert "impact_20" in result
        assert "impact_50" in result
        assert "impact_100" in result
        assert "impact_200" in result

    def test_total_records_and_unknown(self):
        result = run_prioritization()
        assert result["total_records"] >= 700  # KEEP-only filter applied
        assert result["total_groups"] >= 200
        assert result["total_records"] >= result["total_unknown"]


class TestPreReviewIntegration:
    def test_no_non_keep_leaks_in_load(self):
        records = _load_unknowns_all()
        for r in records:
            cat = classify(r.get("nombre_original", ""), r.get("nivel_jerarquia", 0))
            assert cat == KEEP, f"Record {r['account_id']} leaked: {r['nombre_original']} → {cat}"

    def test_no_non_keep_leaks_in_groups(self):
        records = _load_unknowns_all()
        groups = compute_priorities(records)
        for g in groups:
            assert g["motivo_dominante"] != "TOTAL"
            assert g["motivo_dominante"] != "COMPANY_NAME"
            assert g["motivo_dominante"] != "PAGE"


class TestExportCsv:
    def test_csv_generated(self):
        result = run_prioritization()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            out_path = f.name
        try:
            count = export_prioritized_csv(result, out_path)
            assert count == result["total_groups"]
            with open(out_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == result["total_groups"]
                assert "prioridad" in rows[0]
                assert "nombre_representativo" in rows[0]
        finally:
            Path(out_path).unlink(missing_ok=True)


class TestReport:
    def test_report_generated(self):
        result = run_prioritization()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_report(result, output_path=out_path)
            assert "Backlog Inteligente" in text
            assert "Top 100" in text
            assert "Estimación de impacto" in text
            assert "Distribución por familia" in text
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_report_includes_impacts(self):
        result = run_prioritization()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_report(result, output_path=out_path)
            assert "20" in text
            assert "50" in text
            assert "100" in text
            assert "200" in text
        finally:
            Path(out_path).unlink(missing_ok=True)
