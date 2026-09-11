"""DoubleColumnExtractor — separación de balances de doble columna (Frente 1).

Detecta y separa la disposición de doble columna (ACTIVO | PASIVO) en
balances de una página contigua, donde cada fila del PDF contiene DOS
cuentas independientes (una por lado).

Detección cien por ciento estructural (NUNCA por nombre de archivo):
1. Reconocimiento estructural multi-evidencia de códigos contables vs importes.
2. Estimación robusta del corte (mediana de centros de gaps, dispersión acotada y canal libre vertical).
3. Exclusión previa de títulos multilínea, encabezados de tabla y totales antes de estimar el corte.
4. Soporte para bloques asimétricos, glosas largas unilaterales y filas desplazadas (staggered).
5. Rechazo estricto y fallback seguro ante balances tabulares (8 columnas, comparativos) o documentos verticales.
"""

from __future__ import annotations

import logging
import re
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import ExtractorResult, FAMILIA_DESCONOCIDA, SpecializedExtractor
from .universal import UniversalExtractor

logger = logging.getLogger("document_intelligence.extractors.double_column")

# Parámetros de tolerancia y umbrales
MIN_FILAS_DOBLES = 2
MAX_DISPERSION_TOLERANCE = 40.0  # Dispersión máxima permitida entre centros de gaps (~14mm)
MIN_GAP_WIDTH = 8.0              # Ancho mínimo del canal inter-columnas (~2.8mm)

# Patrones estructurales
PAT_MONTO_MILES = re.compile(r'^\(?-?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?$|^\(?\d{2,}(?:,\d+)?\)?$')
PAT_CODIGO_DOTS = re.compile(r'^\d{1,2}(?:\.\d{1,4}){1,6}$')
PAT_CODIGO_RAW = re.compile(r'^\d{5,8}$')
PAT_CODIGO_HYPHEN = re.compile(r'^\d{1,2}(?:-\d+)+$')
PAT_LETRAS = re.compile(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]')

# Pre-filtro: ¿la página parece tener 2+ líneas con 2+ tokens tipo código?
_PREFILTRO_CODIGO = re.compile(
    r'(?<!\d)\d{5,8}(?!\d)|(?<!\S)\d{1,2}(?:\.\d{1,4}){1,6}(?!\S)|(?<!\S)\d{1,2}(?:-\d+)+(?!\S)'
)

# Lado real de una cuenta (retrocompatibilidad)
_CODIGO_LADO = re.compile(r'^\d{5,8}$|^\d(\.\d+){2,}$|^\d(-\d+)+$')
_MONTO_LADO = re.compile(r'\d{1,3}(?:[.,]\d{3})+|\d{5,}')

PALABRAS_ENCABEZADO = {
    'codigo', 'cuenta', 'debito', 'credito', 'deudor', 'acreedor',
    'activo', 'pasivo', 'patrimonio', 'fecha', 'notas', 'nota',
    '2024', '2023', 'clp', 'miles', 'debe', 'haber',
}


def _token_es_monto(token: str) -> bool:
    clean = token.strip().replace('$', '').replace('CLP', '').strip()
    return bool(PAT_MONTO_MILES.match(clean)) and any(c.isdigit() for c in clean)


def _token_es_codigo_candidato(token: str) -> bool:
    """Verifica si la sintaxis del token corresponde a un formato de código contable."""
    clean = token.strip().rstrip(':')
    if PAT_CODIGO_RAW.match(clean):
        return True
    # Dotted code pero no formato de miles estándar chileno (ej. 1.200.000)
    if PAT_CODIGO_DOTS.match(clean) and not (
        '.' in clean and len(clean.split('.')[-1]) == 3 and len(clean.split('.')[0]) <= 3 and len(clean.split('.')) >= 3
    ):
        return True
    if PAT_CODIGO_HYPHEN.match(clean):
        return True
    return False


def _prefiltro_sugiere(texto: str) -> bool:
    """Puerta barata: ¿el texto tiene 2+ líneas con 2+ candidatos a código?"""
    if not texto:
        return False
    n = 0
    for linea in texto.split('\n'):
        if len(_PREFILTRO_CODIGO.findall(linea)) >= 2:
            n += 1
            if n >= 2:
                return True
    return False


def _boundary_2_clusters(words: list[dict]) -> Optional[float]:
    """x0 umbral que separa las columnas izquierda/derecha (2 clusters, retrocompatibilidad)."""
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
    return (best[1] + best[2]) / 2 if best else None


def _lado_es_cuenta(tokens: list[str]) -> bool:
    """Valida si un bloque de tokens corresponde a una cuenta (retrocompatibilidad)."""
    toks = [t for t in tokens if t.strip()]
    if len(toks) < 3:
        return False
    if not _CODIGO_LADO.match(toks[0]):
        return False
    hay_nombre = any(re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', t) for t in toks)
    hay_monto = any(_MONTO_LADO.search(t) for t in toks)
    return hay_nombre and hay_monto


def _detectar_gap_fila_pareada(ws: List[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """
    Detecta el canal inter-columnas en una fila que presenta dos bloques contables completos:
    [Código 1] [Descripción con letras] [Monto 1] ... [Código 2] [Descripción con letras] [Monto 2]
    """
    textos_lower = [w['text'].lower() for w in ws]
    if sum(1 for t in textos_lower if t in PALABRAS_ENCABEZADO) >= 3:
        return None

    cand_cods = [
        i for i, w in enumerate(ws)
        if _token_es_codigo_candidato(w['text']) and i + 1 < len(ws) and PAT_LETRAS.search(ws[i + 1]['text'])
    ]
    if len(cand_cods) < 2:
        return None

    i1, i2 = cand_cods[0], cand_cods[1]
    t_izq, t_der = ws[i1:i2], ws[i2:]

    # Validar integridad contable de ambos lados
    hay_monto_izq = any(_token_es_monto(w['text']) for w in t_izq)
    hay_texto_izq = any(PAT_LETRAS.search(w['text']) for w in t_izq)
    hay_monto_der = any(_token_es_monto(w['text']) for w in t_der)
    hay_texto_der = any(PAT_LETRAS.search(w['text']) for w in t_der)

    if not (hay_monto_izq and hay_texto_izq and hay_monto_der and hay_texto_der):
        return None

    fin_izq = max(w['x1'] for w in t_izq)
    ini_der = ws[i2]['x0']

    if ini_der > fin_izq + MIN_GAP_WIDTH:
        return (fin_izq, ini_der)
    return None


def _calcular_boundary_robusto(page: Any) -> Optional[float]:
    """
    Calcula el eje de corte (boundary) mediante estimador robusto (mediana) y
    validación de dispersión sobre filas contables independientes.
    """
    words = page.extract_words()
    if not words or len(words) < 8:
        return None

    # Agrupar por línea física
    rows: Dict[int, List[Dict[str, Any]]] = {}
    for w in words:
        top_bucket = round(w['top'] / 3.0) * 3
        rows.setdefault(top_bucket, []).append(w)

    # Método 1: Filas pareadas directas
    gaps: List[Tuple[float, float]] = []
    for top in sorted(rows):
        ws = sorted(rows[top], key=lambda x: x['x0'])
        gap = _detectar_gap_fila_pareada(ws)
        if gap:
            gaps.append(gap)

    if len(gaps) >= MIN_FILAS_DOBLES:
        centers = [(g[0] + g[1]) / 2.0 for g in gaps]
        dispersion = max(centers) - min(centers)
        max_left = max(g[0] for g in gaps)
        min_right = min(g[1] for g in gaps)
        if dispersion <= MAX_DISPERSION_TOLERANCE and min_right > max_left:
            return statistics.median(centers)

    # Método 2: Filas contables individuales (para estructuras desfasadas / staggered)
    cuentas_indiv: List[Tuple[float, float]] = []
    for top in sorted(rows):
        ws = sorted(rows[top], key=lambda x: x['x0'])
        textos_lower = [w['text'].lower() for w in ws]
        if sum(1 for t in textos_lower if t in PALABRAS_ENCABEZADO) >= 3:
            continue
        cand_cods = [
            i for i, w in enumerate(ws)
            if _token_es_codigo_candidato(w['text']) and i + 1 < len(ws) and PAT_LETRAS.search(ws[i + 1]['text'])
        ]
        if len(cand_cods) == 1:
            i_c = cand_cods[0]
            toks = ws[i_c:]
            if any(_token_es_monto(w['text']) for w in toks) and any(PAT_LETRAS.search(w['text']) for w in toks):
                # Rechazar filas con 4 o más montos (como balances de 8 columnas)
                if sum(1 for w in ws if _token_es_monto(w['text'])) <= 2:
                    cuentas_indiv.append((ws[i_c]['x0'], max(w['x1'] for w in toks)))

    if len(cuentas_indiv) >= 4:
        x0s = [c[0] for c in cuentas_indiv]
        if max(x0s) > min(x0s) + 100.0:
            mid_x0 = (min(x0s) + max(x0s)) / 2.0
            izqs = [c for c in cuentas_indiv if c[0] < mid_x0]
            ders = [c for c in cuentas_indiv if c[0] >= mid_x0]
            if len(izqs) >= MIN_FILAS_DOBLES and len(ders) >= MIN_FILAS_DOBLES:
                max_izq_x1 = max(c[1] for c in izqs)
                min_der_x0 = min(c[0] for c in ders)
                if min_der_x0 > max_izq_x1 + MIN_GAP_WIDTH:
                    return (max_izq_x1 + min_der_x0) / 2.0

    return None


def separar_page(page: Any) -> Optional[List[str]]:
    """
    Separa una página a dos columnas usando el boundary por consenso geométrico contable.
    Devuelve None si no hay evidencia clara para no forzar bisección.
    """
    try:
        words = page.extract_words()
        if not words:
            return None

        boundary = _calcular_boundary_robusto(page)
        if boundary is None:
            return None

        rows: Dict[int, List[Dict[str, Any]]] = {}
        for w in words:
            top_bucket = round(w['top'] / 3.0) * 3
            rows.setdefault(top_bucket, []).append(w)

        left_rows: Dict[int, List[str]] = {}
        right_rows: Dict[int, List[str]] = {}
        headers: List[str] = []

        for top in sorted(rows):
            ws = sorted(rows[top], key=lambda x: x['x0'])
            line_str = ' '.join(w['text'] for w in ws)
            # Título centrado o cabecera completa que cruza el eje
            if any(w['x0'] < boundary < w['x1'] for w in ws) or (
                ws[0]['x0'] < boundary and ws[-1]['x1'] > boundary and not any(_token_es_codigo_candidato(w['text']) for w in ws)
            ):
                headers.append(line_str)
            else:
                l_words = [w['text'] for w in ws if w['x1'] <= boundary]
                r_words = [w['text'] for w in ws if w['x0'] >= boundary]
                if l_words:
                    left_rows.setdefault(top, []).extend(l_words)
                if r_words:
                    right_rows.setdefault(top, []).extend(r_words)

        lines = list(headers)
        for t in sorted(left_rows):
            lines.append(' '.join(left_rows[t]))
        for t in sorted(right_rows):
            lines.append(' '.join(right_rows[t]))

        return lines
    except Exception as exc:
        logger.debug("Error en separación de doble columna: %s", exc)
        return None


def _extraer_lineas_paginas_pdf(ruta_pdf: Path, paginas: List[int]) -> Optional[List[str]]:
    """Extrae líneas de texto nativo exclusivamente para las páginas seleccionadas (1-indexed)."""
    import pdfplumber
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            paginas_set = set(paginas)
            lineas: List[str] = []
            for idx, page in enumerate(pdf.pages, 1):
                if idx in paginas_set:
                    txt = page.extract_text() or ""
                    for linea in txt.split("\n"):
                        if linea.strip():
                            lineas.append(linea.strip())
            return lineas if lineas else None
    except Exception:
        return None


def separar_desde_pdf(path: Path, paginas: Optional[List[int]] = None) -> Optional[List[str]]:
    """Ejecuta la separación sobre las páginas solicitadas de un PDF (1-indexed)."""
    import pdfplumber
    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return None
            if paginas is not None:
                paginas_set = set(paginas)
                paginas_a_procesar = [p for idx, p in enumerate(pdf.pages, 1) if idx in paginas_set]
            else:
                paginas_a_procesar = pdf.pages

            if not paginas_a_procesar:
                return None

            salida: List[str] = []
            activo_al_menos_una = False
            for page in paginas_a_procesar:
                page_lines = separar_page(page)
                if page_lines is not None:
                    activo_al_menos_una = True
                    salida.extend(linea for linea in page_lines if linea.strip())
                else:
                    raw_text = page.extract_text() or ""
                    salida.extend(linea for linea in raw_text.split('\n') if linea.strip())
            return salida if activo_al_menos_una else None
    except Exception as exc:
        logger.debug("Error procesando PDF de doble columna: %s", exc)
        return None


class DoubleColumnExtractor(SpecializedExtractor):
    """Extrae balances/EEFF de doble columna usando el splitter estructural por consenso."""

    id = "double_column"
    display_name = "Balance Doble Columna"
    supported_families: list[str] = []

    def extract(self, path: Path, context: Any = None, paginas: Optional[List[int]] = None) -> ExtractorResult:
        from parser_universal import ExtractionContext, ParserPDF

        t0 = time.perf_counter()
        lineas = separar_desde_pdf(path, paginas=paginas)
        if lineas is None:
            if paginas is not None:
                raw_lines = _extraer_lineas_paginas_pdf(path, paginas)
                lineas_presplit = raw_lines if raw_lines else ["[EMPTY_PAGE]"]
                ctx = ExtractionContext(lineas_presplit=lineas_presplit)
                res_pdf = ParserPDF().parsear(path, ctx)
                return ExtractorResult(
                    extractor_id=self.id,
                    display_name=self.display_name,
                    family_id=FAMILIA_DESCONOCIDA,
                    confidence=0.0,
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                    fallback_used=True,
                    result=res_pdf,
                )
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

        # Validación posterior de que ambos bloques produjeron cuentas
        cuentas_validas = [c for c in resultado.cuentas if c.monto is not None]
        if len(cuentas_validas) < MIN_FILAS_DOBLES:
            return self.delegate_to_universal(path, context)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return ExtractorResult(
            extractor_id=self.id,
            display_name=self.display_name,
            family_id=FAMILIA_DESCONOCIDA,
            confidence=0.98,
            elapsed_ms=elapsed_ms,
            fallback_used=False,
            result=resultado,
        )