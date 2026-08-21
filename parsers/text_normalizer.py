"""Text Normalizer — capa ligera de higiene textual previa al análisis estructural.

Propósito:
    Recibir líneas extraídas por pdfplumber y devolver líneas normalizadas
    para que LayoutDetector y demás analizadores en DocumentAnalyzer trabajen
    sobre texto más limpio.

NO modifica el parseo de cuentas. NO se usa en ParserPDF.
Solo se integra en DocumentAnalyzer, entre extracción preliminar y análisis.

Reglas (orden de aplicación):
    1. Remover caracteres invisibles (zero-width, control)
    2. Colapsar múltiples espacios consecutivos
    3. Fusionar tokens mono-carácter separados por espacio (OCR spacing)
    4. Descartar líneas vacías resultantes
"""

from __future__ import annotations

import re
from typing import Optional as _Optional

INVISIBLE_RE = re.compile(r'[\u200b\u200c\u200d\ufeff\x00-\x08\x0b\x0c\x0e-\x1f]')
MULTI_SPACE_RE = re.compile(r'  +')
SINGLE_CHAR_ALPHA = re.compile(r'[a-záéíóúñA-ZÁÉÍÓÚÑ]')
OCR_SPACED_WORD_RE = re.compile(
    r'(?<!\w)(?:[a-záéíóúñA-ZÁÉÍÓÚÑ] ){2,}[a-záéíóúñA-ZÁÉÍÓÚÑ](?!\w)',
)
HAS_VOWEL_RE = re.compile(r'[aeiouáéíóúAEIOUÁÉÍÓÚ]', re.I)


def normalize_text_lines(
    lineas: list[str],
    *,
    max_actions: int = 10,
    merge_ocr_spacing: bool = True,
    strip_invisible: bool = True,
    collapse_spaces: bool = True,
    drop_empty: bool = True,
) -> tuple[list[str], list[str]]:
    """Normaliza líneas extraídas para mejorar detección estructural.

    Args:
        lineas: Lista de líneas de texto crudo.
        max_actions: Límite de acciones registradas (evita listas enormes).
        merge_ocr_spacing: Si True, fusiona tokens mono-carácter (OCR spacing).
        strip_invisible: Si True, remueve caracteres invisibles/control.
        collapse_spaces: Si True, colapsa múltiples espacios.
        drop_empty: Si True, descarta líneas vacías.

    Returns:
        (lineas_normalizadas, acciones)
    """
    acciones: list[str] = []
    acciones_set: set[str] = set()

    def _registrar(accion: str) -> None:
        if len(acciones) >= max_actions:
            return
        key = accion.rstrip("0123456789")
        if key in acciones_set:
            # incrementar contador interno
            for i, a in enumerate(acciones):
                if a == accion:
                    return
        acciones.append(accion)
        acciones_set.add(key)

    resultado: list[str] = []
    for linea in lineas:
        original = linea

        # 1. Remover caracteres invisibles
        if strip_invisible:
            linea = INVISIBLE_RE.sub('', linea)

        # 2. Fusionar tokens mono-carácter separados por espacio (OCR spacing)
        #    Se ejecuta ANTES de colapsar espacios para que espacios múltiples
        #    sirvan como delimitadores de palabra.
        if merge_ocr_spacing:
            linea = _fix_ocr_spacing(linea, _registrar)

        # 3. Colapsar múltiples espacios (después de OCR spacing)
        if collapse_spaces:
            antes = linea
            linea = MULTI_SPACE_RE.sub(' ', linea).strip()
            if len(linea) < len(antes):
                n_colapsados = sum(1 for _ in re.finditer(r'  +', antes))
                _registrar(f'collapsed_spaces:{n_colapsados}')

        # 4. Conservar si no está vacía
        if drop_empty and not linea.strip():
            _registrar('removed_empty_line')
            continue

        resultado.append(linea)

        if linea != original:
            _registrar('line_modified')

    return resultado, acciones


def _fix_ocr_spacing(
    linea: str,
    registrar: _Optional[callable] = None,
) -> str:
    """Fusiona 3+ caracteres alfa separados por espacio (OCR spacing).

    OCR produce "A c t i v o" en vez de "Activo". Usa regex para detectar
    secuencias de 3+ letras individuales separadas por espacio simple,
    preservando separaciones mayores (múltiples espacios) como límite
    natural entre palabras.

    Se ejecuta ANTES de colapsar espacios múltiples para que estos sirvan
    como delimitadores de palabra.

    Returns:
        Línea con secuencias fusionadas.
    """
    def _replacer(m: re.Match) -> str:
        fusion = m.group(0).replace(' ', '')
        if HAS_VOWEL_RE.search(fusion):
            return fusion
        return m.group(0)

    nueva = OCR_SPACED_WORD_RE.sub(_replacer, linea)
    if nueva != linea and registrar:
        # Estimar cuántas fusiones ocurrieron
        diff_tokens = len(linea.split()) - len(nueva.split())
        registrar(f'merged_ocr_spacing:{max(1, diff_tokens)}')
    return nueva
