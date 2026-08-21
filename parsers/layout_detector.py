"""Detecta la disposición de columnas de un balance por documento.

Reemplaza la heurística fija ULTIMAS_COLS = [ACTIVO, PASIVO, PERDIDA, GANANCIA]
por detección basada en los encabezados reales del documento.

Estrategia:
  1. Extraer encabezados de columnas desde las primeras líneas del documento
     que contengan palabras clave del lexicon
  2. Si se detectan ≥ 2 encabezados conocidos con orden consistente → usar ese layout
  3. Fallback: heurística actual (últimas 4 columnas = A/P/Pd/G)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# Léxico de encabezados de columna: clave = origen, valores = variantes
HEADER_LEXICON: dict[str, tuple[str, ...]] = {
    "activo": ("activo", "activos", "act", "activo corriente", "activo no corriente"),
    "pasivo": ("pasivo", "pasivos", "pas", "pasivo corriente", "pasivo no corriente"),
    "perdida": ("perdida", "pérdida", "perdidas", "pérdidas", "gasto", "gastos",
                "debe", "deudor", "deudores"),
    "ganancia": ("ganancia", "ganancias", "ingreso", "ingresos",
                 "haber", "acreedor", "acreedores"),
    "patrimonio": ("patrimonio", "capital", "pat"),
    "resultado": ("resultado", "resultados", "ejercicio", "utilidad", "utilidades"),
    "codigo": ("codigo", "código", "code", "cuenta", "cta"),
    "nombre": ("nombre", "name", "cuenta", "denominacion", "denominación"),
    "saldo": ("saldo", "saldo deudor", "saldo acreedor"),
}


@dataclass
class DetectedLayout:
    """Resultado de la detección de layout."""
    columns: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source: str = "fallback"
    header_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "confidence": self.confidence,
            "source": self.source,
            "header_text": self.header_text,
        }


class LayoutDetector:
    """Detecta la disposición de columnas de un balance."""

    DEFAULT_COLUMNS = ["activo", "pasivo", "perdida", "ganancia"]

    def detect(self, lineas: list[str], max_header_lines: int = 30) -> DetectedLayout:
        """Analiza las primeras líneas para detectar encabezados de columnas.

        Args:
            lineas: Líneas de texto extraídas del documento.
            max_header_lines: Máximo de líneas a analizar como encabezado.

        Returns:
            DetectedLayout con las columnas detectadas y confianza.
        """
        # Buscar líneas con encabezados de columna
        header_lines = lineas[:max_header_lines]
        candidates = self._find_header_candidates(header_lines)

        if not candidates:
            return DetectedLayout(
                columns=list(self.DEFAULT_COLUMNS),
                confidence=0.3,
                source="fallback",
            )

        # Filtrar solo los orígenes con orden natural
        ordered = self._resolve_order(candidates)
        if len(ordered) >= 2:
            # Penalizar si faltan columnas esperadas
            expected = set(self.DEFAULT_COLUMNS)
            found = set(ordered)
            missing = expected - found
            extra = found - expected
            conf = 0.5 + 0.1 * len(ordered)
            if missing:
                conf -= 0.05 * len(missing)
            if extra:
                conf -= 0.02 * len(extra)
            conf = max(0.2, min(1.0, conf))

            return DetectedLayout(
                columns=ordered,
                confidence=round(conf, 2),
                source="headers",
            )

        return DetectedLayout(
            columns=list(self.DEFAULT_COLUMNS),
            confidence=0.3,
            source="fallback",
        )

    def _find_header_candidates(self, header_lines: list[str]) -> list[tuple[int, str, str]]:
        """Retorna [(index, origen, matched_word), ...] de líneas de encabezado."""
        candidates: list[tuple[int, str, str]] = []
        seen_origins: set[str] = set()

        for i, line in enumerate(header_lines):
            line_lower = line.lower().strip()
            if not line_lower or len(line_lower) < 3:
                continue

            for origin, variants in HEADER_LEXICON.items():
                if origin in seen_origins:
                    continue
                for variant in variants:
                    # Buscar como token independiente (no substring)
                    pattern = r'\b' + re.escape(variant) + r'\b'
                    if re.search(pattern, line_lower):
                        candidates.append((i, origin, variant))
                        seen_origins.add(origin)
                        break

        return candidates

    def _resolve_order(self, candidates: list[tuple[int, str, str]]) -> list[str]:
        """Ordena los orígenes detectados por su posición de aparición."""
        # Agrupar por origen, tomar la primera aparición
        seen: dict[str, int] = {}
        for idx, origin, _ in candidates:
            if origin not in seen:
                seen[origin] = idx

        # Ordenar por índice de aparición
        ordered = sorted(seen.items(), key=lambda x: x[1])
        return [origin for origin, _ in ordered]
