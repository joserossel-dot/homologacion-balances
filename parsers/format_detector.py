"""Detección de formato de código de cuenta y separador de miles.

Envuelve las funciones del parser original y añade soporte para
configuración (sample size).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from parser_universal import (
    FormatoCodigo as _CodeFormat,
    PATRON_GUION, PATRON_PUNTO, PATRON_COMPACTO,
    detectar_formato_codigo as _detectar_formato,
    detectar_separador_miles as _detectar_separador,
    PATRON_MONTOS,
)

# Re-exportar el enum
CodeFormat = _CodeFormat


def detectar_formato_codigo(
    codigos_muestra: list[str],
    sample_size: int | None = None,
) -> CodeFormat:
    """Detecta el formato dominante de código de cuenta.

    Si sample_size está definido, trunca la muestra.
    """
    muestra = codigos_muestra[:sample_size] if sample_size else codigos_muestra
    return _detectar_formato(muestra)


def detectar_separador_miles(
    montos_muestra: list[str],
    sample_size: int | None = None,
) -> str:
    """Detecta el separador de miles dominante ('.' o ',').

    Si sample_size está definido, trunca la muestra.
    """
    muestra = montos_muestra[:sample_size] if sample_size else montos_muestra
    return _detectar_separador(muestra)


def extraer_muestra_montos(lineas: list[str], max_lines: int = 80) -> list[str]:
    """Extrae tokens numéricos candidatos de las primeras N líneas."""
    muestra: list[str] = []
    for l in lineas[:max_lines]:
        muestra.extend(PATRON_MONTOS.findall(l))
    return muestra
