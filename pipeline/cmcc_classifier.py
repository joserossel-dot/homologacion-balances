from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Optional

from rapidfuzz import fuzz as rf

from knowledge.normalizer import Normalizer


class CMCCClassifier:
    def __init__(self, cmcc_path: str | Path = "knowledge/cmcc.json"):
        self.normalizer = Normalizer()
        with open(cmcc_path, "r", encoding="utf-8") as f:
            self.concepts = json.load(f)
        self._concepts_by_name: dict[str, dict] = {}
        self._all_variants: list[tuple[str, str, str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        for c in self.concepts:
            self._concepts_by_name[c["nombre"]] = c
            name_norm = self.normalizer.normalize(c["nombre"]).text
            self._all_variants.append((name_norm, c["nombre"], c["codigo"], "nombre"))
            for syn in c.get("sinonimos", []):
                syn_norm = self.normalizer.normalize(syn).text
                self._all_variants.append((syn_norm, syn, c["codigo"], "sinonimo"))
            for abbr in c.get("abreviaturas", []):
                abbr_norm = self.normalizer.normalize(abbr).text
                self._all_variants.append((abbr_norm, abbr, c["codigo"], "abreviatura"))
            for var in c.get("variantes", []):
                var_norm = self.normalizer.normalize(var).text
                self._all_variants.append((var_norm, var, c["codigo"], "variante"))

    def classify(self, account_name: str) -> dict[str, Any]:
        if not account_name or not isinstance(account_name, str):
            return {"code": None, "concept": None, "score": 0.0,
                    "matched_variant": None, "matched_concept": None,
                    "method": "none", "evidence": "empty_input"}
        norm_input = self.normalizer.normalize(account_name).text
        if not norm_input:
            return {"code": None, "concept": None, "score": 0.0,
                    "matched_variant": None, "matched_concept": None,
                    "method": "none", "evidence": "empty_after_normalization"}

        best: dict[str, Any] = {
            "score": 0.0, "code": None, "matched_variant": None,
            "matched_concept": None, "method": "none", "evidence": [],
        }

        for norm_variant, original_variant, code, source in self._all_variants:
            if not norm_variant:
                continue
            score = self._score(norm_input, norm_variant)
            if score > best["score"]:
                concept = self._concepts_by_name.get(
                    next((c["nombre"] for c in self.concepts if c["codigo"] == code), ""))
                best = {
                    "score": round(score, 4),
                    "code": code,
                    "concept": concept["nombre"] if concept else code,
                    "matched_variant": original_variant,
                    "matched_concept": next(
                        (c["nombre"] for c in self.concepts if c["codigo"] == code), ""),
                    "method": f"cmcc_{source}",
                    "evidence": [f"matched_{source}: {original_variant[:80]}"],
                }
        if best["score"] > 0:
            return best
        return {"code": None, "concept": None, "score": 0.0,
                "matched_variant": None, "matched_concept": None,
                "method": "cmcc_none", "evidence": ["no_match"]}

    def _score(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        exact = 1.0 if a == b else 0.0
        token_sort = rf.token_sort_ratio(a, b) / 100.0
        token_set = rf.token_set_ratio(a, b) / 100.0
        partial = rf.partial_ratio(a, b) / 100.0
        weighted = (exact * 0.4 + token_sort * 0.3 + token_set * 0.2 + partial * 0.1)
        return round(weighted, 4)

    def classify_batch(self, names: list[str]) -> list[dict[str, Any]]:
        return [self.classify(n) for n in names]
