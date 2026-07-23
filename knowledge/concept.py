from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date


@dataclass
class Concept:
    id: str
    codigo: str
    nombre: str
    categoria: str
    tipo_estado_financiero: str
    sinonimos: list[str] = field(default_factory=list)
    abreviaturas: list[str] = field(default_factory=list)
    variantes: list[str] = field(default_factory=list)
    palabras_clave: list[str] = field(default_factory=list)
    patrones: list[str] = field(default_factory=list)
    ejemplos: list[str] = field(default_factory=list)
    empresas: list[str] = field(default_factory=list)
    confidence: float = 0.5
    version: str = "1.0.0"
    ultima_revision: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Concept:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    def add_variant(self, variant: str) -> None:
        if variant and variant not in self.variantes:
            self.variantes.append(variant)

    def add_synonym(self, synonym: str) -> None:
        if synonym and synonym not in self.sinonimos:
            self.sinonimos.append(synonym)

    def add_abbreviation(self, abbr: str) -> None:
        if abbr and abbr not in self.abreviaturas:
            self.abreviaturas.append(abbr)

    def add_example(self, example: str) -> None:
        if example and example not in self.ejemplos:
            self.ejemplos.append(example)

    def add_empresa(self, empresa: str) -> None:
        if empresa and empresa not in self.empresas:
            self.empresas.append(empresa)

    @property
    def all_tokens(self) -> list[str]:
        tokens = []
        tokens.extend(self.nombre.lower().split())
        for s in self.sinonimos:
            tokens.extend(s.lower().split())
        for a in self.abreviaturas:
            tokens.append(a.lower())
        for v in self.variantes:
            tokens.extend(v.lower().split())
        for k in self.palabras_clave:
            tokens.append(k.lower())
        return list(set(tokens))

    @property
    def coverage_score(self) -> float:
        score = 1.0
        if self.sinonimos:
            score += 0.3 * min(len(self.sinonimos), 5)
        if self.abreviaturas:
            score += 0.2 * min(len(self.abreviaturas), 5)
        if self.variantes:
            score += 0.1 * min(len(self.variantes), 10)
        if self.patrones:
            score += 0.3 * min(len(self.patrones), 5)
        if self.ejemplos:
            score += 0.1 * min(len(self.ejemplos), 10)
        return round(min(score, 5.0), 1)
