"""Registro central de extractores (Sprint 34).

Un diccionario interno mapea `id` de extractor → clase, más un índice
inverso familia → ids de extractores para resolver "qué extractor sabe
procesar esta familia".

Se puebla de dos formas equivalentes:

    1. Decorador:  @register_extractor()
    2. Función:    register_extractor_class(Cls)

El decorador acepta kwargs opcionales (id, display_name, families) que
sobreescriben los atributos de clase si se quiere definirlos ahí.

Registrar dos veces la misma clase es idempotente (no duplica entradas).
"""

from __future__ import annotations

from typing import Optional

from .base import FAMILIA_DESCONOCIDA, SpecializedExtractor

# id de extractor → clase
_REGISTRY: dict[str, type[SpecializedExtractor]] = {}
# family_id → lista de extractor_ids (orden de registro)
_FAMILY_INDEX: dict[str, list[str]] = {}


def register_extractor_class(cls: type[SpecializedExtractor]) -> None:
    """Registra la clase en el diccionario interno (idempotente)."""
    extractor_id = getattr(cls, "id", "specialized")
    _REGISTRY[extractor_id] = cls
    for family_id in getattr(cls, "supported_families", []) or []:
        if family_id and family_id != FAMILIA_DESCONOCIDA:
            registrados = _FAMILY_INDEX.setdefault(family_id, [])
            if extractor_id not in registrados:
                registrados.append(extractor_id)


def register_extractor(
    cls: Optional[type[SpecializedExtractor]] = None,
    *,
    id: Optional[str] = None,
    display_name: Optional[str] = None,
    families: Optional[list[str]] = None,
):
    """Decorador para registrar un extractor automáticamente.

    Uso:

        @register_extractor()
        class NogalesExtractor(SpecializedExtractor):
            id = "nogales"
            supported_families = ["cluster_4c326713f3"]

        @register_extractor(id="aicsa", families=["cluster_0a1bebffff"])
        class AicsaExtractor(SpecializedExtractor):
            ...

    También funciona sin paréntesis: `@register_extractor`.
    """
    def _wrap(clase):
        if id is not None:
            clase.id = id
        if display_name is not None:
            clase.display_name = display_name
        if families is not None:
            clase.supported_families = list(families)
        register_extractor_class(clase)
        return clase

    if cls is not None:
        return _wrap(cls)
    return _wrap


def get_extractor(extractor_id: str) -> Optional[type[SpecializedExtractor]]:
    """Clase registrada para el id, o None."""
    return _REGISTRY.get(extractor_id)


def list_extractors() -> list[str]:
    """Ids de todos los extractores registrados (ordenados)."""
    return sorted(_REGISTRY)


def get_extractor_for_family(family_id: str) -> Optional[type[SpecializedExtractor]]:
    """Primer extractor registrado para esa familia (orden de registro).

    Devuelve None si no hay ningún extractor especializado para la familia
    → el llamador debe usar UniversalExtractor.
    """
    for extractor_id in _FAMILY_INDEX.get(family_id, []):
        clase = _REGISTRY.get(extractor_id)
        if clase is not None:
            return clase
    return None


def instantiate(extractor_id: str, *args, **kwargs) -> Optional[SpecializedExtractor]:
    """Instancia el extractor registrado, o None si no existe."""
    clase = _REGISTRY.get(extractor_id)
    return clase(*args, **kwargs) if clase is not None else None
