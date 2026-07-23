from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from knowledge.concept import Concept


class Repository:
    def __init__(self, path: str | Path = "knowledge/cmcc.json"):
        self.path = Path(path)
        self.concepts: list[Concept] = []
        self._index_by_id: dict[str, Concept] = {}
        self._index_by_codigo: dict[str, Concept] = {}
        self._loaded = False

    def load(self) -> list[Concept]:
        if not self.path.exists():
            self.concepts = []
            self._rebuild_index()
            self._loaded = True
            return self.concepts
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.concepts = [Concept.from_dict(item) for item in raw]
        self._rebuild_index()
        self._loaded = True
        return self.concepts

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [c.to_dict() for c in self.concepts]
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _rebuild_index(self) -> None:
        self._index_by_id = {}
        self._index_by_codigo = {}
        for c in self.concepts:
            self._index_by_id[c.id] = c
            self._index_by_codigo[c.codigo] = c

    def find_by_id(self, concept_id: str) -> Concept | None:
        return self._index_by_id.get(concept_id)

    def find_by_codigo(self, codigo: str) -> Concept | None:
        return self._index_by_codigo.get(codigo)

    def find_by_name(self, name: str, exact: bool = True) -> list[Concept]:
        name_lower = name.lower().strip()
        results = []
        for c in self.concepts:
            candidates = [c.nombre.lower()] + [s.lower() for s in c.sinonimos]
            if exact:
                if name_lower in candidates:
                    results.append(c)
            else:
                if any(name_lower in cand or cand in name_lower for cand in candidates):
                    results.append(c)
        return results

    def find_candidates(self, tokens: set[str]) -> list[tuple[Concept, float]]:
        if not tokens:
            return []
        scored = []
        for c in self.concepts:
            concept_tokens = set(c.all_tokens)
            if not concept_tokens:
                continue
            intersection = tokens & concept_tokens
            if not intersection:
                continue
            jaccard = len(intersection) / len(tokens | concept_tokens)
            overlap = len(intersection) / max(len(tokens), len(concept_tokens))
            score = 0.6 * jaccard + 0.4 * overlap
            if score > 0:
                scored.append((c, round(score, 4)))
        scored.sort(key=lambda x: -x[1])
        return scored[:20]

    def add(self, concept: Concept) -> None:
        if concept.id in self._index_by_id:
            raise ValueError(f"Concept with id '{concept.id}' already exists")
        self.concepts.append(concept)
        self._index_by_id[concept.id] = concept
        self._index_by_codigo[concept.codigo] = concept

    def remove(self, concept_id: str) -> bool:
        c = self._index_by_id.get(concept_id)
        if not c:
            return False
        self.concepts.remove(c)
        self._rebuild_index()
        return True

    def count(self) -> int:
        return len(self.concepts)

    def list_all(self) -> list[Concept]:
        return self.concepts.copy()
