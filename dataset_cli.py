from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_manager import (
    init_db,
    scan_inbox,
    register_existing_files,
    move_to_processing,
    mark_training,
    mark_holdout,
    mark_stress,
    archive,
    reject,
    generate_inventory_report,
    get_inventory,
    DATASET_DB,
)

COMMANDS = {
    "init": "Initialize the database and register existing files",
    "scan": "Scan INBOX for new PDF files and register them",
    "inventory": "Show inventory summary and generate report",
    "move-processing": "Move file from INBOX to PROCESSING",
    "move-training": "Move file from PROCESSING to TRAINING",
    "move-holdout": "Move file from PROCESSING to HOLDOUT",
    "move-stress": "Move file from PROCESSING to STRESS/8_COLUMNS",
    "archive": "Move file to ARCHIVE",
    "reject": "Move file to REJECTED",
}


def print_inventory():
    inv = get_inventory()
    print(f"\nDataset Inventory")
    print(f"{'='*50}")
    print(f"  Total files:       {inv['total']}")
    print(f"  Unique companies:  {inv['total_companies']}")
    print(f"  Duplicate hashes:  {inv['duplicates']}")
    print(f"  Total size:        {inv['file_size_mb']['total_mb']} MB")
    print(f"  Pages:             {inv['pages']['min']}-{inv['pages']['max']} (avg {inv['pages']['avg']})")
    print()
    print("  By status:")
    for s in ["inbox", "processing", "training", "holdout", "stress", "pilot", "archive", "rejected"]:
        cnt = inv["by_status"].get(s, 0)
        if cnt:
            print(f"    {s}: {cnt}")
    print()
    print("  By layout:")
    for lay, cnt in inv["layouts"].items():
        print(f"    {lay}: {cnt}")
    print()
    report_path = generate_inventory_report()
    print(f"  Full report: {report_path}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("Dataset Manager CLI")
        print(f"{'='*50}")
        print(f"Usage: python dataset_cli.py <command> [args]")
        print()
        print("Commands:")
        for cmd, desc in COMMANDS.items():
            print(f"  {cmd:20s}  {desc}")
        print()
        print("Examples:")
        print("  python dataset_cli.py scan")
        print("  python dataset_cli.py inventory")
        print("  python dataset_cli.py move-training archivo.pdf")
        print("  python dataset_cli.py archive archivo.pdf")
        return

    command = sys.argv[1]

    if command == "init":
        init_db()
        count = register_existing_files()
        print(f"Database initialized. Registered {count} existing files.")
        print_inventory()

    elif command == "scan":
        init_db()
        new = scan_inbox()
        if new:
            print(f"Found {len(new)} new file(s) in INBOX:")
            for f in new:
                print(f"  + {f['filename']} ({f['company'] or '?'}, {f['year'] or '?'}, {f['pages']}p)")
        else:
            print("No new files found in INBOX.")

    elif command == "inventory":
        print_inventory()

    elif command == "move-processing":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py move-processing <filename>")
            return
        result = move_to_processing(sys.argv[2])
        _print_result(result)

    elif command == "move-training":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py move-training <filename>")
            return
        result = mark_training(sys.argv[2])
        _print_result(result)

    elif command == "move-holdout":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py move-holdout <filename>")
            return
        result = mark_holdout(sys.argv[2])
        _print_result(result)

    elif command == "move-stress":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py move-stress <filename>")
            return
        result = mark_stress(sys.argv[2])
        _print_result(result)

    elif command == "archive":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py archive <filename>")
            return
        result = archive(sys.argv[2])
        _print_result(result)

    elif command == "reject":
        if len(sys.argv) < 3:
            print("Usage: python dataset_cli.py reject <filename>")
            return
        result = reject(sys.argv[2])
        _print_result(result)

    else:
        print(f"Unknown command: {command}")
        print("Use -h for help.")
        sys.exit(1)


def _print_result(result: dict):
    if result["success"]:
        print(f"Moved: {result['filename']}")
        print(f"  From: {result['from']}")
        print(f"  To:   {result['to']}")
        print(f"  Status: {result['status']}")
    else:
        print(f"Error: {result['error']}")


if __name__ == "__main__":
    main()
