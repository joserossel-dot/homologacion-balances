"""Contrato de catálogo, diccionario y aprendizaje local."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ValidationDecision:
    account_name: str
    validated_code: str
    source: str
    suggested_code: str | None = None
    suggested_method: str | None = None
    suggested_confidence: float | None = None
    reviewer: str = "analista"
    source_file: str = ""
    add_to_dictionary: bool = True

    def as_legacy_dict(self) -> dict[str, Any]:
        """Forma aceptada actualmente por ``NeonKnowledgeStore``."""
        return asdict(self)


@runtime_checkable
class LocalKnowledgeRepository(Protocol):
    """Puerto local consumido por clasificación y revisión humana."""

    def healthcheck(self) -> bool: ...

    def load_catalog(self) -> dict[str, dict[str, Any]]: ...

    def load_dictionary(self) -> list[dict[str, Any]]: ...

    def save_catalog_entry(self, entry: Mapping[str, Any]) -> None: ...

    def save_validation(self, decision: ValidationDecision) -> None: ...

    def save_validations(self, decisions: list[ValidationDecision]) -> None: ...
