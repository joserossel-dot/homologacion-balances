"""
parser_universal.py

Parser universal de balances tributarios chilenos (Excel y PDF).

Pipeline:
  1. Detectar tipo de archivo (xlsx/xls/pdf) y validar integridad
  2. PDF: intentar extracción de texto nativo
  3. Si no hay texto nativo → OCR con detección automática de rotación
  4. Detectar formato de código de cuenta (guion/punto/compacto/sin_codigo)
  5. Detectar separador de miles (punto vs coma)
  6. Parsear líneas → lista de CuentaRaw con código, nombre, monto,
     y columna de origen (activo/pasivo/pérdida/ganancia) cuando exista
"""

import csv
import io
import logging
import math
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pdfplumber
from PIL import Image


logger = logging.getLogger("parser_universal")

RAW_MONETARY_COLUMNS = (
    "debitos", "creditos", "saldo_deudor", "saldo_acreedor",
    "activo", "pasivo", "perdida", "ganancia",
)


def _sin_acentos(texto: str) -> str:
    return ''.join(
        char for char in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(char)
    )


def detectar_años_y_monedas(lineas: list[str]) -> tuple[list[str], list[str]]:
    años = []
    monedas = []
    patron_año = re.compile(r'\b(20\d{2})\b')

    for l in lineas[:60]:
        l_norm = _sin_acentos(l).lower()
        matches = patron_año.findall(l_norm)
        for m in matches:
            if m not in años:
                años.append(m)
        if 'actual' in l_norm and 'actual' not in años:
            años.append('actual')
        if 'anterior' in l_norm and 'anterior' not in años:
            años.append('anterior')
        if 'acumulado' in l_norm and 'acumulado' not in años:
            años.append('acumulado')

        # Scan tokens in order to preserve header column order
        tokens_lower = [t.lower() for t in l.split()]
        for t in tokens_lower:
            if any(w in t for w in ('usd', 'dolar', 'us$', 'dolares')):
                if 'USD' not in monedas:
                    monedas.append('USD')
            elif any(w in t for w in ('clp', 'peso', 'clp$', 'pesos')):
                if 'CLP' not in monedas:
                    monedas.append('CLP')

    if not monedas:
        for l in lineas[:60]:
            if '$' in l:
                monedas.append('CLP')
                break
    return años, monedas


def split_side_by_side(line: str) -> list[str]:
    tokens = line.split()
    if len(tokens) < 6:
        return [line]

    # Una fila tributaria completa ya trae ocho celdas monetarias al final.
    # Guiones internos de la glosa ("Préstamo JL - CP", por ejemplo) forman
    # el patrón textual T-N-T-N y antes se confundían con dos tablas paralelas.
    # Si las ocho columnas están presentes, la fila es canónica y no se parte.
    trailing_amounts = 0
    for token in reversed(tokens):
        cleaned = token.replace("$", "").strip()
        if (
            cleaned in {"-", "—", "−", "o", "O"}
            or re.fullmatch(r"-?\(?\d[\d.,]*\)?", cleaned)
        ):
            trailing_amounts += 1
            continue
        break
    if trailing_amounts >= len(RAW_MONETARY_COLUMNS):
        return [line]

    # Classify tokens
    types = []
    for t in tokens:
        t_stripped = t.replace('$', '').replace('(', '').replace(')', '').strip(' .-–—−,[]')
        is_num = False
        if re.search(r'\d', t_stripped) or t in ('-', '—', '−') or t_stripped in ('', '-', '—', '−'):
            is_num = True
        types.append('N' if is_num else 'T')

    # Collapsed groups
    groups = []  # list of (type, start_idx, end_idx)
    current_type = None
    start_idx = 0
    for idx, t_type in enumerate(types):
        if t_type != current_type:
            if current_type is not None:
                groups.append((current_type, start_idx, idx))
            current_type = t_type
            start_idx = idx
    if current_type is not None:
        groups.append((current_type, start_idx, len(types)))

    # Build the collapsed pattern string
    pattern = "".join(g[0] for g in groups)

    # Check if we have a side-by-side transition 'TNTN'
    if "TNTN" in pattern:
        t_count = 0
        split_token_idx = -1
        for g_idx, (g_type, g_start, g_end) in enumerate(groups):
            if g_type == 'T':
                t_count += 1
                if t_count == 2:
                    split_token_idx = g_start
                    break
        if split_token_idx != -1:
            # Check if the token immediately preceding split_token_idx is a code
            if split_token_idx > 0:
                prev_tok = tokens[split_token_idx - 1]
                if re.match(r'^\d+[\d.\-]*$', prev_tok) and len(prev_tok) >= 3:
                    split_token_idx -= 1
            left_line = " ".join(tokens[:split_token_idx]).strip(' .-–—−')
            right_line = " ".join(tokens[split_token_idx:]).strip(' .-–—−')
            return [left_line, right_line]

    return [line]


def asociar_lineas_verticales(lineas: list[str]) -> list[str]:
    new_lines = []
    skip = False

    for idx in range(len(lineas)):
        if skip:
            skip = False
            continue

        l_curr = lineas[idx].strip()
        if not l_curr:
            new_lines.append("")
            continue

        has_digits_curr = re.search(r'\d{3,}', l_curr)

        if not has_digits_curr and idx + 1 < len(lineas):
            l_next = lineas[idx + 1].strip()
            cleaned_next = re.sub(r'[\d\s.,$()\-—−_\[\]]', '', l_next)

            if cleaned_next == "" and l_next and re.search(r'\d', l_next):
                merged = f"{l_curr} {l_next}"
                new_lines.append(merged)
                skip = True
                continue

        new_lines.append(lineas[idx])

    return new_lines




def _extraer_tabla_balance_8_columnas(page) -> list[str]:
    """Reconstruye tablas nativas donde los guiones preservan columnas vacías.

    ``extract_text`` colapsa esas celdas y desplaza el monto hacia Ganancia.
    ``extract_tables`` conserva las nueve celdas (nombre + ocho importes), por
    lo que se emite una línea canónica compatible con ``parsear_linea``.
    """
    esperados = [
        'nombre', 'debitos', 'creditos', 'saldo deudor', 'saldo acreedor',
        'activo', 'pasivo', 'perdida', 'ganancia',
    ]
    for tabla in page.extract_tables() or []:
        for indice, fila in enumerate(tabla):
            if not fila or len(fila) != 9:
                continue
            encabezados = [
                re.sub(r'\s+', ' ', _sin_acentos(str(celda or '')).lower()).strip()
                for celda in fila
            ]
            if encabezados != esperados:
                continue

            lineas: list[str] = []
            for datos in tabla[indice + 1:]:
                if not datos or len(datos) != 9:
                    continue
                nombre = re.sub(r'\s+', ' ', str(datos[0] or '')).strip()
                if not nombre:
                    continue
                montos = [
                    '0' if str(celda or '').strip() in ('', '-')
                    else re.sub(r'\s+', '', str(celda))
                    for celda in datos[1:]
                ]
                lineas.append(f"{nombre} {' '.join(montos)}")
            if lineas:
                return lineas
    return []


def _agrupar_palabras_por_linea(words: list[dict], tolerancia: float = 2.5) -> list[list[dict]]:
    """Agrupa palabras por coordenada vertical sin depender de bordes de tabla."""
    grupos: list[list[dict]] = []
    for word in sorted(words, key=lambda item: (float(item["top"]), float(item["x0"]))):
        if not grupos or abs(float(word["top"]) - float(grupos[-1][0]["top"])) > tolerancia:
            grupos.append([word])
        else:
            grupos[-1].append(word)
    return grupos


_HEADER_ALIASES = {
    "nombre": {"CUENTA", "NOMBRE", "DESCRIPCION", "DETALLE"},
    "debitos": {"DEBITOS", "DEBITO", "DEBE", "PEBITOS", "DEBIT0S"},
    "creditos": {"CREDITOS", "CREDITO", "HABER"},
    "saldo_deudor": {"DEUDOR", "SDEUDOR", "SALDODEUDOR"},
    "saldo_acreedor": {"ACREEDOR", "ACREEEDOR", "SACREEDOR", "SALDOACREEDOR"},
    "activo": {"ACTIVO", "ACTIVOS"},
    "pasivo": {"PASIVO", "PASIVOS", "PASIWO", "PATRIMONIO"},
    "perdida": {"PERDIDA", "PERDIDAS"},
    "ganancia": {"GANANCIA", "GANANCIAS"},
}


def _extraer_tabla_balance_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Extrae Cuenta + ocho importes usando encabezados y geometría.

    Acepta documentos con o sin código y sinónimos comunes de encabezado. El
    layout detectado se puede reutilizar en páginas continuadas sin encabezado.
    """
    try:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
    except Exception:
        return [], column_centers
    grupos = _agrupar_palabras_por_linea(words)
    header_words: list[dict] | None = None
    detected: dict[str, dict] = {}
    for start in range(len(grupos)):
        for window_size in (1, 2, 3):
            window = grupos[start:start + window_size]
            if len(window) != window_size:
                continue
            if float(window[-1][0]["top"]) - float(window[0][0]["top"]) > 18:
                continue
            combined = [word for group in window for word in group]
            normalized = {
                re.sub(
                    r"[^A-Z]", "",
                    _sin_acentos(str(word.get("text", ""))).upper(),
                ): word
                for word in combined
            }
            matches: dict[str, dict] = {}
            for key, aliases in _HEADER_ALIASES.items():
                for alias in aliases:
                    if alias in normalized:
                        matches[key] = normalized[alias]
                        break
            if all(key in matches for key in RAW_MONETARY_COLUMNS):
                header_words = combined
                detected = matches
                break
        if header_words:
            break
    if not header_words and not column_centers:
        return [], None

    if header_words:
        ordered = [detected["nombre"]] + [detected[key] for key in RAW_MONETARY_COLUMNS]
        centers = [
            (float(word["x0"]) + float(word["x1"])) / 2
            for word in ordered
        ]
    else:
        centers = list(column_centers or [])
    if len(centers) != 9:
        return [], column_centers
    name_center = centers[0]
    amount_centers = centers[1:]
    text_boundary = (name_center + amount_centers[0]) / 2
    header_bottom = max(float(w["top"]) for w in header_words) if header_words else -1.0
    lineas: list[str] = []
    for grupo in grupos:
        if float(grupo[0]["top"]) <= header_bottom + 1.5:
            continue
        text_words: list[dict] = []
        amount_cells: list[list[dict]] = [[] for _ in range(8)]
        for word in grupo:
            token = str(word["text"]).strip()
            xmid = (float(word["x0"]) + float(word["x1"])) / 2
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            es_monto = token == "-" or bool(PATRON_MONTOS.fullmatch(token_normalizado))
            # En tablas escaneadas Tesseract suele leer el cero aislado como
            # pequeños glifos sin dígitos (``o``, ``]``, ``»``...). Sólo los
            # aceptamos dentro de la vecindad de una columna monetaria para no
            # convertir palabras legítimas del nombre en importes.
            distancia_columna = min(abs(xmid - center) for center in amount_centers)
            es_cero_en_celda = (
                distancia_columna <= 32
                and _es_token_cero_ocr_en_celda(token)
            )
            if es_cero_en_celda:
                es_monto = True
            if not es_monto or float(word["x1"]) < text_boundary:
                text_words.append(word)
                continue
            nearest = min(
                range(len(amount_centers)),
                key=lambda index: abs(xmid - amount_centers[index]),
            )
            amount_cells[nearest].append(word)
        text_tokens = [str(w["text"]) for w in sorted(text_words, key=lambda w: w["x0"])]
        code = ""
        if text_tokens and re.fullmatch(r"\d{4,10}|\d+(?:[.-]\d+){1,}", text_tokens[0]):
            code = text_tokens.pop(0)
        name = " ".join(text_tokens).strip()
        if not name:
            continue
        amounts = []
        for cell in amount_cells:
            token = "".join(str(w["text"]) for w in sorted(cell, key=lambda w: w["x0"])).strip()
            token_normalizado = normalizar_token_ocr(token).replace("$", "")
            amounts.append(
                token if token != "-" and PATRON_MONTOS.fullmatch(token_normalizado)
                else "0"
            )
        prefix = f"{code} " if code else ""
        lineas.append(f"{prefix}{name} {' '.join(amounts)}")
    return lineas, centers


def _extraer_tabla_balance_10_columnas_por_coordenadas(
    page, column_centers: Optional[list[float]] = None,
) -> tuple[list[str], Optional[list[float]]]:
    """Alias compatible para la estrategia general de ocho montos."""
    return _extraer_tabla_balance_por_coordenadas(page, column_centers)


# Feature flag: cuando está en False, se usa la heurística fija ULTIMAS_COLS.
# Cuando está en True, LayoutDetector analiza los encabezados del documento
# para determinar el orden real de columnas.
ENABLE_DYNAMIC_LAYOUT = False

# OBSOLETO desde Fase A: ParserPDF ya no ejecuta AccountTypeResolver.
# Se conserva solo para compatibilidad (imports/tests). Sin efecto.
ENABLE_ACCOUNT_TYPE_RESOLVER = False

# Umbral de confianza para aplicar corrección de rotación 180°
# sobre texto nativo. Por debajo de este umbral se usa el flujo normal.
ROTATION_CORRECTION_THRESHOLD = 0.7

# Umbral de confianza para usar LayoutDetector desde ExtractionContext.
# Si la confianza del layout detectado por DocumentAnalyzer supera este
# umbral, ParserPDF usa el orden de columnas del contexto en lugar de la
# heurística estándar (ULTIMAS_COLS).
LAYOUT_CONFIDENCE_THRESHOLD = 0.8

# OBSOLETO desde Fase A: la resolución de tipo_cuenta ya no se activa desde
# ExtractionContext dentro de ParserPDF. Se conserva solo para compatibilidad
# (imports/tests). Sin efecto.
ACCOUNT_TYPE_CONFIDENCE_THRESHOLD = 0.7

# Límites defensivos para OCR en instancias con CPU/memoria acotadas (Render).
# Rasterizar a 250 DPI y entregar imágenes sin límite a Tesseract podía bloquear
# una página durante más de dos minutos y abortar la carga completa.
OCR_RENDER_DPI = 200
OCR_MAX_PIXELS = 3_500_000
OCR_RETRY_MAX_PIXELS = 1_200_000
OCR_PAGE_TIMEOUT_SECONDS = 120
OCR_RETRY_TIMEOUT_SECONDS = 90


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

class FormatoCodigo(str, Enum):
    GUION = 'guion'           # 1-01-01-02-01
    PUNTO = 'punto'            # 1.01.01.02
    COMPACTO = 'compacto'      # 1112001
    SIN_CODIGO = 'sin_codigo'  # solo nombre


class OrigenColumna(str, Enum):
    """Columna del balance donde se reportó el monto (señal para D3/D4)."""
    ACTIVO = 'activo'
    PASIVO = 'pasivo'
    PERDIDA = 'perdida'
    GANANCIA = 'ganancia'
    DEUDOR = 'deudor'
    ACREEDOR = 'acreedor'
    DESCONOCIDO = 'desconocido'


# Mapeo de strings de LayoutDetector a enum OrigenColumna.
# Solo se incluyen columnas informativas para asignación de monto.
_LAYOUT_COLUMN_MAP: dict[str, OrigenColumna] = {
    "activo": OrigenColumna.ACTIVO,
    "pasivo": OrigenColumna.PASIVO,
    "perdida": OrigenColumna.PERDIDA,
    "ganancia": OrigenColumna.GANANCIA,
    "patrimonio": OrigenColumna.PASIVO,
    "deudor": OrigenColumna.DEUDOR,
    "acreedor": OrigenColumna.ACREEDOR,
    "saldo": OrigenColumna.DESCONOCIDO,
}


@dataclass
class CuentaRaw:
    linea: int
    codigo: Optional[str]
    nombre: str
    monto: Optional[float]
    origen_columna: OrigenColumna = OrigenColumna.DESCONOCIDO
    es_total: bool = False
    confianza_extraccion: float = 1.0  # baja si viene de OCR
    tipo_cuenta: Optional[str] = None  # DEPRECATED (Fase A): NO lo escribe ParserPDF; se puebla post-parseo.
    montos_columnas: dict[str, float] = field(default_factory=dict)
    montos_periodos: dict[str, float] = field(default_factory=dict)
    columnas_derivadas: list[str] = field(default_factory=list)


@dataclass
class CertificacionExtraccion:
    estado: str = "no_evaluable"  # certificada | parcial | fallida | no_evaluable
    metodo: str = ""
    totales_impresos: dict[str, float] = field(default_factory=dict)
    totales_calculados: dict[str, float] = field(default_factory=dict)
    diferencias: dict[str, float] = field(default_factory=dict)
    razones: list[str] = field(default_factory=list)
    filas_evaluadas: int = 0
    filas_inconsistentes: list[int] = field(default_factory=list)
    totales_finales_validos: Optional[bool] = None
    resultado_ejercicio: Optional[float] = None
    tipo_resultado: Optional[str] = None
    columnas_total_reconstruidas: list[str] = field(default_factory=list)
    # Independiente del estado de certificación de las ocho columnas.
    columnas_finales_validadas: bool = False
    observaciones_auxiliares: list[dict] = field(default_factory=list)


@dataclass
class ResultadoParseo:
    archivo: str
    formato_codigo: FormatoCodigo
    separador_miles: str            # '.' o ','
    requirio_ocr: bool
    rotacion_aplicada: int           # 0 o 90
    cuentas: list[CuentaRaw] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    # Sprint 31: contexto del análisis documental previo al parseo.
    # None cuando no se ejecutó (Excel) o cuando el análisis falló.
    document_context: Optional[Any] = None
    # Sprint 34: SOLO anotación de qué extractor se seleccionó (id, familia,
    # confidence, fallback, tiempo). NO cambia la extracción: None cuando no
    # hubo análisis documental o cuando el análisis de extractor falló.
    extractor_info: Optional[dict] = None
    certificacion_extraccion: CertificacionExtraccion = field(
        default_factory=CertificacionExtraccion
    )


@dataclass
class ExtractionContext:
    """Contexto de extracción producido por DocumentAnalyzer.

    Contiene pistas estructurales sobre el documento que ParserPDF
    puede usar para adaptar su estrategia de extracción.

    rotation_hint:   rotación detectada por DocumentAnalyzer (0, 90, 180)
    rotation_confidence: confianza de la detección de rotación
    needs_ocr:       si el documento requiere OCR (None = dejar que ParserPDF decida)
    layout_hint:     orden de columnas detectado por LayoutDetector
    format_hint:     formato de código detectado
    confidence:      confianza general del análisis
    """
    rotation_hint: int = 0
    rotation_confidence: float = 0.0
    needs_ocr: Optional[bool] = None
    layout_hint: Optional[list[str]] = None
    layout_confidence: float = 0.0
    format_hint: Optional[FormatoCodigo] = None
    confidence: float = 1.0
    analysis_source: Optional[str] = None
    # Líneas ya separadas por un extractor especializado (doble columna).
    # Si vienen seteadas, ParserPDF las usa en lugar de re-extraer el texto
    # plano del PDF, reutilizando íntegramente el pipeline de parseo.
    lineas_presplit: Optional[list[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIÓN DE ARCHIVO
# ─────────────────────────────────────────────────────────────────────────────

def validar_archivo(path: Path) -> tuple[bool, str]:
    """Valida que el archivo no esté corrupto antes de procesarlo."""
    if not path.exists():
        return False, f"Archivo no existe: {path}"

    size = path.stat().st_size
    if size == 0:
        return False, "Archivo vacío (0 bytes)"

    suffix = path.suffix.lower()

    if suffix in ('.xlsx', '.xlsm'):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                if 'xl/workbook.xml' not in z.namelist():
                    return False, "El .xlsx no contiene workbook.xml válido"
        except zipfile.BadZipFile:
            with open(path, 'rb') as f:
                head = f.read(min(size, 4096))
            if head == b'\x00' * len(head):
                return False, (
                    f"Archivo corrupto: {size} bytes, todo ceros binarios. "
                    "Probablemente una descarga/exportación fallida."
                )
            return False, "Archivo .xlsx corrupto: no es un ZIP válido"

    elif suffix == '.xls':
        with open(path, 'rb') as f:
            header = f.read(8)
        ole2_sig = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        if header != ole2_sig:
            return False, f"Archivo .xls no tiene firma OLE2 válida."

    elif suffix == '.pdf':
        with open(path, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False, f"Archivo .pdf no tiene firma PDF válida."

    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DE FORMATO DE CÓDIGO DE CUENTA Y SEPARADOR DE MILES
# ─────────────────────────────────────────────────────────────────────────────

PATRON_GUION = re.compile(r'^\d+(-\d+){2,}$')
PATRON_PUNTO = re.compile(r'^\d+(\.\d+){2,}$')
# COMPACTO acepta códigos de 5 a 10 dígitos (p. ej. 11010 CAJAS / 21010 OBLIG).
# Antes era 6-10: los códigos de 5 dígitos quedaban como SIN_CODIGO.
PATRON_COMPACTO = re.compile(r'^\d{5,10}$')


def detectar_formato_codigo(codigos_muestra: list[str]) -> FormatoCodigo:
    conteo = {FormatoCodigo.GUION: 0, FormatoCodigo.PUNTO: 0,
              FormatoCodigo.COMPACTO: 0, FormatoCodigo.SIN_CODIGO: 0}

    for c in codigos_muestra:
        c = (c or '').strip()
        if not c:
            conteo[FormatoCodigo.SIN_CODIGO] += 1
        elif PATRON_GUION.match(c):
            conteo[FormatoCodigo.GUION] += 1
        elif PATRON_PUNTO.match(c):
            conteo[FormatoCodigo.PUNTO] += 1
        elif PATRON_COMPACTO.match(c):
            conteo[FormatoCodigo.COMPACTO] += 1
        else:
            conteo[FormatoCodigo.SIN_CODIGO] += 1

    return max(conteo, key=conteo.get)


def detectar_separador_miles(montos_muestra: list[str]) -> str:
    puntos_como_miles = 0
    comas_como_miles = 0

    for m in montos_muestra:
        m = m.strip()
        if not m or m in ('0', '-'):
            continue

        if '.' in m and ',' in m:
            if m.rfind('.') > m.rfind(','):
                comas_como_miles += 1
            else:
                puntos_como_miles += 1
            continue

        if '.' in m:
            partes = m.split('.')
            if all(len(p) == 3 for p in partes[1:]) and len(partes) > 1:
                puntos_como_miles += 1
            elif len(partes) == 2 and len(partes[-1]) in (1, 2):
                pass
            else:
                puntos_como_miles += 1

        elif ',' in m:
            partes = m.split(',')
            if all(len(p) == 3 for p in partes[1:]) and len(partes) > 1:
                comas_como_miles += 1
            elif len(partes) == 2 and len(partes[-1]) in (1, 2):
                pass
            else:
                comas_como_miles += 1

    if puntos_como_miles >= comas_como_miles:
        return '.'
    return ','


def parsear_monto(valor: str, separador_miles: str) -> Optional[float]:
    if valor is None:
        return None
    v = valor.strip().replace(' ', '').replace('$', '').replace('CLP', '').replace('USD', '')
    if v in ('', '-', '—', '−', '0', '0.00', '0,00'):
        return 0.0

    negativo = False
    if v.startswith('(') and v.endswith(')'):
        negativo = True
        v = v[1:-1].strip()
    if v.startswith('-'):
        negativo = True
        v = v[1:].strip()
    if v.endswith('-'):
        negativo = True
        v = v[:-1].strip()

    v = v.replace('(', '').replace(')', '')

    if separador_miles == '.':
        v = v.replace('.', '').replace(',', '.')
    elif separador_miles == ',':
        v = v.replace(',', '')
    else:
        if '.' in v and ',' in v:
            if v.rfind('.') > v.rfind(','):
                v = v.replace(',', '')
            else:
                v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            parts = v.split(',')
            if len(parts) == 2 and len(parts[1]) == 3:
                v = v.replace(',', '')
            else:
                v = v.replace(',', '.')
        elif '.' in v:
            parts = v.split('.')
            if len(parts) == 2 and len(parts[1]) == 3:
                v = v.replace('.', '')
            elif len(parts) > 2:
                v = v.replace('.', '')

    try:
        num = float(v)
        return -num if negativo else num
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# OCR CON ROTACIÓN AUTOMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

TESSDATA_DIR = '/usr/local/share/tessdata'


def _tesseract_env() -> dict[str, str]:
    """Entorno estable para instancias con una fracción pequeña de CPU."""
    return {
        'TESSDATA_PREFIX': TESSDATA_DIR,
        'OMP_THREAD_LIMIT': '1',
    }


def obtener_tesseract_bin() -> str:
    return shutil.which('tesseract') or 'tesseract'


def detectar_rotacion_osd(img_path: Path) -> Optional[int]:
    try:
        result = subprocess.run(
            [obtener_tesseract_bin(), str(img_path), '-', '--psm', '0', '-l', 'osd'],
            capture_output=True, text=True, timeout=60,
            env=_tesseract_env()
        )
        for line in result.stdout.splitlines():
            if 'Orientation in degrees' in line:
                grados = int(line.split(':')[1].strip())
                return grados
    except Exception:
        pass
    return None


def detectar_rotacion_heuristica(img_path: Path) -> int:
    img = Image.open(img_path)
    mejor_rotacion = 0
    mejor_score = -1

    for rot in (0, 90):
        test_img = img if rot == 0 else img.rotate(rot, expand=True)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            test_img.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                [obtener_tesseract_bin(), str(tmp_path), '-', '--psm', '6', '-l', 'spa'],
                capture_output=True, text=True, timeout=90,
                env=_tesseract_env()
            )
            texto = result.stdout
            palabras = re.findall(r'[a-záéíóúñA-ZÁÉÍÓÚÑ]{3,}', texto)
            score = len(palabras)
        except Exception:
            score = 0
        finally:
            tmp_path.unlink(missing_ok=True)

        if score > mejor_score:
            mejor_score = score
            mejor_rotacion = rot

    return mejor_rotacion


def ocr_pagina(img_path: Path, rotacion: int, psm: int = 6) -> str:
    tmp_path: Optional[Path] = None
    retry_path: Optional[Path] = None
    imagen_ocr = img_path

    with Image.open(img_path) as img:
        preparada = img.rotate(rotacion, expand=True) if rotacion != 0 else img.copy()
        pixeles = preparada.width * preparada.height
        if pixeles > OCR_MAX_PIXELS:
            escala = (OCR_MAX_PIXELS / pixeles) ** 0.5
            nuevo_tamano = (
                max(1, int(preparada.width * escala)),
                max(1, int(preparada.height * escala)),
            )
            preparada = preparada.resize(nuevo_tamano, Image.Resampling.LANCZOS)

        if rotacion != 0 or pixeles > OCR_MAX_PIXELS:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                preparada.save(tmp.name)
                tmp_path = Path(tmp.name)
                imagen_ocr = tmp_path

    try:
        try:
            result = subprocess.run(
                [obtener_tesseract_bin(), str(imagen_ocr), '-', '--psm', str(psm), '-l', 'spa'],
                capture_output=True, text=True, timeout=OCR_PAGE_TIMEOUT_SECONDS,
                env=_tesseract_env()
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "OCR excedió %ss; reintentando imagen reducida: %s",
                OCR_PAGE_TIMEOUT_SECONDS,
                img_path.name,
            )
            with Image.open(imagen_ocr) as img:
                pixeles = img.width * img.height
                if pixeles <= OCR_RETRY_MAX_PIXELS:
                    return ""
                escala = (OCR_RETRY_MAX_PIXELS / pixeles) ** 0.5
                reducida = img.resize(
                    (
                        max(1, int(img.width * escala)),
                        max(1, int(img.height * escala)),
                    ),
                    Image.Resampling.LANCZOS,
                )
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    reducida.save(tmp.name)
                    retry_path = Path(tmp.name)
            try:
                result = subprocess.run(
                    [obtener_tesseract_bin(), str(retry_path), '-', '--psm', str(psm), '-l', 'spa'],
                    capture_output=True, text=True,
                    timeout=OCR_RETRY_TIMEOUT_SECONDS,
                    env=_tesseract_env(),
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "OCR omitido tras segundo timeout de %ss: %s",
                    OCR_RETRY_TIMEOUT_SECONDS,
                    img_path.name,
                )
                return ""
        if result.returncode != 0:
            logger.warning(
                "Tesseract falló para %s (código %s): %s",
                img_path.name,
                result.returncode,
                (result.stderr or "").strip()[:300],
            )
            return ""
        return result.stdout
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        if retry_path is not None:
            retry_path.unlink(missing_ok=True)


def ocr_pagina_tsv(img_path: Path, rotacion: int, psm: int = 6) -> list[dict]:
    """Obtiene palabras y coordenadas OCR para reconstrucción tabular."""
    tmp_path: Optional[Path] = None
    imagen_ocr = img_path
    if rotacion != 0:
        with Image.open(img_path) as img:
            preparada = img.rotate(rotacion, expand=True)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preparada.save(tmp.name)
                tmp_path = Path(tmp.name)
                imagen_ocr = tmp_path
    try:
        try:
            result = subprocess.run(
                [
                    obtener_tesseract_bin(), str(imagen_ocr), "stdout", "-l", "spa",
                    "--psm", str(psm), "tsv",
                ],
                capture_output=True, text=True,
                timeout=OCR_PAGE_TIMEOUT_SECONDS,
                env=_tesseract_env(),
            )
        except subprocess.TimeoutExpired:
            logger.warning("OCR TSV excedió el timeout: %s", img_path.name)
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        words: list[dict] = []
        line_positions: dict[tuple[str, str, str, str], float] = {}
        for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
            text = str(row.get("text") or "").strip()
            if row.get("level") != "5" or not text:
                continue
            try:
                left = float(row["left"])
                top = float(row["top"])
                width = float(row["width"])
            except (KeyError, TypeError, ValueError):
                continue
            line_key = (
                str(row.get("page_num") or ""), str(row.get("block_num") or ""),
                str(row.get("par_num") or ""), str(row.get("line_num") or ""),
            )
            if line_key not in line_positions:
                line_positions[line_key] = float(len(line_positions) * 5)
            words.append({
                "text": text,
                "x0": left,
                "x1": left + width,
                "top": line_positions[line_key],
            })
        return words
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


class _OCRWordsPage:
    def __init__(self, words: list[dict]):
        self._words = words

    def extract_words(self, **_kwargs) -> list[dict]:
        return self._words


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIÓN Y CUADRE MATEMÁTICO DEL BALANCE
# ─────────────────────────────────────────────────────────────────────────────

def verificar_cuadre_balance(cuentas: list[CuentaRaw]) -> tuple[bool, dict, list[str]]:
    totales_calculados = {'activo': 0.0, 'pasivo': 0.0, 'perdida': 0.0, 'ganancia': 0.0}

    for c in cuentas:
        if not c.es_total and c.monto and c.origen_columna.value in totales_calculados:
            totales_calculados[c.origen_columna.value] += c.monto

    act = totales_calculados['activo']
    pas = totales_calculados['pasivo']
    per = totales_calculados['perdida']
    gan = totales_calculados['ganancia']

    lado_balance = act - pas
    lado_resultado = gan - per

    cuadra = abs(lado_balance - lado_resultado) < 10.0

    alertas = []
    if not cuadra:
        alertas.append(
            f"⚠️ CONTROL DE CUADRE FALLIDO: Suma Activos ({act:,.0f}) - Pasivos ({pas:,.0f}) = {lado_balance:,.0f} | "
            f"Suma Ganancias ({gan:,.0f}) - Pérdidas ({per:,.0f}) = {lado_resultado:,.0f}. "
            f"Diferencia insalvable: {abs(lado_balance - lado_resultado):,.0f}"
        )
    return cuadra, totales_calculados, alertas


def _validar_columnas_finales(
    cuentas, detalle, subtotal, calculados, finales, puentes, tolerancia,
) -> bool:
    """Valida importes homologables sin reescribir movimientos ni saldos.

    No basta la igualdad global: cada fila necesita respaldo en movimiento o
    saldo; no se admiten filas monetarias omitidas, partidas en varios destinos
    ni discrepancias en los controles finales impresos.
    """
    columnas = RAW_MONETARY_COLUMNS[4:]
    if not detalle:
        return False
    incluidos = {id(c) for c in detalle}
    for c in cuentas:
        if not c.es_total and id(c) not in incluidos and (
            c.codigo or (c.monto is not None and c.monto != 0)
            or any(c.montos_columnas.values())
        ):
            return False
    if not all(
        math.isfinite(float(values.get(col, 0)))
        for values in (subtotal, calculados)
        for col in columnas
    ):
        return False
    if any(abs(calculados[col] - subtotal[col]) > tolerancia for col in columnas):
        return False
    resultado = subtotal["activo"] - subtotal["pasivo"]
    if abs(resultado - (subtotal["ganancia"] - subtotal["perdida"])) > tolerancia:
        return False
    for c in detalle:
        v = c.montos_columnas
        if not all(math.isfinite(float(v[col])) for col in RAW_MONETARY_COLUMNS):
            return False
        pobladas = [col for col in columnas if v[col] != 0]
        if len(pobladas) > 1:
            return False
        if pobladas and c.origen_columna.value != pobladas[0]:
            return False
        derivadas = set(c.columnas_derivadas)
        if derivadas.intersection(columnas):
            return False
        importe = v[pobladas[0]] if pobladas else 0
        if c.monto is None or not math.isfinite(c.monto) or abs(c.monto - importe) > tolerancia:
            return False
        neto_final = v["activo"] + v["perdida"] - v["pasivo"] - v["ganancia"]
        respaldo_movimiento = (
            not derivadas.intersection({"debitos", "creditos"})
            and abs(v["debitos"] - v["creditos"] - neto_final) <= tolerancia
        )
        respaldo_saldo = (
            not derivadas.intersection({"saldo_deudor", "saldo_acreedor"})
            and abs(v["saldo_deudor"] - v["saldo_acreedor"] - neto_final) <= tolerancia
        )
        if not (respaldo_movimiento or respaldo_saldo):
            return False
    puente_esperado = dict.fromkeys(columnas, 0.0)
    for col in (("pasivo", "perdida") if resultado >= 0 else ("activo", "ganancia")):
        puente_esperado[col] = abs(resultado)
    if puentes:
        if any(
            not math.isfinite(float(puentes[-1].montos_columnas.get(col, 0)))
            or abs(puentes[-1].montos_columnas.get(col, 0) - puente_esperado[col]) > tolerancia
            for col in columnas
        ):
            return False
    if finales:
        if any(
            not math.isfinite(float(finales[-1].montos_columnas[col]))
            or abs(finales[-1].montos_columnas[col] - subtotal[col] - puente_esperado[col]) > tolerancia
            for col in columnas
        ):
            return False
    return True


def certificar_extraccion_columnas(
    cuentas: list[CuentaRaw], metodo: str = "",
    tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Certifica las ocho columnas contra un subtotal impreso independiente."""
    filas_detalle = [
        cuenta for cuenta in cuentas
        if (
            not cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
    ]
    # En balances con plan de cuentas explicito, encabezados, firmas y notas
    # OCR sin codigo no son filas contables y no deben afectar la cuadratura.
    filas_codificadas = [cuenta for cuenta in filas_detalle if cuenta.codigo]
    if len(filas_codificadas) >= 3:
        filas_detalle = filas_codificadas
    filas_inconsistentes: list[int] = []
    for cuenta in filas_detalle:
        values = cuenta.montos_columnas
        movement = values["debitos"] - values["creditos"]
        balance = values["saldo_deudor"] - values["saldo_acreedor"]
        classified = (
            values["activo"] + values["pasivo"]
            + values["perdida"] + values["ganancia"]
        )
        if (
            abs(movement - balance) > tolerancia_absoluta
            or abs(values["saldo_deudor"] + values["saldo_acreedor"] - classified)
            > tolerancia_absoluta
        ):
            filas_inconsistentes.append(cuenta.linea)

    def normalized_name(cuenta: CuentaRaw) -> str:
        return re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()

    def control_key(cuenta: CuentaRaw) -> str:
        return re.sub(r"[^a-z0-9]+", "", normalized_name(cuenta))

    finales = [
        cuenta for cuenta in cuentas
        if (
            cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and (
            "totales iguales" in normalized_name(cuenta)
            or "sumas iguales" in normalized_name(cuenta)
            or control_key(cuenta) in {"totales", "totalgeneral", "sumastotales"}
        )
    ]
    totales_finales_validos: Optional[bool] = None
    fila_final_incompleta = False
    if finales:
        values = finales[-1].montos_columnas
        pairs = (
            ("debitos", "creditos"),
            ("saldo_deudor", "saldo_acreedor"),
            ("activo", "pasivo"),
            ("perdida", "ganancia"),
        )
        fila_final_incompleta = any(
            (values[left] == 0) != (values[right] == 0)
            for left, right in pairs
        )
        if not fila_final_incompleta:
            totales_finales_validos = all(
                abs(values[left] - values[right]) <= tolerancia_absoluta
                for left, right in pairs
            )

    candidatos = [
        cuenta for cuenta in cuentas
        if (
            cuenta.es_total
            and set(RAW_MONETARY_COLUMNS).issubset(cuenta.montos_columnas)
        )
        and (
            "subtotal" in control_key(cuenta)
            or control_key(cuenta) == "sumas"
            or control_key(cuenta).startswith("totalacumulado")
        )
    ]
    if not candidatos:
        razones = ["No se detectó un subtotal impreso de ocho columnas."]
        estado = "no_evaluable"
        diferencias_parciales: dict[str, float] = {}
        if finales:
            final_values = finales[-1].montos_columnas
            for column in RAW_MONETARY_COLUMNS[:4]:
                calculated = sum(
                    float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
                    for cuenta in filas_detalle
                )
                diferencias_parciales[column] = round(
                    calculated - float(final_values.get(column, 0.0) or 0.0), 2
                )
            if any(abs(value) > tolerancia_absoluta for value in diferencias_parciales.values()):
                estado = "fallida"
                razones.append(
                    "Las filas no reproducen Débitos, Créditos o Saldos de la "
                    "fila final impresa."
                )
        if filas_inconsistentes:
            estado = "fallida"
            razones.append(
                f"{len(filas_inconsistentes)} filas no cumplen sus identidades "
                "Debe/Haber, saldo o columna de clasificación."
            )
        if totales_finales_validos is False:
            estado = "fallida"
            razones.append("La fila final impresa no está cuadrada.")
        return CertificacionExtraccion(
            estado=estado, metodo=metodo,
            diferencias=diferencias_parciales,
            razones=razones,
            filas_evaluadas=len(filas_detalle),
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
        )
    acumulados = [
        cuenta for cuenta in candidatos
        if normalized_name(cuenta).startswith("total acumulado")
    ]
    subtotal_referencia = acumulados[-1] if acumulados else candidatos[-1]
    total_impreso = dict(subtotal_referencia.montos_columnas)
    puentes_resultado = [
        cuenta for cuenta in cuentas
        if cuenta.es_total and cuenta.montos_columnas
        and re.match(
            r"^(?:perdida o ganancia|resultado|utilidad|perdida net[ao])\b",
            normalized_name(cuenta),
        )
    ]
    calculados = {column: 0.0 for column in RAW_MONETARY_COLUMNS}
    filas = 0
    for cuenta in filas_detalle:
        filas += 1
        for column in RAW_MONETARY_COLUMNS:
            calculados[column] += float(cuenta.montos_columnas.get(column, 0.0) or 0.0)
    if not filas:
        return CertificacionExtraccion(
            estado="fallida", metodo=metodo,
            totales_impresos=dict(total_impreso),
            razones=["No se detectaron filas de cuentas para contrastar el subtotal."],
            filas_evaluadas=0,
            filas_inconsistentes=filas_inconsistentes,
            totales_finales_validos=totales_finales_validos,
        )
    columnas_total_reconstruidas: list[str] = []
    for column in ("debitos", "creditos"):
        calculated = float(calculados.get(column, 0.0) or 0.0)
        printed = float(total_impreso.get(column, 0.0) or 0.0)
        if calculated <= 0 or printed <= 0:
            continue
        calculated_digits = str(int(round(abs(calculated))))
        printed_digits = str(int(round(abs(printed))))
        missing = len(calculated_digits) - len(printed_digits)
        # Algunos generadores PDF recortan uno o dos dígitos finales del total,
        # aunque las cuentas y los demás seis controles estén completos.
        if missing in {1, 2} and calculated_digits.startswith(printed_digits):
            total_impreso[column] = calculated
            columnas_total_reconstruidas.append(column)

    diferencias = {
        column: round(calculados[column] - float(total_impreso.get(column, 0.0) or 0.0), 2)
        for column in RAW_MONETARY_COLUMNS
    }
    fallidas = {
        column: diff for column, diff in diferencias.items()
        if abs(diff) > tolerancia_absoluta
    }
    razones = []
    if columnas_total_reconstruidas:
        razones.append(
            "Se reconstruyó el final truncado de "
            + ", ".join(columnas_total_reconstruidas)
            + " usando la suma exacta de las cuentas."
        )
    if fallidas:
        detalle = ", ".join(f"{column}={diff:,.0f}" for column, diff in fallidas.items())
        razones.append(f"Las sumas extraídas no reproducen el subtotal impreso: {detalle}.")
    if filas_inconsistentes:
        razones.append(
            f"{len(filas_inconsistentes)} filas no cumplen sus identidades "
            "Debe/Haber, saldo o columna de clasificación."
        )
    if totales_finales_validos is False:
        razones.append("La fila TOTALES IGUALES no está cuadrada en sus pares de columnas.")
    if fila_final_incompleta:
        razones.append(
            "La fila final fue extraída con una o más columnas vacías; el "
            "subtotal y sus identidades se usan como control y el documento "
            "requiere revisión humana."
        )
    resultado_balance_subtotal = (
        float(total_impreso.get("activo", 0.0) or 0.0)
        - float(total_impreso.get("pasivo", 0.0) or 0.0)
    )
    resultado_estado_subtotal = (
        float(total_impreso.get("ganancia", 0.0) or 0.0)
        - float(total_impreso.get("perdida", 0.0) or 0.0)
    )
    ecuacion_subtotal_invalida = (
        fila_final_incompleta
        and abs(resultado_balance_subtotal - resultado_estado_subtotal)
        > tolerancia_absoluta
    )
    if ecuacion_subtotal_invalida:
        razones.append(
            "El subtotal impreso no satisface la ecuación entre balance y "
            "resultado del ejercicio."
        )
    resultado_ejercicio: Optional[float] = None
    tipo_resultado: Optional[str] = None
    puente_invalido = False
    if puentes_resultado:
        puente = puentes_resultado[-1]
        resultado_balance = (
            float(total_impreso.get("activo", 0.0) or 0.0)
            - float(total_impreso.get("pasivo", 0.0) or 0.0)
        )
        resultado_estado = (
            float(total_impreso.get("ganancia", 0.0) or 0.0)
            - float(total_impreso.get("perdida", 0.0) or 0.0)
        )
        if abs(resultado_balance - resultado_estado) > tolerancia_absoluta:
            puente_invalido = True
            razones.append(
                "El resultado derivado del balance no coincide con el resultado "
                "derivado de Pérdidas y Ganancias."
            )
        else:
            resultado_ejercicio = round(resultado_balance, 2)
            tipo_resultado = "utilidad" if resultado_balance >= 0 else "perdida"

        if finales:
            final_values = finales[-1].montos_columnas
            bridge_values = puente.montos_columnas
            cierre_reproducido = True
            for column in RAW_MONETARY_COLUMNS:
                expected = (
                    float(total_impreso.get(column, 0.0) or 0.0)
                    + float(bridge_values.get(column, 0.0) or 0.0)
                )
                actual = float(final_values.get(column, 0.0) or 0.0)
                if abs(expected - actual) <= tolerancia_absoluta:
                    continue
                expected_digits = str(int(round(abs(expected))))
                actual_digits = str(int(round(abs(actual))))
                truncated_final = (
                    column in columnas_total_reconstruidas
                    and len(expected_digits) - len(actual_digits) in {1, 2}
                    and expected_digits.startswith(actual_digits)
                )
                if not truncated_final:
                    cierre_reproducido = False
                    break
            if not cierre_reproducido:
                puente_invalido = True
                razones.append(
                    "La fila PÉRDIDA O GANANCIA no conecta el subtotal con "
                    "la fila SUMAS IGUALES."
                )

    failed = bool(
        fallidas or filas_inconsistentes
        or totales_finales_validos is False or puente_invalido
        or ecuacion_subtotal_invalida
    )
    filas_derivadas = [cuenta.linea for cuenta in filas_detalle if cuenta.columnas_derivadas]
    total_derivado = bool(
        subtotal_referencia.columnas_derivadas or fila_final_incompleta
    )
    if (filas_derivadas or total_derivado) and not failed:
        razones.append(
            f"{len(filas_derivadas)} filas contienen movimientos reconstruidos "
            "desde saldos y clasificación"
            + (" y el subtotal fue completado" if total_derivado else "")
            + "; requieren revisión humana."
        )
    columnas_finales_validadas = (
        not set(subtotal_referencia.columnas_derivadas).intersection(RAW_MONETARY_COLUMNS[4:])
        and _validar_columnas_finales(
            cuentas, filas_detalle, total_impreso, calculados, finales,
            puentes_resultado, tolerancia_absoluta,
        )
    )
    observaciones_auxiliares = []
    if columnas_finales_validadas:
        for cuenta in filas_detalle:
            if cuenta.linea not in filas_inconsistentes:
                continue
            v = cuenta.montos_columnas
            neto = v["activo"] + v["perdida"] - v["pasivo"] - v["ganancia"]
            movimiento_respalda = (
                not set(cuenta.columnas_derivadas).intersection({"debitos", "creditos"})
                and abs(v["debitos"] - v["creditos"] - neto) <= tolerancia_absoluta
            )
            observaciones_auxiliares.append({
                "Fila": cuenta.linea,
                "Cuenta": cuenta.nombre,
                "Revisar": "Saldo deudor / Saldo acreedor" if movimiento_respalda else "Debe / Haber",
                "Detalle": (
                    f"Saldo deudor leído: {v['saldo_deudor']:,.0f}; saldo acreedor leído: "
                    f"{v['saldo_acreedor']:,.0f}. El movimiento respalda el importe final "
                    f"de {cuenta.monto:,.0f}; no cambie la columna de clasificación."
                    if movimiento_respalda else
                    f"Debe leído: {v['debitos']:,.0f}; Haber leído: {v['creditos']:,.0f}. "
                    "El saldo respalda el importe final; no cambie la columna de clasificación."
                ),
            })
    return CertificacionExtraccion(
        estado="fallida" if failed else (
            "parcial" if filas_derivadas or total_derivado else "certificada"
        ),
        metodo=metodo,
        totales_impresos={k: float(total_impreso.get(k, 0.0) or 0.0) for k in RAW_MONETARY_COLUMNS},
        totales_calculados={k: round(v, 2) for k, v in calculados.items()},
        diferencias=diferencias,
        razones=razones,
        filas_evaluadas=filas,
        filas_inconsistentes=filas_inconsistentes,
        totales_finales_validos=totales_finales_validos,
        resultado_ejercicio=resultado_ejercicio,
        tipo_resultado=tipo_resultado,
        columnas_total_reconstruidas=columnas_total_reconstruidas,
        columnas_finales_validadas=columnas_finales_validadas,
        observaciones_auxiliares=observaciones_auxiliares,
    )


def certificar_totales_clasificados(
    cuentas: list[CuentaRaw], tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Control parcial para balances clasificados/IFRS de una o dos columnas.

    Certifica únicamente la ecuación final impresa. No afirma que todas las
    cuentas intermedias estén completas ni correctamente homologadas.
    """
    totals: dict[str, float] = {}
    generic_liability_totals: list[float] = []
    for cuenta in cuentas:
        if cuenta.monto is None:
            continue
        name = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        if name in {"total activos", "total de activos", "total assets"}:
            totals["activo"] = float(cuenta.monto)
        elif name in {
            "total pasivos y patrimonio",
            "total pasivos y patrimonio neto",
            "total pasivo y patrimonio",
            "total patrimonio y pasivos",
            "total de patrimonio y pasivos",
            "total equity and liabilities",
        }:
            totals["pasivo_patrimonio"] = float(cuenta.monto)
        elif name in {"total pasivos", "total de pasivos"}:
            generic_liability_totals.append(float(cuenta.monto))
    if "activo" in totals and "pasivo_patrimonio" not in totals:
        matching_totals = [
            value for value in generic_liability_totals
            if abs(value - totals["activo"]) <= tolerancia_absoluta
        ]
        if matching_totals:
            totals["pasivo_patrimonio"] = matching_totals[-1]
    if set(totals) != {"activo", "pasivo_patrimonio"}:
        return CertificacionExtraccion(
            estado="no_evaluable", metodo="classified_totals",
            razones=[
                "No se encontraron ambos totales finales del balance clasificado."
            ],
        )
    difference = round(totals["activo"] - totals["pasivo_patrimonio"], 2)
    secciones: dict[str, float] = {}
    diferencias_seccion: dict[str, float] = {}
    nombres = [
        re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        for cuenta in cuentas
    ]
    for index, nombre in enumerate(nombres):
        if cuentas[index].es_total or cuentas[index].monto is not None:
            continue
        total_buscado = f"total {nombre}"
        total_index = next(
            (
                candidate for candidate in range(index + 1, len(cuentas))
                if nombres[candidate] == total_buscado
                and cuentas[candidate].es_total
                and cuentas[candidate].monto is not None
            ),
            None,
        )
        if total_index is None:
            continue
        detalle = [
            float(cuenta.monto)
            for cuenta, nombre_detalle in zip(
                cuentas[index + 1:total_index],
                nombres[index + 1:total_index],
            )
            if cuenta.monto is not None
            and (
                not cuenta.es_total
                or re.match(
                    r"^(?:utilidad|perdida|resultado)\s+(?:\(perdida\)\s+)?del\s+ejercicio$",
                    nombre_detalle, re.I,
                )
            )
        ]
        if not detalle:
            continue
        calculado = round(sum(detalle), 2)
        impreso = float(cuentas[total_index].monto or 0.0)
        secciones[nombre] = impreso
        diferencias_seccion[f"seccion:{nombre}"] = round(calculado - impreso, 2)

    secciones_fallidas = {
        nombre: diferencia
        for nombre, diferencia in diferencias_seccion.items()
        if abs(diferencia) > tolerancia_absoluta
    }
    if secciones_fallidas:
        detalle = ", ".join(
            f"{nombre.removeprefix('seccion:')}={diferencia:,.0f}"
            for nombre, diferencia in secciones_fallidas.items()
        )
        return CertificacionExtraccion(
            estado="fallida", metodo="classified_section_totals",
            totales_impresos={**totals, **{f"seccion:{k}": v for k, v in secciones.items()}},
            diferencias={
                "activo_menos_pasivo_patrimonio": difference,
                **diferencias_seccion,
            },
            razones=[
                "El detalle extraído no reproduce uno o más subtotales impresos: "
                f"{detalle}."
            ],
            filas_evaluadas=sum(
                1 for cuenta in cuentas if cuenta.monto is not None and not cuenta.es_total
            ),
            totales_finales_validos=abs(difference) <= tolerancia_absoluta,
        )
    if abs(difference) > tolerancia_absoluta:
        return CertificacionExtraccion(
            estado="fallida", metodo="classified_totals",
            totales_impresos=totals,
            diferencias={"activo_menos_pasivo_patrimonio": difference},
            razones=[
                "El total de activos no coincide con el total de pasivos y patrimonio."
            ],
            totales_finales_validos=False,
        )
    return CertificacionExtraccion(
        estado="parcial", metodo="classified_totals",
        totales_impresos=totals,
        diferencias={
            "activo_menos_pasivo_patrimonio": difference,
            **diferencias_seccion,
        },
        razones=[
            "La ecuación final impresa cuadra"
            + (
                f" y {len(diferencias_seccion)} subtotales de sección fueron reproducidos"
                if diferencias_seccion else ""
            )
            + ", pero la homologación todavía requiere revisión."
        ],
        filas_evaluadas=sum(
            1 for cuenta in cuentas if cuenta.monto is not None and not cuenta.es_total
        ),
        totales_finales_validos=True,
    )


_SECTION_HEADING_PATTERNS: tuple[tuple[re.Pattern, OrigenColumna], ...] = (
    (re.compile(
        r"^(?:total\s+)?(?:activos?(?:\s+(?:corrientes?|no\s+corrientes?|"
        r"circulantes?|fijos?))?|otros\s+activos?|"
        r"(?:non[- ]?current|current)\s+assets?|assets?)$", re.I,
    ),
     OrigenColumna.ACTIVO),
    (re.compile(
        r"^(?:total\s+)?pasivos?(?:\s+(?:corrientes?|no\s+corrientes?|"
        r"circulantes?|a\s+largo\s+plazo))?|"
        r"(?:non[- ]?current|current)\s+liabilities|liabilities$", re.I,
    ),
     OrigenColumna.PASIVO),
    (re.compile(r"^(?:total\s+)?(?:patrimonio(?:\s+neto)?|equity)$", re.I),
     OrigenColumna.PASIVO),
    (re.compile(
        r"^(?:ingresos?|ventas|ganancias?|otros\s+ingresos|incomes?|revenues?)$",
        re.I,
    ),
     OrigenColumna.GANANCIA),
    (re.compile(
        r"^(?:costos?|gastos|perdidas?|otros\s+gastos|"
        r"(?:operating|non[- ]?operational)?\s*expenses?)$",
        re.I,
    ),
     OrigenColumna.PERDIDA),
)


def anotar_secciones_balance_clasificado(cuentas: list[CuentaRaw]) -> int:
    """Propaga el encabezado contable a filas de balances clasificados.

    Sólo completa orígenes desconocidos y nunca cambia una columna observada.
    Los encabezados y totales sirven como límites, pero no se convierten en
    cuentas de detalle. Retorna el número de filas enriquecidas.
    """
    seccion: Optional[OrigenColumna] = None
    secciones_paralelas = False
    posiciones_paralelas: dict[int, int] = {}
    detalles_por_linea = Counter(
        cuenta.linea for cuenta in cuentas
        if cuenta.monto is not None and not cuenta.es_total
    )
    anotadas = 0
    for cuenta in cuentas:
        nombre = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre)).strip(" :")
        if re.search(
            r"^(?:estado(?:s)?\s+de\s+)?(?:flujo(?:s)?\s+de\s+efectivo|"
            r"cambios?\s+en\s+el\s+patrimonio|resultado(?:s)?(?:\s+integrales?)?|"
            r"profit\s+and\s+loss(?:\s+account)?)$",
            nombre, re.I,
        ):
            seccion = None
            secciones_paralelas = False
            continue
        if re.match(
            r"^total(?:es)?\s+(?:de\s+)?(?:"
            r"pasivos?\s+y\s+patrimonio(?:\s+neto)?|"
            r"patrimonio\s+y\s+pasivos?|equity\s+and\s+liabilities)$",
            nombre, re.I,
        ):
            seccion = None
            secciones_paralelas = False
            continue
        normalized_english = nombre.replace("-", " ")
        if (
            re.search(r"\bassets?\b", normalized_english, re.I)
            and re.search(r"\b(?:equity|liabilities)\b", normalized_english, re.I)
            and not cuenta.es_total
        ):
            seccion = None
            secciones_paralelas = True
            continue
        encabezado = nombre
        if cuenta.es_total:
            encabezado = re.sub(r"^total(?:es)?\s+", "", nombre, flags=re.I)
        nueva_seccion = None
        for patron, origen in _SECTION_HEADING_PATTERNS:
            if patron.fullmatch(encabezado):
                nueva_seccion = origen
                break
        if nueva_seccion is not None:
            seccion = nueva_seccion
            secciones_paralelas = False
            continue
        if (
            secciones_paralelas
            and detalles_por_linea[cuenta.linea] == 2
            and cuenta.monto is not None
            and not cuenta.es_total
            and (
                cuenta.origen_columna == OrigenColumna.DESCONOCIDO
                or not cuenta.montos_columnas
            )
        ):
            posicion = posiciones_paralelas.get(cuenta.linea, 0)
            origen = (
                OrigenColumna.ACTIVO if posicion == 0 else OrigenColumna.PASIVO
            )
            posiciones_paralelas[cuenta.linea] = posicion + 1
            if cuenta.origen_columna != origen:
                cuenta.origen_columna = origen
                anotadas += 1
            continue
        if (
            seccion is not None
            and cuenta.monto is not None
            and not cuenta.es_total
            and (
                cuenta.origen_columna == OrigenColumna.DESCONOCIDO
                or not cuenta.montos_columnas
            )
        ):
            if cuenta.origen_columna != seccion:
                cuenta.origen_columna = seccion
                anotadas += 1
    return anotadas


def fusionar_cuentas_partidas(cuentas: list[CuentaRaw]) -> tuple[list[CuentaRaw], int]:
    """Une una cuenta partida entre la glosa con código y su fila de importes.

    Algunos extractores PDF entregan dos fragmentos de una misma fila física:
    primero ``código + glosa`` y luego la continuación de la glosa junto a las
    ocho columnas. Ambos conservan el mismo número de línea. Sin esta unión, la
    certificación excluye los importes del fragmento sin código y reporta un
    descuadre aunque el documento haya sido leído completo.

    La regla es deliberadamente estricta: mismo número de línea, primer
    fragmento con código pero sin importes y segundo sin código pero con las
    columnas monetarias observadas. No fusiona totales ni filas adyacentes que
    sólo coincidan por proximidad.
    """
    fusionadas: list[CuentaRaw] = []
    cantidad = 0
    indice = 0
    while indice < len(cuentas):
        actual = cuentas[indice]
        siguiente = cuentas[indice + 1] if indice + 1 < len(cuentas) else None
        if (
            siguiente is not None
            and actual.linea == siguiente.linea
            and bool(actual.codigo)
            and not actual.montos_columnas
            and not actual.es_total
            and not siguiente.codigo
            and bool(siguiente.montos_columnas)
        ):
            siguiente.codigo = actual.codigo
            siguiente.nombre = re.sub(
                r"\s+", " ", f"{actual.nombre} {siguiente.nombre}",
            ).strip()
            # Palabras como "PERDIDA" o "GANANCIA" pueden activar el patrón
            # de total en el fragmento aislado. Al quedar unidas a una cuenta
            # codificada de la misma línea, son parte de la glosa de detalle.
            siguiente.es_total = False
            siguiente.confianza_extraccion = min(
                actual.confianza_extraccion,
                siguiente.confianza_extraccion,
            )
            fusionadas.append(siguiente)
            cantidad += 1
            indice += 2
            continue
        fusionadas.append(actual)
        indice += 1
    return fusionadas, cantidad


# ─────────────────────────────────────────────────────────────────────────────
# PARSER DE LÍNEAS DE TEXTO → CUENTAS
# ─────────────────────────────────────────────────────────────────────────────

PATRONES_CODIGO_LINEA = {
    FormatoCodigo.GUION:    re.compile(r'^(\d+(?:-\d+){2,})\s+(.+)'),
    FormatoCodigo.PUNTO:    re.compile(r'^(\d+(?:\.\d+){2,})\s+(.+)'),
    FormatoCodigo.COMPACTO: re.compile(r'^(\d{5,10})\s+(.+)'),
}

# PQ-2 (FG1/FG2) — recuperación de códigos perdidos en documentos SIN_CODIGO.
# Se prueban SOLO después de los tres patrones estándar y SOLO en la rama de
# auto-detección por línea, por lo que no alteran la extracción de documentos
# con formato GUION/PUNTO/COMPACTO detectado. Reutilizan el resto del flujo
# (montos y columnas) aguas abajo en parsear_linea.
#
# FG1 — código con UN solo separador (guión o punto): 4.021201, 201.1205,
# 1101-51. OCR puede fusionar varios grupos a cualquiera de sus lados.
_PATRON_AUX_UNISEP = re.compile(r'^(\d{1,6}[-.]\d{2,8})\s+([A-Za-zÁÉÍÓÚÑáéíóúñ].+)')
# FG2 — código compacto concatenado al nombre sin espacio: 11090BANCO, 10423CTA.
#    El lookahead `(?=[A-Z...])` parte en la frontera dígito → letra y exige que
#    el código sea de 4 a 6 dígitos seguidos inmediatamente por una letra.
_PATRON_AUX_CONCATENADO = re.compile(r'^(\d{4,6})(?=[A-ZÁÉÍÓÚÑ])(.+)')
PATRONES_CODIGO_AUXILIARES = (_PATRON_AUX_UNISEP, _PATRON_AUX_CONCATENADO)
_PATRON_CODIGO_EMBEBIDO_OCR = re.compile(
    r"^[^\d\n]{1,3}(\d{1,2}(?:[.,/:]\d{1,2}){2,4})\s*[-–—−]?\s*(.+)$"
)

PATRON_MONTOS = re.compile(r'(-?\(?[\d.,]{1,18}\)?)')
_OCR_CERO = re.compile(r'^[oO]$')
_OCR_CERO_EN_CELDA = re.compile(r'^(?:[oO]|[\]\[»«|!lI]{1,3}|[sS][eE][oO])$')


def _es_token_cero_ocr_en_celda(token: str) -> bool:
    """Reconoce únicamente ruido típico de un cero en una celda numérica."""
    return bool(_OCR_CERO_EN_CELDA.fullmatch(token.strip()))


def normalizar_token_ocr(token: str) -> str:
    if _OCR_CERO.match(token):
        return '0'
    # Los dos puntos aparecen como sustituto del punto de miles en escaneos
    # tenues (p. ej. ``3.732:989.407``). Se limita al contexto entre dígitos.
    return re.sub(r"(?<=\d):(?=\d)", ".", token)

PATRON_TOTAL = re.compile(
    r'^(?:total(?:es)?|sub-?total(?:es)?|sumas?(?: iguales)?)\b|'
    r'^(?:resultado(?: del ejercicio| [\x22\x27]?(?:positivo|negativo))?|utilidad(?: neta| del ejercicio)?|'
    r'perdida(?: o ganancia| neta| neto| del ejercicio)?)$',
    re.IGNORECASE
)

# ── Filtro de líneas basura (FASE 24B.2) ─────────────────────────────────
# Cada patrón matchea la línea COMPLETA para no filtrar substrings dentro
# de nombres de cuentas contables.

GARBAGE_PATTERNS: list[re.Pattern] = [
    # URLs
    re.compile(r'^https?://\S+$', re.I),
    re.compile(r'^www\.\S+\.\S+$', re.I),
    # Emails
    re.compile(r'^\S+@\S+\.\S+$'),
    # Teléfonos chilenos (+56 9 XXXX XXXX / (2) XXXX XXXX)
    re.compile(r'^\+56[\s-]?\d[\s\d-]{7,}\d$'),
    re.compile(r'^\(\d{1,4}\)[\s-]?\d[\s\d-]{6,}\d$'),
    # RUTs sueltos
    re.compile(r'^\s*\d{1,2}\.\d{3}\.\d{3}[-][0-9kK]\s*$', re.I),
    # Indicadores de página / folio
    re.compile(r'^\s*(?:P[aá]gina|P[aá]g|Pag|Folio|Hoja|N°|No\.?)\s*\d+(?:\s*(?:de|/)\s*\d+)?\s*$', re.I),
    # Etiquetas administrativas de encabezado (RUT, Domicilio, Teléfono, etc.)
    re.compile(r'^\s*(?:RUT|Domicilio|Comuna|Ciudad|Direcci[oó]n|Tel[eé]fono|Email?|Fax)\s*:.*$', re.I),
    re.compile(r'^\s*Fecha\s*(?:de\s*)?(?:emi[só]i[oó]n|creaci[oó]n)\s*:.*$', re.I),
    # Metadatos frecuentes que terminan en un número y parecen una cuenta.
    re.compile(r'^\s*Nivel\s+\d+(?:[.,]\d+)?\s*$', re.I),
    re.compile(r'^\s*Desde\s+\w+\s+(?:a|hasta)\s+\w+\s+\d{4}\s*$', re.I),
    re.compile(r'^\s*(?:19|20)\d{2}\s+(?:19|20)\d{2}\s*$'),
    # Notas al pie
    re.compile(r'^\s*(?:Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?|Ver\s+Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?)\s*$', re.I),
    re.compile(r'^\s*Art[ií]culo(?:\s+\d+)?\s+C[oó]digo\s+Tributario\b.*$', re.I),
    re.compile(r'^\s*con\s+los\s+antecedentes\s+aportados\s+por\s+el\s+Contribuyente\s*$', re.I),
    # Firmas / cargos
    re.compile(r'^\s*(?:Firma|Representante|Contador|Auditor|Revisor|Preparado)\b.*$', re.I),
    # Firmas de auditoría / consultoría
    re.compile(r'^\s*(?:Deloitte|Ernst\s*Young|PwC|Pricewaterhouse(?:Coopers)?|KPMG|BDO|Grant\s*Thornton|Baker\s*Tilly|Mazars)\b.*$', re.I),
    # Líneas decorativas / separadores
    re.compile(r'^[-=*_]{4,}$'),
    re.compile(r'^\s*-\s*\d+\s*-\s*$'),
    # Fechas sueltas (dd de mes de aaaa o dd/mm/aaaa)
    re.compile(r'^\s*\d{1,2}\s*de\s+\w+\s+de\s+\d{4}\s*$', re.I),
    re.compile(r'^\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$'),
]


def _es_linea_basura(linea: str) -> bool:
    """Retorna True si la línea completa es basura (URL, teléfono, encabezado,
    pie de página, dirección, etc.). No filtra cuentas contables porque los
    patrones matchean la totalidad de la línea, no substrings.
    """
    for patron in GARBAGE_PATTERNS:
        if patron.match(linea):
            return True
    return False

# OCR confunde '.' y ',' dentro de códigos de cuenta tipo X.XX.XX.XX,
# produciendo cosas como "1.1.01,01" o "1,1,08,05". Se detecta un prefijo
# de 3-5 grupos cortos de dígitos separados por '.' o ',' al inicio de la
# línea y se normaliza a '.' antes de cualquier otro procesamiento.
PATRON_CODIGO_OCR = re.compile(r'^(\d{1,2}[.,/:]){2,4}\d{1,2}(?=\s)')


def normalizar_codigo_ocr(linea: str) -> str:
    # Separador tipográfico código/glosa, no un signo del importe.
    linea = re.sub(
        r"^(\d{5,10})\s*[·•]\s*(?=[A-Za-zÁÉÍÓÚÑáéíóúñ])", r"\1 ", linea,
    )
    linea = re.sub(r"(?<=\d)[.,/:]{2,}(?=\d)", ".", linea)
    m = PATRON_CODIGO_OCR.match(linea)
    if not m:
        return linea
    codigo_normalizado = (
        m.group(0).replace(',', '.').replace('/', '.').replace(':', '.')
    )
    return codigo_normalizado + linea[m.end():]


_MONTO_AGRUPADO_OCR = re.compile(r"\d{1,3}(?:[.,]\d{3})+")


def _separar_token_montos_concatenados(token: str) -> str:
    """Separa dos importes agrupados que OCR pegó sin espacio intermedio."""
    for indice in range(1, len(token)):
        izquierda, derecha = token[:indice], token[indice:]
        if (
            _MONTO_AGRUPADO_OCR.fullmatch(izquierda)
            and _MONTO_AGRUPADO_OCR.fullmatch(derecha)
        ):
            return f"{izquierda} {derecha}"
    return token


def normalizar_linea_ocr_tabla(linea: str) -> str:
    """Limpia bordes de tabla y separadores confundidos por OCR.

    No reescribe signos contables ni elimina paréntesis; sólo retira caracteres
    de grilla y normaliza comas intercaladas en montos chilenos.
    """
    limpia = re.sub(r"[\[\]|¡]", " ", linea)
    limpia = " ".join(
        _separar_token_montos_concatenados(token)
        for token in limpia.split()
    )
    limpia = re.sub(r"(?<=\d),(?=\d)", ".", limpia)
    limpia = re.sub(r"(?<=\d):(?=\d)", ".", limpia)
    return re.sub(r"\s+", " ", limpia).strip()


def normalizar_montos_fragmentados(linea: str) -> str:
    """Une el primer dígito separado de un importe con miles agrupados.

    Algunos PDF posicionan visualmente el primer dígito en otro fragmento de
    texto (``2 2.029.324,87``). La regla exige al menos dos grupos de miles para
    no unir códigos, años ni columnas contiguas de montos pequeños.
    """
    return re.sub(
        r"(?<![\d.,])(\d)\s+(\d{1,2}(?:[.,]\d{3}){2,}(?:,\d{2})?)",
        r"\1\2",
        linea,
    )


def _metricas_texto_ocr_balance(texto: str) -> dict[str, int]:
    """Mide estructura contable sin depender de una empresa o plantilla."""
    encabezados = 0
    filas_numericas = 0
    filas_ocho_columnas = 0
    controles = 0
    for linea_cruda in texto.splitlines():
        linea = normalizar_linea_ocr_tabla(linea_cruda)
        if not linea:
            continue
        normalizada = _sin_acentos(linea).upper()
        encabezados += sum(
            1 for token in (
                "DEBIT", "CREDIT", "DEBE", "HABER", "DEUDOR", "ACREEDOR",
                "ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA", "GANANCIA",
            )
            if token in normalizada
        )
        montos = [
            token for token in linea.split()
            if PATRON_MONTOS.fullmatch(normalizar_token_ocr(token).replace("$", ""))
        ]
        if len(montos) >= 2:
            filas_numericas += 1
        if len(montos) >= 8:
            filas_ocho_columnas += 1
        if re.match(r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", linea, re.I):
            controles += 1
    return {
        "encabezados": encabezados,
        "filas_numericas": filas_numericas,
        "filas_ocho_columnas": filas_ocho_columnas,
        "controles": controles,
    }


def _puntuar_texto_ocr_balance(texto: str) -> int:
    metricas = _metricas_texto_ocr_balance(texto)
    return (
        metricas["encabezados"]
        + 2 * metricas["filas_numericas"]
        + 5 * metricas["filas_ocho_columnas"]
        + 8 * metricas["controles"]
    )


def _ocr_requiere_alternativa(texto: str, es_ultima_pagina: bool) -> bool:
    """Evita un segundo Tesseract salvo que pueda aportar evidencia nueva."""
    metricas = _metricas_texto_ocr_balance(texto)
    if not texto.strip() or metricas["filas_numericas"] == 0:
        return True
    if es_ultima_pagina and metricas["controles"] == 0:
        return True
    if _tabla_ocr_necesita_recuperacion(texto.splitlines()):
        return True
    return metricas["encabezados"] < 2 and metricas["filas_ocho_columnas"] == 0


def _combinar_candidatos_ocr(texto_base: str, texto_alternativo: str) -> tuple[str, str]:
    """Selecciona o fusiona lecturas OCR preservando filas y controles."""
    if not texto_alternativo.strip():
        return texto_base, "principal"
    score_base = _puntuar_texto_ocr_balance(texto_base)
    score_alternativo = _puntuar_texto_ocr_balance(texto_alternativo)
    metricas_base = _metricas_texto_ocr_balance(texto_base)
    metricas_alt = _metricas_texto_ocr_balance(texto_alternativo)
    if (
        score_alternativo >= score_base + 10
        and metricas_alt["filas_numericas"] >= metricas_base["filas_numericas"]
    ):
        return texto_alternativo, "tabla"

    controles_alt = []
    for linea in texto_alternativo.splitlines():
        limpia = normalizar_linea_ocr_tabla(linea)
        if re.match(r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", limpia, re.I):
            controles_alt.append(linea)
    if not controles_alt:
        return texto_base, "principal"
    base_sin_controles = []
    for linea in texto_base.splitlines():
        limpia = normalizar_linea_ocr_tabla(linea)
        if not re.match(
            r"^(sumas?|subtotales?|resultado|utilidad|totales?)\b", limpia, re.I,
        ):
            base_sin_controles.append(linea)
    return "\n".join(base_sin_controles + controles_alt), "fusion"


def parsear_linea(
    linea: str,
    numero_linea: int,
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float = 1.0,
    column_order: Optional[list[OrigenColumna]] = None,
    periodo_comparativo: bool = False,
    years: Optional[list[str]] = None,
    currencies: Optional[list[str]] = None,
) -> Optional[CuentaRaw]:
    linea = linea.strip()
    if len(linea) < 4:
        return None

    if _es_linea_basura(linea):
        return None

    codigo = None
    resto = linea
    linea_para_total = re.sub(r"^[^\w]+", "", linea).strip()
    if confianza_base < 1.0:
        # En impresos tenues Tesseract confunde con frecuencia la T inicial y
        # lee ``TOTAL`` como ``FORAL``. Sólo se normaliza al evaluar controles
        # OCR; una cuenta nativa conserva siempre su nombre literal.
        linea_para_total = re.sub(
            r"^foral\b", "total", linea_para_total, flags=re.I,
        )

    # Los totales impresos no llevan código. Evita interpretar su primer monto
    # (p. ej. 72.911.536.017) como un código de formato PUNTO.
    if PATRON_TOTAL.match(linea_para_total):
        resto = linea_para_total
    elif formato_codigo != FormatoCodigo.SIN_CODIGO:
        patron = PATRONES_CODIGO_LINEA[formato_codigo]
        m = patron.match(linea)
        if m:
            codigo = m.group(1)
            resto = m.group(2)
        else:
            # OCR puede perder todos los separadores de una cuenta puntual
            # (1.01.01.01 -> 1010101). Recuperar el formato alternativo evita
            # que el código quede incorporado al nombre y bloquee el matching.
            for fmt, patron_alternativo in PATRONES_CODIGO_LINEA.items():
                if fmt == formato_codigo:
                    continue
                m = patron_alternativo.match(linea)
                if m:
                    codigo = m.group(1)
                    resto = m.group(2)
                    break
            if codigo is None:
                for patron_auxiliar in PATRONES_CODIGO_AUXILIARES:
                    m = patron_auxiliar.match(linea)
                    if m:
                        codigo = m.group(1)
                        resto = m.group(2)
                        break
    else:
        for fmt in (FormatoCodigo.PUNTO, FormatoCodigo.GUION, FormatoCodigo.COMPACTO):
            m = PATRONES_CODIGO_LINEA[fmt].match(linea)
            if m:
                codigo = m.group(1)
                resto = m.group(2)
                break
        # PQ-2 (FG1/FG2): códigos con un solo separador o compactos concatenados
        # al nombre. Solo si ninguno de los patrones estándar coincidió (no
        # altera documentos con formato ya detectado).
        if codigo is None:
            for patron in PATRONES_CODIGO_AUXILIARES:
                m = patron.match(linea)
                if m:
                    codigo = m.group(1)
                    resto = m.group(2)
                    break

    if codigo is None and confianza_base < 1.0:
        embedded = _PATRON_CODIGO_EMBEBIDO_OCR.match(resto)
        if embedded:
            codigo = re.sub(r"[.,/:]", ".", embedded.group(1))
            resto = embedded.group(2)

    tokens = resto.split()
    descartados_finales = 0
    while tokens and descartados_finales < 2 and \
            normalizar_token_ocr(tokens[-1]) != '0' and \
            not re.search(r'\d', tokens[-1]) and len(tokens[-1]) <= 2:
        tokens.pop()
        descartados_finales += 1

    montos_tokens = []
    i = len(tokens) - 1
    while i >= 0 and len(montos_tokens) < 8:
        tok_norm = normalizar_token_ocr(tokens[i])
        if tok_norm == '-':
            montos_tokens.insert(0, '0')
            i -= 1
        elif PATRON_MONTOS.fullmatch(tok_norm.replace('$', '')):
            montos_tokens.insert(0, tok_norm.replace('$', ''))
            i -= 1
        elif montos_tokens and len(tok_norm) <= 2 and not re.search(r'\d', tok_norm):
            # En tablas de ocho columnas Tesseract ocasionalmente convierte
            # un cero intermedio en ruido breve (p. ej. ``ly``). Una vez
            # iniciada la cola numérica se conserva la posición como cero.
            montos_tokens.insert(0, '0')
            i -= 1
        else:
            break

    nombre_tokens = tokens[:i + 1]
    # La raya visual entre codigo y descripcion no forma parte de la cuenta.
    nombre = ' '.join(nombre_tokens).strip(' .-–—−')

    if not nombre or len(nombre) < 3:
        return None

    nombre_para_total = re.sub(r"^[^\w]+", "", nombre).strip()
    es_total = codigo is None and bool(PATRON_TOTAL.match(nombre_para_total))

    # Determinar orden de columnas: si ENABLE_DYNAMIC_LAYOUT está activo
    # y se proporcionó un column_order con confianza suficiente, usarlo.
    # Fallback: heurística actual (últimas 4 columnas = Activo/Pasivo/Pérdida/Ganancia).
    if column_order and ENABLE_DYNAMIC_LAYOUT:
        columnas = column_order
    else:
        columnas = [OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
                    OrigenColumna.PERDIDA, OrigenColumna.GANANCIA]

    n_col = len(columnas)
    monto_principal = None
    origen = OrigenColumna.DESCONOCIDO
    montos_periodos: dict[str, float] = {}

    # Dynamic year/currency mapping
    if (years or currencies) and montos_tokens:
        n_vals = len(montos_tokens)
        active_years = years if years else []
        active_currencies = currencies if currencies else []

        # Determine if we map primarily by currencies or by years
        if len(active_currencies) >= 2:
            # Map columns to currencies
            for idx, curr in enumerate(active_currencies[:n_vals]):
                val = parsear_monto(montos_tokens[idx], separador_miles)
                if val is not None:
                    val_f = float(val)
                    montos_periodos[curr] = val_f
                    # Also map with year if we have a year
                    if len(active_years) >= 1:
                        montos_periodos[f"{active_years[0]}_{curr}"] = val_f
            main_curr = "CLP" if "CLP" in montos_periodos else active_currencies[0]
            monto_principal = montos_periodos.get(main_curr)
        else:
            # Map columns to years
            for idx, yr in enumerate(active_years[:n_vals]):
                val = parsear_monto(montos_tokens[idx], separador_miles)
                if val is not None:
                    val_f = float(val)
                    montos_periodos[yr] = val_f
                    # If we have a single currency (e.g. USD), also map it
                    if len(active_currencies) == 1:
                        curr = active_currencies[0]
                        montos_periodos[f"{yr}_{curr}"] = val_f
                        montos_periodos[curr] = val_f

            if "actual" not in montos_periodos and len(active_years) >= 1:
                montos_periodos["actual"] = montos_periodos.get(active_years[0], 0.0)
            if "anterior" not in montos_periodos and len(active_years) >= 2:
                montos_periodos["anterior"] = montos_periodos.get(active_years[1], 0.0)
            monto_principal = montos_periodos.get("actual")

            # If single currency and we have actual/anterior, populate them too
            if len(active_currencies) == 1:
                curr = active_currencies[0]
                if "actual" in montos_periodos:
                    montos_periodos[f"actual_{curr}"] = montos_periodos["actual"]
                if "anterior" in montos_periodos:
                    montos_periodos[f"anterior_{curr}"] = montos_periodos["anterior"]
                if monto_principal is not None:
                    montos_periodos[curr] = monto_principal

    if periodo_comparativo and len(montos_tokens) >= 3 and re.fullmatch(
        r"\d{1,2}(?:\.\d{1,2}){2,}", montos_tokens[-1],
    ):
        # Referencia de nota (6.1.2, 12.3.1), no un tercer período monetario.
        montos_tokens.pop()

    if not montos_periodos and periodo_comparativo and len(montos_tokens) >= 2:
        actual_token, anterior_token = montos_tokens[-2:]
        actual = float(parsear_monto(actual_token, separador_miles) or 0.0)
        anterior = float(parsear_monto(anterior_token, separador_miles) or 0.0)
        montos_periodos = {"actual": actual, "anterior": anterior}
        monto_principal = actual

    if montos_tokens and not montos_periodos:
        n = len(montos_tokens)
        k = min(n_col, n)
        cola = montos_tokens[-k:]
        etiquetas = columnas[-k:]

        for tok, et in zip(cola, etiquetas):
            val = parsear_monto(tok, separador_miles)
            if val is not None and val != 0:
                monto_principal = val
                origen = et
                break

        if monto_principal is None:
            monto_principal = parsear_monto(cola[0], separador_miles)
            origen = etiquetas[0]

    montos_columnas: dict[str, float] = {}
    columnas_derivadas: list[str] = []
    if len(montos_tokens) == len(RAW_MONETARY_COLUMNS):
        for column, token in zip(RAW_MONETARY_COLUMNS, montos_tokens):
            montos_columnas[column] = float(parsear_monto(token, separador_miles) or 0.0)
        if confianza_base < 1.0:
            def error_identidades(values: dict[str, float]) -> float:
                return abs(
                    (values["debitos"] - values["creditos"])
                    - (values["saldo_deudor"] - values["saldo_acreedor"])
                ) + abs(
                    values["saldo_deudor"] + values["saldo_acreedor"]
                    - values["activo"] - values["pasivo"]
                    - values["perdida"] - values["ganancia"]
                )

            # En OCR de tablas, un cero aislado se confunde con mucha
            # frecuencia con 2, 3, 5, 6 o 9. Sólo se corrige cuando eliminar
            # ese dígito mejora estrictamente las dos identidades contables;
            # nunca se aplica a extracción nativa ni a importes mayores.
            for column in RAW_MONETARY_COLUMNS:
                if not 0 < abs(montos_columnas[column]) <= 10:
                    continue
                error_antes = error_identidades(montos_columnas)
                candidato = dict(montos_columnas)
                candidato[column] = 0.0
                if error_identidades(candidato) < error_antes:
                    montos_columnas[column] = 0.0
                    columnas_derivadas.append(column)

            # Tesseract también puede depositar una marca marginal o parte del
            # RUT en una segunda columna de clasificación (por ejemplo 7.669
            # en Ganancias cuando el saldo completo ya está en Pérdidas). Se
            # elimina sólo una segunda clasificación pequeña cuando al hacerlo
            # ambas identidades quedan exactas. La cuenta de importe pequeño
            # legítimo se conserva porque quitar su única clasificación
            # empeoraría, en vez de mejorar, la identidad saldo-clasificación.
            debtor_total = abs(montos_columnas["saldo_deudor"]) + abs(
                montos_columnas["saldo_acreedor"]
            )
            classification_noise_limit = max(10_000.0, debtor_total * 0.01)
            nonzero_classifications = [
                column for column in ("activo", "pasivo", "perdida", "ganancia")
                if montos_columnas[column] != 0
            ]
            if len(nonzero_classifications) >= 2:
                for column in nonzero_classifications:
                    value = montos_columnas[column]
                    if abs(value) > classification_noise_limit:
                        continue
                    error_antes = error_identidades(montos_columnas)
                    candidato = dict(montos_columnas)
                    candidato[column] = 0.0
                    error_despues = error_identidades(candidato)
                    if error_despues <= 10 and error_despues < error_antes:
                        montos_columnas[column] = 0.0
                        columnas_derivadas.append(column)
                        break

            # Si movimiento y clasificación repiten exactamente el mismo
            # importe unilateral, ambos son evidencia independiente frente a
            # un saldo OCR discrepante. Se corrige sólo esa tercera copia y
            # únicamente en documentos OCR.
            classification_total = sum(
                montos_columnas[column]
                for column in ("activo", "pasivo", "perdida", "ganancia")
            )
            if (
                montos_columnas["creditos"] == 0
                and montos_columnas["saldo_acreedor"] == 0
                and montos_columnas["debitos"] > 0
                and montos_columnas["debitos"] == classification_total
                and montos_columnas["saldo_deudor"] != montos_columnas["debitos"]
            ):
                montos_columnas["saldo_deudor"] = montos_columnas["debitos"]
                columnas_derivadas.append("saldo_deudor")
            elif (
                montos_columnas["debitos"] == 0
                and montos_columnas["saldo_deudor"] == 0
                and montos_columnas["creditos"] > 0
                and montos_columnas["creditos"] == classification_total
                and montos_columnas["saldo_acreedor"] != montos_columnas["creditos"]
            ):
                montos_columnas["saldo_acreedor"] = montos_columnas["creditos"]
                columnas_derivadas.append("saldo_acreedor")

            # Cuando OCR pierde la repetición del saldo en las columnas de
            # clasificación, se recupera únicamente si hay un saldo unilateral
            # y el primer dígito del código entrega una naturaleza coherente.
            # El signo del saldo conserva las contra-cuentas: un código de
            # activo con saldo acreedor se observa en Pasivo, no en Activo.
            classified_sum = sum(
                montos_columnas[column]
                for column in ("activo", "pasivo", "perdida", "ganancia")
            )
            debtor_value = montos_columnas["saldo_deudor"]
            creditor_value = montos_columnas["saldo_acreedor"]
            code_prefix = re.sub(r"\D", "", codigo or "")[:1]
            if (
                classified_sum == 0
                and bool(code_prefix)
                and (debtor_value == 0) != (creditor_value == 0)
            ):
                if code_prefix in {"1", "2"}:
                    target = "activo" if debtor_value else "pasivo"
                elif code_prefix in {"3", "4"}:
                    target = "perdida" if debtor_value else "ganancia"
                else:
                    target = ""
                if target:
                    montos_columnas[target] = debtor_value or creditor_value
                    columnas_derivadas.append(target)
        debit = montos_columnas["debitos"]
        credit = montos_columnas["creditos"]
        debtor = montos_columnas["saldo_deudor"]
        creditor = montos_columnas["saldo_acreedor"]
        classified = (
            montos_columnas["activo"] + montos_columnas["pasivo"]
            + montos_columnas["perdida"] + montos_columnas["ganancia"]
        )
        balance = debtor - creditor
        classification_consistent = abs(debtor + creditor - classified) <= 10
        movement_consistent = abs(debit - credit - balance) <= 10
        movement_is_implausible = abs(debit - credit) > max(
            abs(balance) * 10, abs(balance) + 1000,
        )
        if classification_consistent and not movement_consistent:
            phantom_limit = max(10_000.0, max(abs(debit), abs(credit)) * 0.01)
            if (
                confianza_base < 1.0 and credit == 0 and creditor == 0
                and debtor > 0 and debit != debtor
            ):
                # Saldo deudor y clasificación repiten el mismo importe; si
                # Crédito es cero, esa evidencia redundante permite corregir
                # con seguridad un dígito omitido en Débito.
                montos_columnas["debitos"] = debtor
                columnas_derivadas.append("debitos")
            elif (
                confianza_base < 1.0 and debit == 0 and debtor == 0
                and creditor > 0 and credit != creditor
            ):
                montos_columnas["creditos"] = creditor
                columnas_derivadas.append("creditos")
            elif (
                confianza_base < 1.0 and balance == 0
                and debit > 0 and credit > 0 and debit != credit
                and (
                    str(int(round(max(debit, credit)))).endswith(
                        str(int(round(min(debit, credit))))
                    )
                    and max(debit, credit) >= min(debit, credit) * 10
                )
            ):
                # Un trazo de la columna o del código puede anteponerse al
                # primer movimiento (1.866.316 -> 121.866.316). Con saldo cero
                # Debe y Haber deben ser iguales; el sufijo completo aporta la
                # corrección sin adivinar dígitos internos.
                if debit > credit:
                    montos_columnas["debitos"] = credit
                    columnas_derivadas.append("debitos")
                else:
                    montos_columnas["creditos"] = debit
                    columnas_derivadas.append("creditos")
            elif debit == 0 and credit == 0 and debtor != 0 and creditor == 0:
                montos_columnas["debitos"] = debtor
                columnas_derivadas.append("debitos")
            elif debit == 0 and credit == 0 and creditor != 0 and debtor == 0:
                montos_columnas["creditos"] = creditor
                columnas_derivadas.append("creditos")
            elif (
                debtor == 0 and abs(credit - creditor) <= 10
                and 0 < abs(debit) <= phantom_limit
            ):
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.append("debitos")
            elif (
                creditor == 0 and abs(debit - debtor) <= 10
                and 0 < abs(credit) <= phantom_limit
            ):
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.append("creditos")
            elif movement_is_implausible and credit == 0 and balance >= 0:
                montos_columnas["debitos"] = balance
                columnas_derivadas.append("debitos")
            elif movement_is_implausible and debit == 0 and balance < 0:
                montos_columnas["creditos"] = -balance
                columnas_derivadas.append("creditos")
            elif (
                debit == 0 and creditor == 0
                and credit > 0 and abs(credit - debtor) <= 10
            ):
                montos_columnas["debitos"] = credit
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                credit == 0 and debtor == 0
                and debit > 0 and abs(debit - creditor) <= 10
            ):
                montos_columnas["creditos"] = debit
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                debit == 0 and creditor == 0 and debtor > 0
                and abs(credit - debtor * 10) <= 10
            ):
                # OCR puede anexar el cero de la celda Crédito al monto de
                # Débito (936.090 + 0 -> 9.360.900) y dejar la primera celda
                # vacía. El saldo deudor independiente permite repararlo.
                montos_columnas["debitos"] = debtor
                montos_columnas["creditos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif (
                credit == 0 and debtor == 0 and creditor > 0
                and abs(debit - creditor * 10) <= 10
            ):
                montos_columnas["creditos"] = creditor
                montos_columnas["debitos"] = 0.0
                columnas_derivadas.extend(["debitos", "creditos"])
            elif movement_is_implausible:
                expected_debit = credit + balance
                expected_credit = debit - balance
                if (
                    expected_debit >= 0
                    and abs(debit) > max(1_000_000_000, abs(expected_debit) * 100)
                ):
                    montos_columnas["debitos"] = expected_debit
                    columnas_derivadas.append("debitos")
                elif (
                    expected_credit >= 0
                    and abs(credit) > max(1_000_000_000, abs(expected_credit) * 100)
                ):
                    montos_columnas["creditos"] = expected_credit
                    columnas_derivadas.append("creditos")
        if es_total and debit == credit and debit != 0:
            if debtor == 0 and creditor != 0:
                montos_columnas["saldo_deudor"] = creditor
                columnas_derivadas.append("saldo_deudor")
            elif creditor == 0 and debtor != 0:
                montos_columnas["saldo_acreedor"] = debtor
                columnas_derivadas.append("saldo_acreedor")
        # Las ocho columnas son evidencia más fuerte que años o monedas
        # detectados en la cabecera. Si exactamente una columna de
        # clasificación contiene saldo, esa columna define tanto el importe
        # homologable como su origen físico. Esto evita que una fecha del
        # documento deje la cuenta como DESCONOCIDO y conserve por error el
        # débito o crédito acumulado como monto principal.
        origin_by_column = {
            "activo": OrigenColumna.ACTIVO,
            "pasivo": OrigenColumna.PASIVO,
            "perdida": OrigenColumna.PERDIDA,
            "ganancia": OrigenColumna.GANANCIA,
        }
        classified_values = [
            (column, montos_columnas[column])
            for column in origin_by_column
            if montos_columnas[column] != 0
        ]
        if len(classified_values) == 1:
            column, value = classified_values[0]
            origen = origin_by_column[column]
            monto_principal = value
    return CuentaRaw(
        linea=numero_linea,
        codigo=codigo,
        nombre=nombre,
        monto=monto_principal,
        origen_columna=origen,
        es_total=es_total,
        confianza_extraccion=confianza_base,
        montos_columnas=montos_columnas,
        montos_periodos=montos_periodos,
        columnas_derivadas=columnas_derivadas,
    )


def _error_identidades_cuenta(cuenta: CuentaRaw) -> float:
    values = cuenta.montos_columnas
    if set(values) != set(RAW_MONETARY_COLUMNS):
        return float("inf")
    return abs(
        (values["debitos"] - values["creditos"])
        - (values["saldo_deudor"] - values["saldo_acreedor"])
    ) + abs(
        values["saldo_deudor"] + values["saldo_acreedor"]
        - values["activo"] - values["pasivo"]
        - values["perdida"] - values["ganancia"]
    )


def _cuenta_desde_candidato_ocr(
    linea: str, numero_linea: int, exigir_consistencia: bool = True,
) -> Optional[CuentaRaw]:
    """Obtiene la variante consistente de una fila OCR con 6 a 8 importes."""
    normalized = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(linea))
    candidates: list[CuentaRaw] = []
    for suffix in ("", " 0", " 0 0"):
        candidate = parsear_linea(
            normalized + suffix,
            numero_linea,
            FormatoCodigo.SIN_CODIGO,
            ".",
            0.75,
        )
        if (
            candidate is not None
            and candidate.codigo
            and candidate.montos_columnas
            and (
                not exigir_consistencia
                or _error_identidades_cuenta(candidate) <= 10
            )
        ):
            candidates.append(candidate)
    if not candidates:
        return None
    # Prefiere la variante que conserva más evidencia monetaria. Los sufijos
    # sólo agregan ceros; nunca inventan un importe distinto de cero.
    return min(
        candidates,
        key=lambda account: (
            _error_identidades_cuenta(account),
            -sum(abs(value) for value in account.montos_columnas.values()),
        ),
    )


def _codigo_contable_canonico(codigo: Optional[str]) -> str:
    return re.sub(r"\D", "", codigo or "")


def _nombres_ocr_compatibles(left: str, right: str) -> bool:
    def tokens(value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", _sin_acentos(value).lower())
            if len(token) >= 3
        }

    left_normalized = re.sub(r"\s+", " ", _sin_acentos(left).lower()).strip()
    right_normalized = re.sub(r"\s+", " ", _sin_acentos(right).lower()).strip()
    if left_normalized == right_normalized:
        return True
    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return False
    # La cobertura se mide sobre la glosa más larga. Medirla sobre la más corta
    # hacía que "Peajes" pareciera equivalente a "Combustibles, Peajes,
    # Estacionamiento" y bloqueaba la recuperación de esta última.
    return len(left_tokens & right_tokens) / max(
        len(left_tokens), len(right_tokens),
    ) >= 0.6


def recuperar_filas_tabla_ocr(
    lineas_coordenadas: list[str], texto_alternativo: str,
) -> tuple[list[str], int]:
    """Recupera celdas omitidas usando PSM 4 sin duplicar la tabla.

    Exige glosas compatibles y dos identidades contables válidas. La alternativa
    puede completar una fila vacía, movimientos Debe/Haber omitidos o una fila
    completa que el OCR geométrico no vio, siempre que no exista ya el mismo
    código ni una glosa equivalente.
    """
    alternatives: dict[str, tuple[str, CuentaRaw]] = {}
    ordered_alternatives: list[tuple[str, CuentaRaw]] = []
    alternative_controls: dict[str, str] = {}
    for index, line in enumerate(texto_alternativo.splitlines()):
        account = _cuenta_desde_candidato_ocr(line, index)
        if account is not None:
            alternatives[_codigo_contable_canonico(account.codigo)] = (line, account)
            ordered_alternatives.append((line, account))
        normalized_control = normalizar_linea_ocr_tabla(line)
        control_match = re.match(
            r"^\W*(sumas?|subtotales?)\b", normalized_control, re.I,
        )
        if control_match:
            alternative_controls[control_match.group(1).lower()] = normalized_control

    current_accounts = [
        account
        for index, line in enumerate(lineas_coordenadas)
        if (
            account := _cuenta_desde_candidato_ocr(
                line, index, exigir_consistencia=False,
            )
        ) is not None
    ]
    recovered: list[str] = []
    replacements = 0
    for index, line in enumerate(lineas_coordenadas):
        normalized_current = normalizar_linea_ocr_tabla(line)
        current_control_match = re.match(
            r"^\W*(sumas?|subtotales?)\b", normalized_current, re.I,
        )
        if current_control_match:
            alternate_control = alternative_controls.get(
                current_control_match.group(1).lower(),
            )
            if alternate_control:
                current_amounts = [
                    float(parsear_monto(token.replace(",", "."), ".") or 0.0)
                    for token in _MONTO_AGRUPADO_OCR.findall(normalized_current)
                ]
                alternate_amounts = [
                    float(parsear_monto(token.replace(",", "."), ".") or 0.0)
                    for token in _MONTO_AGRUPADO_OCR.findall(alternate_control)
                ]
                current_tail = current_amounts[-6:]
                alternate_head = alternate_amounts[:6]
                if (
                    len(current_tail) == 6
                    and len(alternate_head) == 6
                    and all(
                        abs(left - right) <= 10
                        for left, right in zip(alternate_head[2:], current_tail[:4])
                    )
                ):
                    combined = alternate_head[:2] + current_tail
                    combined_line = (
                        f"{current_control_match.group(1)} "
                        + " ".join(str(int(round(value))) for value in combined)
                    )
                    combined_account = parsear_linea(
                        combined_line, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                    )
                    if (
                        combined_account is not None
                        and _error_identidades_cuenta(combined_account) <= 10
                    ):
                        recovered.append(combined_line)
                        replacements += 1
                        continue

        current = _cuenta_desde_candidato_ocr(
            line, index, exigir_consistencia=False,
        )
        if current is None:
            recovered.append(line)
            continue
        alternative_pair = alternatives.get(_codigo_contable_canonico(current.codigo))
        if alternative_pair is None:
            recovered.append(line)
            continue
        alternative_line, alternative = alternative_pair
        if not _nombres_ocr_compatibles(current.nombre, alternative.nombre):
            recovered.append(line)
            continue

        current_values = current.montos_columnas
        alternative_values = alternative.montos_columnas
        current_balance = tuple(
            current_values[column]
            for column in ("saldo_deudor", "saldo_acreedor")
        )
        alternative_balance = tuple(
            alternative_values[column]
            for column in ("saldo_deudor", "saldo_acreedor")
        )
        current_classification = tuple(
            current_values[column]
            for column in ("activo", "pasivo", "perdida", "ganancia")
        )
        alternative_classification = tuple(
            alternative_values[column]
            for column in ("activo", "pasivo", "perdida", "ganancia")
        )
        current_empty = not any(current_values.values())
        alternative_has_data = any(alternative_values.values())
        current_invalid = _error_identidades_cuenta(current) > 10
        added_debit = alternative_values["debitos"] - current_values["debitos"]
        added_credit = alternative_values["creditos"] - current_values["creditos"]
        completes_movements = (
            current_balance == alternative_balance
            and current_classification == alternative_classification
            and added_debit > 0
            and abs(added_debit - added_credit) <= 10
        )
        if (
            (current_empty and alternative_has_data)
            or current_invalid
            or completes_movements
        ):
            normalized = normalizar_codigo_ocr(normalizar_linea_ocr_tabla(alternative_line))
            # Conserva las ocho posiciones para que el parseo definitivo use
            # exactamente la misma estructura validada arriba.
            parsed_normalized = parsear_linea(
                normalized, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if parsed_normalized is None or not parsed_normalized.montos_columnas:
                for suffix in (" 0", " 0 0"):
                    padded = normalized + suffix
                    parsed = parsear_linea(
                        padded, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
                    )
                    if (
                        parsed is not None
                        and parsed.montos_columnas
                        and _error_identidades_cuenta(parsed) <= 10
                        and parsed.montos_columnas == alternative_values
                    ):
                        normalized = padded
                        break
            recovered.append(normalized)
            replacements += 1
        else:
            recovered.append(line)

    # PSM 6 por coordenadas puede omitir una línea completa aunque PSM 4 la
    # lea con sus ocho columnas. Se incorpora únicamente evidencia contable
    # autoconsistente y se evita duplicar tanto por código como por glosa; así
    # una variante OCR del código (4.02.09.60 vs 4.02.04.60) tampoco duplica la
    # cuenta ya observada.
    current_codes = {
        _codigo_contable_canonico(account.codigo) for account in current_accounts
    }
    for alternative_line, alternative in ordered_alternatives:
        alternative_code = _codigo_contable_canonico(alternative.codigo)
        normalized_alternative = normalizar_linea_ocr_tabla(alternative_line)
        is_control = bool(re.match(
            r"^\W*(?:sumas?|subtotales?|totales?|resultado|utilidad)\b",
            normalized_alternative,
            re.I,
        ))
        already_present = alternative_code in current_codes or any(
            _nombres_ocr_compatibles(current.nombre, alternative.nombre)
            for current in current_accounts
        )
        if already_present or alternative.es_total or is_control:
            continue
        normalized = normalizar_codigo_ocr(normalized_alternative)
        recovered.append(normalized)
        current_accounts.append(alternative)
        current_codes.add(alternative_code)
        replacements += 1
    return recovered, replacements


def _tabla_ocr_necesita_recuperacion(lineas: list[str]) -> bool:
    for index, line in enumerate(lineas):
        normalized = normalizar_linea_ocr_tabla(line)
        if (
            re.match(r"^\W*(?:sumas?|subtotales?)\b", normalized, re.I)
            and len(_MONTO_AGRUPADO_OCR.findall(normalized)) >= 4
        ):
            parsed_control = parsear_linea(
                normalized, index, FormatoCodigo.SIN_CODIGO, ".", 0.75,
            )
            if (
                parsed_control is None
                or not parsed_control.montos_columnas
                or not any(parsed_control.montos_columnas.values())
                or _error_identidades_cuenta(parsed_control) > 10
            ):
                return True
        account = _cuenta_desde_candidato_ocr(
            line, index, exigir_consistencia=False,
        )
        if account is not None and _error_identidades_cuenta(account) > 10:
            return True
        if account is None or any(account.montos_columnas.values()):
            continue
        grouped_amounts = _MONTO_AGRUPADO_OCR.findall(line)
        if any(re.sub(r"\D", "", token).lstrip("0") for token in grouped_amounts):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# PARSER PRINCIPAL PDF
# ─────────────────────────────────────────────────────────────────────────────

class ParserPDF:

    def parsear(
        self,
        path: Path,
        context: Optional[ExtractionContext] = None,
    ) -> ResultadoParseo:
        ok, msg = validar_archivo(path)
        if not ok:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
                advertencias=[f"VALIDACIÓN FALLIDA: {msg}"]
            )

        # Sprint 31 — Análisis documental ANTES del parseo.
        # Lee solo las primeras páginas, produce un FormatSignature y decide
        # extractor vía ExtractorFactory. NO cambia la extracción: si el
        # análisis falla, se continúa exactamente como antes (backward
        # compatibility).
        advertencias_iniciales: list[str] = []
        try:
            documento_ctx = self._analizar_documento(path)
        except Exception as exc:  # noqa: BLE001 — backward compatibility
            logger.debug(
                "Análisis documental falló (%s); usando flujo clásico.",
                exc, exc_info=True,
            )
            documento_ctx = None
        if documento_ctx is not None:
            logger.info("\n" + documento_ctx.to_log_block())
            for w in documento_ctx.warnings:
                if w not in advertencias_iniciales:
                    advertencias_iniciales.append(w)

        self._ocr_advertencias: list[str] = []
        self._extraction_method = "text"
        lineas, requirio_ocr, rotacion = self._extraer_lineas(path, context)

        if not lineas:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=requirio_ocr,
                rotacion_aplicada=rotacion,
                advertencias=(
                    self._ocr_advertencias
                    + ["No se pudo extraer texto (ni nativo ni OCR)"]
                ),
                document_context=documento_ctx,
            )

        if requirio_ocr:
            lineas = [normalizar_linea_ocr_tabla(l) for l in lineas]
        elif self._extraction_method not in {
            "coordinates_8_amounts",
            "native_table_8_columns",
        }:
            lineas = [normalizar_montos_fragmentados(l) for l in lineas]
        lineas = [normalizar_codigo_ocr(l) for l in lineas]

        primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        muestra_montos = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra_montos)
        periodo_comparativo = any(
            re.search(r"\bactual\s+anterior\b", _sin_acentos(linea), re.I)
            or re.fullmatch(r"\s*(?:19|20)\d{2}\s+(?:19|20)\d{2}\s*", linea)
            for linea in lineas
        )

        # 3b. Detectar layout de columnas
        # Prioridad:
        #   1) ExtractionContext (de DocumentAnalyzer) si confianza suficiente
        #   2) Perfil de familia aprendido (Sprint 36, solo si ENABLE_DYNAMIC_LAYOUT)
        #   3) LayoutDetector interno (solo si ENABLE_DYNAMIC_LAYOUT)
        #   4) Heurística estándar (ULTIMAS_COLS) por defecto
        advertencias = list(advertencias_iniciales) + self._ocr_advertencias
        column_order: Optional[list[OrigenColumna]] = None
        layout_columns: Optional[list[str]] = None

        # Sprint 36 — detección anticipada de familia/extractor (se reutiliza
        # en _anotar_extractor para no detectar dos veces). Gated por
        # ENABLE_DYNAMIC_LAYOUT: si falla, todo continúa como antes.
        detectado_extractor: Optional[dict] = None
        if ENABLE_DYNAMIC_LAYOUT and documento_ctx is not None:
            try:
                from document_intelligence.extractors.factory import (
                    SpecializedExtractorFactory,
                )
                detectado_extractor = SpecializedExtractorFactory().detect(
                    path, documento_ctx,
                )
            except Exception as exc:  # noqa: BLE001 — fallback deliberado
                logger.debug(
                    "Detección anticipada de extractor falló; "
                    "se sigue con heurística estándar: %s", exc,
                )

        if context and context.layout_hint and context.layout_confidence >= LAYOUT_CONFIDENCE_THRESHOLD:
            layout_columns = list(context.layout_hint)
            cols = []
            for c in layout_columns:
                oc = _LAYOUT_COLUMN_MAP.get(c)
                if oc is not None:
                    cols.append(oc)
            if len(cols) >= 2:
                column_order = cols
                advertencias.append(
                    f"LayoutDetector (context): {len(cols)} columnas "
                    f"({', '.join(c.value for c in cols)}), "
                    f"confianza={context.layout_confidence:.2f}"
                )
            else:
                advertencias.append(
                    "LayoutDetector detectó columnas en contexto pero ninguna "
                    "fue reconocida — usando heurística estándar."
                )
        elif detectado_extractor is not None and detectado_extractor.get(
            "family_id"
        ) not in (None, "", "DESCONOCIDO"):
            # Perfil de familia aprendido (Sprint 36): el orden de columnas
            # proviene del training (Sprint 35) para la familia detectada.
            # Se aplica con cualquier familia match de confianza, tenga o no
            # extractor registrado (los perfiles existen para las 23 familias).
            try:
                from document_intelligence.extractors.profile_driven import (
                    profile_layout_hint,
                )
                hint = profile_layout_hint(
                    path, documento_ctx,
                    family_id=detectado_extractor.get("family_id", ""),
                    lines=lineas,
                )
            except Exception as exc:  # noqa: BLE001 — fallback deliberado
                hint = None
                logger.debug(
                    "Perfil de familia no aplicable (%s); heurística estándar.",
                    exc,
                )
            if hint:
                cols = []
                for c in hint:
                    oc = _LAYOUT_COLUMN_MAP.get(c)
                    if oc is not None:
                        cols.append(oc)
                if len(cols) >= 2:
                    column_order = cols
                    layout_columns = list(hint)
                    advertencias.append(
                        f"Perfil de familia "
                        f"({detectado_extractor.get('family_id', '')}): "
                        f"{len(cols)} columnas "
                        f"({', '.join(c.value for c in cols)})"
                    )
                else:
                    advertencias.append(
                        "Perfil de familia sin columnas aprovechables — "
                        "usando heurística estándar."
                    )
            else:
                advertencias.append(
                    "Perfil de familia no aplicable o sin cobertura — "
                    "usando heurística estándar."
                )
        elif ENABLE_DYNAMIC_LAYOUT:
            from parsers.layout_detector import LayoutDetector
            detector = LayoutDetector()
            layout = detector.detect(lineas)
            if layout.confidence >= 0.5:
                layout_columns = list(layout.columns)
                cols = []
                for c in layout.columns:
                    oc = _LAYOUT_COLUMN_MAP.get(c)
                    if oc is not None:
                        cols.append(oc)
                if len(cols) >= 2:
                    column_order = cols
                    advertencias.append(
                        f"LayoutDetector: {len(cols)} columnas "
                        f"({', '.join(c.value for c in cols)}), "
                        f"confianza={layout.confidence:.2f}"
                    )
                else:
                    advertencias.append(
                        "LayoutDetector detectó columnas pero ninguna "
                        "fue reconocida — usando heurística estándar."
                    )
            else:
                advertencias.append(
                    f"LayoutDetector: confianza insuficiente "
                    f"({layout.confidence:.2f}) — usando heurística estándar."
                )

        # Scan years and currencies dynamically
        years, currencies = detectar_años_y_monedas(lineas)

        # Pre-process lines to associate vertical labels and amounts
        lineas = asociar_lineas_verticales(lineas)

        # 4. Parsear todas las líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        for i, l in enumerate(lineas):
            sub_lines = split_side_by_side(l)
            for sub_l in sub_lines:
                c = parsear_linea(sub_l, i, formato_codigo, separador, confianza,
                                  column_order=column_order,
                                  periodo_comparativo=periodo_comparativo,
                                  years=years,
                                  currencies=currencies)
                if c:
                    cuentas.append(c)

        cuentas, cuentas_partidas = fusionar_cuentas_partidas(cuentas)
        if cuentas_partidas:
            advertencias.append(
                f"Se reconstruyeron {cuentas_partidas} cuentas partidas entre "
                "su código, glosa e importes."
            )

        secciones_anotadas = anotar_secciones_balance_clasificado(cuentas)
        if secciones_anotadas:
            advertencias.append(
                f"Se recuperó la sección contable de {secciones_anotadas} cuentas "
                "desde encabezados del balance clasificado."
            )

        # NOTA (Fase A): la resolución de tipo_cuenta se eliminó de ParserPDF.
        # El parser es un extractor pasivo: NO escribe CuentaRaw.tipo_cuenta.
        # La resolución contable ocurre fuera del parser (HomologationPipeline
        # o reportes vía AccountTypeResolver).
        # Ver reports/cuenta_raw_architecture/fase_a_impact_analysis.md.

        if requirio_ocr:
            advertencias.append(
                f"Documento procesado vía OCR (rotación={rotacion}°). "
                "Confianza de extracción reducida a 0.75 — recomendar revisión humana."
            )

        if not requirio_ocr and rotacion == 180 and context and context.rotation_confidence >= ROTATION_CORRECTION_THRESHOLD:
            advertencias.append(
                f"Documento corregido desde rotación 180° "
                f"(confianza={context.rotation_confidence:.2f})"
            )

        certificacion = certificar_extraccion_columnas(
            cuentas, metodo=self._extraction_method,
        )
        if certificacion.estado == "no_evaluable":
            certificacion_clasificada = certificar_totales_clasificados(cuentas)
            if certificacion_clasificada.estado != "no_evaluable":
                certificacion = certificacion_clasificada

        resultado = ResultadoParseo(
            archivo=path.name,
            formato_codigo=formato_codigo,
            separador_miles=separador,
            requirio_ocr=requirio_ocr,
            rotacion_aplicada=rotacion,
            cuentas=cuentas,
            advertencias=advertencias,
            document_context=documento_ctx,
            certificacion_extraccion=certificacion,
        )
        if resultado.certificacion_extraccion.estado == "fallida":
            resultado.advertencias.extend(resultado.certificacion_extraccion.razones)
        self._anotar_extractor(resultado, detectado_extractor)
        return resultado

    def _anotar_extractor(
        self,
        resultado: ResultadoParseo,
        detectado: Optional[dict] = None,
    ) -> None:
        """Sprint 34 — anota `extractor_info` SIN cambiar la extracción.

        `detectado` es el resultado de la detección anticipada del Sprint 36
        (si ENABLE_DYNAMIC_LAYOUT la computó antes del bucle de parseo);
        si viene None se detecta aquí. Si la factory falla, `extractor_info`
        queda en None y el parseo continúa exactamente igual (backward
        compatibility / fallback obligatorio).
        """
        if resultado.document_context is None:
            return
        try:
            if detectado is None:
                from document_intelligence.extractors.factory import (
                    SpecializedExtractorFactory,
                )
                detectado = SpecializedExtractorFactory().detect(
                    resultado.document_context.pdf_path,
                    resultado.document_context,
                )
            resultado.extractor_info = detectado
        except Exception as exc:  # noqa: BLE001 — fallback deliberado
            logger.debug(
                "Anotación de extractor falló; se omite: %s", exc, exc_info=True,
            )

    def _analizar_documento(self, path: Path) -> Optional[Any]:
        """Sprint 31 — análisis documental previo al parseo.

        Nunca lanza excepción: si el análisis falla retorna None y el flujo
        continúa exactamente como antes (backward compatibility).
        """
        try:
            from document_intelligence.context import analyze_document_preview
            return analyze_document_preview(path)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Document Intelligence no disponible (%s); "
                "usando flujo clásico.", exc, exc_info=True,
            )
            return None

    def _extraer_lineas(
        self,
        path: Path,
        context: Optional[ExtractionContext] = None,
    ) -> tuple[list[str], bool, int]:
        # Sprint F: si un extractor especializado ya separó las líneas
        # (p. ej. doble columna ACTIVO|PASIVO), usarlas directamente. Se
        # reutiliza íntegramente el pipeline de parseo posterior (formato,
        # separador, parsear_linea); no se duplica ninguna lógica.
        if context is not None and context.lineas_presplit:
            lineas = [l for l in context.lineas_presplit if l.strip()]
            if lineas:
                return lineas, False, 0

        lineas: list[str] = []
        # Conserva el layout monetario detectado entre paginas nativas. Debe
        # existir incluso cuando la primera pagina no contiene una tabla de
        # ocho columnas; de lo contrario el fallback por coordenadas intentaba
        # leer una variable local aun no inicializada.
        coordinate_centers: Optional[list[float]] = None

        with pdfplumber.open(path) as pdf:
            n_paginas = len(pdf.pages)
            for page in pdf.pages:
                texto = page.extract_text() or ""
                if not texto.strip():
                    continue
                # Sprint F — doble columna: si la página parece tener dos
                # columnas de cuenta (pre-filtro barato sobre el texto plano),
                # intentar la separación estructural por coordenadas (x0).
                # Si el análisis no confirma, se conserva el texto plano tal
                # cual (comportamiento universal idéntico).
                page_lineas: Optional[list[str]] = None
                try:
                    from document_intelligence.extractors.double_column import (
                        _prefiltro_sugiere,
                        separar_page,
                    )
                    if _prefiltro_sugiere(texto):
                        page_lineas = separar_page(page)
                except Exception as exc:  # noqa: BLE001 — fallback seguro
                    logger.debug(
                        "Detección de doble columna no disponible (%s); "
                        "universal.", exc,
                    )
                if page_lineas:
                    lineas.extend(l for l in page_lineas if l.strip())
                else:
                    tabla_8_columnas = _extraer_tabla_balance_8_columnas(page)
                    if tabla_8_columnas:
                        self._extraction_method = "native_table_8_columns"
                        lineas.extend(tabla_8_columnas)
                    else:
                        tabla_coordenadas, detected_centers = (
                            _extraer_tabla_balance_por_coordenadas(
                                page, coordinate_centers,
                            )
                        )
                        if tabla_coordenadas:
                            coordinate_centers = detected_centers
                            self._extraction_method = "coordinates_8_amounts"
                            lineas.extend(tabla_coordenadas)
                        else:
                            lineas.extend(texto.split('\n'))

        if lineas:
            if self._debe_corregir_rotacion(context):
                lineas = [ParserPDF._reverse_line(l) for l in lineas]
                return lineas, False, 180
            return lineas, False, 0

        return self._ocr_documento(path, n_paginas)

    @staticmethod
    def _debe_corregir_rotacion(context: Optional[ExtractionContext]) -> bool:
        if not context:
            return False
        return (
            context.rotation_hint == 180
            and context.rotation_confidence >= ROTATION_CORRECTION_THRESHOLD
        )

    @staticmethod
    def _reverse_line(linea: str) -> str:
        if not linea.strip():
            return linea
        return " ".join(w[::-1] for w in linea.split())

    def _ocr_documento(self, path: Path, n_paginas: int) -> tuple[list[str], bool, int]:
        lineas: list[str] = []
        rotacion_global: Optional[int] = None
        coordinate_centers: Optional[list[float]] = None

        pdftoppm_bin = shutil.which('pdftoppm') or 'pdftoppm'

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            for pagina in range(1, n_paginas + 1):
                prefix = tmpdir_path / f'pg{pagina}'
                try:
                    raster = subprocess.run(
                        [pdftoppm_bin, '-png', '-gray', '-r', str(OCR_RENDER_DPI),
                         '-f', str(pagina), '-l', str(pagina),
                         str(path), str(prefix)],
                        capture_output=True, timeout=OCR_PAGE_TIMEOUT_SECONDS
                    )
                except subprocess.TimeoutExpired:
                    self._ocr_advertencias.append(
                        f"Página {pagina}: no pudo rasterizarse dentro de "
                        f"{OCR_PAGE_TIMEOUT_SECONDS} segundos y fue omitida."
                    )
                    logger.warning(
                        "Rasterización OCR omitida por timeout en página %d de %s",
                        pagina,
                        path.name,
                    )
                    continue
                if raster.returncode != 0:
                    self._ocr_advertencias.append(
                        f"Página {pagina}: falló su rasterización OCR y fue omitida."
                    )
                    logger.warning(
                        "No se pudo rasterizar página %d de %s (código %s)",
                        pagina,
                        path.name,
                        raster.returncode,
                    )
                    continue
                imgs = list(tmpdir_path.glob(f'pg{pagina}*.png'))
                if not imgs:
                    continue
                img_path = imgs[0]

                if rotacion_global is None:
                    rot = detectar_rotacion_osd(img_path)
                    if rot is None:
                        rot = detectar_rotacion_heuristica(img_path)
                    rotacion_global = rot

                texto = ocr_pagina(img_path, rotacion_global)
                texto_principal = texto
                words_tsv = ocr_pagina_tsv(img_path, rotacion_global)
                tabla_coordenadas_usada = False
                if words_tsv:
                    tabla_ocr, detected_centers = _extraer_tabla_balance_por_coordenadas(
                        _OCRWordsPage(words_tsv), coordinate_centers,
                    )
                    if len(tabla_ocr) >= 3 and detected_centers:
                        coordinate_centers = detected_centers
                        texto = "\n".join(tabla_ocr)
                        self._extraction_method = "ocr_coordinates_8_amounts"
                        tabla_coordenadas_usada = True
                if tabla_coordenadas_usada and texto_principal.strip():
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_principal,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "al contrastar la geometría con la lectura textual OCR."
                        )
                if tabla_coordenadas_usada and _tabla_ocr_necesita_recuperacion(
                    texto.splitlines(),
                ):
                    texto_tabla = ocr_pagina(img_path, rotacion_global, psm=4)
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_tabla,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "por verificación cruzada de dos lecturas OCR."
                        )
                # Una tabla reconstruida por coordenadas ya contiene la misma
                # pagina. Fusionarla con PSM 4 duplicaba sus cuentas y montos.
                if (
                    not tabla_coordenadas_usada
                    and _ocr_requiere_alternativa(texto, pagina == n_paginas)
                ):
                    texto_tabla = ocr_pagina(img_path, rotacion_global, psm=4)
                    recovered, replacements = recuperar_filas_tabla_ocr(
                        texto.splitlines(), texto_tabla,
                    )
                    if replacements:
                        texto = "\n".join(recovered)
                        self._ocr_advertencias.append(
                            f"Página {pagina}: se recuperaron {replacements} filas "
                            "por verificación cruzada de dos lecturas OCR."
                        )
                    else:
                        texto, estrategia = _combinar_candidatos_ocr(
                            texto, texto_tabla,
                        )
                        if estrategia != "principal":
                            self._ocr_advertencias.append(
                                f"Página {pagina}: OCR de tabla seleccionado por "
                                f"mayor calidad estructural ({estrategia})."
                            )
                if not texto.strip():
                    self._ocr_advertencias.append(
                        f"Página {pagina}: OCR sin texto utilizable; revise que el "
                        "documento procesado esté completo."
                    )
                lineas.extend(texto.split('\n'))

        return lineas, True, rotacion_global or 0


# ─────────────────────────────────────────────────────────────────────────────
# EXCEL PARSER (extraído de app_validacion para eliminar import circular)
# ─────────────────────────────────────────────────────────────────────────────

def parsear_excel(file) -> list[CuentaRaw]:
    df = pd.read_excel(file, header=None)

    header_aliases = {
        "debito": "debitos", "debitos": "debitos", "debe": "debitos",
        "credito": "creditos", "creditos": "creditos", "haber": "creditos",
        "deudor": "saldo_deudor", "acreedor": "saldo_acreedor",
        "activo": "activo", "pasivo": "pasivo",
        "perdida": "perdida", "ganancia": "ganancia",
    }
    eight_column_map: dict[int, str] = {}
    eight_column_header = -1
    for row_idx in range(min(30, df.shape[0])):
        candidate: dict[int, str] = {}
        for col_idx, value in enumerate(df.iloc[row_idx].tolist()):
            if pd.isna(value):
                continue
            label = _sin_acentos(str(value)).lower().strip(" .:$")
            label = re.sub(r"\s+", " ", label)
            if label in header_aliases:
                candidate[col_idx] = header_aliases[label]
        if len(set(candidate.values())) >= 6 and {
            "activo", "pasivo", "perdida", "ganancia",
        }.issubset(candidate.values()):
            eight_column_map = candidate
            eight_column_header = row_idx
            break

    if eight_column_map:
        accounts: list[CuentaRaw] = []
        origin_by_column = {
            "activo": OrigenColumna.ACTIVO,
            "pasivo": OrigenColumna.PASIVO,
            "perdida": OrigenColumna.PERDIDA,
            "ganancia": OrigenColumna.GANANCIA,
        }
        for row_idx in range(eight_column_header + 1, df.shape[0]):
            values = df.iloc[row_idx].tolist()
            text_cells = [
                str(value).strip() for value in values
                if isinstance(value, str) and value.strip()
            ]
            if not text_cells:
                continue
            label = max(text_cells, key=len)
            match = re.match(
                r"^\s*(\d+(?:[.\-]\d+)+)\s+(.+?)\s*$", label,
            )
            code = match.group(1) if match else None
            name = match.group(2).strip() if match else label
            amounts = {column: 0.0 for column in RAW_MONETARY_COLUMNS}
            numeric_seen = False
            for col_idx, column in eight_column_map.items():
                value = values[col_idx]
                if pd.isna(value):
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    amounts[column] = float(value)
                    numeric_seen = True
                else:
                    parsed = parsear_monto(str(value), ".")
                    if parsed is not None:
                        amounts[column] = float(parsed)
                        numeric_seen = True
            if not numeric_seen:
                continue
            classified = [
                (column, amounts[column])
                for column in origin_by_column if amounts[column] != 0
            ]
            if len(classified) == 1:
                column, amount = classified[0]
                origin = origin_by_column[column]
            else:
                amount = 0.0 if not classified else classified[0][1]
                origin = OrigenColumna.DESCONOCIDO
            accounts.append(CuentaRaw(
                linea=row_idx, codigo=code, nombre=name, monto=amount,
                origen_columna=origin,
                es_total=code is None and bool(PATRON_TOTAL.match(name)),
                confianza_extraccion=1.0,
                montos_columnas=amounts,
            ))
        return accounts

    # Helper to detect year and currency for a column
    # Scan the top 15 rows of this column and its immediate left neighbor
    col_meta = {}
    for col_idx in range(df.shape[1]):
        year = None
        currency = None
        # Look in current column and adjacent left column (useful for merged cells)
        for c in (col_idx, col_idx - 1):
            if c < 0 or c >= df.shape[1]:
                continue
            for r in range(min(15, df.shape[0])):
                val = df.iloc[r, c]
                if pd.isna(val) or (isinstance(val, (int, float)) and not (1990 <= val <= 2050)):
                    continue
                val_str = str(val).strip().lower()

                # Check year
                year_match = re.search(r'\b(20\d{2})\b', val_str)
                if year_match and not year:
                    year = year_match.group(1)
                elif 'actual' in val_str and not year:
                    year = 'actual'
                elif 'anterior' in val_str and not year:
                    year = 'anterior'
                elif 'acumulado' in val_str and not year:
                    year = 'acumulado'

                # Check currency
                if ('usd' in val_str or 'dolar' in val_str or 'us$' in val_str) and not currency:
                    currency = 'USD'
                elif ('clp' in val_str or 'peso' in val_str or 'clp$' in val_str) and not currency:
                    currency = 'CLP'
        col_meta[col_idx] = (year, currency)

    cuentas = []
    for i, row in df.iterrows():
        vals = row.tolist()
        non_na_vals = [v for v in vals if pd.notna(v)]
        if not non_na_vals:
            continue

        textos = [v for v in non_na_vals if isinstance(v, str)]
        numeros = [v for v in non_na_vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not textos:
            continue

        nombre = max(textos, key=len)
        if len(nombre) < 3:
            continue

        # Skip header/meta rows (e.g. if the row itself has words like 'balance', 'rut', 'año' and no numeric figures)
        if any(w in nombre.lower() for w in ('rut', 'razon social', 'fecha', 'periodo', 'moneda', 'balance general')) and not numeros:
            continue

        # Detect account code. En históricos exportados suele estar en una
        # columna numérica separada, no necesariamente en la primera.
        codigo = None
        primer = str(vals[0]) if pd.notna(vals[0]) else ""
        if re.match(r'^[\d.\-]+$', primer) and primer != nombre:
            codigo = primer
        if codigo is None:
            name_index = vals.index(nombre) if nombre in vals else len(vals)
            for col_idx, value in enumerate(vals):
                if col_idx >= name_index:
                    break
                if pd.isna(value):
                    continue
                candidate = str(value).strip()
                if re.fullmatch(r"\d{6,}(?:\.0)?", candidate):
                    codigo = candidate.removesuffix(".0")
                    break

        # Map all numeric amounts to their year/currency
        montos_periodos = {}
        montos_columnas = {}
        last_monto = None

        for col_idx, val in enumerate(vals):
            if pd.isna(val) or not isinstance(val, (int, float)) or isinstance(val, bool):
                continue
            if codigo and str(val) == codigo:
                continue
            if col_idx == 0 and isinstance(val, int) and val < 500:
                continue

            val_f = float(val)
            last_monto = val_f

            year, currency = col_meta.get(col_idx, (None, None))

            if year and currency:
                montos_periodos[f"{year}_{currency}"] = val_f
                montos_periodos[year] = val_f
                montos_periodos[currency] = val_f
            elif year:
                montos_periodos[year] = val_f
            elif currency:
                montos_periodos[currency] = val_f

            col_name = f"col_{col_idx}"
            if year:
                col_name += f"_{year}"
            if currency:
                col_name += f"_{currency}"
            montos_columnas[col_name] = val_f

        detected_years = sorted(list({col_meta[c][0] for c in col_meta if col_meta[c][0] is not None}), reverse=True)
        if detected_years:
            if "actual" not in montos_periodos and len(detected_years) >= 1:
                montos_periodos["actual"] = montos_periodos.get(detected_years[0], 0.0)
            if "anterior" not in montos_periodos and len(detected_years) >= 2:
                montos_periodos["anterior"] = montos_periodos.get(detected_years[1], 0.0)

        monto_principal = (
            montos_periodos["actual"]
            if "actual" in montos_periodos else last_monto
        )
        origin = OrigenColumna.DESCONOCIDO
        if codigo:
            origin = {
                "1": OrigenColumna.ACTIVO,
                "2": OrigenColumna.PASIVO,
                "5": OrigenColumna.GANANCIA,
                "6": OrigenColumna.PERDIDA,
            }.get(codigo[0], OrigenColumna.DESCONOCIDO)

        cuentas.append(CuentaRaw(
            linea=i, codigo=codigo, nombre=nombre, monto=monto_principal,
            origen_columna=origin, confianza_extraccion=0.9,
            montos_periodos=montos_periodos, montos_columnas=montos_columnas
        ))

    return cuentas



# ─────────────────────────────────────────────────────────────────────────────
# CLI DE PRUEBA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python parser_universal.py <ruta_al_pdf>")
        sys.exit(1)

    parser = ParserPDF()
    archivo = Path(sys.argv[1])

    resultado = parser.parsear(archivo)

    print(f"Archivo: {resultado.archivo}")
    print(f"Formato código: {resultado.formato_codigo}")
    print(f"Separador miles: '{resultado.separador_miles}'")
    print(f"Requirió OCR: {resultado.requirio_ocr} (rotación {resultado.rotacion_aplicada}°)")
    print(f"Advertencias: {resultado.advertencias}")
    print(f"Total cuentas extraídas: {len(resultado.cuentas)}")
    print()
    for c in resultado.cuentas[:25]:
        print(f"  [{c.codigo or '-':18s}] {c.nombre[:45]:45s} "
              f"monto={c.monto!s:>15} ({c.origen_columna.value}) "
              f"{'[TOTAL]' if c.es_total else ''}")
