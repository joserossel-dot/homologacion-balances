from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.account_evidence import AccountEvidence


def serialize_evidence(ev: AccountEvidence) -> dict[str, Any]:
    d = ev.to_dict()
    d["_evidence_version"] = 1
    return d


def deserialize_evidence(data: dict[str, Any]) -> AccountEvidence:
    data.pop("_evidence_version", None)
    return AccountEvidence.from_dict(data)


def serialize_evidence_list(evidences: list[AccountEvidence]) -> list[dict[str, Any]]:
    return [serialize_evidence(e) for e in evidences]


def deserialize_evidence_list(data_list: list[dict[str, Any]]) -> list[AccountEvidence]:
    return [deserialize_evidence(d) for d in data_list]


def save_evidence_json(evidences: list[AccountEvidence], path: str | Path) -> Path:
    path = Path(path)
    data = {
        "_meta": {
            "version": 1,
            "type": "AccountEvidence",
            "count": len(evidences),
        },
        "evidences": serialize_evidence_list(evidences),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_evidence_json(path: str | Path) -> list[AccountEvidence]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    raw_list = data.get("evidences", data if isinstance(data, list) else [])
    return deserialize_evidence_list(raw_list)


def convert_shadow_to_evidences(
    shadow_path: str,
    evidence_path: str | None = None,
) -> list[AccountEvidence]:
    from evidence.evidence_builder import build_from_shadow_entry

    with open(shadow_path) as f:
        shadow = json.load(f)

    accounts = shadow.get("accounts", [])
    evidences = []
    for i, entry in enumerate(accounts):
        before = [{"account_name": a.get("account_name", "")} for a in accounts[max(0, i - 3):i]]
        after = [{"account_name": a.get("account_name", "")} for a in accounts[i + 1:i + 4]]
        ev = build_from_shadow_entry(
            entry,
            context_before=before,
            context_after=after,
        )
        ev.record_id = f"ev_{i:06d}"
        ev.row_number = i
        evidences.append(ev)

    if evidence_path:
        save_evidence_json(evidences, evidence_path)

    return evidences


def to_shadow_compatible(evidences: list[AccountEvidence]) -> list[dict]:
    result = []
    for ev in evidences:
        d = {
            "account_code": ev.original_account_code or ev.clean_account_code,
            "account_name": ev.original_account_name or ev.clean_account_name,
            "nature": ev.metadata.get("nature", ""),
            "classification_amount": ev.classification_amount,
            "standard_code": ev.final_code if ev.final_code else None,
            "final_code": ev.final_code if ev.final_code else None,
            "confidence": ev.classification_confidence,
            "method": ev.classification_method,
            "reason": ev.metadata.get("reason", ""),
            "special_rule": "",
            "source_file": ev.source_file,
            "source_page": ev.source_page,
            "semantic_result": {
                "semantic_type": ev.semantic_type or "unknown",
                "financial_statement": "",
                "economic_nature": "",
                "presentation": "",
                "expected_side": ev.expected_side or "unknown",
                "parent_category": "",
                "contra_account_type": None,
                "confidence": ev.classification_confidence,
                "matched_rule": ev.semantic_rule or "no_match",
                "observations": "",
            },
            "source_group": ev.source_group,
            "source_path": ev.source_path,
        }
        result.append(d)
    return result
