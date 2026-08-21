from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from semantic.models import SemanticMatch
from semantic.normalizer import SemanticNormalizer
from semantic.scorer import Scorer


class SemanticMatcher:
    """Matcher semántico de cuentas contables.

    Independiente del pipeline. Solo conoce:
    - Concept Catalog (knowledge/concept_catalog.json)
    - Normalizer y Scorer propios

    No conoce:
    - CMCC (el código viene del catálogo, no es lógica interna)
    - Regex
    - Parser
    - Pipeline
    """

    def __init__(self, catalog_path: str):
        self._catalog_path = catalog_path
        self._catalog = self._load_catalog(catalog_path)
        self._normalizer = SemanticNormalizer(self._catalog)
        self._scorer = Scorer()

    def _load_catalog(self, path: str) -> list[dict]:
        """Carga conceptos desde concept_catalog.json."""
        with open(path) as f:
            data = json.load(f)
        concepts = data.get("concepts", [])
        if not concepts:
            raise ValueError(f"Catálogo vacío o inválido en {path}")
        return concepts

    @property
    def concept_count(self) -> int:
        return len(self._catalog)

    def match(
        self,
        account_name: str,
        account_type: Optional[str] = None,
    ) -> SemanticMatch:
        """Matching completo de una cuenta contra el catálogo.

        Flujo:
        1. Normalizar nombre
        2. Extraer raíz léxica
        3. Evaluar los 6 tiers contra cada concepto
        4. Retornar el mejor match (o UNKNOWN)
        """
        if not account_name or len(account_name.strip()) < 3:
            return SemanticMatch(account_name=account_name)

        norm = self._normalizer.normalize(account_name)
        if not norm or len(norm) < 2:
            return SemanticMatch(account_name=account_name)

        root_word = self._normalizer.root_word(account_name)

        best: Optional[SemanticMatch] = None

        for concept in self._catalog:
            result = self._scorer.evaluate_concept(
                norm, concept, root_word, account_type
            )
            if result is not None:
                if best is None or result.score > best.score:
                    best = result

        if best is not None and best.score >= 0.60:
            return best

        return SemanticMatch(account_name=account_name)

    def match_batch(
        self,
        names: list[str],
        types: Optional[list[str]] = None,
    ) -> list[SemanticMatch]:
        results = []
        for i, name in enumerate(names):
            at = types[i] if types and i < len(types) else None
            results.append(self.match(name, at))
        return results

    def get_concept(self, concept_id: str) -> Optional[dict]:
        for c in self._catalog:
            if c["id"] == concept_id:
                return c
        return None

    def explain(self, account_name: str) -> str:
        """Retorna explicación legible del match."""
        match = self.match(account_name)
        if match.is_unknown:
            return f"UNKNOWN: '{account_name}' no match para ningún concepto"
        tier_names = {1: "keyword exacto", 2: "sinónimo exacto", 3: "abreviatura",
                      4: "fuzzy keyword", 5: "fuzzy sinónimo", 6: "raíz léxica"}
        return (
            f"'{account_name}' → {match.concept_name} ({match.concept_id}) "
            f"vía {tier_names.get(match.match_tier, '?')} "
            f"score={match.score:.4f} confianza={match.confidence} "
            f"→ {match.expected_cmcc}"
        )

    def benchmark_on_accounts(
        self,
        accounts: list[dict],
    ) -> dict:
        """Benchmark sobre lista de cuentas.

        Cada cuenta debe tener:
          - account_name (str)
          - account_code (str)
          - tipo (str) — opcional
          - source_file (str) — opcional
        """
        results = []
        t_start = time.perf_counter()

        for a in accounts:
            name = a.get("account_name", "")
            atype = a.get("tipo")
            match = self.match(name, atype)
            results.append(match.to_dict())

        elapsed = time.perf_counter() - t_start

        total = len(results)
        classified = sum(1 for r in results if not r["is_unknown"])
        unknown = total - classified

        concept_usage: dict[str, int] = {}
        tier_usage: dict[int, int] = {}
        confidence_dist: dict[str, int] = {}

        for r in results:
            if not r["is_unknown"]:
                cid = r["concept_id"]
                concept_usage[cid] = concept_usage.get(cid, 0) + 1
                tier = r["match_tier"]
                tier_usage[tier] = tier_usage.get(tier, 0) + 1
                conf = r["confidence"]
                confidence_dist[conf] = confidence_dist.get(conf, 0) + 1

        avg_score = 0.0
        if classified > 0:
            avg_score = sum(r["score"] for r in results if not r["is_unknown"]) / classified

        return {
            "metadata": {
                "total_accounts": total,
                "classified": classified,
                "unknown": unknown,
                "classification_rate": round(classified / total * 100, 2) if total else 0,
                "avg_score": round(avg_score, 4),
                "elapsed_seconds": round(elapsed, 2),
                "avg_ms_per_account": round(elapsed / total * 1000, 2) if total else 0,
                "concepts_used": len(concept_usage),
                "total_concepts_available": self.concept_count,
            },
            "concept_usage": dict(sorted(concept_usage.items(), key=lambda x: -x[1])),
            "tier_usage": dict(sorted(tier_usage.items())),
            "confidence_distribution": dict(sorted(confidence_dist.items(), key=lambda x: -x[1])),
            "results": results,
        }
