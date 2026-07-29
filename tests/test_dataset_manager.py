from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from dataset_manager import (
    DATASET_ROOT,
    INBOX,
    PROCESSING,
    TRAINING,
    HOLDOUT,
    STRESS,
    PILOT,
    ARCHIVE,
    REJECTED,
    init_db,
    scan_inbox,
    register_dataset,
    _register,
    _sha256,
    _infer_company,
    _infer_year,
    _infer_layout,
    _get_page_count,
    _ensure_dirs,
    move_to_processing,
    mark_training,
    mark_holdout,
    mark_stress,
    archive,
    reject,
    get_inventory,
    generate_inventory_report,
    register_existing_files,
)


# --- Helpers ---

def _create_dummy_pdf(path: str | Path, content: bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _count_db_rows(db_path: str | Path) -> int:
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM dataset_files").fetchone()[0]
    conn.close()
    return count


# --- Fixtures ---

@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


# --- Test init_db ---

class TestInitDb:
    def test_init_creates_table(self, tmp_db):
        conn = sqlite3.connect(str(tmp_db))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        assert ("dataset_files",) in tables

    def test_init_creates_dirs(self, tmp_path):
        test_root = tmp_path / "datasets"
        import dataset_manager as dm
        orig = dm.DATASET_ROOT
        dm.DATASET_ROOT = test_root
        dm.init_db(str(tmp_path / "test.db"))
        for fname in ["INBOX", "PROCESSING", "TRAINING", "HOLDOUT",
                       "STRESS/8_COLUMNS", "PILOT", "ARCHIVE", "REJECTED"]:
            assert (test_root / fname).exists()
        dm.DATASET_ROOT = orig


# --- Test _sha256 ---

class TestSha256:
    def test_sha256_consistent(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"hello world")
        h1 = _sha256(f)
        h2 = _sha256(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_sha256_changes(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"content a")
        h1 = _sha256(f)
        f.write_bytes(b"content b")
        h2 = _sha256(f)
        assert h1 != h2


# --- Test _infer_company ---

class TestInferCompany:
    def test_known_company(self):
        assert "AICSA" in _infer_company("Balance AICSA 2019.pdf")

    def test_company_with_ltda(self):
        result = _infer_company("Balance Transportes Libardon Ltda 2015.pdf")
        assert "Libardon" in result

    def test_company_stopwords_removed(self):
        result = _infer_company("BALANCE CLASIFICADO AICSA 2019.pdf")
        assert "AICSA" in result
        assert "balance" not in result.lower()

    def test_no_inference_possible(self):
        result = _infer_company("2019.pdf")
        assert result == "2019"

    def test_empty_filename(self):
        result = _infer_company(".pdf")
        assert result == ".pdf"


# --- Test _infer_year ---

class TestInferYear:
    def test_year_in_filename(self):
        assert _infer_year("Balance 2019.pdf") == 2019

    def test_multiple_years(self):
        assert _infer_year("Balance 2011-2012.pdf") == 2012

    def test_no_year(self):
        assert _infer_year("Balance.pdf") is None

    def test_short_year(self):
        assert _infer_year("Balance 99.pdf") is None


# --- Test _infer_layout ---

class TestInferLayout:
    def test_clasificado(self):
        assert _infer_layout("Balance Clasificado 2019.pdf") == "clasificado"

    def test_original(self):
        assert _infer_layout("Balance Original.pdf") == "original"

    def test_8_columnas(self):
        assert _infer_layout("Balance 8 Columnas.pdf") == "8_columnas"

    def test_resultados(self):
        assert _infer_layout("Estado Resultados.pdf") == "resultados"

    def test_general(self):
        assert _infer_layout("Balance General.pdf") == "general"

    def test_unknown(self):
        assert _infer_layout("Mi Archivo.pdf") == "unknown"


# --- Test _get_page_count ---

class TestGetPageCount:
    def test_non_pdf_returns_zero(self, tmp_path):
        f = tmp_path / "not_a_pdf.pdf"
        f.write_text("not a pdf")
        assert _get_page_count(f) == 0

    def test_minimal_pdf(self, tmp_path):
        minimal_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"startxref\n190\n%%EOF"
        )
        f = tmp_path / "minimal.pdf"
        f.write_bytes(minimal_pdf)
        assert _get_page_count(f) > 0


# --- Test register + scan ---

class TestRegisterAndScan:
    def test_register_pdf(self, tmp_path, tmp_db):
        f = _create_dummy_pdf(tmp_path / "test.pdf")
        rid = register_dataset(f, db_path=tmp_db)
        assert rid > 0
        assert _count_db_rows(tmp_db) == 1

    def test_register_duplicate_hash(self, tmp_path, tmp_db):
        content = b"same content"
        f1 = _create_dummy_pdf(tmp_path / "a.pdf", content)
        f2 = _create_dummy_pdf(tmp_path / "b.pdf", content)
        rid1 = register_dataset(f1, db_path=tmp_db)
        rid2 = register_dataset(f2, db_path=tmp_db)
        assert rid2 > 0
        assert _count_db_rows(tmp_db) == 1

    def test_scan_inbox_finds_new_pdfs(self, tmp_path, tmp_db):
        inbox = tmp_path / "INBOX"
        inbox.mkdir()
        _create_dummy_pdf(inbox / "nuevo.pdf", b"%PDF file a")
        _create_dummy_pdf(inbox / "otro.pdf", b"%PDF file b")
        _create_dummy_pdf(inbox / "not_pdf.txt", b"text file")

        import dataset_manager as dm
        original = dm.INBOX
        dm.INBOX = inbox
        dm.DATASET_DB = tmp_db

        try:
            new = dm.scan_inbox(db_path=tmp_db)
            assert len(new) == 2
            assert _count_db_rows(tmp_db) == 2
        finally:
            dm.INBOX = original

    def test_scan_inbox_skips_duplicates(self, tmp_path, tmp_db):
        inbox = tmp_path / "INBOX"
        inbox.mkdir()
        content = b"duplicate"
        _create_dummy_pdf(inbox / "a.pdf", content)
        _create_dummy_pdf(inbox / "b.pdf", content)

        import dataset_manager as dm
        original = dm.INBOX
        dm.INBOX = inbox
        dm.DATASET_DB = tmp_db

        try:
            new = dm.scan_inbox(db_path=tmp_db)
            assert len(new) == 1
        finally:
            dm.INBOX = original


# --- Test move operations ---

class TestMoveOperations:
    def test_move_to_processing(self, tmp_path, tmp_db):
        inbox = tmp_path / "INBOX"
        inbox.mkdir()
        processing = tmp_path / "PROCESSING"
        processing.mkdir()
        src = _create_dummy_pdf(inbox / "moveme.pdf")

        import dataset_manager as dm
        original_inbox = dm.INBOX
        original_processing = dm.PROCESSING
        dm.INBOX = inbox
        dm.PROCESSING = processing
        dm.DATASET_DB = tmp_db

        try:
            _register(
                "moveme.pdf", _sha256(src), "inbox",
                current_folder=str(inbox),
                db_path=tmp_db,
            )
            result = dm.move_to_processing("moveme.pdf", db_path=tmp_db)
            assert result["success"]
            assert result["status"] == "processing"
            assert not src.exists()
            assert (processing / "moveme.pdf").exists()
        finally:
            dm.INBOX = original_inbox
            dm.PROCESSING = original_processing

    def test_move_updates_db(self, tmp_path, tmp_db):
        src = _create_dummy_pdf(tmp_path / "test.pdf")
        _register(
            "test.pdf", _sha256(src), "inbox",
            current_folder=str(tmp_path),
            db_path=tmp_db,
        )
        target = tmp_path / "TARGET"
        target.mkdir()

        import dataset_manager as dm
        original = dm.PROCESSING
        dm.PROCESSING = target
        dm.DATASET_DB = tmp_db

        try:
            dm.move_to_processing("test.pdf", db_path=tmp_db)
            conn = sqlite3.connect(str(tmp_db))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, current_folder FROM dataset_files WHERE filename='test.pdf'"
            ).fetchone()
            conn.close()
            assert row["status"] == "processing"
            assert "TARGET" in row["current_folder"]
        finally:
            dm.PROCESSING = original

    def test_move_nonexistent_file(self, tmp_db):
        result = move_to_processing("nonexistent.pdf", db_path=tmp_db)
        assert not result["success"]
        assert "error" in result


# --- Test inventory ---

class TestInventory:
    def test_empty_inventory(self, tmp_db):
        inv = get_inventory(db_path=tmp_db)
        assert inv["total"] == 0
        assert inv["by_status"] == {}

    def test_inventory_counts(self, tmp_path, tmp_db):
        for i in range(3):
            f = _create_dummy_pdf(tmp_path / f"file_{i}.pdf", f"%PDF content {i}".encode())
            _register(
                f"file_{i}.pdf", _sha256(f), "inbox",
                current_folder=str(tmp_path),
                company=f"Company {i}",
                year=2020 + i,
                layout="clasificado",
                pages=i + 1,
                db_path=tmp_db,
            )
        inv = get_inventory(db_path=tmp_db)
        assert inv["total"] == 3
        assert inv["by_status"].get("inbox") == 3
        assert inv["total_companies"] == 3

    def test_inventory_report_generated(self, tmp_path, tmp_db):
        f = _create_dummy_pdf(tmp_path / "report_test.pdf")
        _register(
            "report_test.pdf", _sha256(f), "inbox",
            current_folder=str(tmp_path),
            company="TestCo",
            year=2024,
            layout="original",
            db_path=tmp_db,
        )
        report_path = tmp_path / "inventory.md"
        text = generate_inventory_report(report_path, db_path=tmp_db)
        assert "Dataset Inventory" in text
        assert "TestCo" in text
        assert "original" in text


# --- Test register_existing_files ---

class TestRegisterExisting:
    def test_register_existing(self, tmp_path, tmp_db):
        holdout = tmp_path / "HOLDOUT"
        holdout.mkdir(parents=True)
        _create_dummy_pdf(holdout / "existing.pdf")

        import dataset_manager as dm
        original = dm.HOLDOUT
        dm.HOLDOUT = holdout
        dm.DATASET_DB = tmp_db

        try:
            count = dm.register_existing_files(db_path=tmp_db)
            assert count == 1
            inv = dm.get_inventory(db_path=tmp_db)
            assert inv["total"] == 1
            assert inv["by_status"].get("holdout") == 1
        finally:
            dm.HOLDOUT = original


# --- Test _ensure_dirs ---

class TestEnsureDirs:
    def test_dirs_created(self, tmp_path):
        import dataset_manager as dm
        test_root = tmp_path / "datasets"
        original = dm.DATASET_ROOT
        dm.DATASET_ROOT = test_root

        for folder in [dm.INBOX, dm.PROCESSING, dm.TRAINING,
                       dm.HOLDOUT, dm.STRESS, dm.PILOT,
                       dm.ARCHIVE, dm.REJECTED]:
            dm._ensure_dirs()
            assert folder.exists()
        dm.DATASET_ROOT = original


class TestCLIIntegration:
    def test_scan_then_move_lifecycle(self, tmp_path, tmp_db):
        inbox = tmp_path / "INBOX"
        inbox.mkdir()
        processing = tmp_path / "PROCESSING"
        processing.mkdir()

        src = _create_dummy_pdf(inbox / "lifecycle.pdf", b"%PDF lifecycle")

        import dataset_manager as dm
        orig_inbox = dm.INBOX
        orig_processing = dm.PROCESSING
        dm.INBOX = inbox
        dm.PROCESSING = processing
        dm.DATASET_DB = tmp_db

        try:
            new = dm.scan_inbox(db_path=tmp_db)
            assert len(new) == 1
            result = dm.move_to_processing("lifecycle.pdf", db_path=tmp_db)
            assert result["success"]
            conn = sqlite3.connect(str(tmp_db))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, current_folder FROM dataset_files WHERE filename='lifecycle.pdf'"
            ).fetchone()
            conn.close()
            assert row["status"] == "processing"
        finally:
            dm.INBOX = orig_inbox
            dm.PROCESSING = orig_processing
