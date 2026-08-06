"""Framework de extractores especializados (Sprint 34).

Infraestructura definitiva sobre la que se construirán los extractores
especializados (Nogales, AICSA, Wilug, Gonzagri, ...). Este sprint solo
deja la arquitectura preparada: TODOS los extractores delegan al Parser
Universal y el comportamiento del sistema es idéntico al actual.

Módulos:

  - base.py        ExtractorResult + ABC SpecializedExtractor
  - registry.py    Registro automático (decorator + diccionario interno)
  - universal.py   UniversalExtractor (delegación 1:1 al Parser Universal)
  - specialized.py Scaffolds: Nogales/Aicsa/Wilug/Gonzagri (delegan)
  - factory.py     SpecializedExtractorFactory (selección + fallback)

Uso rápido:

    from document_intelligence.extractors import (
        SpecializedExtractorFactory, UniversalExtractor, get_extractor,
    )

    factory = SpecializedExtractorFactory()
    extractor = factory.build(path, contexto_documento)
    result = extractor.extract(path, contexto_documento)
"""

from __future__ import annotations

from .base import ExtractorResult, SpecializedExtractor
from .registry import (
    get_extractor,
    get_extractor_for_family,
    instantiate,
    list_extractors,
    register_extractor,
    register_extractor_class,
)
from .universal import UniversalExtractor
from . import specialized  # noqa: F401 — registra los scaffolds al importar
from .double_column import DoubleColumnExtractor  # noqa: F401 — doble columna
from .factory import SpecializedExtractorFactory
from .profile_driven import GenericTableExtractor

__all__ = [
    "ExtractorResult",
    "SpecializedExtractor",
    "SpecializedExtractorFactory",
    "UniversalExtractor",
    "GenericTableExtractor",
    "register_extractor",
    "register_extractor_class",
    "get_extractor",
    "get_extractor_for_family",
    "list_extractors",
    "instantiate",
]
