from __future__ import annotations

from typing import Any

from evidence.account_evidence import AccountEvidence


def build_context_windows(
    entries: list[dict[str, Any]],
    window_size: int = 3,
) -> list[tuple[list[dict], list[dict]]]:
    windows: list[tuple[list[dict], list[dict]]] = []
    for i in range(len(entries)):
        start = max(0, i - window_size)
        before = entries[start:i]
        after = entries[i + 1:min(len(entries), i + 1 + window_size)]
        windows.append((before, after))
    return windows


def add_context_to_evidences(
    evidences: list[AccountEvidence],
    source_entries: list[dict[str, Any]] | None = None,
    window_size: int = 3,
) -> list[AccountEvidence]:
    if source_entries is None:
        source_entries = [_evidence_to_entry(ev) for ev in evidences]

    windows = build_context_windows(source_entries, window_size)

    for ev, (before, after) in zip(evidences, windows):
        ev.context_before = [_entry_context(e) for e in before]
        ev.context_after = [_entry_context(e) for e in after]

    return evidences


def _entry_context(entry: dict[str, Any] | AccountEvidence) -> dict[str, Any]:
    if isinstance(entry, AccountEvidence):
        return {
            "account_name": entry.original_account_name or entry.clean_account_name,
            "account_code": entry.original_account_code or entry.clean_account_code,
            "method": entry.classification_method,
            "amount": entry.classification_amount,
        }
    return {
        "account_name": entry.get("account_name", ""),
        "account_code": entry.get("account_code", ""),
        "method": entry.get("method", ""),
        "amount": entry.get("classification_amount", 0.0),
    }


def _evidence_to_entry(ev: AccountEvidence) -> dict[str, Any]:
    return {
        "account_name": ev.original_account_name or ev.clean_account_name,
        "account_code": ev.original_account_code or ev.clean_account_code,
        "method": ev.classification_method,
        "classification_amount": ev.classification_amount,
    }
