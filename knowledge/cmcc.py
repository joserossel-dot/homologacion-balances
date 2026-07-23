from __future__ import annotations
from pathlib import Path
from typing import Optional

from knowledge.concept import Concept
from knowledge.repository import Repository
from knowledge.normalizer import Normalizer, NormalizerResult
from knowledge.matcher import Matcher, MatchResult
from knowledge.metrics import Metrics


class CMCC:
    def __init__(self, cmcc_path: str | Path = "knowledge/cmcc.json"):
        self.repository = Repository(cmcc_path)
        self.normalizer = Normalizer()
        self.matcher = Matcher(self.repository, self.normalizer)
        self._loaded = False

    def load(self) -> None:
        self.repository.load()
        self.matcher = Matcher(self.repository, self.normalizer)
        self._loaded = True

    def save(self) -> None:
        self.repository.save()

    def normalize(self, text: str) -> NormalizerResult:
        return self.normalizer.normalize(text)

    def match(self, text: str, top_n: int = 10) -> list[MatchResult]:
        return self.matcher.match(text, top_n=top_n)

    def add_variant(self, codigo: str, variant: str) -> bool:
        concept = self.repository.find_by_codigo(codigo)
        if not concept:
            return False
        concept.add_variant(variant)
        return True

    def add_synonym(self, codigo: str, synonym: str) -> bool:
        concept = self.repository.find_by_codigo(codigo)
        if not concept:
            return False
        concept.add_synonym(synonym)
        return True

    def add_abbreviation(self, codigo: str, abbr: str) -> bool:
        concept = self.repository.find_by_codigo(codigo)
        if not concept:
            return False
        concept.add_abbreviation(abbr)
        return True

    def create_concept(self, concept: Concept) -> None:
        self.repository.add(concept)

    def find_by_id(self, concept_id: str) -> Optional[Concept]:
        return self.repository.find_by_id(concept_id)

    def find_by_codigo(self, codigo: str) -> Optional[Concept]:
        return self.repository.find_by_codigo(codigo)

    def find_by_name(self, name: str, exact: bool = True) -> list[Concept]:
        return self.repository.find_by_name(name, exact=exact)

    @property
    def metrics(self) -> Metrics:
        return Metrics(self.repository)

    @property
    def concepts(self) -> list[Concept]:
        return self.repository.list_all()

    @property
    def count(self) -> int:
        return self.repository.count()
