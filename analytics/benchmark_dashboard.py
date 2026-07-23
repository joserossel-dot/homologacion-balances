from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError:
    pd = None

from gold_standard.builder import GoldBuilder
from validation.validation_session import ValidationSession

logger = logging.getLogger(__name__)


class BenchmarkDashboard:
    def __init__(self, db_path: str | Path = "gold_standard.db") -> None:
        self._builder = GoldBuilder(db_path)
        self._refresh()

    def _refresh(self) -> None:
        self._gs_records = {
            r.account_name: r.final_code
            for r in self._builder.list_all()
            if r.account_name and r.final_code
        }

    def close(self) -> None:
        self._builder.close()

    def evaluate(self, session: ValidationSession) -> dict[str, Any]:
        self._refresh()
        accounts = session.processed_accounts

        if not self._gs_records:
            return {
                "error": "Gold Standard is empty — cannot evaluate",
                "total_gs_records": 0,
            }

        tp_by_code: dict[str, int] = Counter()
        fp_by_code: dict[str, int] = Counter()
        fn_by_code: dict[str, int] = Counter()
        exact_matches = 0
        total_gs_covered = 0
        learning_correct = 0
        learning_total = 0
        non_learning_correct = 0
        non_learning_total = 0
        top3_correct = 0
        top3_total = 0

        for acct in accounts:
            name = acct.get("account_name", "")
            predicted = acct.get("final_code") or acct.get("standard_code")
            method = acct.get("method", "unknown")

            if not name or name not in self._gs_records:
                continue
            ground_truth = self._gs_records[name]
            total_gs_covered += 1

            if predicted == ground_truth:
                exact_matches += 1
                tp_by_code[ground_truth] += 1
                if method.startswith("learning_"):
                    learning_correct += 1
                else:
                    non_learning_correct += 1
            else:
                if predicted:
                    fp_by_code[predicted] += 1
                fn_by_code[ground_truth] += 1

            if method.startswith("learning_"):
                learning_total += 1
            else:
                non_learning_total += 1

        all_codes = set(tp_by_code) | set(fp_by_code) | set(fn_by_code)

        per_code: list[dict[str, Any]] = []
        for code in sorted(all_codes):
            tp = tp_by_code[code]
            fp = fp_by_code[code]
            fn = fn_by_code[code]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )
            support = tp + fn
            per_code.append({
                "code": code,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "support": support,
            })

        accuracy = exact_matches / total_gs_covered if total_gs_covered > 0 else 0.0

        macro_precision = (
            sum(p["precision"] for p in per_code) / len(per_code) if per_code else 0.0
        )
        macro_recall = (
            sum(p["recall"] for p in per_code) / len(per_code) if per_code else 0.0
        )
        macro_f1 = (
            2 * macro_precision * macro_recall / (macro_precision + macro_recall)
            if (macro_precision + macro_recall) > 0
            else 0.0
        )

        total_support = sum(p["support"] for p in per_code) or 1
        weighted_precision = (
            sum(p["precision"] * p["support"] for p in per_code) / total_support
            if per_code
            else 0.0
        )
        weighted_recall = (
            sum(p["recall"] * p["support"] for p in per_code) / total_support
            if per_code
            else 0.0
        )
        weighted_f1 = (
            2 * weighted_precision * weighted_recall / (weighted_precision + weighted_recall)
            if (weighted_precision + weighted_recall) > 0
            else 0.0
        )

        return {
            "total_gs_records": len(self._gs_records),
            "total_accounts_in_pipeline": len(accounts),
            "gs_covered_accounts": total_gs_covered,
            "accuracy": round(accuracy, 4),
            "exact_matches": exact_matches,
            "macro_precision": round(macro_precision, 4),
            "macro_recall": round(macro_recall, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_precision": round(weighted_precision, 4),
            "weighted_recall": round(weighted_recall, 4),
            "weighted_f1": round(weighted_f1, 4),
            "learning_accuracy": round(learning_correct / learning_total, 4) if learning_total > 0 else 0.0,
            "non_learning_accuracy": round(non_learning_correct / non_learning_total, 4) if non_learning_total > 0 else 0.0,
            "per_code": per_code,
        }

    @staticmethod
    def compare_legacy(
        legacy_metrics: dict[str, Any],
        new_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for key in [
            "accounts_classified", "accounts_unclassified",
            "learning_hits", "dictionary_hits", "code_hits", "fuzzy_hits",
            "processing_time", "avg_time",
        ]:
            before = legacy_metrics.get(key, 0)
            after = new_metrics.get(key, 0)
            diff[f"{key}_before"] = before
            diff[f"{key}_after"] = after
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                diff[f"{key}_delta"] = round(after - before, 4)
                if before != 0:
                    diff[f"{key}_pct"] = round((after - before) / abs(before) * 100, 2)
                else:
                    diff[f"{key}_pct"] = None
        return diff

    @staticmethod
    def load_metrics(report_dir: str | Path) -> dict[str, Any]:
        path = Path(report_dir) / "metrics.json"
        if not path.exists():
            raise FileNotFoundError(f"metrics.json not found in {report_dir}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def to_dataframe(self, data: dict[str, Any]) -> Any:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        flat = {k: v for k, v in data.items() if k != "per_code"}
        return pd.DataFrame([flat])

    def export_excel(self, path: str | Path, session: ValidationSession | None = None) -> Path:
        if pd is None:
            raise ImportError("pandas is required for Excel export")
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            if session is not None:
                result = self.evaluate(session)
                flat = {k: v for k, v in result.items() if k != "per_code"}
                pd.DataFrame([flat]).to_excel(writer, sheet_name="Summary", index=False)
                per_code = result.get("per_code", [])
                if per_code:
                    pd.DataFrame(per_code).to_excel(writer, sheet_name="PerCode", index=False)

        logger.info("Benchmark exported to: %s", out.resolve())
        return out
