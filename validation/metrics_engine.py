from __future__ import annotations

import statistics
from typing import Any

from validation.validation_session import ValidationSession


class MetricsEngine:
    def compute(self, session: ValidationSession) -> dict[str, Any]:
        files = session.processed_files
        accounts = session.processed_accounts
        errors = session.errors

        total_documents = len(files)
        pdf_count = sum(1 for f in files if f.get("source_file", "").lower().endswith(".pdf"))
        excel_count = sum(1 for f in files if f.get("source_file", "").lower().endswith((".xls", ".xlsx")))
        ocr_count = sum(1 for f in files if f.get("ocr", False))

        accounts_total = len(accounts)
        accounts_classified = sum(1 for a in accounts if a.get("standard_code") is not None)
        accounts_manual = len(session.unclassified_accounts())

        method_counts = session.counts_by_method()
        learning_hits = method_counts.get("learning_exact", 0) + method_counts.get("learning_fuzzy", 0)
        dictionary_hits = method_counts.get("dictionary_exact", 0) + method_counts.get("dictionary_fuzzy", 0)
        code_hits = method_counts.get("code", 0)
        fuzzy_hits = method_counts.get("dictionary_fuzzy", 0)

        parser_errors = sum(1 for e in errors if e.get("category") == "parser")

        timings = [f.get("elapsed_seconds", 0.0) for f in files if f.get("elapsed_seconds", 0.0) > 0]
        processing_time = sum(timings)
        avg_time = statistics.mean(timings) if timings else 0.0
        p95_time = self._percentile(sorted(timings), 95) if timings else 0.0

        return {
            "total_documents": total_documents,
            "pdf_count": pdf_count,
            "excel_count": excel_count,
            "ocr_count": ocr_count,
            "accounts_total": accounts_total,
            "accounts_classified": accounts_classified,
            "accounts_manual": accounts_manual,
            "accounts_unclassified": accounts_manual,
            "learning_hits": learning_hits,
            "dictionary_hits": dictionary_hits,
            "code_hits": code_hits,
            "fuzzy_hits": fuzzy_hits,
            "parser_errors": parser_errors,
            "processing_time": round(processing_time, 3),
            "avg_time": round(avg_time, 4),
            "p95_time": round(p95_time, 4),
            "files_by_group": self._files_by_group(files),
            "methods_distribution": method_counts,
        }

    @staticmethod
    def _percentile(sorted_data: list[float], p: int) -> float:
        if not sorted_data:
            return 0.0
        k = (p / 100.0) * (len(sorted_data) - 1)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    @staticmethod
    def _files_by_group(files: list[dict[str, Any]]) -> dict[str, int]:
        groups: dict[str, int] = {}
        for f in files:
            gf = f.get("group", "unknown")
            groups[gf] = groups.get(gf, 0) + 1
        return groups
