from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from gold_import.validator import validate_template
from gold_import.versioning import GoldSnapshot
from gold_import.importer import import_gold_standard
from gold_import.models import ImportResult
from gold_import.reports import ImportReport
from gold_import.validator import ValidationResult
from gold_standard.builder import GoldBuilder
from gold_standard.models import GoldRecord


class TestValidator:
    REQUIRED = [
        "source_file", "account_name", "gold_standard_code",
        "gold_standard_name", "notes",
    ]

    def make_template(self, tmp_path: Path, rows: list[dict]) -> Path:
        df = pd.DataFrame(rows)
        p = tmp_path / "template.xlsx"
        df.to_excel(p, index=False)
        return p

    def test_valid_file(self, tmp_path):
        p = self.make_template(tmp_path, [{
            "source_file": "test.pdf", "account_name": "Caja",
            "gold_standard_code": "AC.01", "gold_standard_name": "Caja y Bancos",
            "notes": "",
        }])
        r = validate_template(p)
        assert r.valid
        assert r.total_rows == 1
        assert r.reviewed_rows == 1
        assert r.unreviewed_rows == 0

    def test_missing_file(self):
        r = validate_template("nonexistent.xlsx")
        assert not r.valid
        assert any("no encontrado" in e.message.lower() for e in r.errors)

    def test_missing_columns(self, tmp_path):
        p = self.make_template(tmp_path, [{"account_name": "Caja"}])
        r = validate_template(p)
        assert not r.valid
        col_errors = [e for e in r.errors if e.field == "columns"]
        assert len(col_errors) > 0

    def test_invalid_cmcc_code(self, tmp_path):
        p = self.make_template(tmp_path, [{
            "source_file": "test.pdf", "account_name": "Caja",
            "gold_standard_code": "INVALID", "gold_standard_name": "Caja",
            "notes": "",
        }])
        r = validate_template(p)
        assert not r.valid
        assert any("inválido" in e.message.lower() for e in r.errors)

    def test_unreviewed_rows(self, tmp_path):
        p = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja", "notes": ""},
            {"source_file": "b.pdf", "account_name": "Banco",
             "gold_standard_code": "", "gold_standard_name": "", "notes": ""},
        ])
        r = validate_template(p)
        assert r.valid
        assert r.reviewed_rows == 1
        assert r.unreviewed_rows == 1

    def test_all_unreviewed_warning(self, tmp_path):
        p = self.make_template(tmp_path, [{
            "source_file": "a.pdf", "account_name": "Caja",
            "gold_standard_code": "", "gold_standard_name": "", "notes": "",
        }])
        r = validate_template(p)
        assert r.valid
        assert len(r.warnings) > 0

    def test_duplicate_detection(self, tmp_path):
        p = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja", "notes": ""},
            {"source_file": "b.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja", "notes": ""},
        ])
        r = validate_template(p)
        assert r.valid
        assert any("duplicada" in w.lower() for w in r.warnings)

    def test_cmcc_codes_seen(self, tmp_path):
        p = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja", "notes": ""},
            {"source_file": "b.pdf", "account_name": "Proveedores",
             "gold_standard_code": "PC.01", "gold_standard_name": "Proveedores", "notes": ""},
        ])
        r = validate_template(p)
        assert "AC.01" in r.cmcc_codes_seen
        assert "PC.01" in r.cmcc_codes_seen

    def test_empty_gold_standard_name_warning(self, tmp_path):
        p = self.make_template(tmp_path, [{
            "source_file": "a.pdf", "account_name": "Caja",
            "gold_standard_code": "AC.01", "gold_standard_name": "", "notes": "",
        }])
        r = validate_template(p)
        assert r.valid
        assert any("gold_standard_name" in w for w in r.warnings)


class TestGoldSnapshot:
    def test_capture_empty_db(self, tmp_path):
        db = tmp_path / "test.db"
        snap = GoldSnapshot(str(db))
        data = snap.capture(label="test")
        assert data["total_records"] == 0
        assert data["label"] == "test"
        assert "timestamp" in data

    def test_capture_with_records(self, tmp_path):
        db = tmp_path / "test.db"
        builder = GoldBuilder(str(db))
        builder.add_record(GoldRecord(
            account_name="Caja", final_code="AC.01",
        ))
        builder.add_record(GoldRecord(
            account_name="Proveedores", final_code="PC.01",
        ))
        builder.close()

        snap = GoldSnapshot(str(db))
        data = snap.capture()
        assert data["total_records"] == 2
        assert data["reviewed_records"] == 2
        assert data["unique_codes"] == 2

    def test_save_and_load(self, tmp_path):
        db = tmp_path / "test.db"
        snap = GoldSnapshot(str(db))
        snap.capture()
        p = snap.save(tmp_path / "snapshot.json")
        assert p.exists()
        loaded = GoldSnapshot.load(p)
        assert loaded["total_records"] == 0

    def test_statistics(self, tmp_path):
        db = tmp_path / "test.db"
        builder = GoldBuilder(str(db))
        builder.add_record(GoldRecord(
            account_name="Caja", suggested_code="AC.01", final_code="AC.01",
        ))
        builder.add_record(GoldRecord(
            account_name="Banco", suggested_code="AC.01", final_code="PC.01",
        ))
        builder.close()

        snap = GoldSnapshot(str(db))
        data = snap.capture()
        assert data["statistics"]["total_records"] == 2
        assert data["statistics"]["exact_hits"] == 1  # one where suggested == final


class TestImportGoldStandard:
    def make_template(self, tmp_path: Path, rows: list[dict]) -> Path:
        df = pd.DataFrame(rows)
        p = tmp_path / "completed.xlsx"
        df.to_excel(p, index=False)
        return p

    def test_import_new_records(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja y Bancos",
             "notes": "ok", "account_code": "001", "nature": "profit",
             "parser_final_code": "AC.01", "parser_confidence": 0.98},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert result.imported == 1
        assert result.updated == 0
        assert result.total_in_template == 1
        assert result.reviewed_in_template == 1

        builder = GoldBuilder(str(db))
        records = builder.list_all()
        builder.close()
        assert len(records) == 1
        assert records[0].final_code == "AC.01"
        assert records[0].account_name == "Caja"

    def test_update_existing(self, tmp_path):
        db = tmp_path / "gold.db"
        builder = GoldBuilder(str(db))
        builder.add_record(GoldRecord(
            account_name="Caja", final_code="AC.01",
        ))
        builder.close()

        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja y Bancos",
             "notes": "updated", "account_code": "001", "nature": "profit",
             "parser_final_code": "AC.01", "parser_confidence": 0.98},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert result.imported == 0
        assert result.updated == 1

        builder = GoldBuilder(str(db))
        records = builder.list_all()
        builder.close()
        assert len(records) == 1
        assert records[0].usage_count >= 1

    def test_skips_unreviewed(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "", "gold_standard_name": "",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert result.imported == 0
        assert result.reviewed_in_template == 0

    def test_validation_errors_stop_import(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "BADCODE", "gold_standard_name": "Caja",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert len(result.errors) > 0

    def test_snapshots_generated(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert Path(result.snapshot_before).exists()
        assert Path(result.snapshot_after).exists()

    def test_reviewer_field(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), reviewer="test_user",
                                       output_dir=str(tmp_path / "out"))
        assert result.reviewer == "test_user"
        builder = GoldBuilder(str(db))
        records = builder.list_all()
        builder.close()
        assert records[0].reviewer == "test_user"

    def test_multiple_records(self, tmp_path):
        db = tmp_path / "gold.db"
        tmpl = self.make_template(tmp_path, [
            {"source_file": "a.pdf", "account_name": "Caja",
             "gold_standard_code": "AC.01", "gold_standard_name": "Caja",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
            {"source_file": "b.pdf", "account_name": "Proveedores",
             "gold_standard_code": "PC.01", "gold_standard_name": "Proveedores",
             "notes": "", "account_code": "", "nature": "",
             "parser_final_code": "", "parser_confidence": ""},
        ])
        result = import_gold_standard(tmpl, db_path=str(db), output_dir=str(tmp_path / "out"))
        assert result.imported == 2

        builder = GoldBuilder(str(db))
        assert len(builder.list_all()) == 2
        builder.close()

    def test_import_result_to_dict(self):
        r = ImportResult(
            total_in_template=10, reviewed_in_template=5,
            imported=3, updated=1,
        )
        d = r.to_dict()
        assert d["total_in_template"] == 10
        assert d["imported"] == 3


class TestImportReport:
    def make_result(self) -> ImportResult:
        return ImportResult(
            total_in_template=5, reviewed_in_template=3,
            imported=2, updated=1, reviewer="test",
        )

    def make_snapshot(self, total: int = 0) -> dict:
        return {
            "total_records": total,
            "reviewed_records": total,
            "unique_codes": total,
            "statistics": {"total_records": total, "exact_hits": 0, "conflicts": 0},
            "code_distribution": {},
            "conflicts": [],
        }

    def make_validation(self) -> ValidationResult:
        r = ValidationResult(valid=True, total_rows=5, reviewed_rows=3, filename="test.xlsx")
        return r

    def test_export_md(self, tmp_path):
        r = ImportReport(
            result=self.make_result(),
            snap_before=self.make_snapshot(0),
            snap_after=self.make_snapshot(2),
            validation=self.make_validation(),
            output_dir=str(tmp_path),
        )
        p = r.export_md()
        assert Path(p).exists()
        content = Path(p).read_text()
        assert "Reporte de Importación" in content
        assert "2" in content  # imported count

    def test_export_xlsx(self, tmp_path):
        r = ImportReport(
            result=self.make_result(),
            snap_before=self.make_snapshot(0),
            snap_after=self.make_snapshot(2),
            validation=self.make_validation(),
            output_dir=str(tmp_path),
        )
        p = r.export_xlsx()
        assert Path(p).exists()
        df = pd.read_excel(p)
        assert len(df) > 0
