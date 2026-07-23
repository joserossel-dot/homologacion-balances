from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gold_standard.builder import GoldBuilder
from gold_standard.models import GoldRecord
from pipeline.homologation_pipeline import HomologationPipeline
from validation.dataset_manager import DatasetManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_TOTAL_PATTERN = re.compile(r"\btotal\b", re.IGNORECASE)


def _is_total_row(account_name: str) -> bool:
    return bool(_TOTAL_PATTERN.search(account_name))


def _is_valid_account(rec: dict) -> bool:
    if not rec.get("standard_code"):
        return False
    if rec.get("confidence", 0) <= 0:
        return False
    if not rec.get("account_name"):
        return False
    if not rec.get("account_code"):
        return False
    if _is_total_row(rec.get("account_name", "")):
        return False
    return True


def seed(
    datasets_root: str | Path,
    db_path: str | Path = "gold_standard.db",
    min_confidence: float = 0.95,
    dry_run: bool = False,
) -> dict:
    root = Path(datasets_root)
    if not root.is_dir():
        raise NotADirectoryError(f"Dataset root not found: {root}")

    pipeline = HomologationPipeline(str(db_path))
    builder = GoldBuilder(str(db_path)) if not dry_run else None
    manager = DatasetManager(root)
    files = manager.discover()

    logger.info("Found %d file(s) in %s", len(files), root)

    stats = {
        "total_accounts": 0,
        "valid_accounts": 0,
        "inserted": 0,
        "updated": 0,
        "conflicts": 0,
        "skipped_empty_code": 0,
        "skipped_low_confidence": 0,
        "skipped_total": 0,
        "skipped_no_name": 0,
        "skipped_no_code": 0,
        "conflict_details": [],
    }

    for dfile in files:
        logger.info("Processing: %s", dfile.path.name)
        try:
            result = pipeline.process(dfile.path)
        except Exception as e:
            logger.warning("Error processing %s: %s", dfile.path.name, e)
            continue

        for rec in result.get("classified", []):
            stats["total_accounts"] += 1

            if not rec.get("standard_code"):
                stats["skipped_empty_code"] += 1
                continue

            if not rec.get("account_name"):
                stats["skipped_no_name"] += 1
                continue

            if not rec.get("account_code"):
                stats["skipped_no_code"] += 1
                continue

            if rec.get("confidence", 0) < min_confidence:
                stats["skipped_low_confidence"] += 1
                continue

            if _is_total_row(rec.get("account_name", "")):
                stats["skipped_total"] += 1
                continue

            stats["valid_accounts"] += 1

            if dry_run:
                continue

            gold_rec = GoldRecord(
                source_file=rec.get("source_file", dfile.path.name),
                account_code_original=rec.get("account_code", ""),
                account_name=rec.get("account_name", ""),
                account_nature=rec.get("nature", ""),
                suggested_code=rec.get("standard_code", ""),
                suggested_confidence=rec.get("confidence", 0.0),
                final_code=rec.get("final_code", rec.get("standard_code", "")),
                reviewer="seed_script",
                comments="Auto-seeded from pipeline classification",
                usage_count=1,
            )

            existing_list = builder.find_by_name(gold_rec.account_name)
            conflict = False
            for existing in existing_list:
                if existing.final_code != gold_rec.final_code:
                    stats["conflicts"] += 1
                    stats["conflict_details"].append({
                        "account_name": gold_rec.account_name,
                        "existing_code": existing.final_code,
                        "new_code": gold_rec.final_code,
                        "source_file": dfile.path.name,
                    })
                    conflict = True
                    break

            if conflict:
                continue

            record_id = builder.add_or_update(gold_rec)
            if any(
                r.id == record_id
                for r in (builder.find_by_name_and_code(gold_rec.account_name, gold_rec.final_code) and []) or []
            ):
                pass

            existing_after = builder.find_by_name_and_code(
                gold_rec.account_name, gold_rec.final_code
            )
            if existing_after is not None and existing_after.usage_count > 1:
                stats["updated"] += 1
            else:
                stats["inserted"] += 1

    if builder:
        builder.close()

    return stats


def _print_summary(stats: dict, min_confidence: float, dry_run: bool) -> None:
    print()
    print("-" * 37)
    if dry_run:
        print("  GOLD STANDARD SEED — DRY RUN")
    else:
        print("  GOLD STANDARD SEED COMPLETE")
    print("-" * 37)
    print(f"  Min confidence:          {min_confidence}")
    print(f"  Total classified:       {stats['total_accounts']}")
    print(f"  Valid (passed filters): {stats['valid_accounts']}")
    print(f"  Records inserted:       {stats['inserted']}")
    print(f"  Existing updated:       {stats['updated']}")
    print(f"  Conflicts detected:     {stats['conflicts']}")
    print(f"  Skipped (no code):      {stats['skipped_empty_code']}")
    print(f"  Skipped (low conf):     {stats['skipped_low_confidence']}")
    print(f"  Skipped (total row):    {stats['skipped_total']}")
    print(f"  Skipped (no name):      {stats['skipped_no_name']}")
    print(f"  Skipped (no code):      {stats['skipped_no_code']}")
    print()

    if stats["conflict_details"]:
        print("  CONFLICTS:")
        for c in stats["conflict_details"][:20]:
            print(f"    '{c['account_name']}': existing='{c['existing_code']}' vs new='{c['new_code']}' ({c['source_file']})")
        if len(stats["conflict_details"]) > 20:
            print(f"    ... and {len(stats['conflict_details']) - 20} more")
        print()

    if not dry_run:
        builder = GoldBuilder()
        top = builder.top_learned(20)
        builder.close()
        if top:
            print("  TOP 20 LEARNED ACCOUNTS:")
            print(f"  {'Account':<40} {'Code':<12} {'Count':<6} {'Last Used':<22}")
            print(f"  {'-'*40} {'-'*12} {'-'*6} {'-'*22}")
            for row in top:
                print(f"  {row['account_name']:<40} {row['final_code']:<12} {row['usage_count']:<6} {row['last_used']:<22}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Gold Standard from pipeline classifications")
    parser.add_argument("datasets_root", help="Root directory containing dataset groups")
    parser.add_argument("--db", default="gold_standard.db", help="Gold Standard database path")
    parser.add_argument("--min-confidence", type=float, default=0.95, help="Minimum confidence threshold (default: 0.95)")
    parser.add_argument("--dry-run", action="store_true", help="Show statistics without modifying the database")
    args = parser.parse_args()

    start = time.perf_counter()
    stats = seed(
        datasets_root=args.datasets_root,
        db_path=args.db,
        min_confidence=args.min_confidence,
        dry_run=args.dry_run,
    )
    elapsed = time.perf_counter() - start

    _print_summary(stats, args.min_confidence, args.dry_run)

    print(f"  Elapsed: {elapsed:.3f}s")
    print()

    if not args.dry_run:
        builder = GoldBuilder(args.db)
        gs_stats = builder.statistics()
        builder.close()
        print(f"  Gold Standard final size: {gs_stats['total_records']} records")
        print(f"  Exact hits:               {gs_stats['exact_hits']}")
        print(f"  Total conflicts:          {gs_stats['conflicts']}")
        if stats["valid_accounts"] > 0:
            print(f"  Avg usage_count:          {gs_stats['total_records'] / stats['valid_accounts']:.2f}")
        print()


if __name__ == "__main__":
    main()
