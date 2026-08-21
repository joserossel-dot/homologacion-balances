from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationSession:
    processed_files: list[dict[str, Any]] = field(default_factory=list)
    processed_accounts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    memory_peak: float = 0.0
    _start_time: float = field(default_factory=time.perf_counter, repr=False)

    def start_timer(self) -> None:
        self._start_time = time.perf_counter()

    def stop_timer(self) -> float:
        self.execution_time = time.perf_counter() - self._start_time
        return self.execution_time

    def add_file(self, entry: dict[str, Any]) -> None:
        self.processed_files.append(entry)

    def add_account(self, entry: dict[str, Any]) -> None:
        self.processed_accounts.append(entry)

    def add_error(self, entry: dict[str, Any]) -> None:
        self.errors.append(entry)

    def add_warning(self, entry: dict[str, Any]) -> None:
        self.warnings.append(entry)

    def merge_file_result(self, result: dict[str, Any]) -> None:
        classified = result.get("classified", [])
        for acct in classified:
            self.processed_accounts.append(acct)
        entry: dict[str, Any] = {
            "source_file": result.get("source_file", ""),
            "accounts_total": result.get("accounts_total", 0),
            "accounts_classified": result.get("accounts_classified", 0),
            "accounts_ignored": result.get("accounts_ignored", 0),
            "accounts_without_dictionary_match": result.get("accounts_without_dictionary_match", 0),
            "learning_hits": result.get("learning_hits", 0),
            "learning_exact": result.get("learning_exact", 0),
            "learning_fuzzy": result.get("learning_fuzzy", 0),
            "fallback_classifier": result.get("fallback_classifier", 0),
            "elapsed_seconds": result.get("elapsed_seconds", 0.0),
        }
        for extra in ("group", "ocr", "file_type"):
            if extra in result:
                entry[extra] = result[extra]
        self.processed_files.append(entry)

    def counts_by_method(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for acct in self.processed_accounts:
            m = acct.get("method", "unknown")
            counts[m] = counts.get(m, 0) + 1
        return counts

    def unclassified_accounts(self) -> list[dict[str, Any]]:
        return [
            a for a in self.processed_accounts
            if a.get("standard_code") is None
        ]

    def accounts_by_group(self, group: str) -> list[dict[str, Any]]:
        return [
            a for a in self.processed_accounts
            if a.get("source_file", "").startswith(group)
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "files_total": len(self.processed_files),
            "accounts_total": len(self.processed_accounts),
            "errors_total": len(self.errors),
            "warnings_total": len(self.warnings),
            "execution_time": round(self.execution_time, 3),
            "memory_peak": round(self.memory_peak, 2),
        }
