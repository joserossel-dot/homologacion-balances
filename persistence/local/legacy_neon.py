"""Compatibilidad entre el contrato nuevo y ``NeonKnowledgeStore``."""

from __future__ import annotations

from typing import Any, Mapping

from persistence.contracts.knowledge import ValidationDecision


class LegacyNeonKnowledgeAdapter:
    """Delega sin cambiar el comportamiento del repositorio existente."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def healthcheck(self) -> bool:
        return bool(self.store.healthcheck())

    def load_catalog(self) -> dict[str, dict[str, Any]]:
        return self.store.load_catalog()

    def load_dictionary(self) -> list[dict[str, Any]]:
        return self.store.load_dictionary()

    def save_catalog_entry(self, entry: Mapping[str, Any]) -> None:
        self.store.save_catalog_entry(dict(entry))

    def save_validation(self, decision: ValidationDecision) -> None:
        self.store.save_validation(**decision.as_legacy_dict())

    def save_validations(self, decisions: list[ValidationDecision]) -> None:
        self.store.save_validations([
            decision.as_legacy_dict() for decision in decisions
        ])
