"""Aliases historicos del catalogo maestro.

Los codigos canonicos son los unicos que deben producir nuevas decisiones.
Los aliases se conservan para leer datos historicos sin romper trazabilidad.
"""

from __future__ import annotations

from typing import Any, Iterable


CATALOG_CODE_ALIASES = {
    "PAT.09": "PAT.03",
}

CANONICAL_CATALOG_NAMES = {
    "PAT.03": "Resultados Acumulados",
}


def canonical_catalog_code(code: Any) -> str:
    """Devuelve el codigo vigente equivalente a un codigo historico."""
    normalized = str(code or "").strip().upper()
    return CATALOG_CODE_ALIASES.get(normalized, normalized)


def canonicalize_dictionary(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza codigos sin mutar las filas recibidas."""
    return [
        {
            **entry,
            "codigo_estandar": canonical_catalog_code(entry.get("codigo_estandar")),
        }
        for entry in entries
    ]


def canonicalize_catalog(catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Impone nombres vigentes y oculta aliases aunque Neon conserve filas antiguas."""
    result = {code: dict(entry) for code, entry in catalog.items()}
    for code, name in CANONICAL_CATALOG_NAMES.items():
        if code in result:
            result[code]["nombre_estandar"] = name
    for alias, canonical in CATALOG_CODE_ALIASES.items():
        if alias in result:
            result[alias]["clasificable"] = False
            result[alias]["codigo_canonico"] = canonical
    return result
