"""SpecializedExtractorFactory — selección del extractor (Sprint 34).

Proceso de decisión:

  1. Construir el fingerprint del documento reutilizando la signature del
     `DocumentProcessingContext` + el preview (texto nativo). Es EXACTAMENTE
     el mismo fingerprint que usa el mining (DocumentFingerprint.build con
     FormatAnalyzer + extract_preview_lines), así la similitud es coherente.
  2. Comparar contra los centroides de las familias del mining
     (knowledge_base/document_mining.json) con `fingerprint_similarity`
     (la misma función del clustering).
  3. Si la mejor familia tiene similitud >= umbral Y existe un extractor
     registrado para esa familia → devolver ese extractor.
  4. En cualquier otro caso → UniversalExtractor.

GARANTÍAS:
  - NUNCA lanza excepción (cualquier fallo termina en UniversalExtractor).
  - UniversalExtractor es el fallback obligatorio y el extractor por defecto.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from ..knowledge.fingerprint import DocumentFingerprint, extract_preview_lines
from .base import FAMILIA_DESCONOCIDA, SpecializedExtractor
from .registry import get_extractor_for_family
from .universal import UniversalExtractor

logger = logging.getLogger("document_intelligence.extractors.factory")

# Alineado con el umbral de clustering del mining (70).
DEFAULT_THRESHOLD = 70.0
DEFAULT_MINING_PATH = "knowledge_base/document_mining.json"


class SpecializedExtractorFactory:
    """Selecciona el extractor correcto para un documento.

    El estado (familias del mining) se comparte entre instancias con el
    mismo `mining_path` (cache a nivel de clase): se parsea el JSON una
    sola vez por proceso.
    """

    _shared_cache: dict[str, list[Any]] = {}

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        mining_path: str = DEFAULT_MINING_PATH,
        families: Optional[list[Any]] = None,
    ):
        self.threshold = float(threshold)
        self.mining_path = str(mining_path)
        # `families` permite inyectar familias en tests (DocumentFamily o
        # cualquier objeto con .id y .centroid).
        self._familias: list[Any] = list(families) if families is not None else []

    # ------------------------------------------------------------------
    # Carga de familias del mining (con cache compartida)
    # ------------------------------------------------------------------

    def _cargar_familias(self) -> list[Any]:
        if self._familias:
            return self._familias
        cache_key = self.mining_path
        if cache_key not in self._shared_cache:
            self._shared_cache[cache_key] = self._load_familias()
        return self._shared_cache[cache_key]

    def _load_familias(self) -> list[Any]:
        try:
            from ..mining import DocumentFamily, load_analysis_result
            data = load_analysis_result(self.mining_path) or {}
            return [
                DocumentFamily.from_dict(f)
                for f in data.get("families", [])
            ]
        except Exception as exc:  # noqa: BLE001 — fallback obligatorio
            logger.debug("No se pudieron cargar las familias del mining: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Decisión
    # ------------------------------------------------------------------

    def _decidir(
        self,
        path: Path,
        context: Any = None,
    ) -> tuple[SpecializedExtractor, str, float, str, bool]:
        """Devuelve (extractor, family_id, confidence, reason, fallback)."""
        family_id = FAMILIA_DESCONOCIDA
        confidence = 0.0
        reason = "sin análisis documental"
        fallback = True

        if context is None:
            return UniversalExtractor(), family_id, confidence, reason, fallback

        signature = getattr(context, "signature", None)
        if signature is None:
            reason = "contexto sin signature"
            return UniversalExtractor(), family_id, confidence, reason, fallback

        try:
            lineas = extract_preview_lines(path)
            query = DocumentFingerprint.build(signature, lineas)

            mejor_id = FAMILIA_DESCONOCIDA
            mejor_sim = 0.0
            for familia in self._cargar_familias():
                centroid = getattr(familia, "centroid", None)
                if centroid is None:
                    continue
                sim = self._similitud(query, centroid)
                if sim > mejor_sim:
                    mejor_sim = sim
                    mejor_id = familia.id

            confidence = round(mejor_sim / 100.0, 4)
            family_id = mejor_id

            if mejor_sim < self.threshold:
                reason = (
                    f"similitud {mejor_sim:.1f}% < umbral {self.threshold}%"
                )
                return UniversalExtractor(), family_id, confidence, reason, fallback

            clase = get_extractor_for_family(mejor_id)
            if clase is None:
                reason = "familia sin extractor especializado registrado"
                return UniversalExtractor(), family_id, confidence, reason, fallback

            return clase(), family_id, confidence, (
                f"match familia {mejor_id} (similitud {mejor_sim:.1f}%)"
            ), False

        except Exception as exc:  # noqa: BLE001 — fallback obligatorio
            logger.debug("Factory falló; usando UniversalExtractor: %s", exc, exc_info=True)
            return UniversalExtractor(), family_id, confidence, (
                f"fallback por error en la factory: {exc}"
            ), True

    @staticmethod
    def _similitud(query: DocumentFingerprint, centroid: DocumentFingerprint) -> float:
        """Similitud 0-100 fingerprint a fingerprint (igual que el mining)."""
        from ..mining import fingerprint_similarity
        return fingerprint_similarity(query, centroid)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def build(
        self,
        path: Path | str,
        context: Any = None,
    ) -> SpecializedExtractor:
        """Devuelve el extractor concreto a usar (siempre uno)."""
        try:
            extractor, *_ = self._decidir(path, context)
            return extractor
        except Exception:  # noqa: BLE001 — fallback absoluto
            return UniversalExtractor()

    def detect(
        self,
        path: Path | str,
        context: Any = None,
    ) -> dict[str, Any]:
        """Información de decisión SIN ejecutar la extracción.

        Estructura (usada en `resultado.extractor_info`):
          extractor_id, display_name, family_id, confidence,
          fallback_used, reason, elapsed_ms
        """
        t0 = time.perf_counter()
        try:
            extractor, family_id, confidence, reason, fallback = self._decidir(
                path, context,
            )
        except Exception as exc:  # noqa: BLE001 — fallback absoluto
            extractor = UniversalExtractor()
            family_id = FAMILIA_DESCONOCIDA
            confidence = 0.0
            reason = f"fallback por error en la factory: {exc}"
            fallback = True
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "extractor_id": extractor.id,
            "display_name": extractor.display_name,
            "family_id": family_id,
            "confidence": confidence,
            "fallback_used": fallback,
            "reason": reason,
            "elapsed_ms": elapsed_ms,
        }
