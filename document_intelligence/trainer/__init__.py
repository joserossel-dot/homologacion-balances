"""Extractor Trainer — aprendizaje automático de formatos (Sprint 35).

Sistema que aprende automáticamente cómo extraer una familia documental a
partir de los balances existentes. NO modifica el Parser Universal ni el
pipeline: solo genera perfiles estructurales (JSON) que el Sprint 36
(GenericTableExtractor) consumirá para reemplazar gradualmente al
universal cuando exista un perfil confiable.

Módulos:

  - profile.py     TableProfile, ColumnProfile, HeaderProfile, FooterProfile
  - trainer.py     TableProfileTrainer (aprende el perfil de una familia)
  - repository.py  ProfileRepository (persistencia JSON + reporte)
  - validator.py   ProfileValidator (cobertura, precisión, columnas, filas)

Uso rápido:

    from document_intelligence.trainer import (
        TableProfileTrainer, ProfileValidator, ProfileRepository,
    )

    profile = TableProfileTrainer().train(family_id, name, doc_paths)
    profile.validation = ProfileValidator().validate(profile, doc_paths)
    ProfileRepository().save({family_id: profile})
"""

from __future__ import annotations

from .profile import (
    AMOUNT_HEADER_KEYWORDS,
    AMOUNT_ORDER,
    CODE_HEADER_KEYWORDS,
    NAME_HEADER_KEYWORDS,
    COLUMN_LABELS,
    ColumnProfile,
    FooterProfile,
    HeaderProfile,
    TableProfile,
)
from .trainer import TableProfileTrainer
from .validator import ProfileValidator
from .repository import ProfileRepository

__all__ = [
    "ColumnProfile",
    "HeaderProfile",
    "FooterProfile",
    "TableProfile",
    "TableProfileTrainer",
    "ProfileValidator",
    "ProfileRepository",
    "AMOUNT_HEADER_KEYWORDS",
    "AMOUNT_ORDER",
    "CODE_HEADER_KEYWORDS",
    "NAME_HEADER_KEYWORDS",
    "COLUMN_LABELS",
]
