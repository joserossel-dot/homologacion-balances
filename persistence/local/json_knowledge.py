"""Catálogo y diccionario locales respaldados por JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from datetime import datetime, timezone

from catalog_aliases import canonical_catalog_code, canonicalize_catalog
from persistence.contracts.knowledge import ValidationDecision
from persistence.neon_store import normalize_account_name
from persistence.local.locking import exclusive_file_lock


class JsonKnowledgeRepository:
    """Adaptador transicional para instalaciones sin PostgreSQL.

    Mantiene la forma de los JSON actuales, realiza sustitución atómica,
    serializa escritores y deja historial local de cada decisión humana.
    """

    def __init__(self, catalog_path: str | Path, dictionary_path: str | Path) -> None:
        self.catalog_path = Path(catalog_path)
        self.dictionary_path = Path(dictionary_path)
        self.lock_path = self.dictionary_path.with_suffix(
            self.dictionary_path.suffix + ".lock"
        )
        self.catalog_lock_path = self.catalog_path.with_suffix(
            self.catalog_path.suffix + ".lock"
        )
        self.history_path = self.dictionary_path.parent / "history" / "validations.jsonl"
        self.catalog_history_path = (
            self.catalog_path.parent / "history" / "catalog.jsonl"
        )

    def healthcheck(self) -> bool:
        try:
            self.load_catalog()
            self.load_dictionary()
            return True
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return False

    def load_catalog(self) -> dict[str, dict[str, Any]]:
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("El catálogo JSON debe ser un objeto por código.")
        return canonicalize_catalog(raw)

    def load_dictionary(self) -> list[dict[str, Any]]:
        raw = json.loads(self.dictionary_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("El diccionario JSON debe ser una lista.")
        return [dict(row) for row in raw]

    def save_catalog_entry(self, entry: Mapping[str, Any]) -> None:
        """Agrega una categoría al catálogo durable sin redefinir códigos.

        Una repetición byte-lógica del mismo registro es idempotente. Un código
        existente con otros atributos se rechaza para no sobrescribir una
        decisión humana ni una categoría maestra activa de forma silenciosa.
        """
        normalized = self._normalize_catalog_entry(entry)
        code = normalized["codigo_estandar"]
        with exclusive_file_lock(self.catalog_lock_path):
            catalog = self.load_catalog()
            previous = catalog.get(code)
            if previous is not None:
                comparable_previous = dict(previous)
                comparable_previous.setdefault("codigo_estandar", code)
                if comparable_previous != normalized:
                    raise ValueError(
                        f"La categoría {code} ya existe y no puede redefinirse."
                    )
                return
            catalog[code] = {
                key: value for key, value in normalized.items()
                if key != "codigo_estandar"
            }
            ordered = {key: catalog[key] for key in sorted(catalog)}
            self._atomic_json_write(self.catalog_path, ordered)
            self._append_catalog_history(normalized)

    def save_validation(self, decision: ValidationDecision) -> None:
        with exclusive_file_lock(self.lock_path):
            previous_code = None
            if decision.add_to_dictionary:
                dictionary = self.load_dictionary()
                previous_code = self._apply_decision(dictionary, decision)
                dictionary.sort(
                    key=lambda row: normalize_account_name(row["cuenta_original"])
                )
                self._atomic_json_write(self.dictionary_path, dictionary)
            self._append_history(decision, previous_code)

    def save_validations(self, decisions: list[ValidationDecision]) -> None:
        if not decisions:
            return
        with exclusive_file_lock(self.lock_path):
            dictionary = self.load_dictionary()
            history: list[tuple[ValidationDecision, str | None]] = []
            dictionary_changed = False
            for decision in decisions:
                if decision.add_to_dictionary:
                    previous = self._apply_decision(dictionary, decision)
                    dictionary_changed = True
                else:
                    previous = None
                history.append((decision, previous))
            if dictionary_changed:
                dictionary.sort(
                    key=lambda row: normalize_account_name(row["cuenta_original"])
                )
                self._atomic_json_write(self.dictionary_path, dictionary)
            for decision, previous_code in history:
                self._append_history(decision, previous_code)

    @staticmethod
    def _apply_decision(
        dictionary: list[dict[str, Any]], decision: ValidationDecision,
    ) -> str | None:
        normalized = normalize_account_name(decision.account_name)
        replacement = {
            "cuenta_original": decision.account_name,
            "codigo_estandar": canonical_catalog_code(decision.validated_code),
            "fuente": decision.source,
        }
        for index, row in enumerate(dictionary):
            if normalize_account_name(row.get("cuenta_original", "")) == normalized:
                previous_code = row.get("codigo_estandar")
                dictionary[index] = replacement
                return str(previous_code) if previous_code else None
        dictionary.append(replacement)
        return None

    def _append_history(
        self, decision: ValidationDecision, previous_code: str | None,
    ) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "account_name": decision.account_name,
            "previous_code": previous_code,
            "validated_code": canonical_catalog_code(decision.validated_code),
            "source": decision.source,
            "reviewer": decision.reviewer,
            "source_file": decision.source_file,
            "add_to_dictionary": decision.add_to_dictionary,
        }
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _append_catalog_history(self, entry: Mapping[str, Any]) -> None:
        self.catalog_history_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "action": "INSERT",
            "codigo_estandar": entry["codigo_estandar"],
            "entry": dict(entry),
        }
        with self.catalog_history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _normalize_catalog_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            "codigo_estandar", "nombre_estandar", "categoria",
            "tipo_estado", "naturaleza",
        )
        missing = [key for key in required if not str(entry.get(key, "")).strip()]
        if missing:
            raise ValueError(
                "Categoría incompleta; faltan: " + ", ".join(sorted(missing))
            )
        normalized = dict(entry)
        normalized["codigo_estandar"] = canonical_catalog_code(
            str(entry["codigo_estandar"]).strip()
        )
        for key in ("nombre_estandar", "categoria", "tipo_estado", "naturaleza"):
            normalized[key] = str(entry[key]).strip()
        normalized.setdefault("signo_normal", 1)
        normalized.setdefault("es_deuda_financiera", False)
        normalized.setdefault("es_activo_liquido", False)
        normalized.setdefault("afecta_ebitda", False)
        return normalized

    @staticmethod
    def _atomic_json_write(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
