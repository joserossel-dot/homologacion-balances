#!/usr/bin/env python3
"""Sprint 27.3 — Human Review Interface CLI (CMCC v1, shadow mode)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_ui import (
    ReviewSession, ReviewRepository,
    approve, reject, reassign, undo,
    compute_statistics, generate_reports,
)


def main():
    t0 = time.perf_counter()
    print("=" * 70)
    print("  SPRINT 27.3 — Human Review Interface")
    print("  Shadow mode. No dictionary writes.")
    print("=" * 70)

    repo = ReviewRepository()
    session = ReviewSession(repo)

    # ── Load pending from queue ──
    loaded = session.load_pending()
    print(f"\n  Loaded {len(loaded)} new decisions from queue")

    remaining = session.repo.count_pending()
    print(f"  Pending in DB: {remaining}")

    # ── Process examples (simulated review) ──
    pending = session.get_pending(limit=5)
    for d in pending:
        print(f"\n  [{d.review_id[:8]}] variant='{d.variant[:40]}' → {d.current_concept}")
        approve(d, repo, reviewer="system_test", reason="automatic approval", comments="Simulated batch")

    # ── Reassign example (change concept) ──
    pending2 = session.get_pending(limit=1)
    for d in pending2:
        reassign(d, repo, new_concept="AC.02", new_concept_name="Valores Negociables",
                 reviewer="system_test", reason="manual reassign")

    # ── Reject example ──
    pending3 = session.get_pending(limit=1)
    for d in pending3:
        reject(d, repo, reviewer="system_test", reason="not a valid match")

    # ── Undo example ──
    approved_list = repo.load_approved()
    if approved_list:
        undo(approved_list[0], repo)

    # ── Statistics ──
    all_decisions = repo.all_decisions()
    stats = compute_statistics(all_decisions)
    print(f"\n  Statistics:")
    print(f"    Total: {stats['total_decisions']}")
    print(f"    Approved: {stats['approved']}")
    print(f"    Rejected: {stats['rejected']}")
    print(f"    Reassigned: {stats['reassigned']}")
    print(f"    Pending: {stats['pending']}")

    # ── Reports ──
    paths = generate_reports(all_decisions, stats)
    print(f"\n  Reports generated:")
    for name, p in paths.items():
        print(f"    {name}: {p.stat().st_size:,} bytes")

    elapsed = time.perf_counter() - t0
    print(f"\n{'=' * 70}")
    print(f"  DONE — {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
