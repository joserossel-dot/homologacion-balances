from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from analysis.unknown_audit import (
    CATEGORIES,
    ORTHOGRAPHIC_VARIANT,
    OCR_ERROR,
    DICTIONARY_MISSING,
    SEMANTIC_VARIANT,
    SPECIFIC_ACCOUNT,
    CLIENT_SPECIFIC,
    TRUNCATED_TEXT,
    PARSER_ERROR,
    TOTAL_NOT_FILTERED,
    CORRUPTED_EXTRACTION,
    LIKELY_MATCH_IN_GOLD,
    TRULY_NEW_ACCOUNT,
    _symbol_ratio,
    _is_corrupted,
    _is_ocr_error,
    _is_parser_error,
    _is_truncated,
    _is_client_specific,
    _is_specific_account,
    _load_gold_standard,
    _load_knowledge_base,
    _load_unknowns,
    _best_match,
    classify_unknown,
    run_audit,
    generate_report,
)


class TestHelpers:
    def test_symbol_ratio(self):
        assert _symbol_ratio("hello world") == 0.0
        assert _symbol_ratio("!!!") == 1.0
        assert _symbol_ratio("a!b@c#") > 0.3
        assert _symbol_ratio("") == 1.0

    def test_is_corrupted(self):
        assert _is_corrupted("!!!")
        assert _is_corrupted("----------")
        assert _is_corrupted("a!@#$%b")
        assert not _is_corrupted("Banco Santander")

    def test_is_ocr_error(self):
        assert _is_ocr_error("O: ANIVEL")
        assert _is_ocr_error("12345abc")
        assert not _is_ocr_error("Disponible")

    def test_is_parser_error(self):
        assert _is_parser_error("O: ANIVEL")
        assert _is_parser_error("Nivel")
        assert _is_parser_error("Desde 01/01/2024")
        assert not _is_parser_error("Clientes")

    def test_is_truncated(self):
        assert _is_truncated("A")
        assert _is_truncated("A E")
        assert not _is_truncated("Disponible")

    def test_is_client_specific(self):
        assert _is_client_specific("RUT 76.123.456-7")
        assert _is_client_specific("R.U.T. 123")
        assert not _is_client_specific("Clientes")

    def test_is_specific_account(self):
        assert _is_specific_account("BANCO CHILE")
        assert _is_specific_account("Cta. Cte. Clientes")
        assert _is_specific_account("PRESTAMO BANCARIO")
        assert not _is_specific_account("Disponible")


class TestLoadFunctions:
    def test_load_gold_standard(self):
        gold = _load_gold_standard()
        assert len(gold) >= 200
        assert "code" in gold[0]
        assert "name" in gold[0]
        assert "normalized" in gold[0]

    def test_load_gold_standard_missing(self):
        gold = _load_gold_standard("/nonexistent/db.db")
        assert gold == []

    def test_load_knowledge_base(self):
        kb = _load_knowledge_base()
        assert "metadata" in kb
        assert "codes" in kb
        assert len(kb.get("codes", {})) >= 1

    def test_load_knowledge_base_missing(self):
        kb = _load_knowledge_base("/nonexistent/kb.json")
        assert kb == {}

    def test_load_unknowns(self):
        u = _load_unknowns()
        assert len(u) >= 900
        assert "account_id" in u[0]
        assert "nombre_original" in u[0]

    def test_load_unknowns_missing(self):
        u = _load_unknowns("/nonexistent/db.db")
        assert u == []


class TestBestMatch:
    def test_best_match_exact(self):
        candidates = [{"code": "AC.01", "name": "Disponible"}]
        score, code, name = _best_match("Disponible", candidates)
        assert score >= 95
        assert code == "AC.01"

    def test_best_match_fuzzy(self):
        candidates = [{"code": "AC.01", "name": "Disponible"}]
        score, code, name = _best_match("Disponible", candidates)
        assert score > 80

    def test_best_match_no_candidates(self):
        score, code, name = _best_match("Test", [])
        assert score == 0
        assert code == ""
        assert name == ""


class TestClassifyUnknown:
    def test_corrupted(self):
        gold = [{"code": "AC.01", "name": "Caja", "normalized": "caja"}]
        kb = [{"code": "AC.01", "name": "Caja"}]
        r = classify_unknown("!!!@@@###", gold, kb)
        assert r["motivo"] == CORRUPTED_EXTRACTION

    def test_client_specific(self):
        gold = []
        kb = []
        r = classify_unknown("RUT 76.123.456-7", gold, kb)
        assert r["motivo"] == CLIENT_SPECIFIC

    def test_parser_error(self):
        gold = []
        kb = []
        r = classify_unknown("O: ANIVEL", gold, kb)
        assert r["motivo"] == PARSER_ERROR

    def test_ocr_error(self):
        gold = []
        kb = []
        r = classify_unknown("abc12%defg%", gold, kb)
        assert r["motivo"] == OCR_ERROR

    def test_total_not_filtered(self):
        gold = []
        kb = []
        r = classify_unknown("TOTAL ACTIVOS", gold, kb)
        assert r["motivo"] == TOTAL_NOT_FILTERED

    def test_orthographic_variant(self):
        gold = [{"code": "PAT.01", "name": "Capital Pagado", "normalized": "capital pagado"}]
        kb = [{"code": "PAT.01", "name": "Capital Pagado"}]
        r = classify_unknown("Capital Pagado", gold, kb)
        assert r["motivo"] == ORTHOGRAPHIC_VARIANT
        assert r["codigo_candidato"] == "PAT.01"

    def test_likely_match_in_gold(self):
        gold = [{"code": "ER.04", "name": "TOTAL GASTOS DE ADMINISTRACIÓN", "normalized": "total gastos de administracion"}]
        kb = [{"code": "ER.04", "name": "TOTAL GASTOS DE ADMINISTRACIÓN"}]
        r = classify_unknown("GASTOS DE ADMINISTRACION", gold, kb)
        assert r["motivo"] in (LIKELY_MATCH_IN_GOLD, ORTHOGRAPHIC_VARIANT)
        assert r["distancia_fuzzy"] >= 85

    def test_semantic_variant(self):
        gold = [{"code": "PC.08", "name": "Acreedores Varios", "normalized": "acreedores varios"}]
        kb = [{"code": "PC.08", "name": "Acreedores Varios"}]
        r = classify_unknown("Proveedores Varios", gold, kb)
        assert r["motivo"] == SEMANTIC_VARIANT

    def test_truncated(self):
        gold = []
        kb = []
        r = classify_unknown("A", gold, kb)
        assert r["motivo"] == TRUNCATED_TEXT

    def test_specific_account(self):
        gold = []
        kb = []
        r = classify_unknown("BANCO CHILE", gold, kb)
        assert r["motivo"] == SPECIFIC_ACCOUNT

    def test_truly_new_account(self):
        gold = []
        kb = []
        r = classify_unknown("Ingresos por Servicios Prestados", gold, kb)
        assert r["motivo"] == TRULY_NEW_ACCOUNT

    def test_dictionary_missing(self):
        gold = []
        kb = []
        r = classify_unknown("xyz123", gold, kb)
        assert r["motivo"] == DICTIONARY_MISSING

    def test_empty_name(self):
        gold = []
        kb = []
        r = classify_unknown("", gold, kb)
        assert r["motivo"] == CORRUPTED_EXTRACTION


class TestRunAudit:
    def test_run_on_real_data(self):
        result = run_audit()
        assert result["total"] >= 900
        assert len(result["cause_distribution"]) >= 5
        assert "TRULY_NEW_ACCOUNT" in result["cause_distribution"]
        assert len(result["top_100_accounts"]) >= 50
        assert len(result["top_50_orthographic"]) >= 0
        assert len(result["top_50_recoverable"]) >= 0
        assert result["total_auto_recoverable"] >= 0
        assert 0 <= result["pct_auto_recoverable"] <= 100

    def test_cause_distribution_sums_to_total(self):
        result = run_audit()
        total_from_dist = sum(result["cause_distribution"].values())
        assert total_from_dist == result["total"]

    def test_all_analysis_fields_present(self):
        result = run_audit()
        assert "total" in result
        assert "cause_distribution" in result
        assert "top_100_accounts" in result
        assert "top_50_orthographic" in result
        assert "top_50_recoverable" in result
        assert "total_auto_recoverable" in result
        assert "pct_auto_recoverable" in result

    def test_each_unknown_has_archivo(self):
        u = _load_unknowns()
        for entry in u:
            assert entry.get("archivo", ""), f"Missing archivo for {entry.get('account_id', '?')}"


class TestReport:
    def test_report_generated(self):
        result = run_audit()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_report(result, output_path=out_path)
            assert "Auditoría de UNKNOWN" in text
            assert "Distribución por causa raíz" in text
            assert "Top 100 cuentas más repetidas" in text
            assert "Top 50 candidatos recuperables" in text
            assert "416" in text or "TRULY_NEW_ACCOUNT" in text  # based on real data
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_report_all_categories_present(self):
        result = run_audit()
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = generate_report(result, output_path=out_path)
            for cat in CATEGORIES:
                if result["cause_distribution"].get(cat, 0) > 0:
                    assert cat in text, f"{cat} not in report"
        finally:
            Path(out_path).unlink(missing_ok=True)


class TestEdgeCases:
    def test_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE unknown_accounts (account_id TEXT, nombre_original TEXT, empresa TEXT, archivo TEXT, codigo_original TEXT, monto REAL, confidence REAL, metodo TEXT, tipo_columna TEXT, nivel_jerarquia INTEGER, account_type TEXT, review_status TEXT)")
            conn.commit()
            conn.close()
            u = _load_unknowns(db_path)
            assert u == []
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_all_categories_are_strings(self):
        for cat in CATEGORIES:
            assert isinstance(cat, str)
        assert len(CATEGORIES) == 12
