from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DATASET_ROOT = Path("datasets")
INBOX = DATASET_ROOT / "INBOX"
PROCESSING = DATASET_ROOT / "PROCESSING"
TRAINING = DATASET_ROOT / "TRAINING"
HOLDOUT = DATASET_ROOT / "HOLDOUT"
STRESS = DATASET_ROOT / "STRESS" / "8_COLUMNS"
PILOT = DATASET_ROOT / "PILOT"
ARCHIVE = DATASET_ROOT / "ARCHIVE"
REJECTED = DATASET_ROOT / "REJECTED"
DATASET_DB = DATASET_ROOT / "dataset_registry.db"

ALL_FOLDERS = [INBOX, PROCESSING, TRAINING, HOLDOUT, STRESS, PILOT, ARCHIVE, REJECTED]

_STATUS_FLOW = {
    "inbox": "processing",
    "processing": None,
    "training": None,
    "holdout": None,
    "stress": None,
    "pilot": None,
    "archive": None,
    "rejected": None,
}

STATUS_ORDER = [
    "inbox", "processing", "training", "holdout",
    "stress", "pilot", "archive", "rejected",
]

_YEAR_PAT = re.compile(r"(?:19|20)\d{2}")
_COMPANY_PAT = re.compile(
    r"(?P<name>[A-Z][A-Za-z0-9\s\.\,\-áéíóúñüÁÉÍÓÚÑÜ]+)"
    r"(?:\s+(LTDA|LIMITADA|SA|S\.A\.|EIRL|SPA|Ltda|Limitada|S\.A))?"
)

_LAYOUT_KEYWORDS: dict[str, list[str]] = {
    "clasificado": ["clasificado", "classified"],
    "original": ["original", "tributario", "tributaria"],
    "8_columnas": ["8 columna", "ocho columna", "8 columnas"],
    "resultados": ["resultado", "estado resultado", "income statement"],
    "general": ["balance general", "general balance"],
}


def _all_folders_fn() -> list[Path]:
    return [
        DATASET_ROOT / "INBOX",
        DATASET_ROOT / "PROCESSING",
        DATASET_ROOT / "TRAINING",
        DATASET_ROOT / "HOLDOUT",
        DATASET_ROOT / "STRESS" / "8_COLUMNS",
        DATASET_ROOT / "PILOT",
        DATASET_ROOT / "ARCHIVE",
        DATASET_ROOT / "REJECTED",
    ]


def _ensure_dirs() -> None:
    for folder in _all_folders_fn():
        folder.mkdir(parents=True, exist_ok=True)


def _sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _infer_company(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"\s*\(.*?\)\s*", " ", stem)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stopwords = [
        "balance", "balance general", "balance clasificado",
        "estado", "resultado", "resumen",
        "eeff", "ee ff", "original", "tributario", "tributaria",
        "clasificado", "clasificados",
        "general", "consolidado",
        "2010", "2011", "2012", "2013", "2014", "2015",
        "2016", "2017", "2018", "2019", "2020", "2021",
        "2022", "2023", "2024", "2025", "2026",
        "dic", "diciembre", "enero", "febrero", "marzo",
        "abril", "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre",
        "pdf", "v3", "v2", "v4", "final", "version",
        "balance", "estado", "situacion", "financiera",
    ]
    words = stem.split()
    filtered = [w for w in words if w.lower() not in stopwords]
    company = " ".join(filtered[:4])
    company = re.sub(r"\s+", " ", company).strip()
    if len(company) <= 2:
        company = stem
    return company[:100]


def _infer_year(filename: str) -> int | None:
    years = _YEAR_PAT.findall(filename)
    if years:
        return int(years[-1])
    return None


def _infer_layout(filename: str) -> str:
    low = filename.lower()
    for layout, keywords in _LAYOUT_KEYWORDS.items():
        for kw in keywords:
            if kw in low:
                return layout
    return "unknown"


def _get_page_count(filepath: str | Path) -> int:
    try:
        import pdfplumber
        with pdfplumber.open(str(filepath)) as pdf:
            return len(pdf.pages)
    except Exception:
        try:
            from pdfminer.pdfparser import PDFParser
            from pdfminer.pdfdocument import PDFDocument
            with open(filepath, "rb") as f:
                parser = PDFParser(f)
                doc = PDFDocument(parser)
                return len(list(doc.get_pages()))
        except Exception:
            return 0


def _get_pdf_metadata(filepath: str | Path) -> dict[str, Any]:
    filepath = Path(filepath)
    stat = filepath.stat()
    sha = _sha256(filepath)
    pages = _get_page_count(filepath)
    return {
        "filename": filepath.name,
        "sha256": sha,
        "file_size": stat.st_size,
        "pages": pages,
        "created_date": datetime.datetime.fromtimestamp(
            stat.st_birthtime if hasattr(stat, "st_birthtime") else stat.st_mtime
        ).isoformat(),
    }


def init_db(db_path: str | Path = DATASET_DB) -> None:
    _ensure_dirs()
    db_path = Path(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'inbox',
            source_folder TEXT,
            current_folder TEXT,
            company TEXT,
            year INTEGER,
            layout TEXT DEFAULT 'unknown',
            pages INTEGER DEFAULT 0,
            file_size INTEGER DEFAULT 0,
            ocr TEXT DEFAULT 'pending',
            processed_date TIMESTAMP,
            benchmark_used INTEGER DEFAULT 0,
            training_used INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _conn(db_path: str | Path = DATASET_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    if not db_path.exists():
        init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _register(
    filename: str,
    sha256: str,
    status: str = "inbox",
    source_folder: str | None = None,
    current_folder: str | None = None,
    company: str | None = None,
    year: int | None = None,
    layout: str = "unknown",
    pages: int = 0,
    file_size: int = 0,
    ocr: str = "pending",
    notes: str = "",
    db_path: str | Path = DATASET_DB,
) -> int:
    conn = _conn(db_path)
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cur = conn.execute(
            """
            INSERT INTO dataset_files
                (filename, sha256, status, source_folder, current_folder,
                 company, year, layout, pages, file_size, ocr,
                 processed_date, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
                status=excluded.status,
                current_folder=excluded.current_folder,
                updated_at=excluded.updated_at
            """,
            (
                filename, sha256, status, source_folder, current_folder,
                company, year, layout, pages, file_size, ocr,
                now, notes, now, now,
            ),
        )
        conn.commit()
        if cur.lastrowid and cur.lastrowid > 0:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM dataset_files WHERE sha256=?", (sha256,)
        ).fetchone()
        return row["id"] if row else 0
    finally:
        conn.close()


def register_dataset(
    filepath: str | Path,
    status: str = "inbox",
    notes: str = "",
    db_path: str | Path = DATASET_DB,
) -> int:
    filepath = Path(filepath)
    meta = _get_pdf_metadata(filepath)
    company = _infer_company(filepath.name)
    year = _infer_year(filepath.name)
    layout = _infer_layout(filepath.name)
    return _register(
        filename=filepath.name,
        sha256=meta["sha256"],
        status=status,
        source_folder=str(filepath.parent),
        current_folder=str(filepath.parent),
        company=company,
        year=year,
        layout=layout,
        pages=meta["pages"],
        file_size=meta["file_size"],
        ocr="pending",
        notes=notes,
        db_path=db_path,
    )


def scan_inbox(db_path: str | Path = DATASET_DB) -> list[dict[str, Any]]:
    _ensure_dirs()
    conn = _conn(db_path)

    existing_hashes = set(
        row["sha256"] for row in conn.execute("SELECT sha256 FROM dataset_files").fetchall()
    )
    conn.close()

    new_files: list[dict[str, Any]] = []
    for entry in sorted(INBOX.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in (".pdf", ".PDF"):
            continue

        meta = _get_pdf_metadata(entry)
        if meta["sha256"] in existing_hashes:
            continue

        company = _infer_company(entry.name)
        year = _infer_year(entry.name)
        layout = _infer_layout(entry.name)

        _register(
            filename=entry.name,
            sha256=meta["sha256"],
            status="inbox",
            source_folder=str(INBOX),
            current_folder=str(INBOX),
            company=company,
            year=year,
            layout=layout,
            pages=meta["pages"],
            file_size=meta["file_size"],
            ocr="pending",
            db_path=db_path,
        )

        existing_hashes.add(meta["sha256"])
        new_files.append({
            "filename": entry.name,
            "sha256": meta["sha256"],
            "pages": meta["pages"],
            "file_size": meta["file_size"],
            "company": company,
            "year": year,
            "layout": layout,
        })

    return new_files


def _move_file(
    filename: str,
    target_status: str,
    target_folder: Path,
    db_path: str | Path = DATASET_DB,
) -> dict[str, Any]:
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM dataset_files WHERE filename=? AND status=?",
            (filename, _reverse_status(target_status)),
        ).fetchone()

        if row is None:
            row = conn.execute(
                "SELECT * FROM dataset_files WHERE filename=?",
                (filename,),
            ).fetchone()

        if row is None:
            return {"success": False, "error": f"Archivo no encontrado: {filename}"}

        source = Path(row["current_folder"]) / row["filename"]
        if not source.exists():
            return {"success": False, "error": f"Archivo no existe en disco: {source}"}

        target_folder.mkdir(parents=True, exist_ok=True)
        dest = target_folder / row["filename"]

        counter = 1
        stem = dest.stem
        suffix = dest.suffix
        while dest.exists():
            dest = target_folder / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.move(str(source), str(dest))
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn.execute(
            """
            UPDATE dataset_files
            SET status=?, current_folder=?, updated_at=?, processed_date=COALESCE(processed_date,?)
            WHERE sha256=?
            """,
            (target_status, str(dest.parent), now, now, row["sha256"]),
        )
        conn.commit()

        return {
            "success": True,
            "filename": dest.name,
            "from": str(source.parent),
            "to": str(dest.parent),
            "status": target_status,
        }
    finally:
        conn.close()


def _reverse_status(target: str) -> str:
    for k, v in _STATUS_FLOW.items():
        if v == target:
            return k
    return "inbox"


def move_to_processing(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "processing", PROCESSING, db_path)


def mark_training(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "training", TRAINING, db_path)


def mark_holdout(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "holdout", HOLDOUT, db_path)


def mark_stress(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "stress", STRESS, db_path)


def archive(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "archive", ARCHIVE, db_path)


def reject(
    filename: str, db_path: str | Path = DATASET_DB
) -> dict[str, Any]:
    return _move_file(filename, "rejected", REJECTED, db_path)


def register_existing_files(db_path: str | Path = DATASET_DB) -> int:
    existing_folders = {
        "training": TRAINING,
        "holdout": HOLDOUT,
        "stress": STRESS,
        "pilot": PILOT,
    }
    registered = 0
    for status, folder in existing_folders.items():
        if not folder.exists():
            continue
        for entry in sorted(folder.iterdir()):
            if not entry.is_file() or entry.suffix.lower() not in (".pdf", ".PDF"):
                continue
            meta = _get_pdf_metadata(entry)
            company = _infer_company(entry.name)
            year = _infer_year(entry.name)
            layout = _infer_layout(entry.name)
            try:
                _register(
                    filename=entry.name,
                    sha256=meta["sha256"],
                    status=status,
                    source_folder=str(folder),
                    current_folder=str(folder),
                    company=company,
                    year=year,
                    layout=layout,
                    pages=meta["pages"],
                    file_size=meta["file_size"],
                    ocr="pending",
                    db_path=db_path,
                )
                registered += 1
            except sqlite3.IntegrityError:
                pass
    return registered


def get_inventory(db_path: str | Path = DATASET_DB) -> dict[str, Any]:
    conn = _conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM dataset_files ORDER BY filename").fetchall()

        total = len(rows)
        by_status: Counter[str] = Counter()
        companies: Counter[str] = Counter()
        years: Counter[int] = Counter()
        layouts: Counter[str] = Counter()
        pages_dist: list[int] = []
        sizes: list[int] = []

        sha256_set: set[str] = set()
        duplicates = 0

        for r in rows:
            by_status[r["status"]] += 1
            companies[r["company"] or "unknown"] += 1
            years[r["year"] if r["year"] else 0] += 1
            layouts[r["layout"] or "unknown"] += 1
            pages_dist.append(r["pages"] or 0)
            sizes.append(r["file_size"] or 0)

            if r["sha256"] in sha256_set:
                duplicates += 1
            sha256_set.add(r["sha256"])

        return {
            "total": total,
            "by_status": dict(by_status.most_common()),
            "companies": dict(companies.most_common(30)),
            "total_companies": len(companies),
            "years": dict(years.most_common()),
            "layouts": dict(layouts.most_common()),
            "pages": {
                "min": min(pages_dist) if pages_dist else 0,
                "max": max(pages_dist) if pages_dist else 0,
                "avg": round(sum(pages_dist) / max(len(pages_dist), 1), 1),
            },
            "file_size_mb": {
                "total_mb": round(sum(sizes) / (1024 * 1024), 2),
                "avg_mb": round(sum(sizes) / max(len(sizes), 1) / (1024 * 1024), 2),
            },
            "duplicates": duplicates,
        }
    finally:
        conn.close()


def generate_inventory_report(
    output_path: str | Path = "reports/dataset_inventory.md",
    db_path: str | Path = DATASET_DB,
) -> str:
    inv = get_inventory(db_path)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    lines: list[str] = []
    lines.append("# Dataset Inventory")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Source:** `{DATASET_DB}`")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total files | {inv['total']} |")
    lines.append(f"| Unique companies | {inv['total_companies']} |")
    lines.append(f"| Duplicate hashes | {inv['duplicates']} |")
    lines.append(f"| Total size | {inv['file_size_mb']['total_mb']} MB |")
    lines.append(f"| Avg size | {inv['file_size_mb']['avg_mb']} MB |")
    lines.append(f"| Pages range | {inv['pages']['min']} – {inv['pages']['max']} |")
    lines.append(f"| Avg pages | {inv['pages']['avg']} |")
    lines.append("")

    lines.append("## Files per status")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for s in STATUS_ORDER:
        cnt = inv["by_status"].get(s, 0)
        if cnt > 0:
            lines.append(f"| {s} | {cnt} |")
    lines.append("")

    lines.append("## Layout distribution")
    lines.append("")
    lines.append("| Layout | Count |")
    lines.append("|--------|-------|")
    for lay, cnt in inv["layouts"].items():
        lines.append(f"| {lay} | {cnt} |")
    lines.append("")

    lines.append("## Year distribution")
    lines.append("")
    lines.append("| Year | Count |")
    lines.append("|------|-------|")
    for yr, cnt in sorted(inv["years"].items()):
        label = str(yr) if yr else "unknown"
        lines.append(f"| {label} | {cnt} |")
    lines.append("")

    lines.append("## Top companies")
    lines.append("")
    lines.append("| Company | Files |")
    lines.append("|--------|-------|")
    for comp, cnt in list(inv["companies"].items())[:30]:
        label = comp[:50] if len(comp) > 50 else comp
        lines.append(f"| {label} | {cnt} |")
    lines.append("")

    text = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding="utf-8")
    return text
