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

Basado en el análisis de 12 balances tributarios reales:
  - 5 formatos estructurales distintos
  - 58% de PDFs son escaneados (requieren OCR)
  - 3 esquemas de código de cuenta (guion, punto, compacto)
  - separador de miles inconsistente entre emisores
"""

import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import pdfplumber
from PIL import Image


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


@dataclass
class CuentaRaw:
    linea: int
    codigo: Optional[str]
    nombre: str
    monto: Optional[float]
    origen_columna: OrigenColumna = OrigenColumna.DESCONOCIDO
    es_total: bool = False
    confianza_extraccion: float = 1.0  # baja si viene de OCR


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
    """
    Valida que el archivo no esté corrupto antes de procesarlo.
    Detecta casos como el PMGD.xlsx (44KB de ceros binarios).
    """
    if not path.exists():
        return False, f"Archivo no existe: {path}"

    size = path.stat().st_size
    if size == 0:
        return False, "Archivo vacío (0 bytes)"

    suffix = path.suffix.lower()

    if suffix in ('.xlsx', '.xlsm'):
        # xlsx es un zip; validar que lo sea
        try:
            with zipfile.ZipFile(path, 'r') as z:
                if 'xl/workbook.xml' not in z.namelist():
                    return False, "El .xlsx no contiene workbook.xml válido"
        except zipfile.BadZipFile:
            # Verificar si es todo ceros (corrupción común)
            with open(path, 'rb') as f:
                head = f.read(min(size, 4096))
            if head == b'\x00' * len(head):
                return False, (
                    f"Archivo corrupto: {size} bytes, todo ceros binarios. "
                    "Probablemente una descarga/exportación fallida. "
                    "Solicitar reexportación del archivo original."
                )
            return False, "Archivo .xlsx corrupto: no es un ZIP válido"

    elif suffix == '.xls':
        # xls legacy: header OLE2 esperado D0 CF 11 E0
        with open(path, 'rb') as f:
            header = f.read(8)
        ole2_sig = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
        if header != ole2_sig:
            return False, (
                f"Archivo .xls no tiene firma OLE2 válida (header={header.hex()}). "
                "Puede estar corrupto o ser otro formato con extensión incorrecta."
            )

    elif suffix == '.pdf':
        with open(path, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False, f"Archivo .pdf no tiene firma PDF válida (header={header})"

    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DE FORMATO DE CÓDIGO Y SEPARADOR DE MILES
# ─────────────────────────────────────────────────────────────────────────────

PATRON_GUION = re.compile(r'^\d+(-\d+){2,}$')
PATRON_PUNTO = re.compile(r'^\d+(\.\d+){2,}$')
PATRON_COMPACTO = re.compile(r'^\d{6,10}$')


def detectar_formato_codigo(codigos_muestra: list[str]) -> FormatoCodigo:
    """
    Recibe una muestra de strings que podrían ser códigos de cuenta
    y determina el formato dominante.
    """
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
    """
    Detecta si el separador de miles es '.' o ','.

    Heurística: en montos con ambos separadores (1.234.567,89 o 1,234,567.89)
    el separador decimal es siempre el último y tiene 1-2 dígitos después.
    En montos sin decimales (la mayoría en balances chilenos), se cuenta
    la frecuencia de grupos de 3 dígitos separados por '.' vs ','.
    """
    puntos_como_miles = 0
    comas_como_miles = 0

    for m in montos_muestra:
        m = m.strip()
        if not m or m in ('0', '-'):
            continue

        # Caso con ambos separadores: el último es decimal
        if '.' in m and ',' in m:
            if m.rfind('.') > m.rfind(','):
                comas_como_miles += 1   # 1,234,567.89 → coma es miles
            else:
                puntos_como_miles += 1  # 1.234.567,89 → punto es miles
            continue

        # Solo puntos: verificar patrón de miles (grupos de 3 dígitos)
        if '.' in m:
            partes = m.split('.')
            if all(len(p) == 3 for p in partes[1:]) and len(partes) > 1:
                puntos_como_miles += 1
            elif len(partes) == 2 and len(partes[-1]) in (1, 2):
                pass  # podría ser decimal, no contamos
            else:
                puntos_como_miles += 1

        # Solo comas: verificar patrón de miles
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
    """Convierte un string de monto al float correspondiente."""
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
        # punto = miles, coma = decimal
        v = v.replace('.', '').replace(',', '.')
    else:
        # coma = miles, punto = decimal
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


def detectar_rotacion_osd(img_path: Path) -> Optional[int]:
    """
    Usa Tesseract OSD para detectar la rotación necesaria (0 o 90).
    Retorna None si OSD no puede determinarlo (página con poco texto).
    """
    try:
        result = subprocess.run(
            ['/usr/local/bin/tesseract', str(img_path), '-', '--psm', '0', '-l', 'osd'],
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
    """
    Fallback cuando OSD falla: prueba OCR en 0° y 90°, cuenta cuántas
    palabras reconocibles (con vocales, longitud > 2) aparecen en cada caso.
    Retorna la rotación con más palabras válidas.
    """
    img = Image.open(img_path)
    mejor_rotacion = 0
    mejor_score = -1

    for rot in (0, 90):
        if rot == 0:
            test_img = img
        else:
            test_img = img.rotate(rot, expand=True)

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            test_img.save(tmp.name)
            tmp_path = Path(tmp.name)

        try:
            result = subprocess.run(
                ['/usr/local/bin/tesseract', str(tmp_path), '-', '--psm', '6', '-l', 'spa'],
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
    """Ejecuta OCR sobre una imagen, aplicando la rotación dada."""
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
            ['/usr/local/bin/tesseract', str(tmp_path), '-', '--psm', '6', '-l', 'spa'],
            capture_output=True, text=True, timeout=120,
            env={'TESSDATA_PREFIX': TESSDATA_DIR}
        )
        return result.stdout
    finally:
        if rotacion != 0:
            tmp_path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# PARSER DE LÍNEAS DE TEXTO → CUENTAS
# ─────────────────────────────────────────────────────────────────────────────

# Patrones de código según formato
PATRONES_CODIGO_LINEA = {
    FormatoCodigo.GUION:    re.compile(r'^(\d+(?:-\d+){2,})\s+(.+)'),
    FormatoCodigo.PUNTO:    re.compile(r'^(\d+(?:\.\d+){2,})\s+(.+)'),
    FormatoCodigo.COMPACTO: re.compile(r'^(\d{6,10})\s+(.+)'),
}

# Patrón para extraer todos los montos al final de una línea
PATRON_MONTOS = re.compile(r'(-?\(?[\d.,]{1,18}\)?)')

# OCR confunde frecuentemente 'o'/'O' con '0' en columnas de saldo cero,
# y a veces agrega basura de un carácter (':', '|', '.') al final de la línea.
_OCR_CERO = re.compile(r'^[oO]$')


def normalizar_token_ocr(token: str) -> str:
    """Normaliza un token candidato a monto: 'o'/'O' aislados → '0'."""
    if _OCR_CERO.match(token):
        return '0'
    return token

PATRON_TOTAL = re.compile(
    r'^(total(es)?|sub-?total(es)?|sumas?( iguales)?|resultado)\b',
    re.IGNORECASE
)

# OCR confunde '.' y ',' dentro de códigos de cuenta tipo X.XX.XX.XX,
# produciendo cosas como "1.1.01,01" o "1,1,08,05". Se detecta un prefijo
# de 3-5 grupos cortos de dígitos separados por '.' o ',' al inicio de la
# línea y se normaliza a '.' antes de cualquier otro procesamiento.
PATRON_CODIGO_OCR = re.compile(r'^(\d{1,2}[.,]){2,4}\d{1,2}(?=\s)')


def normalizar_codigo_ocr(linea: str) -> str:
    """Normaliza separadores de código de cuenta cuando vienen mezclados por OCR."""
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
) -> Optional[CuentaRaw]:
    """
    Parsea una línea de texto de balance en un CuentaRaw.
    Estrategia: separar código (si existe) + nombre, luego extraer
    todos los números de la cola de la línea como montos candidatos.
    """
    linea = linea.strip()
    if len(linea) < 4:
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
        # El formato global no se pudo determinar (común en OCR con mucho
        # texto de encabezado). Probar los 3 patrones por línea.
        for fmt in (FormatoCodigo.PUNTO, FormatoCodigo.GUION, FormatoCodigo.COMPACTO):
            m = PATRONES_CODIGO_LINEA[fmt].match(linea)
            if m:
                codigo = m.group(1)
                resto = m.group(2)
                break

    # Separar nombre de los montos: buscar todos los tokens numéricos
    # al final de la línea. Se permite descartar hasta 2 tokens finales
    # de basura OCR (símbolos sueltos como ':', '|', '.') antes de
    # empezar a contar montos.
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

    if PATRON_TOTAL.match(nombre):
        return CuentaRaw(
            linea=numero_linea, codigo=codigo, nombre=nombre,
            monto=None, es_total=True, confianza_extraccion=confianza_base
        )

    # El monto relevante para clasificación NO es Debe/Haber/Deudor/Acreedor
    # (columnas intermedias), sino el saldo ya clasificado en
    # Activo / Pasivo / Pérdida / Ganancia — que en TODOS los formatos
    # analizados son consistentemente las últimas 4 columnas numéricas.
    # Tomamos las últimas min(4, N) columnas y buscamos la primera no-cero,
    # en orden Activo→Pasivo→Pérdida→Ganancia.
    ULTIMAS_COLS = [OrigenColumna.ACTIVO, OrigenColumna.PASIVO,
                    OrigenColumna.PERDIDA, OrigenColumna.GANANCIA]

    monto_principal = None
    origen = OrigenColumna.DESCONOCIDO

    if montos_tokens:
        n = len(montos_tokens)
        k = min(4, n)
        cola = montos_tokens[-k:]
        etiquetas = ULTIMAS_COLS[-k:]

        for tok, et in zip(cola, etiquetas):
            val = parsear_monto(tok, separador_miles)
            if val is not None and val != 0:
                monto_principal = val
                origen = et
                break

        if monto_principal is None:
            # todas son cero: usar la primera de la cola con valor 0
            monto_principal = parsear_monto(cola[0], separador_miles)
            origen = etiquetas[0]

    return CuentaRaw(
        linea=numero_linea,
        codigo=codigo,
        nombre=nombre,
        monto=monto_principal,
        origen_columna=origen,
        es_total=False,
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

        # 1. Intentar texto nativo
        lineas, requirio_ocr, rotacion = self._extraer_lineas(path)

        if not lineas:
            return ResultadoParseo(
                archivo=path.name, formato_codigo=FormatoCodigo.SIN_CODIGO,
                separador_miles='.', requirio_ocr=requirio_ocr,
                rotacion_aplicada=rotacion,
                advertencias=["No se pudo extraer texto (ni nativo ni OCR)"]
            )

        # Normalizar separadores de código confundidos por OCR
        lineas = [normalizar_codigo_ocr(l) for l in lineas]

        # 2. Detectar formato de código con muestra de líneas
        primer_tokens = [l.split()[0] if l.split() else '' for l in lineas[:60]]
        formato_codigo = detectar_formato_codigo(primer_tokens)

        # 3. Detectar separador de miles con muestra de montos
        muestra_montos = []
        for l in lineas[:80]:
            muestra_montos.extend(PATRON_MONTOS.findall(l))
        separador = detectar_separador_miles(muestra_montos)

        # 4. Parsear todas las líneas
        confianza = 0.75 if requirio_ocr else 1.0
        cuentas = []
        advertencias = []
        for i, l in enumerate(lineas):
            c = parsear_linea(l, i, formato_codigo, separador, confianza)
            if c:
                cuentas.append(c)

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
        """
        Retorna (lineas_de_texto, requirio_ocr, rotacion_aplicada).
        Intenta texto nativo en todas las páginas; si ninguna tiene texto,
        recurre a OCR con detección de rotación.
        """
        lineas: list[str] = []

        with pdfplumber.open(path) as pdf:
            n_paginas = len(pdf.pages)
            for page in pdf.pages:
                texto = page.extract_text() or ""
                if texto.strip():
                    lineas.extend(texto.split('\n'))

        if lineas:
            return lineas, False, 0

        # Sin texto nativo → OCR
        return self._ocr_documento(path, n_paginas)

    def _ocr_documento(self, path: Path, n_paginas: int) -> tuple[list[str], bool, int]:
        lineas: list[str] = []
        rotacion_global: Optional[int] = None

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            for pagina in range(1, n_paginas + 1):
                prefix = tmpdir_path / f'pg{pagina}'
                subprocess.run(
                    ['pdftoppm', '-png', '-r', '250',
                     '-f', str(pagina), '-l', str(pagina),
                     str(path), str(prefix)],
                    capture_output=True, timeout=120
                )
                imgs = list(tmpdir_path.glob(f'pg{pagina}*.png'))
                if not imgs:
                    continue
                img_path = imgs[0]

                # Detectar rotación solo en la primera página, reutilizar
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
