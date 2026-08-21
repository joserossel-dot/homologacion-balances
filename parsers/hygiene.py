"""Filtro de líneas basura — envuelve GARBAGE_PATTERNS del parser original.

Re-exporta los patrones y la función, sin modificar el original.
"""

from __future__ import annotations

import re

# Re-exportar patrones del parser original
from parser_universal import GARBAGE_PATTERNS as _ORIGINAL_PATTERNS

# Mantener compatibilidad
GARBAGE_PATTERNS: list[re.Pattern] = _ORIGINAL_PATTERNS


def es_linea_basura(linea: str) -> bool:
    """Retorna True si la línea completa coincide con algún patrón de basura."""
    for patron in GARBAGE_PATTERNS:
        if patron.match(linea):
            return True
    return False
