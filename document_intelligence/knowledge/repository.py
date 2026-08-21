"""Repositorio de perfiles documentales (DKB).

Persistencia JSON con operaciones CRUD, merge, estadísticas y búsquedas:

  - save / load
  - add / update / remove
  - merge (otro repositorio o lista de perfiles)
  - statistics
  - find_by_company / find_by_family
  - find_similar (usa Matcher)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .document_profile import DocumentProfile
from .fingerprint import DocumentFingerprint
from .matcher import Matcher
from .statistics import compute_statistics


class DocumentKnowledgeBase:
    """Base de conocimiento documental persistente en JSON."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self.profiles: list[DocumentProfile] = []
        self._by_id: dict[str, DocumentProfile] = {}

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _reindex(self) -> None:
        self._by_id = {p.id: p for p in self.profiles}

    def get(self, profile_id: str) -> Optional[DocumentProfile]:
        return self._by_id.get(profile_id)

    def get_by_hash(self, signature_hash: str) -> Optional[DocumentProfile]:
        for p in self.profiles:
            if p.fingerprint.signature_hash == signature_hash:
                return p
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, profile: DocumentProfile) -> None:
        self.profiles.append(profile)
        self._by_id[profile.id] = profile

    def update(self, profile: DocumentProfile) -> bool:
        for i, p in enumerate(self.profiles):
            if p.id == profile.id:
                self.profiles[i] = profile
                self._by_id[profile.id] = profile
                return True
        return False

    def upsert(self, profile: DocumentProfile) -> bool:
        if self.get(profile.id) is not None:
            return self.update(profile)
        self.add(profile)
        return True

    def remove(self, profile_id: str) -> bool:
        before = len(self.profiles)
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        self._reindex()
        return len(self.profiles) < before

    def merge(self, other: "DocumentKnowledgeBase") -> int:
        """Fusiona perfiles por id. Devuelve cuántos quedaron nuevos."""
        merged = 0
        for profile in other.profiles:
            existing = self.get(profile.id)
            if existing is None:
                self.add(profile)
                merged += 1
            else:
                # Conserva el más reciente / con más apariciones.
                if profile.times_seen > existing.times_seen:
                    self.update(profile)
        return merged

    # ------------------------------------------------------------------
    # Búsquedas
    # ------------------------------------------------------------------

    def find_by_company(self, company: str) -> list[DocumentProfile]:
        query = company.strip().lower()
        if not query:
            return []
        results = []
        for p in self.profiles:
            if query == p.company.strip().lower():
                results.append(p)
            elif any(query == v.strip().lower() for v in p.known_variants):
                results.append(p)
        return results

    def find_by_family(self, family: str) -> list[DocumentProfile]:
        query = family.strip().upper()
        return [p for p in self.profiles if p.family.upper() == query]

    def find_similar(
        self,
        fingerprint: DocumentFingerprint,
        company: str = "",
        top_n: int = 5,
    ) -> list[tuple[DocumentProfile, float]]:
        """Devuelve los Top N perfiles más similares (score 0-100)."""
        matcher = Matcher()
        result = matcher.match(fingerprint, self.profiles, company=company, top_n=top_n)
        return result.ranking

    # ------------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------------

    def statistics(self) -> dict[str, Any]:
        return compute_statistics(self.profiles)

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "profiles": [p.to_dict() for p in self.profiles],
            "statistics": self.statistics(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentKnowledgeBase":
        kb = cls()
        for item in data.get("profiles", []):
            kb.add(DocumentProfile.from_dict(item))
        return kb

    def save(self, path: Optional[str | Path] = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("DocumentKnowledgeBase.save() requiere un path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.path = target
        return target

    def load(self, path: Optional[str | Path] = None) -> "DocumentKnowledgeBase":
        target = Path(path) if path else self.path
        if target is None or not target.exists():
            raise FileNotFoundError(f"Repositorio no encontrado: {target}")
        data = json.loads(target.read_text(encoding="utf-8"))
        restored = DocumentKnowledgeBase.from_dict(data)
        restored.path = target
        self.profiles = restored.profiles
        self.path = target
        self._reindex()
        return self
