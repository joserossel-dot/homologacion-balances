"""UniversalExtractor — delegación 1:1 al Parser Universal (Sprint 34).

Es el extractor por defecto y el fallback obligatorio de todo el sistema.
NO altera absolutamente nada de la extracción: simplemente envuelve
`ParserPDF.parsear()` en un `ExtractorResult` para que la arquitectura
tenga una interfaz uniforme.

Nunca lanza excepción: si el parser fallara, devuelve un ExtractorResult
de fallback (result=None) con `fallback_used=True`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from .base import ExtractorResult, FAMILIA_DESCONOCIDA, SpecializedExtractor


class UniversalExtractor(SpecializedExtractor):
    id = "universal"
    display_name = "Parser Universal"
    supported_families: list[str] = []

    def extract(self, path: Path, context: Any = None) -> ExtractorResult:
        # Import diferido: evita import circular con parser_universal.
        from parser_universal import ParserPDF

        t0 = time.perf_counter()
        try:
            resultado = ParserPDF().parsear(path)
        except Exception:  # noqa: BLE001 — fallback deliberado
            resultado = None
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return ExtractorResult(
            extractor_id=self.id,
            display_name=self.display_name,
            family_id=FAMILIA_DESCONOCIDA,
            confidence=0.0,
            elapsed_ms=elapsed_ms,
            fallback_used=True,
            result=resultado,
        )
