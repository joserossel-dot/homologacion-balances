"""Parser de líneas de texto → RawAccount.

Envuelve las funciones de parseo del parser original y añade
RawAccount como modelo de datos del Core 2.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from parser_universal import (
    OrigenColumna,
    parsear_linea as _parsear_linea,
    parsear_monto as _parsear_monto,
    normalizar_codigo_ocr as _normalizar_codigo_ocr,
    normalizar_token_ocr as _normalizar_token_ocr,
    FormatoCodigo,
    CuentaRaw,
)


@dataclass
class RawAccount:
    """Modelo de cuenta del Core 2.0 (idéntico a CuentaRaw)."""
    line: int
    code: Optional[str]
    name: str
    amount: Optional[float]
    column_origin: str = "desconocido"
    is_total: bool = False
    extraction_confidence: float = 1.0


def parsear_linea(
    linea: str,
    numero_linea: int,
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float = 1.0,
) -> Optional[RawAccount]:
    """Envuelve parser_universal.parsear_linea() → RawAccount."""
    cr = _parsear_linea(linea, numero_linea, formato_codigo, separador_miles, confianza_base)
    if cr is None:
        return None
    return _cuenta_raw_to_account(cr)


def parsear_monto(valor: str, separador_miles: str) -> Optional[float]:
    """Envuelve parser_universal.parsear_monto()."""
    return _parsear_monto(valor, separador_miles)


def normalizar_codigo_ocr(linea: str) -> str:
    """Envuelve parser_universal.normalizar_codigo_ocr()."""
    return _normalizar_codigo_ocr(linea)


def normalizar_token_ocr(token: str) -> str:
    """Envuelve parser_universal.normalizar_token_ocr()."""
    return _normalizar_token_ocr(token)


def _cuenta_raw_to_account(cr: CuentaRaw) -> RawAccount:
    return RawAccount(
        line=cr.linea,
        code=cr.codigo,
        name=cr.nombre,
        amount=cr.monto,
        column_origin=cr.origen_columna.value,
        is_total=cr.es_total,
        extraction_confidence=cr.confianza_extraccion,
    )


def raw_account_to_cuenta_raw(ra: RawAccount) -> CuentaRaw:
    """Conversión inversa para compatibilidad."""
    return CuentaRaw(
        linea=ra.line,
        codigo=ra.code,
        nombre=ra.name,
        monto=ra.amount,
        origen_columna=OrigenColumna(ra.column_origin),
        es_total=ra.is_total,
        confianza_extraccion=ra.extraction_confidence,
    )


def parsear_todas(
    lineas: list[str],
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float = 1.0,
) -> list[RawAccount]:
    """Parsea todas las líneas de una lista."""
    result: list[RawAccount] = []
    for i, l in enumerate(lineas):
        ra = parsear_linea(l, i, formato_codigo, separador_miles, confianza_base)
        if ra:
            result.append(ra)
    return result
