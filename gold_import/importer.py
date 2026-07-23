from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from gold_import.models import ImportResult
from gold_import.validator import validate_template
from gold_import.versioning import GoldSnapshot
from gold_import.reports import ImportReport
from gold_standard.builder import GoldBuilder
from gold_standard.models import GoldRecord


_SENTINEL = object()


def _v(val: object, default: str = "") -> str:
    if val is None or val is _SENTINEL:
        return default
    if isinstance(val, float) and (math.isnan(val) or val != val):
        return default
    return str(val).strip()


def _vf(val: object, default: float = 0.0) -> float:
    if val is None or val is _SENTINEL:
        return default
    if isinstance(val, float) and (math.isnan(val) or val != val):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def import_gold_standard(
    template_path: str | Path,
    db_path: str | Path = "gold_standard.db",
    reviewer: str = "manual",
    output_dir: str | Path = "reports/gold_import",
) -> ImportResult:
    result = ImportResult(reviewer=reviewer)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Validate template ──
    validation = validate_template(template_path)
    if not validation.valid:
        result.errors = [e.message for e in validation.errors]
        result.warnings = validation.warnings
        return result

    result.total_in_template = validation.total_rows
    result.reviewed_in_template = validation.reviewed_rows
    result.unreviewed_in_template = validation.unreviewed_rows
    result.warnings = validation.warnings

    # ── Snapshot before ──
    snap_before = GoldSnapshot(db_path)
    snap_before.capture(label="before_import")
    snap_path_before = out_dir / "snapshots" / "before_import.json"
    result.snapshot_before = str(snap_before.save(snap_path_before))

    # ── Read template ──
    df = pd.read_excel(template_path)
    df.columns = [str(c).strip() for c in df.columns]
    reviewed = df[df["gold_standard_code"].notna() & (df["gold_standard_code"].astype(str).str.strip() != "")]

    # ── Import ──
    builder = GoldBuilder(str(db_path))
    now = datetime.now(timezone.utc).isoformat()

    for _, row in reviewed.iterrows():
        account_name = _v(row.get("account_name"))
        final_code = _v(row.get("gold_standard_code"))
        source_file = _v(row.get("source_file"))
        account_code_original = _v(row.get("account_code"))
        account_nature = _v(row.get("nature"))
        suggested_code = _v(row.get("parser_final_code"))
        suggested_confidence = _vf(row.get("parser_confidence"))
        notes = _v(row.get("notes"))

        record = GoldRecord(
            source_file=source_file,
            account_code_original=account_code_original,
            account_name=account_name,
            account_nature=account_nature,
            suggested_code=suggested_code,
            suggested_confidence=suggested_confidence,
            final_code=final_code,
            reviewer=reviewer,
            review_date=now,
            comments=notes,
        )

        existing = builder.find_by_name_and_code(account_name, final_code)
        if existing is not None:
            existing.increment_usage()
            existing.reviewer = reviewer
            existing.review_date = now
            existing.comments = notes
            existing.source_file = source_file
            builder.update_record(existing.id, existing)
            result.updated += 1
        else:
            builder.add_record(record)
            result.imported += 1

    builder.close()

    # ── Snapshot after ──
    snap_after = GoldSnapshot(db_path)
    snap_after.capture(label="after_import")
    snap_path_after = out_dir / "snapshots" / "after_import.json"
    result.snapshot_after = str(snap_after.save(snap_path_after))

    # ── Generate report ──
    report = ImportReport(
        result=result,
        snap_before=snap_before.data,
        snap_after=snap_after.data,
        validation=validation,
        output_dir=str(out_dir),
    )
    result.report_xlsx = report.export_xlsx()
    result.report_md = report.export_md()

    return result
