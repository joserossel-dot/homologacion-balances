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
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
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


def _agrupar_palabras_por_linea(words: list[dict], tolerancia: float = 1.5) -> list[list[dict]]:
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
    "debitos": {"DEBITOS", "DEBITO", "DEBE"},
    "creditos": {"CREDITOS", "CREDITO", "HABER"},
    "saldo_deudor": {"DEUDOR"},
    "saldo_acreedor": {"ACREEDOR", "ACREEEDOR"},
    "activo": {"ACTIVO"},
    "pasivo": {"PASIVO", "PASIWO", "PATRIMONIO"},
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


def certificar_extraccion_columnas(
    cuentas: list[CuentaRaw], metodo: str = "",
    tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Certifica las ocho columnas contra un subtotal impreso independiente."""
    filas_detalle = [
        cuenta for cuenta in cuentas
        if not cuenta.es_total and cuenta.montos_columnas
    ]
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

    finales = [
        cuenta for cuenta in cuentas
        if cuenta.es_total and cuenta.montos_columnas
        and (
            "totales iguales" in normalized_name(cuenta)
            or normalized_name(cuenta) in {"totales", "total general"}
        )
    ]
    totales_finales_validos: Optional[bool] = None
    if finales:
        values = finales[-1].montos_columnas
        totales_finales_validos = all((
            abs(values["debitos"] - values["creditos"]) <= tolerancia_absoluta,
            abs(values["saldo_deudor"] - values["saldo_acreedor"]) <= tolerancia_absoluta,
            abs(values["activo"] - values["pasivo"]) <= tolerancia_absoluta,
            abs(values["perdida"] - values["ganancia"]) <= tolerancia_absoluta,
        ))

    candidatos = [
        cuenta for cuenta in cuentas
        if cuenta.es_total and cuenta.montos_columnas
        and (
            "subtotal" in normalized_name(cuenta)
            or normalized_name(cuenta) in {"sumas", "sumas iguales"}
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
    total_impreso = candidatos[-1].montos_columnas
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
    diferencias = {
        column: round(calculados[column] - float(total_impreso.get(column, 0.0) or 0.0), 2)
        for column in RAW_MONETARY_COLUMNS
    }
    fallidas = {
        column: diff for column, diff in diferencias.items()
        if abs(diff) > tolerancia_absoluta
    }
    razones = []
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
    failed = bool(fallidas or filas_inconsistentes or totales_finales_validos is False)
    filas_derivadas = [cuenta.linea for cuenta in filas_detalle if cuenta.columnas_derivadas]
    if filas_derivadas and not failed:
        razones.append(
            f"{len(filas_derivadas)} filas contienen movimientos reconstruidos "
            "desde saldos y clasificación; requieren revisión humana."
        )
    return CertificacionExtraccion(
        estado="fallida" if failed else ("parcial" if filas_derivadas else "certificada"),
        metodo=metodo,
        totales_impresos={k: float(total_impreso.get(k, 0.0) or 0.0) for k in RAW_MONETARY_COLUMNS},
        totales_calculados={k: round(v, 2) for k, v in calculados.items()},
        diferencias=diferencias,
        razones=razones,
        filas_evaluadas=filas,
        filas_inconsistentes=filas_inconsistentes,
        totales_finales_validos=totales_finales_validos,
    )


def certificar_totales_clasificados(
    cuentas: list[CuentaRaw], tolerancia_absoluta: float = 10.0,
) -> CertificacionExtraccion:
    """Control parcial para balances clasificados/IFRS de una o dos columnas.

    Certifica únicamente la ecuación final impresa. No afirma que todas las
    cuentas intermedias estén completas ni correctamente homologadas.
    """
    totals: dict[str, float] = {}
    for cuenta in cuentas:
        if cuenta.monto is None:
            continue
        name = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre).lower()).strip()
        if name == "total activos":
            totals["activo"] = float(cuenta.monto)
        elif name in {
            "total pasivos y patrimonio",
            "total pasivos y patrimonio neto",
            "total pasivo y patrimonio",
        }:
            totals["pasivo_patrimonio"] = float(cuenta.monto)
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
        r"circulantes?|fijos?))?|otros\s+activos?)$", re.I,
    ),
     OrigenColumna.ACTIVO),
    (re.compile(
        r"^(?:total\s+)?pasivos?(?:\s+(?:corrientes?|no\s+corrientes?|"
        r"circulantes?|a\s+largo\s+plazo))?$", re.I,
    ),
     OrigenColumna.PASIVO),
    (re.compile(r"^(?:total\s+)?patrimonio(?:\s+neto)?$", re.I),
     OrigenColumna.PASIVO),
    (re.compile(r"^(?:ingresos?|ventas|ganancias?|otros\s+ingresos)$", re.I),
     OrigenColumna.GANANCIA),
    (re.compile(r"^(?:costos?|gastos|perdidas?|otros\s+gastos)$", re.I),
     OrigenColumna.PERDIDA),
)


def anotar_secciones_balance_clasificado(cuentas: list[CuentaRaw]) -> int:
    """Propaga el encabezado contable a filas de balances clasificados.

    Sólo completa orígenes desconocidos y nunca cambia una columna observada.
    Los encabezados y totales sirven como límites, pero no se convierten en
    cuentas de detalle. Retorna el número de filas enriquecidas.
    """
    seccion: Optional[OrigenColumna] = None
    anotadas = 0
    for cuenta in cuentas:
        nombre = re.sub(r"\s+", " ", _sin_acentos(cuenta.nombre)).strip()
        if re.search(
            r"^(?:estado(?:s)?\s+de\s+)?(?:flujo(?:s)?\s+de\s+efectivo|"
            r"cambios?\s+en\s+el\s+patrimonio|resultado(?:s)?(?:\s+integrales?)?)$",
            nombre, re.I,
        ):
            seccion = None
            continue
        if re.match(
            r"^total(?:es)?\s+pasivos?\s+y\s+patrimonio(?:\s+neto)?$",
            nombre, re.I,
        ):
            seccion = None
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
    # Metadatos frecuentes que terminan en un número y parecen una cuenta.
    re.compile(r'^\s*Nivel\s+\d+(?:[.,]\d+)?\s*$', re.I),
    re.compile(r'^\s*Desde\s+\w+\s+(?:a|hasta)\s+\w+\s+\d{4}\s*$', re.I),
    re.compile(r'^\s*(?:19|20)\d{2}\s+(?:19|20)\d{2}\s*$'),
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
PATRON_CODIGO_OCR = re.compile(r'^(\d{1,2}[.,/]){2,4}\d{1,2}(?=\s)')


def normalizar_codigo_ocr(linea: str) -> str:
    m = PATRON_CODIGO_OCR.match(linea)
    if not m:
        return linea
    codigo_normalizado = m.group(0).replace(',', '.').replace('/', '.')
    return codigo_normalizado + linea[m.end():]


def normalizar_linea_ocr_tabla(linea: str) -> str:
    """Limpia bordes de tabla y separadores confundidos por OCR.

    No reescribe signos contables ni elimina paréntesis; sólo retira caracteres
    de grilla y normaliza comas intercaladas en montos chilenos.
    """
    limpia = re.sub(r"[\[\]|¡]", " ", linea)
    limpia = re.sub(r"(?<=\d),(?=\d)", ".", limpia)
    return re.sub(r"\s+", " ", limpia).strip()


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
) -> Optional[CuentaRaw]:
    linea = linea.strip()
    if len(linea) < 4:
        return None

    if _es_linea_basura(linea):
        return None

    codigo = None
    resto = linea

    # Los totales impresos no llevan código. Evita interpretar su primer monto
    # (p. ej. 72.911.536.017) como un código de formato PUNTO.
    if PATRON_TOTAL.match(linea):
        resto = linea
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
    montos_periodos: dict[str, float] = {}

    if periodo_comparativo and len(montos_tokens) >= 3 and re.fullmatch(
        r"\d{1,2}(?:\.\d{1,2}){2,}", montos_tokens[-1],
    ):
        # Referencia de nota (6.1.2, 12.3.1), no un tercer período monetario.
        montos_tokens.pop()

    if periodo_comparativo and len(montos_tokens) >= 2:
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
        debit = montos_columnas["debitos"]
        credit = montos_columnas["creditos"]
        debtor = montos_columnas["saldo_deudor"]
        creditor = montos_columnas["saldo_acreedor"]
        classified = (
            montos_columnas["activo"] + montos_columnas["pasivo"]
            + montos_columnas["perdida"] + montos_columnas["ganancia"]
        )
        if debit == 0 and credit == 0 and abs(debtor + creditor - classified) <= 10:
            if debtor != 0 and creditor == 0:
                montos_columnas["debitos"] = debtor
                columnas_derivadas.append("debitos")
            elif creditor != 0 and debtor == 0:
                montos_columnas["creditos"] = creditor
                columnas_derivadas.append("creditos")

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

        # 4. Parsear todas las líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        for i, l in enumerate(lineas):
            c = parsear_linea(l, i, formato_codigo, separador, confianza,
                              column_order=column_order,
                              periodo_comparativo=periodo_comparativo)
            if c:
                cuentas.append(c)

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
                words_tsv = ocr_pagina_tsv(img_path, rotacion_global)
                if words_tsv:
                    tabla_ocr, detected_centers = _extraer_tabla_balance_por_coordenadas(
                        _OCRWordsPage(words_tsv), None,
                    )
                    if len(tabla_ocr) >= 3 and detected_centers:
                        texto = "\n".join(tabla_ocr)
                        self._extraction_method = "ocr_coordinates_8_amounts"
                if _ocr_requiere_alternativa(texto, pagina == n_paginas):
                    texto_tabla = ocr_pagina(img_path, rotacion_global, psm=4)
                    texto, estrategia = _combinar_candidatos_ocr(texto, texto_tabla)
                    if estrategia != "principal":
                        self._ocr_advertencias.append(
                            f"Página {pagina}: OCR de tabla seleccionado por mayor "
                            f"calidad estructural ({estrategia})."
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
