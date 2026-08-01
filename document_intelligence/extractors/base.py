"""Contrato de los extractores especializados (Sprint 34).

Define la interfaz uniforme del framework:

  - `ExtractorResult`: resultado estandarizado que CUALQUIER extractor
    devuelve (extractor usado, familia detectada, confianza, tiempo,
    flag de fallback y el ResultadoParseo real).
  - `SpecializedExtractor`: ABC que todo extractor debe implementar.
    Los atributos de clase `id`, `display_name` y `supported_families`
    son la configuración estática; `extract()` es el único método
    obligatorio.

Este sprint todos los extractores delegan al Parser Universal
(`delegate_to_universal`): la arquitectura está lista, la lógica
específica llega en el Sprint siguiente.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Familia "vacía" usada cuando no hay detección.
FAMILIA_DESCONOCIDA = "DESCONOCIDO"


@dataclass
class ExtractorResult:
    """Resultado uniforme de un extractor (especializado o universal)."""

    extractor_id: str
    display_name: str
    result: Any = None
    family_id: str = FAMILIA_DESCONOCIDA
    confidence: float = 0.0
    elapsed_ms: int = 0
    fallback_used: bool = True

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Versión plana para logs, UI y `resultado.extractor_info`."""
        return {
            "extractor_id": self.extractor_id,
            "display_name": self.display_name,
            "family_id": self.family_id,
            "confidence": round(self.confidence, 4),
            "elapsed_ms": self.elapsed_ms,
            "fallback_used": self.fallback_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExtractorResult":
        return cls(
            extractor_id=data.get("extractor_id", "universal"),
            display_name=data.get("display_name", "Parser Universal"),
            family_id=data.get("family_id", FAMILIA_DESCONOCIDA),
            confidence=data.get("confidence", 0.0),
            elapsed_ms=data.get("elapsed_ms", 0),
            fallback_used=data.get("fallback_used", True),
        )


class SpecializedExtractor(ABC):
    """ABC de los extractores especializados.

    Configuración estática (atributos de clase):
      - id: identificador único (se registra en el diccionario interno)
      - display_name: nombre legible para UI/logs
      - supported_families: ids de familia del mining (cluster_...)
        que este extractor puede procesar mejor que el universal

    El método `extract()` es obligatorio.
    """

    id: str = "specialized"
    display_name: str = "Extractor Especializado"
    supported_families: list[str] = []

    # ------------------------------------------------------------------
    # API obligatoria
    # ------------------------------------------------------------------

    @abstractmethod
    def extract(self, path: Path, context: Any = None) -> ExtractorResult:
        """Extrae cuentas del documento y devuelve un ExtractorResult."""

    # ------------------------------------------------------------------
    # Helpers compartidos
    # ------------------------------------------------------------------

    def delegate_to_universal(
        self,
        path: Path,
        context: Any = None,
        family_id: str = "",
        confidence: float = 0.0,
    ) -> ExtractorResult:
        """Delega la extracción al Parser Universal (Sprint 34).

        Devuelve un ExtractorResult con el id de ESTE extractor (así se
        sabe cuál fue seleccionado) pero con `fallback_used=True`: la
        extracción la hizo el universal. Se usa hasta que cada extractor
        implemente su lógica específica.
        """
        from .universal import UniversalExtractor

        universal = UniversalExtractor().extract(path, context)
        return ExtractorResult(
            extractor_id=self.id,
            display_name=self.display_name,
            family_id=family_id or (self.supported_families[0] if self.supported_families else FAMILIA_DESCONOCIDA),
            confidence=confidence,
            elapsed_ms=universal.elapsed_ms,
            fallback_used=True,
            result=universal.result,
        )

    def fallback(self, path: Path) -> ExtractorResult:
        """ExtractorResult de fallback sin tocar el parser."""
        return ExtractorResult(
            extractor_id="universal",
            display_name="Parser Universal",
            family_id=FAMILIA_DESCONOCIDA,
            confidence=0.0,
            elapsed_ms=0,
            fallback_used=True,
            result=None,
        )
