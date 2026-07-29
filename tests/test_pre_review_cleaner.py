from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from review_workspace.pre_review_cleaner import (
    KEEP,
    TOTAL,
    SUBTOTAL,
    HEADER,
    FOOTER,
    PAGE,
    COMPANY_NAME,
    DATE,
    ADMIN_TEXT,
    CORRUPTED,
    SUSPECT_EXTRACTION,
    CATEGORIES,
    classify,
    load_unknowns,
    classify_records,
    export_clean_csv,
    build_report,
    run_cleaner,
)


class TestClassify:
    def test_keep_normal_account(self):
        assert classify("Banco Santander") == KEEP
        assert classify("Clientes") == KEEP
        assert classify("Capital Pagado") == KEEP
        assert classify("Maquinarias y Equipos") == KEEP

    def test_total(self):
        assert classify("TOTAL ACTIVOS") == TOTAL
        assert classify("Total Activos Circulantes") == TOTAL
        assert classify("TOTAL PASIVOS") == TOTAL
        assert classify("TOTAL PATRIMONIO") == TOTAL
        assert classify("Total General") == TOTAL
        assert classify("RESULTADO DEL EJERCICIO") == TOTAL
        assert classify("Resultado Acumulado") == TOTAL
        assert classify("UTILIDAD DEL EJERCICIO") == TOTAL
        assert classify("PÉRDIDA DEL EJERCICIO") == TOTAL
        assert classify("Perdida del Ejercicio") == TOTAL
        assert classify("TOTAL INGRESOS") == TOTAL
        assert classify("TOTAL GASTOS") == TOTAL

    def test_subtotal(self):
        assert classify("SUBTOTAL") == SUBTOTAL
        assert classify("Subtotal") == SUBTOTAL
        assert classify("Sub Total") == SUBTOTAL
        assert classify("SUB TOTAL") == SUBTOTAL
        assert classify("SUB-TOTAL") == SUBTOTAL

    def test_page(self):
        assert classify("Página 1") == PAGE
        assert classify("Pagina 2") == PAGE
        assert classify("Pág. 3") == PAGE
        assert classify("Page 10") == PAGE
        assert classify("Hoja 5") == PAGE
        assert classify("Folio 123") == ADMIN_TEXT

    def test_footer(self):
        assert classify("De la Página Anterior") == FOOTER
        assert classify("Dela Página Anterior") == FOOTER
        assert classify("Dela Pagina Anterior") == FOOTER
        assert classify("Continúa") == FOOTER
        assert classify("Viene de") == FOOTER
        assert classify("Notas a los Estados Financieros") == FOOTER
        assert classify("Total Pásina") == FOOTER

    def test_header(self):
        assert classify("") == HEADER
        assert classify("  ") == HEADER
        assert classify("EN MILES DE PESOS") == HEADER
        assert classify("Cifras en miles") == HEADER
        assert classify("Estado de Situación Financiera") == HEADER
        assert classify("Balance General") == HEADER
        assert classify("ACTIVO") == HEADER
        assert classify("PASIVO") == HEADER
        assert classify("PATRIMONIO") == HEADER

    def test_company_name(self):
        assert classify("RUT 76.123.456-7") == COMPANY_NAME
        assert classify("Razón Social: Empresa SA") == COMPANY_NAME
        assert classify("Empresa ABC LTDA") == COMPANY_NAME
        assert classify("CONTRIBUYENTE: 12345") == COMPANY_NAME

    def test_date(self):
        assert classify("Desde Enero a Diciembre") == DATE
        assert classify("Hasta Diciembre 2024") == DATE
        assert classify("Al 31/12/2024") == DATE  # slashes now allowed
        assert classify("Periodo 2024") == DATE
        assert classify("Año 2024") == DATE

    def test_admin_text(self):
        assert classify("Nivel") == ADMIN_TEXT
        assert classify("Folio N* 123") == ADMIN_TEXT
        assert classify("Nro. Cuenta") == ADMIN_TEXT
        assert classify("NÚMERO") == ADMIN_TEXT

    def test_corrupted(self):
        assert classify("A _ — — á+>=>=+=—=2211 aa ed DOOM ANP FOdio") == CORRUPTED
        assert classify("----------") == CORRUPTED

    def test_suspect_extraction(self):
        assert classify("A E") == SUSPECT_EXTRACTION
        assert classify("z z") == SUSPECT_EXTRACTION
        assert classify("] DOCUMENTOS") == SUSPECT_EXTRACTION

    def test_priority_total_over_date(self):
        assert classify("TOTAL ACTIVOS 2024") == TOTAL

    def test_priority_corrupted_over_total(self):
        assert classify("TOTAL ——— ACTIVOS ———") == CORRUPTED


class TestLoadUnknowns:
    def test_load_from_real_db(self):
        records = load_unknowns()
        assert len(records) >= 1000
        assert "account_id" in records[0]
        assert "nombre_original" in records[0]

    def test_load_missing_db(self):
        records = load_unknowns("/nonexistent/db.db")
        assert records == []

    def test_load_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_db = f.name
        try:
            conn = sqlite3.connect(empty_db)
            conn.execute("CREATE TABLE unknown_accounts (account_id TEXT, nombre_original TEXT)")
            conn.commit()
            conn.close()
            records = load_unknowns(empty_db)
            assert records == []
        finally:
            Path(empty_db).unlink(missing_ok=True)

    def test_classify_records_returns_correct_keys(self):
        records = load_unknowns()
        classifications = classify_records(records)
        assert len(classifications) == len(records)
        for c in classifications:
            assert "id" in c
            assert "nombre_original" in c
            assert "categoria" in c
            assert c["categoria"] in CATEGORIES


class TestExportCleanCsv:
    def test_export_only_keep(self):
        records = [
            {"account_id": "1", "nombre_original": "Banco Santander", "archivo": "a.pdf",
             "empresa": "E1", "periodo": "2024", "monto": 1000.0, "codigo_original": "",
             "tipo_columna": "unknown", "ruta_jerarquica": "Banco Santander",
             "padre": "", "hijos": [], "hermanos": [], "layout_detectado": "",
             "confidence": 0.0, "metodo": "unclassified", "account_type": "",
             "batch_id": "test", "pagina": 0},
            {"account_id": "2", "nombre_original": "TOTAL ACTIVOS", "archivo": "a.pdf",
             "empresa": "E1", "periodo": "2024", "monto": 50000.0, "codigo_original": "",
             "tipo_columna": "unknown", "ruta_jerarquica": "TOTAL ACTIVOS",
             "padre": "", "hijos": [], "hermanos": [], "layout_detectado": "",
             "confidence": 0.0, "metodo": "unclassified", "account_type": "",
             "batch_id": "test", "pagina": 0},
            {"account_id": "3", "nombre_original": "Página 1", "archivo": "a.pdf",
             "empresa": "E1", "periodo": "2024", "monto": 0.0, "codigo_original": "",
             "tipo_columna": "unknown", "ruta_jerarquica": "Página 1",
             "padre": "", "hijos": [], "hermanos": [], "layout_detectado": "",
             "confidence": 0.0, "metodo": "unclassified", "account_type": "",
             "batch_id": "test", "pagina": 0},
        ]
        classifications = [
            {"id": "1", "nombre_original": "Banco Santander", "categoria": KEEP},
            {"id": "2", "nombre_original": "TOTAL ACTIVOS", "categoria": TOTAL},
            {"id": "3", "nombre_original": "Página 1", "categoria": PAGE},
        ]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            out_path = f.name
        try:
            count = export_clean_csv(records, classifications, out_path)
            assert count == 1
            with open(out_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["id"] == "1"
                assert rows[0]["nombre_cuenta"] == "Banco Santander"
        finally:
            Path(out_path).unlink(missing_ok=True)


class TestRunCleaner:
    def test_run_cleaner_on_real_db(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as csv_f:
            csv_path = csv_f.name
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as rep_f:
            rep_path = rep_f.name
        try:
            result = run_cleaner(csv_path=Path(csv_path), report_path=Path(rep_path))
            assert result["total"] >= 1000
            assert result["keep"] >= 700
            assert result["removed"] >= 200
            assert result["reduction_pct"] > 0
            assert result["keep"] + result["removed"] == result["total"]
            assert Path(csv_path).exists()
            assert Path(rep_path).exists()
        finally:
            Path(csv_path).unlink(missing_ok=True)
            Path(rep_path).unlink(missing_ok=True)

    def test_run_cleaner_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_f:
            db_path = db_f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE unknown_accounts (account_id TEXT, nombre_original TEXT)")
            conn.commit()
            conn.close()
            result = run_cleaner(db_path=Path(db_path))
            assert result["total"] == 0
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_run_cleaner_missing_db(self):
        result = run_cleaner(db_path=Path("/nonexistent/db.db"))
        assert result["total"] == 0


class TestReport:
    def test_build_report(self):
        classifications = [
            {"id": "1", "nombre_original": "Banco", "categoria": KEEP},
            {"id": "2", "nombre_original": "TOTAL ACTIVOS", "categoria": TOTAL},
            {"id": "3", "nombre_original": "Página 1", "categoria": PAGE},
            {"id": "4", "nombre_original": "Cliente", "categoria": KEEP},
        ]
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            out_path = f.name
        try:
            text = build_report(classifications, output_path=Path(out_path))
            assert "Pre-Review Cleaner" in text
            assert "Total registros originales" in text
            assert "4" in text
            assert "Registros KEEP" in text
            assert "2" in text
            assert "Registros eliminados" in text
            assert "50" in text  # pct
            assert "TRAZABILIDAD" in text or "trazabilidad" in text
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_log_json_generated(self):
        result = run_cleaner()
        log_path = Path("reports/pre_review_cleaner_log.json")
        assert log_path.exists()
        with open(log_path) as f:
            log_data = json.load(f)
        assert "total" in log_data
        assert "keep" in log_data
        assert "removed" in log_data
        assert "reduction_pct" in log_data
        assert "classifications" in log_data
        assert len(log_data["classifications"]) == log_data["total"]


class TestRUTWordBoundary:
    def test_rut_not_match_inside_words(self):
        assert classify("Ganancia bruta") == KEEP
        assert classify("Margen Bruto") == KEEP
        assert classify("COSTO VENTA FRUTA") == KEEP
        assert classify("FRUTA COMERCIAL") == KEEP
        assert classify("— FLETESPRUTA") == KEEP

    def test_rut_still_matches_explicit(self):
        assert classify("RUT 76.123.456-7") == COMPANY_NAME
        assert classify("R.U.T. 76.123") == COMPANY_NAME
        assert classify("Empresa ABC LTDA") == COMPANY_NAME
        assert classify("Razón Social: Empresa SA") == COMPANY_NAME


class TestUtilidadNotTotal:
    def test_specific_accounts_with_utilidad_are_keep(self):
        assert classify("Utilidad (pérdida) en venta de activo fijo") == KEEP
        assert classify("Utilidad en venta de activo fijo") == KEEP

    def test_total_patterns_still_captured(self):
        assert classify("UTILIDAD DEL EJERCICIO") == TOTAL
        assert classify("PÉRDIDA DEL EJERCICIO") == TOTAL
        assert classify("Perdida del Ejercicio") == TOTAL


class TestEdgeCases:
    def test_total_with_junk_in_name(self):
        c = classify("Total Activo Circulante 139.560.504 PRESTAMO BANCO SECURITY")
        assert c == TOTAL

    def test_empty_string(self):
        assert classify("") == HEADER
        assert classify("   ") == HEADER

    def test_single_char(self):
        assert classify("A") == SUSPECT_EXTRACTION
        assert classify("1") == SUSPECT_EXTRACTION

    def test_suspect_bracket_prefix(self):
        assert classify("] DOCUMENTOS") == SUSPECT_EXTRACTION
        assert classify("[ SALDO") == SUSPECT_EXTRACTION

    def test_corrupted_repeated_symbols(self):
        assert classify("=== === ===") == CORRUPTED
        assert classify("----------") == CORRUPTED

    def test_real_accounts_keep(self):
        real = [
            "Disponible",
            "Inversiones",
            "Documentos por cobrar (neto)",
            "Deudores varios (neto)",
            "Construcciones y obras de infraestructura",
            "Reserva revalorización capital",
            "BANCO CHILE",
            "IVA CREDITO FISCAL",
            "GASTOS DE ADMINISTRACION",
            "Ingresos de Explotación",
        ]
        for name in real:
            assert classify(name) == KEEP, f"{name!r} debería ser KEEP, no {classify(name)}"

    def test_classify_all_categories(self):
        for cat in CATEGORIES:
            assert cat in CATEGORIES
        assert len(CATEGORIES) == 11
