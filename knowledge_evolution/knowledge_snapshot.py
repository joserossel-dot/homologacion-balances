from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd


class KnowledgeSnapshot:
    def __init__(
        self,
        cmcc_path: str | Path = "knowledge/cmcc.json",
        audit_path: str | Path = "reports/audit/audit_data.json",
        shadow_path: str | Path = "reports/cmcc_shadow/cmcc_shadow.xlsx",
        trace_path: str | Path = "reports/decision_trace/decision_trace.json",
    ):
        self.cmcc_path = Path(cmcc_path)
        self.audit_path = Path(audit_path)
        self.shadow_path = Path(shadow_path)
        self.trace_path = Path(trace_path)
        self.data: dict[str, Any] = {}

    def capture(self) -> dict[str, Any]:
        conceptos = self._load_cmcc()
        audit_data = self._load_audit()
        shadow_data = self._load_shadow()
        trace_data = self._load_trace()

        cmcc_bytes = json.dumps(conceptos, sort_keys=True).encode("utf-8") if conceptos else b""
        cmcc_hash = hashlib.sha256(cmcc_bytes).hexdigest()[:16]

        accounts = audit_data.get("accounts", [])
        classified = [a for a in accounts if a.get("final_code") is not None]
        unknown_accounts = [a for a in accounts if a.get("final_code") is None]

        concept_counts: Counter = Counter()
        for a in classified:
            code = str(a.get("final_code", "")).upper().strip()
            if code:
                concept_counts[code] += 1

        unknown_names = [str(a.get("account_name", "")).strip() for a in unknown_accounts if a.get("account_name")]

        variants_by_code: dict[str, list[str]] = {}
        for c in conceptos:
            code = c.get("codigo", "").upper().strip()
            variants_by_code[code] = [v.lower().strip() for v in c.get("variantes", [])]

        total_variants = sum(len(v) for v in variants_by_code.values())
        total_synonyms = sum(len(c.get("sinonimos", [])) for c in conceptos)
        total_rules = sum(1 for c in conceptos if c.get("patrones"))

        shadow_rows = len(shadow_data) if shadow_data is not None else 0

        stats = self._compute_statistics(accounts, classified, unknown_accounts)

        self.data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": stats.get("version", "1.0"),
            "cmcc_hash": cmcc_hash,
            "dictionary_hash": cmcc_hash,
            "variant_count": total_variants,
            "concept_count": len(conceptos),
            "rule_count": total_rules,
            "synonym_count": total_synonyms,
            "parser_version": "3.0",
            "shadow_version": "1.0",
            "decision_trace_version": "1.0",
            "statistics": stats,
            "variants_by_code": variants_by_code,
            "unknown_names": unknown_names,
            "concept_counts": dict(concept_counts.most_common()),
            "shadow_count": shadow_rows,
        }
        return self.data

    def _load_cmcc(self) -> list[dict]:
        if self.cmcc_path.exists():
            with open(self.cmcc_path, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _load_audit(self) -> dict:
        if self.audit_path.exists():
            with open(self.audit_path, encoding="utf-8") as f:
                return json.load(f)
        return {"accounts": []}

    def _load_shadow(self) -> Optional[list[dict]]:
        if self.shadow_path.exists():
            try:
                df = pd.read_excel(self.shadow_path)
                return df.to_dict("records")
            except Exception:
                return None
        return None

    def _load_trace(self) -> Optional[dict]:
        if self.trace_path.exists():
            try:
                with open(self.trace_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _compute_statistics(self, accounts: list, classified: list, unknown: list) -> dict:
        total = len(accounts) or 1
        return {
            "version": "1.0",
            "total_accounts": len(accounts),
            "total_classified": len(classified),
            "total_unknown": len(unknown),
            "classify_rate": round(len(classified) / total * 100, 1),
            "unknown_rate": round(len(unknown) / total * 100, 1),
            "companies": len(set(
                str(a.get("source_file", a.get("source_path", "")))
                for a in accounts if a.get("source_file") or a.get("source_path")
            )),
            "files": len(set(
                str(a.get("source_file", a.get("source_path", "")))
                for a in accounts
            )),
        }

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
