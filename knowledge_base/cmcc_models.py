from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


SECCIONES = {
    "AC": "Activo",
    "ANC": "Activo No Corriente",
    "PC": "Pasivo",
    "PNC": "Pasivo No Corriente",
    "PAT": "Patrimonio",
    "ER": "Resultado",
}


def inferir_seccion(codigo: str) -> str:
    prefijo = codigo.split(".")[0] if "." in codigo else codigo
    return SECCIONES.get(prefijo, "Desconocido")


def inferir_nivel(codigo: str) -> int:
    if "." not in codigo:
        return 1
    partes = codigo.split(".")
    if len(partes) >= 2 and partes[1]:
        return 3
    return 2


@dataclass
class VariantInfo:
    nombre: str
    normalized: str
    frecuencia: int = 0
    confianza: float = 0.0
    source_records: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "frecuencia": self.frecuencia,
            "confianza": round(self.confianza, 4),
            "source_records": self.source_records[:20],
        }


@dataclass
class CodeEntry:
    codigo: str
    nombre: str = ""
    frecuencia: int = 0
    variantes: list[VariantInfo] = field(default_factory=list)
    seccion: str = ""
    nivel: int = 0
    empresas: list[str] = field(default_factory=list)
    archivos: list[str] = field(default_factory=list)
    naturaleza: str = ""
    usage_count: int = 0
    fecha_primera: str = ""
    fecha_ultima: str = ""
    confianza: float = 0.0
    variante_canonica: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "nombre": self.nombre,
            "frecuencia": self.frecuencia,
            "variantes": [v.to_dict() for v in self.variantes],
            "seccion": self.seccion,
            "nivel": self.nivel,
            "empresas": sorted(set(self.empresas)),
            "archivos": sorted(set(self.archivos)),
            "naturaleza": self.naturaleza,
            "usage_count": self.usage_count,
            "confianza": round(self.confianza, 4),
            "variante_canonica": self.variante_canonica,
        }


@dataclass
class FamilyGroup:
    nombre: str
    prefijo: str
    seccion: str
    nivel_base: int
    miembros: list[str] = field(default_factory=list)
    total_frecuencia: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "prefijo": self.prefijo,
            "seccion": self.seccion,
            "miembros": self.miembros,
            "total_frecuencia": self.total_frecuencia,
        }


@dataclass
class KnowledgeBase:
    generated_at: str = ""
    total_codes: int = 0
    total_records: int = 0
    codes: dict[str, CodeEntry] = field(default_factory=dict)
    families: list[FamilyGroup] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "generated_at": self.generated_at,
                "total_codes": self.total_codes,
                "total_records": self.total_records,
                "total_families": len(self.families),
            },
            "families": [f.to_dict() for f in self.families],
            "codes": {k: v.to_dict() for k, v in sorted(self.codes.items())},
        }
