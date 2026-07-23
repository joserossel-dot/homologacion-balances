from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class QualitySnapshot:
    def __init__(self, snapshot_id: str | None = None):
        self.snapshot_id = snapshot_id or datetime.now(timezone.utc).strftime("snap_%Y%m%d_%H%M%S")
        self.data: dict[str, Any] = {}

    def capture(
        self,
        audit_path: str | Path = "reports/audit/audit_data.json",
        cmcc_path: str | Path = "knowledge/cmcc.json",
        shadow_path: str | Path = "reports/cmcc_shadow/cmcc_shadow.xlsx",
        trace_path: str | Path = "reports/decision_trace/decision_trace.json",
    ) -> dict[str, Any]:
        audit_data = self._load_json(audit_path) or {"accounts": [], "files": []}
        cmcc_data = self._load_json(cmcc_path) or []
        shadow_data = self._load_shadow(shadow_path)
        trace_data = self._load_json(trace_path) or {}

        accounts = audit_data.get("accounts", [])
        files_info = audit_data.get("files", [])

        classified = [a for a in accounts if a.get("final_code") is not None]
        unknown = [a for a in accounts if a.get("final_code") is None]
        total = len(accounts) or 1

        coverage = round(len(classified) / total * 100, 1)
        unknown_rate = round(len(unknown) / total * 100, 1)

        cmcc_bytes = json.dumps(cmcc_data, sort_keys=True).encode("utf-8") if cmcc_data else b""
        cmcc_hash = hashlib.sha256(cmcc_bytes).hexdigest()[:16]

        decision_dist = dict(Counter(a.get("method", "unknown") for a in accounts).most_common())
        layout_dist = dict(Counter(
            str(a.get("source_group", "unknown")) for a in accounts
        ).most_common())
        unknown_dist = dict(Counter(
            str(a.get("reason", "unknown"))[:60] for a in accounts
            if a.get("final_code") is None
        ).most_common(10)) if unknown else {}

        avg_parser_conf = round(
            sum(self._safe_float(a.get("confidence", 0)) for a in classified) / max(len(classified), 1), 4
        )

        shadow_count = len(shadow_data) if shadow_data else 0
        trace_summary = trace_data.get("summary", {}) if trace_data else {}

        doc_types = Counter(f.get("file_type", "unknown") for f in files_info)
        ocr_dist = {"pdf": doc_types.get("pdf", 0), "excel": doc_types.get("excel", 0),
                     "unknown": doc_types.get("unknown", 0)}

        self.data = {
            "snapshot_id": self.snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": self._get_git_commit(),
            "cmcc_version": "1.0",
            "dictionary_hash": cmcc_hash,
            "parser_version": "3.0",
            "documents": len(files_info),
            "accounts": len(accounts),
            "classified": len(classified),
            "unknown": len(unknown),
            "coverage": coverage,
            "unknown_rate": unknown_rate,
            "accuracy": trace_summary.get("classify_rate", coverage),
            "precision": trace_summary.get("classify_rate", coverage),
            "recall": trace_summary.get("classify_rate", coverage),
            "macro_f1": 0.0,
            "micro_f1": 0.0,
            "shadow_precision": 0.0,
            "parser_precision": 0.0,
            "ocr_precision": 0.0,
            "layout_precision": 0.0,
            "average_parser_confidence": avg_parser_conf,
            "average_document_confidence": avg_parser_conf,
            "layout_distribution": layout_dist,
            "ocr_distribution": ocr_dist,
            "decision_distribution": decision_dist,
            "unknown_distribution": unknown_dist,
            "shadow_count": shadow_count,
            "concept_count": len(cmcc_data),
            "variant_count": sum(len(c.get("variantes", [])) for c in cmcc_data) if cmcc_data else 0,
        }
        return self.data

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return out

    @staticmethod
    def load(path: str | Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_json(path: Path) -> Any:
        p = Path(path)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    @staticmethod
    def _load_shadow(path: Path) -> list[dict] | None:
        p = Path(path)
        if p.exists():
            try:
                df = pd.read_excel(p)
                return df.to_dict("records")
            except Exception:
                return None
        return None

    @staticmethod
    def _safe_float(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError, OverflowError):
            return 0.0

    @staticmethod
    def _get_git_commit() -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--oneline", "-1"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()[:40] if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"
