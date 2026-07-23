from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .decision_trace import DecisionTrace
from .enums import DecisionCode


_METHOD_TO_CODE: dict[str, DecisionCode] = {
    "learning_exact": DecisionCode.D001,
    "learning_fuzzy": DecisionCode.D005,
    "dictionary_exact": DecisionCode.D002,
    "dictionary_fuzzy": DecisionCode.D005,
    "code": DecisionCode.D006,
    "unclassified": DecisionCode.D201,
    "cmcc_nombre": DecisionCode.D001,
    "cmcc_variante": DecisionCode.D001,
    "cmcc_sinonimo": DecisionCode.D004,
    "cmcc_abreviatura": DecisionCode.D003,
    "cmcc_none": DecisionCode.D201,
}


class TraceBuilder:
    def __init__(
        self,
        audit_path: str | Path = "reports/audit/audit_data.json",
        shadow_path: str | Path = "reports/cmcc_shadow/cmcc_shadow.xlsx",
    ):
        self.audit_path = Path(audit_path)
        self.shadow_path = Path(shadow_path)
        self.traces: list[DecisionTrace] = []

    def build_all(self) -> list[DecisionTrace]:
        with open(self.audit_path, encoding="utf-8") as f:
            audit = json.load(f)

        accounts: list[dict] = audit.get("accounts", [])
        files_map: dict[str, dict] = {}
        for f_info in audit.get("files", []):
            src = f_info.get("source_file", "") or f_info.get("path", "")
            files_map[src] = f_info

        shadow_by_cuenta: dict[str, list[dict]] = defaultdict(list)
        if self.shadow_path.exists():
            shadow_df = pd.read_excel(self.shadow_path)
            for _, row in shadow_df.iterrows():
                cuenta = str(row.get("Cuenta", "")).strip()
                shadow_by_cuenta[cuenta].append({
                    "codigo": str(row.get("Código sugerido", "")).strip(),
                    "concepto": str(row.get("Concepto", "")).strip(),
                    "score": self._safe_float(row.get("Score", 0)),
                    "metodo": str(row.get("Método", "")).strip(),
                    "variante": str(row.get("Variante utilizada", "")).strip(),
                })

        self.traces = []
        for a in accounts:
            trace = self._build_one(a, files_map, shadow_by_cuenta)
            self.traces.append(trace)

        return self.traces

    def _build_one(
        self,
        account: dict,
        files_map: dict[str, dict],
        shadow_by_cuenta: dict[str, list[dict]],
    ) -> DecisionTrace:
        original = str(account.get("account_name", "")).strip()
        method = str(account.get("method", "unclassified")).strip().lower()
        reason = str(account.get("reason", "")).strip()
        final_code = account.get("final_code")
        confidence = self._safe_float(account.get("confidence", 0))
        source_file = str(account.get("source_file", account.get("source_path", ""))).strip()
        source_group = str(account.get("source_group", "")).strip()
        nature = str(account.get("nature", "")).strip()
        standard_code = account.get("standard_code")
        special_rule = account.get("special_rule")

        f_info = files_map.get(source_file, {})
        file_type = str(f_info.get("file_type", "")).strip().lower() if f_info else ""

        normalized = self._normalize_name(original)
        normalized_for_key = normalized[:80]

        is_unknown = method == "unclassified" or final_code is None

        decision_code, decision_desc = self._resolve_decision(method, reason, is_unknown, confidence)

        shadow_matches = shadow_by_cuenta.get(original, [])
        shadow_classification = ""
        shadow_confidence = 0.0

        inline_shadow = account.get("cmcc_shadow")
        if inline_shadow and isinstance(inline_shadow, dict):
            sc = inline_shadow.get("code") or inline_shadow.get("codigo")
            if sc:
                shadow_classification = str(sc)
                shadow_confidence = self._safe_float(inline_shadow.get("score", 0))

        if not shadow_classification:
            for sm in shadow_matches:
                shadow_classification = sm.get("codigo", "")
                shadow_confidence = self._safe_float(sm.get("score", 0))

        official_classification = str(final_code) if final_code and not is_unknown else "UNKNOWN"
        official_confidence = 0.0 if is_unknown else confidence

        cmcc_match = not is_unknown and (
            method.startswith("learning") or method.startswith("cmcc")
        )
        if cmcc_match:
            if method.startswith("cmcc"):
                cmcc_match_type = method.replace("cmcc_", "")
                cmcc_score = official_confidence
            else:
                cmcc_match_type = "exact" if method == "learning_exact" else "fuzzy"
                cmcc_score = official_confidence
        else:
            cmcc_match_type = ""
            cmcc_score = 0.0
        cmcc_variant = self._extract_variant_from_reason(reason) if cmcc_match else ""

        dictionary_match = method in ("dictionary_exact", "dictionary_fuzzy")
        dictionary_source = self._extract_code_from_reason(reason) if dictionary_match else ""

        layout = source_group if source_group else "unknown"
        layout_confidence = 1.0 if layout in ("validacion",) else 0.5 if layout == "edge_cases" else 0.0
        ocr_confidence = 1.0 if file_type == "excel" else 0.8 if file_type == "pdf" else 0.5
        parser_confidence = 0.8 if not is_unknown else 0.0
        column_mapping_confidence = 0.8 if layout in ("validacion",) else 0.5
        candidate_accept_rate = official_confidence if not is_unknown else 0.0
        candidate_status = "accepted" if not is_unknown else "rejected"
        candidate_reasons = [reason] if reason else []

        company = self._extract_company(source_file)

        document_id = f"{source_file}::{account.get('account_code', '')}"

        return DecisionTrace(
            document_id=document_id,
            company=company,
            layout=layout,
            layout_confidence=layout_confidence,
            ocr_confidence=ocr_confidence,
            parser_confidence=parser_confidence,
            column_mapping_confidence=column_mapping_confidence,
            candidate_accept_rate=candidate_accept_rate,
            candidate_status=candidate_status,
            candidate_reasons=candidate_reasons,
            normalized_name=normalized,
            original_name=original,
            cmcc_match=cmcc_match,
            cmcc_match_type=cmcc_match_type,
            cmcc_variant=cmcc_variant,
            cmcc_score=cmcc_score,
            dictionary_match=dictionary_match,
            dictionary_source=dictionary_source,
            official_classification=official_classification,
            official_confidence=official_confidence,
            shadow_classification=shadow_classification,
            shadow_confidence=shadow_confidence,
            decision_code=decision_code,
            decision_description=decision_desc,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _resolve_decision(self, method: str, reason: str, is_unknown: bool, confidence: float) -> tuple[str, str]:
        if not is_unknown:
            code = _METHOD_TO_CODE.get(method, DecisionCode.D001)
            return code.value, reason or code.describe()

        shadow_note = ""
        if confidence > 0 and is_unknown:
            pass

        return DecisionCode.D201.value, "Sin coincidencia en código ni diccionario"

    @staticmethod
    def _normalize_name(name: str) -> str:
        if not name:
            return ""
        n = name.lower().strip()
        n = re.sub(r"\s+", " ", n)
        return n[:120]

    @staticmethod
    def _extract_variant_from_reason(reason: str) -> str:
        m = re.search(r"matched:\s*(.+?)\)?\s*$", reason)
        if m:
            return m.group(1).strip()
        m = re.search(r"→\s*(.+?)$", reason)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _extract_code_from_reason(reason: str) -> str:
        m = re.search(r"→\s*(\S+)", reason)
        if m:
            return m.group(1).strip()
        return ""

    @staticmethod
    def _extract_company(source_file: str) -> str:
        if not source_file:
            return ""
        name = Path(source_file).stem
        name = re.sub(r"^\d+\s*", "", name)
        name = re.sub(r"\s*\d{4}.*$", "", name)
        return name.strip()[:80]

    @staticmethod
    def _safe_float(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (ValueError, TypeError, OverflowError):
            return 0.0
