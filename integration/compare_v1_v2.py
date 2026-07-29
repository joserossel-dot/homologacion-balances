from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pipeline.homologation_pipeline import HomologationPipeline
from orchestrator.pipeline_v2 import HomologationPipelineV2


class PipelineComparator:
    def __init__(
        self,
        db_path: str | Path = "gold_standard.db",
    ):
        self._v1 = HomologationPipeline(db_path=db_path)
        self._v2 = HomologationPipelineV2(db_path=db_path)
        self._results: list[dict[str, Any]] = []
        self._diffs: list[dict[str, Any]] = []

    def compare_file(self, pdf_path: str | Path) -> dict[str, Any]:
        path = Path(pdf_path)
        fname = path.name

        start_v1 = time.perf_counter()
        res_v1 = self._v1.process(str(path))
        elapsed_v1 = time.perf_counter() - start_v1
        res_v1["elapsed_seconds"] = round(elapsed_v1, 3)

        start_v2 = time.perf_counter()
        ctx = self._v2.process(str(path))
        elapsed_v2 = time.perf_counter() - start_v2

        from adapters.kb_adapter import KBAdapter
        res_v2 = KBAdapter.extract_v1_summary(ctx)
        res_v2["elapsed_seconds_v2"] = round(elapsed_v2, 3)
        res_v2["dce_state"] = ctx.state.value
        res_v2["dce_events"] = len(ctx.events)
        res_v2["dce_snapshots"] = len(ctx.snapshots)

        diff = self._compare_results(fname, res_v1, res_v2)
        self._results.append({
            "file": fname,
            "v1": res_v1,
            "v2": res_v2,
            "diff": diff,
        })
        self._diffs.append(diff)

        return diff

    def _compare_results(self, fname: str, v1: dict, v2: dict) -> dict[str, Any]:
        diffs: dict[str, Any] = {}

        scalar_keys = [
            "accounts_total", "accounts_classified", "accounts_ignored",
            "accounts_without_dictionary_match", "learning_hits",
            "learning_exact", "learning_fuzzy", "fallback_classifier",
        ]
        for key in scalar_keys:
            a = v1.get(key, 0)
            b = v2.get(key, 0)
            if a != b:
                diffs[key] = {"v1": a, "v2": b}

        v1_classified = v1.get("classified", [])
        v2_classified = v2.get("classified", [])
        if len(v1_classified) != len(v2_classified):
            diffs["classified_count"] = {"v1": len(v1_classified), "v2": len(v2_classified)}
        else:
            account_diffs = []
            for i, (c1, c2) in enumerate(zip(v1_classified, v2_classified)):
                ad = self._compare_classified_entry(c1, c2)
                if ad:
                    account_diffs.append({"index": i, "account_code": c1.get("account_code", ""), "diff": ad})
            if account_diffs:
                diffs["classified_entries"] = account_diffs

        v1_ignored = v1.get("ignored", [])
        v2_ignored = v2.get("ignored", [])
        if len(v1_ignored) != len(v2_ignored):
            diffs["ignored_count"] = {"v1": len(v1_ignored), "v2": len(v2_ignored)}

        return diffs

    def _compare_classified_entry(self, c1: dict, c2: dict) -> dict[str, Any]:
        diffs = {}
        for key in ("standard_code", "final_code", "confidence", "method", "account_code", "account_name"):
            v1_val = c1.get(key)
            v2_val = c2.get(key)
            if key == "confidence":
                if abs(float(v1_val or 0) - float(v2_val or 0)) > 0.0001:
                    diffs[key] = {"v1": v1_val, "v2": v2_val}
            elif v1_val != v2_val:
                diffs[key] = {"v1": v1_val, "v2": v2_val}
        return diffs

    def has_diffs(self) -> bool:
        return any(d for d in self._diffs)

    def diff_summary(self) -> list[dict[str, Any]]:
        return [d for d in self._diffs if d]

    def run_holdout(self, holdout_dir: str | Path = "datasets/HOLDOUT") -> dict[str, Any]:
        path = Path(holdout_dir)
        pdfs = sorted(path.glob("*.pdf"))
        results = {"total": len(pdfs), "diffs": 0, "ok": 0, "errors": [], "file_results": []}
        total_v1_time = 0.0
        total_v2_time = 0.0

        for pdf in pdfs:
            try:
                diff = self.compare_file(pdf)
                if diff:
                    results["diffs"] += 1
                else:
                    results["ok"] += 1
                v1 = self._results[-1]["v1"]
                v2 = self._results[-1]["v2"]
                total_v1_time += v1.get("elapsed_seconds", 0)
                total_v2_time += v2.get("elapsed_seconds_v2", 0)
                results["file_results"].append({
                    "file": pdf.name,
                    "has_diff": bool(diff),
                    "v1_time": v1.get("elapsed_seconds", 0),
                    "v2_time": v2.get("elapsed_seconds_v2", 0),
                    "v1_classified": v1.get("accounts_classified", 0),
                    "v2_classified": v2.get("accounts_classified", 0),
                })
            except Exception as e:
                results["errors"].append({"file": pdf.name, "error": str(e)})

        results["total_v1_time"] = round(total_v1_time, 3)
        results["total_v2_time"] = round(total_v2_time, 3)
        return results

    def run_dataset(
        self,
        dataset_dir: str | Path,
        label: str = "",
    ) -> dict[str, Any]:
        path = Path(dataset_dir)
        results: dict[str, Any] = {
            "label": label or path.name,
            "total": 0,
            "diffs": 0,
            "ok": 0,
            "errors": [],
            "file_results": [],
        }
        total_v1_time = 0.0
        total_v2_time = 0.0

        pdfs = sorted(path.glob("*.pdf"))
        if not pdfs:
            subdirs = [d for d in path.iterdir() if d.is_dir()]
            for sd in subdirs:
                pdfs.extend(sorted(sd.glob("*.pdf")))

        results["total"] = len(pdfs)

        for pdf in pdfs:
            try:
                diff = self.compare_file(pdf)
                if diff:
                    results["diffs"] += 1
                else:
                    results["ok"] += 1
                v1 = self._results[-1]["v1"]
                v2 = self._results[-1]["v2"]
                total_v1_time += v1.get("elapsed_seconds", 0)
                total_v2_time += v2.get("elapsed_seconds_v2", 0)
                results["file_results"].append({
                    "file": pdf.name,
                    "has_diff": bool(diff),
                    "v1_time": v1.get("elapsed_seconds", 0),
                    "v2_time": v2.get("elapsed_seconds_v2", 0),
                })
            except Exception as e:
                results["errors"].append({"file": pdf.name, "error": str(e)})

        results["total_v1_time"] = round(total_v1_time, 3)
        results["total_v2_time"] = round(total_v2_time, 3)
        return results

    def generate_report(self, output_path: str | Path = "reports/comparison_v1_v2.json") -> None:
        report = {
            "summary": {
                "total_files": len(self._results),
                "files_with_diffs": len(self._diffs),
                "files_ok": len(self._results) - sum(1 for d in self._diffs if d),
            },
            "diffs": self._diffs,
        }
        Path(output_path).write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
