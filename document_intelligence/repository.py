from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .signature import FormatSignature


class FormatRepository:
    def __init__(self, path: str | Path = "format_families.json"):
        self.path = Path(path)
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._cache = raw
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_signature(self, family_name: str, sig: FormatSignature):
        if family_name not in self._cache:
            self._cache[family_name] = []
        existing = [
            s for s in self._cache[family_name]
            if s.get("company_name") == sig.company_name
            and s.get("code_pattern") == sig.code_pattern.value
        ]
        entry = sig.to_dict()
        if existing:
            existing[0].update(entry)
        else:
            self._cache[family_name].append(entry)
        self._save()

    def load_family(self, family_name: str) -> list[FormatSignature]:
        raw_list = self._cache.get(family_name, [])
        return [FormatSignature.from_dict(d) for d in raw_list]

    def list_families(self) -> list[str]:
        return list(self._cache.keys())

    def remove_family(self, family_name: str):
        self._cache.pop(family_name, None)
        self._save()

    def find_by_code_pattern(self, pattern: str) -> list[FormatSignature]:
        results = []
        for family_list in self._cache.values():
            for d in family_list:
                if d.get("code_pattern") == pattern:
                    results.append(FormatSignature.from_dict(d))
        return results

    def find_by_layout(self, layout: str) -> list[FormatSignature]:
        results = []
        for family_list in self._cache.values():
            for d in family_list:
                if d.get("layout") == layout:
                    results.append(FormatSignature.from_dict(d))
        return results

    def get_statistics(self) -> dict[str, Any]:
        total = 0
        family_counts: dict[str, int] = {}
        for family_name, entries in self._cache.items():
            family_counts[family_name] = len(entries)
            total += len(entries)
        return {
            "total_families": len(self._cache),
            "total_signatures": total,
            "families": family_counts,
        }
