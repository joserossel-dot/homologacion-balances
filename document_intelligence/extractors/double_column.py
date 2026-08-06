"""DoubleColumnExtractor — separación de balances de doble columna (Sprint F).

Detecta y separa la disposición de doble columna (ACTIVO | PASIVO) en
balances de una página contigua, donde cada fila del PDF contiene DOS
cuentas independientes (una por lado). Está pensado para "Balance
Clasificado" cuyas dos columnas comparten coordenada `top`, de modo que
`page.extract_text()` las fusiona en una sola línea incoherente.

Detección cien por ciento estructural (NUNCA por nombre de archivo):

  1. `_sugiere_doble_columna` — pre-filtro barato sobre el texto plano ya
     extraído (regex), para no abrir pdfplumber de más en documentos que no
     tienen esta disposición.
  2. `_boundary_2_clusters` — calcula el `x0` de corte con clustering de 2
     grupos (minimización de varianza intra-cluster).
  3. `_lado_es_cuenta` — un lado es una cuenta real si empieza con un token
     tipo código de cuenta + un nombre alfabético + un monto.
  4. Una página es doble columna si al menos `MIN_FILAS_DOBLES` filas tienen
     cuenta a AMBOS lados del boundary.

Regla de oro (aprobada por arquitectura): este módulo NO reimplementa
`parsear_linea`, `detectar_formato_codigo` ni la resolución de montos.
Únicamente produce DOS líneas independientes por cada fila doble; el resto
del pipeline (Parser Universal) parsea esas líneas con la lógica existente.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from .base import ExtractorResult, FAMILIA_DESCONOCIDA, SpecializedExtractor
from .universal import UniversalExtractor

logger = logging.getLogger("document_intelligence.extractors.double_column")

# Umbral: cuántas filas con cuenta en ambos lados se requieren para declarar
# doble columna. Filtra falsos positivos de tablas normales con una sola
# columna de códigos (discriminador validado: 1/474 en el dataset).
MIN_FILAS_DOBLES = 2

# Pre-filtro: ¿la página parece tener 2+ líneas con 2+ tokens compactos
# (5-6 dígitos)? Es solo una puerta barata; la decisión final es estructural.
_PREFILTRO_COMPACTO = re.compile(r'(?<!\d)\d{5,6}(?!\d)')

# Lado real de una cuenta: primer token tipo código.
_CODIGO_LADO = re.compile(r'^\d{5,6}$|^\d(\.\d+){2,}$|^\d(-\d+)+$')
# Token de monto: "1.234.567", "12345" (≥5 dígitos).
_MONTO_LADO = re.compile(r'\d{1,3}(?:[.,]\d{3})+|\d{5,}')


def _prefiltro_sugiere(texto: str) -> bool:
    """Puerta barata: ¿el texto tiene 2+ líneas con 2+ códigos de 5-6 dígitos?"""
    if not texto:
        return False
    n = 0
    for linea in texto.split('\n'):
        if len(_PREFILTRO_COMPACTO.findall(linea)) >= 2:
            n += 1
            if n >= 2:
                return True
    return False


def _boundary_2_clusters(words: list[dict]) -> Optional[float]:
    """x0 umbral que separa las columnas izquierda/derecha (2 clusters)."""
    xs = sorted(w['x0'] for w in words)
    n = len(xs)
    if n < 12:
        return None
    best = None
    for i in range(1, n):
        left = xs[:i]
        right = xs[i:]
        cl = sum((x - sum(left) / len(left)) ** 2 for x in left)
        cr = sum((x - sum(right) / len(right)) ** 2 for x in right)
        total = cl + cr
        if best is None or total < best[0]:
            best = (total, xs[i - 1], xs[i])
    return (best[1] + best[2]) / 2


def _lado_es_cuenta(tokens: list[str]) -> bool:
    toks = [t for t in tokens if t.strip()]
    if len(toks) < 3:
        return False
    if not _CODIGO_LADO.match(toks[0]):
        return False
    hay_nombre = any(re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', t) for t in toks)
    hay_monto = any(_MONTO_LADO.search(t) for t in toks)
    return hay_nombre and hay_monto


def separar_page(page: Any) -> Optional[list[str]]:
    """Separa una página de doble columna → lista de líneas independientes.

    Devuelve None si la página NO es doble columna (para delegar al parser
    universal normal). Nunca lanza: cualquier fallo → None.
    """
    try:
        words = page.extract_words()
        if not words:
            return None
        boundary = _boundary_2_clusters(words)
        if boundary is None:
            return None
        rows: dict[int, list[dict]] = {}
        for w in words:
            rows.setdefault(round(w['top'], 1), []).append(w)

        salida: list[str] = []
        filas_dobles = 0
        for top in sorted(rows):
            ws = sorted(rows[top], key=lambda w: w['x0'])
            left = [w['text'] for w in ws if w['x0'] < boundary]
            right = [w['text'] for w in ws if w['x0'] >= boundary]
            if _lado_es_cuenta(left) and _lado_es_cuenta(right):
                filas_dobles += 1
                salida.append(' '.join(left))
                salida.append(' '.join(right))
            else:
                salida.append(' '.join(w['text'] for w in ws))
        if filas_dobles < MIN_FILAS_DOBLES:
            return None
        logger.debug(
            "Doble columna detectada (%d filas dobles, boundary=%.1f)",
            filas_dobles, boundary,
        )
        return salida
    except Exception as exc:  # noqa: BLE001 — nunca romper el parser
        logger.debug("Análisis de doble columna falló (%s); universal.", exc)
        return None


def separar_desde_pdf(path: Path) -> Optional[list[str]]:
    """Separa TODO el PDF de doble columna si lo es, o None."""
    import pdfplumber
    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return None
            # Pre-filtro: si el texto plano no sugiere doble columna, salimos.
            texto0 = pdf.pages[0].extract_text() or ""
            if not _prefiltro_sugiere(texto0):
                return None
            salida: list[str] = []
            for page in pdf.pages:
                page_lines = separar_page(page)
                if page_lines is None:
                    page_lines = (page.extract_text() or "").split('\n')
                salida.extend(l for l in page_lines if l.strip())
            return salida
    except Exception as exc:  # noqa: BLE001
        logger.debug("Doble columna PDF falló (%s); universal.", exc)
        return None


class DoubleColumnExtractor(SpecializedExtractor):
    """Extrae balances/EEFF de doble columna usando el splitter estructural.

    La detección es estructural (x0/coordenadas) y NUNCA por nombre. Cuando
    detecta doble columna genera dos líneas por fila y delega el parseo al
    Parser Universal (reutilizando `parsear_linea`); ante cualquier
    incertidumbre delega tal cual al universal (fallback obligatorio).
    """

    id = "double_column"
    display_name = "Balance Doble Columna"
    supported_families: list[str] = []

    def extract(self, path: Path, context: Any = None) -> ExtractorResult:
        from parser_universal import ExtractionContext, ParserPDF

        t0 = time.perf_counter()
        lineas = separar_desde_pdf(path)
        if lineas is None:
            # No es doble columna → fallback obligatorio (universal exacto).
            res = UniversalExtractor().extract(path, context)
            return ExtractorResult(
                extractor_id=self.id,
                display_name=self.display_name,
                family_id=FAMILIA_DESCONOCIDA,
                confidence=0.0,
                elapsed_ms=res.elapsed_ms,
                fallback_used=True,
                result=res.result,
            )

        try:
            # Inyecta las líneas ya separadas como hint estructural: el
            # ParserPDF usará estas líneas (reutilizando parsear_linea,
            # detectar_formato_codigo y la resolución de montos existente).
            contexto = ExtractionContext(lineas_presplit=lineas)
            resultado = ParserPDF().parsear(path, contexto)
        except Exception as exc:  # noqa: BLE001 — fallback obligatorio
            logger.debug("Parseo con doble columna falló (%s); universal.", exc)
            return self.delegate_to_universal(path, context)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExtractorResult(
            extractor_id=self.id,
            display_name=self.display_name,
            family_id=FAMILIA_DESCONOCIDA,
            confidence=0.95,
            elapsed_ms=elapsed_ms,
            fallback_used=False,
            result=resultado,
        )