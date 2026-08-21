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

import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import pdfplumber
from PIL import Image


logger = logging.getLogger("parser_universal")


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
OCR_RENDER_DPI = 165
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
    v = valor.strip().replace(' ', '')
    if v in ('', '-', '0', '0.00', '0,00'):
        return 0.0 if v != '' and v != '-' else None

    negativo = False
    if v.startswith('(') and v.endswith(')'):
        negativo = True
        v = v[1:-1]
    if v.startswith('-'):
        negativo = True
        v = v[1:]

    if separador_miles == '.':
        v = v.replace('.', '').replace(',', '.')
    else:
        v = v.replace(',', '')

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


def ocr_pagina(img_path: Path, rotacion: int) -> str:
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
                [obtener_tesseract_bin(), str(imagen_ocr), '-', '--psm', '6', '-l', 'spa'],
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
                    [obtener_tesseract_bin(), str(retry_path), '-', '--psm', '6', '-l', 'spa'],
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
# FG1 — código con UN solo separador (guión o punto): 1101-51, 13216-0000.
#   La guarda `\d{4,6}` al inicio excluye RUT (7-8 dígitos) y fechas cortas.
_PATRON_AUX_UNISEP = re.compile(r'^(\d{4,6}[-.]\d{1,6})\s+(.+)')
# FG2 — código compacto concatenado al nombre sin espacio: 11090BANCO, 10423CTA.
#    El lookahead `(?=[A-Z...])` parte en la frontera dígito → letra y exige que
#    el código sea de 4 a 6 dígitos seguidos inmediatamente por una letra.
_PATRON_AUX_CONCATENADO = re.compile(r'^(\d{4,6})(?=[A-ZÁÉÍÓÚÑ])(.+)')
PATRONES_CODIGO_AUXILIARES = (_PATRON_AUX_UNISEP, _PATRON_AUX_CONCATENADO)

PATRON_MONTOS = re.compile(r'(-?\(?[\d.,]{1,18}\)?)')
_OCR_CERO = re.compile(r'^[oO]$')


def normalizar_token_ocr(token: str) -> str:
    if _OCR_CERO.match(token):
        return '0'
    return token

PATRON_TOTAL = re.compile(
    r'^(total(es)?|sub-?total(es)?|sumas?( iguales)?|resultado|utilidad|perdida neto)\b',
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
    # Notas al pie
    re.compile(r'^\s*(?:Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?|Ver\s+Notas?\s+\d+(?:\s*(?:a|l|y|al)\s*\d+)?)\s*$', re.I),
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
PATRON_CODIGO_OCR = re.compile(r'^(\d{1,2}[.,]){2,4}\d{1,2}(?=\s)')


def normalizar_codigo_ocr(linea: str) -> str:
    m = PATRON_CODIGO_OCR.match(linea)
    if not m:
        return linea
    codigo_normalizado = m.group(0).replace(',', '.')
    return codigo_normalizado + linea[m.end():]


def parsear_linea(
    linea: str,
    numero_linea: int,
    formato_codigo: FormatoCodigo,
    separador_miles: str,
    confianza_base: float = 1.0,
    column_order: Optional[list[OrigenColumna]] = None,
) -> Optional[CuentaRaw]:
    linea = linea.strip()
    if len(linea) < 4:
        return None

    if _es_linea_basura(linea):
        return None

    codigo = None
    resto = linea

    if formato_codigo != FormatoCodigo.SIN_CODIGO:
        patron = PATRONES_CODIGO_LINEA[formato_codigo]
        m = patron.match(linea)
        if m:
            codigo = m.group(1)
            resto = m.group(2)
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

    tokens = resto.split()
    descartados_finales = 0
    while tokens and descartados_finales < 2 and \
            not re.search(r'\d', tokens[-1]) and len(tokens[-1]) <= 2:
        tokens.pop()
        descartados_finales += 1

    montos_tokens = []
    i = len(tokens) - 1
    while i >= 0:
        tok_norm = normalizar_token_ocr(tokens[i])
        if tok_norm == '-':
            montos_tokens.insert(0, '0')
            i -= 1
        elif PATRON_MONTOS.fullmatch(tok_norm.replace('$', '')):
            montos_tokens.insert(0, tok_norm.replace('$', ''))
            i -= 1
        else:
            break

    nombre_tokens = tokens[:i + 1]
    nombre = ' '.join(nombre_tokens).strip(' .-')

    if not nombre or len(nombre) < 3:
        return None

    es_total = bool(PATRON_TOTAL.match(nombre))

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

    if montos_tokens:
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

    return CuentaRaw(
        linea=numero_linea,
        codigo=codigo,
        nombre=nombre,
        monto=monto_principal,
        origen_columna=origen,
        es_total=es_total,
        confianza_extraccion=confianza_base,
    )


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

        lineas = [normalizar_codigo_ocr(l) for l in lineas]

        primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        muestra_montos = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra_montos)

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

        # 4. Parsear todas las líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        for i, l in enumerate(lineas):
            c = parsear_linea(l, i, formato_codigo, separador, confianza,
                              column_order=column_order)
            if c:
                cuentas.append(c)

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

        resultado = ResultadoParseo(
            archivo=path.name,
            formato_codigo=formato_codigo,
            separador_miles=separador,
            requirio_ocr=requirio_ocr,
            rotacion_aplicada=rotacion,
            cuentas=cuentas,
            advertencias=advertencias,
            document_context=documento_ctx,
        )
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
    cuentas = []
    for i, row in df.iterrows():
        vals = [v for v in row.tolist() if pd.notna(v)]
        if not vals: continue
        textos = [v for v in vals if isinstance(v, str)]
        numeros = [v for v in vals if isinstance(v, (int, float))]
        if not textos: continue
        nombre = max(textos, key=len)
        if len(nombre) < 3: continue
        codigo = None
        primer = str(vals[0])
        if re.match(r'^[\d.\-]+$', primer) and primer != nombre:
            codigo = primer
        monto = numeros[-1] if numeros else None
        cuentas.append(CuentaRaw(
            linea=i, codigo=codigo, nombre=nombre, monto=monto,
            origen_columna=OrigenColumna.DESCONOCIDO, confianza_extraccion=0.9
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
