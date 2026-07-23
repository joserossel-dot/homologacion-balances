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

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import pdfplumber
from PIL import Image


# Feature flag: cuando está en False, se usa la heurística fija ULTIMAS_COLS.
# Cuando está en True, LayoutDetector analiza los encabezados del documento
# para determinar el orden real de columnas.
ENABLE_DYNAMIC_LAYOUT = False

# Feature flag: cuando está en False, no se ejecuta AccountTypeResolver.
# Cuando está en True, cada cuenta se resuelve a AccountType después del parseo.
ENABLE_ACCOUNT_TYPE_RESOLVER = False


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
    tipo_cuenta: Optional[str] = None  # AccountType resuelto (ACTIVO|PASIVO|...)


@dataclass
class ResultadoParseo:
    archivo: str
    formato_codigo: FormatoCodigo
    separador_miles: str            # '.' o ','
    requirio_ocr: bool
    rotacion_aplicada: int           # 0 o 90
    cuentas: list[CuentaRaw] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)


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
PATRON_COMPACTO = re.compile(r'^\d{6,10}$')


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


def obtener_tesseract_bin() -> str:
    return shutil.which('tesseract') or 'tesseract'


def detectar_rotacion_osd(img_path: Path) -> Optional[int]:
    try:
        result = subprocess.run(
            [obtener_tesseract_bin(), str(img_path), '-', '--psm', '0', '-l', 'osd'],
            capture_output=True, text=True, timeout=60,
            env={'TESSDATA_PREFIX': TESSDATA_DIR}
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
                env={'TESSDATA_PREFIX': TESSDATA_DIR}
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
    if rotacion != 0:
        img = Image.open(img_path)
        img_rot = img.rotate(rotacion, expand=True)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            img_rot.save(tmp.name)
            tmp_path = Path(tmp.name)
    else:
        tmp_path = img_path

    try:
        result = subprocess.run(
            [obtener_tesseract_bin(), str(tmp_path), '-', '--psm', '6', '-l', 'spa'],
            capture_output=True, text=True, timeout=120,
            env={'TESSDATA_PREFIX': TESSDATA_DIR}
        )
        return result.stdout
    finally:
        if rotacion != 0:
            tmp_path.unlink(missing_ok=True)


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
    FormatoCodigo.COMPACTO: re.compile(r'^(\d{6,10})\s+(.+)'),
}

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

<<<<<<< HEAD
=======
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
>>>>>>> 6f7d24a (Recovery: save all work through Sprint 28.5)
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

<<<<<<< HEAD
    ULTIMAS_COLS = [OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
=======
    # Determinar orden de columnas: si ENABLE_DYNAMIC_LAYOUT está activo
    # y se proporcionó un column_order con confianza suficiente, usarlo.
    # Fallback: heurística actual (últimas 4 columnas = Activo/Pasivo/Pérdida/Ganancia).
    if column_order and ENABLE_DYNAMIC_LAYOUT:
        columnas = column_order
    else:
        columnas = [OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
>>>>>>> 6f7d24a (Recovery: save all work through Sprint 28.5)
                    OrigenColumna.PERDIDA, OrigenColumna.GANANCIA]

    n_col = len(columnas)
    monto_principal = None
    origen = OrigenColumna.DESCONOCIDO

    if montos_tokens:
        n = len(montos_tokens)
<<<<<<< HEAD
        
        if n >= 4:
            cola = montos_tokens[-4:]
            for tok, et in zip(cola, ULTIMAS_COLS):
                val = parsear_monto(tok, separador_miles)
                if val is not None and val != 0:
                    monto_principal = val
                    origen = et
                    break
            if monto_principal is None:
                monto_principal = parsear_monto(cola[0], separador_miles)
                origen = ULTIMAS_COLS[0]
                
        else:
            for tok in reversed(montos_tokens):
                val = parsear_monto(tok, separador_miles)
                if val is not None and val != 0:
                    monto_principal = val
                    break
            if monto_principal is None and montos_tokens:
                monto_principal = parsear_monto(montos_tokens[-1], separador_miles)

            if codigo:
                digito_raiz = codigo.replace('.', '').replace('-', '').strip()[0]
                if digito_raiz == '1':
                    origen = OrigenColumna.ACTIVO
                elif digito_raiz == '2':
                    origen = OrigenColumna.PASIVO
                elif digito_raiz == '3':
                    origen = OrigenColumna.PASIVO if 'capital' in nombre.lower() or 'patrimonio' in nombre.lower() else OrigenColumna.PERDIDA
                elif digito_raiz == '4':
                    origen = OrigenColumna.PERDIDA
                elif digito_raiz == '5':
                    origen = OrigenColumna.GANANCIA
            
            if origen == OrigenColumna.DESCONOCIDO:
                nom_lower = nombre.lower()
                if any(x in nom_lower for x in ['caja', 'banco', 'clientes', 'iva', 'activo', 'fijo', 'existencias', 'ppm']):
                    origen = OrigenColumna.ACTIVO
                elif any(x in nom_lower for x in ['proveedores', 'acreedores', 'capital', 'retenciones', 'pasivo', 'letras por pagar']):
                    origen = OrigenColumna.PASIVO
                elif any(x in nom_lower for x in ['gasto', 'costo', 'arriendo', 'remuneraciones', 'perdida', 'patente', 'honorarios']):
                    origen = OrigenColumna.PERDIDA
                elif any(x in nom_lower for x in ['venta', 'ingreso', 'ganancia', 'utilidad', 'percibido']):
                    origen = OrigenColumna.GANANCIA
=======
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
>>>>>>> 6f7d24a (Recovery: save all work through Sprint 28.5)

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

    def parsear(self, path: Path) -> ResultadoParseo:
        ok, msg = validar_archivo(path)
        if not ok:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=False, rotacion_aplicada=0,
                advertencias=[f"VALIDACIÓN FALLIDA: {msg}"]
            )

        lineas, requirio_ocr, rotacion = self._extraer_lineas(path)

        if not lineas:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=requirio_ocr,
                rotacion_aplicada=rotacion,
                advertencias=["No se pudo extraer texto (ni nativo ni OCR)"]
            )

        lineas = [normalizar_codigo_ocr(l) for l in lineas]

        primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        muestra_montos = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra_montos)

<<<<<<< HEAD
=======
        # 3b. Detectar layout de columnas (solo si ENABLE_DYNAMIC_LAYOUT está activo)
        advertencias = []
        column_order: Optional[list[OrigenColumna]] = None
        layout_columns: Optional[list[str]] = None
        if ENABLE_DYNAMIC_LAYOUT:
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
>>>>>>> 6f7d24a (Recovery: save all work through Sprint 28.5)
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        for i, l in enumerate(lineas):
            c = parsear_linea(l, i, formato_codigo, separador, confianza,
                              column_order=column_order)
            if c:
                cuentas.append(c)

<<<<<<< HEAD
        cuadra_ok, totales, alertas_cuadre = verificar_cuadre_balance(cuentas)
        advertencias.extend(alertas_cuadre)
=======
        # 4b. Resolver tipo de cuenta (solo si ENABLE_ACCOUNT_TYPE_RESOLVER está activo)
        if ENABLE_ACCOUNT_TYPE_RESOLVER and cuentas:
            from parsers.account_type_resolver import AccountTypeResolver
            resolver = AccountTypeResolver()
            suma_conf = 0.0
            for c in cuentas:
                result = resolver.resolve(
                    origen_columna=c.origen_columna,
                    codigo=c.codigo,
                    layout_columns=layout_columns,
                )
                c.tipo_cuenta = result.account_type.value
                suma_conf += result.confidence
            prom_conf = suma_conf / len(cuentas)
            advertencias.append(
                f"AccountTypeResolver: {len(cuentas)} cuentas resueltas, "
                f"confianza promedio={prom_conf:.2f}"
            )
>>>>>>> 6f7d24a (Recovery: save all work through Sprint 28.5)

        if requirio_ocr:
            advertencias.append(
                f"Documento procesado vía OCR (rotación={rotacion}°). "
                "Confianza de extracción reducida a 0.75 — recomendar revisión humana."
            )

        return ResultadoParseo(
            archivo=path.name,
            formato_codigo=formato_codigo,
            separador_miles=separador,
            requirio_ocr=requirio_ocr,
            rotacion_aplicada=rotacion,
            cuentas=cuentas,
            advertencias=advertencias,
        )

    def _extraer_lineas(self, path: Path) -> tuple[list[str], bool, int]:
        lineas: list[str] = []

        with pdfplumber.open(path) as pdf:
            n_paginas = len(pdf.pages)
            for page in pdf.pages:
                texto = page.extract_text() or ""
                if texto.strip():
                    lineas.extend(texto.split('\n'))

        if lineas:
            return lineas, False, 0

        return self._ocr_documento(path, n_paginas)

    def _ocr_documento(self, path: Path, n_paginas: int) -> tuple[list[str], bool, int]:
        lineas: list[str] = []
        rotacion_global: Optional[int] = None

        pdftoppm_bin = shutil.which('pdftoppm') or 'pdftoppm'

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            for pagina in range(1, n_paginas + 1):
                prefix = tmpdir_path / f'pg{pagina}'
                subprocess.run(
                    [pdftoppm_bin, '-png', '-r', '250',
                     '-f', str(pagina), '-l', str(pagina),
                     str(path), str(prefix)],
                    capture_output=True, timeout=120
                )
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
                lineas.extend(texto.split('\n'))

        return lineas, True, rotacion_global or 0


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
