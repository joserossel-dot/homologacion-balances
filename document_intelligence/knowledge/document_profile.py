"""DocumentProfile — perfil de un formato conocido en la DKB.

Agrupa un fingerprint representativo (centroide de un cluster) con la
información histórica de su uso:

  - variantes conocidas
  - extractor recomendado
  - primera/última aparición
  - frecuencia de aparición
  - metadata libre (empresas, archivos, descripción)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .fingerprint import DocumentFingerprint


@dataclass
class DocumentProfile:
    """Perfil persistente de un formato documental."""

    id: str
    name: str
    company: str
    family: str
    description: str
    fingerprint: DocumentFingerprint
    known_variants: list[str] = field(default_factory=list)
    recommended_extractor: str = "STANDARD_PARSER"
    first_seen: str = ""
    last_seen: str = ""
    times_seen: int = 0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "company": self.company,
            "family": self.family,
            "description": self.description,
            "fingerprint": self.fingerprint.to_dict(),
            "known_variants": list(self.known_variants),
            "recommended_extractor": self.recommended_extractor,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "times_seen": self.times_seen,
            "confidence": round(self.confidence, 4),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentProfile":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            company=data.get("company", ""),
            family=data.get("family", "DESCONOCIDO"),
            description=data.get("description", ""),
            fingerprint=DocumentFingerprint.from_dict(data.get("fingerprint", {})),
            known_variants=list(data.get("known_variants", [])),
            recommended_extractor=data.get(
                "recommended_extractor", "STANDARD_PARSER"
            ),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
            times_seen=data.get("times_seen", 0),
            confidence=data.get("confidence", 0.0),
            metadata=dict(data.get("metadata", {})),
        )

    # ------------------------------------------------------------------

    @classmethod
    def new(
        cls,
        name: str,
        company: str,
        family: str,
        fingerprint: DocumentFingerprint,
        recommended_extractor: str = "STANDARD_PARSER",
        description: str = "",
        **metadata: Any,
    ) -> "DocumentProfile":
        """Crea un perfil nuevo con id y fechas automáticos."""
        today = date.today().isoformat()
        return cls(
            id=f"dkb_{uuid.uuid4().hex[:12]}",
            name=name,
            company=company,
            family=family,
            description=description,
            fingerprint=fingerprint,
            recommended_extractor=recommended_extractor,
            first_seen=today,
            last_seen=today,
            times_seen=1,
            confidence=1.0,
            metadata=metadata,
        )

    def register_seen(self, when: str = "") -> None:
        """Registra una nueva aparición del formato."""
        self.times_seen += 1
        if not when:
            when = date.today().isoformat()
        if not self.first_seen or when < self.first_seen:
            self.first_seen = when
        if not self.last_seen or when > self.last_seen:
            self.last_seen = when
